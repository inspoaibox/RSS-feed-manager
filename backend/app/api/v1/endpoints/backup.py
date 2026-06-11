"""Backup and restore API endpoints."""
import json
import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from webdav3.client import Client
from webdav3.exceptions import WebDavException

from app.api.deps import CurrentUserId, DbSession
from app.models.ai_provider import AIModel, AIProvider
from app.models.category import Category
from app.models.custom_rule import CustomRule
from app.models.feed import Feed
from app.models.system_settings import SystemSettings
from sqlalchemy import select

router = APIRouter()


# WebDAV Configuration Models
class WebDAVConfig(BaseModel):
    """WebDAV configuration."""
    server_url: str
    username: str
    password: str
    backup_path: str = "/rss_manager_backups/"


class WebDAVConfigResponse(BaseModel):
    """WebDAV configuration response (without password)."""
    server_url: Optional[str] = None
    username: Optional[str] = None
    backup_path: str = "/rss_manager_backups/"
    configured: bool = False


class WebDAVBackupInfo(BaseModel):
    """WebDAV backup file info."""
    filename: str
    size: int
    modified: str


class WebDAVBackupList(BaseModel):
    """List of WebDAV backups."""
    backups: List[WebDAVBackupInfo]


def get_webdav_client(config: dict) -> Client:
    """Create WebDAV client from config."""
    options = {
        'webdav_hostname': config['server_url'],
        'webdav_login': config['username'],
        'webdav_password': config['password'],
    }
    return Client(options)


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
                "use_playwright": f.use_playwright,
                "browser_engine": getattr(
                    f,
                    "browser_engine",
                    "playwright" if f.use_playwright else "http",
                ),
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

            browser_engine = feed_data.get(
                "browser_engine",
                "playwright" if feed_data.get("use_playwright", False) else "http",
            )
            
            feed = Feed(
                user_id=user_id,
                url=feed_data["url"],
                title=feed_data.get("title", ""),
                category_id=category_id,
                fetch_interval=feed_data.get("fetch_interval", 3600),
                is_active=feed_data.get("is_active", True),
                use_playwright=feed_data.get("use_playwright", browser_engine != "http"),
                browser_engine=browser_engine,
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


# ==================== WebDAV Backup APIs ====================

WEBDAV_CONFIG_KEY = "webdav_config"


async def get_webdav_config_from_db(db: DbSession, user_id: int) -> Optional[dict]:
    """Get WebDAV config from database."""
    result = await db.execute(
        select(SystemSettings).where(
            SystemSettings.key == f"{WEBDAV_CONFIG_KEY}_{user_id}"
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        return json.loads(setting.value)
    return None


async def save_webdav_config_to_db(db: DbSession, user_id: int, config: dict):
    """Save WebDAV config to database."""
    key = f"{WEBDAV_CONFIG_KEY}_{user_id}"
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = json.dumps(config)
    else:
        setting = SystemSettings(key=key, value=json.dumps(config))
        db.add(setting)
    
    await db.commit()


async def generate_backup_data(db: DbSession, user_id: int) -> dict:
    """Generate backup data for a user."""
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
    
    return {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "categories": [{"name": c.name} for c in categories],
        "feeds": [
            {
                "url": f.url,
                "title": f.title,
                "category_name": next((c.name for c in categories if c.id == f.category_id), None),
                "fetch_interval": f.fetch_interval,
                "is_active": f.is_active,
                "use_playwright": f.use_playwright,
                "browser_engine": getattr(
                    f,
                    "browser_engine",
                    "playwright" if f.use_playwright else "http",
                ),
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


@router.get("/webdav/config", response_model=WebDAVConfigResponse)
async def get_webdav_config(user_id: CurrentUserId, db: DbSession):
    """Get WebDAV configuration (without password)."""
    config = await get_webdav_config_from_db(db, user_id)
    if config:
        return WebDAVConfigResponse(
            server_url=config.get("server_url"),
            username=config.get("username"),
            backup_path=config.get("backup_path", "/rss_manager_backups/"),
            configured=True,
        )
    return WebDAVConfigResponse(configured=False)


@router.post("/webdav/config")
async def save_webdav_config(config: WebDAVConfig, user_id: CurrentUserId, db: DbSession):
    """Save WebDAV configuration."""
    # If password is empty, try to use existing password
    config_dict = config.dict()
    if not config_dict.get("password"):
        existing_config = await get_webdav_config_from_db(db, user_id)
        if existing_config and existing_config.get("password"):
            config_dict["password"] = existing_config["password"]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码不能为空"
            )
    
    # Test connection first
    try:
        client = get_webdav_client(config_dict)
        # Try to check if backup path exists, create if not
        backup_path = config_dict["backup_path"].rstrip('/') + '/'
        if not client.check(backup_path):
            client.mkdir(backup_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"WebDAV 连接失败: {str(e)}"
        )
    
    await save_webdav_config_to_db(db, user_id, config_dict)
    return {"success": True, "message": "WebDAV 配置已保存"}


@router.post("/webdav/test")
async def test_webdav_connection(config: WebDAVConfig, user_id: CurrentUserId, db: DbSession):
    """Test WebDAV connection without saving."""
    config_dict = config.dict()
    if not config_dict.get("password"):
        existing_config = await get_webdav_config_from_db(db, user_id)
        if existing_config and existing_config.get("password"):
            config_dict["password"] = existing_config["password"]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码不能为空"
            )
    
    try:
        client = get_webdav_client(config_dict)
        # Test by checking root or backup path
        backup_path = config_dict["backup_path"].rstrip('/') + '/'
        # Try to list root to verify connection
        client.list("/")
        return {"success": True, "message": "WebDAV 连接成功"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"WebDAV 连接失败: {str(e)}"
        )


@router.get("/webdav/list", response_model=WebDAVBackupList)
async def list_webdav_backups(user_id: CurrentUserId, db: DbSession):
    """List all backups from WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        
        if not client.check(backup_path):
            return WebDAVBackupList(backups=[])
        
        # webdavclient3 list() returns list of filenames (strings)
        files = client.list(backup_path)
        backups = []
        
        for filename in files:
            # Skip empty strings and non-json files
            if not filename or not filename.endswith('.json'):
                continue
            
            # Try to get file info
            try:
                remote_path = backup_path + filename
                info = client.info(remote_path)
                size = int(info.get('size', 0) or 0)
                modified = str(info.get('modified', '') or '')
            except Exception:
                size = 0
                modified = ''
            
            backups.append(WebDAVBackupInfo(
                filename=filename,
                size=size,
                modified=modified,
            ))
        
        # Sort by filename descending (since filenames contain timestamps)
        backups.sort(key=lambda x: x.filename, reverse=True)
        return WebDAVBackupList(backups=backups)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取备份列表失败: {str(e)}"
        )


@router.post("/webdav/upload")
async def upload_to_webdav(user_id: CurrentUserId, db: DbSession):
    """Upload current backup to WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        # Generate backup data
        backup_data = await generate_backup_data(db, user_id)
        content = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        # Upload to WebDAV
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        filename = f"rss_manager_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        remote_path = backup_path + filename
        
        # Ensure backup directory exists
        if not client.check(backup_path):
            client.mkdir(backup_path)
        
        # Upload using buffer
        buffer = io.BytesIO(content.encode('utf-8'))
        client.upload_to(buffer, remote_path)
        
        return {"success": True, "filename": filename, "message": "备份已上传到 WebDAV"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传备份失败: {str(e)}"
        )


@router.get("/webdav/download/{filename}")
async def download_from_webdav(filename: str, user_id: CurrentUserId, db: DbSession):
    """Download a specific backup from WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        remote_path = backup_path + filename
        
        if not client.check(remote_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="备份文件不存在"
            )
        
        # Download to buffer
        buffer = io.BytesIO()
        client.download_from(remote_path, buffer)
        buffer.seek(0)
        content = buffer.read()
        
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载备份失败: {str(e)}"
        )


@router.post("/webdav/restore/{filename}", response_model=ImportResult)
async def restore_from_webdav(filename: str, user_id: CurrentUserId, db: DbSession):
    """Restore from a specific WebDAV backup."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        remote_path = backup_path + filename
        
        if not client.check(remote_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="备份文件不存在"
            )
        
        # Download backup content
        buffer = io.BytesIO()
        client.download_from(remote_path, buffer)
        buffer.seek(0)
        content = buffer.read()
        
        # Parse and import
        try:
            data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError:
            return ImportResult(success=False, errors=["无效的 JSON 文件"])
        
        # Reuse import logic
        errors = []
        categories_imported = 0
        feeds_imported = 0
        ai_providers_imported = 0
        custom_rules_imported = 0
        
        category_map = {}
        
        # Import categories
        for cat_data in data.get("categories", []):
            try:
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
                result = await db.execute(
                    select(Feed).where(
                        Feed.user_id == user_id,
                        Feed.url == feed_data["url"]
                    )
                )
                if result.scalar_one_or_none():
                    continue
                
                category_id = None
                if feed_data.get("category_name"):
                    category_id = category_map.get(feed_data["category_name"])

                browser_engine = feed_data.get(
                    "browser_engine",
                    "playwright" if feed_data.get("use_playwright", False) else "http",
                )
                
                feed = Feed(
                    user_id=user_id,
                    url=feed_data["url"],
                    title=feed_data.get("title", ""),
                    category_id=category_id,
                    fetch_interval=feed_data.get("fetch_interval", 3600),
                    is_active=feed_data.get("is_active", True),
                    use_playwright=feed_data.get("use_playwright", browser_engine != "http"),
                    browser_engine=browser_engine,
                )
                db.add(feed)
                feeds_imported += 1
            except Exception as e:
                errors.append(f"订阅源 '{feed_data.get('url', '?')}': {str(e)}")
        
        provider_map = {}
        
        # Import AI providers
        for provider_data in data.get("ai_providers", []):
            try:
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
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复备份失败: {str(e)}"
        )


@router.delete("/webdav/delete/{filename}")
async def delete_webdav_backup(filename: str, user_id: CurrentUserId, db: DbSession):
    """Delete a specific backup from WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV 未配置"
        )
    
    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip('/') + '/'
        remote_path = backup_path + filename
        
        if not client.check(remote_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="备份文件不存在"
            )
        
        client.clean(remote_path)
        return {"success": True, "message": "备份已删除"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除备份失败: {str(e)}"
        )
