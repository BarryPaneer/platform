""" 
handle requests for courseware search http requests.

This is used to replace url entrypoint: "/search/course_discovery" to fix more than one value selected for single course facet.
"""
# This contains just the url entry points to use if desired, which currently has only one
import dateutil.parser
import logging
import json

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from contentstore.utils import get_lms_link_for_item, reverse_course_url
from course_creators.views import add_user_with_status_unrequested, get_course_creator_status
from eventtracking import tracker as track
from opaque_keys.edx.keys import CourseKey
from search.api import QueryParseError, course_discovery_search, course_discovery_filter_fields
from search.api import programs_discovery_search
from student.roles import GlobalStaff
from xmodule import course_metadata_utils


# log appears to be standard name used for logger
log = logging.getLogger(__name__)  # pylint: disable=invalid-name

__all__ = [
    'course_discovery',
    'program_discovery'
]


def _process_pagination_values(request):
    """ process pagination requests from request parameter """
    size = 20
    page = 0
    from_ = 0
    if "page_size" in request.POST:
        size = int(request.POST["page_size"])
        max_page_size = getattr(settings, "SEARCH_MAX_PAGE_SIZE", 2000)
        # The parens below are superfluous, but make it much clearer to the reader what is going on
        if not (0 < size <= max_page_size):  # pylint: disable=superfluous-parens
            raise ValueError(_('Invalid page size of {page_size}').format(page_size=size))

        if "page_index" in request.POST:
            page = int(request.POST["page_index"])
            from_ = page * size
    return size, from_, page


def _process_field_values(request):
    """ Create separate dictionary of supported filter values provided """
    field_values = {}
    for field_key in request.POST:
        # Check if the key's value is array so using request.POST.getlist to get array value.
        if field_key.endswith('[]'):
            if field_key[:-2] in course_discovery_filter_fields():
                field_values[field_key[:-2]] = request.POST.getlist(field_key)[0] if len(
                    request.POST.getlist(field_key)) == 1 else request.POST.getlist(field_key)
        elif field_key in course_discovery_filter_fields():
            field_values[field_key] = request.POST[field_key]

    return field_values


def _get_course_creator_status(user):
    """
    Helper method for returning the course creator status for a particular user,
    taking into account the values of DISABLE_COURSE_CREATION and ENABLE_CREATOR_GROUP.

    If the user passed in has not previously visited the index page, it will be
    added with status 'unrequested' if the course creator group is in use.
    """

    if user.is_staff:
        course_creator_status = 'granted'
    elif settings.FEATURES.get('DISABLE_COURSE_CREATION', False):
        course_creator_status = 'disallowed_for_this_site'
    elif settings.FEATURES.get('ENABLE_CREATOR_GROUP', False):
        course_creator_status = get_course_creator_status(user)
        if course_creator_status is None:
            # User not grandfathered in as an existing user, has not previously visited the dashboard page.
            # Add the user to the course creator admin table with status 'unrequested'.
            add_user_with_status_unrequested(user)
            course_creator_status = get_course_creator_status(user)
    else:
        course_creator_status = 'granted'

    return course_creator_status


def add_extra_data(request, results):
    """Add extra data for cms homepage to display."""

    def allow_reruns(request):
        """Get if the course can be rerun."""
        user = request.user
        allow_course_reruns = settings.FEATURES.get(u'ALLOW_COURSE_RERUNS', True)
        rerun_creator_status = GlobalStaff().has_user(user)
        course_creator_status = _get_course_creator_status(user)
        return allow_course_reruns and rerun_creator_status and course_creator_status == 'granted'

    for course in results['results']:
        course_id = CourseKey.from_string(course['_id'])
        course_location = course_id.make_usage_key('course', 'course')
        course['data']['run'] = course_location.run
        course['data']['url'] = reverse_course_url('course_handler', course_id),
        course['data']['rerun_link'] = reverse_course_url('course_rerun_handler', course_id)
        course['data']['allowReruns'] = allow_reruns(request)
        course['data']['lms_link'] = get_lms_link_for_item(course_location)
        course_end = course['data'].get('end', None)
        if course_end:
            course['data']['archived'] = course_metadata_utils.has_course_ended(dateutil.parser.parse(course_end))
        else:
            course['data']['archived'] = False


@csrf_exempt
@require_POST
def course_discovery(request):
    """
    Search for courses

    Args:
        request (required) - django request object

    Returns:
        http json response with the following fields
            "took" - how many seconds the operation took
            "total" - how many results were found
            "max_score" - maximum score from these resutls
            "results" - json array of result documents

            or

            "error" - displayable information about an error that occured on the server

    POST Params:
        "search_string" (optional) - text with which to search for courses
        "page_size" (optional)- how many results to return per page (defaults to 20, with maximum cutoff at 100)
        "page_index" (optional) - for which page (zero-indexed) to include results (defaults to 0)
    """
    results = {
        "error": _("Nothing to search")
    }
    status_code = 500

    search_term = request.POST.get("search_string", None)

    try:
        size, from_, page = _process_pagination_values(request)
        field_dictionary = _process_field_values(request)

        # Analytics - log search request
        track.emit(
            'edx.course_discovery.search.initiated',
            {
                "search_term": search_term,
                "page_size": size,
                "page_number": page,
            }
        )

        results = course_discovery_search(
            search_term=search_term,
            size=size,
            from_=from_,
            field_dictionary=field_dictionary,
            user=request.user,
            include_course_filter=True
        )

        add_extra_data(request, results)
        log.info('%s courses find.', results['total'])

        # Analytics - log search results before sending to browser
        track.emit(
            'edx.course_discovery.search.results_displayed',
            {
                "search_term": search_term,
                "page_size": size,
                "page_number": page,
                "results_count": results["total"],
            }
        )

        status_code = 200

    except ValueError as invalid_err:
        results = {
            "error": unicode(invalid_err)
        }
        log.debug(unicode(invalid_err))

    except QueryParseError:
        results = {
            "error": _('Your query seems malformed. Check for unmatched quotes.')
        }

    # Allow for broad exceptions here - this is an entry point from external reference
    except Exception as err:  # pylint: disable=broad-except
        results = {
            "error": _('An error occurred when searching for "{search_string}"').format(search_string=search_term)
        }
        log.exception(
            'Search view exception when searching for %s for user %s: %r',
            search_term,
            request.user.id,
            err
        )

    return HttpResponse(
        json.dumps(results, cls=DjangoJSONEncoder),
        content_type='application/json',
        status=status_code
    )


@csrf_exempt
@require_POST
def program_discovery(request):
    """
    Search for programs

    Args:
        request (required) - django request object

    Returns:
        http json response with the following fields
            "took" - how many seconds the operation took
            "total" - how many results were found
            "max_score" - maximum score from these resutls
            "results" - json array of result documents

            or

            "error" - displayable information about an error that occured on the server

    POST Params:
        "search_string" (optional) - text with which to search for courses
        "page_size" (optional)- how many results to return per page (defaults to 20, with maximum cutoff at 100)
        "page_index" (optional) - for which page (zero-indexed) to include results (defaults to 0)
    """
    results = {
        "error": _("Nothing to search")
    }
    status_code = 500

    search_term = request.POST.get("search_string", None)

    try:
        size, from_, page = _process_pagination_values(request)
        field_dictionary = _process_field_values(request)

        # Analytics - log search request
        track.emit(
            'edx.course_discovery.search.initiated',
            {
                "search_term": search_term,
                "page_size": size,
                "page_number": page,
            }
        )

        results = programs_discovery_search(
            search_term=search_term,
            size=size,
            from_=from_,
            field_dictionary=field_dictionary,
            user=request.user,
            include_course_filter=True
        )

        log.info('%s programs find.', results['total'])

        # Analytics - log search results before sending to browser
        track.emit(
            'edx.course_discovery.search.results_displayed',
            {
                "search_term": search_term,
                "page_size": size,
                "page_number": page,
                "results_count": results["total"],
            }
        )

        status_code = 200

    except ValueError as invalid_err:
        results = {
            "error": unicode(invalid_err)
        }
        log.debug(unicode(invalid_err))

    except QueryParseError:
        results = {
            "error": _('Your query seems malformed. Check for unmatched quotes.')
        }

    # Allow for broad exceptions here - this is an entry point from external reference
    except Exception as e:
        results = {
            "error": _('An error occurred when searching for "{search_string}"').format(search_string=search_term)
        }
        log.exception(
            'Search view exception when searching for %s for user %s: %s',
            search_term,
            request.user.id,
            e
        )

    return HttpResponse(
        json.dumps(results, cls=DjangoJSONEncoder),
        content_type='application/json',
        status=status_code
    )
