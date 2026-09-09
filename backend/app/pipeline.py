"""
Pipeline — orquestra Ingestão -> Saneamento -> Deduplicação -> Auditoria/Validação
-> Exception Queue -> Data Readiness -> Dry Run.

Duas entradas hoje:
  run_pipeline_csv        — só CSV/Excel (comportamento original).
  run_pipeline_multi_source — CSV + SPED + XML combinados, consolidados
                              por EAN antes de entrar nos mesmos estágios
                              de saneamento/validação/dedup/aderência.

Participante (Cliente/Fornecedor) tem pipeline próprio, mais simples —
não passa por saneamento/dedup (não tem lógica pra isso ainda, CNPJ já
sendo chave exata reduz bastante a necessidade). Ver run_participante_pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.audit.logger import quality_report, write_audit_log
from app.canonical.models import CanonicalParticipante, CanonicalProduct, ExceptionRecord
from app.consolidation.consolidate import consolidate_participantes, consolidate_produtos
from app.dedup.dedup import find_probable_duplicates
from app.ingestion.ingest import ingest_csv
from app.normalization.rules import normalize_product
from app.validation.participante_rules import validate_participantes_batch
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


class ParticipanteResult:
    def __init__(self, participantes: list[CanonicalParticipante],
                 exceptions: list[ExceptionRecord]):
        self.participantes = participantes
        self.exceptions = exceptions


def _run_downstream_stages(products: list[CanonicalProduct],
                            adherence_answers: dict | None) -> PipelineResult:
    """Estágios compartilhados por qualquer fonte de produto (CSV, SPED,
    XML ou combinação): saneamento -> validação -> dedup -> aderência -> relatório."""
    products = [normalize_product(p) for p in products]
    products, exceptions = validate_batch(products)

    dedup_exceptions = find_probable_duplicates(products)
    exceptions.extend(dedup_exceptions)

    if adherence_answers is not None:
        from app.winthor.adherence import apply_adherence  # import local: pipeline.py é
        # genérico hoje, mas a lógica de aderência já é Winthor-específica —
        # quando existir 2º ERP, despachar aqui por qual conector o projeto usa.
        adherence_exceptions = apply_adherence(products, adherence_answers)
        exceptions.extend(adherence_exceptions)

    report = quality_report(products, exceptions)
    return PipelineResult(products, exceptions, report)


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
    products = list(ingest_csv(input_path, extra_field_names=extra_field_names))
    return _run_downstream_stages(products, adherence_answers)


def run_pipeline_multi_source(
    csv_path: str | Path | None = None,
    sped_paths: list | None = None,
    xml_paths: list | None = None,
    company_cnpj: str | None = None,
    adherence_answers: dict | None = None,
    extra_field_names: list[str] | None = None,
) -> PipelineResult:
    """Combina CSV + SPED + XML — pelo menos uma fonte precisa ser
    passada. company_cnpj é obrigatório se sped_paths ou xml_paths forem
    usados (precisa saber quem é a empresa pra classificar
    entrada/saída -> fornecedor/cliente, e produto por código próprio
    vs. código de fornecedor).

    Consolidação entre fontes só por EAN válido — ver
    app/consolidation/consolidate.py pro racional completo. Produto sem
    EAN de fontes diferentes fica separado; find_probable_duplicates
    (já rodado como estágio downstream) sinaliza como possível
    duplicata pra revisão humana, não funde sozinho.
    """
    sources: list[list[CanonicalProduct]] = []

    if csv_path is not None:
        sources.append(list(ingest_csv(csv_path, extra_field_names=extra_field_names)))

    if sped_paths:
        from app.sped.produto_extractor import extract_produtos_from_sped
        sources.append(extract_produtos_from_sped(sped_paths))

    if xml_paths:
        if not company_cnpj:
            raise ValueError("company_cnpj é obrigatório para extrair produto de XML de NF-e.")
        from app.nfe.produto_extractor import extract_produtos_from_nfe
        sources.append(extract_produtos_from_nfe(xml_paths, company_cnpj))

    if not sources:
        raise ValueError("Pelo menos uma fonte (csv_path, sped_paths ou xml_paths) é obrigatória.")

    products = consolidate_produtos(sources)
    return _run_downstream_stages(products, adherence_answers)


def run_participante_pipeline(
    sped_paths: list | None = None,
    xml_paths: list | None = None,
    company_cnpj: str | None = None,
) -> ParticipanteResult:
    """Extrai + consolida + valida Cliente/Fornecedor. Sem saneamento/dedup
    própria ainda — CNPJ/CPF já sendo chave exata reduz bastante a
    necessidade (ao contrário de produto, que não tem chave universal)."""
    sources: list[list[CanonicalParticipante]] = []

    if sped_paths:
        from app.sped.participante_extractor import extract_participantes_from_sped
        sources.append(extract_participantes_from_sped(sped_paths))

    if xml_paths:
        if not company_cnpj:
            raise ValueError("company_cnpj é obrigatório para extrair participante de XML de NF-e.")
        from app.nfe.participante_extractor import extract_participantes_from_nfe
        sources.append(extract_participantes_from_nfe(xml_paths, company_cnpj))

    if not sources:
        raise ValueError("Pelo menos uma fonte (sped_paths ou xml_paths) é obrigatória.")

    participantes = consolidate_participantes(sources)
    exceptions = validate_participantes_batch(participantes)
    return ParticipanteResult(participantes, exceptions)
