from lms.djangoapps.external_catalog.models import CrehanaLanguage


class _LanguagesMapping(object):
    """
        Mapping from lang_id->lang_name & lang_name->lang_id
        &
        Reload all data if `search key` miss in cache.
    """
    def __init__(self):
        self.__last_loading_time = 0
        self.__id_2_names = {}
        self.__name_2_ids = {}

    def __contains__(self, lang_id_or_name):
        """Test cache,  if `key` doesn't exist then reload all mapping"""
        # test cache
        if self._cache_hitted(lang_id_or_name):
            return True
        # reload all, because of cache miss
        self._load_mapping_from_table()
        # test cache again.
        if isinstance(lang_id_or_name, int):
            return lang_id_or_name in self.__id_2_names
        else:
            return lang_id_or_name.lower() in self.__name_2_ids

    def _cache_hitted(self, lang_id_or_name):
        """Test cache"""
        if isinstance(lang_id_or_name, int):
            return lang_id_or_name in self.__id_2_names
        else:
            return lang_id_or_name.lower() in self.__name_2_ids

    def _load_mapping_from_table(self):
        """Rebuild mapping from table"""
        self.__id_2_names = {}
        self.__name_2_ids = {}

        for lang in CrehanaLanguage.objects.all():
            lang_name = lang.language.lower()
            self.__id_2_names[lang.language_id] = lang_name
            self.__name_2_ids[lang_name] = lang.language_id

    def get_lang_id_by_name(self, name):
        if name not in self:
            return None

        return self.__name_2_ids.get(name)

    def get_lang_name_by_id(self, id):
        if id not in self:
            return None

        return self.__id_2_names.get(id)


languages_mapping = _LanguagesMapping()
