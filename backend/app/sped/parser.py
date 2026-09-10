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
    for reg, campos in parse_sped_records_ordered(path):
        records.setdefault(reg, []).append(campos)
    return records


def parse_sped_records_ordered(path: str | Path) -> list[tuple[str, list[str]]]:
    """Igual a parse_sped_records, mas preserva a ORDEM original do arquivo
    em vez de agrupar por tipo. Necessário quando o significado de um
    registro depende do registro "pai" que veio antes dele no arquivo —
    ex: C170 (item de documento fiscal) só faz sentido junto do C100
    (documento fiscal) mais recente que o precede, que diz se é
    entrada/saída e a data. parse_sped_records() perde essa relação
    (agrupa tudo por tipo), esta função não."""
    path = Path(path)
    registros: list[tuple[str, list[str]]] = []

    with path.open(encoding="iso-8859-1", newline="") as f:
        for line in f:
            line = line.strip("\r\n")
            if not line:
                continue
            fields = line.split("|")
            if fields and fields[0] == "":
                fields = fields[1:]
            if fields and fields[-1] == "":
                fields = fields[:-1]
            if not fields:
                continue

            reg = fields[0]
            campos = fields[1:]
            registros.append((reg, campos))

    return registros
