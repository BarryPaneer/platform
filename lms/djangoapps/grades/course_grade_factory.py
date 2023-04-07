"""
Course Grade Factory Class
"""
from __future__ import division
from collections import namedtuple
from datetime import datetime
from logging import getLogger

from django.utils import timezone
import dogstats_wrapper as dog_stats_api
from six import text_type

from courseware.models import StudentModule
from lms.djangoapps.certificates.models import GeneratedCertificate
from openedx.core.djangoapps.request_cache import clear_cache
from openedx.core.djangoapps.signals.signals import COURSE_GRADE_CHANGED, COURSE_GRADE_NOW_PASSED
from openedx.core.lib.gating.api import get_subsection_completion_percentage_with_gradebook_edit
from student.models import CourseEnrollment
from xmodule.modulestore.django import modulestore
from util.course import get_badge_url

from .config import assume_zero_if_absent, should_persist_grades
from .course_data import CourseData
from .course_grade import CourseGrade, ZeroCourseGrade
from .models import PersistentCourseGrade, PersistentCourseProgress, PersistentSubsectionGradeOverride, prefetch
from lms.djangoapps.program_enrollments.models import ProgramCourseEnrollment


log = getLogger(__name__)
CACHE_NAMESPACE = u"grades.models.VisibleBlocks"


class CourseGradeFactory(object):
    """
    Factory class to create Course Grade objects.
    """
    GradeResult = namedtuple('GradeResult', ['student', 'course_grade', 'error'])

    def read(
            self,
            user,
            course=None,
            collected_block_structure=None,
            course_structure=None,
            course_key=None,
            create_if_needed=True,
            clear_request_cache=False
    ):
        """
        Returns the CourseGrade for the given user in the course.
        Reads the value from storage.
        If not in storage, returns a ZeroGrade if ASSUME_ZERO_GRADE_IF_ABSENT.
        Else if create_if_needed, computes and returns a new value.
        Else, returns None.

        At least one of course, collected_block_structure, course_structure,
        or course_key should be provided.
        """
        course_data = CourseData(user, course, collected_block_structure, course_structure, course_key)
        try:
            return self._read(user, course_data)
        except PersistentCourseGrade.DoesNotExist:
            if assume_zero_if_absent(course_data.course_key):
                return self._create_zero(user, course_data)
            elif create_if_needed:
                return self._update(user, course_data, force_update_subsections=True)
            else:
                return None

    def update(
            self,
            user,
            course=None,
            collected_block_structure=None,
            course_structure=None,
            course_key=None,
            force_update_subsections=False,
            clear_request_cache=False,
    ):
        """
        Computes, updates, and returns the CourseGrade for the given
        user in the course.

        At least one of course, collected_block_structure, course_structure,
        or course_key should be provided.
        """
        course_data = CourseData(user, course, collected_block_structure, course_structure, course_key)
        enrollment = CourseEnrollment.get_enrollment(user, course_data.course_key)
        self.check_badge_success(user, course_data.course_key, enrollment)
        return self._update(
            user,
            course_data,
            force_update_subsections=force_update_subsections,
            clear_request_cache=clear_request_cache
        )

    def iter(
            self,
            users,
            course=None,
            collected_block_structure=None,
            course_key=None,
            force_update=False,
            clear_request_cache=False
    ):
        """
        Given a course and an iterable of students (User), yield a GradeResult
        for every student enrolled in the course.  GradeResult is a named tuple of:

            (student, course_grade, err_msg)

        If an error occurred, course_grade will be None and err_msg will be an
        exception message. If there was no error, err_msg is an empty string.
        """
        # Pre-fetch the collected course_structure (in _iter_grade_result) so:
        # 1. Correctness: the same version of the course is used to
        #    compute the grade for all students.
        # 2. Optimization: the collected course_structure is not
        #    retrieved from the data store multiple times.
        course_data = CourseData(
            user=None, course=course, collected_block_structure=collected_block_structure, course_key=course_key,
        )
        stats_tags = [u'action:{}'.format(course_data.course_key)]
        for user in users:
            with dog_stats_api.timer('lms.grades.CourseGradeFactory.iter', tags=stats_tags):
                yield self._iter_grade_result(user, course_data, force_update, clear_request_cache)

    def _iter_grade_result(self, user, course_data, force_update, clear_request_cache=False):
        try:
            kwargs = {
                'user': user,
                'course': course_data.course,
                'collected_block_structure': course_data.collected_structure,
                'course_key': course_data.course_key,
                'clear_request_cache': clear_request_cache
            }
            if force_update:
                kwargs['force_update_subsections'] = True

            method = CourseGradeFactory().update if force_update else CourseGradeFactory().read
            course_grade = method(**kwargs)
            return self.GradeResult(user, course_grade, None)
        except Exception as exc:  # pylint: disable=broad-except
            # Keep marching on even if this student couldn't be graded for
            # some reason, but log it for future reference.
            log.exception(
                'Cannot grade student %s in course %s because of exception: %s',
                user.id,
                course_data.course_key,
                text_type(exc)
            )
            return self.GradeResult(user, None, exc)

    @staticmethod
    def _create_zero(user, course_data):
        """
        Returns a ZeroCourseGrade object for the given user and course.
        """
        log.debug(u'Grades: CreateZero, %s, User: %s', unicode(course_data), user.id)
        return ZeroCourseGrade(user, course_data)

    @staticmethod
    def _read(user, course_data):
        """
        Returns a CourseGrade object based on stored grade information
        for the given user and course.
        """
        if not should_persist_grades(course_data.course_key):
            raise PersistentCourseGrade.DoesNotExist

        persistent_grade = PersistentCourseGrade.read(user.id, course_data.course_key)
        log.info(u'Grades: Read, %s, User: %s, %s', unicode(course_data), user.id, persistent_grade)

        return CourseGrade(
            user,
            course_data,
            persistent_grade.percent_grade,
            persistent_grade.letter_grade,
            persistent_grade.letter_grade is not u''
        )

    @staticmethod
    def _update(user, course_data, force_update_subsections=False, clear_request_cache=False):
        """
        Computes, saves, and returns a CourseGrade object for the
        given user and course.
        Sends a COURSE_GRADE_CHANGED signal to listeners and a
        COURSE_GRADE_NOW_PASSED if learner has passed course.
        """
        should_persist = should_persist_grades(course_data.course_key)

        if should_persist and force_update_subsections:
            prefetch(user, course_data.course_key)

        course_grade = CourseGrade(
            user,
            course_data,
            force_update_subsections=force_update_subsections
        )
        course_grade = course_grade.update()

        should_persist = should_persist and course_grade.attempted
        if should_persist:
            course_grade._subsection_grade_factory.bulk_create_unsaved()
            PersistentCourseGrade.update_or_create(
                user_id=user.id,
                course_id=course_data.course_key,
                course_version=course_data.version,
                course_edited_timestamp=course_data.edited_on,
                grading_policy_hash=course_data.grading_policy_hash,
                percent_grade=course_grade.percent,
                letter_grade=course_grade.letter_grade or "",
                passed=course_grade.passed,
            )

        COURSE_GRADE_CHANGED.send_robust(
            sender=None,
            user=user,
            course_grade=course_grade,
            course_key=course_data.course_key,
            deadline=course_data.course.end,
        )
        if course_grade.passed:
            COURSE_GRADE_NOW_PASSED.send(
                sender=CourseGradeFactory,
                user=user,
                course_id=course_data.course_key,
            )

        log.info(
            u'Grades: Update, %s, User: %s, %s, persisted: %s',
            course_data.full_string(), user.id, course_grade, should_persist,
        )

        if clear_request_cache:
            clear_cache(CACHE_NAMESPACE)

        return course_grade

    def update_course_completion_percentage(self, course_key, user, course_grade=None,
                                            enrollment=None, force_update_grade=False):
        from triboo_analytics.models import LeaderBoard
        course_usage_key = modulestore().make_course_usage_key(course_key)
        overrides = PersistentSubsectionGradeOverride.objects.filter(
            grade__user_id=user.id,
            grade__course_id=course_key,
        ).select_related('grade')
        overridden_subsection_keys = [i.grade.usage_key for i in overrides]
        overridden_subsection_keys = list(set(overridden_subsection_keys))
        percent_progress = get_subsection_completion_percentage_with_gradebook_edit(
            course_usage_key, user, overrides=overridden_subsection_keys
        )
        log.info(u'Course Progress Calculate: %s, User: %s, Progress: %s',
                 unicode(course_key), user.id, percent_progress)
        if not enrollment:
            enrollment = CourseEnrollment.get_enrollment(user, course_key)

        # in some cases, we call the update_progress function, but the learner's enrollment
        # somehow doesn't exit any more (deleted for some reason), we should end this function
        # asap, not causing attribute error.
        if enrollment is None:
            pass
        else:
            should_be_completed = False
            if percent_progress == 100:
                should_be_completed = True
            elif overrides.exists() or modulestore().get_course(course_key).course_completion_rule == 'minimum':
                if force_update_grade:
                    course_grade = self.update(user, course_key=course_key)
                else:
                    if not course_grade:
                        course_grade = self.read(user, course_key=course_key)
                passed = course_grade.passed
                if passed:
                    should_be_completed = True

            if should_be_completed:
                if not enrollment.completed:
                    completion_date = datetime.today()
                    enrollment.completed = completion_date
                    enrollment.save()
                    log.info(
                        "Create completion date for user id %d / %s: %s" % (user.id, course_key, completion_date))
                    affected_programs_number = ProgramCourseEnrollment.update_programs_completion_status(
                        user,
                        completed_course_id=course_key
                    )
                    leader_board, _ = LeaderBoard.objects.get_or_create(user=user)
                    leader_board.course_completed = leader_board.course_completed + 1
                    leader_board.learning_path_completed += affected_programs_number
                    leader_board.save()
                    log.info(
                        "updated course completed & learning_path_completed(+{affected_programs}) of leaderboard score "
                        "for user: {user_id}, course_id: {course_id}".format(
                            affected_programs=affected_programs_number,
                            user_id=user.id,
                            course_id=course_key
                        )
                    )
            else:
                if enrollment.completed:
                    affected_programs_number = ProgramCourseEnrollment.update_programs_completion_status(
                        user,
                        uncompleted_course_id=course_key
                    )
                    enrollment.completed = None
                    enrollment.save()
                    log.info("Delete completion date for user id %d / %s" % (user.id, course_key))
                    leader_board, _ = LeaderBoard.objects.get_or_create(user=user)
                    if leader_board.course_completed > 0:
                        leader_board.course_completed = leader_board.course_completed - 1
                        if leader_board.learning_path_completed > 0:
                            new_number = leader_board.learning_path_completed - affected_programs_number
                            leader_board.learning_path_completed = new_number if new_number >= 0 else 0
                        leader_board.save()
                        log.info(
                            "updated course completed (-1) & learning_path_completed(-{affected_programs}) of leaderboard score "
                            "for user: {user_id}, course_id: {course_id}".format(
                                affected_programs=affected_programs_number,
                                user_id=user.id,
                                course_id=course_key
                            )
                        )
                    cert = GeneratedCertificate.objects.filter(
                        user=user, course_id=course_key, status='downloadable'
                    )
                    if cert.exists():
                        cert.delete()

        if percent_progress < 100 and round(percent_progress / 100, 2) == 1:
            rounded_progress = 0.99
        else:
            rounded_progress = round(percent_progress / 100, 2)
        if should_persist_grades(course_key):
            PersistentCourseProgress.update_or_create(
                user_id=user.id,
                course_id=course_key,
                percent_progress=rounded_progress
            )
            # modified by yang
            self.check_badge_success(user, course_key, enrollment)
        return rounded_progress


    def get_course_completion_percentage(self, user, course_key, course_grade=None, enrollment=None):
        """
        return the completed percentage of the given course
        """
        try:
            persistent_progress = PersistentCourseProgress.read(user.id, course_key)
            log.info(u'Course Progress Read: %s, User: %s', unicode(course_key), user.id)
            return persistent_progress.percent_progress
        except PersistentCourseProgress.DoesNotExist:
            # check if user ever interacts with course before
            if StudentModule.objects.filter(student=user, course_id=course_key).exists():
                return self.update_course_completion_percentage(
                    course_key, user, course_grade=course_grade, enrollment=enrollment)
            else:
                return 0


    def get_nb_trophies_possible(self, course):
        """
        return the number of badges of the given course
        course :: CourseDescriptor
        """
        nb_trophies_possible = 0
        grading_rules = course.raw_grader
        for rule in grading_rules:
            nb_trophies_possible += rule.get('min_count', 0)
        return nb_trophies_possible


    def get_nb_trophies_earned(self, user, course, grade_summary=None):
         """
         Get the specific course's badges earned for the user.
         """
         if not grade_summary:
             grade_summary = self.read(user, course)
         if not grade_summary:
             return

         nb_trophies_earned = 0
         grading_rules_dict = {}
         grading_rules = course.raw_grader
         for rule in grading_rules:
             if not rule.get('threshold'):
                 rule['threshold'] = 1
             grading_rules_dict.update({
                 rule.get('type'): rule
             })

         for subsection_grade in grade_summary.grader_result['section_breakdown']:
             grade_type = subsection_grade['category']
             if subsection_grade['percent'] >= grading_rules_dict[grade_type]['threshold']:
                 nb_trophies_earned += 1

         return nb_trophies_earned

    def get_user_success_badges(self, user, course_ids):
         """
         Get the specific course's badges earned for the user.
         """
         from triboo_analytics.models import LearnerBadgeSuccess

         return LearnerBadgeSuccess.objects.filter(
             user=user, badge__course_id__in=course_ids
         ).count()


    def check_badge_success(self, user, course_key, enrollment):
        from triboo_analytics.models import Badge, LearnerBadgeSuccess

        course = modulestore().get_course(course_key)
        if not course:
            log.error("course_id=%s returned Http404" % course_key)
            return

        progress = self.get_progress(user, course, enrollment=enrollment)
        i = 0
        for chapter in progress['trophies_by_chapter']:
            for trophy in chapter['trophies']:
                i += 1
                badge_hash = Badge.get_badge_hash(trophy['section_format'],
                                                  chapter['url'],
                                                  trophy['section_url'])
                badge = Badge.objects.filter(course_id=course_key, badge_hash=badge_hash).first()
                if trophy['result'] >= trophy['threshold']:
                    if not badge:
                        badge, _ = Badge.objects.update_or_create(course_id=course_key,
                                                               badge_hash=badge_hash,
                                                               defaults={'order': i,
                                                                         'grading_rule': trophy['section_format'],
                                                                         'section_name': trophy['section_name'],
                                                                         'threshold': (trophy['threshold'] * 100)})
                    success = LearnerBadgeSuccess.objects.filter(user=user, badge=badge).first()
                    if not success:
                        LearnerBadgeSuccess.objects.update_or_create(user=user,
                                                                     badge=badge,
                                                                     defaults={'success_date': timezone.now()})
                else:
                    if badge:
                        success = LearnerBadgeSuccess.objects.filter(user=user, badge=badge).first()
                        if success:
                            success.delete()


    def get_progress(self, user, course, progress=None, grade_summary=None, enrollment=None, clear_request_cache=False):
        course_key = course.id
        if not grade_summary:
            grade_summary = self.read(user, course, clear_request_cache=clear_request_cache)
        if not grade_summary:
            return

        nb_trophies_attempted = 0
        nb_trophies_earned = 0
        nb_trophies_possible = 0
        current_total_weight = 0
        trophies_by_chapter = []

        grading_rules = course.raw_grader
        grading_rules_dict = {}
        for rule in grading_rules:
            nb_trophies_possible += rule.get('min_count', 0)
            rule['available_count'] = rule.get('min_count') - rule.get('drop_count')
            if not rule.get('threshold'):
                rule['threshold'] = 1
            grading_rules_dict.update({
                rule.get('type'): rule
            })

        chapter_grades = grade_summary.chapter_grades.values()
        for chapter in chapter_grades:
            trophies = []
            for section in chapter['sections']:
                if section.graded and grading_rules_dict:
                    grader = grading_rules_dict[section.format]
                    trophy = {
                        'result': section.percent_graded,
                        'attempted': section.attempted_graded or section.override is not None,
                        'section_format': section.format,
                        'section_name': section.display_name,
                        'section_url': section.url_name,
                        'threshold': grader['threshold'],
                        'trophy_img': get_badge_url(course_key, grader)
                    }
                    trophy['passed'] = trophy['result'] >= trophy['threshold']
                    trophies.append(trophy)
                    if trophy['attempted']:
                        nb_trophies_attempted += 1
                        if grader['available_count'] > 0:
                            current_total_weight += grader['weight'] / (grader['min_count'] - grader['drop_count'])
                            grader['available_count'] += -1
                        if trophy['passed']:
                            nb_trophies_earned += 1
            if len(trophies) > 0:
                trophies_by_chapter.append({
                    'url': chapter['url_name'],
                    'chapter_name': chapter['display_name'],
                    'trophies': trophies
                })
        current_total_weight = round(current_total_weight, 2)
        if current_total_weight > 0:
            current_score = round(grade_summary.percent * 100 / current_total_weight)
            # sometime the round function doesn't work as expected
            if current_score > 100:
                current_score = 100
        else:
            current_score = 0

        if not progress:
            progress = self.get_course_completion_percentage(
                user, course_key, course_grade=grade_summary, enrollment=enrollment)

        return {
            'current_score': current_score,
            'is_course_passed': grade_summary.passed,
            'nb_trophies_attempted': nb_trophies_attempted,
            'nb_trophies_earned': nb_trophies_earned,
            'nb_trophies_possible': nb_trophies_possible,
            'trophies_by_chapter': trophies_by_chapter,
            'progress': progress
        }


def get_total_score_possible(course_key, user, course_grade=None):
    if not course_grade:
        course_grade = CourseGradeFactory().read(user, course_key=course_key)
    chapter_grades = course_grade.chapter_grades
    possible_score = 0
    chapter_result = {}
    for chapter_id, chapter in chapter_grades.items():
        chapter_block = modulestore().get_item(chapter_id)
        now = datetime.now()
        start_date = chapter_block.start
        if start_date:
            visible = now >= chapter_block.start.replace(tzinfo=None)
        else:
            visible = True
        if not visible:
            continue
        chapter_result[chapter_id] = {"possible_score": 0, "subsections": []}
        score = 0
        for section in chapter['sections']:
            if section.all_total.possible > 0:
                score += section.all_total.possible
                chapter_result[chapter_id]["subsections"].append(section.location)
        chapter_result[chapter_id]["possible_score"] = score
        possible_score += score
    return chapter_result, possible_score


def calculate_eucalyptus_progress(possible_all, subsection_grades):
    possible_graded = 0
    for i in subsection_grades:
        possible_graded += i.possible_graded
    if possible_all == 0:
        return 0
    return float(possible_graded) / float(possible_all)
