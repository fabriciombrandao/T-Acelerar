"""
Audit Log — grava, em JSONL, cada transformação aplicada a cada registro.

Isto é o que sustenta a promessa de "rastreabilidade total" do documento:
qualquer alteração de dado deve poder ser explicada (regra + evidência + confiança).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.canonical.models import CanonicalProduct


def write_audit_log(products: list[CanonicalProduct], path: str | Path) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        for p in products:
            for prov in p.provenance:
                entry = {
                    "record_id": p.external_id,
                    "sku": p.sku,
                    "field": prov.field,
                    "origin": prov.origin,
                    "rule": prov.rule,
                    "confidence": prov.confidence,
                    "evidence": prov.evidence,
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def quality_report(products: list[CanonicalProduct], exceptions: list) -> dict:
    total = len(products)
    with_exception = len({e.record_id for e in exceptions})
    blocker = sum(1 for e in exceptions if e.severity == "BLOCKER")

    return {
        "total_registros": total,
        "registros_com_excecao": with_exception,
        "exception_rate": round(with_exception / total, 4) if total else 0,
        "excecoes_bloqueantes": blocker,
        "data_readiness_score": round(1 - (with_exception / total), 4) if total else 0,
        "total_excecoes": len(exceptions),
        "excecoes_por_tipo": _count_by(exceptions, "reason_code"),
        "excecoes_por_severidade": _count_by(exceptions, "severity"),
    }


def _count_by(exceptions: list, attr: str) -> dict:
    counts: dict[str, int] = {}
    for e in exceptions:
        key = getattr(e, attr)
        counts[key] = counts.get(key, 0) + 1
    return counts
