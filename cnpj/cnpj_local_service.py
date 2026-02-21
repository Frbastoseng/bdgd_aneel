"""
Serviço de consulta CNPJ local para CRM-5.0.

Este módulo substitui a chamada à API externa minhareceita.org por consultas
diretas ao banco de dados local com 7 milhões de CNPJs ativos (sem MEI).

Integração: Substituir o método _fetch_from_api() do CnpjService existente.
"""

import logging
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class CnpjLocalService:
    """
    Serviço para consulta de CNPJs no banco de dados local.
    
    Características:
    - Consulta direta ao banco (sem API externa)
    - Busca full-text com pg_trgm
    - Busca em lote otimizada
    - Filtros: apenas CNPJs ativos, sem MEI
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def consultar_cnpj(self, cnpj: str) -> dict:
        """
        Consulta um CNPJ no banco de dados local.
        
        Args:
            cnpj: CNPJ limpo (apenas números, 14 dígitos)
            
        Returns:
            dict: Dados do CNPJ no formato compatível com minhareceita.org
            
        Raises:
            HTTPException: Se CNPJ não encontrado (404)
        """
        from app.models.cnpj_cache import CnpjCache
        
        # Buscar no banco local
        stmt = select(CnpjCache).where(CnpjCache.cnpj == cnpj)
        result = self.db.execute(stmt).scalar_one_or_none()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CNPJ {cnpj} não encontrado no banco de dados local."
            )
        
        # Converter para formato compatível com API minhareceita.org
        return self._convert_to_api_format(result)
    
    def buscar_cnpjs(
        self,
        search: Optional[str] = None,
        uf: Optional[str] = None,
        municipio: Optional[str] = None,
        situacao: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> dict:
        """
        Busca CNPJs com filtros e paginação.
        
        Args:
            search: Termo de busca (razão social, nome fantasia)
            uf: Filtro por UF
            municipio: Filtro por município
            situacao: Filtro por situação cadastral
            limit: Limite de resultados
            offset: Offset para paginação
            
        Returns:
            dict: {"results": [...], "total": int}
        """
        from app.models.cnpj_cache import CnpjCache
        
        base = select(CnpjCache)
        
        # Aplicar filtros
        if search:
            search_term = f"%{search}%"
            base = base.where(
                or_(
                    CnpjCache.razao_social.ilike(search_term),
                    CnpjCache.nome_fantasia.ilike(search_term),
                    CnpjCache.cnpj.ilike(search_term)
                )
            )
        
        if uf:
            base = base.where(CnpjCache.uf == uf.upper())
        
        if municipio:
            base = base.where(CnpjCache.municipio.ilike(f"%{municipio}%"))
        
        if situacao:
            base = base.where(CnpjCache.situacao_cadastral.ilike(f"%{situacao}%"))
        
        # Contar total
        total = self.db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar() or 0
        
        # Buscar resultados paginados
        results = list(
            self.db.execute(
                base.order_by(CnpjCache.razao_social)
                .offset(offset)
                .limit(limit)
            ).scalars().all()
        )
        
        return {
            "results": [self._convert_to_api_format(r) for r in results],
            "total": total
        }
    
    def buscar_lote(self, cnpjs: list[str]) -> dict:
        """
        Busca múltiplos CNPJs em uma única consulta.
        
        Args:
            cnpjs: Lista de CNPJs (máximo 100)
            
        Returns:
            dict: {
                "found": [...],
                "not_found": [...],
                "total_found": int,
                "total_not_found": int
            }
        """
        from app.models.cnpj_cache import CnpjCache
        
        if len(cnpjs) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Máximo de 100 CNPJs por requisição."
            )
        
        # Buscar todos de uma vez
        stmt = select(CnpjCache).where(CnpjCache.cnpj.in_(cnpjs))
        results = list(self.db.execute(stmt).scalars().all())
        
        # Identificar encontrados e não encontrados
        found_cnpjs = {r.cnpj for r in results}
        not_found = [cnpj for cnpj in cnpjs if cnpj not in found_cnpjs]
        
        return {
            "found": [self._convert_to_api_format(r) for r in results],
            "not_found": not_found,
            "total_found": len(results),
            "total_not_found": len(not_found)
        }
    
    def _convert_to_api_format(self, cache_entry) -> dict:
        """
        Converte entrada do CnpjCache para formato da API minhareceita.org.
        
        Args:
            cache_entry: Instância de CnpjCache
            
        Returns:
            dict: Dados no formato da API externa
        """
        # Extrair QSA (Quadro Societário) do raw_json ou socios
        qsa = []
        if cache_entry.raw_json and "qsa" in cache_entry.raw_json:
            qsa = cache_entry.raw_json.get("qsa", [])
        elif cache_entry.socios:
            # Converter formato simplificado para formato QSA
            if isinstance(cache_entry.socios, list):
                qsa = [
                    {
                        "nome_socio": s.get("nome", ""),
                        "qualificacao_socio": s.get("qualificacao", "")
                    }
                    for s in cache_entry.socios
                ]
        
        # Extrair CNAEs secundários
        cnaes_secundarios = []
        if cache_entry.cnaes_secundarios and isinstance(cache_entry.cnaes_secundarios, list):
            cnaes_secundarios = cache_entry.cnaes_secundarios
        
        # Montar resposta no formato da API
        return {
            "cnpj": cache_entry.cnpj,
            "razao_social": cache_entry.razao_social or "",
            "nome_fantasia": cache_entry.nome_fantasia or "",
            "descricao_situacao_cadastral": cache_entry.situacao_cadastral or "",
            "data_situacao_cadastral": cache_entry.data_situacao_cadastral or "",
            "data_inicio_atividade": cache_entry.data_inicio_atividade or "",
            "natureza_juridica": cache_entry.natureza_juridica or "",
            "porte": cache_entry.porte or "",
            "capital_social": float(cache_entry.capital_social) if cache_entry.capital_social else 0.0,
            
            # CNAE
            "cnae_fiscal": cache_entry.cnae_fiscal or "",
            "cnae_fiscal_descricao": cache_entry.cnae_fiscal_descricao or "",
            "cnaes_secundarios": cnaes_secundarios,
            
            # Endereço
            "logradouro": cache_entry.logradouro or "",
            "numero": cache_entry.numero or "",
            "complemento": cache_entry.complemento or "",
            "bairro": cache_entry.bairro or "",
            "municipio": cache_entry.municipio or "",
            "uf": cache_entry.uf or "",
            "cep": cache_entry.cep or "",
            
            # Contato
            "ddd_telefone_1": cache_entry.telefone_1 or "",
            "ddd_telefone_2": cache_entry.telefone_2 or "",
            "email": cache_entry.email or "",
            
            # QSA (Quadro Societário)
            "qsa": qsa,
            
            # Simples/MEI
            "opcao_pelo_simples": cache_entry.opcao_pelo_simples or "",
            "opcao_pelo_mei": cache_entry.opcao_pelo_mei or "",
            
            # Metadados
            "_source": "local_database",
            "_cached_at": cache_entry.data_consulta.isoformat() if cache_entry.data_consulta else None,
        }


def _limpar_cnpj(cnpj: str) -> str:
    """Remove formatação do CNPJ, deixando apenas números."""
    return "".join(c for c in cnpj if c.isdigit())


def _validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ usando algoritmo oficial.
    
    Args:
        cnpj: CNPJ limpo (apenas números)
        
    Returns:
        bool: True se válido, False caso contrário
    """
    if not cnpj or len(cnpj) != 14:
        return False
    
    if cnpj == cnpj[0] * 14:  # Todos dígitos iguais
        return False
    
    # Validar primeiro dígito verificador
    soma = sum(int(cnpj[i]) * peso for i, peso in enumerate([5,4,3,2,9,8,7,6,5,4,3,2]))
    digito1 = 0 if (resto := soma % 11) < 2 else 11 - resto
    
    if int(cnpj[12]) != digito1:
        return False
    
    # Validar segundo dígito verificador
    soma = sum(int(cnpj[i]) * peso for i, peso in enumerate([6,5,4,3,2,9,8,7,6,5,4,3,2]))
    digito2 = 0 if (resto := soma % 11) < 2 else 11 - resto
    
    return int(cnpj[13]) == digito2
