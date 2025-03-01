import random
from typing import Callable, Dict, List

from django.utils.timezone import now

from posthog.constants import (
    BREAKDOWN,
    BREAKDOWN_TYPE,
    DATE_FROM,
    DISPLAY,
    INSIGHT,
    INTERVAL,
    PROPERTIES,
    SHOWN_AS,
    TREND_FILTER_TYPE_EVENTS,
    TRENDS_CUMULATIVE,
    TRENDS_FUNNEL,
    TRENDS_LINEAR,
    TRENDS_PIE,
    TRENDS_STICKINESS,
)
from posthog.models.dashboard import Dashboard
from posthog.models.dashboard_item import DashboardItem

DASHBOARD_COLORS: List[str] = ["white", "blue", "green", "purple", "black"]


def _create_default_app_items(dashboard: Dashboard) -> None:

    DashboardItem.objects.create(
        team=dashboard.team,
        dashboard=dashboard,
        name="Daily Active Users (DAUs)",
        type=TRENDS_LINEAR,
        filters={
            TREND_FILTER_TYPE_EVENTS: [{"id": "$pageview", "math": "dau", "type": TREND_FILTER_TYPE_EVENTS}],
            INTERVAL: "day",
        },
        last_refresh=now(),
        description="Shows the number of unique users that use your app everyday.",
    )

    DashboardItem.objects.create(
        team=dashboard.team,
        dashboard=dashboard,
        name="Weekly revenue (from Order Completed)",
        type=TRENDS_LINEAR,
        filters={
            TREND_FILTER_TYPE_EVENTS: [
                {"id": "Order Completed", "math": "sum", "type": TREND_FILTER_TYPE_EVENTS, "math_property": "revenue"}
            ],
            INTERVAL: "week",
            DATE_FROM: "-60d",
        },
        last_refresh=now(),
        color=random.choice(DASHBOARD_COLORS),
        description="Shows how much revenue your app is capturing from orders every week. "
        'Sales should be registered with an "Order Completed" event.',
    )

    DashboardItem.objects.create(
        team=dashboard.team,
        dashboard=dashboard,
        name="Cumulative DAUs",
        type=TRENDS_CUMULATIVE,
        filters={
            TREND_FILTER_TYPE_EVENTS: [{"id": "$pageview", "math": "dau", "type": TREND_FILTER_TYPE_EVENTS}],
            INTERVAL: "day",
            DATE_FROM: "-30d",
            DISPLAY: TRENDS_CUMULATIVE,
        },
        last_refresh=now(),
        color=random.choice(DASHBOARD_COLORS),
        description="Shows the total cumulative number of unique users that have been using your app.",
    )

    DashboardItem.objects.create(
        team=dashboard.team,
        dashboard=dashboard,
        name="Repeat users over time",
        type=TRENDS_LINEAR,
        filters={
            TREND_FILTER_TYPE_EVENTS: [{"id": "$pageview", "math": "dau", "type": TREND_FILTER_TYPE_EVENTS}],
            INTERVAL: "day",
            SHOWN_AS: TRENDS_STICKINESS,
        },
        last_refresh=now(),
        color=random.choice(DASHBOARD_COLORS),
        description="Shows you how many users visited your app for a specific number of days "
        '(e.g. a user that visited your app twice in the time period will be shown under "2 days").',
    )

    DashboardItem.objects.create(
        team=dashboard.team,
        dashboard=dashboard,
        name="Sample - Purchase conversion funnel",
        type=TRENDS_FUNNEL,
        filters={
            TREND_FILTER_TYPE_EVENTS: [
                {"id": "$pageview", "type": TREND_FILTER_TYPE_EVENTS, "order": 0},
                {
                    "id": "$autocapture",
                    "name": "Clicked purchase button",
                    "type": TREND_FILTER_TYPE_EVENTS,
                    PROPERTIES: [
                        {"key": "$event_type", "type": "event", "value": "click"},
                        {"key": "text", "type": "element", "value": "Purchase"},
                    ],
                    "order": 1,
                },
                {
                    "id": "$autocapture",
                    "name": "Submitted checkout form",
                    "type": TREND_FILTER_TYPE_EVENTS,
                    PROPERTIES: [
                        {"key": "$event_type", "type": "event", "value": "submit"},
                        {"key": "$pathname", "type": "event", "value": "/purchase"},
                    ],
                    "order": 2,
                },
                {"id": "Order Completed", "name": "Order Completed", "type": TREND_FILTER_TYPE_EVENTS, "order": 3},
            ],
            INSIGHT: "FUNNELS",
        },
        last_refresh=now(),
        color=random.choice(DASHBOARD_COLORS),
        is_sample=True,
        description="This is a sample of how a user funnel could look like. It represents the number of users that performed "
        "a specific action at each step.",
    )

    DashboardItem.objects.create(
        team=dashboard.team,
        dashboard=dashboard,
        name="Users by browser (last 2 weeks)",
        type=TRENDS_PIE,
        filters={
            TREND_FILTER_TYPE_EVENTS: [{"id": "$pageview", "math": "dau", "type": TREND_FILTER_TYPE_EVENTS}],
            DATE_FROM: "-14d",
            INTERVAL: "day",
            BREAKDOWN_TYPE: "person",
            BREAKDOWN: "$browser",
            DISPLAY: TRENDS_PIE,
        },
        last_refresh=now(),
        description="Shows a breakdown of browsers used to visit your app per unique users in the last 14 days.",
    )

    DashboardItem.objects.create(
        team=dashboard.team,
        dashboard=dashboard,
        name="Users by traffic source",
        type=TRENDS_LINEAR,
        filters={
            TREND_FILTER_TYPE_EVENTS: [{"id": "$pageview", "math": "dau", "type": TREND_FILTER_TYPE_EVENTS}],
            INTERVAL: "day",
            BREAKDOWN_TYPE: "event",
            BREAKDOWN: "$initial_referring_domain",
        },
        last_refresh=now(),
        description="Shows a breakdown of where unique users came from when visiting your app.",
    )


DASHBOARD_TEMPLATES: Dict[str, Callable] = {
    "DEFAULT_APP": _create_default_app_items,
}


def create_dashboard_from_template(template_key: str, dashboard: Dashboard) -> None:

    if template_key not in DASHBOARD_TEMPLATES:
        raise AttributeError(f"Invalid template key `{template_key}` provided.")

    DASHBOARD_TEMPLATES[template_key](dashboard)
