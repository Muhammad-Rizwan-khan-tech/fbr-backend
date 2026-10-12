"""Filesystem storage for development and tests.

Signed URLs are HMAC tokens served by ``GET /api/v1/documents/files/{token}`` so the
local backend exercises the same "short-lived signed URL" flow as S3.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from backend.app.core.config import settings
from backend.app.core.errors import StorageError
from backend.app.storage.base import SignedUrl, StorageBackend


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign_local_token(payload: dict) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"


def verify_local_token(token: str) -> Optional[dict]:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(sig), expected):
            return None
        payload = json.loads(_unb64(body))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


class LocalStorage(StorageBackend):
    provider_name = "local"

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or settings.LOCAL_STORAGE_PATH).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:  # path traversal guard
            raise StorageError("Invalid storage key")
        return path

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        try:
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
            tmp.write_bytes(data)
            try:
                os.replace(tmp, path)
            except OSError:
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                if not path.exists():
                    raise
        except StorageError:
            raise
        except OSError as exc:
            raise StorageError(f"Local upload failed: {exc}") from exc

    def download(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("Object not found") from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"Local delete failed: {exc}") from exc

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def generate_signed_url(self, key: str, expires_in: int = 300, file_name: Optional[str] = None,
                            content_type: Optional[str] = None) -> SignedUrl:
        exp = int(time.time()) + expires_in
        token = sign_local_token({"key": key, "exp": exp, "name": file_name, "ct": content_type})
        url = f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}{settings.API_V1_STR}/documents/files/{token}"
        return SignedUrl(url=url, expires_at=datetime.fromtimestamp(exp, tz=timezone.utc))

    def healthcheck(self) -> bool:
        try:
            probe = self.root / ".healthcheck"
            probe.write_text("ok")
            return probe.read_text() == "ok"
        except OSError:
            return False
