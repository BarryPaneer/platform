import logging
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import DatabaseError
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from lms.djangoapps.external_catalog.models import AndersPinkArticle, AndersPinkBoard
from util.json_request import JsonResponse, expect_json


log = logging.getLogger(__name__)


class BoardData(View):
    """Data interface for ANDERSPINK BOARDS"""

    def _get_board_parameters(self):
        """
            Return:
                {
                    'status': 'success',
                    'message': '',
                    "board_data": {
                        'boards': [
                            {'text': 'test_category_a', 'value': 'id_100'},
                            {'text': 'test_category_b', 'value': 'id_101'}
                        ],
                    }
                }
        """
        return_dict = {
            'status': 'success',
            'message': '',
            "board_data": {"boards" : []}
        }

        try:
            # fetch: boards
            return_dict['board_data']['boards'] = [
                {
                    'text': article.name,
                    'value': article.board_id
                }
                for article in AndersPinkBoard.objects.all()
            ]

        except DatabaseError as e:
            status, message = 'fail', 'Database error for transaction ({})'.format(str(e))
            log.exception(message)
        except Exception as e:
            log.exception(str(e))

        return return_dict

    
    def _get_articles(self, request):
        """
            Return dict obj. to board & Article List
            Return:
            {
                'status': 'success',
                'message': '',
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

        """
        return_dict = {
            'status': 'success', 'message': '',
            'article_list': [], 'article_count': 0
        }

        try:
            print(request.json)
            queryset = AndersPinkArticle.objects.filter(board_id_id__board_id=int(request.json["board_id"]))
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
            
            paginator = Paginator(page_records, request.json['page_size'])
            articles = paginator.page(request.json['page_no'])


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
        

   
    def get(self, request, *args, **kwargs):
        """Return `board` data to browser"""

        return JsonResponse(
            self._get_board_parameters()
        )

    @method_decorator(login_required)
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(expect_json)
    def post(self, request, *args, **kwargs):
        """Return `articles` & `board` data to browser"""

        return JsonResponse(
            self._get_articles(request)
        )
