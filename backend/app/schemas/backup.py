"""Backup data operations."""

from typing import Any

from pydantic import BaseModel, Field


class BackupData(BaseModel):
    """Backup data structure."""

    version: str = "1.0"
    exported_at: str
    user_settings: dict[str, Any] = Field(default_factory=dict)
    notification_channels: list[dict[str, Any]] = Field(default_factory=list)
    notification_rules: list[dict[str, Any]] = Field(default_factory=list)
    categories: list[dict[str, Any]]
    feeds: list[dict[str, Any]]
    articles: list[dict[str, Any]] = Field(default_factory=list)
    user_articles: list[dict[str, Any]] = Field(default_factory=list)
    ai_providers: list[dict[str, Any]]
    ai_models: list[dict[str, Any]]
    custom_rules: list[dict[str, Any]]
    keyword_subscriptions: list[dict[str, Any]] = Field(default_factory=list)
    proxy_pool_entries: list[dict[str, Any]] = Field(default_factory=list)
    google_translate_keys: list[dict[str, Any]] = Field(default_factory=list)
    analysis_queries: list[dict[str, Any]] = Field(default_factory=list)
    recommended_feeds: list[dict[str, Any]] = Field(default_factory=list)
    notifications: list[dict[str, Any]] = Field(default_factory=list)
    user_notification_reads: list[dict[str, Any]] = Field(default_factory=list)


class ImportResult(BaseModel):
    """Import result."""

    success: bool
    categories_imported: int = 0
    feeds_imported: int = 0
    articles_imported: int = 0
    user_articles_imported: int = 0
    ai_providers_imported: int = 0
    ai_models_imported: int = 0
    custom_rules_imported: int = 0
    keyword_subscriptions_imported: int = 0
    proxy_pool_entries_imported: int = 0
    google_translate_keys_imported: int = 0
    analysis_queries_imported: int = 0
    recommended_feeds_imported: int = 0
    notifications_imported: int = 0
    user_notification_reads_imported: int = 0
    updated: int = 0
    errors: list[str] = Field(default_factory=list)
