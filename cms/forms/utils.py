# -*- coding: utf-8 -*-
from collections import OrderedDict, defaultdict

from django.conf import settings
from django.contrib.sites.models import Site
from django.db.models.signals import post_save, post_delete
from django.utils.html import escape
from django.utils.safestring import mark_safe

from cms.cache.choices import (
    clean_site_choices_cache, clean_page_choices_cache,
    _site_cache_key, _page_cache_key)
from cms.exceptions import LanguageError
from cms.models import Page, Title
from cms.utils import i18n


# We want all pages on all sites to be available in the PageField dropdown.
# The easiest way to do this is to find all the languages that aren't already in language_order
# and then append them to language_order.
# But the order of the extra languages appended to language_order is important, as it will
# determine the language used to display the page title in the PageField dropdown.
# In particular, if we're on a site whose languages are [en-us, es-mx] and we're linking to a site
# whose languages are [en-gb, es, fr, and pt], we want to display the en-gb title for the page if it
# exists (because the first language of the site we're linking from is en-us), and if not we display
# the es title if it exists, and only then display the fr or pt title.
# This code sorts to the required ordering.
def get_expanded_language_order(language_order):
    all_languages = set(l[0] for l in settings.LANGUAGES)
    non_site_languages = all_languages.difference(language_order)

    def get_base_language(lang):
        return lang.split('-')[0]

    language_order_bases = [get_base_language(l) for l in language_order]

    def position_of_base_in_language_order(lang):
        lang_base = get_base_language(lang)
        for i, base in enumerate(language_order_bases):
            if base == lang_base:
                return i
        return len(language_order)  # If not found, return one past the end so sorting will work

    return language_order + sorted(non_site_languages, key=position_of_base_in_language_order)


def update_site_and_page_choices(lang=None):
    lang = lang or i18n.get_current_language()
    SITE_CHOICES_KEY = _site_cache_key(lang)
    PAGE_CHOICES_KEY = _page_cache_key(lang)
    title_queryset = (Title.objects.drafts()
                      .select_related('page', 'page__site')
                      .order_by('page__path'))
    pages = defaultdict(OrderedDict)
    sites = {}
    for title in title_queryset:
        page = pages[title.page.site.pk].get(title.page.pk, {})
        page[title.language] = title
        pages[title.page.site.pk][title.page.pk] = page
        sites[title.page.site.pk] = title.page.site.name

    site_choices = []
    page_choices = [('', '----')]

    try:
        fallbacks = i18n.get_fallback_languages(lang)
    except LanguageError:
        fallbacks = []
    language_order = [lang] + fallbacks

    language_order = get_expanded_language_order(language_order)

    for sitepk, sitename in sites.items():
        site_choices.append((sitepk, sitename))

        site_page_choices = []
        for titles in pages[sitepk].values():
            title = None
            for language in language_order:
                title = titles.get(language)
                if title:
                    break
            if not title:
                continue

            indent = u"&nbsp;&nbsp;" * (title.page.depth - 1)
            page_title = mark_safe(u"%s%s" % (indent, escape(title.title)))
            site_page_choices.append((title.page.pk, page_title))

        page_choices.append((sitename, site_page_choices))
    from django.core.cache import cache
    # We set it to 1 day here because we actively invalidate this cache.
    cache.set(SITE_CHOICES_KEY, site_choices, 86400)
    cache.set(PAGE_CHOICES_KEY, page_choices, 86400)
    return site_choices, page_choices


def get_site_choices(lang=None):
    from django.core.cache import cache
    lang = lang or i18n.get_current_language()
    site_choices = cache.get(_site_cache_key(lang))
    if site_choices is None:
        site_choices, page_choices = update_site_and_page_choices(lang)
    return site_choices


def get_page_choices(lang=None):
    from django.core.cache import cache
    lang = lang or i18n.get_current_language()
    page_choices = cache.get(_page_cache_key(lang))
    if page_choices is None:
        site_choices, page_choices = update_site_and_page_choices(lang)
    return page_choices


post_save.connect(clean_page_choices_cache, sender=Page)
post_save.connect(clean_site_choices_cache, sender=Site)
post_delete.connect(clean_page_choices_cache, sender=Page)
post_delete.connect(clean_site_choices_cache, sender=Site)
