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
def process_import_task(self, batch_id: str, file_path: str) -> None:
    """Roda o pipeline completo e persiste o resultado. Chamado via
    .delay(...) — em modo eager, executa na hora; em modo real, um worker
    Celery separado pega da fila."""
    # Imports locais (não no topo do módulo) para não criar dependência
    # circular entre tasks.py <-> api.py <-> db.py no processo web.
    from app.db import get_session
    from app.pipeline import run_pipeline_csv
    from app.repository import (finalize_pipeline_result, mark_batch_failed,
                                 mark_batch_processing)

    session = get_session()
    try:
        mark_batch_processing(session, batch_id)
        result = run_pipeline_csv(file_path)
        finalize_pipeline_result(session, batch_id, result)
    except Exception as exc:  # noqa: BLE001 — precisa capturar qualquer falha do pipeline
        mark_batch_failed(session, batch_id, str(exc))
        raise
    finally:
        session.close()
