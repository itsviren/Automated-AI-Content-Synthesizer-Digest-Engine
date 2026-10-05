import hashlib
import ipaddress
import json
import logging
import socket
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser
import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
MAX_BODY = 2_000_000


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Only ordinary HTTP(S) source URLs are supported")
    if parts.port not in {None, 80, 443}:
        raise ValueError("Unsupported source port")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(sorted(query)), ""))


def validate_public_url(url: str) -> str:
    url = normalize_url(url)
    host = urlsplit(url).hostname
    addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Source must resolve to public IP addresses")
    return url


def fetch(client: httpx.Client, url: str) -> bytes:
    # Validate redirects explicitly instead of letting the HTTP client follow them.
    for _ in range(6):
        url = validate_public_url(url)
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    raise ValueError("Source body exceeds 2 MB limit")
            return bytes(body)
    raise ValueError("Too many source redirects")


def clean_text(html: str | bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        node.decompose()
    # News pages often put related-story cards in separate <article> blocks.
    # Prefer a dedicated body container, then the longest article over the first.
    content = soup.select_one("[itemprop='articleBody'], .entry-content, .post-content, .article-body")
    if content is None:
        articles = soup.find_all("article")
        content = max(articles, key=lambda node: len(node.get_text(" ", strip=True))) if articles else soup.find("main")
    content = content if content is not None else soup
    for node in content.select("button, video, audio, .share-buttons, .related-posts, .related-articles"):
        node.decompose()
    return " ".join(content.get_text(" ", strip=True).split())


@dataclass
class Article:
    title: str
    url: str
    category: str
    text: str
    published: str

    @property
    def content_hash(self):
        return hashlib.sha256(self.text.casefold().encode()).hexdigest()


def load_sources(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    sources = [(category["name"], normalize_url(url))
               for category in config["categories"] for url in category["sources"]]
    if not sources:
        raise ValueError("Configure at least one feed")
    return sources


def collect(settings, store, client: httpx.Client):
    articles, errors = [], []
    urls, hashes = set(), set()
    successful_feeds = 0
    for category, source in load_sources(settings.feeds_path):
        if len(articles) >= settings.max_articles:
            break
        try:
            parsed = feedparser.parse(fetch(client, source))
            if not parsed.entries and parsed.bozo:
                raise ValueError("Invalid or unreadable feed")
            successful_feeds += 1
        except (httpx.HTTPError, ValueError, OSError, KeyError):
            log.warning("Feed fetch failed for configured category %s", category)
            errors.append(f"Feed unavailable: {category}")
            continue
        for entry in parsed.entries[:settings.max_feed_entries]:
            if len(articles) >= settings.max_articles:
                break
            try:
                url = normalize_url(entry.get("link", ""))
                if url in urls or store.seen_url(url):
                    continue
                text = clean_text(entry.get("summary", ""))
                try:
                    extracted = clean_text(fetch(client, url))
                    if len(extracted) >= 100:
                        text = extracted
                except (httpx.HTTPError, ValueError, OSError, KeyError):
                    log.info("Using feed excerpt for an unavailable article")
                text = text[:16000]
                if len(text) < 40:
                    continue
                article = Article(clean_text(entry.get("title", "Untitled"))[:300], url,
                                  category, text, entry.get("published", "")[:100])
                if article.content_hash in hashes or store.seen_hash(article.content_hash):
                    continue
                articles.append(article)
                urls.add(url)
                hashes.add(article.content_hash)
            except (ValueError, OSError):
                log.warning("Skipping invalid article metadata")
    if successful_feeds == 0:
        raise RuntimeError("All configured feeds failed; no digest was generated")
    return articles, errors
