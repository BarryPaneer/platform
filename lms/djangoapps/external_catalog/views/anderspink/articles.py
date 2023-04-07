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
from django.db.models import Q, F
from django.db.models import Value
from django.db.models import When
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from edxmako.shortcuts import render_to_response
from lms.djangoapps.external_catalog.models import AndersPinkBriefing, AndersPinkArticle
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from util.json_request import JsonResponse, expect_json
from lms.djangoapps.external_catalog.utils import get_external_catalogs_by_user, is_anderspink_enabled


log = logging.getLogger(__name__)


class SearchPage(View):
    """Page interface for ANDERSPINK"""
    TEMPLATE_PATH = r'external_catalog/anderspink_catalog_courses.html'

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        if not is_anderspink_enabled(request.user.groups.all()):
            raise Http404

        external_catalogs = get_external_catalogs_by_user(request.user)

        return render_to_response(
            self.TEMPLATE_PATH,
            {
                'external_catalogs': external_catalogs
            }
        )

class _ReadingTimeCount(object):
    """Count ReadingTime number for `ReadingTime filter`"""
    READINGTIME_LEVEL_1 = (0, 60 * 3)
    READINGTIME_LEVEL_2 = (60 * 3, 60 * 5)
    READINGTIME_LEVEL_3 = (60 * 5, 60 * 8)
    READINGTIME_LEVEL_4 = (60 * 8, 0xFFFFFFFF)

    @staticmethod
    def map_level_to_range(level):
        if level == 1:
            return _ReadingTimeCount.READINGTIME_LEVEL_1
        elif level == 2:
            return _ReadingTimeCount.READINGTIME_LEVEL_2
        elif level == 3:
            return _ReadingTimeCount.READINGTIME_LEVEL_3
        elif level == 4:
            return _ReadingTimeCount.READINGTIME_LEVEL_4

        return None

    @staticmethod
    def query_readingtime_counts(course_queryset):
        queryset = course_queryset.annotate(
            readingtime_level=Case(
                When(reading_time__lt=60 * 3, then=Value(1)),
                When(reading_time__gte=60 * 3, reading_time__lt=60 * 5, then=Value(2)),
                When(reading_time__gte=60 * 5, reading_time__lt=60 * 8, then=Value(3)),
                default=Value(4),
                output_field=IntegerField()
            )
        ).values('readingtime_level').annotate(count=Count('readingtime_level')).order_by('readingtime_level')

        return [{'reading_time': record['readingtime_level'], 'count': record['count']} for record in queryset]


class Data(View):
    """Data interface for ANDERSPINK"""
    def _get_sidebar_parameters(self, article_queryset=None):
        """
            Return sidebar render parameters
            Return:
                {
                    'status': 'success',
                    'message': '',
                    "sidebar_data": {
                        'briefings': [
                            {'text': 'test_category_a', 'value': 'id_100'},
                            {'text': 'test_category_b', 'value': 'id_101'}
                        ],
                        'reading_time': [
                            {'text': '180', 'value':180, 'count': 1},
                            {'text': '120', 'value': 120, 'count': 1}
                        ],
                        'language': [
                            {'text': 'en', 'value': 'en', 'count': 2},
                            {'text': 'es', 'value': 'es', 'count': 2}
                        ],
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
            # fetch: briefings
            return_dict['sidebar_data']['briefings'] = [
                {
                    'text': article.name,
                    'value': article.briefing_id
                }
                for article in AndersPinkBriefing.objects.all()
            ]

            # fetch: reading_time & languages
            article_queryset = article_queryset if article_queryset else AndersPinkArticle.objects.all()

            languages_queryset = article_queryset.values(distinct_language=F('language')).annotate(
                count=Count('language')).order_by()
            languages_queryset = languages_queryset.filter(count__gt=0)
            return_dict['sidebar_data']['language'] = [{
                'count': language['count'],
                'text': language['distinct_language'],
                'value': language['distinct_language']
            }
                for language in languages_queryset
            ]

            return_dict['sidebar_data']['reading_time'] = [  # Fetch reading_time
                {'text': '{}'.format(item['reading_time']), 'value': item['reading_time'], 'count': item['count']}
                for item in _ReadingTimeCount.query_readingtime_counts(article_queryset)
            ]


        except DatabaseError as e:
            status, message = 'fail', 'Database error for transaction ({})'.format(str(e))
            log.exception(message)
        except Exception as e:
            log.exception(str(e))

        return return_dict

    def _get_articles(self, request):
        """
            Return dict obj. to Sidebar & Article List
            Return:
            {
                'status': 'success',
                'message': '',
                'search_content': request.json['search_content'],
                'atricle_list': [
                    {
                        'title': 'test_course_title_A',
                        'reading_time': 150,
                        'author':'author_abc',
                        'date_published':'
                        'language': 'en',
                        'url': 'https://medium.com/javascript-scene/how-to-build-a-neuron-exploring-ai-in-javascript-pt-2-2f2acb9747ed',
                        'image': 'https://cdn-images-1.medium.com/max/1200/1*p37KRWpihIwr1UJ0gozG9g.jpeg'
                    },
                    ...
                ],
                'article_count': 2,
                'sidebar_data': {Ref method: _get_sidebar_parameters()}

        """
        return_dict = {
            'status': 'success', 'message': '',
            'search_content': request.json['search_content'],
            'article_list': [], 'article_count': 0, 'sidebar_data': {}
        }

        try:
            queryset = AndersPinkArticle.objects.all()

            # Assemble query with input parameters (filter_content)
            for filter_type, filter_param in request.json['filter_content'].items():
                if isinstance(filter_param, Iterable) and 'all' in filter_param:
                    continue  # skip for `query all`

                if filter_type == 'reading_time':
                    min_range = _ReadingTimeCount.map_level_to_range(min(filter_param))
                    max_range = _ReadingTimeCount.map_level_to_range(max(filter_param))
                    if filter_param[0] == 4:
                        queryset = queryset.filter(Q(reading_time__gt=min_range[0]) | Q(reading_time__isnull=True))
                    else:
                        queryset = queryset.filter(reading_time__gt=min_range[0], reading_time__lte=max_range[1])
                elif filter_type == 'language':
                    queryset = queryset.filter(language__in=filter_param)
                elif filter_type == 'briefing':
                    queryset = queryset.filter(briefing_id__name=filter_param)
                else:
                    queryset = queryset.filter(**{filter_type + '__in': filter_param})

            if request.json['search_content']:
                queryset = queryset.filter(title__icontains=request.json['search_content'])
            sort_type = request.json['sort_type']
            if sort_type == '-display_name':
                queryset = queryset.order_by('-title')
            elif sort_type == '+display_name':
                queryset = queryset.order_by('title')
            elif sort_type == '-display_name_time':
                queryset = queryset.order_by('date_published')
            else:
                queryset = queryset.order_by('-date_published')

            def _format_resource_for_page(record):
                articles = {attr: getattr(record, attr) for attr in
                            {'title', 'reading_time', 'language', 'image', 'date_published', 'author', 'url'}}
                try:
                    articles['title'] = articles['title'].decode('unicode_escape').encode('utf-8')
                except UnicodeEncodeError:
                    articles['title'] = articles['title'].encode('utf-8')
                if articles['author']:
                    try:
                        articles['author'] = articles['author'].decode('unicode_escape').encode('utf-8')
                    except UnicodeEncodeError:
                        articles['author'] = articles['author'].encode('utf-8')
                return articles

            page_records = list(map(_format_resource_for_page, queryset))
            return_dict['article_count'] = len(page_records)
            # If no search results, set queryset as the default queryset
            if not return_dict['article_count']:
                page_records = list(map(_format_resource_for_page, AndersPinkArticle.objects.all()))

            paginator = Paginator(page_records, request.json['page_size'])
            articles = paginator.page(request.json['page_no'])

            return_dict['sidebar_data'] = self._get_sidebar_parameters(
                queryset
            )['sidebar_data']

        except DatabaseError as e:
            status, message = 'fail', 'Database error for transaction ({})'.format(str(e))
            return_dict['status'] = status
            return_dict['message'] = message
            log.exception(message)
        except PageNotAnInteger:
            articles = paginator.page(1)
        except EmptyPage:
            articles = paginator.page(paginator.num_pages)

        return_dict['article_list'] = articles.object_list

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
        """Return `articles` & `sidebar` data to browser"""
        if not configuration_helpers.get_value(
            'ENABLE_EXTERNAL_CATALOG',
            settings.FEATURES.get('ENABLE_EXTERNAL_CATALOG', False)
        ):
            raise Http404

        return JsonResponse(
            self._get_articles(request)
        )
