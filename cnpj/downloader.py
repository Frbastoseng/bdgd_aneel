"""
Downloads bulk CNPJ data from Receita Federal open data portal.

Source: https://dados.rfb.gov.br/CNPJ/dados_abertos_cnpj/

Files downloaded:
- Empresas0..9.zip      (razao_social, capital_social, porte, natureza_juridica)
- Estabelecimentos0..9.zip (CNPJ completo, endereco, contato, CNAE, situacao)
- Simples.zip            (opcao_pelo_simples, opcao_pelo_mei)
- Socios0..9.zip         (QSA - quadro societario)
- Lookup tables: Cnaes, Municipios, Naturezas, Qualificacoes, Motivos, Paises
"""

import logging
import re
from pathlib import Path

import httpx

from cnpj.config import DOWNLOAD_DIR, RF_BASE_URL

logger = logging.getLogger(__name__)

# File groups to download
FILE_GROUPS = {
    "empresas": [f"Empresas{i}" for i in range(10)],
    "estabelecimentos": [f"Estabelecimentos{i}" for i in range(10)],
    "socios": [f"Socios{i}" for i in range(10)],
    "simples": ["Simples"],
    "lookups": ["Cnaes", "Municipios", "Naturezas", "Qualificacoes", "Motivos", "Paises"],
}

ALL_FILES = []
for group_files in FILE_GROUPS.values():
    ALL_FILES.extend(group_files)


def discover_files() -> list[dict]:
    """
    Discover available files from the Receita Federal portal.

    Returns list of {name, url, size_mb} dicts.
    """
    logger.info("Discovering files at %s ...", RF_BASE_URL)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(RF_BASE_URL)
        resp.raise_for_status()

    html = resp.text
    files = []

    for name in ALL_FILES:
        filename = f"{name}.zip"
        if filename in html:
            files.append({
                "name": name,
                "filename": filename,
                "url": f"{RF_BASE_URL}{filename}",
            })

    logger.info("Found %d files available for download.", len(files))
    return files


def download_file(url: str, dest: Path, resume: bool = True) -> Path:
    """
    Download a single file with progress and resume support.

    Args:
        url: URL to download
        dest: Destination file path
        resume: Whether to resume partial downloads

    Returns:
        Path to downloaded file
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {}
    mode = "wb"
    existing_size = 0

    if resume and dest.exists():
        existing_size = dest.stat().st_size
        headers["Range"] = f"bytes={existing_size}-"
        mode = "ab"

    with httpx.stream(
        "GET", url,
        headers=headers,
        timeout=httpx.Timeout(30.0, read=300.0),
        follow_redirects=True,
    ) as resp:
        if resp.status_code == 416:
            # Range not satisfiable = file already complete
            logger.info("  %s already complete (%d MB).", dest.name, existing_size // (1024 * 1024))
            return dest

        if resp.status_code not in (200, 206):
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code}", request=resp.request, response=resp
            )

        total = int(resp.headers.get("content-length", 0)) + existing_size
        total_mb = total / (1024 * 1024)

        with open(dest, mode) as f:
            downloaded = existing_size
            last_pct = -1

            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)

                if total > 0:
                    pct = int(downloaded * 100 / total)
                    if pct != last_pct and pct % 10 == 0:
                        logger.info(
                            "  %s: %d%% (%d/%d MB)",
                            dest.name, pct,
                            downloaded // (1024 * 1024),
                            int(total_mb),
                        )
                        last_pct = pct

    logger.info("  %s complete (%.1f MB).", dest.name, downloaded / (1024 * 1024))
    return dest


def download_all(groups: list[str] | None = None) -> list[Path]:
    """
    Download all (or selected) file groups from Receita Federal.

    Args:
        groups: Optional list of groups to download.
                Valid: "empresas", "estabelecimentos", "socios", "simples", "lookups"
                If None, downloads all.

    Returns:
        List of downloaded file paths.
    """
    if groups is None:
        groups = list(FILE_GROUPS.keys())

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    files_to_download = []
    for group in groups:
        if group not in FILE_GROUPS:
            logger.warning("Unknown group '%s', skipping.", group)
            continue
        for name in FILE_GROUPS[group]:
            files_to_download.append({
                "name": name,
                "filename": f"{name}.zip",
                "url": f"{RF_BASE_URL}{name}.zip",
            })

    logger.info(
        "Downloading %d files to %s ...",
        len(files_to_download), DOWNLOAD_DIR,
    )

    downloaded = []
    for i, f in enumerate(files_to_download, 1):
        dest = DOWNLOAD_DIR / f["filename"]
        logger.info("[%d/%d] Downloading %s ...", i, len(files_to_download), f["filename"])
        try:
            download_file(f["url"], dest)
            downloaded.append(dest)
        except Exception as e:
            logger.error("Failed to download %s: %s", f["filename"], e)

    logger.info("Download complete: %d/%d files.", len(downloaded), len(files_to_download))
    return downloaded
