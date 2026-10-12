from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Header, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.user import User
from backend.app.models.tenant import Organization
from backend.app.models.document import Document
from backend.app.schemas.document import DocumentResponse, DocumentDownloadResponse
from backend.app.services.document_service import document_service
from backend.app.storage.local import verify_local_token
from backend.app.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (INVOICE, CREDIT_NOTE, etc.)"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    limit: int = Query(50, ge=1, le=100),
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List document metadata records for the current tenant."""
    return document_service.list_documents(
        db=db,
        tenant_id=tenant.id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_metadata(
    document_id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve document metadata ensuring strict tenant isolation."""
    return document_service.get_document(db=db, document_id=document_id, tenant_id=tenant.id)


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
def get_document_download_url(
    document_id: str,
    expires_in: int = Query(300, ge=60, le=3600, description="URL validity in seconds"),
    redirect: bool = Query(False, description="If true, immediately 307 redirects to download URL"),
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generates a short-lived signed URL for secure, tenant-isolated document access."""
    doc, signed_url = document_service.generate_download_url(
        db=db,
        document_id=document_id,
        tenant_id=tenant.id,
        expires_in=expires_in,
    )
    if redirect:
        return RedirectResponse(url=signed_url.url, status_code=307)

    return DocumentDownloadResponse(
        document=doc,
        download_url=signed_url.url,
        expires_at=signed_url.expires_at,
    )


@router.get("/files/{token}")
def serve_signed_local_file(token: str):
    """Public token verification endpoint for local storage backend.
    Validates HMAC signature and expiry, then streams raw document bytes.
    """
    payload = verify_local_token(token)
    if not payload:
        raise HTTPException(status_code=403, detail="Signed URL is invalid or has expired.")

    storage = get_storage()
    try:
        data = storage.download(payload["key"])
        file_name = payload.get("name") or "document.bin"
        content_type = payload.get("ct") or "application/octet-stream"
        return Response(
            content=data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{file_name}"',
                "Cache-Control": "private, max-age=300",
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Requested file was not found in storage.")
