from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Text, TIMESTAMP, ForeignKey, func, Integer, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as Uuid

from bimcalc.db.models import Base

class ProjectDocumentModel(Base):
    """Uploaded project document (invoice, schedule, etc.)."""

    __tablename__ = "project_documents"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False) # Path on disk/storage
    file_type: Mapped[str] = mapped_column(Text, nullable=False) # e.g., "application/pdf"
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending") # pending, processing, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text)
    
    uploaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # Extracted items from this document
    extracted_items: Mapped[list["ExtractedItemModel"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

class ExtractedItemModel(Base):
    """Line item extracted from a document."""

    __tablename__ = "extracted_items"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Raw extracted text
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Parsed fields (nullable as extraction might be partial)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float | None] = mapped_column(Numeric(12, 2))
    unit: Mapped[str | None] = mapped_column(Text)
    unit_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    total_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    
    # Status of this item (e.g., converted to estimate)
    is_converted: Mapped[bool] = mapped_column(default=False)
    converted_item_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))

    document: Mapped["ProjectDocumentModel"] = relationship(back_populates="extracted_items")
