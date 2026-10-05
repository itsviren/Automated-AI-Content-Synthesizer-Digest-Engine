import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from src.app import app, get_store
from src.ingestion import Article, clean_text, collect, normalize_url, validate_public_url
from src.output import export
from src.pipeline import run
from src.settings import Settings
from src.storage import SQLiteStore, SupabaseStore
from src.synthesis import Synthesizer


@pytest.fixture
def settings(tmp_path, monkeypatch):
    for name in ["GEMINI_API_KEY", "GEMINI_MODEL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    base = Settings.from_env()
    path = tmp_path / "feeds.json"
    path.write_text(json.dumps({"categories": [{"name": "AI", "sources": ["https://example.com/feed"]}]}))
    return replace(base, sqlite_path=str(tmp_path / "test.db"), feeds_path=path, output_dir=tmp_path / "exports")


@pytest.fixture
def store(settings):
    instance = SQLiteStore(settings.sqlite_path)
    yield instance
    instance.close()


def article(text=None):
    return Article("A new research method", "https://example.com/article", "AI",
                   text or "Researchers introduced a new method for comparing models. The evaluation covers three public datasets. Further work is needed to assess reliability.", "")


def digest(day="2026-10-05", items=None):
    return {"id": day + "-executive", "day": day, "profile": "executive",
            "created_at": "2026-10-05T02:47:00+00:00", "warnings": [], "items": items or []}


def persist(store, value, articles=None):
    status, token = store.claim(value["id"])
    assert status == "claimed"
    store.complete(value, articles or [], token)


def test_normalize_tracking_without_destroying_semantic_query():
    assert normalize_url("https://EXAMPLE.com/post?utm_source=rss&id=2#section") == "https://example.com/post?id=2"
    with pytest.raises(ValueError):
        normalize_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        normalize_url("https://user:secret@example.com/")


def test_private_sources_rejected(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 0))])
    with pytest.raises(ValueError, match="public"):
        validate_public_url("http://localhost/")


def test_clean_removes_active_content_and_boilerplate():
    result = clean_text("<nav>Ignore me</nav><article><h1>Title</h1><p>Real text.</p><script>evil()</script></article>")
    assert result == "Title Real text."


def test_extraction_ignores_related_story_cards():
    page = '<article>Related story.</article><article><h1>Main story</h1><p>The full primary article has substantially more text.</p><button>Share</button></article>'
    result = clean_text(page)
    assert "Main story" in result
    assert "Related story" not in result and "Share" not in result


def test_redirects_to_private_network_are_rejected(monkeypatch):
    from src.ingestion import fetch
    def resolver(host, *args, **kwargs):
        ip = "127.0.0.1" if host == "localhost" else "93.184.216.34"
        return [(2, 1, 6, "", (ip, 0))]
    monkeypatch.setattr("socket.getaddrinfo", resolver)
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://localhost/internal"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="public"):
            fetch(client, "https://example.com/")
    assert len(requests) == 1


def test_expired_lease_can_be_reclaimed(store):
    _, old_token = store.claim("2026-10-05-executive")
    with store.db:
        store.db.execute("UPDATE runs SET lease_until='2000-01-01T00:00:00+00:00'")
    status, token = store.claim("2026-10-05-executive")
    assert status == "claimed" and token != old_token
    with pytest.raises(RuntimeError, match="lease"):
        store.complete(digest(), [], old_token)


def test_no_key_uses_labelled_extractive_summary(settings):
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("Unexpected network"))) as client:
        result = Synthesizer(settings, client).summarize(article(), "executive")
    assert result["method"] == "extractive"
    assert "Researchers" in result["summary"]


def test_ai_quota_exhaustion_stops_further_calls(settings):
    settings = replace(settings, gemini_key="test-secret", gemini_model="test-model")
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(429)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        synth = Synthesizer(settings, client)
        assert synth.summarize(article(), "executive")["method"] == "extractive"
        assert synth.summarize(article(), "executive")["method"] == "extractive"
    assert len(requests) == 1
    assert "test-secret" not in str(requests[0].url)


@pytest.mark.parametrize("data", [{"summary": "invented", "takeaways": "wrong"}, {"summary": "", "takeaways": ["text"]}])
def test_malformed_ai_output_falls_back(settings, data):
    settings = replace(settings, gemini_key="test", gemini_model="test")
    response = {"candidates": [{"content": {"parts": [{"text": json.dumps(data)}]}}]}
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))) as client:
        assert Synthesizer(settings, client).summarize(article(), "technical")["method"] == "extractive"


def test_valid_ai_output(settings):
    settings = replace(settings, gemini_key="test", gemini_model="test")
    response = {"candidates": [{"content": {"parts": [{"text": json.dumps({"summary": "A supported summary.", "takeaways": ["A supported point."]})}]}}]}
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))) as client:
        assert Synthesizer(settings, client).summarize(article(), "executive")["method"] == "gemini"


def test_lease_duplicate_and_failed_retry(store):
    status, token = store.claim("2026-10-05-executive")
    assert status == "claimed"
    assert store.claim("2026-10-05-executive")[0] == "busy"
    store.fail("2026-10-05-executive", token, "offline")
    status, token2 = store.claim("2026-10-05-executive")
    assert status == "claimed" and token2 != token
    with pytest.raises(RuntimeError, match="lease"):
        store.complete(digest(), [], token)
    store.complete(digest(), [article()], token2)
    assert store.claim("2026-10-05-executive")[0] == "completed"
    assert store.seen_url(article().url)
    assert store.seen_hash(article().content_hash)


def test_storage_completion_is_atomic(store):
    _, token = store.claim("2026-10-05-executive")
    invalid = digest()
    del invalid["day"]
    with pytest.raises(KeyError):
        store.complete(invalid, [article()], token)
    assert not store.seen_url(article().url)
    assert store.get("2026-10-05-executive") is None


def test_dedup_is_per_profile(store):
    persist(store, digest(), [article()])
    store.profile = "technical"
    assert not store.seen_url(article().url)


def test_ingestion_skips_duplicate_content(settings, store, monkeypatch):
    monkeypatch.setattr("src.ingestion.validate_public_url", lambda u: normalize_url(u))
    feed = '''<rss version="2.0"><channel><title>Test</title>
    <item><title>One</title><link>https://example.com/one</link></item>
    <item><title>Two</title><link>https://example.com/two</link></item>
    </channel></rss>'''
    def handler(request):
        return httpx.Response(200, text=feed if request.url.path == "/feed" else "<article>" + article().text + "</article>")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        articles, warnings = collect(settings, store, client)
    assert len(articles) == 1 and not warnings


def test_total_source_failure_is_not_empty_success(settings, store, monkeypatch):
    monkeypatch.setattr("src.ingestion.validate_public_url", lambda u: u)
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        with pytest.raises(RuntimeError, match="All configured feeds"):
            collect(settings, store, client)


def test_pipeline_rerun_reexports_without_fetching(settings, store, monkeypatch):
    monkeypatch.setattr("src.pipeline.collect", lambda *args: ([article()], []))
    result, status = run(settings, store, day="2026-10-05")
    assert status == "created" and len(result["items"]) == 1
    monkeypatch.setattr("src.pipeline.collect", lambda *args: pytest.fail("Duplicate execution"))
    result2, status2 = run(settings, store, day="2026-10-05")
    assert status2 == "existing" and result == result2
    assert (settings.output_dir / "2026-10-05-executive.md").exists()


def test_pipeline_failure_releases_lease(settings, store, monkeypatch):
    def fail(*args):
        raise RuntimeError("offline")
    monkeypatch.setattr("src.pipeline.collect", fail)
    with pytest.raises(RuntimeError):
        run(settings, store, day="2026-10-05")
    assert store.claim("2026-10-05-executive")[0] == "claimed"


def test_html_export_escapes_source(settings):
    value = digest(items=[{"title": "<script>alert(1)</script>", "category": "AI", "url": "https://example.com/",
                           "method": "extractive", "summary": "<img src=x onerror=evil()>", "takeaways": ["point"]}])
    export(value, settings.output_dir)
    page = (settings.output_dir / (value["id"] + ".html")).read_text()
    assert "<script>" not in page and "<img src=" not in page


def test_dashboard_api_rss_and_search(store):
    value = digest(items=[{"title": "<script>Unsafe</script>", "url": "https://example.com/",
                           "category": "AI", "method": "extractive", "summary": "Searchable research", "takeaways": ["Point"], "note": ""}])
    persist(store, value)
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            assert client.get("/health").json()["status"] == "ok"
            page = client.get("/")
            assert page.status_code == 200
            assert "&lt;script&gt;Unsafe&lt;/script&gt;" in page.text
            assert "<script>Unsafe" not in page.text
            assert "No matching briefings" in client.get("/?q=unmatched").text
            assert "Searchable research" in client.get("/?q=research").text
            assert client.get("/api/digests").json()["digests"][0]["id"] == value["id"]
            assert client.get("/api/digests/missing").status_code == 404
            assert client.get("/digests/2026-10-05-executive.md").status_code == 200
            assert "&lt;script&gt;" in client.get("/rss.xml").text
            assert client.get("/api/digests?limit=10000").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_supabase_requests_keep_credentials_out_of_url():
    store = SupabaseStore("https://test.supabase.co", "secret-key")
    store.client.close()
    requests = []
    def handler(request):
        requests.append(request)
        if "claim_digest" in str(request.url):
            return httpx.Response(200, json="claimed")
        return httpx.Response(200, json=[])
    store.client = httpx.Client(base_url="https://test.supabase.co/rest/v1/",
                               transport=httpx.MockTransport(handler), headers={"apikey": "secret-key"})
    try:
        assert store.claim("2026-10-05-executive")[0] == "claimed"
        assert not store.seen_url("https://example.com/")
        assert all("secret-key" not in str(r.url) for r in requests)
    finally:
        store.close()
