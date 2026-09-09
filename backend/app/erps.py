"""
Registro central de ERPs suportados pelo T-Acelerar.

Um projeto escolhe o ERP na criação (não é escolha de instância/deploy —
ver decisão registrada no README, "Decisões de design e por quê").
Hoje só existe o conector Winthor; adicionar um novo ERP aqui é o primeiro
passo quando um segundo conector (ex: Protheus) for implementado de verdade.
"""

from __future__ import annotations

SUPPORTED_ERPS: dict[str, str] = {
    "winthor": "Winthor",
}


def is_supported_erp(erp_type: str) -> bool:
    return erp_type in SUPPORTED_ERPS
