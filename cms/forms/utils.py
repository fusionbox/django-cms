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
from cms.utils.conf import get_cms_setting


def get_base_language(l):
    return l.split('-')[0]


# We want all pages on all sites to be available in the PageField dropdown.
# To do this in a way that ensures the title will display in reasonable languages,
# in the the dropdown, we make 'language order' equal to the list of languages of the
# site we're linking to, but ordered by the ordering for the list of languages of the
# site we're linking from. We also make sure 'en-gb' is treated equal to 'en-us', etc.
# Additionally, there is a bug in Django CMS where the 'lang' parameter passed in
# to update_site_and_page_choices is set to 'en-us' even if we're on another site.
# This is because the ajax request that gets the admin popup window is made
# to /en-us/, regardless of the site we're on.
# Fortunately, we don't need the lang parameter now anyway, since we're calling
# i18n.get_languages() ourselves, which gets all the languages for the site we're
# really on. Since the site and page choices no longer depend on lang, we also
# stop caching update_site_and_page_choices. That will result in a couple of
# unnessesary db queries, but this is just a dropdown in the admin anyway,
# so it doesn't really matter.
def get_language_order(link_from_language_order, link_to_language_order):
    base_lang_order_key = {}
    for i, l in enumerate(link_from_language_order):
        base = get_base_language(l)
        if base not in base_lang_order_key:
            base_lang_order_key[base] = i

    return (
        sorted(
            (l for l in link_to_language_order if get_base_language(l) in base_lang_order_key),
            key=lambda x: base_lang_order_key[get_base_language(x)]
        )
        + [l for l in link_to_language_order if get_base_language(l) not in base_lang_order_key]
    )


def update_site_and_page_choices(lang=None):
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

    link_from_language_order = [l['code'] for l in i18n.get_languages()]

    for sitepk, sitename in sites.items():
        site_choices.append((sitepk, sitename))

        link_to_language_order = [l['code'] for l in i18n.get_languages(sitepk)]
        language_order = get_language_order(link_from_language_order, link_to_language_order)

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
    return site_choices, page_choices


def get_site_choices(lang=None):
    site_choices, page_choices = update_site_and_page_choices()
    return site_choices


def get_page_choices(lang=None):
    site_choices, page_choices = update_site_and_page_choices()
    return page_choices


post_save.connect(clean_page_choices_cache, sender=Page)
post_save.connect(clean_site_choices_cache, sender=Site)
post_delete.connect(clean_page_choices_cache, sender=Page)
post_delete.connect(clean_site_choices_cache, sender=Site)
