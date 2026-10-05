from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.output import markdown
from src.settings import Settings
from src.storage import make_store

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Signal / Content Digest", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def get_store():
    store = make_store(Settings.from_env())
    try:
        yield store
    finally:
        store.close()


@app.exception_handler(RuntimeError)
@app.exception_handler(httpx.HTTPError)
def storage_error(request, exc):
    return PlainTextResponse("Storage is temporarily unavailable. Please try again later.", status_code=503)


@app.get("/health")
def health():
    # Liveness only: deliberately no database or external API calls.
    return {"status": "ok", "service": "digest-engine"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, q: str = Query("", max_length=100),
              profile: str = Query("all", pattern="^(all|executive|technical)$"), store=Depends(get_store)):
    digests = store.list(30)
    filtered = [d for d in digests if profile == "all" or d["profile"] == profile]
    if q:
        filtered = [dict(d, items=[i for i in d["items"] if q.casefold() in
                    (i["title"] + " " + i["category"] + " " + i["summary"]).casefold()]) for d in filtered]
        filtered = [d for d in filtered if d["items"]]
    latest = filtered[0] if filtered else None
    return templates.TemplateResponse(request=request, name="index.html", context={
        "digests": filtered, "latest": latest, "q": q, "profile": profile,
        "total": sum(len(d["items"]) for d in digests), "archive_count": len(digests),
        "categories": sorted({i["category"] for d in digests for i in d["items"]}),
    })


@app.get("/api/digests")
def list_digests(limit: int = Query(30, ge=1, le=100), store=Depends(get_store)):
    return {"digests": store.list(limit)}


@app.get("/api/digests/{digest_id}")
def get_digest(digest_id: str, store=Depends(get_store)):
    digest = store.get(digest_id)
    if digest is None:
        raise HTTPException(404, "Digest not found")
    return digest


@app.get("/digests/{digest_id}.md", response_class=PlainTextResponse)
def download(digest_id: str, store=Depends(get_store)):
    digest = store.get(digest_id)
    if digest is None:
        raise HTTPException(404, "Digest not found")
    # Do not interpolate a user-controlled identifier into response headers.
    return PlainTextResponse(markdown(digest), headers={"Content-Disposition": 'attachment; filename="digest.md"'})


@app.get("/rss.xml")
def rss(request: Request, store=Depends(get_store)):
    root = Element("rss", version="2.0")
    channel = SubElement(root, "channel")
    SubElement(channel, "title").text = "Signal — Daily Content Digest"
    SubElement(channel, "link").text = str(request.base_url)
    SubElement(channel, "description").text = "Source-linked daily briefings"
    for digest in store.list(30):
        item = SubElement(channel, "item")
        SubElement(item, "title").text = f"{digest['day']} / {digest['profile']}"
        SubElement(item, "guid", isPermaLink="false").text = digest["id"]
        SubElement(item, "link").text = str(request.base_url) + "digests/" + digest["id"] + ".md"
        SubElement(item, "description").text = "\n".join(i["title"] + ": " + i["summary"] for i in digest["items"])
    return Response(tostring(root, encoding="utf-8", xml_declaration=True), media_type="application/rss+xml")
