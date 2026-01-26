"""
Serviço de autenticação e gerenciamento de usuários
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.models.user import User, UserStatus, UserRole, AccessRequest, RefreshToken
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.core.config import settings
from app.schemas.user import UserCreate, Token


class AuthService:
    """Serviço de autenticação"""
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Busca usuário por email"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Busca usuário por ID"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
        """Cria novo usuário com status pendente"""
        hashed_password = get_password_hash(user_data.password)
        
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            company=user_data.company,
            phone=user_data.phone,
            role=UserRole.USER,
            status=UserStatus.PENDING
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Criar solicitação de acesso
        access_request = AccessRequest(
            user_id=user.id,
            message=user_data.message,
            status=UserStatus.PENDING
        )
        db.add(access_request)
        await db.commit()
        
        return user
    
    @staticmethod
    async def create_admin_user(db: AsyncSession) -> Optional[User]:
        """Cria usuário admin padrão se não existir"""
        existing = await AuthService.get_user_by_email(db, settings.ADMIN_EMAIL)
        if existing:
            return existing
        
        # Garantir que a senha não está vazia e truncar se necessário (bcrypt max 72 bytes)
        admin_password = settings.ADMIN_PASSWORD or "admin123456"
        if len(admin_password.encode('utf-8')) > 72:
            admin_password = admin_password[:72]
        
        hashed_password = get_password_hash(admin_password)
        
        admin = User(
            email=settings.ADMIN_EMAIL,
            hashed_password=hashed_password,
            full_name="Administrador",
            role=UserRole.ADMIN,
            status=UserStatus.APPROVED,
            approved_at=datetime.utcnow()
        )
        
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        
        return admin
    
    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
        """Autentica usuário"""
        user = await AuthService.get_user_by_email(db, email)
        
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user
    
    @staticmethod
    async def create_tokens(db: AsyncSession, user: User) -> Token:
        """Cria tokens de acesso e refresh"""
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Salvar refresh token no banco
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        db_token = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at
        )
        db.add(db_token)
        
        # Atualizar último login
        user.last_login = datetime.utcnow()
        
        await db.commit()
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    
    @staticmethod
    async def refresh_tokens(db: AsyncSession, refresh_token: str) -> Optional[Token]:
        """Renova tokens usando refresh token"""
        result = await db.execute(
            select(RefreshToken)
            .where(
                and_(
                    RefreshToken.token == refresh_token,
                    RefreshToken.is_revoked == False,
                    RefreshToken.expires_at > datetime.utcnow()
                )
            )
        )
        db_token = result.scalar_one_or_none()
        
        if not db_token:
            return None
        
        # Revogar token antigo
        db_token.is_revoked = True
        
        # Buscar usuário
        user = await AuthService.get_user_by_id(db, db_token.user_id)
        if not user or not user.is_active or user.status != UserStatus.APPROVED:
            return None
        
        # Criar novos tokens
        return await AuthService.create_tokens(db, user)
    
    @staticmethod
    async def logout(db: AsyncSession, user_id: int) -> bool:
        """Revoga todos os refresh tokens do usuário"""
        result = await db.execute(
            select(RefreshToken)
            .where(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            )
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            token.is_revoked = True
        
        await db.commit()
        return True


class AccessRequestService:
    """Serviço de solicitações de acesso"""
    
    @staticmethod
    async def get_pending_requests(db: AsyncSession, skip: int = 0, limit: int = 50) -> Tuple[List[AccessRequest], int]:
        """Lista solicitações pendentes"""
        # Count
        count_result = await db.execute(
            select(func.count(AccessRequest.id))
            .where(AccessRequest.status == UserStatus.PENDING)
        )
        total = count_result.scalar()
        
        # Requests
        result = await db.execute(
            select(AccessRequest)
            .options(selectinload(AccessRequest.user))
            .where(AccessRequest.status == UserStatus.PENDING)
            .order_by(AccessRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        requests = result.scalars().all()
        
        return requests, total
    
    @staticmethod
    async def review_request(
        db: AsyncSession,
        request_id: int,
        admin_id: int,
        status: UserStatus,
        admin_response: Optional[str] = None
    ) -> Optional[AccessRequest]:
        """Admin revisa solicitação"""
        result = await db.execute(
            select(AccessRequest)
            .options(selectinload(AccessRequest.user))
            .where(AccessRequest.id == request_id)
        )
        request = result.scalar_one_or_none()
        
        if not request:
            return None
        
        # Atualizar solicitação
        request.status = status
        request.admin_response = admin_response
        request.reviewed_by_id = admin_id
        request.reviewed_at = datetime.utcnow()
        
        # Atualizar usuário
        user = request.user
        user.status = status
        user.approved_by_id = admin_id
        
        if status == UserStatus.APPROVED:
            user.approved_at = datetime.utcnow()
        elif status == UserStatus.REJECTED:
            user.rejection_reason = admin_response
        
        await db.commit()
        await db.refresh(request)
        
        return request


class UserService:
    """Serviço de gerenciamento de usuários"""
    
    @staticmethod
    async def get_users(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        status: Optional[UserStatus] = None
    ) -> Tuple[List[User], int]:
        """Lista usuários com filtros"""
        query = select(User)
        count_query = select(func.count(User.id))
        
        if status:
            query = query.where(User.status == status)
            count_query = count_query.where(User.status == status)
        
        # Count
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # Users
        result = await db.execute(
            query.order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        users = result.scalars().all()
        
        return users, total
    
    @staticmethod
    async def update_user(
        db: AsyncSession,
        user_id: int,
        **kwargs
    ) -> Optional[User]:
        """Atualiza usuário"""
        user = await AuthService.get_user_by_id(db, user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        
        await db.commit()
        await db.refresh(user)
        
        return user
    
    @staticmethod
    async def change_password(
        db: AsyncSession,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> bool:
        """Muda senha do usuário"""
        user = await AuthService.get_user_by_id(db, user_id)
        if not user:
            return False
        
        if not verify_password(current_password, user.hashed_password):
            return False
        
        user.hashed_password = get_password_hash(new_password)
        await db.commit()
        
        return True
    
    @staticmethod
    async def get_admin_stats(db: AsyncSession) -> dict:
        """Estatísticas para dashboard admin"""
        # Total de usuários
        total_result = await db.execute(select(func.count(User.id)))
        total_users = total_result.scalar()
        
        # Pendentes
        pending_result = await db.execute(
            select(func.count(AccessRequest.id))
            .where(AccessRequest.status == UserStatus.PENDING)
        )
        pending_requests = pending_result.scalar()
        
        # Ativos
        active_result = await db.execute(
            select(func.count(User.id))
            .where(
                and_(
                    User.status == UserStatus.APPROVED,
                    User.is_active == True
                )
            )
        )
        active_users = active_result.scalar()
        
        return {
            "total_users": total_users,
            "pending_requests": pending_requests,
            "active_users": active_users,
            "total_queries_today": 0  # Implementar com logs
        }
