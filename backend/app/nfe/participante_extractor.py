"""
Extração de Cliente/Fornecedor a partir de XML de NF-e.

Nota de entrada (empresa é `dest`) -> o `emit` é FORNECEDOR.
Nota de saída (empresa é `emit`)    -> o `dest` é CLIENTE.

Mesmo CanonicalParticipante usado pela extração via SPED
(app/sped/participante_extractor.py) — os dois alimentam o mesmo
modelo, consolidação final por CNPJ/CPF funciona entre as duas fontes
sem tratamento especial (é só rodar as duas listas pela mesma função
de merge, que ainda não existe como módulo próprio — hoje cada fonte
devolve sua lista, consolidar as duas é responsabilidade de quem chama).
"""

from __future__ import annotations

import re

from app.canonical.models import CanonicalParticipante, RecordStatus
from app.nfe.parser import classify_direction, parse_nfe_xml


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def extract_participantes_from_nfe(
    paths: list, company_cnpj: str,
) -> list[CanonicalParticipante]:
    by_key: dict[str, CanonicalParticipante] = {}

    for path in paths:
        doc = parse_nfe_xml(path)
        direction = classify_direction(doc, company_cnpj)
        if direction is None:
            continue  # nota não envolve o CNPJ informado — ignora, não quebra

        other = doc["emit"] if direction == "entrada" else doc["dest"]
        tipo = "fornecedor" if direction == "entrada" else "cliente"

        cnpj = other.get("cnpj")
        cpf = other.get("cpf")
        key = _only_digits(cnpj) or _only_digits(cpf)
        if not key:
            continue  # sem documento identificável, não dá pra consolidar

        if key not in by_key:
            participante = CanonicalParticipante(
                external_id=key, nome=other.get("nome") or "",
                cnpj=cnpj, cpf=cpf, ie=other.get("ie"),
                cod_municipio=other.get("cod_municipio"),
                endereco=other.get("endereco"), numero=other.get("numero"),
                bairro=other.get("bairro"), status=RecordStatus.PARSED,
                source_file=doc["source_file"],
            )
            by_key[key] = participante

        by_key[key].tipo.add(tipo)
        by_key[key].add_provenance(
            field="*", origin=f"nfe:{doc['source_file']}",
            rule=f"det_direction:{direction}", confidence=1.0,
        )

    return list(by_key.values())
