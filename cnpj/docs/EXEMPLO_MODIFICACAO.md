# 📝 Exemplo de Modificação do CnpjService

## Arquivo: `app/services/cnpj_service.py`

### Modificação Necessária

Você precisa fazer apenas **UMA** alteração no arquivo existente do CRM.

### Passo 1: Adicionar Import (no topo do arquivo)

Localize a seção de imports no início do arquivo e adicione:

```python
from app.services.cnpj_local_service import CnpjLocalService
```

**Exemplo completo da seção de imports:**

```python
"""Service for CNPJ lookup with local cache + minhareceita.org fallback."""

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CnpjCache, Funcionario, Grupo, GrupoFuncionario, Lead
from app.repositories.lead_repository import LeadRepository
from app.services.cnpj_local_service import CnpjLocalService  # ← ADICIONAR ESTA LINHA

logger = logging.getLogger(__name__)
```

### Passo 2: Substituir Método `_fetch_from_api`

Localize o método `_fetch_from_api` (aproximadamente na linha 400-450) e **substitua completamente** por:

**ANTES (código original):**

```python
async def _fetch_from_api(self, cnpj: str) -> dict:
    """Call minhareceita.org and return JSON response."""
    url = f"{self.MINHA_RECEITA_URL}/{cnpj}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
            
            if "message" in data and "CNPJ" in data.get("message", ""):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"CNPJ {cnpj} nao encontrado na Receita Federal."
                )
            
            return data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CNPJ {cnpj} nao encontrado."
            )
        logger.error(f"HTTP error calling minhareceita.org: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao consultar API externa."
        )
    except Exception as e:
        logger.error(f"Error calling minhareceita.org: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao consultar API externa."
        )
```

**DEPOIS (novo código):**

```python
async def _fetch_from_api(self, cnpj: str) -> dict:
    """
    Busca CNPJ no banco de dados local (substituindo chamada à API externa).
    
    Args:
        cnpj: CNPJ limpo (14 dígitos)
        
    Returns:
        dict: Dados do CNPJ no formato da API minhareceita.org
        
    Raises:
        HTTPException: Se CNPJ não encontrado (404)
    """
    local_service = CnpjLocalService(self.db)
    return local_service.consultar_cnpj(cnpj)
```

### Resumo das Alterações

| Item | Ação | Localização |
|------|------|-------------|
| 1 | Adicionar import | Topo do arquivo (seção de imports) |
| 2 | Substituir método | Linha ~400-450 (método `_fetch_from_api`) |

### Verificação

Após as alterações, o método `consultar_cnpj` (que usa `_fetch_from_api` internamente) continuará funcionando exatamente da mesma forma, mas agora consultando o banco local ao invés da API externa.

**Teste:**

```python
# Este código continua funcionando sem alterações
service = CnpjService(db)
resultado = await service.consultar_cnpj("00000000000191")
print(resultado['razao_social'])  # BANCO DO BRASIL S.A.
```

### Rollback (se necessário)

Se precisar voltar para a API externa, basta reverter as alterações:

1. Remover o import `from app.services.cnpj_local_service import CnpjLocalService`
2. Restaurar o código original do método `_fetch_from_api`

---

**Nota**: Todas as outras partes do `CnpjService` permanecem inalteradas. Apenas este método é modificado para usar o banco local.
