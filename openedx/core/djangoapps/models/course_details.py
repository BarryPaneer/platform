# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""
CourseDetails
"""
import re
import logging

from django.conf import settings
from django.utils.translation import ugettext as _

from openedx.core.lib.courses import course_image_url
from xmodule.fields import Date
from xmodule.modulestore.exceptions import ItemNotFoundError
from xmodule.modulestore.django import modulestore


# This list represents the attribute keys for a course's 'about' info.
# Note: The 'video' attribute is intentionally excluded as it must be
# handled separately; its value maps to an alternate key name.
ABOUT_ATTRIBUTES = [
    'syllabus',
    'title',
    'subtitle',
    'duration',
    'description',
    'short_description',
    'overview',
    'effort',
    'entrance_exam_enabled',
    'entrance_exam_id',
    'entrance_exam_minimum_score_pct',
    'about_sidebar_html',
]


class CourseDetails(object):
    """
    An interface for extracting course information from the modulestore.
    """
    def __init__(self, org, course_id, run):
        # still need these for now b/c the client's screen shows these 3
        # fields
        self.org = org
        self.course_id = course_id
        self.run = run
        self.language = None
        self.course_category = None
        self.course_country = []
        self.vendor = []
        self.start_date = None  # 'start'
        self.end_date = None  # 'end'
        self.enrollment_start = None
        self.enrollment_end = None
        self.syllabus = None  # a pdf file asset
        self.title = ""
        self.subtitle = ""
        self.duration = ""
        self.description = ""
        self.short_description = ""
        self.overview = ""  # html to render as the overview
        self.about_sidebar_html = ""
        self.intro_video = None  # a video pointer
        self.effort = None  # hours/week
        self.license = "all-rights-reserved"  # default course license is all rights reserved
        self.course_image_name = ""
        self.course_image_asset_path = ""  # URL of the course image
        self.banner_image_name = ""
        self.banner_image_asset_path = ""
        self.video_thumbnail_image_name = ""
        self.video_thumbnail_image_asset_path = ""
        self.pre_requisite_courses = []  # pre-requisite courses
        self.entrance_exam_enabled = ""  # is entrance exam enabled
        self.entrance_exam_id = ""  # the content location for the entrance exam
        self.entrance_exam_minimum_score_pct = settings.FEATURES.get(
            'ENTRANCE_EXAM_MIN_SCORE_PCT',
            '50'
        )  # minimum passing score for entrance exam content module/tree,
        self.self_paced = None
        self.learning_info = []
        self.instructor_info = []
        self.reminder_info = []
        self.course_finish_days = ''
        self.course_re_enroll_time = ''
        self.re_enroll_time_unit = 'month'
        self.periodic_reminder_day = 1
        self.course_order = None
        self.course_mandatory_enabled = ''
        self.enrollment_learning_groups = []  # used for automatically enrollment course by user learning group
        self.display_coursenumber = ''
        self.catalog_visibility = 'both'
        self.is_new = False
        self.anderspink_boards = None

    @classmethod
    def fetch_about_attribute(cls, course_key, attribute):
        """
        Retrieve an attribute from a course's "about" info
        """
        if attribute not in ABOUT_ATTRIBUTES + ['video']:
            raise ValueError("'{0}' is not a valid course about attribute.".format(attribute))

        usage_key = course_key.make_usage_key('about', attribute)
        try:
            value = modulestore().get_item(usage_key).data
        except ItemNotFoundError:
            value = None
        return value

    @classmethod
    def fetch(cls, course_key):
        """
        Fetch the course details for the given course from persistence
        and return a CourseDetails model.
        """
        return cls.populate(modulestore().get_course(course_key))

    @classmethod
    def populate(cls, course_descriptor):
        """
        Returns a fully populated CourseDetails model given the course descriptor
        """
        course_key = course_descriptor.id
        course_details = cls(course_key.org, course_key.course, course_key.run)
        course_details.start_date = course_descriptor.start
        course_details.end_date = course_descriptor.end
        course_details.certificate_available_date = course_descriptor.certificate_available_date
        course_details.enrollment_start = course_descriptor.enrollment_start
        course_details.enrollment_end = course_descriptor.enrollment_end
        course_details.pre_requisite_courses = course_descriptor.pre_requisite_courses
        course_details.course_image_name = course_descriptor.course_image
        course_details.course_image_asset_path = course_image_url(course_descriptor, 'course_image')
        course_details.banner_image_name = course_descriptor.banner_image
        course_details.banner_image_asset_path = course_image_url(course_descriptor, 'banner_image')
        course_details.video_thumbnail_image_name = course_descriptor.video_thumbnail_image
        course_details.video_thumbnail_image_asset_path = course_image_url(course_descriptor, 'video_thumbnail_image')
        course_details.language = course_descriptor.language
        course_details.course_category = course_descriptor.course_category
        course_details.course_country = course_descriptor.course_country
        course_details.vendor = course_descriptor.vendor
        course_details.self_paced = course_descriptor.self_paced
        course_details.learning_info = course_descriptor.learning_info
        course_details.instructor_info = course_descriptor.instructor_info
        course_details.reminder_info = course_descriptor.reminder_info
        course_details.course_finish_days = course_descriptor.course_finish_days
        course_details.course_re_enroll_time = course_descriptor.course_re_enroll_time
        course_details.re_enroll_time_unit = course_descriptor.re_enroll_time_unit
        course_details.periodic_reminder_day = course_descriptor.periodic_reminder_day
        course_details.course_order = course_descriptor.course_order
        course_details.course_mandatory_enabled = course_descriptor.course_mandatory_enabled
        course_details.enrollment_learning_groups = course_descriptor.enrollment_learning_groups
        course_details.display_coursenumber = course_descriptor.display_coursenumber
        course_details.catalog_visibility = course_descriptor.catalog_visibility
        course_details.is_new = course_descriptor.is_new
        course_details.anderspink_boards = course_descriptor.anderspink_boards

        # Default course license is "All Rights Reserved"
        course_details.license = getattr(course_descriptor, "license", "all-rights-reserved")

        course_details.intro_video = cls.fetch_youtube_video_id(course_key)

        for attribute in ABOUT_ATTRIBUTES:
            value = cls.fetch_about_attribute(course_key, attribute)
            if value is not None:
                setattr(course_details, attribute, value)
            elif not course_details.title and course_descriptor.display_name:
                ### Not sure Why we took `Course.Title` from `def fetch_about_attribute()` Bypass `course_descriptor.display_name`.
                ### But sometimes we still got empty Course.Title from `fetch_about_attribute()`.
                ### So I added this line.
                course_details.title = course_descriptor.display_name

        return course_details

    @classmethod
    def fetch_youtube_video_id(cls, course_key):
        """
        Returns the course about video ID.
        """
        raw_video = cls.fetch_about_attribute(course_key, 'video')
        if raw_video:
            return cls.parse_video_tag(raw_video)

    @classmethod
    def fetch_video_url(cls, course_key):
        """
        Returns the course about video URL.
        """
        video_id = cls.fetch_youtube_video_id(course_key)
        if video_id:
            return "http://www.youtube.com/watch?v={0}".format(video_id)

    @classmethod
    def update_about_item(cls, course, about_key, data, user_id, store=None):
        """
        Update the about item with the new data blob. If data is None,
        then delete the about item.
        """
        temploc = course.id.make_usage_key('about', about_key)
        store = store or modulestore()
        if data is None:
            try:
                store.delete_item(temploc, user_id)
            # Ignore an attempt to delete an item that doesn't exist
            except ValueError:
                pass
        else:
            try:
                about_item = store.get_item(temploc)
            except ItemNotFoundError:
                about_item = store.create_xblock(course.runtime, course.id, 'about', about_key)
            if about_item.data != data:
                logging.info('User {user_id} edited {attr} from "{old_val}" to "{new_val}", '
                             'course_name: {course_name}, course_id: {course_id}'.format(
                    user_id=user_id, attr=about_key, old_val=about_item.data, new_val=data,
                    course_name=course.display_name, course_id=course.id
                ))
                about_item.data = data
            store.update_item(about_item, user_id, allow_not_found=True)

    @classmethod
    def update_about_video(cls, course, video_id, user_id):
        """
        Updates the Course's about video to the given video ID.
        """
        recomposed_video_tag = CourseDetails.recompose_video_tag(course.id, video_id)
        cls.update_about_item(course, 'video', recomposed_video_tag, user_id)

    @classmethod
    def update_from_json(cls, course_key, jsondict, user, request=None):  # pylint: disable=too-many-statements
        """
        Decode the json into CourseDetails and save any changed attrs to the db
        """
        module_store = modulestore()
        descriptor = module_store.get_course(course_key)
        edited_fields = {}
        dirty = False

        # In the descriptor's setter, the date is converted to JSON
        # using Date's to_json method. Calling to_json on something that
        # is already JSON doesn't work. Since reaching directly into the
        # model is nasty, convert the JSON Date to a Python date, which
        # is what the setter expects as input.
        date = Date()
        if 'start_date' in jsondict:
            converted = date.from_json(jsondict['start_date'])
        else:
            converted = None
        if converted != descriptor.start:
            dirty = True
            edited_fields['start_date'] = (descriptor.start, converted)
            descriptor.start = converted

        if 'end_date' in jsondict:
            converted = date.from_json(jsondict['end_date'])
        else:
            converted = None

        if converted != descriptor.end:
            dirty = True
            edited_fields['end_date'] = (descriptor.end, converted)
            descriptor.end = converted

        if 'enrollment_start' in jsondict:
            converted = date.from_json(jsondict['enrollment_start'])
        else:
            converted = None

        if converted != descriptor.enrollment_start:
            dirty = True
            edited_fields['enrollment_start'] = (descriptor.enrollment_start, converted)
            descriptor.enrollment_start = converted

        if 'enrollment_end' in jsondict:
            converted = date.from_json(jsondict['enrollment_end'])
        else:
            converted = None

        if converted != descriptor.enrollment_end:
            dirty = True
            edited_fields['enrollment_end'] = (descriptor.enrollment_end, converted)
            descriptor.enrollment_end = converted

        if 'certificate_available_date' in jsondict:
            converted = date.from_json(jsondict['certificate_available_date'])
        else:
            converted = None

        if converted != descriptor.certificate_available_date:
            dirty = True
            edited_fields['certificate_available_date'] = (descriptor.certificate_available_date, converted)
            descriptor.certificate_available_date = converted

        if 'course_image_name' in jsondict and jsondict['course_image_name'] != descriptor.course_image:
            edited_fields['course_image_name'] = (descriptor.course_image, jsondict['course_image_name'])
            descriptor.course_image = jsondict['course_image_name']
            dirty = True

        if 'banner_image_name' in jsondict and jsondict['banner_image_name'] != descriptor.banner_image:
            edited_fields['banner_image_name'] = (descriptor.banner_image, jsondict['banner_image_name'])
            descriptor.banner_image = jsondict['banner_image_name']
            dirty = True

        if 'video_thumbnail_image_name' in jsondict \
                and jsondict['video_thumbnail_image_name'] != descriptor.video_thumbnail_image:
            edited_fields['video_thumbnail_image_name'] = (descriptor.video_thumbnail_image,
                                                           jsondict['video_thumbnail_image_name'])
            descriptor.video_thumbnail_image = jsondict['video_thumbnail_image_name']
            dirty = True

        if 'pre_requisite_courses' in jsondict \
                and sorted(jsondict['pre_requisite_courses']) != sorted(descriptor.pre_requisite_courses):
            edited_fields['pre_requisite_courses'] = (descriptor.pre_requisite_courses,
                                                      jsondict['pre_requisite_courses'])
            descriptor.pre_requisite_courses = jsondict['pre_requisite_courses']
            dirty = True

        if 'license' in jsondict:
            descriptor.license = jsondict['license']
            dirty = True

        if 'learning_info' in jsondict:
            descriptor.learning_info = jsondict['learning_info']
            dirty = True

        if 'instructor_info' in jsondict:
            added_instructor = [instr for instr in jsondict['instructor_info']['instructors'] if instr
                                not in descriptor.instructor_info['instructors']]
            removed_instructor = [instr for instr in descriptor.instructor_info['instructors'] if instr
                                  not in jsondict['instructor_info']['instructors']]
            if added_instructor:
                logging.info('User {user_id} added new instructor(s) {instructors} to the course: {course_name}, '
                             'course_id: {course_id}'.format(user_id=user.id,
                                                             instructors=added_instructor,
                                                             course_name=descriptor.display_name,
                                                             course_id=course_key))
            if removed_instructor:
                logging.info('User {user_id} removed instructor(s) {instructors} from the course: {course_name}, '
                             'course_id: {course_id}'.format(user_id=user.id,
                                                             instructors=removed_instructor,
                                                             course_name=descriptor.display_name,
                                                             course_id=course_key))
            descriptor.instructor_info = jsondict['instructor_info']
            dirty = True

        if 'language' in jsondict and jsondict['language'] != descriptor.language:
            edited_fields['language'] = (descriptor.language, jsondict['language'])
            descriptor.language = jsondict['language']
            dirty = True

        if 'reminder_info' in jsondict:
            reminder = jsondict['reminder_info']
            tmp = []
            for i in reminder:
                try:
                    tmp.append(int(i))
                except ValueError:
                    pass
            tmp.sort()
            descriptor.reminder_info = tmp
            dirty = True

        if 'course_finish_days' in jsondict and jsondict['course_finish_days'] != descriptor.course_finish_days:
            edited_fields['course_finish_days'] = (descriptor.course_finish_days, jsondict['course_finish_days'])
            descriptor.course_finish_days = jsondict['course_finish_days']
            dirty = True

        if 'course_re_enroll_time' in jsondict and \
                jsondict['course_re_enroll_time'] != descriptor.course_re_enroll_time:
            edited_fields['course_re_enroll_time'] = (descriptor.course_re_enroll_time, jsondict['course_re_enroll_time'])
            descriptor.course_re_enroll_time = jsondict['course_re_enroll_time']
            dirty = True

        if 're_enroll_time_unit' in jsondict and jsondict['re_enroll_time_unit'] != descriptor.re_enroll_time_unit:
            edited_fields['re_enroll_time_unit'] = (descriptor.re_enroll_time_unit, jsondict['re_enroll_time_unit'])
            descriptor.re_enroll_time_unit = jsondict['re_enroll_time_unit']
            dirty = True

        if 'periodic_reminder_day' in jsondict and \
                jsondict['periodic_reminder_day'] != descriptor.periodic_reminder_day:
            descriptor.periodic_reminder_day = jsondict['periodic_reminder_day']
            dirty = True

        if 'course_order' in jsondict and jsondict['course_order'] != descriptor.course_order:
            edited_fields['course_order'] = (descriptor.course_order, jsondict['course_order'])
            descriptor.course_order = jsondict['course_order']
            dirty = True

        if 'course_category' in jsondict and jsondict['course_category'] != descriptor.course_category:
            edited_fields['course_category'] = (descriptor.course_category, jsondict['course_category'])
            descriptor.course_category = jsondict['course_category']
            dirty = True

        if 'course_country' in jsondict and jsondict['course_country'] != descriptor.course_country:
            ticked_countries = [ctr for ctr in jsondict['course_country'] if ctr not in descriptor.course_country]
            unticked_countries = [ctr for ctr in descriptor.course_country if ctr not in jsondict['course_country']]
            if ticked_countries:
                logging.info('User {user_id} ticked new course countries {countries}, course_name: {course_name}, '
                             'course_id: {course_id}'.format(user_id=user.id,
                                                             countries=ticked_countries,
                                                             course_name=descriptor.display_name,
                                                             course_id=course_key))
            if unticked_countries:
                logging.info('User {user_id} unticked course countries {countries}, course_name: {course_name}, '
                             'course_id: {course_id}'.format(user_id=user.id,
                                                             countries=unticked_countries,
                                                             course_name=descriptor.display_name,
                                                             course_id=course_key))
            descriptor.course_country = jsondict['course_country']
            dirty = True

        if 'vendor' in jsondict and jsondict['vendor'] != descriptor.vendor:
            edited_fields['vendor'] = (descriptor.vendor, jsondict['vendor'])
            descriptor.vendor = jsondict['vendor']
            dirty = True

        if 'course_mandatory_enabled' in jsondict and \
                jsondict['course_mandatory_enabled'] != descriptor.course_mandatory_enabled:
            if descriptor.course_mandatory_enabled:
                logging.info('User {user_id} disabled course_mandatory, course_name: {course_name}, '
                             'course_id: {course_id}'.format(user_id=user.id,
                                                             course_name=descriptor.display_name,
                                                             course_id=course_key))
            else:
                logging.info('User {user_id} enabled course_mandatory, course_name: {course_name}, '
                             'course_id: {course_id}'.format(user_id=user.id,
                                                             course_name=descriptor.display_name,
                                                             course_id=course_key))
            descriptor.course_mandatory_enabled = jsondict['course_mandatory_enabled']
            dirty = True

        if (descriptor.can_toggle_course_pacing
                and 'self_paced' in jsondict
                and jsondict['self_paced'] != descriptor.self_paced):
            if descriptor.self_paced:
                action = 'disabled'
            else:
                action = 'enabled'
            logging.info('User {user_id} {action} self paced mode of course: {course_name}, '
                         'course_id: {course_id}'.format(user_id=user.id,
                                                         action=action,
                                                         course_name=descriptor.display_name,
                                                         course_id=course_key))
            descriptor.self_paced = jsondict['self_paced']
            dirty = True

        if 'enrollment_learning_groups' in jsondict and jsondict['enrollment_learning_groups'] != descriptor.enrollment_learning_groups:
            ticked_group = [grp for grp in jsondict['enrollment_learning_groups'] if grp not in
                            descriptor.enrollment_learning_groups]
            unticked_group = [grp for grp in descriptor.enrollment_learning_groups if grp not in
                              jsondict['enrollment_learning_groups']]
            if ticked_group:
                logging.info('User {user_id} ticked new learning group(s) {groups}, course_name: {course_name}, '
                             'course_id: {course_id}'.format(user_id=user.id,
                                                             groups=ticked_group,
                                                             course_name=descriptor.display_name,
                                                             course_id=course_key))
            if unticked_group:
                logging.info('User {user_id} unticked learning group(s) {groups}, course_name: {course_name}, '
                             'course_id: {course_id}'.format(user_id=user.id,
                                                             groups=unticked_group,
                                                             course_name=descriptor.display_name,
                                                             course_id=course_key))
            descriptor.enrollment_learning_groups = jsondict['enrollment_learning_groups']
            dirty = True

        if 'display_coursenumber' in jsondict and jsondict['display_coursenumber'] != descriptor.display_coursenumber:
            descriptor.display_coursenumber = jsondict['display_coursenumber']
            dirty = True

        if 'catalog_visibility' in jsondict and jsondict['catalog_visibility'] != descriptor.catalog_visibility:
            edited_fields['catalog_visibility'] = (descriptor.catalog_visibility, jsondict['catalog_visibility'])
            descriptor.catalog_visibility = jsondict['catalog_visibility']
            dirty = True

        if 'is_new' in jsondict and jsondict['is_new'] != descriptor.is_new:
            descriptor.is_new = jsondict['is_new']
            dirty = True

        if 'title' in jsondict and jsondict['title'] and jsondict['title'] != descriptor.display_name:
            edited_fields['title'] = (descriptor.display_name, jsondict['title'])
            descriptor.display_name = jsondict['title']
            dirty = True

        if 'anderspink_boards' in  jsondict and jsondict['anderspink_boards'] != descriptor.anderspink_boards:
            edited_fields['anderspink_boards'] = (descriptor.anderspink_boards, jsondict['anderspink_boards'])
            descriptor.anderspink_boards = jsondict['anderspink_boards']
            dirty = True

        if dirty:
            module_store.update_item(descriptor, user.id)

        for attr, data in edited_fields.items():
            logging.info('User {user_id} edited {attr} from "{old_val}" to "{new_val}", '
                         'course_name: {course_name}, course_id: {course_id}'.format(
                user_id=user.id, attr=attr, old_val=data[0], new_val=data[1],
                course_name=descriptor.display_name, course_id=course_key
            ))

        # NOTE: below auto writes to the db w/o verifying that any of
        # the fields actually changed to make faster, could compare
        # against db or could have client send over a list of which
        # fields changed.
        for attribute in ABOUT_ATTRIBUTES:
            if attribute in jsondict:
                cls.update_about_item(descriptor, attribute, jsondict[attribute], user.id)

        cls.update_about_video(descriptor, jsondict['intro_video'], user.id)

        # Could just return jsondict w/o doing any db reads, but I put
        # the reads in as a means to confirm it persisted correctly
        return CourseDetails.fetch(course_key)

    @staticmethod
    def parse_video_tag(raw_video):
        """
        Because the client really only wants the author to specify the
        youtube key, that's all we send to and get from the client. The
        problem is that the db stores the html markup as well (which, of
        course, makes any site-wide changes to how we do videos next to
        impossible.)
        """
        if not raw_video:
            return None

        keystring_matcher = re.search(r'(?<=embed/)[a-zA-Z0-9_-]+', raw_video)
        if keystring_matcher is None:
            keystring_matcher = re.search(r'<?=\d+:[a-zA-Z0-9_-]+', raw_video)
            if keystring_matcher is None:
                keystring_matcher = re.search(r'(?<=data-video-id=")[a-zA-Z0-9_-]+', raw_video)

        if keystring_matcher:
            return keystring_matcher.group(0)
        else:
            logging.warn("ignoring the content because it doesn't not conform to expected pattern: " + raw_video)
            return None

    @staticmethod
    def recompose_video_tag(course_key, video_key):
        """
        Returns HTML string to embed the video in an iFrame.
        """
        # TODO should this use a mako template? Of course, my hope is
        # that this is a short-term workaround for the db not storing
        #  the right thing
        from contentstore.views.videos import _get_encoded_video_url
        result = None
        if video_key:
            encoded_video_url = _get_encoded_video_url(unicode(course_key), video_key)
            if encoded_video_url is None:
                result = (
                        '<iframe title="YouTube Video" width="560" height="315" src="//www.youtube.com/embed/' +
                        video_key +
                        '?rel=0" frameborder="0" allowfullscreen=""></iframe>'
                )
            else:
                result = ('<video id="intro-video" controls="" width="560" height="315">' +
                          '<source src="{url}" data-video-id="{video_id}">'.format(
                              url=encoded_video_url, video_id=video_key) +
                          _("Your browser does not support this video format. Try using a different browser.") +
                          '</video>'
                          )
        return result
