from backend.app.core.config import settings
from backend.app.storage.base import StorageBackend, SignedUrl, build_storage_key
from backend.app.storage.local import LocalStorage
from backend.app.storage.s3 import S3Storage

_storage_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage_instance
    if _storage_instance is None:
        if settings.STORAGE_BACKEND == "s3":
            _storage_instance = S3Storage()
        else:
            _storage_instance = LocalStorage()
    return _storage_instance
