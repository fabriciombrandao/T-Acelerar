"""
Processamento assíncrono de import — Celery.

Degradação graciosa deliberada:
  - TACELERAR_REDIS_URL não configurado (dev local, testes, CI) -> tasks
    rodam em modo "eager": síncronas, dentro do próprio processo, na hora
    em que são chamadas. Comportamento idêntico ao pipeline síncrono
    original — nenhum teste precisa saber que Celery existe.
  - TACELERAR_REDIS_URL configurado (VPS de produção) -> tasks são
    enfileiradas de verdade; um processo `celery worker` separado
    (serviço `worker` no docker-compose) as processa. A requisição HTTP
    de upload responde na hora (202/lote em PENDING), sem esperar o
    processamento terminar — essencial pra arquivo grande não estourar
    timeout de nginx/browser.

Sem isso, um import de 500 mil linhas travaria a requisição HTTP por
minutos (ou mais, dependendo do dedup) — inviável em produção.
"""

from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("TACELERAR_REDIS_URL")
EAGER_MODE = REDIS_URL is None

celery_app = Celery(
    "winthor",
    broker=REDIS_URL or "memory://",
    backend=REDIS_URL or "cache+memory://",
)
celery_app.conf.task_always_eager = EAGER_MODE
celery_app.conf.task_eager_propagates = True
celery_app.conf.worker_max_tasks_per_child = 50  # libera memória entre imports grandes


@celery_app.task(name="process_import", bind=True, max_retries=1)
def process_import_task(self, batch_id: str, file_paths: list, source_type: str = "csv") -> None:
    """Roda o pipeline completo e persiste o resultado. Chamado via
    .delay(...) — em modo eager, executa na hora; em modo real, um worker
    Celery separado pega da fila.

    file_paths é sempre uma lista (mesmo pra CSV, que só aceita 1 arquivo
    — mantém a assinatura uniforme pros 3 source_type). source_type
    decide qual pipeline roda: 'csv' -> só produto (run_pipeline_csv,
    original); 'sped'/'xml' -> produto E participante juntos (a mesma
    fonte fiscal dá as duas entidades de uma vez, não é escolha de
    ou-um-ou-outro)."""
    # Imports locais (não no topo do módulo) para não criar dependência
    # circular entre tasks.py <-> api.py <-> db.py no processo web.
    from app.db import ImportBatch, Project, get_session
    from app.pipeline import (run_participante_pipeline, run_pipeline_csv,
                               run_pipeline_multi_source)
    from app.repository import (finalize_multi_entity_result, mark_batch_failed,
                                 mark_batch_processing)
    from app.winthor.text_file_generator import extra_pcprodut_field_names

    session = get_session()
    try:
        mark_batch_processing(session, batch_id)

        batch = session.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        project = session.query(Project).filter(Project.id == batch.project_id).first()
        adherence_answers = (project.adherence_answers or {}) if project else {}
        company_cnpj = project.company_cnpj if project else None

        # Sempre Winthor por enquanto — quando existir um 2º ERP, despachar
        # por project.erp_type (ver comentário equivalente em pipeline.py).
        extra_fields = extra_pcprodut_field_names()

        if source_type == "csv":
            product_result = run_pipeline_csv(file_paths[0], adherence_answers=adherence_answers,
                                               extra_field_names=extra_fields)
            finalize_multi_entity_result(session, batch_id, product_result=product_result)

        elif source_type == "sped":
            product_result = run_pipeline_multi_source(
                sped_paths=file_paths, adherence_answers=adherence_answers,
                extra_field_names=extra_fields,
            )
            participante_result = run_participante_pipeline(sped_paths=file_paths)
            finalize_multi_entity_result(session, batch_id, product_result=product_result,
                                          participante_result=participante_result)

        elif source_type == "xml":
            product_result = run_pipeline_multi_source(
                xml_paths=file_paths, company_cnpj=company_cnpj,
                adherence_answers=adherence_answers, extra_field_names=extra_fields,
            )
            participante_result = run_participante_pipeline(xml_paths=file_paths,
                                                              company_cnpj=company_cnpj)
            finalize_multi_entity_result(session, batch_id, product_result=product_result,
                                          participante_result=participante_result)

        else:
            raise ValueError(f"source_type desconhecido: {source_type!r}")

    except Exception as exc:  # noqa: BLE001 — precisa capturar qualquer falha do pipeline
        mark_batch_failed(session, batch_id, str(exc))
        raise
    finally:
        session.close()
