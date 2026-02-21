"""
CLI entry point for the standalone CNPJ module.

Usage:
    python -m cnpj download [--groups empresas,estabelecimentos,socios,simples,lookups]
    python -m cnpj load
    python -m cnpj stats
    python -m cnpj query <cnpj>
    python -m cnpj search <term> [--uf SP] [--limit 10]
    python -m cnpj indexes
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def cmd_download(args):
    """Download data from Receita Federal."""
    from cnpj.downloader import download_all

    groups = args.groups.split(",") if args.groups else None
    download_all(groups)


def cmd_load(args):
    """Process downloaded files and load into database."""
    from cnpj.loader import run_full_load

    run_full_load(delete_after=not args.keep_files)


def cmd_stats(args):
    """Show database statistics."""
    from cnpj.service import get_stats

    stats = get_stats()
    print("\n" + "=" * 50)
    print("  CNPJ Cache - Estatísticas")
    print("=" * 50)
    for key, value in stats.items():
        label = key.replace("_", " ").title()
        if isinstance(value, int):
            print(f"  {label:.<30} {value:>10,}")
        else:
            print(f"  {label:.<30} {value}")
    print("=" * 50)


def cmd_query(args):
    """Query a specific CNPJ."""
    from cnpj.service import consultar_cnpj

    result = consultar_cnpj(args.cnpj)
    if not result:
        print(f"CNPJ {args.cnpj} não encontrado no banco de dados.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print(f"  CNPJ: {result['cnpj']}")
    print("=" * 50)
    for key, value in result.items():
        if key.startswith("_") or key == "cnpj":
            continue
        if isinstance(value, list):
            print(f"  {key}: [{len(value)} itens]")
            for item in value[:5]:
                if isinstance(item, dict):
                    print(f"    - {item.get('nome', item)}")
                else:
                    print(f"    - {item}")
        elif value:
            print(f"  {key}: {value}")
    print("=" * 50)


def cmd_search(args):
    """Search CNPJs by term."""
    from cnpj.service import buscar_cnpjs

    result = buscar_cnpjs(
        search=args.term,
        uf=args.uf,
        limit=args.limit,
    )

    print(f"\nEncontrados: {result['total']} resultados")
    print("-" * 80)
    for r in result["results"]:
        print(f"  {r['cnpj']}  {r['razao_social'][:50]:<50}  {r['uf']}  {r['situacao_cadastral']}")
    print("-" * 80)


def cmd_indexes(args):
    """Create performance indexes."""
    from cnpj.database import get_session

    session = get_session()
    try:
        logger.info("Creating pg_trgm extension ...")
        session.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        session.commit()

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_razao_social_trgm ON crm.cnpj_cache USING gin (razao_social gin_trgm_ops)",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_nome_fantasia_trgm ON crm.cnpj_cache USING gin (nome_fantasia gin_trgm_ops)",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_uf ON crm.cnpj_cache(uf)",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_municipio ON crm.cnpj_cache(municipio)",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_situacao ON crm.cnpj_cache(situacao_cadastral)",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_uf_situacao ON crm.cnpj_cache(uf, situacao_cadastral)",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_razao_social_btree ON crm.cnpj_cache(razao_social)",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_data_consulta ON crm.cnpj_cache(data_consulta)",
        ]

        for idx_sql in indexes:
            logger.info("  %s", idx_sql.split("idx_")[1].split(" ON")[0])
            session.execute(__import__("sqlalchemy").text(idx_sql))
            session.commit()

        session.execute(__import__("sqlalchemy").text("ANALYZE crm.cnpj_cache"))
        session.commit()
        logger.info("All indexes created and statistics updated.")
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        prog="cnpj",
        description="Módulo CNPJ Local - Dados da Receita Federal para CRM-5.0",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comando a executar")

    # download
    dl = subparsers.add_parser("download", help="Download dados da Receita Federal")
    dl.add_argument(
        "--groups",
        type=str,
        default=None,
        help="Grupos para download (comma-separated): empresas,estabelecimentos,socios,simples,lookups",
    )

    # load
    ld = subparsers.add_parser("load", help="Processar arquivos e carregar no banco")
    ld.add_argument("--keep-files", action="store_true", help="Não deletar ZIPs após carga")

    # stats
    subparsers.add_parser("stats", help="Estatísticas do banco de dados")

    # query
    q = subparsers.add_parser("query", help="Consultar um CNPJ específico")
    q.add_argument("cnpj", type=str, help="CNPJ para consultar")

    # search
    s = subparsers.add_parser("search", help="Buscar CNPJs por termo")
    s.add_argument("term", type=str, help="Termo de busca")
    s.add_argument("--uf", type=str, default=None, help="Filtrar por UF")
    s.add_argument("--limit", type=int, default=10, help="Limite de resultados")

    # indexes
    subparsers.add_parser("indexes", help="Criar índices de performance no banco")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "download": cmd_download,
        "load": cmd_load,
        "stats": cmd_stats,
        "query": cmd_query,
        "search": cmd_search,
        "indexes": cmd_indexes,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
