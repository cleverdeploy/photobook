"""Photobook — a self-hosted, AI-themed shared photo album app.

Owner logs in to create albums (titled, AI-themed) and gets a share link to
paste into WhatsApp. Anyone with the link can view the album and drop in their
own photos — no account needed.
"""
from __future__ import annotations

import re
import secrets
import uuid
from typing import Optional

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import config, db, images, theme

app = FastAPI(title="Photobook")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=60 * 60 * 24 * 30)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def revalidate_cache(request: Request, call_next):
    """Force browsers to revalidate before reusing a cached copy.

    The app ships no other cache headers, so mobile browsers were heuristically
    caching pages *and* /static assets (e.g. album.js) and serving them stale
    after a deploy. `no-cache` means "store, but check with the server first":
    StaticFiles already sends an ETag, so revalidation is a cheap 304.
    """
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.on_event("startup")
def _startup() -> None:
    config.ensure_dirs()
    db.init_db()


# --- helpers ---------------------------------------------------------------

def is_owner(request: Request) -> bool:
    return bool(request.session.get("owner"))


def abs_base(request: Request) -> str:
    return config.BASE_URL or str(request.base_url).rstrip("/")


def album_payload(request: Request, album) -> dict:
    """Common view data for an album."""
    photos = db.list_photos(album["id"])
    return {
        "album": album,
        "theme": db.album_theme(album),
        "photos": photos,
        "share_url": f"{abs_base(request)}/a/{album['share_token']}",
    }


def _photo_belongs(photo, album_id: str) -> bool:
    return photo is not None and photo["album_id"] == album_id


# --- auth ------------------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if is_owner(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, password: str = Form(...)):
    if secrets.compare_digest(password, config.OWNER_PASSWORD):
        request.session["owner"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"error": "Wrong password."}, status_code=401
    )


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# --- owner dashboard -------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # Non-owners never see albums — they get the public waitlist landing page.
    if not is_owner(request):
        return templates.TemplateResponse(
            request,
            "landing.html",
            {
                "joined": request.query_params.get("joined") == "1",
                "error": request.query_params.get("error") == "1",
            },
        )
    albums = db.list_albums()
    rows = []
    for a in albums:
        rows.append(
            {
                "album": a,
                "theme": db.album_theme(a),
                "count": db.count_photos(a["id"]),
                "share_url": f"{abs_base(request)}/a/{a['share_token']}",
            }
        )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "albums": rows,
            "waitlist": db.list_waitlist(),
            "waitlist_count": db.count_waitlist(),
        },
    )


@app.post("/waitlist")
def join_waitlist(request: Request, email: str = Form(default="")):
    email = email.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        return RedirectResponse("/?error=1#waitlist", status_code=303)
    db.add_waitlist(email)
    return RedirectResponse("/?joined=1#waitlist", status_code=303)


@app.post("/albums")
def create_album(request: Request, title: str = Form(...)):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    title = title.strip() or "Untitled Album"
    album_id = uuid.uuid4().hex
    token = secrets.token_urlsafe(16)
    generated = theme.generate_theme(title)  # blocking; runs in threadpool (sync route)
    db.create_album(album_id, title, token, generated)
    return RedirectResponse(f"/album/{album_id}", status_code=303)


@app.get("/album/{album_id}", response_class=HTMLResponse)
def manage_album(request: Request, album_id: str):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    album = db.get_album(album_id)
    if album is None:
        return RedirectResponse("/", status_code=303)
    ctx = album_payload(request, album)
    return templates.TemplateResponse(request, "manage.html", ctx)


@app.post("/album/{album_id}/upload")
def owner_upload(
    request: Request,
    album_id: str,
    files: list[UploadFile] = File(default=[]),
):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    album = db.get_album(album_id)
    if album is None:
        return RedirectResponse("/", status_code=303)
    _ingest(album_id, files, contributor=None)
    return RedirectResponse(f"/album/{album_id}", status_code=303)


@app.post("/album/{album_id}/title")
def rename_album(request: Request, album_id: str, title: str = Form(...)):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    db.update_album_title(album_id, title.strip() or "Untitled Album")
    return RedirectResponse(f"/album/{album_id}", status_code=303)


@app.post("/album/{album_id}/description")
def update_album_description(
    request: Request, album_id: str, description: str = Form(default="")
):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    album = db.get_album(album_id)
    if album is not None:
        th = db.album_theme(album)
        th["description"] = description.strip()[:120]  # match theme._sanitise cap
        db.update_album_theme(album_id, th)
    return RedirectResponse(f"/album/{album_id}", status_code=303)


@app.post("/album/{album_id}/retheme")
def retheme_album(request: Request, album_id: str):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    album = db.get_album(album_id)
    if album is not None:
        db.update_album_theme(album_id, theme.generate_theme(album["title"]))
    return RedirectResponse(f"/album/{album_id}", status_code=303)


@app.post("/album/{album_id}/cover")
def set_cover(request: Request, album_id: str, photo_id: str = Form(...)):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    photo = db.get_photo(photo_id)
    if _photo_belongs(photo, album_id):
        db.set_cover(album_id, photo_id)
    return RedirectResponse(f"/album/{album_id}", status_code=303)


@app.post("/album/{album_id}/delete")
def delete_album(request: Request, album_id: str):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    db.delete_album(album_id)
    images.delete_album_files(album_id)
    return RedirectResponse("/", status_code=303)


@app.post("/photo/{photo_id}/delete")
def delete_photo(request: Request, photo_id: str, album_id: str = Form(...)):
    if not is_owner(request):
        return RedirectResponse("/login", status_code=303)
    photo = db.get_photo(photo_id)
    if _photo_belongs(photo, album_id):
        images.delete_photo_files(album_id, photo_id, photo["ext"])
        db.delete_photo(photo_id)
        album = db.get_album(album_id)
        if album is not None and album["cover_id"] == photo_id:
            remaining = db.list_photos(album_id)
            db.set_cover(album_id, remaining[0]["id"] if remaining else None)
    return RedirectResponse(f"/album/{album_id}", status_code=303)


# --- public album ----------------------------------------------------------

@app.get("/a/{token}", response_class=HTMLResponse)
def public_album(request: Request, token: str):
    album = db.get_album_by_token(token)
    if album is None:
        return templates.TemplateResponse(
            request, "notfound.html", {}, status_code=404
        )
    th = db.album_theme(album)
    photos = db.list_photos(album["id"])
    base = abs_base(request)
    og_image = (
        f"{base}/media/{album['id']}/disp/{album['cover_id']}.jpg"
        if album["cover_id"]
        else None
    )
    return templates.TemplateResponse(
        request,
        "album.html",
        {
            "album": album,
            "theme": th,
            "photos": photos,
            "token": token,
            "og_image": og_image,
            "page_url": f"{base}/a/{token}",
            "owner": is_owner(request),
        },
    )


@app.post("/a/{token}/contribute")
def contribute(
    request: Request,
    token: str,
    name: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
):
    album = db.get_album_by_token(token)
    if album is None:
        return RedirectResponse("/", status_code=303)
    contributor = name.strip()[:60] or None
    added = _ingest(album["id"], files, contributor=contributor)
    return RedirectResponse(f"/a/{token}?added={added}#gallery", status_code=303)


# --- media -----------------------------------------------------------------

@app.get("/media/{album_id}/thumb/{photo_id}.jpg")
def media_thumb(album_id: str, photo_id: str):
    photo = db.get_photo(photo_id)
    if not _photo_belongs(photo, album_id):
        return Response(status_code=404)
    path = images.thumb_path(album_id, photo_id)
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/jpeg")


@app.get("/media/{album_id}/disp/{photo_id}.jpg")
def media_disp(album_id: str, photo_id: str):
    photo = db.get_photo(photo_id)
    if not _photo_belongs(photo, album_id):
        return Response(status_code=404)
    path = images.disp_path(album_id, photo_id)
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/jpeg")


@app.get("/media/{album_id}/orig/{photo_id}")
def media_orig(album_id: str, photo_id: str):
    photo = db.get_photo(photo_id)
    if not _photo_belongs(photo, album_id):
        return Response(status_code=404)
    path = images.orig_path(album_id, photo_id, photo["ext"])
    if not path.exists():
        return Response(status_code=404)
    filename = photo["original_name"] or f"{photo_id}{photo['ext']}"
    return FileResponse(path, filename=filename)


@app.get("/healthz")
def healthz():
    return {"ok": True}


# --- ingest shared by owner upload + public contribute ---------------------

def _ingest(album_id: str, files: list[UploadFile], contributor: Optional[str]) -> int:
    added = 0
    for up in files:
        if not up or not up.filename:
            continue
        suffix = images._ext_of(up.filename)
        tmp = images.stream_to_temp(up.file, suffix=suffix)
        if tmp is None:
            continue
        try:
            if suffix == ".zip":
                added += images.add_zip_from_path(album_id, tmp, contributor)
            elif images.is_allowed_image(up.filename):
                if images.add_image_from_path(album_id, tmp, up.filename, contributor):
                    added += 1
        finally:
            tmp.unlink(missing_ok=True)
    return added
