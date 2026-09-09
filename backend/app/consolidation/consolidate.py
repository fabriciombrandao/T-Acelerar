"""
Consolidação multi-fonte — funde Participante/Produto vindos de CSV +
SPED + XML num catálogo só.

Regra central (deliberada, não é detalhe de implementação):

  PARTICIPANTE funde automático por CNPJ/CPF — é chave exata, universal,
  com dígito verificador. Duas fontes trazendo o mesmo CNPJ são,
  garantidamente, a mesma empresa/pessoa.

  PRODUTO só funde automático por EAN válido — quando não tem EAN (ou o
  EAN não bate dígito verificador), os registros ficam SEPARADOS. Não
  existe chave universal de produto entre fontes diferentes (código de
  fornecedor, código de SPED, código de CSV do cliente são numerações
  independentes). Fundir por descrição parecida seria uma decisão de
  negócio, não um fato — por isso vira candidato pro motor de dedup
  fuzzy já existente (Exception Queue), nunca fusão silenciosa.
"""

from __future__ import annotations

import re

from app.canonical.models import CanonicalParticipante, CanonicalProduct
from app.validation.rules import validate_ean13


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def consolidate_participantes(
    sources: list[list[CanonicalParticipante]],
) -> list[CanonicalParticipante]:
    """Funde por CNPJ/CPF exato. Campo vazio num registro é preenchido
    pelo valor da outra fonte se existir; papéis (tipo) se somam."""
    by_key: dict[str, CanonicalParticipante] = {}

    for source_list in sources:
        for p in source_list:
            key = _only_digits(p.cnpj) or _only_digits(p.cpf) or p.external_id
            if key not in by_key:
                by_key[key] = p
                continue

            existing = by_key[key]
            existing.tipo |= p.tipo
            existing.provenance.extend(p.provenance)
            for field in ("nome", "ie", "cod_municipio", "endereco",
                          "numero", "complemento", "bairro"):
                if not getattr(existing, field) and getattr(p, field):
                    setattr(existing, field, getattr(p, field))

    return list(by_key.values())


def consolidate_produtos(sources: list[list[CanonicalProduct]]) -> list[CanonicalProduct]:
    """Funde só por EAN válido. Sem EAN (ou EAN inválido) = registro
    separado — fica pro dedup fuzzy (app/dedup/dedup.py) sinalizar como
    possível duplicata, não é fundido aqui."""
    by_ean: dict[str, CanonicalProduct] = {}
    sem_ean_confiavel: list[CanonicalProduct] = []

    for source_list in sources:
        for p in source_list:
            if p.barcode and validate_ean13(p.barcode):
                key = p.barcode
                if key not in by_ean:
                    by_ean[key] = p
                else:
                    existing = by_ean[key]
                    existing.provenance.extend(p.provenance)
                    for field in ("description", "ncm", "cest", "unit", "weight"):
                        if not getattr(existing, field) and getattr(p, field):
                            setattr(existing, field, getattr(p, field))
            else:
                sem_ean_confiavel.append(p)

    return list(by_ean.values()) + sem_ean_confiavel
