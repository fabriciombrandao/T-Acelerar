"""
Parser de XML de NF-e — genérico, não é específico do Winthor. Layout
público SEFAZ (versão 4.00), confirmado contra 10 XMLs reais de entrada
(compra) antes de escrever qualquer campo — mesma disciplina usada com
SPED e com o manual Winthor.

Achados reais que moldam o design:
- cEAN frequentemente vem "SEM GTIN" (literal) — nem todo fornecedor
  cadastra código de barras. Não dá pra depender de EAN como chave.
- cProd É estável dentro do MESMO fornecedor entre notas diferentes
  (mesmo produto, mesmo código, em 4 notas de datas diferentes) — mas o
  código não é único GLOBALMENTE (fornecedores diferentes podem usar o
  mesmo número pra produtos diferentes). Chave de consolidação correta
  pra produto de nota de entrada é (CNPJ do fornecedor, cProd), não
  cProd sozinho.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def _text(node, path: str) -> str | None:
    el = node.find(path, NS)
    return el.text.strip() if el is not None and el.text else None


def parse_nfe_xml(path: str | Path) -> dict:
    """Extrai emit, dest e itens de um XML de NF-e (aceita nfeProc ou NFe
    puro — ambos têm infNFe em algum nível)."""
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()
    inf = root.find(".//nfe:infNFe", NS)
    if inf is None:
        raise ValueError(f"XML sem infNFe reconhecível: {path.name}")

    emit_node = inf.find("nfe:emit", NS)
    dest_node = inf.find("nfe:dest", NS)

    emit = {
        "cnpj": _text(emit_node, "nfe:CNPJ"),
        "cpf": _text(emit_node, "nfe:CPF"),
        "nome": _text(emit_node, "nfe:xNome"),
        "endereco": _text(emit_node, "nfe:enderEmit/nfe:xLgr"),
        "numero": _text(emit_node, "nfe:enderEmit/nfe:nro"),
        "bairro": _text(emit_node, "nfe:enderEmit/nfe:xBairro"),
        "cod_municipio": _text(emit_node, "nfe:enderEmit/nfe:cMun"),
        "ie": _text(emit_node, "nfe:IE"),
    } if emit_node is not None else {}

    dest = {
        "cnpj": _text(dest_node, "nfe:CNPJ"),
        "cpf": _text(dest_node, "nfe:CPF"),
        "nome": _text(dest_node, "nfe:xNome"),
        "endereco": _text(dest_node, "nfe:enderDest/nfe:xLgr"),
        "numero": _text(dest_node, "nfe:enderDest/nfe:nro"),
        "bairro": _text(dest_node, "nfe:enderDest/nfe:xBairro"),
        "cod_municipio": _text(dest_node, "nfe:enderDest/nfe:cMun"),
        "ie": _text(dest_node, "nfe:IE"),
    } if dest_node is not None else {}

    itens = []
    for det in inf.findall("nfe:det", NS):
        prod = det.find("nfe:prod", NS)
        if prod is None:
            continue
        cean = _text(prod, "nfe:cEAN")
        itens.append({
            "cProd": _text(prod, "nfe:cProd"),
            "cEAN": None if cean == "SEM GTIN" else cean,
            "xProd": _text(prod, "nfe:xProd"),
            "NCM": _text(prod, "nfe:NCM"),
            "CEST": _text(prod, "nfe:CEST"),
            "CFOP": _text(prod, "nfe:CFOP"),
            "uCom": _text(prod, "nfe:uCom"),
            "qCom": _text(prod, "nfe:qCom"),
            "vUnCom": _text(prod, "nfe:vUnCom"),
            "vProd": _text(prod, "nfe:vProd"),
        })

    return {"emit": emit, "dest": dest, "itens": itens, "source_file": path.name}


def classify_direction(doc: dict, company_cnpj: str) -> str | None:
    """'entrada' se a empresa é destinatária (comprou), 'saida' se é
    emitente (vendeu). None se a nota não envolve o CNPJ informado
    (não deveria acontecer num lote bem separado, mas não derruba o
    processamento — vira um caso pra revisão manual, não um crash)."""
    company_digits = re.sub(r"\D", "", company_cnpj or "")
    emit_cnpj = re.sub(r"\D", "", doc["emit"].get("cnpj") or "")
    dest_cnpj = re.sub(r"\D", "", doc["dest"].get("cnpj") or "")

    if dest_cnpj == company_digits:
        return "entrada"
    if emit_cnpj == company_digits:
        return "saida"
    return None
