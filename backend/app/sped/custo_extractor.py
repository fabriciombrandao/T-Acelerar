"""
Extração de custo unitário — C170 (item de documento fiscal) não traz
valor unitário direto, só QTD e VL_ITEM (valor total da linha). Custo
unitário = VL_ITEM / QTD — validado contra XML real da mesma nota
(vUnCom do XML bateu exato com VL_ITEM/QTD do SPED em 11 itens
conferidos, incluindo casos com preço diferente por item).

Só conta transação de ENTRADA (compra) pra custo — venda dá preço de
venda, não custo. Um produto aparece em várias compras ao longo do
tempo, com preços diferentes; fica a mais RECENTE (data do documento,
C100/DT_DOC) — é a referência de custo que faz sentido pra cadastro de
produto, não uma média histórica.
"""

from __future__ import annotations

from pathlib import Path

from app.sped.parser import parse_sped_records_ordered


def _parse_valor_br(value: str) -> float | None:
    """SPED usa vírgula decimal ('87425,00') — sem separador de milhar."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _parse_data_sped(value: str) -> tuple[int, int, int] | None:
    """DT_DOC vem como DDMMAAAA (8 dígitos, sem separador)."""
    value = (value or "").strip()
    if len(value) != 8 or not value.isdigit():
        return None
    dia, mes, ano = int(value[0:2]), int(value[2:4]), int(value[4:8])
    return (ano, mes, dia)  # tupla ordenável (ano primeiro) pra "mais recente"


def extract_custo_unitario_from_sped(paths: list) -> dict[str, dict]:
    """Devolve {COD_ITEM: {'valor_unitario': float, 'data': (ano,mes,dia)}}
    — só a compra mais recente de cada item, entre todos os arquivos
    passados."""
    custos: dict[str, dict] = {}

    for path in paths:
        path = Path(path)
        registros = parse_sped_records_ordered(path)

        ind_oper_atual: str | None = None
        data_atual: tuple[int, int, int] | None = None

        for reg, campos in registros:
            if reg == "C100":
                if len(campos) < 9:
                    ind_oper_atual = None
                    data_atual = None
                    continue
                ind_oper_atual = campos[0]
                data_atual = _parse_data_sped(campos[8])  # DT_DOC
                continue

            if reg == "C170":
                if ind_oper_atual != "0":  # só entrada (compra) vira custo
                    continue
                if len(campos) < 6:
                    continue

                cod_item = campos[1].strip()
                qtd = _parse_valor_br(campos[3])
                vl_item = _parse_valor_br(campos[5])
                if not cod_item or not qtd or qtd == 0 or vl_item is None:
                    continue

                valor_unitario = round(vl_item / qtd, 4)
                existente = custos.get(cod_item)

                # Sem data confiável (C100 malformado) -> aceita só se
                # ainda não tiver nada pra esse item; nunca sobrescreve
                # um valor com data por um sem data.
                if existente is None:
                    custos[cod_item] = {"valor_unitario": valor_unitario, "data": data_atual}
                elif data_atual is not None and (
                    existente["data"] is None or data_atual > existente["data"]
                ):
                    custos[cod_item] = {"valor_unitario": valor_unitario, "data": data_atual}

    return custos
