"""
Extração de Cliente/Fornecedor a partir de SPED Fiscal e/ou Contribuições.

Registro 0150 (Cadastro de Participante) dá o cadastro base — nome,
CNPJ/CPF, IE, endereço. Não diz se é cliente ou fornecedor: isso vem do
registro C100 (Documento Fiscal), campo IND_OPER (0=entrada, 1=saída),
cruzado com o COD_PART referenciado.

  IND_OPER=0 (entrada, empresa comprou) -> o participante é FORNECEDOR
  IND_OPER=1 (saída, empresa vendeu)    -> o participante é CLIENTE

Um mesmo participante pode aparecer como as duas coisas (compra E vende
pra mesma empresa) — `tipo` é um set, não campo único.

IMPORTANTE: COD_PART é numerado DENTRO de cada arquivo SPED — o mesmo
número pode representar participantes diferentes em arquivos diferentes
(ex: Fiscal ICMS/IPI e Contribuições PIS/COFINS são arquivos separados,
cada um com sua própria numeração). Por isso a consolidação final é por
CNPJ/CPF (chave real), nunca por COD_PART — e o mapa COD_PART->chave é
reiniciado a cada arquivo processado.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.canonical.models import CanonicalParticipante, RecordStatus
from app.sped.parser import parse_sped_records


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def extract_participantes_from_sped(
    paths: list[str | Path], source_label: str | None = None,
) -> list[CanonicalParticipante]:
    """Lê um ou mais arquivos SPED (ex: Fiscal ICMS/IPI + Contribuições
    PIS/COFINS do mesmo período/empresa) e devolve a lista consolidada de
    participantes, cada um já classificado como cliente e/ou fornecedor."""
    by_key: dict[str, CanonicalParticipante] = {}

    for path in paths:
        path = Path(path)
        records = parse_sped_records(path)
        cod_part_to_key: dict[str, str] = {}  # escopo: só este arquivo

        for campos in records.get("0150", []):
            campos = campos + [""] * (12 - len(campos))  # tolera linha curta
            cod_part, nome, _cod_pais, cnpj, cpf, ie, cod_mun, _suframa, \
                end, num, compl, bairro = campos[:12]

            cnpj = cnpj.strip() or None
            cpf = cpf.strip() or None
            key = _only_digits(cnpj or "") or _only_digits(cpf or "") or f"codpart:{cod_part}"
            cod_part_to_key[cod_part] = key

            if key not in by_key:
                participante = CanonicalParticipante(
                    external_id=key, nome=nome.strip(), cnpj=cnpj, cpf=cpf,
                    ie=ie.strip() or None, cod_municipio=cod_mun.strip() or None,
                    endereco=end.strip() or None, numero=num.strip() or None,
                    complemento=compl.strip() or None, bairro=bairro.strip() or None,
                    status=RecordStatus.PARSED,
                    source_file=source_label or path.name,
                )
                participante.add_provenance(
                    field="*", origin=f"sped:{path.name}", rule="registro_0150", confidence=1.0,
                )
                by_key[key] = participante

        for campos in records.get("C100", []):
            if len(campos) < 3:
                continue
            ind_oper, _ind_emit, cod_part = campos[0], campos[1], campos[2]
            key = cod_part_to_key.get(cod_part)
            if not key or key not in by_key:
                continue  # participante referenciado sem 0150 correspondente

            if ind_oper == "0":
                by_key[key].tipo.add("fornecedor")
            elif ind_oper == "1":
                by_key[key].tipo.add("cliente")

    return list(by_key.values())
