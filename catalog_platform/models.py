"""Metadata only: image binaries stay in Drive, credentials are encrypted."""

from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Product(Record, Base):
    __tablename__ = "rincon_products"
    __table_args__ = (UniqueConstraint("tenant_id", "sku"),)
    sku: Mapped[str] = mapped_column(String(80), index=True)
    barcode: Mapped[str] = mapped_column(String(40), default="", index=True)
    name: Mapped[str] = mapped_column(String(180))
    brand: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(160), default="")
    subcategory: Mapped[str] = mapped_column(String(160), default="")
    short_description: Mapped[str] = mapped_column(Text, default="")
    long_description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    product_type: Mapped[str] = mapped_column(String(20), default="simple")
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("rincon_products.id"), nullable=True
    )
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock: Mapped[float | None] = mapped_column(Float, nullable=True)
    woocommerce_stock: Mapped[float | None] = mapped_column(Float, nullable=True)
    loyverse_stock: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    sync_status: Mapped[str] = mapped_column(String(24), default="pending")
    woocommerce_product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    woocommerce_variation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wordpress_media_ids: Mapped[list] = mapped_column(JSON, default=list)
    loyverse_item_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    loyverse_variant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    loyverse_store_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_woocommerce_sync: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    woocommerce_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_loyverse_sync: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class ProductVariant(Record, Base):
    __tablename__ = "rincon_product_variants"
    __table_args__ = (UniqueConstraint("tenant_id", "child_product_id"),)
    product_id: Mapped[str] = mapped_column(ForeignKey("rincon_products.id"))
    child_product_id: Mapped[str] = mapped_column(ForeignKey("rincon_products.id"))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class ProductImage(Record, Base):
    __tablename__ = "rincon_product_images"
    product_id: Mapped[str] = mapped_column(
        ForeignKey("rincon_products.id"), index=True
    )
    drive_file_id: Mapped[str] = mapped_column(String(160))
    url: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(String(24), default="reference")
    status: Mapped[str] = mapped_column(String(24), default="completed")
    checksum: Mapped[str] = mapped_column(String(64), default="")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(80), default="image/jpeg")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Category(Record, Base):
    __tablename__ = "rincon_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    name: Mapped[str] = mapped_column(String(160))


class Brand(Record, Base):
    __tablename__ = "rincon_brands"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    name: Mapped[str] = mapped_column(String(120))


class InventoryMovement(Record, Base):
    __tablename__ = "rincon_inventory_movements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "source_event_id", "product_id"),
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("rincon_products.id"), index=True
    )
    variant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(30))
    source_event_id: Mapped[str] = mapped_column(String(200))
    store_id: Mapped[str] = mapped_column(String(100), default="")
    quantity_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity_after: Mapped[float] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class GenerationJob(Record, Base):
    __tablename__ = "rincon_generation_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_key", "product_id"),
        Index("rincon_job_queue", "status", "created_at"),
    )
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("rincon_products.id"), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(240))
    kind: Mapped[str] = mapped_column(String(30), default="generation")
    request_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), default="queued")
    provider: Mapped[str] = mapped_column(String(30), default="gemini")
    model: Mapped[str] = mapped_column(String(100), default="")
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="En cola")
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_until: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class GeneratedAsset(Record, Base):
    __tablename__ = "rincon_generated_assets"
    __table_args__ = (UniqueConstraint("job_id", "slot", "sample"),)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("rincon_generation_jobs.id"), index=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("rincon_products.id"), index=True
    )
    image_id: Mapped[str] = mapped_column(ForeignKey("rincon_product_images.id"))
    raw_drive_file_id: Mapped[str] = mapped_column(String(160))
    slot: Mapped[str] = mapped_column(String(30))
    sample: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(30), default="gemini")
    model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    history: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class IntegrationAccount(Record, Base):
    __tablename__ = "rincon_integration_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "actor"),)
    provider: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(240))
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="connected")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class IntegrationMapping(Record, Base):
    __tablename__ = "rincon_integration_mappings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "entity_type", "external_id"),
    )
    internal_product_id: Mapped[str] = mapped_column(ForeignKey("rincon_products.id"))
    provider: Mapped[str] = mapped_column(String(30))
    entity_type: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(160))
    parent_external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class SyncEvent(Record, Base):
    __tablename__ = "rincon_sync_events"
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("rincon_products.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(30))
    destination: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24))
    message: Mapped[str] = mapped_column(Text, default="")
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class WebhookEvent(Record, Base):
    __tablename__ = "rincon_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id"),
        UniqueConstraint("tenant_id", "provider", "payload_hash"),
    )
    provider: Mapped[str] = mapped_column(String(30))
    event_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), default="queued")
    encrypted_payload: Mapped[str] = mapped_column(Text)


class AuditLog(Record, Base):
    __tablename__ = "rincon_audit_logs"
    actor: Mapped[str] = mapped_column(String(240))
    action: Mapped[str] = mapped_column(String(100))
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    system: Mapped[str] = mapped_column(String(40), default="app")
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(String(40), default="completed")


class WorkerHeartbeat(Base):
    __tablename__ = "rincon_worker_heartbeats"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    updated: Mapped[float] = mapped_column(Float)
    version: Mapped[str] = mapped_column(String(100), default="")


class OrderSnapshot(Record, Base):
    __tablename__ = "rincon_order_snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "woocommerce_id"),)
    woocommerce_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40))
    total: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
