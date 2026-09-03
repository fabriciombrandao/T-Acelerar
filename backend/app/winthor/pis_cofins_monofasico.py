"""
Derivação automática de PISCOFINSRETIDO a partir do NCM.

Decisão de arquitetura (não é pergunta de wizard): monofasia/retenção de
PIS-COFINS é determinada por lei conforme o produto (NCM), não por processo
de negócio do cliente. Perguntar isso no wizard de aderência estaria errado
— o cliente não "escolhe" ter ou não esse regime, o produto que ele vende
já carrega essa característica.

ATENÇÃO: lista abaixo é uma AMOSTRA ilustrativa de categorias classicamente
monofásicas (combustíveis, bebidas frias, cigarros, alguns cosméticos e
autopeças). NÃO é exaustiva nem substitui parametrização fiscal validada
por um contador/tributarista antes de ir para produção. Ver TODO abaixo.
"""

from __future__ import annotations

# Prefixos de NCM (posição/subposição) classicamente monofásicos/com
# regime especial de PIS/COFINS. Checagem por prefixo (startswith).
MONOFASICO_NCM_PREFIXES: list[str] = [
    "2710",   # combustíveis derivados de petróleo
    "2203",   # cervejas
    "2202",   # refrigerantes e águas
    "2402",   # cigarros
    "3303",   # perfumes
    "3304",   # cosméticos/maquiagem
    "3305",   # produtos capilares
    "3306",   # higiene bucal
    "3401",   # sabões
    "8407", "8408",  # motores (autopeças — regime especial em alguns casos)
    "4011",   # pneus
]


def is_monofasico(ncm: str | None) -> bool:
    if not ncm:
        return False
    digits = "".join(ch for ch in ncm if ch.isdigit())
    return any(digits.startswith(prefix) for prefix in MONOFASICO_NCM_PREFIXES)


def derive_pis_cofins_retido(ncm: str | None) -> str:
    """Retorna 'S' ou 'N' para o campo PISCOFINSRETIDO."""
    return "S" if is_monofasico(ncm) else "N"


# TODO(fiscal): substituir esta lista por integração com uma base fiscal
# validada (ex: tabela de tributação do próprio TOTVS/rotina 580 mencionada
# no documento DA.RPI.010) antes de usar em produção. Este módulo existe
# para não obrigar o consultor a perguntar isso no wizard — não para ser
# fonte de verdade fiscal definitiva.
