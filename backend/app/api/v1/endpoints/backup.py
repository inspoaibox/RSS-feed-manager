"""Backup and restore API endpoints."""

import asyncio
import io

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserId, DbSession
from app.core.clock import utc_now
from app.schemas.backup import ImportResult
from app.services.backup_crypto import decrypt_backup, encrypt_backup
from app.services.backup_export import generate_backup_data
from app.services.backup_import import import_backup_data
from app.services.backup_settings import get_webdav_config_from_db, save_webdav_config_to_db
from app.services.webdav_client import (
    LimitedBackupBuffer,
    get_webdav_client,
    guarded_webdav,
    validate_backup_filename,
)
from app.utils.uploads import read_upload_limited

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

    server_url: str | None = None
    username: str | None = None
    backup_path: str = "/rss_manager_backups/"
    configured: bool = False


class WebDAVBackupInfo(BaseModel):
    """WebDAV backup file info."""

    filename: str
    size: int
    modified: str


class WebDAVBackupList(BaseModel):
    """List of WebDAV backups."""

    backups: list[WebDAVBackupInfo]


class BackupPassword(BaseModel):
    passphrase: str = Field(..., min_length=12, max_length=256)


@router.post("/export")
async def export_all(data: BackupPassword, user_id: CurrentUserId, db: DbSession):
    """Export all user settings and data."""
    backup = await generate_backup_data(db, user_id)
    content = await asyncio.to_thread(encrypt_backup, backup, data.passphrase)
    filename = f"rss_manager_backup_{utc_now().strftime('%Y%m%d_%H%M%S')}.json"

    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/import", response_model=ImportResult)
async def import_all(
    file: UploadFile = File(...),
    user_id: CurrentUserId = None,
    db: DbSession = None,
    passphrase: str | None = Form(None, max_length=256),
):
    """Import settings and data from backup file."""
    content = await read_upload_limited(file)
    try:
        data = await asyncio.to_thread(decrypt_backup, content, passphrase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await import_backup_data(db, user_id, data)


# ==================== WebDAV Backup APIs ====================


@router.get("/webdav/config", response_model=WebDAVConfigResponse)
@guarded_webdav
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
@guarded_webdav
async def save_webdav_config(config: WebDAVConfig, user_id: CurrentUserId, db: DbSession):
    """Save WebDAV configuration."""
    # If password is empty, try to use existing password
    config_dict = config.dict()
    if not config_dict.get("password"):
        existing_config = await get_webdav_config_from_db(db, user_id)
        if existing_config and existing_config.get("password"):
            config_dict["password"] = existing_config["password"]
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码不能为空")

    # Test connection first
    try:
        client = get_webdav_client(config_dict)
        # Try to check if backup path exists, create if not
        backup_path = config_dict["backup_path"].rstrip("/") + "/"
        if not await asyncio.to_thread(client.check, backup_path):
            await asyncio.to_thread(client.mkdir, backup_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"WebDAV 连接失败: {str(e)}"
        )

    await save_webdav_config_to_db(db, user_id, config_dict)
    return {"success": True, "message": "WebDAV 配置已保存"}


@router.post("/webdav/test")
@guarded_webdav
async def test_webdav_connection(config: WebDAVConfig, user_id: CurrentUserId, db: DbSession):
    """Test WebDAV connection without saving."""
    config_dict = config.dict()
    if not config_dict.get("password"):
        existing_config = await get_webdav_config_from_db(db, user_id)
        if existing_config and existing_config.get("password"):
            config_dict["password"] = existing_config["password"]
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码不能为空")

    try:
        client = get_webdav_client(config_dict)
        # Test by checking root or backup path
        # Try to list root to verify connection
        await asyncio.to_thread(client.list, "/")
        return {"success": True, "message": "WebDAV 连接成功"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"WebDAV 连接失败: {str(e)}"
        )


@router.get("/webdav/list", response_model=WebDAVBackupList)
@guarded_webdav
async def list_webdav_backups(user_id: CurrentUserId, db: DbSession):
    """List all backups from WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WebDAV 未配置")

    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip("/") + "/"

        if not await asyncio.to_thread(client.check, backup_path):
            return WebDAVBackupList(backups=[])

        # webdavclient3 list() returns list of filenames (strings)
        files = await asyncio.to_thread(client.list, backup_path)
        backups = []

        for filename in files:
            # Skip empty strings and non-json files
            if not filename or not filename.endswith(".json"):
                continue

            # Try to get file info
            try:
                remote_path = backup_path + filename
                info = await asyncio.to_thread(client.info, remote_path)
                size = int(info.get("size", 0) or 0)
                modified = str(info.get("modified", "") or "")
            except Exception:
                size = 0
                modified = ""

            backups.append(
                WebDAVBackupInfo(
                    filename=filename,
                    size=size,
                    modified=modified,
                )
            )

        # Sort by filename descending (since filenames contain timestamps)
        backups.sort(key=lambda x: x.filename, reverse=True)
        return WebDAVBackupList(backups=backups)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取备份列表失败: {str(e)}"
        )


@router.post("/webdav/upload")
@guarded_webdav
async def upload_to_webdav(data: BackupPassword, user_id: CurrentUserId, db: DbSession):
    """Upload current backup to WebDAV."""
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WebDAV 未配置")

    try:
        # Generate backup data
        backup_data = await generate_backup_data(db, user_id)
        content = await asyncio.to_thread(encrypt_backup, backup_data, data.passphrase)

        # Upload to WebDAV
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip("/") + "/"
        filename = f"rss_manager_backup_{utc_now().strftime('%Y%m%d_%H%M%S')}.json"
        remote_path = backup_path + filename

        # Ensure backup directory exists
        if not await asyncio.to_thread(client.check, backup_path):
            await asyncio.to_thread(client.mkdir, backup_path)

        # Upload using buffer
        buffer = io.BytesIO(content)
        await asyncio.to_thread(client.upload_to, buffer, remote_path)

        return {"success": True, "filename": filename, "message": "备份已上传到 WebDAV"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"上传备份失败: {str(e)}"
        )


@router.get("/webdav/download/{filename}")
@guarded_webdav
async def download_from_webdav(filename: str, user_id: CurrentUserId, db: DbSession):
    """Download a specific backup from WebDAV."""
    validate_backup_filename(filename)
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WebDAV 未配置")

    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip("/") + "/"
        remote_path = backup_path + filename

        if not await asyncio.to_thread(client.check, remote_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备份文件不存在")

        # Download to buffer
        buffer = LimitedBackupBuffer()
        await asyncio.to_thread(client.download_from, remote_path, buffer)
        buffer.seek(0)
        content = buffer.read()

        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"下载备份失败: {str(e)}"
        )


@router.post("/webdav/restore/{filename}", response_model=ImportResult)
@guarded_webdav
async def restore_from_webdav(
    filename: str,
    data: BackupPassword,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Restore from a specific WebDAV backup."""
    validate_backup_filename(filename)
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WebDAV 未配置")

    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip("/") + "/"
        remote_path = backup_path + filename

        if not await asyncio.to_thread(client.check, remote_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备份文件不存在")

        # Download backup content
        buffer = LimitedBackupBuffer()
        await asyncio.to_thread(client.download_from, remote_path, buffer)
        buffer.seek(0)
        content = buffer.read()

        # Parse and import
        try:
            backup_data = await asyncio.to_thread(decrypt_backup, content, data.passphrase)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return await import_backup_data(db, user_id, backup_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"恢复备份失败: {str(e)}"
        )


@router.delete("/webdav/delete/{filename}")
@guarded_webdav
async def delete_webdav_backup(filename: str, user_id: CurrentUserId, db: DbSession):
    """Delete a specific backup from WebDAV."""
    validate_backup_filename(filename)
    config = await get_webdav_config_from_db(db, user_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WebDAV 未配置")

    try:
        client = get_webdav_client(config)
        backup_path = config.get("backup_path", "/rss_manager_backups/").rstrip("/") + "/"
        remote_path = backup_path + filename

        if not await asyncio.to_thread(client.check, remote_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备份文件不存在")

        await asyncio.to_thread(client.clean, remote_path)
        return {"success": True, "message": "备份已删除"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除备份失败: {str(e)}"
        )
