"""
Saneamento — regras determinísticas de normalização de descrição e unidade.

Princípio: IA sugere, regra decide. Este módulo é 100% determinístico
e auditável; qualquer sugestão de IA passaria por aqui como um "rule
candidate" antes de virar transformação aplicada.
"""

from __future__ import annotations

import re

from app.canonical.models import CanonicalProduct, RecordStatus

# Abreviações comuns observadas em cadastros legados -> forma padrão.
# Em produção isto vem de um dicionário curado por vertical/cliente.
ABBREVIATION_MAP = {
    r"\bLT\b": "L",
    r"\bLTS\b": "L",
    r"\bUNID\b": "UN",
    r"\bUNI\b": "UN",
    r"\bPCT\b": "PCT",
    r"\bCX\b": "CX",
    r"\bKG\b": "KG",
    r"\bGR\b": "G",
}

# Padronização de marcas grafadas de forma inconsistente.
BRAND_CANONICAL = {
    "COCA COLA": "COCA-COLA",
    "COCA-COLA": "COCA-COLA",
    "COCACOLA": "COCA-COLA",
}

UNIT_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s?(ML|L|KG|G|UN)\b", re.IGNORECASE)


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_description(raw: str) -> tuple[str, list[str]]:
    """Retorna (descrição normalizada, lista de regras aplicadas)."""
    applied: list[str] = []
    text = raw.upper()
    text = _collapse_spaces(text)
    if text != raw.upper().strip():
        applied.append("collapse_spaces")

    for brand_variant, brand_std in BRAND_CANONICAL.items():
        if brand_variant in text and brand_variant != brand_std:
            text = text.replace(brand_variant, brand_std)
            applied.append(f"brand_std:{brand_std}")

    for pattern, replacement in ABBREVIATION_MAP.items():
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            applied.append(f"abbrev:{pattern.strip(chr(92)+'b')}->{replacement}")
            text = new_text

    # normaliza "2 L" -> "2L" (sem espaço entre número e unidade de volume/peso)
    text = re.sub(r"(\d+(?:[.,]\d+)?)\s+(ML|L|KG|G)\b", r"\1\2", text)
    text = _collapse_spaces(text)

    return text, applied


def extract_unit(description: str) -> str | None:
    match = UNIT_PATTERN.search(description)
    if match:
        return match.group(2).upper()
    return None


def normalize_product(product: CanonicalProduct) -> CanonicalProduct:
    """Aplica saneamento determinístico e registra proveniência de cada mudança."""
    normalized, rules_applied = normalize_description(product.description_raw)
    product.description = normalized
    for rule in rules_applied:
        product.add_provenance(
            field="description", origin="regra_saneamento", rule=rule, confidence=1.0
        )

    if not product.unit:
        inferred_unit = extract_unit(normalized)
        if inferred_unit:
            product.unit = inferred_unit
            product.add_provenance(
                field="unit", origin="inferido_da_descricao",
                rule="extract_unit", confidence=0.9,
                evidence=normalized,
            )

    product.status = RecordStatus.NORMALIZED
    return product
