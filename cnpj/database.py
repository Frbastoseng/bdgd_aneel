"""
Standalone database connection for the CNPJ module.

No dependencies on app.* - uses its own engine and session.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cnpj.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    """Get a new database session."""
    return SessionLocal()
