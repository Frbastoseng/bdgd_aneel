"""
Schemas Pydantic para usuários e autenticação
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from app.models.user import UserStatus, UserRole


# ============ Schemas de Autenticação ============

class Token(BaseModel):
    """Resposta de token"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Dados contidos no token"""
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    """Request de login"""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Request para renovar token"""
    refresh_token: str


# ============ Schemas de Usuário ============

class UserBase(BaseModel):
    """Base do usuário"""
    email: EmailStr
    full_name: str = Field(..., min_length=3, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)


class UserCreate(UserBase):
    """Criação de usuário (registro)"""
    password: str = Field(..., min_length=8)
    message: Optional[str] = Field(None, description="Mensagem para o administrador")


class UserUpdate(BaseModel):
    """Atualização de usuário"""
    full_name: Optional[str] = Field(None, min_length=3, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)


class UserResponse(UserBase):
    """Resposta de usuário"""
    id: int
    role: UserRole
    status: UserStatus
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Lista de usuários com paginação"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int


class ChangePasswordRequest(BaseModel):
    """Request para mudar senha"""
    current_password: str
    new_password: str = Field(..., min_length=8)


# ============ Schemas de Solicitação de Acesso ============

class AccessRequestCreate(BaseModel):
    """Criar solicitação de acesso"""
    message: Optional[str] = None


class AccessRequestResponse(BaseModel):
    """Resposta de solicitação"""
    id: int
    user_id: int
    user_email: str
    user_name: str
    message: Optional[str]
    status: UserStatus
    admin_response: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AccessRequestReview(BaseModel):
    """Admin revisar solicitação"""
    status: UserStatus = Field(..., description="approved ou rejected")
    admin_response: Optional[str] = None


class PendingRequestsResponse(BaseModel):
    """Lista de solicitações pendentes"""
    requests: List[AccessRequestResponse]
    total: int


# ============ Schemas de Admin ============

class AdminUserUpdate(BaseModel):
    """Admin atualizar usuário"""
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    is_active: Optional[bool] = None


class AdminStats(BaseModel):
    """Estatísticas para admin"""
    total_users: int
    pending_requests: int
    active_users: int
    total_queries_today: int
