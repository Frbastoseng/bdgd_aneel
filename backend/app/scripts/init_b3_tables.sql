-- Tabelas para matching B3 -> CNPJ
-- Separadas das tabelas ANEEL (bdgd_clientes / bdgd_cnpj_matches)

-- Tabela de clientes B3 (extraídos do parquet)
CREATE TABLE IF NOT EXISTS b3_clientes (
    cod_id TEXT PRIMARY KEY,
    lgrd_original TEXT,
    brr_original TEXT,
    cep_original TEXT,
    cnae_original TEXT,
    logradouro_norm TEXT,
    numero_norm TEXT,
    bairro_norm TEXT,
    cep_norm TEXT,
    cnae_norm TEXT,
    cnae_5dig TEXT,
    mun_code TEXT,
    municipio_nome TEXT,
    uf TEXT,
    point_x FLOAT,
    point_y FLOAT,
    clas_sub TEXT,
    gru_tar TEXT,
    consumo_anual FLOAT,
    consumo_medio FLOAT,
    car_inst FLOAT,
    fas_con TEXT,
    sit_ativ TEXT,
    dic_anual FLOAT,
    fic_anual FLOAT,
    possui_solar BOOLEAN DEFAULT FALSE,
    -- Campos de geocodificação reversa
    geo_logradouro TEXT,
    geo_numero TEXT,
    geo_bairro TEXT,
    geo_cep TEXT,
    geo_municipio TEXT,
    geo_uf TEXT,
    geo_source TEXT,
    geo_status TEXT
);

-- Índices para b3_clientes
CREATE INDEX IF NOT EXISTS idx_b3_clientes_cep ON b3_clientes(cep_norm);
CREATE INDEX IF NOT EXISTS idx_b3_clientes_cnae ON b3_clientes(cnae_norm);
CREATE INDEX IF NOT EXISTS idx_b3_clientes_uf ON b3_clientes(uf);
CREATE INDEX IF NOT EXISTS idx_b3_clientes_municipio ON b3_clientes(municipio_nome);

-- Tabela de matches B3 -> CNPJ
CREATE TABLE IF NOT EXISTS b3_cnpj_matches (
    id SERIAL PRIMARY KEY,
    bdgd_cod_id TEXT NOT NULL REFERENCES b3_clientes(cod_id) ON DELETE CASCADE,
    cnpj TEXT NOT NULL,
    score_total FLOAT NOT NULL DEFAULT 0,
    score_cep FLOAT DEFAULT 0,
    score_cnae FLOAT DEFAULT 0,
    score_endereco FLOAT DEFAULT 0,
    score_numero FLOAT DEFAULT 0,
    score_bairro FLOAT DEFAULT 0,
    rank INTEGER NOT NULL DEFAULT 1,
    address_source TEXT DEFAULT 'bdgd',
    razao_social TEXT,
    nome_fantasia TEXT,
    cnpj_logradouro TEXT,
    cnpj_numero TEXT,
    cnpj_bairro TEXT,
    cnpj_cep TEXT,
    cnpj_municipio TEXT,
    cnpj_uf TEXT,
    cnpj_cnae TEXT,
    cnpj_cnae_descricao TEXT,
    cnpj_situacao TEXT,
    cnpj_telefone TEXT,
    cnpj_email TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para b3_cnpj_matches
CREATE INDEX IF NOT EXISTS idx_b3_matches_cod_id ON b3_cnpj_matches(bdgd_cod_id);
CREATE INDEX IF NOT EXISTS idx_b3_matches_rank ON b3_cnpj_matches(bdgd_cod_id, rank);
CREATE INDEX IF NOT EXISTS idx_b3_matches_score ON b3_cnpj_matches(score_total DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_b3_matches_unique ON b3_cnpj_matches(bdgd_cod_id, cnpj);

-- Tabelas para listas de prospecção B3
CREATE TABLE IF NOT EXISTS b3_listas_prospeccao (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filtros_aplicados JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS b3_lista_unidades (
    lista_id INTEGER NOT NULL REFERENCES b3_listas_prospeccao(id) ON DELETE CASCADE,
    cod_id TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (lista_id, cod_id)
);

CREATE INDEX IF NOT EXISTS idx_b3_listas_user ON b3_listas_prospeccao(user_id);
CREATE INDEX IF NOT EXISTS idx_b3_lista_unidades_lista ON b3_lista_unidades(lista_id);
