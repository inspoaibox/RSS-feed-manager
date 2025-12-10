"""Repository for AnalysisQuery database operations."""
from typing import List

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_query import AnalysisQuery


class AnalysisQueryRepository:
    """Repository for AnalysisQuery CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, query: str) -> AnalysisQuery:
        """
        Create a new analysis query record.
        
        Args:
            user_id: The user ID
            query: The query text
            
        Returns:
            The created AnalysisQuery
        """
        analysis_query = AnalysisQuery(user_id=user_id, query=query)
        self.session.add(analysis_query)
        await self.session.flush()
        return analysis_query

    async def get_by_id(self, query_id: int, user_id: int) -> AnalysisQuery | None:
        """
        Get an analysis query by ID.
        
        Args:
            query_id: The query ID
            user_id: The user ID (for ownership verification)
            
        Returns:
            The AnalysisQuery or None if not found
        """
        result = await self.session.execute(
            select(AnalysisQuery).where(
                AnalysisQuery.id == query_id,
                AnalysisQuery.user_id == user_id
            )
        )
        return result.scalar_one_or_none()


    async def get_recent_by_user(
        self, user_id: int, limit: int = 10
    ) -> List[AnalysisQuery]:
        """
        Get recent analysis queries for a user.
        
        Args:
            user_id: The user ID
            limit: Maximum number of queries to return (default 10)
            
        Returns:
            List of recent AnalysisQuery objects
        """
        result = await self.session.execute(
            select(AnalysisQuery)
            .where(AnalysisQuery.user_id == user_id)
            .order_by(desc(AnalysisQuery.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete(self, query_id: int, user_id: int) -> bool:
        """
        Delete an analysis query.
        
        Args:
            query_id: The query ID
            user_id: The user ID (for ownership verification)
            
        Returns:
            True if deleted, False if not found
        """
        result = await self.session.execute(
            delete(AnalysisQuery).where(
                AnalysisQuery.id == query_id,
                AnalysisQuery.user_id == user_id
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def delete_old_queries(self, user_id: int, keep_count: int = 10) -> int:
        """
        Delete old queries keeping only the most recent ones.
        
        Args:
            user_id: The user ID
            keep_count: Number of recent queries to keep
            
        Returns:
            Number of deleted queries
        """
        # 获取要保留的查询 ID
        keep_query = (
            select(AnalysisQuery.id)
            .where(AnalysisQuery.user_id == user_id)
            .order_by(desc(AnalysisQuery.created_at))
            .limit(keep_count)
        )
        keep_result = await self.session.execute(keep_query)
        keep_ids = [row[0] for row in keep_result.fetchall()]

        if not keep_ids:
            return 0

        # 删除不在保留列表中的查询
        delete_result = await self.session.execute(
            delete(AnalysisQuery).where(
                AnalysisQuery.user_id == user_id,
                AnalysisQuery.id.notin_(keep_ids)
            )
        )
        await self.session.flush()
        return delete_result.rowcount
