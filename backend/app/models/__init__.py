"""SQLAlchemy models."""

from app.models.ai_provider import AIModel, AIProvider
from app.models.analysis_query import AnalysisQuery
from app.models.argos_translation_log import ArgosTranslationLog
from app.models.article import Article, UserArticle
from app.models.category import Category
from app.models.custom_rule import CustomRule
from app.models.external_notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationRule,
    NotificationRuleChannel,
)
from app.models.feed import Feed
from app.models.google_translate_key import GoogleTranslateKey
from app.models.keyword_article_match import KeywordArticleMatch
from app.models.keyword_subscription import KeywordSubscription
from app.models.proxy_pool import ProxyPoolEntry
from app.models.push_notification import (
    NotificationPush,
    NotificationSubscription,
    WebPushSubscription,
)
from app.models.recommended_feed import RecommendedFeed
from app.models.system_settings import SystemSettings
from app.models.user import User

__all__ = [
    "User",
    "Category",
    "Feed",
    "Article",
    "UserArticle",
    "AIProvider",
    "AIModel",
    "CustomRule",
    "SystemSettings",
    "AnalysisQuery",
    "RecommendedFeed",
    "KeywordSubscription",
    "KeywordArticleMatch",
    "ProxyPoolEntry",
    "GoogleTranslateKey",
    "ArgosTranslationLog",
    "NotificationSubscription",
    "NotificationPush",
    "WebPushSubscription",
    "NotificationChannel",
    "NotificationRule",
    "NotificationRuleChannel",
    "NotificationDelivery",
]


def _install_notification_hooks():
    from app.services.notification_outbox import install_outbox_hooks

    install_outbox_hooks()


_install_notification_hooks()
