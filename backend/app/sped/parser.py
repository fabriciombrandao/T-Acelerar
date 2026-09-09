"""
Parser de arquivo SPED — genérico, não é específico do Winthor. SPED é
padrão do governo (Receita Federal), reutilizável por qualquer conector
de ERP que precise extrair dado fiscal — a parte Winthor-específica é só
o MAPEAMENTO de registro SPED pra campo PCCLIENT/PCFORNEC/PCPRODUT
(ver app/winthor/), não este parser.

Formato: texto delimitado por '|', uma linha por registro, cada linha
começa e termina com '|'. Encoding é ISO-8859-1/Latin-1 (padrão SPED,
confirmado contra arquivo real de referência — nunca UTF-8).
"""

from __future__ import annotations

from pathlib import Path


def parse_sped_records(path: str | Path) -> dict[str, list[list[str]]]:
    """Lê um arquivo SPED e agrupa os campos de cada linha por tipo de
    registro (REG). Cada valor é a lista de campos daquela linha, SEM o
    próprio REG (já usado como chave) e sem os '|' vazios do início/fim.

    Ex: linha "|0150|123|FULANO LTDA|...|" com REG=0150 vira uma entrada
    em records["0150"] = ["123", "FULANO LTDA", ...].
    """
    records: dict[str, list[list[str]]] = {}
    path = Path(path)

    with path.open(encoding="iso-8859-1", newline="") as f:
        for line in f:
            line = line.strip("\r\n")
            if not line:
                continue
            fields = line.split("|")
            # Linha bem formada começa e termina com '|', gerando string
            # vazia como primeiro e último elemento do split — descarta.
            if fields and fields[0] == "":
                fields = fields[1:]
            if fields and fields[-1] == "":
                fields = fields[:-1]
            if not fields:
                continue

            reg = fields[0]
            campos = fields[1:]
            records.setdefault(reg, []).append(campos)

    return records
