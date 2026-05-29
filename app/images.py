"""Upload handling: streaming to disk, HEIC/EXIF-aware derivatives, safe zips.

For every accepted photo we keep three files under the album's directory:
  orig/<id>.<ext>   the original bytes (for download / fidelity)
  disp/<id>.jpg     a web-safe display image (<=1600px) used in the lightbox
  thumb/<id>.jpg    a small thumbnail (<=600px) used in the grid

HEIC/HEIF (the iPhone default) can't render in browsers, so we always serve the
JPEG derivatives and apply EXIF orientation so nothing comes out sideways.
"""
from __future__ import annotations

import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import BinaryIO, Optional

from PIL import Image, ImageOps

from . import config, db

# Register HEIF/HEIC support with Pillow.
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001 - degrade gracefully if the lib is missing
    pass

DISPLAY_MAX_EDGE = 1600


def _album_dir(album_id: str) -> Path:
    return config.ALBUMS_DIR / album_id


def orig_path(album_id: str, photo_id: str, ext: str) -> Path:
    return _album_dir(album_id) / "orig" / f"{photo_id}{ext}"


def disp_path(album_id: str, photo_id: str) -> Path:
    return _album_dir(album_id) / "disp" / f"{photo_id}.jpg"


def thumb_path(album_id: str, photo_id: str) -> Path:
    return _album_dir(album_id) / "thumb" / f"{photo_id}.jpg"


def _ext_of(name: str) -> str:
    return Path(name).suffix.lower()


def is_allowed_image(name: str) -> bool:
    return _ext_of(name) in config.ALLOWED_IMAGE_EXTS


def stream_to_temp(src: BinaryIO, suffix: str = "") -> Optional[Path]:
    """Copy an uploaded stream to a temp file, enforcing the per-file cap.

    Returns the temp path, or None if the file exceeds MAX_FILE_BYTES.
    """
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    total = 0
    try:
        with open(fd, "wb") as out:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > config.MAX_FILE_BYTES:
                    Path(tmp).unlink(missing_ok=True)
                    return None
                out.write(chunk)
        return Path(tmp)
    except Exception:  # noqa: BLE001
        Path(tmp).unlink(missing_ok=True)
        return None


def _make_derivative(img: Image.Image, dest: Path, max_edge: int) -> None:
    work = img.copy()
    work.thumbnail((max_edge, max_edge), Image.LANCZOS)
    if work.mode not in ("RGB", "L"):
        work = work.convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    work.save(dest, format="JPEG", quality=85, optimize=True)


def add_image_from_path(
    album_id: str,
    src_path: Path,
    original_name: str,
    contributor: Optional[str],
) -> Optional[str]:
    """Validate, store, and index one image. Returns the new photo id or None."""
    ext = _ext_of(original_name)
    if ext not in config.ALLOWED_IMAGE_EXTS:
        return None
    try:
        with Image.open(src_path) as raw:
            img = ImageOps.exif_transpose(raw)  # honour orientation
            width, height = img.size
            photo_id = uuid.uuid4().hex
            _make_derivative(img, disp_path(album_id, photo_id), DISPLAY_MAX_EDGE)
            _make_derivative(img, thumb_path(album_id, photo_id), config.THUMB_MAX_EDGE)
    except Exception:  # noqa: BLE001 - not a decodable image; skip it
        return None

    dest_orig = orig_path(album_id, photo_id, ext)
    dest_orig.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_path, dest_orig)

    db.add_photo(photo_id, album_id, ext, original_name, contributor, width, height)
    # First photo in an album becomes its cover automatically.
    album = db.get_album(album_id)
    if album is not None and not album["cover_id"]:
        db.set_cover(album_id, photo_id)
    return photo_id


def add_zip_from_path(
    album_id: str, zip_path: Path, contributor: Optional[str]
) -> int:
    """Extract image entries from a zip safely and add them. Returns count added."""
    added = 0
    extracted_total = 0
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                # zip-slip guard: ignore absolute paths and parent traversal.
                if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                    continue
                base = Path(name).name
                if not base or not is_allowed_image(base):
                    continue
                extracted_total += info.file_size
                if extracted_total > config.MAX_ZIP_EXTRACTED_BYTES:
                    break
                with zf.open(info) as member:
                    tmp = stream_to_temp(member, suffix=_ext_of(base))
                if tmp is None:
                    continue
                try:
                    if add_image_from_path(album_id, tmp, base, contributor):
                        added += 1
                finally:
                    tmp.unlink(missing_ok=True)
    except zipfile.BadZipFile:
        return added
    return added


def delete_photo_files(album_id: str, photo_id: str, ext: str) -> None:
    for p in (
        orig_path(album_id, photo_id, ext),
        disp_path(album_id, photo_id),
        thumb_path(album_id, photo_id),
    ):
        p.unlink(missing_ok=True)


def delete_album_files(album_id: str) -> None:
    shutil.rmtree(_album_dir(album_id), ignore_errors=True)
