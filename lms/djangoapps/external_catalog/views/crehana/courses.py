from collections import Counter as CounterLanguages
from collections import Iterable
import logging
import operator

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import DatabaseError
from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import FloatField
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from edxmako.shortcuts import render_to_response
from .languages_mapping import languages_mapping
from lms.djangoapps.external_catalog.models import CrehanaResource
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from util.json_request import JsonResponse, expect_json
from lms.djangoapps.external_catalog.utils import is_crehana_enabled, get_external_catalogs_by_user


log = logging.getLogger(__name__)


class SearchPage(View):
    """Page interface for CREHANA"""
    TEMPLATE_PATH = r'external_catalog/crehana_catalog_courses.html'

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        if not is_crehana_enabled(request.user.groups.all()):
            raise Http404

        external_catalogs = get_external_catalogs_by_user(request.user)

        return render_to_response(
            self.TEMPLATE_PATH,
            {
                'external_catalogs': external_catalogs
            }
        )


class _DurationsCount(object):
    """Count durations number for `video duration filter`"""
    DURATION_LEVEL_1 = (0, 3600 * 2)
    DURATION_LEVEL_2 = (3600 * 2, 3600 * 6)
    DURATION_LEVEL_3 = (3600 * 6, 3600 * 16)
    DURATION_LEVEL_4 = (3600 * 16, 0xFFFFFFFF)

    @staticmethod
    def map_level_to_range(level):
        if level == 1:
            return _DurationsCount.DURATION_LEVEL_1
        elif level == 2:
            return _DurationsCount.DURATION_LEVEL_2
        elif level == 3:
            return _DurationsCount.DURATION_LEVEL_3
        elif level == 4:
            return _DurationsCount.DURATION_LEVEL_4

        return None

    @staticmethod
    def query_durations_counts(course_queryset):
        queryset = course_queryset.annotate(
            duration_level=Case(
                When(duration__lt=3600 * 2, then=Value(1)),
                When(duration__gte=3600 * 2, duration__lt=3600 * 6, then=Value(2)),
                When(duration__gte=3600 * 6, duration__lt=3600 * 16, then=Value(3)),
                default=Value(4),
                output_field=IntegerField()
            )
        ).values('duration_level').annotate(count=Count('duration_level')).order_by('duration_level')

        return [{'duration': record['duration_level'], 'count': record['count']} for record in queryset]


class _RatingsCount(object):
    """Count rating number for `rating filter`"""
    @staticmethod
    def query_ratings_counts(course_queryset):
        queryset = course_queryset.annotate(
            rating_level=Case(
                When(rating__gte=3, rating__lt=3.5, then=Value(3)),     # level 3:   3<=rating<3.5
                When(rating__gte=3.5, rating__lt=4, then=Value(3.5)),   # level 3.5: 3.5<=rating<4
                When(rating__gte=4, rating__lt=4.5, then=Value(4)),     # level 4:   4<=rating<4.5
                When(rating__gte=4.5, rating__lt=5, then=Value(4.5)),   # level 4.5: 4.5<=rating<5
                When(rating__gte=5, then=Value(5)),                     # level 5:   5<=rating
                default=Value(0),                                       # default level: 0
                output_field=FloatField()
            )
        ).values('rating_level').annotate(count=Count('rating_level')).order_by('-rating_level')

        return [{'rating': record['rating_level'], 'count': record['count']} for record in queryset]


class Data(View):
    """Data interface for CREHANA"""
    def _get_sidebar_parameters(self, course_queryset=None):
        """
            Return sidebar render parameters
            Return:
                {
                    'status': 'success',
                    'message': '',
                    "sidebar_data": {
                        'categories': [
                            {'text': 'test_category_a', 'value': 'id_100'},
                            {'text': 'test_category_b', 'value': 'id_101'}
                        ],
                        'duration': [
                            {'text': '3600', 'value': 3600, 'count': 1},
                            {'text': '1200', 'value': 1200, 'count': 1}
                        ],
                        'language': [
                            {'text': 'en', 'value': 'en', 'count': 2},
                            {'text': 'fr', 'value': 'fr', 'count': 2}
                        ],
                        'rating_range': [
                                {'text': '4.5', 'value':4.5, 'count': 1},
                                {'text': '4.0', 'value': 4.0, 'count': 1}
                            ]
                        }
                    }
                }
        """
        return_dict = {
            'status': 'success',
            'message': '',
            "sidebar_data": {}
        }

        try:
            # fetch: categories
            return_dict['sidebar_data']['categories'] = []
            # fetch: duration & languages & rating
            course_queryset = course_queryset if course_queryset else CrehanaResource.objects.all()
            # count number for lang_id --> count(lang_id)
            langs_counter = CounterLanguages(
                (
                    int(lang_id)
                    for course in course_queryset.values('languages').all() if course.get('languages')
                    for lang_id in course['languages'].split(',') if int(lang_id) in languages_mapping
                )
            )
            return_dict['sidebar_data']['language'] = [    # Fetch languages
                {
                    'text': languages_mapping.get_lang_name_by_id(lang_id),
                    'value': languages_mapping.get_lang_name_by_id(lang_id),
                    'count': lang_count
                }
                for lang_id, lang_count in langs_counter.items()
            ]
            return_dict['sidebar_data']['rating_range'] = [  # Fetch rating_range
                {'text': '{}'.format(item['rating']), 'value': item['rating'], 'count': item['count']}
                for item in _RatingsCount.query_ratings_counts(course_queryset)
            ]
            return_dict['sidebar_data']['duration'] = [    # Fetch duration
                {'text': '{}'.format(item['duration']), 'value': item['duration'], 'count': item['count']}
                for item in _DurationsCount.query_durations_counts(course_queryset)
            ]

        except DatabaseError as e:
            status, message = 'fail', 'Database error for transaction ({})'.format(str(e))
            log.exception(message)
        except Exception as e:
            log.exception(str(e))

        return return_dict

    def _get_courses(self, request):
        """
            Return dict obj. to Sidebar & Resources List
            Return:
            {
                'status': 'success',
                'message': '',
                'search_content': request.json['search_content'],
                'course_list': [
                    {
                        'resource_id': 1,
                        'title': 'test_course_title_A',
                        'duration': 3600,
                        'languages': ['en', 'fr'],
                        'description': 'test test...',
                        'image': 'https://cdn.edflex.com/media/cache/catalog_product_458x275/mooc/logo/da766ff0e4e236183e7aa3ae781d3775a4bbd7c9.jpg',
                        'rating': 4
                    },
                    ...
                ],
                'course_count': 2,
                'sidebar_data': {Ref method: _get_sidebar_parameters()}
            }
        """
        return_dict = {
            'status': 'success', 'message': '',
            'search_content': request.json['search_content'],
            'course_list': [], 'course_count': 0, 'sidebar_data': {}
        }

        try:
            queryset = CrehanaResource.objects.all()

            # Assemble query with input parameters (filter_content)
            for filter_type, filter_param in request.json['filter_content'].items():
                if isinstance(filter_param, Iterable) and 'all' in filter_param:
                    continue    # skip for `query all`

                if filter_type == 'rating_range':
                    queryset = queryset.filter(rating__gte=min(filter_param))
                elif filter_type == 'duration':
                    min_range = _DurationsCount.map_level_to_range(min(filter_param))
                    max_range = _DurationsCount.map_level_to_range(max(filter_param))
                    queryset = queryset.filter(duration__gt=min_range[0], duration__lte=max_range[1])
                elif filter_type == 'language':
                    queryset = queryset.filter(
                        reduce(
                            operator.or_,
                            (Q(languages__contains=languages_mapping.get_lang_id_by_name(lang_name)) for lang_name in filter_param)
                        )
                    )
                else:
                    queryset = queryset.filter(**{filter_type + '__in': filter_param})

            if request.json['search_content']:
                queryset = queryset.filter(title__icontains=request.json['search_content'])
            sort_type = request.json['sort_type']
            if sort_type == '-display_name':
                queryset = queryset.order_by('-title')
            else:
                queryset = queryset.order_by('title')
            def _format_resource_for_page(record):
                course = {attr: getattr(record, attr) for attr in {'title', 'duration', 'image', 'rating', 'url'}}
                course['languages'] = [languages_mapping.get_lang_name_by_id(int(lang_id)) for lang_id in record.languages.split(',') if int(lang_id) in languages_mapping]
                return course

            page_records = list(map(_format_resource_for_page, queryset))
            return_dict['course_count'] = len(page_records)
            # If no search results, set queryset as the default queryset
            if not return_dict['course_count']:
                page_records = list(map(_format_resource_for_page, CrehanaResource.objects.all()))

            paginator = Paginator(page_records, request.json['page_size'])
            courses = paginator.page(request.json['page_no'])

            return_dict['sidebar_data'] = self._get_sidebar_parameters(
                queryset
            )['sidebar_data']

        except DatabaseError as e:
            status, message = 'fail', 'Database error for transaction ({})'.format(str(e))
            return_dict['status'] = status
            return_dict['message'] = message
            log.exception(message)
        except PageNotAnInteger:
            courses = paginator.page(1)
        except EmptyPage:
            courses = paginator.page(paginator.num_pages)

        return_dict['course_list'] = courses.object_list

        return return_dict

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(expect_json)
    def get(self, request, *args, **kwargs):
        """Return `sidebar` data to browser"""
        if not configuration_helpers.get_value(
            'ENABLE_EXTERNAL_CATALOG',
            settings.FEATURES.get('ENABLE_EXTERNAL_CATALOG', False)
        ):
            raise Http404

        return JsonResponse(
            self._get_sidebar_parameters()
        )

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(expect_json)
    def post(self, request, *args, **kwargs):
        """Return `resources` & `sidebar` data to browser"""
        if not configuration_helpers.get_value(
            'ENABLE_EXTERNAL_CATALOG',
            settings.FEATURES.get('ENABLE_EXTERNAL_CATALOG', False)
        ):
            raise Http404

        return JsonResponse(
            self._get_courses(request)
        )
