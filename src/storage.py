import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import httpx


def now():
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, path, profile="executive"):
        self.profile = profile
        self.db = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                profile TEXT NOT NULL, url TEXT NOT NULL, content_hash TEXT NOT NULL,
                title TEXT NOT NULL, category TEXT NOT NULL, excerpt TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY (profile, url));
            CREATE INDEX IF NOT EXISTS articles_hash ON articles(profile, content_hash);
            CREATE TABLE IF NOT EXISTS digests (
                id TEXT PRIMARY KEY, day TEXT NOT NULL, profile TEXT NOT NULL,
                created_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, token TEXT NOT NULL, status TEXT NOT NULL,
                updated_at TEXT NOT NULL, lease_until TEXT NOT NULL, error TEXT);
        """)

    def close(self):
        self.db.close()

    def seen_url(self, url):
        return self.db.execute("SELECT 1 FROM articles WHERE profile=? AND url=?", (self.profile, url)).fetchone() is not None

    def seen_hash(self, content_hash):
        return self.db.execute("SELECT 1 FROM articles WHERE profile=? AND content_hash=?", (self.profile, content_hash)).fetchone() is not None

    def claim(self, digest_id):
        token = str(uuid.uuid4())
        try:
            self.db.execute("BEGIN IMMEDIATE")
            if self.db.execute("SELECT 1 FROM digests WHERE id=?", (digest_id,)).fetchone():
                self.db.commit()
                return "completed", None
            row = self.db.execute("SELECT * FROM runs WHERE id=?", (digest_id,)).fetchone()
            timestamp = now()
            if row and row["status"] == "running" and row["lease_until"] > timestamp:
                self.db.commit()
                return "busy", None
            lease = (datetime.now(timezone.utc) + timedelta(minutes=35)).isoformat()
            self.db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, 'running', ?, ?, NULL)",
                            (digest_id, token, timestamp, lease))
            self.db.commit()
            return "claimed", token
        except Exception:
            self.db.rollback()
            raise

    def complete(self, digest, articles, token):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT token,status,lease_until FROM runs WHERE id=?", (digest["id"],)).fetchone()
            if not row or row["token"] != token or row["status"] != "running" or row["lease_until"] <= now():
                raise RuntimeError("Run lease lost")
            for article in articles:
                self.db.execute("INSERT OR IGNORE INTO articles VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (digest["profile"], article.url, article.content_hash, article.title,
                                 article.category, article.text[:1000], digest["created_at"]))
            self.db.execute("INSERT INTO digests VALUES (?, ?, ?, ?, ?)",
                            (digest["id"], digest["day"], digest["profile"], digest["created_at"], json.dumps(digest)))
            self.db.execute("UPDATE runs SET status='completed', updated_at=? WHERE id=? AND token=?",
                            (now(), digest["id"], token))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def fail(self, digest_id, token, error):
        with self.db:
            self.db.execute("UPDATE runs SET status='failed',error=?,updated_at=? WHERE id=? AND token=? AND status='running'",
                            (error[:500], now(), digest_id, token))

    def get(self, digest_id):
        row = self.db.execute("SELECT payload FROM digests WHERE id=?", (digest_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, limit=30):
        return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM digests ORDER BY day DESC, profile LIMIT ?", (limit,))]


class SupabaseStore:
    def __init__(self, url, key, profile="executive"):
        self.profile = profile
        self.client = httpx.Client(base_url=url + "/rest/v1/", timeout=30,
                                   headers={"apikey": key, "Authorization": f"Bearer {key}"})

    def close(self):
        self.client.close()

    def request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            # Keep database URLs, credentials, and returned data out of errors.
            raise RuntimeError(f"Supabase request failed (HTTP {response.status_code}); check schema and server configuration")
        return response.json() if response.content else None

    def seen_url(self, url):
        return bool(self.request("GET", "articles", params={"profile": "eq." + self.profile, "url": "eq." + url, "select": "url", "limit": 1}))

    def seen_hash(self, content_hash):
        return bool(self.request("GET", "articles", params={"profile": "eq." + self.profile, "content_hash": "eq." + content_hash, "select": "url", "limit": 1}))

    def claim(self, digest_id):
        token = str(uuid.uuid4())
        result = self.request("POST", "rpc/claim_digest", json={"p_id": digest_id, "p_token": token})
        return result, token if result == "claimed" else None

    def complete(self, digest, articles, token):
        rows = [{"profile": digest["profile"], "url": a.url, "content_hash": a.content_hash,
                 "title": a.title, "category": a.category, "excerpt": a.text[:1000],
                 "created_at": digest["created_at"]} for a in articles]
        self.request("POST", "rpc/complete_digest", json={"p_digest": digest, "p_articles": rows, "p_token": token})

    def fail(self, digest_id, token, error):
        self.request("PATCH", "runs", params={"id": "eq." + digest_id, "token": "eq." + token, "status": "eq.running"},
                     json={"status": "failed", "error": error[:500], "updated_at": now()})

    def get(self, digest_id):
        rows = self.request("GET", "digests", params={"id": "eq." + digest_id, "select": "payload", "limit": 1})
        return rows[0]["payload"] if rows else None

    def list(self, limit=30):
        rows = self.request("GET", "digests", params={"select": "payload", "order": "day.desc,profile.asc", "limit": limit})
        return [r["payload"] for r in rows]


def make_store(settings, profile="executive"):
    if settings.backend == "supabase":
        return SupabaseStore(settings.supabase_url, settings.supabase_key, profile)
    return SQLiteStore(settings.sqlite_path, profile)
