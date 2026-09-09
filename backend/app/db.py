"""
Persistência — SQLAlchemy. SQLite por padrão (arquivo local), mesmo schema
funciona em Postgres trocando apenas a DATABASE_URL (requisito do documento:
"Construir o schema PostgreSQL").
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                         Integer, String, create_engine)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

DATABASE_URL = os.environ.get("TACELERAR_DB_URL", "sqlite:///./tacelerar.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="analista")  # diretor | coordenador | analista
    manager_id = Column(String, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    segment = Column(String, nullable=True)
    subsegment = Column(String, nullable=True)
    adherence_answers = Column(JSON, default=dict)  # {module_id: bool}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    batches = relationship("ImportBatch", back_populates="project", cascade="all, delete-orphan")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    source_file = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="PENDING")  # PENDING | PROCESSING | DONE | FAILED
    error_message = Column(String, nullable=True)
    total_records = Column(Integer, default=0)
    exception_count = Column(Integer, default=0)
    data_readiness_score = Column(Float, default=0.0)
    report = Column(JSON, default=dict)

    project = relationship("Project", back_populates="batches")
    products = relationship("ProductRecord", back_populates="batch", cascade="all, delete-orphan")
    exceptions = relationship("ExceptionRow", back_populates="batch", cascade="all, delete-orphan")


class ProductRecord(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, ForeignKey("import_batches.id"), nullable=False, index=True)

    external_id = Column(String, nullable=False)
    sku = Column(String, nullable=False, index=True)
    description_raw = Column(String)
    description = Column(String)
    barcode = Column(String)
    ncm = Column(String)
    cest = Column(String)
    unit = Column(String)
    brand = Column(String)
    family = Column(String)
    department = Column(String)
    weight = Column(Float)
    origin_field = Column(String)
    status = Column(String, default="RAW")
    provenance = Column(JSON, default=list)
    extra = Column(JSON, default=dict)

    batch = relationship("ImportBatch", back_populates="products")


class ExceptionRow(Base):
    __tablename__ = "exceptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, ForeignKey("import_batches.id"), nullable=False, index=True)

    record_id = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    reason_code = Column(String, nullable=False)
    description = Column(String)
    severity = Column(String, default="MEDIUM")
    payload = Column(JSON, default=dict)

    # Exception Queue — workflow de decisão humana (princípio central do documento).
    resolution_status = Column(String, default="PENDING", index=True)  # PENDING | APPROVED | REJECTED
    resolved_by = Column(String, nullable=True)
    resolution_note = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    batch = relationship("ImportBatch", back_populates="exceptions")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()


def get_db():
    """Dependência FastAPI — sessão por request, fechada ao final."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()
