# -*- coding: utf-8 -*-
from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool
from django.utils.translation import ugettext_lazy as _

from aldryn_news.cms_menus import NewsCategoryMenu


class NewsApp(CMSApp):
    name = _('News')

    def get_urls(self, page=None, language=None, **kwargs):
        return ['aldryn_news.urls']

    def get_menus(self, page=None, language=None, **kwargs):
        return [NewsCategoryMenu]


apphook_pool.register(NewsApp)
