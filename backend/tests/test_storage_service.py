import pytest
import time
from backend.app.core.database import SessionLocal
from backend.app.core.errors import StorageError, NotFoundError
from backend.app.storage.local import LocalStorage, sign_local_token, verify_local_token
from backend.app.services.document_service import document_service


def test_local_storage_crud(tmp_path):
    storage = LocalStorage(root=str(tmp_path))
    key = "tenants/t1/invoice/inv-1/v1/test.pdf"
    content = b"%PDF-1.4 sample content"

    assert not storage.exists(key)
    storage.upload(key, content, "application/pdf")
    assert storage.exists(key)

    downloaded = storage.download(key)
    assert downloaded == content

    storage.delete(key)
    assert not storage.exists(key)


def test_local_storage_path_traversal_guard(tmp_path):
    storage = LocalStorage(root=str(tmp_path))
    with pytest.raises(StorageError):
        storage.upload("../outside.txt", b"malicious", "text/plain")


def test_hmac_signed_url_token_verification():
    payload = {"key": "test/path.pdf", "exp": int(time.time()) + 60, "name": "path.pdf", "ct": "application/pdf"}
    token = sign_local_token(payload)
    verified = verify_local_token(token)
    assert verified is not None
    assert verified["key"] == "test/path.pdf"

    # Test expired token
    expired_payload = {"key": "test/path.pdf", "exp": int(time.time()) - 60}
    expired_token = sign_local_token(expired_payload)
    assert verify_local_token(expired_token) is None

    # Test tampered token
    parts = token.split(".")
    tampered_token = f"{parts[0]}.invalid_signature"
    assert verify_local_token(tampered_token) is None


import uuid


def test_document_service_versioning_and_tenant_isolation():
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    tenant_a = f"tenant-isolation-a-{uid}"
    tenant_b = f"tenant-isolation-b-{uid}"
    entity_id = f"inv-iso-{uid}"

    try:
        # Store version 1
        doc_v1 = document_service.store_document(
            db=db,
            tenant_id=tenant_a,
            entity_type="INVOICE",
            entity_id=entity_id,
            document_type="INVOICE_PDF",
            file_name="INV-100.pdf",
            mime_type="application/pdf",
            data=b"version 1 bytes",
            is_simulated=True,
        )
        assert doc_v1.version == 1

        # Store version 2 for the same entity
        doc_v2 = document_service.store_document(
            db=db,
            tenant_id=tenant_a,
            entity_type="INVOICE",
            entity_id=entity_id,
            document_type="INVOICE_PDF",
            file_name="INV-100.pdf",
            mime_type="application/pdf",
            data=b"version 2 bytes",
            is_simulated=True,
        )
        assert doc_v2.version == 2

        # Fetch latest version
        latest = document_service.get_latest_document(
            db=db,
            tenant_id=tenant_a,
            entity_type="INVOICE",
            entity_id=entity_id,
        )
        assert latest is not None
        assert latest.version == 2

        # Tenant B MUST NOT be able to access Tenant A's document
        with pytest.raises(NotFoundError):
            document_service.get_document(db, document_id=doc_v1.id, tenant_id=tenant_b)

        # Signed URL generation for valid tenant
        doc, signed_url = document_service.generate_download_url(
            db=db, document_id=doc_v1.id, tenant_id=tenant_a
        )
        assert signed_url.url.startswith("http")

    finally:
        db.close()
