"""Merge data/url_alive.txt into data/url.txt — the ONLY sanctioned way to
refill the traffic pool.

Replaces the old manual copy step: url_alive.txt entries produced by
run_url_check.py already passed BLOCKED_KEYWORDS at ingestion, but this tool
re-filters anyway (defense in depth — the manual copy that existed before had
no filter at all, which is how 30 crypto-mining sites entered url.txt,
security-team finding 2026-10-27). Also: dedupes against url.txt, keeps a
timestamped backup, and refuses to run when nothing would change.

Usage:
    python tool/merge_url_alive.py            # merge + report
    python tool/merge_url_alive.py --dry-run  # show what would change
"""
import argparse
import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util_traffic import read_urls_from_file  # noqa: E402
from util_log import LogSetup  # noqa: E402
from tool.run_url_check import is_safe_keyword  # noqa: E402

logger = LogSetup().setup_logging()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL_FILE = os.path.join(BASE_DIR, "data", "url.txt")
ALIVE_FILE = os.path.join(BASE_DIR, "data", "url_alive.txt")


def domain(url: str) -> str:
    d = url.lower().strip()
    for pre in ("http://", "https://"):
        if d.startswith(pre):
            d = d[len(pre):]
    return d.split("/")[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge url_alive.txt into url.txt (filtered).")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing.")
    args = parser.parse_args()

    if not os.path.exists(ALIVE_FILE):
        logger.error(f"{ALIVE_FILE} not found.")
        sys.exit(1)
    if not os.path.exists(URL_FILE):
        logger.error(f"{URL_FILE} not found.")
        sys.exit(1)

    with open(URL_FILE, encoding="utf-8") as f:
        existing = {line.strip() for line in f if line.strip()}
    with open(ALIVE_FILE, encoding="utf-8") as f:
        candidates = [line.strip() for line in f if line.strip()]

    added: list[str] = []
    dropped: list[str] = []
    for url in candidates:
        if url in existing:
            logger.info(f"Duplicate in DB, skipping: {url}")
            continue
        if not is_safe_keyword(domain(url)):
            dropped.append(url)
            logger.warning(f"BLOCKED by keyword filter (mining/safety): {url}")
            continue
        added.append(url)

    logger.info(f"candidates={len(candidates)} added={len(added)} blocked={len(dropped)} "
                f"dupes={len(candidates) - len(added) - len(dropped)}")
    if dropped:
        logger.warning("Blocked lines (investigate where they came from):")
        for u in dropped:
            logger.warning(f"  {u}")

    if args.dry_run:
        logger.info("dry-run: nothing written.")
        sys.exit(0)
    if not added:
        logger.info("Nothing to merge.")
        sys.exit(0)

    backup = f"{URL_FILE}.bak-{datetime.date.today():%Y%m%d}"
    with open(backup, "w", encoding="utf-8") as f_in, open(URL_FILE, encoding="utf-8") as f_out:
        f_out.write(f_in.read())
    logger.info(f"backup written: {backup}")

    with open(URL_FILE, "a", encoding="utf-8") as f:
        for u in added:
            f.write(u + "\n")
    logger.info(f"Merged {len(added)} URLs into {URL_FILE} (new total {len(existing) + len(added)}).")

    # consumed source: empty it so the same lines are not merged twice
    with open(ALIVE_FILE, "w", encoding="utf-8"):
        pass
    logger.info(f"{ALIVE_FILE} cleared.")


if __name__ == "__main__":
    main()
