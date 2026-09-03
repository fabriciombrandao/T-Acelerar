"""
Profiling automático de colunas.

Gap identificado na revisão do documento original: "profiling automático" era citado
mas nunca especificado. Isto resolve a parte de inferência de mapeamento — dado um
header de arquivo desconhecido, sugere para qual campo canônico ele mapeia, com
confiança, em vez de exigir configuração manual fixa por cliente.

Ainda é determinístico (aliases + similaridade textual), não é IA. Ponto de extensão
documentado no final do arquivo para quando um classificador for plugado.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

# Aliases conhecidos por campo canônico. Cresce por cliente/vertical ao longo do uso.
FIELD_ALIASES: dict[str, list[str]] = {
    "external_id": ["codigo", "cod", "id", "codigo_produto", "cod_produto"],
    "sku": ["sku", "codigo_interno", "referencia", "ref"],
    "description_raw": ["descricao", "desc", "nome", "produto", "descricao_produto"],
    "barcode": ["ean", "codigo_barras", "gtin", "cod_barras"],
    "ncm": ["ncm", "codigo_ncm"],
    "cest": ["cest", "codigo_cest"],
    "unit": ["unidade", "un", "unid", "medida"],
    "brand": ["marca", "fabricante"],
    "family": ["familia", "categoria", "grupo"],
    "department": ["departamento", "setor", "secao"],
    "weight": ["peso", "peso_kg", "peso_liquido"],
    "origin": ["origem", "procedencia"],
}

SIMILARITY_THRESHOLD = 0.72


@dataclass
class ColumnSuggestion:
    source_column: str
    canonical_field: str | None
    confidence: float


def _norm(s: str) -> str:
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def suggest_column_map(headers: list[str]) -> tuple[dict[str, str], list[ColumnSuggestion]]:
    """Para cada header de origem, sugere o campo canônico mais provável.

    Retorna (column_map pronto para uso, lista de sugestões com confiança para
    auditoria/revisão humana quando a confiança for baixa).
    """
    suggestions: list[ColumnSuggestion] = []
    column_map: dict[str, str] = {}
    used_fields: set[str] = set()

    for header in headers:
        norm_header = _norm(header)
        best_field: str | None = None
        best_score = 0.0

        for field, aliases in FIELD_ALIASES.items():
            if field in used_fields:
                continue
            for alias in [field, *aliases]:
                score = SequenceMatcher(None, norm_header, alias).ratio()
                if norm_header == alias:
                    score = 1.0
                if score > best_score:
                    best_score = score
                    best_field = field

        if best_score >= SIMILARITY_THRESHOLD:
            column_map[norm_header] = best_field
            used_fields.add(best_field)
            suggestions.append(ColumnSuggestion(header, best_field, round(best_score, 3)))
        else:
            suggestions.append(ColumnSuggestion(header, None, round(best_score, 3)))

    return column_map, suggestions


def low_confidence_suggestions(suggestions: list[ColumnSuggestion],
                                threshold: float = 0.85) -> list[ColumnSuggestion]:
    """Sugestões que idealmente deveriam ir para revisão humana antes de confirmar o import."""
    return [s for s in suggestions if s.canonical_field and s.confidence < threshold]
