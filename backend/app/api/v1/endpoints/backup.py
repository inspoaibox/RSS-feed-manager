"""Backup and restore API endpoints."""
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, File, Response, UploadFile, status
from pydantic import BaseModel

from app.api.deps import CurrentUserId, DbSession
from app.models.ai_provider import AIModel, AIProvider
from app.models.category import Category
from app.models.custom_rule import CustomRule
from app.models.feed import Feed
from sqlalchemy import select

router = APIRouter()


class BackupData(BaseModel):
    """Backup data structure."""
    version: str = "1.0"
    exported_at: str
    categories: List[Dict[str, Any]]
    feeds: List[Dict[str, Any]]
    ai_providers: List[Dict[str, Any]]
    ai_models: List[Dict[str, Any]]
    custom_rules: List[Dict[str, Any]]


class ImportResult(BaseModel):
    """Import result."""
    success: bool
    categories_imported: int = 0
    feeds_imported: int = 0
    ai_providers_imported: int = 0
    custom_rules_imported: int = 0
    errors: List[str] = []


@router.get("/export")
async def export_all(user_id: CurrentUserId, db: DbSession):
    """Export all user settings and subscriptions."""
    # Get categories
    result = await db.execute(select(Category).where(Category.user_id == user_id))
    categories = result.scalars().all()
    
    # Get feeds
    result = await db.execute(select(Feed).where(Feed.user_id == user_id))
    feeds = result.scalars().all()
    
    # Get AI providers
    result = await db.execute(select(AIProvider).where(AIProvider.user_id == user_id))
    providers = result.scalars().all()
    
    # Get AI models
    provider_ids = [p.id for p in providers]
    models = []
    if provider_ids:
        result = await db.execute(select(AIModel).where(AIModel.provider_id.in_(provider_ids)))
        models = result.scalars().all()
    
    # Get custom rules
    result = await db.execute(select(CustomRule).where(CustomRule.user_id == user_id))
    rules = result.scalars().all()
    
    # Build backup data
    backup = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "categories": [
            {"name": c.name}
            for c in categories
        ],
        "feeds": [
            {
                "url": f.url,
                "title": f.title,
                "category_name": next((c.name for c in categories if c.id == f.category_id), None),
                "fetch_interval": f.fetch_interval,
                "is_active": f.is_active,
            }
            for f in feeds
        ],
        "ai_providers": [
            {
                "name": p.name,
                "type": p.type,
                "api_key": p.api_key,
                "base_url": p.base_url,
                "is_active": p.is_active,
            }
            for p in providers
        ],
        "ai_models": [
            {
                "provider_name": next((p.name for p in providers if p.id == m.provider_id), None),
                "name": m.name,
                "model_id": m.model_id,
                "is_default": m.is_default,
            }
            for m in models
        ],
        "custom_rules": [
            {
                "name": r.name,
                "target_url": r.target_url,
                "list_selector": r.list_selector,
                "title_selector": r.title_selector,
                "link_selector": r.link_selector,
                "content_selector": r.content_selector,
                "fetch_interval": r.fetch_interval,
                "is_active": r.is_active,
            }
            for r in rules
        ],
    }
    
    import json
    content = json.dumps(backup, ensure_ascii=False, indent=2)
    filename = f"rss_manager_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/import", response_model=ImportResult)
async def import_all(
    file: UploadFile = File(...),
    user_id: CurrentUserId = None,
    db: DbSession = None
):
    """Import settings and subscriptions from backup file."""
    import json
    
    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        return ImportResult(success=False, errors=["无效的 JSON 文件"])
    
    errors = []
    categories_imported = 0
    feeds_imported = 0
    ai_providers_imported = 0
    custom_rules_imported = 0
    
    # Category name to ID mapping
    category_map = {}
    
    # Import categories
    for cat_data in data.get("categories", []):
        try:
            # Check if category exists
            result = await db.execute(
                select(Category).where(
                    Category.user_id == user_id,
                    Category.name == cat_data["name"]
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                category_map[cat_data["name"]] = existing.id
            else:
                category = Category(user_id=user_id, name=cat_data["name"])
                db.add(category)
                await db.flush()
                category_map[cat_data["name"]] = category.id
                categories_imported += 1
        except Exception as e:
            errors.append(f"分类 '{cat_data.get('name', '?')}': {str(e)}")
    
    # Import feeds
    for feed_data in data.get("feeds", []):
        try:
            # Check if feed exists
            result = await db.execute(
                select(Feed).where(
                    Feed.user_id == user_id,
                    Feed.url == feed_data["url"]
                )
            )
            if result.scalar_one_or_none():
                continue  # Skip existing
            
            category_id = None
            if feed_data.get("category_name"):
                category_id = category_map.get(feed_data["category_name"])
            
            feed = Feed(
                user_id=user_id,
                url=feed_data["url"],
                title=feed_data.get("title", ""),
                category_id=category_id,
                fetch_interval=feed_data.get("fetch_interval", 3600),
                is_active=feed_data.get("is_active", True),
            )
            db.add(feed)
            feeds_imported += 1
        except Exception as e:
            errors.append(f"订阅源 '{feed_data.get('url', '?')}': {str(e)}")
    
    # Provider name to ID mapping
    provider_map = {}
    
    # Import AI providers
    for provider_data in data.get("ai_providers", []):
        try:
            # Check if provider exists
            result = await db.execute(
                select(AIProvider).where(
                    AIProvider.user_id == user_id,
                    AIProvider.name == provider_data["name"]
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                provider_map[provider_data["name"]] = existing.id
            else:
                provider = AIProvider(
                    user_id=user_id,
                    name=provider_data["name"],
                    type=provider_data["type"],
                    api_key=provider_data["api_key"],
                    base_url=provider_data.get("base_url"),
                    is_active=provider_data.get("is_active", True),
                )
                db.add(provider)
                await db.flush()
                provider_map[provider_data["name"]] = provider.id
                ai_providers_imported += 1
        except Exception as e:
            errors.append(f"AI 渠道 '{provider_data.get('name', '?')}': {str(e)}")
    
    # Import AI models
    for model_data in data.get("ai_models", []):
        try:
            provider_name = model_data.get("provider_name")
            if not provider_name or provider_name not in provider_map:
                continue
            
            provider_id = provider_map[provider_name]
            
            # Check if model exists
            result = await db.execute(
                select(AIModel).where(
                    AIModel.provider_id == provider_id,
                    AIModel.model_id == model_data["model_id"]
                )
            )
            if result.scalar_one_or_none():
                continue
            
            model = AIModel(
                provider_id=provider_id,
                name=model_data["name"],
                model_id=model_data["model_id"],
                is_default=model_data.get("is_default", False),
            )
            db.add(model)
        except Exception as e:
            errors.append(f"AI 模型 '{model_data.get('name', '?')}': {str(e)}")
    
    # Import custom rules
    for rule_data in data.get("custom_rules", []):
        try:
            # Check if rule exists
            result = await db.execute(
                select(CustomRule).where(
                    CustomRule.user_id == user_id,
                    CustomRule.target_url == rule_data["target_url"]
                )
            )
            if result.scalar_one_or_none():
                continue
            
            rule = CustomRule(
                user_id=user_id,
                name=rule_data["name"],
                target_url=rule_data["target_url"],
                list_selector=rule_data["list_selector"],
                title_selector=rule_data["title_selector"],
                link_selector=rule_data["link_selector"],
                content_selector=rule_data.get("content_selector"),
                fetch_interval=rule_data.get("fetch_interval", 3600),
                is_active=rule_data.get("is_active", True),
            )
            db.add(rule)
            custom_rules_imported += 1
        except Exception as e:
            errors.append(f"自定义规则 '{rule_data.get('name', '?')}': {str(e)}")
    
    await db.commit()
    
    return ImportResult(
        success=len(errors) == 0,
        categories_imported=categories_imported,
        feeds_imported=feeds_imported,
        ai_providers_imported=ai_providers_imported,
        custom_rules_imported=custom_rules_imported,
        errors=errors,
    )
