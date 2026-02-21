"""
Script para carregar dados de CNPJs no banco do CRM-5.0.

Este script lê dados da Receita Federal e carrega no banco PostgreSQL do CRM,
aplicando os filtros: apenas CNPJs ATIVOS e sem MEI.

Uso:
    python load_data_to_crm.py --database-url "postgresql://user:pass@host:5432/crm"
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def limpar_cnpj(cnpj: str) -> str:
    """Remove formatação do CNPJ."""
    return "".join(c for c in str(cnpj) if c.isdigit())


def parse_csv_line(line: str) -> dict:
    """
    Parse uma linha do CSV da Receita Federal.
    
    Formato esperado (separado por ponto-e-vírgula):
    CNPJ;RAZAO_SOCIAL;NOME_FANTASIA;SITUACAO;...
    """
    parts = line.strip().split(';')
    
    if len(parts) < 20:
        return None
    
    try:
        return {
            'cnpj': limpar_cnpj(parts[0]),
            'razao_social': parts[1].strip(),
            'nome_fantasia': parts[2].strip() if parts[2] else None,
            'situacao_cadastral': parts[3].strip(),
            'data_situacao_cadastral': parts[4].strip() if parts[4] else None,
            'data_inicio_atividade': parts[5].strip() if parts[5] else None,
            'natureza_juridica': parts[6].strip() if parts[6] else None,
            'porte': parts[7].strip() if parts[7] else None,
            'capital_social': float(parts[8].replace(',', '.')) if parts[8] else None,
            'cnae_fiscal': parts[9].strip() if parts[9] else None,
            'cnae_fiscal_descricao': parts[10].strip() if parts[10] else None,
            'logradouro': parts[11].strip() if parts[11] else None,
            'numero': parts[12].strip() if parts[12] else None,
            'complemento': parts[13].strip() if parts[13] else None,
            'bairro': parts[14].strip() if parts[14] else None,
            'municipio': parts[15].strip() if parts[15] else None,
            'uf': parts[16].strip() if parts[16] else None,
            'cep': parts[17].strip() if parts[17] else None,
            'telefone_1': parts[18].strip() if parts[18] else None,
            'email': parts[19].strip() if parts[19] else None,
            'opcao_pelo_simples': parts[20].strip() if len(parts) > 20 and parts[20] else None,
            'opcao_pelo_mei': parts[21].strip() if len(parts) > 21 and parts[21] else None,
        }
    except (ValueError, IndexError) as e:
        logger.warning(f"Erro ao parsear linha: {e}")
        return None


def should_include(data: dict) -> bool:
    """
    Verifica se o CNPJ deve ser incluído.
    
    Critérios:
    - Situação cadastral ATIVA
    - NÃO é MEI
    """
    situacao = data.get('situacao_cadastral', '').upper()
    mei = data.get('opcao_pelo_mei', '').upper()
    
    is_active = 'ATIVA' in situacao
    is_not_mei = mei != 'SIM'
    
    return is_active and is_not_mei


def load_from_csv(csv_path: Path, database_url: str, batch_size: int = 1000):
    """
    Carrega dados de arquivo CSV para o banco do CRM.
    
    Args:
        csv_path: Caminho para arquivo CSV
        database_url: URL de conexão com PostgreSQL
        batch_size: Tamanho do lote para inserção
    """
    logger.info(f"Conectando ao banco: {database_url}")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    
    # Verificar se tabela existe
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'crm' AND table_name = 'cnpj_cache')"
        ))
        if not result.scalar():
            logger.error("Tabela crm.cnpj_cache não existe!")
            sys.exit(1)
    
    logger.info(f"Lendo arquivo: {csv_path}")
    
    total_lines = 0
    included = 0
    excluded_inactive = 0
    excluded_mei = 0
    batch = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Pular cabeçalho
        next(f)
        
        for line in tqdm(f, desc="Processando CNPJs"):
            total_lines += 1
            
            data = parse_csv_line(line)
            if not data:
                continue
            
            # Aplicar filtros
            if not should_include(data):
                situacao = data.get('situacao_cadastral', '').upper()
                mei = data.get('opcao_pelo_mei', '').upper()
                
                if 'ATIVA' not in situacao:
                    excluded_inactive += 1
                elif mei == 'SIM':
                    excluded_mei += 1
                continue
            
            # Adicionar ao lote
            batch.append(data)
            included += 1
            
            # Inserir lote quando atingir tamanho
            if len(batch) >= batch_size:
                insert_batch(Session, batch)
                batch = []
    
    # Inserir lote restante
    if batch:
        insert_batch(Session, batch)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Processamento concluído!")
    logger.info(f"Total de linhas processadas: {total_lines:,}")
    logger.info(f"CNPJs incluídos (ativos, sem MEI): {included:,}")
    logger.info(f"Excluídos (inativos): {excluded_inactive:,}")
    logger.info(f"Excluídos (MEI): {excluded_mei:,}")
    logger.info(f"Taxa de inclusão: {(included/total_lines*100):.1f}%")
    logger.info(f"{'='*60}")


def insert_batch(Session, batch: list):
    """Insere lote de CNPJs no banco."""
    session = Session()
    try:
        for data in batch:
            # Preparar dados para inserção
            insert_data = {
                'cnpj': data['cnpj'],
                'razao_social': data.get('razao_social'),
                'nome_fantasia': data.get('nome_fantasia'),
                'situacao_cadastral': data.get('situacao_cadastral'),
                'data_situacao_cadastral': data.get('data_situacao_cadastral'),
                'data_inicio_atividade': data.get('data_inicio_atividade'),
                'natureza_juridica': data.get('natureza_juridica'),
                'porte': data.get('porte'),
                'capital_social': data.get('capital_social'),
                'cnae_fiscal': data.get('cnae_fiscal'),
                'cnae_fiscal_descricao': data.get('cnae_fiscal_descricao'),
                'logradouro': data.get('logradouro'),
                'numero': data.get('numero'),
                'complemento': data.get('complemento'),
                'bairro': data.get('bairro'),
                'municipio': data.get('municipio'),
                'uf': data.get('uf'),
                'cep': data.get('cep'),
                'telefone_1': data.get('telefone_1'),
                'email': data.get('email'),
                'opcao_pelo_simples': data.get('opcao_pelo_simples'),
                'opcao_pelo_mei': data.get('opcao_pelo_mei'),
                'data_consulta': datetime.now(),
                'raw_json': data,  # Salvar dados completos
            }
            
            # Insert com ON CONFLICT (upsert)
            stmt = text("""
                INSERT INTO crm.cnpj_cache (
                    cnpj, razao_social, nome_fantasia, situacao_cadastral,
                    data_situacao_cadastral, data_inicio_atividade,
                    natureza_juridica, porte, capital_social,
                    cnae_fiscal, cnae_fiscal_descricao,
                    logradouro, numero, complemento, bairro,
                    municipio, uf, cep,
                    telefone_1, email,
                    opcao_pelo_simples, opcao_pelo_mei,
                    data_consulta, raw_json
                ) VALUES (
                    :cnpj, :razao_social, :nome_fantasia, :situacao_cadastral,
                    :data_situacao_cadastral, :data_inicio_atividade,
                    :natureza_juridica, :porte, :capital_social,
                    :cnae_fiscal, :cnae_fiscal_descricao,
                    :logradouro, :numero, :complemento, :bairro,
                    :municipio, :uf, :cep,
                    :telefone_1, :email,
                    :opcao_pelo_simples, :opcao_pelo_mei,
                    :data_consulta, :raw_json::jsonb
                )
                ON CONFLICT (cnpj) DO UPDATE SET
                    razao_social = EXCLUDED.razao_social,
                    nome_fantasia = EXCLUDED.nome_fantasia,
                    situacao_cadastral = EXCLUDED.situacao_cadastral,
                    updated_at = NOW()
            """)
            
            session.execute(stmt, {
                **insert_data,
                'raw_json': json.dumps(data, ensure_ascii=False)
            })
        
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Erro ao inserir lote: {e}")
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Carrega dados de CNPJs no banco do CRM-5.0"
    )
    parser.add_argument(
        '--csv',
        type=Path,
        required=True,
        help='Caminho para arquivo CSV com dados da Receita Federal'
    )
    parser.add_argument(
        '--database-url',
        type=str,
        required=True,
        help='URL de conexão PostgreSQL (ex: postgresql://user:pass@host:5432/crm)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Tamanho do lote para inserção (padrão: 1000)'
    )
    
    args = parser.parse_args()
    
    if not args.csv.exists():
        logger.error(f"Arquivo não encontrado: {args.csv}")
        sys.exit(1)
    
    load_from_csv(args.csv, args.database_url, args.batch_size)


if __name__ == '__main__':
    main()
