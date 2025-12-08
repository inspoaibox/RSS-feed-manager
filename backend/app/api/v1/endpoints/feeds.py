"""Feed API endpoints."""
from typing import List

from fastapi import APIRouter, File, Response, UploadFile, status

from app.api.deps import CurrentUserId, DbSession
from app.schemas.feed import FeedCreate, FeedResponse, FeedUpdate, OPMLImportResult
from app.services.feed_service import FeedService

router = APIRouter()


@router.get("", response_model=List[FeedResponse])
async def get_feeds(user_id: CurrentUserId, db: DbSession):
    """Get all feeds for the current user."""
    service = FeedService(db)
    return await service.get_all(user_id)


@router.post("", response_model=FeedResponse, status_code=status.HTTP_201_CREATED)
async def create_feed(data: FeedCreate, user_id: CurrentUserId, db: DbSession):
    """Add a new feed by URL."""
    service = FeedService(db)
    return await service.create(user_id, data)


@router.get("/{feed_id}", response_model=FeedResponse)
async def get_feed(feed_id: int, user_id: CurrentUserId, db: DbSession):
    """Get a feed by ID."""
    service = FeedService(db)
    return await service.get_by_id(user_id, feed_id)


@router.put("/{feed_id}", response_model=FeedResponse)
async def update_feed(feed_id: int, data: FeedUpdate, user_id: CurrentUserId, db: DbSession):
    """Update a feed."""
    service = FeedService(db)
    return await service.update(user_id, feed_id, data)


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feed(feed_id: int, user_id: CurrentUserId, db: DbSession):
    """Delete a feed."""
    service = FeedService(db)
    await service.delete(user_id, feed_id)


@router.post("/{feed_id}/refresh", response_model=FeedResponse)
async def refresh_feed(feed_id: int, user_id: CurrentUserId, db: DbSession):
    """Manually refresh a feed."""
    service = FeedService(db)
    return await service.refresh(user_id, feed_id)


@router.post("/import", response_model=OPMLImportResult)
async def import_opml(file: UploadFile = File(...), user_id: CurrentUserId = None, db: DbSession = None):
    """Import feeds from OPML file."""
    content = await file.read()
    service = FeedService(db)
    return await service.import_opml(user_id, content.decode("utf-8"))


@router.get("/export/opml")
async def export_opml(user_id: CurrentUserId, db: DbSession):
    """Export feeds to OPML format."""
    service = FeedService(db)
    opml_content = await service.export_opml(user_id)
    return Response(
        content=opml_content,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=subscriptions.opml"}
    )
