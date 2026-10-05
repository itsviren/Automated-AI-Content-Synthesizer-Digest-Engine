import argparse
import logging
from pathlib import Path
from dataclasses import replace

from src.pipeline import run
from src.settings import Settings
from src.storage import make_store


def main():
    parser = argparse.ArgumentParser(description="Generate a source-linked daily digest")
    parser.add_argument("--profile", choices=["executive", "technical"], default="executive")
    parser.add_argument("--date", help="Digest date, YYYY-MM-DD (defaults to local app timezone)")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # HTTP client loggers can include URLs; keep these quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings.from_env()
    if args.output_dir:
        settings = replace(settings, output_dir=args.output_dir)
    store = make_store(settings, args.profile)
    try:
        digest, status = run(settings, store, args.profile, args.date)
        print(f"Digest {status}: {digest['id']} ({len(digest['items'])} articles)")
    finally:
        store.close()


if __name__ == "__main__":
    main()
