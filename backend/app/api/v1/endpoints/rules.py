"""Custom rules API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.custom_rule import (
    AIGenerateRuleRequest,
    AIGenerateRuleResponse,
    CustomRuleCreate,
    CustomRuleResponse,
    CustomRuleTestRequest,
    CustomRuleTestResult,
    CustomRuleUpdate,
)
from app.services.custom_rule_service import CustomRuleService

router = APIRouter()


@router.get("", response_model=list[CustomRuleResponse])
async def get_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all custom rules for the current user."""
    service = CustomRuleService(db)
    return await service.get_user_rules(current_user.id)


@router.post("", response_model=CustomRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    data: CustomRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new custom rule."""
    service = CustomRuleService(db)
    return await service.create_rule(current_user.id, data)


@router.get("/{rule_id}", response_model=CustomRuleResponse)
async def get_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific custom rule."""
    service = CustomRuleService(db)
    rule = await service.get_rule(rule_id, current_user.id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    return rule


@router.put("/{rule_id}", response_model=CustomRuleResponse)
async def update_rule(
    rule_id: int,
    data: CustomRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a custom rule."""
    service = CustomRuleService(db)
    rule = await service.update_rule(rule_id, current_user.id, data)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom rule."""
    service = CustomRuleService(db)
    deleted = await service.delete_rule(rule_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )


@router.post("/test", response_model=CustomRuleTestResult)
async def test_rule(
    data: CustomRuleTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test a custom rule without saving it."""
    service = CustomRuleService(db)
    return await service.test_rule(current_user.id, data)


@router.post("/generate", response_model=AIGenerateRuleResponse)
async def generate_rule(
    data: AIGenerateRuleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Use AI to automatically generate CSS selectors for a webpage."""
    service = CustomRuleService(db)
    return await service.generate_rule_with_ai(current_user.id, data.target_url, data.custom_prompt)


@router.get("/generate/default-prompt")
async def get_default_generate_prompt(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the default prompt template for AI rule generation."""
    service = CustomRuleService(db)
    return {"prompt": service.get_default_generate_prompt()}


@router.post("/{rule_id}/execute", response_model=dict)
async def execute_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually execute a custom rule to fetch articles."""
    service = CustomRuleService(db)
    rule = await service.get_rule(rule_id, current_user.id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    
    try:
        articles = await service.execute_rule(rule)
        return {"success": True, "articles_found": len(articles)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute rule: {str(e)}"
        )
