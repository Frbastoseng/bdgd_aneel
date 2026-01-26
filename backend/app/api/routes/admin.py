"""
Rotas de administração
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.models.user import User, UserStatus, UserRole
from app.schemas.user import (
    UserResponse,
    UserListResponse,
    AdminUserUpdate,
    AdminStats,
    AccessRequestResponse,
    AccessRequestReview,
    PendingRequestsResponse
)
from app.services.auth_service import AuthService, AccessRequestService, UserService
from app.api.deps import get_current_admin

router = APIRouter(prefix="/admin", tags=["Administração"])


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Estatísticas do dashboard admin"""
    stats = await UserService.get_admin_stats(db)
    return AdminStats(**stats)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[UserStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Lista todos os usuários"""
    skip = (page - 1) * per_page
    users, total = await UserService.get_users(db, skip=skip, limit=per_page, status=status)
    
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Obtém detalhes de um usuário"""
    user = await AuthService.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    update_data: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Atualiza um usuário (role, status, ativo)"""
    user = await UserService.update_user(
        db,
        user_id,
        role=update_data.role,
        status=update_data.status,
        is_active=update_data.is_active
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    return user


@router.get("/access-requests", response_model=PendingRequestsResponse)
async def list_pending_requests(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Lista solicitações de acesso pendentes"""
    skip = (page - 1) * per_page
    requests, total = await AccessRequestService.get_pending_requests(db, skip=skip, limit=per_page)
    
    response_requests = []
    for req in requests:
        response_requests.append(AccessRequestResponse(
            id=req.id,
            user_id=req.user_id,
            user_email=req.user.email,
            user_name=req.user.full_name,
            message=req.message,
            status=req.status,
            admin_response=req.admin_response,
            created_at=req.created_at,
            reviewed_at=req.reviewed_at
        ))
    
    return PendingRequestsResponse(
        requests=response_requests,
        total=total
    )


@router.post("/access-requests/{request_id}/review", response_model=AccessRequestResponse)
async def review_access_request(
    request_id: int,
    review_data: AccessRequestReview,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Aprovar ou rejeitar solicitação de acesso"""
    if review_data.status not in [UserStatus.APPROVED, UserStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status deve ser 'approved' ou 'rejected'"
        )
    
    request = await AccessRequestService.review_request(
        db,
        request_id,
        admin_id=current_admin.id,
        status=review_data.status,
        admin_response=review_data.admin_response
    )
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação não encontrada"
        )
    
    return AccessRequestResponse(
        id=request.id,
        user_id=request.user_id,
        user_email=request.user.email,
        user_name=request.user.full_name,
        message=request.message,
        status=request.status,
        admin_response=request.admin_response,
        created_at=request.created_at,
        reviewed_at=request.reviewed_at
    )


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Suspende um usuário"""
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode suspender a si mesmo"
        )
    
    user = await UserService.update_user(db, user_id, status=UserStatus.SUSPENDED)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    return {"message": "Usuário suspenso com sucesso"}


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Reativa um usuário suspenso"""
    user = await UserService.update_user(db, user_id, status=UserStatus.APPROVED, is_active=True)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    return {"message": "Usuário ativado com sucesso"}
