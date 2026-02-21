"""
Download all Receita Federal CNPJ data files.

Run: python cnpj/run_download.py

Downloads ~6.8 GB of data to cnpj/data/ directory.
Supports resume - can be interrupted and restarted.
"""

import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cnpj.config import DOWNLOAD_DIR, RF_BASE_URL

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Download order: small files first, then by priority
FILES = [
    # Lookups (tiny, needed first for loading)
    "Cnaes.zip", "Municipios.zip", "Naturezas.zip",
    "Qualificacoes.zip", "Motivos.zip", "Paises.zip",
    # Simples (needed for MEI filter)
    "Simples.zip",
    # Empresas (needed for razao_social, capital, etc.)
    *[f"Empresas{i}.zip" for i in range(10)],
    # Estabelecimentos (main data - largest files)
    *[f"Estabelecimentos{i}.zip" for i in range(10)],
    # Socios (QSA data)
    *[f"Socios{i}.zip" for i in range(10)],
]


def download_file(url: str, dest: Path) -> bool:
    """Download a single file with resume support."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {}
    mode = "wb"
    existing_size = 0

    if dest.exists():
        existing_size = dest.stat().st_size
        headers["Range"] = f"bytes={existing_size}-"
        mode = "ab"

    try:
        with httpx.stream(
            "GET", url,
            headers=headers,
            timeout=httpx.Timeout(30.0, read=600.0),
            follow_redirects=True,
        ) as resp:
            if resp.status_code == 416:
                logger.info("  Already complete (%d MB)", existing_size // (1024 * 1024))
                return True

            if resp.status_code not in (200, 206):
                logger.error("  HTTP %d", resp.status_code)
                return False

            total = int(resp.headers.get("content-length", 0)) + existing_size
            total_mb = total / (1024 * 1024)

            with open(dest, mode) as f:
                downloaded = existing_size
                start = time.time()
                last_log = start

                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_log >= 5:  # Log every 5 seconds
                        elapsed = now - start
                        speed = (downloaded - existing_size) / elapsed / (1024 * 1024) if elapsed > 0 else 0
                        pct = downloaded * 100 / total if total > 0 else 0
                        eta = (total - downloaded) / (speed * 1024 * 1024) if speed > 0 else 0
                        logger.info(
                            "  %s: %.0f%% (%d/%d MB) %.1f MB/s ETA %.0fs",
                            dest.name, pct,
                            downloaded // (1024 * 1024), int(total_mb),
                            speed, eta,
                        )
                        last_log = now

        logger.info("  %s complete (%.1f MB)", dest.name, downloaded / (1024 * 1024))
        return True

    except Exception as e:
        logger.error("  Error: %s", e)
        return False


def main():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("CNPJ Data Download - Receita Federal (Jan 2026)")
    logger.info("Source: %s", RF_BASE_URL)
    logger.info("Destination: %s", DOWNLOAD_DIR)
    logger.info("Files: %d total (~6.8 GB)", len(FILES))
    logger.info("=" * 60)

    success = 0
    failed = 0
    start = time.time()

    for i, filename in enumerate(FILES, 1):
        url = f"{RF_BASE_URL}{filename}"
        dest = DOWNLOAD_DIR / filename
        logger.info("[%d/%d] %s", i, len(FILES), filename)
        if download_file(url, dest):
            success += 1
        else:
            failed += 1

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info("Download complete in %.0f minutes", elapsed / 60)
    logger.info("  Success: %d", success)
    logger.info("  Failed: %d", failed)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
