"""Bounded upload helpers."""

from fastapi import HTTPException, UploadFile

from app.core.config import settings


async def read_upload_limited(file: UploadFile) -> bytes:
    content = await file.read(settings.MAX_IMPORT_BYTES + 1)
    if len(content) > settings.MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {settings.MAX_IMPORT_BYTES // (1024 * 1024)} MB limit",
        )
    return content
