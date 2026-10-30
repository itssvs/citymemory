"""Privacy and security helpers.

- Photos: only real JPEG/PNG/WebP images up to MAX_PHOTO_MB are accepted. Each one is decoded and
  re-saved as a fresh JPEG, which drops all metadata (EXIF, including GPS location and phone model),
  and is downsized to MAX_SIDE pixels.
- Photos are never served publicly. API responses carry a signed link that expires after
  PHOTO_LINK_SECONDS, issued only to people allowed to see that record.
- Login: after MAX_FAILS wrong passwords for a username within LOCK_MINUTES, that username is locked
  for LOCK_MINUTES.
"""
import hashlib
import hmac
import io
import os
import re
import secrets
import threading
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(HERE, "uploads")
SECRET_FILE = os.path.join(HERE, ".secret")
MAX_PHOTO_MB = 8
MAX_SIDE = 1600
PHOTO_LINK_SECONDS = 3600
MAX_FAILS = 5
LOCK_MINUTES = 15
NAME_RE = re.compile(r"^[a-f0-9]{32}\.(jpg|jpeg|png|webp)$")


def _secret() -> bytes:
    env = os.environ.get("CITYMEMORY_SECRET")
    if env:
        return env.encode()
    if not os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "w") as f:
            f.write(secrets.token_hex(32))
    with open(SECRET_FILE) as f:
        return f.read().strip().encode()


SECRET = _secret()


# ---------------------------------------------------------------- photos
class PhotoError(ValueError):
    pass


def save_image(upload) -> str:
    """Validate, strip metadata, downsize and store an uploaded image. Returns the stored path."""
    from PIL import Image, UnidentifiedImageError

    data = upload.file.read(MAX_PHOTO_MB * 1024 * 1024 + 1)
    if len(data) > MAX_PHOTO_MB * 1024 * 1024:
        raise PhotoError(f"The photo is larger than {MAX_PHOTO_MB} MB. Please choose a smaller one.")
    if not data:
        raise PhotoError("The photo file is empty.")
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG", "WEBP", "MPO"):
            raise PhotoError("Only JPEG, PNG or WebP photos are accepted.")
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise PhotoError("That file is not a photo we can read. Please upload a JPEG, PNG or WebP image.")
    try:
        from PIL import ImageOps

        img = ImageOps.exif_transpose(img)  # keep the photo upright before the metadata is dropped
    except Exception:
        pass
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    os.makedirs(UPLOADS, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    img.save(os.path.join(UPLOADS, name), "JPEG", quality=85, optimize=True)  # no exif= argument: nothing carried over
    return f"/uploads/{name}"


def scrub_existing() -> int:
    """Re-save photos uploaded before metadata stripping existed. Safe to run on every start."""
    from PIL import Image

    cleaned = 0
    if not os.path.isdir(UPLOADS):
        return 0
    for name in os.listdir(UPLOADS):
        path = os.path.join(UPLOADS, name)
        if not NAME_RE.match(name):
            continue
        try:
            with Image.open(path) as img:
                if not (img.info.get("exif") or len(img.getexif())):
                    continue
                img.load()
                clean = img.convert("RGB")
            clean.save(path, "JPEG" if name.endswith((".jpg", ".jpeg")) else img.format or "JPEG", quality=85)
            cleaned += 1
        except Exception:
            continue
    return cleaned


def _sig(name: str, exp: int) -> str:
    return hmac.new(SECRET, f"{name}|{exp}".encode(), hashlib.sha256).hexdigest()[:40]


def sign_photo(stored):
    """Turn a stored '/uploads/<name>' path into a short-lived signed API link."""
    if not stored:
        return None
    name = os.path.basename(stored)
    exp = int(time.time()) + PHOTO_LINK_SECONDS
    return f"/api/photos/{name}?exp={exp}&sig={_sig(name, exp)}"


def check_photo_link(name: str, exp: int, sig: str) -> bool:
    if not NAME_RE.match(name or "") or exp < time.time():
        return False
    return hmac.compare_digest(_sig(name, exp), sig or "")


def sign_fields(d: dict, *keys) -> dict:
    for k in keys:
        if d.get(k):
            d[k] = sign_photo(d[k])
    return d


# ---------------------------------------------------------------- sessions
def token_hash(token: str) -> str:
    """Sessions are stored as hashes, so a copy of the database does not hand out live logins."""
    return hashlib.sha256((token or "").encode()).hexdigest()


# ---------------------------------------------------------------- login attempts
class LoginLimiter:
    def __init__(self):
        self._fails = {}
        self._lock = threading.Lock()

    def _recent(self, key):
        cutoff = time.time() - LOCK_MINUTES * 60
        return [t for t in self._fails.get(key, []) if t > cutoff]

    def locked_for(self, username: str) -> int:
        """Seconds left on the lock, or 0."""
        key = (username or "").strip().lower()
        with self._lock:
            recent = self._recent(key)
            self._fails[key] = recent
            if len(recent) >= MAX_FAILS:
                return int(recent[-MAX_FAILS] + LOCK_MINUTES * 60 - time.time()) + 1
        return 0

    def failed(self, username: str):
        key = (username or "").strip().lower()
        with self._lock:
            self._fails[key] = self._recent(key) + [time.time()]

    def succeeded(self, username: str):
        with self._lock:
            self._fails.pop((username or "").strip().lower(), None)

    def reset(self):
        with self._lock:
            self._fails.clear()


LIMITER = LoginLimiter()

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(self), geolocation=(self), microphone=()",
}
