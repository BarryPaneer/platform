import json
import logging

from celery import task
from dateutil.parser import parse
from django.db import IntegrityError
from django.core.exceptions import ImproperlyConfigured
from requests.exceptions import ConnectionError

from .api import EdflexOauthClient
from .models import EdflexCategory, EdflexResource, EdflexSelection
from .utils import get_edflex_configuration
import emoji


log = logging.getLogger('external_catalog')


def fetch_selection(edflex_client):
    selections = edflex_client.get_resource(EdflexOauthClient.SELECTIONS_URL)
    selection_ids = []
    for selection in (selections or []):
        r_selection = edflex_client.get_resource(EdflexOauthClient.SELECTION_URL.format(id=selection['id']))
        if r_selection is None:
            continue
        try:
            EdflexSelection.objects.update_or_create(
                selection_id=r_selection['id'],
                defaults={
                    'title': r_selection['title'],
                    'publication_date': parse(r_selection['publication_date']) if r_selection['publication_date'] else None,
                    'items': json.dumps(r_selection['items'])
                }
            )
            log.info(u"Updated: Selection <{title}> ({id})".format(id=r_selection['id'], title=r_selection['title']))
        except KeyError:
            continue

        selection_ids.append(r_selection['id'])

    EdflexSelection.objects.exclude(selection_id__in=selection_ids).delete()


def fetch_resources(client_id, client_secret, locale, base_api_url):
    edflex_client = EdflexOauthClient(client_id, client_secret, locale, base_api_url)
    catalogs = edflex_client.get_resource(EdflexOauthClient.CATALOGS_URL)
    resource_ids = []
    category_ids = []

    for catalog in catalogs or []:
        r_catalog = edflex_client.get_resource(EdflexOauthClient.CATALOG_URL.format(id=catalog['id']))
        if r_catalog is None:
            continue

        for resource in r_catalog['items']:
            r_resource = edflex_client.get_resource(
                EdflexOauthClient.RESOURCE_URL.format(id=resource['resource']['id']))
            if r_resource is None:
                continue
            try:
                clean_title = emoji.get_emoji_regexp().sub(r'', r_resource['title'])
                model_resource, _ = EdflexResource.objects.update_or_create(
                    resource_id=r_resource['id'],
                    defaults={
                        'title': clean_title,
                        'type': r_resource['type'],
                        'language': r_resource['language'],
                        'url': r_resource['provider_url'],
                        'duration': r_resource['duration'],
                        'publication_date': parse(r_resource['publication_date']) if r_resource.get('publication_date', None) else None,
                        'image_url': r_resource['image']['original'],
                        'rating': r_resource['note']['global']
                    },
                )
                log.info(u"Updated: Resource <{title}> ({id})".format(id=r_resource['id'], title=clean_title))
            except KeyError as e:
                log.error(u"%s doesn't exist for resource: %s" % (e, r_resource['id']))
                continue
            except IntegrityError as e:
                log.error(u"Database IntegrityError: %s" % str(e))
                continue

            resource_ids.append(r_resource['id'])
            model_resource.categories.clear()

            for r_category in r_resource.get('categories', []):
                model_category, _ = EdflexCategory.objects.update_or_create(
                    category_id=r_category['id'],
                    language=locale,
                    defaults={'name': r_category['name']}
                )
                model_resource.categories.add(model_category)
                log.info(u"Updated: Category <{cname}> ({cid}) for Resource {id}".format(
                    cid=r_category['id'],
                    cname=r_category['name'],
                    id=r_resource['id']
                ))
                category_ids.append(r_category['id'])

    EdflexResource.objects.exclude(resource_id__in=resource_ids).delete()
    EdflexCategory.objects.exclude(category_id__in=category_ids).delete()

    fetch_selection(edflex_client)


def fetch_other_categories(client_id, client_secret, locale, base_api_url):
    edflex_client = EdflexOauthClient(client_id, client_secret, locale, base_api_url)
    catalogs = edflex_client.get_resource(EdflexOauthClient.CATALOGS_URL)
    category_ids = []

    for catalog in catalogs or []:
        r_catalog = edflex_client.get_resource(EdflexOauthClient.CATALOG_URL.format(id=catalog['id']))
        if r_catalog is None:
            continue

        for resource in r_catalog['items']:
            r_resource = edflex_client.get_resource(
                EdflexOauthClient.RESOURCE_URL.format(id=resource['resource']['id']))
            if r_resource is None:
                continue

            try:
                model_resource = EdflexResource.objects.get(resource_id=r_resource['id'])
                for r_category in r_resource.get('categories', []):
                    model_category, _ = EdflexCategory.objects.update_or_create(
                        category_id=r_category['id'],
                        language=locale,
                        defaults={'name': r_category['name']}
                    )
                    log.info(u"Updated: Category <{cname}> ({cid}) for Resource <{title}> {id}".format(
                        cid=r_category['id'],
                        cname=r_category['name'],
                        id=r_resource['id'],
                        title=r_resource['title']
                    ))
                    category_ids.append(r_category['id'])
                    model_resource.categories.add(model_category)
            except (ConnectionError, EdflexResource.DoesNotExist):
                pass


def get_resources():
    edflex_configuration = get_edflex_configuration()
    for conf, val in edflex_configuration.items():
        if not val:
            raise ImproperlyConfigured(
                'In order to use API for Edflex of the followings must be configured: '
                'EDFLEX_CLIENT_ID, EDFLEX_CLIENT_SECRET, EDFLEX_LOCALE, EDFLEX_BASE_API_URL'
            )
    languages = edflex_configuration['locale']
    default_language = languages[0]
    basic_configuration = edflex_configuration.copy()
    basic_configuration['locale'] = default_language
    fetch_resources(**basic_configuration)
    for language in languages[1:]:
        basic_configuration['locale'] = language
        fetch_resources(**basic_configuration)


@task(name="task.fetch_edflex_data", bind=True)
def fetch_edflex_data():
    get_resources()
