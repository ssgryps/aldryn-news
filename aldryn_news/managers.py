# -*- coding: utf-8 -*-
import datetime
from collections import Counter

from django.contrib.contenttypes.models import ContentType
from django.db import models, router
from django.db.models import signals
from django.utils import timezone
from hvad.models import TranslationManager
from hvad.manager import TranslationQueryset
from taggit.managers import _TaggableManager
from taggit.models import Tag, TaggedItem
from taggit.utils import require_instance_manager


class CategoryManager(TranslationManager):

    def get_with_usage_count(self, language=None, news_ids=None, **kwargs):
        if not news_ids:
            news_ids = self.language(language).values_list('pk', flat=True)

        kwargs['news__in'] = news_ids

        categories = list(self.language(language).filter(**kwargs).distinct())

        # No annotate in hvad.
        for category in categories:
            category.news_count = category.news_set.count()
        return sorted(categories, key=lambda x: -x.news_count)


class RelatedManager(TranslationManager):

    def get_queryset(self):
        qs = super(RelatedManager, self).get_queryset()
        qs = qs.select_related('key_visual')
        # bug in hvad - Meta ordering isn't preserved
        qs = qs.order_by('-publication_start')
        return qs

    def get_tags(self, language, news_ids=None):
        """Returns tags used to tag news and its count. Results are ordered by count."""

        # get tagged news

        if not news_ids:
            news_ids = self.language(language).values_list('pk', flat=True)

        kwargs = {
            "object_id__in": set(news_ids),
            "content_type": ContentType.objects.get_for_model(self.model)
        }

        # aggregate and sort
        counted_tags = dict(TaggedItem.objects
                                      .filter(**kwargs)
                                      .values('tag')
                                      .annotate(count=models.Count('tag'))
                                      .values_list('tag', 'count'))

        # and finally get the results
        tags = Tag.objects.filter(pk__in=list(counted_tags.keys()))
        for tag in tags:
            tag.count = counted_tags[tag.pk]
        return sorted(tags, key=lambda x: -x.count)

    def get_months(self, language):
        """Get months with aggregated count (how much news is in the month). Results are ordered by date."""
        # done via naive way as django's having tough time while aggregating on date fields
        news = self.language(language)
        dates = news.values_list('publication_start', flat=True)
        dates = [(x.year, x.month) for x in dates]
        date_counter = Counter(dates)
        dates = set(dates)
        dates = sorted(dates, reverse=True)
        return [{'date': datetime.date(year=year, month=month, day=1),
                 'count': date_counter[year, month]} for year, month in dates]


class NewsTranslationQueryset(TranslationQueryset):
    """
    https://github.com/KristianOellegaard/django-hvad/issues/86
    """

    def get_published(self):
        qs = self.filter(publication_start__lte=timezone.now())
        qs = qs.filter(models.Q(publication_end__isnull=True) | models.Q(publication_end__gte=timezone.now()))
        return qs


class PublishedManager(RelatedManager):

    def get_queryset(self):
        qs = super(PublishedManager, self).get_queryset()
        qs = qs.filter(publication_start__lte=timezone.now())
        qs = qs.filter(models.Q(publication_end__isnull=True) | models.Q(publication_end__gte=timezone.now()))
        return qs

    def get_published(self):
        return self.get_queryset().get_published()


class TagManager(TranslationManager):

    def get_queryset(self):
        return self.language()


class CustomTaggableManager(_TaggableManager):
    """
    Used this custom manager because of django-hvad on Tag model.
    """

    @require_instance_manager
    def set(self, *tags, **kwargs):
        """
        Set the object's tags to the given n tags. If the clear kwarg is True
        then all existing tags are removed (using `.clear()`) and the new tags
        added. Otherwise, only those tags that are not present in the args are
        removed and any new tags added.
        """
        db = router.db_for_write(self.through, instance=self.instance)
        clear = kwargs.pop("clear", False)

        if clear:
            self.clear()
            self.add(*tags)
        else:
            # make sure we're working with a collection of a uniform type
            objs = self._to_tag_model_instances(tags)

            # get the existing tag strings
            old_tag_strs = set(
                self.through._default_manager.using(db)
                    .filter(**self._lookup_kwargs())
                    .values_list("tag__translations__name", flat=True)
            )

            new_objs = []
            for obj in objs:
                if obj.name in old_tag_strs:
                    old_tag_strs.remove(obj.name)
                else:
                    new_objs.append(obj)

            self.remove(*old_tag_strs)
            self.add(*new_objs)

    @require_instance_manager
    def remove(self, *tags):
        if not tags:
            return

        db = router.db_for_write(self.through, instance=self.instance)

        qs = (
            self.through._default_manager.using(db)
                .filter(**self._lookup_kwargs())
                .filter(tag__translations__name__in=tags)
        )

        old_ids = set(qs.values_list("tag_id", flat=True))

        signals.m2m_changed.send(
            sender=self.through,
            action="pre_remove",
            instance=self.instance,
            reverse=False,
            model=self.through.tag_model(),
            pk_set=old_ids,
            using=db,
        )
        qs.delete()
        signals.m2m_changed.send(
            sender=self.through,
            action="post_remove",
            instance=self.instance,
            reverse=False,
            model=self.through.tag_model(),
            pk_set=old_ids,
            using=db,
        )
