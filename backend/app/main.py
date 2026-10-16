"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.deps import DbSession
from app.api.v1 import router as api_v1_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check(db: DbSession):
    """Health check endpoint."""
    try:
        await db.execute(text("SELECT 1"))
        if settings.ENVIRONMENT == "production":
            from redis.asyncio import from_url

            client = from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
            try:
                await client.ping()
            finally:
                await client.aclose()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependencies unavailable") from exc
    return {"status": "healthy", "version": settings.APP_VERSION}


app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
