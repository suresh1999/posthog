from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from posthog.models.filters import Filter
from posthog.utils import generate_cache_key


class DashboardItem(models.Model):
    dashboard: models.ForeignKey = models.ForeignKey(
        "Dashboard", related_name="items", on_delete=models.CASCADE, null=True, blank=True
    )
    name: models.CharField = models.CharField(max_length=400, null=True, blank=True)
    description: models.CharField = models.CharField(max_length=400, null=True, blank=True)
    team: models.ForeignKey = models.ForeignKey("Team", on_delete=models.CASCADE)
    filters: JSONField = JSONField(default=dict)
    filters_hash: models.CharField = models.CharField(max_length=400, null=True, blank=True)
    order: models.IntegerField = models.IntegerField(null=True, blank=True)
    type: models.CharField = models.CharField(max_length=400, null=True, blank=True)
    deleted: models.BooleanField = models.BooleanField(default=False)
    saved: models.BooleanField = models.BooleanField(default=False)
    created_at: models.DateTimeField = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    layouts: JSONField = JSONField(default=dict)
    color: models.CharField = models.CharField(max_length=400, null=True, blank=True)
    last_refresh: models.DateTimeField = models.DateTimeField(blank=True, null=True)
    refreshing: models.BooleanField = models.BooleanField(default=False)
    funnel: models.ForeignKey = models.ForeignKey("Funnel", on_delete=models.CASCADE, null=True, blank=True)
    created_by: models.ForeignKey = models.ForeignKey("User", on_delete=models.SET_NULL, null=True, blank=True)
    is_sample: models.BooleanField = models.BooleanField(
        default=False
    )  # indicates if it's a sample graph generated by dashboard templates


@receiver(pre_save, sender=DashboardItem)
def dashboard_item_saved(sender, instance: DashboardItem, **kwargs):
    if instance.filters and instance.filters != {}:
        filter = Filter(data=instance.filters)
        instance.filters_hash = generate_cache_key("{}_{}".format(filter.toJSON(), instance.team_id))
