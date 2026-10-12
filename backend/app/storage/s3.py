"""S3-compatible storage (AWS S3, Cloudflare R2, MinIO, ...)."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.app.core.config import settings
from backend.app.core.errors import StorageError
from backend.app.storage.base import SignedUrl, StorageBackend


class S3Storage(StorageBackend):
    provider_name = "s3"

    def __init__(self, client=None, bucket: Optional[str] = None):
        self.bucket = bucket or settings.OBJECT_STORAGE_BUCKET
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=settings.OBJECT_STORAGE_ENDPOINT or None,
                region_name=settings.OBJECT_STORAGE_REGION,
                aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY or None,
                aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_KEY or None,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                              retries={"max_attempts": 3, "mode": "standard"}),
            )
        self.client = client

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        kwargs = {"Bucket": self.bucket, "Key": key, "Body": data, "ContentType": content_type}
        if not settings.OBJECT_STORAGE_ENDPOINT:  # plain AWS S3; other providers manage encryption themselves
            kwargs["ServerSideEncryption"] = "AES256"
        try:
            self.client.put_object(**kwargs)
        except Exception as exc:
            raise StorageError(f"S3 upload failed: {exc.__class__.__name__}") from exc

    def download(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as exc:
            raise StorageError(f"S3 download failed: {exc.__class__.__name__}") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise StorageError(f"S3 delete failed: {exc.__class__.__name__}") from exc

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise StorageError(f"S3 exists check failed: {exc.__class__.__name__}") from exc

    def generate_signed_url(self, key: str, expires_in: int = 300, file_name: Optional[str] = None,
                            content_type: Optional[str] = None) -> SignedUrl:
        params = {"Bucket": self.bucket, "Key": key}
        if file_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{file_name}"'
        if content_type:
            params["ResponseContentType"] = content_type
        try:
            url = self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)
        except Exception as exc:
            raise StorageError(f"S3 signing failed: {exc.__class__.__name__}") from exc
        return SignedUrl(url=url, expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in))

    def healthcheck(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False
