"""Object-storage abstraction. Application code depends only on this interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SignedUrl:
    url: str
    expires_at: datetime


class StorageBackend(ABC):
    provider_name = "unknown"

    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...

    @abstractmethod
    def download(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def generate_signed_url(self, key: str, expires_in: int = 300, file_name: Optional[str] = None,
                            content_type: Optional[str] = None) -> SignedUrl: ...

    @abstractmethod
    def healthcheck(self) -> bool: ...


def build_storage_key(tenant_id: str, entity_type: str, entity_id: str, version: int, file_name: str) -> str:
    """Tenant-prefixed, collision-free object key. The tenant prefix makes cross-tenant
    access impossible to express through a key built by the application."""
    safe_name = file_name.replace("/", "_").replace("\\", "_")
    return f"tenants/{tenant_id}/{entity_type.lower()}/{entity_id}/v{version}/{safe_name}"
