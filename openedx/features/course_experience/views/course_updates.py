"""
Views that handle course updates.
"""
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template.context_processors import csrf
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from opaque_keys.edx.keys import CourseKey
from web_fragments.fragment import Fragment

from courseware.courses import get_course_info_section_module, get_course_with_access
from lms.djangoapps.courseware.views.views import CourseTabView
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from openedx.features.course_experience import default_course_url_name
from student.roles import (
    CourseInstructorRole,
    GlobalStaff
)

from .. import USE_BOOTSTRAP_FLAG
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

STATUS_VISIBLE = 'visible'
STATUS_DELETED = 'deleted'


def get_ordered_updates(request, course):
    """
    Returns any course updates in reverse chronological order.
    """
    info_module = get_course_info_section_module(request, request.user, course, 'updates')

    updates = info_module.items if info_module else []
    info_block = getattr(info_module, '_xmodule', info_module) if info_module else None
    ordered_updates = [update for update in updates if update.get('status') == STATUS_VISIBLE and
                       filter_available_date(update['date'])]
    ordered_updates.sort(
        key=lambda item: (safe_parse_date(item['date']), item['id']),
        reverse=True
    )
    for update in ordered_updates:
        update['content'] = info_block.system.replace_urls(update['content'])
    for update in ordered_updates:
        update['is_new'] = is_new_update(update['date'])
    return ordered_updates


def safe_parse_date(date):
    """
    Since this is used solely for ordering purposes, use today's date as a default
    """
    try:
        return datetime.strptime(date, '%B %d, %Y')
    except ValueError:  # occurs for ill-formatted date values
        return datetime.today()


def filter_available_date(date):
    """
    Get only course updates before than or equal to today
    """
    try:
        date = datetime.strptime(date, '%B %d, %Y')
        today = datetime.today()
        return date <= today
    except ValueError:
        return False


def is_new_update(date):
    """
    Check if the course update is marked new(less than or equal to 14 days before today).
    """
    try:
        date = datetime.strptime(date, '%B %d, %Y')
        today = datetime.today()
        return date <= today and today - date <= timedelta(days=14)  # two weeks
    except ValueError:
        return False


class CourseUpdatesView(CourseTabView):
    """
    The course updates page.
    """
    @method_decorator(login_required)
    @method_decorator(cache_control(no_cache=True, no_store=True, must_revalidate=True))
    def get(self, request, course_id, **kwargs):
        """
        Displays the home page for the specified course.
        """
        return super(CourseUpdatesView, self).get(request, course_id, 'courseware', **kwargs)

    def uses_bootstrap(self, request, course, tab):
        """
        Returns true if the USE_BOOTSTRAP Waffle flag is enabled.
        """
        return USE_BOOTSTRAP_FLAG.is_enabled(course.id)

    def render_to_fragment(self, request, course=None, tab=None, **kwargs):
        course_id = unicode(course.id)
        kwargs['fragment_page'] = False
        updates_fragment_view = CourseUpdatesFragmentView()
        return updates_fragment_view.render_to_fragment(request, course_id=course_id, class_name_str='page-content-container', id_str='course-updates', **kwargs)


class CourseUpdatesFragmentView(EdxFragmentView):
    """
    A fragment to render the updates page for a course.
    """
    def render_to_fragment(self, request, course_id=None, class_name_str='', id_str='', **kwargs):
        """
        Renders the course's home page as a fragment.
        """
        course_key = CourseKey.from_string(course_id)
        course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=True)
        course_url_name = default_course_url_name(course.id)
        course_url = reverse(course_url_name, kwargs={'course_id': unicode(course.id)})

        add_more_enabled = True if GlobalStaff().has_user(request.user) or CourseInstructorRole(course_key).has_user(
            request.user) else False
        add_more_url = u"//{cms_base}/course_info/{course_key}".format(cms_base=configuration_helpers.get_value('SITE_CMS_DOMAIN_NAME', settings.CMS_BASE),
                                                                       course_key=course_id)
        view_more_url = reverse('openedx.course_experience.course_updates', kwargs={'course_id': course_id})

        ordered_updates = get_ordered_updates(request, course)
        plain_html_updates = ''
        if ordered_updates:
            plain_html_updates = self.get_plain_html_updates(request, course)

        # fragment page and standalone page show different numbers of course updates.
        fragment_page = kwargs.get('fragment_page', True)
        if fragment_page and len(ordered_updates) > 2:
            ordered_updates = ordered_updates[:2]

        # Render the course home fragment
        context = {
            'class_name_str': class_name_str,
            'id_str': id_str,
            'csrf': csrf(request)['csrf_token'],
            'course': course,
            'course_url': course_url,
            'updates': ordered_updates,
            'plain_html_updates': plain_html_updates,
            'disable_courseware_js': True,
            'uses_pattern_library': True,
            'fragment_page': fragment_page,
            'add_more_enabled': add_more_enabled,
            'add_more_url': add_more_url,
            'view_more_url': view_more_url
        }
        html = render_to_string('course_experience/course-updates-fragment.html', context)
        return Fragment(html)

    @classmethod
    def has_updates(cls, request, course):
        return get_ordered_updates(request, course)

    @classmethod
    def get_plain_html_updates(cls, request, course):
        """
        Returns any course updates in an html chunk. Used
        for older implementations and a few tests that store
        a single html object representing all the updates.
        """
        info_module = get_course_info_section_module(request, request.user, course, 'updates')
        info_block = getattr(info_module, '_xmodule', info_module)
        return info_block.system.replace_urls(info_module.data) if info_module else ''
