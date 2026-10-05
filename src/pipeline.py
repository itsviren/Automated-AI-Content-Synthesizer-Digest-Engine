import logging
from datetime import datetime

import httpx

from src.ingestion import collect
from src.output import export
from src.storage import now
from src.synthesis import PROFILES, Synthesizer

log = logging.getLogger(__name__)


def run(settings, store, profile="executive", day=None):
    if profile not in PROFILES:
        raise ValueError("Unknown profile")
    day = day or datetime.now(settings.timezone).date().isoformat()
    # Validated dates also keep export filenames safe.
    day = datetime.strptime(day, "%Y-%m-%d").date().isoformat()
    digest_id = f"{day}-{profile}"
    store.profile = profile
    status, token = store.claim(digest_id)
    if status == "completed":
        digest = store.get(digest_id)
        export(digest, settings.output_dir)
        return digest, "existing"
    if status == "busy":
        raise RuntimeError("A digest run for this date/profile is already active")
    try:
        with httpx.Client(timeout=httpx.Timeout(25, connect=10),
                          headers={"User-Agent": "ContentDigestEngine/0.1 (RSS digest reader)"},
                          trust_env=False) as client:
            articles, warnings = collect(settings, store, client)
            synth = Synthesizer(settings, client)
            items = []
            for article in articles:
                summary = synth.summarize(article, profile)
                items.append({"title": article.title, "url": article.url,
                              "category": article.category, "published": article.published, **summary})
        digest = {"id": digest_id, "day": day, "profile": profile, "created_at": now(),
                  "items": items, "warnings": warnings}
        store.complete(digest, articles, token)
    except Exception as exc:
        try:
            # Persist a safe error category rather than credentials or arbitrary response text.
            store.fail(digest_id, token, f"Pipeline failed: {type(exc).__name__}")
        except Exception:
            log.error("Unable to persist failure status")
        raise
    export(digest, settings.output_dir)
    return digest, "created"
