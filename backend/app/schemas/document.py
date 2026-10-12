from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: str
    tenant_id: str
    document_type: str
    entity_type: str
    entity_id: str
    storage_provider: str
    file_name: str
    mime_type: str
    file_size: int
    checksum: str
    version: int
    is_simulated: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDownloadResponse(BaseModel):
    document: DocumentResponse
    download_url: str
    expires_at: datetime
