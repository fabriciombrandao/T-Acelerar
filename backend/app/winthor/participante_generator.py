"""
Gerador de arquivo texto pra PCCLIENT/PCFORNEC — mesmo mecanismo do
PCPRODUT (generate_text_file, formato #/;-delimitado do DA.RPI.010),
reaproveitado sem alteração: ele já lê layout dinamicamente via
'fonte': 'core:X' / 'extra:X', só precisa de um layout diferente e um
dict de origem no formato certo.

Cobertura por fonte fiscal (SPED 0150 + XML emit/dest): identificação
(nome/razão social), CNPJ/CPF, IE, endereço completo (rua, número,
bairro, município, UF, CEP), telefone quando o XML trouxe. Cobre
~20 dos 64 campos do PCCLIENT e ~13 dos 25 do PCFORNEC — o resto é
dado comercial (vendedor, limite de crédito, forma de pagamento, praça)
que não existe em documento fiscal. Não implementado: módulo de
aderência pra esses campos comerciais (mesmo padrão do PCPRODUT, fica
pra quando for prioridade real) — hoje eles só geram aviso de campo
obrigatório ausente na hora de exportar, sem bloqueio prévio na
Exception Queue.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.canonical.models import CanonicalParticipante
from app.winthor.text_file_generator import (TextFileResult, generate_text_file,
                                              load_layout)

_MAPPINGS_DIR = Path(__file__).resolve().parents[3] / "mappings" / "winthor"
CLIENTE_LAYOUT_PATH = _MAPPINGS_DIR / "pccliente_layout.json"
FORNECEDOR_LAYOUT_PATH = _MAPPINGS_DIR / "pcfornec_layout.json"


def _tipo_pessoa(participante: CanonicalParticipante) -> str:
    """CNPJ -> J (jurídica), CPF -> F (física). Derivação real, não é
    campo de negócio — dado fiscal já diz isso sozinho."""
    if participante.cnpj:
        return "J"
    if participante.cpf:
        return "F"
    return ""


def _participante_to_dict(participante: CanonicalParticipante, codigo_sequencial: int,
                           codigo_field: str, tipo_field: str) -> dict:
    """Monta o dict no formato que generate_text_file espera: campos
    'core' no nível raiz, campos Winthor-específicos dentro de 'extra'."""
    extra = dict(participante.extra)
    extra[codigo_field] = codigo_sequencial
    extra[tipo_field] = _tipo_pessoa(participante)

    return {
        "external_id": participante.external_id,
        "nome": participante.nome,
        "cnpj": participante.cnpj,
        "cpf": participante.cpf,
        "ie": participante.ie,
        "cod_municipio": participante.cod_municipio,
        "municipio": participante.municipio,
        "uf": participante.uf,
        "cep": participante.cep,
        "fone": participante.fone,
        "endereco": participante.endereco,
        "numero": participante.numero,
        "bairro": participante.bairro,
        "extra": extra,
    }


def generate_pccliente_file(participantes: list[CanonicalParticipante],
                             separator: str | None = None) -> TextFileResult:
    """Só os participantes com papel 'cliente' — os outros são ignorados
    aqui (não é erro, um fornecedor puro não deveria virar linha de
    PCCLIENT)."""
    clientes = [p for p in participantes if "cliente" in p.tipo]
    layout = load_layout(CLIENTE_LAYOUT_PATH)
    dicts = [
        _participante_to_dict(p, codigo_sequencial=i, codigo_field="CODCLI", tipo_field="TIPOFJ")
        for i, p in enumerate(clientes, start=1)
    ]
    return generate_text_file(dicts, blocked_record_ids=set(), layout=layout,
                               separator=separator)


def generate_pcfornec_file(participantes: list[CanonicalParticipante],
                            separator: str | None = None) -> TextFileResult:
    fornecedores = [p for p in participantes if "fornecedor" in p.tipo]
    layout = load_layout(FORNECEDOR_LAYOUT_PATH)
    dicts = [
        _participante_to_dict(p, codigo_sequencial=i, codigo_field="CODFORNEC", tipo_field="TIPOPESSOA")
        for i, p in enumerate(fornecedores, start=1)
    ]
    return generate_text_file(dicts, blocked_record_ids=set(), layout=layout,
                               separator=separator)
