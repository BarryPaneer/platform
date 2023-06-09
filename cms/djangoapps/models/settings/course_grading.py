import logging
import json
from base64 import b64encode
from datetime import timedelta
from hashlib import sha1

from contentstore.signals.signals import GRADING_POLICY_CHANGED
from eventtracking import tracker
from track.event_transaction_utils import create_new_event_transaction_id
from util.course import get_badge_url
from xmodule.modulestore.django import modulestore

from openedx.core.djangoapps.content.block_structure.api import clear_course_from_cache

GRADING_POLICY_CHANGED_EVENT_TYPE = 'edx.grades.grading_policy_changed'
log = logging.getLogger(__name__)


class CourseGradingModel(object):
    """
    Basically a DAO and Model combo for CRUD operations pertaining to grading policy.
    """
    # Within this class, allow access to protected members of client classes.
    # This comes up when accessing kvs data and caches during kvs saves and modulestore writes.
    def __init__(self, course_descriptor):
        self.graders = [
            CourseGradingModel.jsonize_grader(i, grader, course_descriptor.id) for i, grader in enumerate(
                course_descriptor.raw_grader)
        ]  # weights transformed to ints [0..100]
        self.grade_cutoffs = course_descriptor.grade_cutoffs
        self.grace_period = CourseGradingModel.convert_set_grace_period(course_descriptor)
        self.minimum_grade_credit = course_descriptor.minimum_grade_credit
        self.course_completion_rule = course_descriptor.course_completion_rule

    @classmethod
    def fetch(cls, course_key):
        """
        Fetch the course grading policy for the given course from persistence and return a CourseGradingModel.
        """
        descriptor = modulestore().get_course(course_key)
        model = cls(descriptor)
        return model

    @staticmethod
    def fetch_grader(course_key, index):
        """
        Fetch the course's nth grader
        Returns an empty dict if there's no such grader.
        """
        descriptor = modulestore().get_course(course_key)
        index = int(index)
        if len(descriptor.raw_grader) > index:
            return CourseGradingModel.jsonize_grader(index, descriptor.raw_grader[index], course_key)

        # return empty model
        else:
            return {"id": index,
                    "type": "",
                    "min_count": 0,
                    "drop_count": 0,
                    "short_label": None,
                    "weight": 0,
                    "threshold": 100,
                    "badge_url": ""
                    }

    @staticmethod
    def update_from_json(course_key, jsondict, user):
        """
        Decode the json into CourseGradingModel and save any changes. Returns the modified model.
        Probably not the usual path for updates as it's too coarse grained.
        """
        descriptor = modulestore().get_course(course_key)
        graders_parsed = [CourseGradingModel.parse_grader(jsonele) for jsonele in jsondict['graders']]
        for assignment in descriptor.raw_grader:
            if assignment not in graders_parsed:
                log.info('User {user_id} update or removed a grading rule: {rule}, course: {course_name}, '
                         'course_id: {course_id}'.format(user_id=user.id,
                                                         rule=assignment,
                                                         course_name=descriptor.display_name.encode('utf-8'),
                                                         course_id=course_key))
        for assignment in graders_parsed:
            if assignment not in descriptor.raw_grader:
                log.info('User {user_id} created or update a grading rule: {rule}, course: {course_name}, '
                         'course_id: {course_id}'.format(user_id=user.id,
                                                         rule=assignment,
                                                         course_name=descriptor.display_name.encode('utf-8'),
                                                         course_id=course_key))
        completion_rule = jsondict['course_completion_rule']
        if completion_rule != descriptor.course_completion_rule:
            log.info('User {user_id} edited course_completion_rule from {old_val} to {new_val}, '
                     'course: {course_name}, course_id: {course_id}'.format(user_id=user.id,
                                                                            old_val=descriptor.course_completion_rule,
                                                                            new_val=completion_rule,
                                                                            course_name=descriptor.display_name.encode('utf-8'),
                                                                            course_id=course_key))
        if jsondict['grade_cutoffs'] != descriptor.grade_cutoffs:
            log.info('User {user_id} edited grade_cutoffs from {old_val} to {new_val}, '
                     'course: {course_name}, course_id: {course_id}'.format(user_id=user.id,
                                                                            old_val=descriptor.grade_cutoffs,
                                                                            new_val=jsondict['grade_cutoffs'],
                                                                            course_name=descriptor.display_name.encode('utf-8'),
                                                                            course_id=course_key))

        descriptor.raw_grader = graders_parsed
        descriptor.course_completion_rule = completion_rule
        descriptor.grade_cutoffs = jsondict['grade_cutoffs']

        modulestore().update_item(descriptor, user.id)

        CourseGradingModel.update_grace_period_from_json(course_key, jsondict['grace_period'], user)

        CourseGradingModel.update_minimum_grade_credit_from_json(course_key, jsondict['minimum_grade_credit'], user)

        # if grader is renamed or deleted, we need to unbind it if it is assigned to a subsection
        new_grader_types = [i['type'] for i in graders_parsed]
        blocks = modulestore().get_items(course_key)
        sequentials = [b for b in blocks if b.category == 'sequential' and b.graded and
                       b.format not in new_grader_types]

        if sequentials:
            for s in sequentials:
                del s.format
                del s.graded
                modulestore().update_item(s, user.id)
            clear_course_from_cache(course_key)

        _grading_event_and_signal(course_key, user.id)

        return CourseGradingModel.fetch(course_key)

    @staticmethod
    def update_grader_from_json(course_key, grader, user):
        """
        Create or update the grader of the given type (string key) for the given course. Returns the modified
        grader which is a full model on the client but not on the server (just a dict)
        """
        descriptor = modulestore().get_course(course_key)

        # parse removes the id; so, grab it before parse
        index = int(grader.get('id', len(descriptor.raw_grader)))
        grader = CourseGradingModel.parse_grader(grader)

        if index < len(descriptor.raw_grader):
            descriptor.raw_grader[index] = grader
        else:
            descriptor.raw_grader.append(grader)

        modulestore().update_item(descriptor, user.id)
        _grading_event_and_signal(course_key, user.id)

        return CourseGradingModel.jsonize_grader(index, descriptor.raw_grader[index])

    @staticmethod
    def update_cutoffs_from_json(course_key, cutoffs, user):
        """
        Create or update the grade cutoffs for the given course. Returns sent in cutoffs (ie., no extra
        db fetch).
        """
        descriptor = modulestore().get_course(course_key)
        descriptor.grade_cutoffs = cutoffs

        modulestore().update_item(descriptor, user.id)
        _grading_event_and_signal(course_key, user.id)
        return cutoffs

    @staticmethod
    def update_grace_period_from_json(course_key, graceperiodjson, user):
        """
        Update the course's default grace period. Incoming dict is {hours: h, minutes: m} possibly as a
        grace_period entry in an enclosing dict. It is also safe to call this method with a value of
        None for graceperiodjson.
        """
        descriptor = modulestore().get_course(course_key)

        # Before a graceperiod has ever been created, it will be None (once it has been
        # created, it cannot be set back to None).
        if graceperiodjson is not None:
            if 'grace_period' in graceperiodjson:
                graceperiodjson = graceperiodjson['grace_period']

            grace_timedelta = timedelta(**graceperiodjson)
            descriptor.graceperiod = grace_timedelta

            modulestore().update_item(descriptor, user.id)

    @staticmethod
    def update_minimum_grade_credit_from_json(course_key, minimum_grade_credit, user):
        """Update the course's default minimum grade requirement for credit.

        Args:
            course_key(CourseKey): The course identifier
            minimum_grade_json(Float): Minimum grade value
            user(User): The user object

        """
        descriptor = modulestore().get_course(course_key)

        # 'minimum_grade_credit' cannot be set to None
        if minimum_grade_credit is not None:
            minimum_grade_credit = minimum_grade_credit

            descriptor.minimum_grade_credit = minimum_grade_credit
            modulestore().update_item(descriptor, user.id)

    @staticmethod
    def delete_grader(course_key, index, user):
        """
        Delete the grader of the given type from the given course.
        """
        descriptor = modulestore().get_course(course_key)

        index = int(index)
        if index < len(descriptor.raw_grader):
            del descriptor.raw_grader[index]
            # force propagation to definition
            descriptor.raw_grader = descriptor.raw_grader

        modulestore().update_item(descriptor, user.id)
        _grading_event_and_signal(course_key, user.id)

    @staticmethod
    def delete_grace_period(course_key, user):
        """
        Delete the course's grace period.
        """
        descriptor = modulestore().get_course(course_key)

        del descriptor.graceperiod

        modulestore().update_item(descriptor, user.id)

    @staticmethod
    def get_section_grader_type(location):
        descriptor = modulestore().get_item(location)
        return {
            "graderType": descriptor.format if descriptor.format is not None else 'notgraded',
            "location": unicode(location),
        }

    @staticmethod
    def update_section_grader_type(descriptor, grader_type, user):
        if grader_type is not None and grader_type != u'notgraded':
            descriptor.format = grader_type
            descriptor.graded = True
        else:
            del descriptor.format
            del descriptor.graded

        modulestore().update_item(descriptor, user.id)
        _grading_event_and_signal(descriptor.location.course_key, user.id)
        return {'graderType': grader_type}

    @staticmethod
    def convert_set_grace_period(descriptor):
        # 5 hours 59 minutes 59 seconds => converted to iso format
        rawgrace = descriptor.graceperiod
        if rawgrace:
            hours_from_days = rawgrace.days * 24
            seconds = rawgrace.seconds
            hours_from_seconds = int(seconds / 3600)
            hours = hours_from_days + hours_from_seconds
            seconds -= hours_from_seconds * 3600
            minutes = int(seconds / 60)
            seconds -= minutes * 60

            graceperiod = {'hours': 0, 'minutes': 0, 'seconds': 0}
            if hours > 0:
                graceperiod['hours'] = hours

            if minutes > 0:
                graceperiod['minutes'] = minutes

            if seconds > 0:
                graceperiod['seconds'] = seconds

            return graceperiod
        else:
            return None

    @staticmethod
    def parse_grader(json_grader):
        # manual to clear out kruft
        result = {"type": json_grader["type"],
                  "min_count": int(json_grader.get('min_count', 0)),
                  "drop_count": int(json_grader.get('drop_count', 0)),
                  "short_label": json_grader.get('short_label', None),
                  "weight": float(json_grader.get('weight', 0)) / 100.0,
                  "threshold": float(json_grader.get('threshold', 100)) / 100.0,
                  "badge_url": json_grader.get('badge_url', '')
                  }

        return result

    @staticmethod
    def jsonize_grader(i, grader, course=None):
        # Warning: converting weight to integer might give unwanted results due
        # to the reason how floating point arithmetic works
        # e.g, "0.29 * 100 = 28.999999999999996"
        return {
            "id": i,
            "type": grader["type"],
            "min_count": grader.get('min_count', 0),
            "drop_count": grader.get('drop_count', 0),
            "short_label": grader.get('short_label', ""),
            "weight": grader.get('weight', 0) * 100,
            "threshold": grader.get('threshold', 1) * 100,
            "badge_url": grader.get('badge_url', '') if course is None else get_badge_url(course, grader)
        }


def _grading_event_and_signal(course_key, user_id):
    name = GRADING_POLICY_CHANGED_EVENT_TYPE
    course = modulestore().get_course(course_key)

    data = {
        "course_id": unicode(course_key),
        "user_id": unicode(user_id),
        "grading_policy_hash": unicode(hash_grading_policy(course.grading_policy)),
        "event_transaction_id": unicode(create_new_event_transaction_id()),
        "event_transaction_type": GRADING_POLICY_CHANGED_EVENT_TYPE,
    }
    tracker.emit(name, data)
    GRADING_POLICY_CHANGED.send(sender=CourseGradingModel, user_id=user_id, course_key=course_key)


def hash_grading_policy(grading_policy):
    ordered_policy = json.dumps(
        grading_policy,
        separators=(',', ':'),  # Remove spaces from separators for more compact representation
        sort_keys=True,
    )
    return b64encode(sha1(ordered_policy).digest())
