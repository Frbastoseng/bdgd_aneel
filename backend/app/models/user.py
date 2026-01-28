"""
Modelos do banco de dados para usuários e autenticação
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class UserStatus(str, enum.Enum):
    """Status do usuário no sistema"""
    PENDING = "pending"      # Aguardando aprovação
    APPROVED = "approved"    # Aprovado pelo admin
    REJECTED = "rejected"    # Rejeitado pelo admin
    SUSPENDED = "suspended"  # Suspenso


class UserRole(str, enum.Enum):
    """Tipos de usuário"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(Base):
    """Modelo de usuário"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    status = Column(SQLEnum(UserStatus), default=UserStatus.PENDING, nullable=False)
    
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Quem aprovou
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by = relationship("User", remote_side=[id], foreign_keys=[approved_by_id])
    
    # Motivo de rejeição (se aplicável)
    rejection_reason = Column(Text, nullable=True)
    
    # Relacionamentos
    access_requests = relationship("AccessRequest", back_populates="user", foreign_keys="AccessRequest.user_id")
    
    def __repr__(self):
        return f"<User {self.email}>"


class AccessRequest(Base):
    """Solicitações de acesso pendentes"""
    __tablename__ = "access_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Mensagem do usuário
    message = Column(Text, nullable=True)
    
    # Status da solicitação
    status = Column(SQLEnum(UserStatus), default=UserStatus.PENDING, nullable=False)
    
    # Resposta do admin
    admin_response = Column(Text, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relacionamentos
    user = relationship("User", back_populates="access_requests", foreign_keys=[user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    
    def __repr__(self):
        return f"<AccessRequest {self.id} - User {self.user_id}>"


class RefreshToken(Base):
    """Tokens de refresh para sessões"""
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_revoked = Column(Boolean, default=False)
    
    user = relationship("User")
    
    def __repr__(self):
        return f"<RefreshToken {self.id}>"


class AuditLog(Base):
    """Log de auditoria de ações"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User")
    
    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id}>"


class SavedQuery(Base):
    """Consultas salvas pelo usuário"""
    __tablename__ = "saved_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Nome e descrição da consulta
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Filtros salvos em JSON
    filters = Column(Text, nullable=False)  # JSON string com todos os filtros
    
    # Tipo de consulta (consulta, mapa, tarifas)
    query_type = Column(String(50), default="consulta")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Contador de uso
    use_count = Column(Integer, default=0)
    
    # Relacionamento
    user = relationship("User")
    
    def __repr__(self):
        return f"<SavedQuery {self.name} by {self.user_id}>"
