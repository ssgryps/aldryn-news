CHANGELOG
=========

0.1.21 (2019-03-19)
------------------

* pin django-select2 to 5.11.1
* fix at code to according library


0.1.21 (2019-03-18)
------------------

* add support for djangocms 3.2 (rename cms_app.py and cms_toolbar.py)


0.1.20 (2019-03-17)
------------------

* django-select2 == 4.3.2 - in next release will be update compatibility with next major release of this library
* move to 'south_migrations' migrations for django<1.7
* create one native migration for django>=1.7
* fix 'get_query_set' method