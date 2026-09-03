"""
Deduplicação — detecta produtos semanticamente iguais com SKU/EAN diferentes.

MVP usa similaridade textual determinística (difflib). Isto é o "ponto de
ambiguidade" documentado no roadmap onde, depois, um classificador de IA
pode propor candidatos com confiança — mas a decisão final permanece
humana via Exception Queue.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from app.canonical.models import CanonicalProduct, ExceptionRecord

SIMILARITY_THRESHOLD = 0.90


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_probable_duplicates(products: list[CanonicalProduct]) -> list[ExceptionRecord]:
    """Compara descrições normalizadas par a par (O(n^2) — ok para MVP/lotes pequenos).

    Para lotes grandes, trocar por blocking (ex: por family/brand) + índice invertido
    antes de comparar.
    """
    exceptions: list[ExceptionRecord] = []
    n = len(products)

    for i in range(n):
        p1 = products[i]
        if not p1.description:
            continue
        for j in range(i + 1, n):
            p2 = products[j]
            if not p2.description or p1.sku == p2.sku:
                continue
            score = _similarity(p1.description, p2.description)
            if score >= SIMILARITY_THRESHOLD:
                exceptions.append(ExceptionRecord(
                    record_id=p1.external_id, entity="Product",
                    reason_code="PROVAVEL_DUPLICADO",
                    description=(
                        f"'{p1.description}' (SKU {p1.sku}) é {score:.0%} similar a "
                        f"'{p2.description}' (SKU {p2.sku})."
                    ),
                    severity="MEDIUM",
                    payload={"sku_a": p1.sku, "sku_b": p2.sku, "similarity": round(score, 4)},
                ))
    return exceptions
