"""
Data Ingestion — converte arquivos de origem (CSV/Excel) em CanonicalProduct.

Mantém sempre o dado RAW original (description_raw) separado de qualquer
transformação, conforme guardrail de "dados ruins na origem".
"""

from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import Iterator

from app.canonical.models import CanonicalProduct, RecordStatus
from app.ingestion.profiling import suggest_column_map

# Mapeamento de colunas de origem -> campos canônicos, usado como fallback quando
# a inferência automática (profiling) não encontra correspondência suficiente.
DEFAULT_COLUMN_MAP = {
    "codigo": "external_id",
    "sku": "sku",
    "descricao": "description_raw",
    "ean": "barcode",
    "ncm": "ncm",
    "cest": "cest",
    "unidade": "unit",
    "marca": "brand",
    "familia": "family",
    "departamento": "department",
    "peso": "weight",
    "origem": "origin",
}


def _normalize_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_")


def resolve_column_map(headers: list[str], column_map: dict | None) -> dict:
    """Se column_map não for fornecido explicitamente, usa profiling automático
    (suggest_column_map) para inferir; cai para DEFAULT_COLUMN_MAP quando a
    inferência não encontra nada para um header conhecido."""
    if column_map is not None:
        return column_map

    inferred, _suggestions = suggest_column_map(headers)
    merged = dict(DEFAULT_COLUMN_MAP)
    merged.update(inferred)
    return merged


def ingest_csv(path: str | Path, column_map: dict | None = None,
               source_label: str | None = None) -> Iterator[CanonicalProduct]:
    """Lê um CSV de produtos e produz registros canônicos em status RAW/PARSED.

    Se column_map não for passado, infere automaticamente via profiling de headers.
    """
    path = Path(path)
    batch_id = str(uuid.uuid4())[:8]

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_headers = list(reader.fieldnames)
        reader.fieldnames = [_normalize_header(h) for h in raw_headers]
        column_map = resolve_column_map(reader.fieldnames, column_map)

        for i, row in enumerate(reader, start=1):
            data: dict = {}
            for src_col, canon_field in column_map.items():
                if src_col in row and row[src_col] not in (None, ""):
                    data[canon_field] = row[src_col].strip()

            external_id = data.get("external_id") or data.get("sku") or f"row-{i}"
            sku = data.get("sku") or external_id
            description_raw = data.get("description_raw", "")

            weight = None
            if data.get("weight"):
                try:
                    weight = float(str(data["weight"]).replace(",", "."))
                except ValueError:
                    weight = None

            product = CanonicalProduct(
                external_id=str(external_id),
                sku=str(sku),
                description_raw=description_raw,
                barcode=data.get("barcode"),
                ncm=data.get("ncm"),
                cest=data.get("cest"),
                unit=data.get("unit"),
                brand=data.get("brand"),
                family=data.get("family"),
                department=data.get("department"),
                weight=weight,
                origin=data.get("origin"),
                status=RecordStatus.PARSED,
                source_file=path.name,
                import_batch_id=batch_id,
            )
            product.add_provenance(
                field="*", origin=source_label or f"arquivo:{path.name}",
                rule="ingest_csv", confidence=1.0,
            )
            yield product


def ingest_excel(path: str | Path, column_map: dict | None = None,
                  sheet_name: str | int = 0) -> Iterator[CanonicalProduct]:
    """Lê um XLSX de produtos. Requer openpyxl."""
    try:
        import openpyxl  # noqa: F401
        from openpyxl.utils import get_column_letter  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "openpyxl não instalado. Rode: pip install openpyxl --break-system-packages"
        ) from e

    import openpyxl

    path = Path(path)
    batch_id = str(uuid.uuid4())[:8]

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet_name] if isinstance(sheet_name, str) else wb.worksheets[sheet_name]

    rows = ws.iter_rows(values_only=True)
    headers = [_normalize_header(str(h)) for h in next(rows)]
    column_map = resolve_column_map(headers, column_map)

    for i, raw_row in enumerate(rows, start=1):
        row = dict(zip(headers, raw_row))
        data: dict = {}
        for src_col, canon_field in column_map.items():
            val = row.get(src_col)
            if val not in (None, ""):
                data[canon_field] = str(val).strip()

        if not data:
            continue

        external_id = data.get("external_id") or data.get("sku") or f"row-{i}"
        sku = data.get("sku") or external_id
        description_raw = data.get("description_raw", "")

        weight = None
        if data.get("weight"):
            try:
                weight = float(str(data["weight"]).replace(",", "."))
            except ValueError:
                weight = None

        product = CanonicalProduct(
            external_id=str(external_id),
            sku=str(sku),
            description_raw=description_raw,
            barcode=data.get("barcode"),
            ncm=data.get("ncm"),
            cest=data.get("cest"),
            unit=data.get("unit"),
            brand=data.get("brand"),
            family=data.get("family"),
            department=data.get("department"),
            weight=weight,
            origin=data.get("origin"),
            status=RecordStatus.PARSED,
            source_file=path.name,
            import_batch_id=batch_id,
        )
        product.add_provenance(field="*", origin=f"arquivo:{path.name}", rule="ingest_excel")
        yield product
