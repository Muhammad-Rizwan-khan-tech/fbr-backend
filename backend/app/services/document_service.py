import hashlib
import logging
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError

from backend.app.core.errors import NotFoundError, AuthorizationError, StorageError
from backend.app.models.document import Document, DocumentType
from backend.app.storage import get_storage, build_storage_key
from backend.app.storage.base import SignedUrl

logger = logging.getLogger(__name__)


class DocumentService:
    """Manages document lifecycle, metadata persistence in PostgreSQL,
    and object storage interactions with strict tenant isolation.
    """

    def __init__(self, storage=None):
        self.storage = storage or get_storage()

    def store_document(
        self,
        db: Session,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        document_type: str,
        file_name: str,
        mime_type: str,
        data: bytes,
        created_by: Optional[str] = None,
        is_simulated: bool = False,
    ) -> Document:
        """Stores binary data to object storage and writes a metadata record to PostgreSQL."""
        checksum = hashlib.sha256(data).hexdigest()
        file_size = len(data)

        # Check existing highest version
        existing_doc = (
            db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.entity_type == entity_type,
                Document.entity_id == entity_id,
                Document.document_type == document_type,
            )
            .order_by(desc(Document.version))
            .first()
        )
        version = (existing_doc.version + 1) if existing_doc else 1

        # Build tenant-prefixed collision-free storage key
        storage_key = build_storage_key(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            version=version,
            file_name=file_name,
        )

        logger.info(
            "Uploading document to storage",
            extra={
                "tenant_id": tenant_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "version": version,
                "storage_key": storage_key,
                "file_size": file_size,
            },
        )

        # Upload to storage provider
        self.storage.upload(storage_key, data, content_type=mime_type)

        # Persist document metadata in DB
        doc = Document(
            tenant_id=tenant_id,
            document_type=document_type,
            entity_type=entity_type,
            entity_id=entity_id,
            storage_provider=self.storage.provider_name,
            storage_key=storage_key,
            file_name=file_name,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
            version=version,
            is_simulated=is_simulated,
            created_by=created_by,
        )
        try:
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return doc
        except IntegrityError:
            db.rollback()
            existing = self.get_latest_document(
                db=db,
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                document_type=document_type
            )
            if existing:
                return existing
            raise

    def get_document(self, db: Session, document_id: str, tenant_id: str) -> Document:
        """Fetch document metadata ensuring strict tenant isolation."""
        doc = (
            db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            raise NotFoundError(f"Document {document_id} not found or access denied")
        return doc

    def get_latest_document(
        self,
        db: Session,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        document_type: str = DocumentType.INVOICE_PDF.value,
    ) -> Optional[Document]:
        """Fetch latest version of a document for a given entity."""
        return (
            db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.entity_type == entity_type,
                Document.entity_id == entity_id,
                Document.document_type == document_type,
            )
            .order_by(desc(Document.version))
            .first()
        )

    def list_documents(
        self,
        db: Session,
        tenant_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Document]:
        """List documents for a tenant with optional entity filters."""
        query = db.query(Document).filter(Document.tenant_id == tenant_id)
        if entity_type:
            query = query.filter(Document.entity_type == entity_type)
        if entity_id:
            query = query.filter(Document.entity_id == entity_id)
        return query.order_by(desc(Document.created_at)).limit(limit).all()

    def generate_download_url(
        self, db: Session, document_id: str, tenant_id: str, expires_in: int = 300
    ) -> Tuple[Document, SignedUrl]:
        """Verify tenant ownership and generate a short-lived signed download URL."""
        doc = self.get_document(db, document_id=document_id, tenant_id=tenant_id)
        signed_url = self.storage.generate_signed_url(
            key=doc.storage_key,
            expires_in=expires_in,
            file_name=doc.file_name,
            content_type=doc.mime_type,
        )
        return doc, signed_url

    def download_document_bytes(
        self, db: Session, document_id: str, tenant_id: str
    ) -> Tuple[Document, bytes]:
        """Directly download raw bytes for a document."""
        doc = self.get_document(db, document_id=document_id, tenant_id=tenant_id)
        data = self.storage.download(doc.storage_key)
        return doc, data


document_service = DocumentService()
