"""API v1 router."""
from fastapi import APIRouter

from app.api.v1.endpoints import ai, articles, auth, backup, categories, feeds, keywords, mobile, notifications, oauth, recommendations, rules, stats, system

router = APIRouter()

# Include routers
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(oauth.router, prefix="/auth", tags=["oauth"])  # OAuth under /auth
router.include_router(categories.router, prefix="/categories", tags=["categories"])
router.include_router(feeds.router, prefix="/feeds", tags=["feeds"])
router.include_router(keywords.router, prefix="/keywords", tags=["keywords"])
router.include_router(articles.router, prefix="/articles", tags=["articles"])
router.include_router(mobile.router, prefix="/mobile", tags=["mobile"])
router.include_router(mobile.router, prefix="", tags=["mobile"])
router.include_router(ai.router, prefix="/ai", tags=["ai"])
router.include_router(rules.router, prefix="/rules", tags=["rules"])
router.include_router(backup.router, prefix="/backup", tags=["backup"])
router.include_router(stats.router, prefix="/stats", tags=["stats"])
router.include_router(system.router, prefix="/system", tags=["system"])
router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
