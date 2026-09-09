"""
Extração de Produto a partir de XML de NF-e — o caso difícil (item de
transação, não cadastro pronto). Chave de consolidação MUDA conforme a
direção da nota, confirmado contra 20 XMLs reais (10 entrada + 10 saída
da mesma empresa):

- Nota de SAÍDA (empresa vendeu): `cProd` é o código da PRÓPRIA empresa
  — testado em 40 produtos distintos, 0 inconsistência de descrição
  entre notas diferentes. Chave de consolidação: cProd sozinho.
- Nota de ENTRADA (empresa comprou): `cProd` é o código do FORNECEDOR
  — testado, é estável DENTRO do mesmo fornecedor (mesmo código, mesma
  descrição, em notas de datas diferentes), mas dois fornecedores
  podem usar o mesmo número pra produtos diferentes. Chave de
  consolidação: (CNPJ do fornecedor, cProd), nunca cProd sozinho.

cEAN não é usado como chave primária aqui — no dataset real, boa parte
vem "SEM GTIN" (sem código de barras cadastrado pelo fornecedor). Fica
guardado em `extra` quando existir, pra eventual reconciliação manual,
mas a chave estável de verdade é a dupla acima.

Consolidar produto de fornecedores DIFERENTES que são o mesmo produto
físico (mesmo produto, dois fornecedores, potencialmente descrição
parecida) não é resolvido aqui — isso é o motor de dedup fuzzy que já
existe (app/dedup/dedup.py), rodado depois, não nesta extração.
"""

from __future__ import annotations

from app.canonical.models import CanonicalProduct, RecordStatus
from app.nfe.parser import classify_direction, parse_nfe_xml


def extract_produtos_from_nfe(paths: list, company_cnpj: str) -> list[CanonicalProduct]:
    by_key: dict[str, CanonicalProduct] = {}

    for path in paths:
        doc = parse_nfe_xml(path)
        direction = classify_direction(doc, company_cnpj)
        if direction is None:
            continue

        fornecedor_cnpj = doc["emit"].get("cnpj") if direction == "entrada" else None

        for item in doc["itens"]:
            cprod = item.get("cProd") or ""
            key = cprod if direction == "saida" else f"{fornecedor_cnpj}:{cprod}"

            if key not in by_key:
                product = CanonicalProduct(
                    external_id=key, sku=cprod,
                    description_raw=item.get("xProd") or "",
                    description=item.get("xProd") or "",
                    ncm=item.get("NCM"), cest=item.get("CEST"),
                    unit=item.get("uCom"), barcode=item.get("cEAN"),
                    status=RecordStatus.PARSED,
                    source_file=doc["source_file"],
                )
                if direction == "entrada":
                    product.extra["FORNECEDOR_CNPJ"] = fornecedor_cnpj
                    product.extra["FORNECEDOR_COD_PROD"] = cprod
                product.add_provenance(
                    field="*", origin=f"nfe:{doc['source_file']}",
                    rule=f"det_direction:{direction}", confidence=1.0,
                )
                by_key[key] = product

    return list(by_key.values())
