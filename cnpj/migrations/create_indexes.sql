-- ============================================================================
-- Índices para otimização de consultas CNPJ no CRM-5.0
-- ============================================================================
-- 
-- Este script cria índices otimizados para:
-- 1. Busca full-text com pg_trgm (tolerância a erros)
-- 2. Filtros por UF, município, situação
-- 3. Performance geral de consultas
--
-- Executar como superuser ou owner do schema 'crm'
-- ============================================================================

-- Habilitar extensão pg_trgm (necessária para busca fuzzy)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- Índices GIN para busca full-text (trigram)
-- ============================================================================

-- Índice para busca por razão social (tolerante a erros)
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_razao_social_trgm 
ON crm.cnpj_cache USING gin (razao_social gin_trgm_ops);

-- Índice para busca por nome fantasia (tolerante a erros)
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_nome_fantasia_trgm 
ON crm.cnpj_cache USING gin (nome_fantasia gin_trgm_ops);

-- ============================================================================
-- Índices B-tree para filtros exatos
-- ============================================================================

-- Índice para filtro por UF (muito usado)
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_uf 
ON crm.cnpj_cache(uf);

-- Índice para filtro por município
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_municipio 
ON crm.cnpj_cache(municipio);

-- Índice para filtro por situação cadastral
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_situacao 
ON crm.cnpj_cache(situacao_cadastral);

-- Índice composto para filtros combinados (UF + situação)
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_uf_situacao 
ON crm.cnpj_cache(uf, situacao_cadastral);

-- ============================================================================
-- Índices para ordenação e paginação
-- ============================================================================

-- Índice para ordenação por razão social
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_razao_social_btree 
ON crm.cnpj_cache(razao_social);

-- Índice para ordenação por data de consulta (útil para refresh)
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_data_consulta 
ON crm.cnpj_cache(data_consulta);

-- ============================================================================
-- Índices JSONB para campos raw_json e socios
-- ============================================================================

-- Índice GIN para busca em raw_json
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_raw_json 
ON crm.cnpj_cache USING gin (raw_json);

-- Índice GIN para busca em socios
CREATE INDEX IF NOT EXISTS idx_cnpj_cache_socios 
ON crm.cnpj_cache USING gin (socios);

-- ============================================================================
-- Estatísticas e análise
-- ============================================================================

-- Atualizar estatísticas da tabela para otimizar planos de consulta
ANALYZE crm.cnpj_cache;

-- ============================================================================
-- Verificação dos índices criados
-- ============================================================================

SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'crm' 
  AND tablename = 'cnpj_cache'
ORDER BY indexname;

-- ============================================================================
-- Estimativa de tamanho dos índices
-- ============================================================================

SELECT 
    schemaname || '.' || tablename AS table_name,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'crm' 
  AND tablename = 'cnpj_cache'
ORDER BY pg_relation_size(indexrelid) DESC;
