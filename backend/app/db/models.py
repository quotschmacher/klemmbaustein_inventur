from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BIGINT,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InventoryClass(StrEnum):
    REQUIRED = "required"
    SPARE = "spare"


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectStatus(StrEnum):
    PENDING_IMPORT = "pending_import"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    DEFICIT = "deficit"
    SURPLUS_REVIEW = "surplus_review"
    UNVERIFIED = "unverified"


class SnapshotValidationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


class CountOperation(StrEnum):
    ADJUST = "adjust"
    SET = "set"
    REPLACEMENT_BOOKING = "replacement_booking"


def value_enum(enum_class: type[StrEnum]) -> Enum:
    return Enum(
        enum_class,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
    )


class LegoSet(Base):
    __tablename__ = "sets"
    __table_args__ = (UniqueConstraint("provider", "provider_set_id", name="uq_sets_provider_set"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_set_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    set_id: Mapped[UUID] = mapped_column(ForeignKey("sets.id", ondelete="RESTRICT"), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    inventory_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inventory_snapshots.id", ondelete="RESTRICT")
    )
    status: Mapped[ProjectStatus] = mapped_column(
        value_enum(ProjectStatus),
        nullable=False,
        default=ProjectStatus.PENDING_IMPORT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (UniqueConstraint("set_id", "provider", "source_revision", name="uq_snapshot_source"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    set_id: Mapped[UUID] = mapped_column(ForeignKey("sets.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    validation_status: Mapped[SnapshotValidationStatus] = mapped_column(
        value_enum(SnapshotValidationStatus),
        nullable=False,
        default=SnapshotValidationStatus.PENDING,
    )
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)


class Color(Base):
    __tablename__ = "colors"
    __table_args__ = (UniqueConstraint("provider", "provider_color_id", name="uq_colors_provider_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_color_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rgb: Mapped[str | None] = mapped_column(String(6))
    bricklink_id: Mapped[int | None] = mapped_column(Integer)


class PartCatalog(Base):
    __tablename__ = "part_catalog"
    __table_args__ = (UniqueConstraint("provider", "part_num", name="uq_part_catalog_provider_num"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    part_num: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    bricklink_part_id: Mapped[str | None] = mapped_column(String(255))


class InventoryRequirement(Base):
    __tablename__ = "inventory_requirements"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "part_id", "color_id", "inventory_class", name="uq_requirement_identity"
        ),
        CheckConstraint("expected_qty >= 0", name="ck_requirement_expected_qty_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    part_id: Mapped[UUID] = mapped_column(ForeignKey("part_catalog.id", ondelete="RESTRICT"), nullable=False)
    color_id: Mapped[UUID] = mapped_column(ForeignKey("colors.id", ondelete="RESTRICT"), nullable=False)
    inventory_class: Mapped[InventoryClass] = mapped_column(
        value_enum(InventoryClass), nullable=False
    )
    expected_qty: Mapped[int] = mapped_column(BIGINT, nullable=False)


class InventoryProvenance(Base):
    __tablename__ = "inventory_provenance"
    __table_args__ = (CheckConstraint("quantity >= 0", name="ck_provenance_quantity_nonnegative"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_requirements.id", ondelete="RESTRICT"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(BIGINT, nullable=False)


class MinifigRequirement(Base):
    __tablename__ = "minifig_requirements"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "fig_ref", name="uq_minifig_requirement_snapshot_ref"),
        CheckConstraint("expected_qty >= 0", name="ck_minifig_expected_qty_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    fig_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    expected_qty: Mapped[int] = mapped_column(BIGINT, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048))


class CountingSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("project_id", "position", name="uq_session_project_position"),
        CheckConstraint("position >= 0", name="ck_session_position_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[SessionStatus] = mapped_column(
        value_enum(SessionStatus),
        nullable=False,
        default=SessionStatus.IN_PROGRESS,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CountBalance(Base):
    __tablename__ = "count_balances"
    __table_args__ = (
        UniqueConstraint("session_id", "requirement_id", name="uq_count_balance_session_requirement"),
        CheckConstraint("quantity >= 0", name="ck_count_balance_quantity_nonnegative"),
        CheckConstraint("revision >= 0", name="ck_count_balance_revision_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_requirements.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CountEvent(Base):
    __tablename__ = "count_events"
    __table_args__ = (
        UniqueConstraint("project_id", "client_mutation_id", name="uq_count_event_project_mutation"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_requirements.id", ondelete="RESTRICT"), nullable=False
    )
    client_mutation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation: Mapped[CountOperation] = mapped_column(
        value_enum(CountOperation), nullable=False
    )
    delta: Mapped[int | None] = mapped_column(BIGINT)
    quantity_before: Mapped[int | None] = mapped_column(BIGINT)
    quantity_after: Mapped[int | None] = mapped_column(BIGINT)
    order_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("replacement_items.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UnlistedFind(Base):
    __tablename__ = "unlisted_finds"
    __table_args__ = (CheckConstraint("qty >= 0", name="ck_unlisted_find_qty_nonnegative"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False)
    part_num: Mapped[str | None] = mapped_column(String(255))
    color_ref: Mapped[str | None] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    qty: Mapped[int] = mapped_column(BIGINT, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReplacementOrder(Base):
    __tablename__ = "replacement_orders"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReplacementItem(Base):
    __tablename__ = "replacement_items"
    __table_args__ = (
        CheckConstraint("qty_ordered >= 0", name="ck_replacement_item_ordered_nonnegative"),
        CheckConstraint("qty_received >= 0", name="ck_replacement_item_received_nonnegative"),
        CheckConstraint("qty_booked >= 0", name="ck_replacement_item_booked_nonnegative"),
        CheckConstraint("qty_booked <= qty_received", name="ck_replacement_item_booked_received"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("replacement_orders.id", ondelete="RESTRICT"), nullable=False
    )
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_requirements.id", ondelete="RESTRICT"), nullable=False
    )
    qty_ordered: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    qty_received: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    target_session_id: Mapped[UUID | None] = mapped_column(ForeignKey("sessions.id", ondelete="RESTRICT"))
    qty_booked: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)


class ProjectEvent(Base):
    __tablename__ = "project_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
