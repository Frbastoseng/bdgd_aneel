"""
Módulo CNPJ Local - Standalone data provider for CRM-5.0.

Downloads bulk CNPJ data from Receita Federal (dados abertos)
and populates the crm.cnpj_cache table in PostgreSQL.

Usage:
    python -m cnpj download     # Download from Receita Federal
    python -m cnpj load         # Process and load into database
    python -m cnpj stats        # Show database statistics
    python -m cnpj query <cnpj> # Query a specific CNPJ
"""

__version__ = "1.0.0"
