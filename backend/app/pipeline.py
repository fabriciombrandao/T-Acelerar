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


def run_pipeline_csv(input_path: str | Path, adherence_answers: dict | None = None,
                      extra_field_names: list[str] | None = None) -> PipelineResult:
    """
    adherence_answers: respostas do wizard de aderência do projeto
        ({module_id: bool}). Se None, pula a etapa de aderência inteira —
        usado pelo CLI standalone e por testes que não têm projeto/wizard.
        Se {} (wizard nunca preenchido), aplica módulos opcionais como
        "não aplicável" (default) mas ainda cobra os campos sempre-obrigatórios
        (cadastro básico, fiscal NCM) — ver app/winthor/adherence.py.
    extra_field_names: nomes de campo (ex: os 34 do PCPRODUT sem lugar no
        canônico) que a ingestão deve tentar capturar direto de colunas do
        arquivo de origem. Hoje sempre vem do módulo Winthor
        (extra_pcprodut_field_names()) — quando existir um segundo ERP,
        este é o ponto que precisa despachar por Project.erp_type.
    """
    # 1. Ingestão (RAW -> PARSED)
    products = list(ingest_csv(input_path, extra_field_names=extra_field_names))

    # 2. Saneamento (PARSED -> NORMALIZED)
    products = [normalize_product(p) for p in products]

    # 3. Auditoria/Validação (NORMALIZED -> VALIDATED | EXCEPTION)
    products, exceptions = validate_batch(products)

    # 4. Deduplicação (gera exceções adicionais, não altera status individual)
    dedup_exceptions = find_probable_duplicates(products)
    exceptions.extend(dedup_exceptions)

    # 5. Motor de aderência — aplica default de módulo não-aplicável,
    # bloqueia campo obrigatório de módulo aplicável ausente.
    if adherence_answers is not None:
        from app.winthor.adherence import apply_adherence  # import local: pipeline.py é
        # genérico hoje, mas a lógica de aderência já é Winthor-específica —
        # quando existir 2º ERP, despachar aqui por qual conector o projeto usa.
        adherence_exceptions = apply_adherence(products, adherence_answers)
        exceptions.extend(adherence_exceptions)

    # 6. Data Readiness Score
    report = quality_report(products, exceptions)

    return PipelineResult(products, exceptions, report)
