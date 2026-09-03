"""
Pipeline — orquestra Ingestão -> Saneamento -> Deduplicação -> Auditoria/Validação
-> Exception Queue -> Data Readiness -> Dry Run.

Corresponde ao "Piloto Recomendado" (Produtos + Fiscal Evidence) do documento,
sem a camada fiscal (SPED/XML) ainda — ponto de extensão futura.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.audit.logger import quality_report, write_audit_log
from app.canonical.models import CanonicalProduct, ExceptionRecord
from app.dedup.dedup import find_probable_duplicates
from app.ingestion.ingest import ingest_csv
from app.normalization.rules import normalize_product
from app.validation.rules import validate_batch


class PipelineResult:
    def __init__(self, products: list[CanonicalProduct], exceptions: list[ExceptionRecord],
                 report: dict):
        self.products = products
        self.exceptions = exceptions
        self.report = report

    def save(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        with (output_dir / "cadastro_canonico.json").open("w", encoding="utf-8") as f:
            json.dump([p.model_dump(mode="json") for p in self.products], f,
                       ensure_ascii=False, indent=2)

        with (output_dir / "excecoes.json").open("w", encoding="utf-8") as f:
            json.dump([e.model_dump(mode="json") for e in self.exceptions], f,
                       ensure_ascii=False, indent=2)

        write_audit_log(self.products, output_dir / "audit_log.jsonl")

        with (output_dir / "relatorio_qualidade.json").open("w", encoding="utf-8") as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2)


def run_pipeline_csv(input_path: str | Path) -> PipelineResult:
    # 1. Ingestão (RAW -> PARSED)
    products = list(ingest_csv(input_path))

    # 2. Saneamento (PARSED -> NORMALIZED)
    products = [normalize_product(p) for p in products]

    # 3. Auditoria/Validação (NORMALIZED -> VALIDATED | EXCEPTION)
    products, exceptions = validate_batch(products)

    # 4. Deduplicação (gera exceções adicionais, não altera status individual)
    dedup_exceptions = find_probable_duplicates(products)
    exceptions.extend(dedup_exceptions)

    # 5. Data Readiness Score
    report = quality_report(products, exceptions)

    return PipelineResult(products, exceptions, report)
