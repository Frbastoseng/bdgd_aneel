"""Cliente HTTP para consultar a API de Geração Distribuída (microserviço GD)."""

import logging
import time
from typing import Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache simples em memória com TTL
_cache: Dict[str, dict] = {}
_cache_ts: Dict[str, float] = {}
CACHE_TTL = 300  # 5 minutos


def _get_cached(key: str) -> Optional[dict]:
    if key in _cache and (time.time() - _cache_ts.get(key, 0)) < CACHE_TTL:
        return _cache[key]
    return None


def _set_cached(key: str, value: dict):
    _cache[key] = value
    _cache_ts[key] = time.time()


async def buscar_multiplos_cegs(cegs: List[str]) -> Dict[str, dict]:
    """Busca dados de GD para múltiplos códigos CEG via batch endpoint.

    Retorna dict {ceg: dados_gd} para os que foram encontrados.
    Usa cache para evitar chamadas repetidas.
    """
    if not cegs:
        return {}

    # Separar cached e não-cached
    resultado = {}
    cegs_para_buscar = []

    for ceg in cegs:
        cached = _get_cached(f"ceg:{ceg}")
        if cached is not None:
            resultado[ceg] = cached
        else:
            cegs_para_buscar.append(ceg)

    if not cegs_para_buscar:
        return resultado

    # Buscar no microserviço GD
    url = f"{settings.GD_API_URL}/api/v1/gd/batch?include_tecnico=true"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json={"codigos": cegs_para_buscar})
            response.raise_for_status()
            data = response.json()

            # Cachear resultados
            for ceg, gd_data in data.items():
                _set_cached(f"ceg:{ceg}", gd_data)
                resultado[ceg] = gd_data

            # Cachear misses (CEGs não encontrados) como dict vazio
            for ceg in cegs_para_buscar:
                if ceg not in data:
                    _set_cached(f"ceg:{ceg}", {})

    except httpx.HTTPStatusError as e:
        logger.warning(f"GD API retornou erro {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        logger.warning(f"Erro ao consultar GD API: {e}")

    return resultado


async def buscar_por_cnpj(cnpj: str) -> List[dict]:
    """Busca empreendimentos GD por CNPJ."""
    url = f"{settings.GD_API_URL}/api/v1/gd/cnpj/{cnpj}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.warning(f"Erro ao buscar GD por CNPJ {cnpj}: {e}")
        return []
