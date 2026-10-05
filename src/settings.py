import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def bounded_int(name: str, default: int, maximum: int) -> int:
    value = int(os.getenv(name, str(default)))
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    backend: str
    sqlite_path: str
    supabase_url: str
    supabase_key: str
    gemini_key: str
    gemini_model: str
    max_articles: int
    max_feed_entries: int
    max_ai_calls: int
    feeds_path: Path
    output_dir: Path
    timezone: ZoneInfo

    @classmethod
    def from_env(cls):
        backend = os.getenv("STORAGE_BACKEND", "sqlite")
        if backend not in {"sqlite", "supabase"}:
            raise ValueError("STORAGE_BACKEND must be sqlite or supabase")
        url = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if backend == "supabase" and (not url.startswith("https://") or not key):
            raise ValueError("Supabase requires an HTTPS URL and service-role key")
        return cls(
            backend, os.getenv("SQLITE_PATH", str(ROOT / "digest_engine.db")),
            url, key, os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", ""),
            bounded_int("MAX_ARTICLES_PER_RUN", 20, 100),
            bounded_int("MAX_ENTRIES_PER_FEED", 5, 25),
            bounded_int("MAX_AI_CALLS_PER_RUN", 20, 100),
            Path(os.getenv("FEEDS_PATH", str(ROOT / "config/feeds.json"))),
            Path(os.getenv("OUTPUT_DIR", str(ROOT / "digests"))),
            ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata")),
        )
