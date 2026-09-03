"""
Winthor Adapter — Oracle SQL generator.

O Winthor não expõe API. A carga é feita rodando um script de INSERT
diretamente no banco Oracle do cliente. Este módulo faz exatamente o
"MAPPING WINTHOR" + parte de "CARGA" do pipeline conceitual do documento,
trocando "chamada de API" por "geração de arquivo .sql".

Guardrails aplicados aqui (seção 30 do documento original):
- Nenhum registro com exceção BLOCKER pendente entra no script (Dry Run obrigatório).
- Todo valor de texto é escapado para Oracle (aspas simples duplicadas).
- Truncamento silencioso de campo é tratado como warning, não como corte mudo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[3] / "mappings" / "winthor" / "produto.json"


@dataclass
class GenerationWarning:
    record_id: str
    column: str
    message: str


@dataclass
class ScriptResult:
    sql: str
    records_included: int
    records_skipped: list[str] = field(default_factory=list)
    warnings: list[GenerationWarning] = field(default_factory=list)


def load_mapping(path: str | Path = DEFAULT_MAPPING_PATH) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def _oracle_escape_string(value: str) -> str:
    return value.replace("'", "''")


def _format_value(value, col_type: str, max_length: int | None,
                   record_id: str, column: str,
                   warnings: list[GenerationWarning]) -> str:
    if value is None or value == "":
        return "NULL"

    if col_type == "number":
        try:
            return str(float(value)) if isinstance(value, str) else str(value)
        except (TypeError, ValueError):
            warnings.append(GenerationWarning(
                record_id, column, f"Valor '{value}' não numérico; gravado como NULL."
            ))
            return "NULL"

    text = str(value)
    if max_length and len(text) > max_length:
        warnings.append(GenerationWarning(
            record_id, column,
            f"Valor truncado de {len(text)} para {max_length} caracteres: '{text}'",
        ))
        text = text[:max_length]

    return f"'{_oracle_escape_string(text)}'"


def generate_insert_script(products: list[dict], blocked_record_ids: set[str],
                            mapping: dict | None = None,
                            batch_id: str | None = None) -> ScriptResult:
    """Gera o script de INSERT Oracle.

    `products` é uma lista de dicts com os campos canônicos (ex: vindos de
    ProductRecord convertido). `blocked_record_ids` são external_ids com
    exceção BLOCKER ainda PENDING — ficam de fora do script.
    """
    mapping = mapping or load_mapping()
    table = mapping["table"]
    columns_cfg = mapping["columns"]
    fixed_columns = mapping.get("fixed_columns", {})

    column_names = [c["column"] for c in columns_cfg] + list(fixed_columns.keys())
    warnings: list[GenerationWarning] = []
    skipped: list[str] = []

    lines: list[str] = [
        f"-- Winthor Data Deploy — script de carga gerado em "
        f"{datetime.now(timezone.utc).isoformat()}",
        f"-- Lote: {batch_id or 'N/A'} | Tabela destino: {table}",
        "-- ATENÇÃO: mapping ainda não validado contra dicionário oficial Winthor.",
        "",
    ]

    included = 0
    for p in products:
        record_id = p.get("external_id", "")
        if record_id in blocked_record_ids:
            skipped.append(record_id)
            continue

        values = []
        for col in columns_cfg:
            raw_value = p.get(col["canonical"])
            if not col.get("nullable", True) and (raw_value is None or raw_value == ""):
                warnings.append(GenerationWarning(
                    record_id, col["column"],
                    "Campo obrigatório vazio — registro deveria ter sido bloqueado na validação.",
                ))
            values.append(_format_value(
                raw_value, col["type"], col.get("max_length"),
                record_id, col["column"], warnings,
            ))

        values.extend(fixed_columns.values())

        lines.append(
            f"INSERT INTO {table} ({', '.join(column_names)}) "
            f"VALUES ({', '.join(values)});"
        )
        included += 1

    lines.append("")
    lines.append("COMMIT;")

    return ScriptResult(
        sql="\n".join(lines),
        records_included=included,
        records_skipped=skipped,
        warnings=warnings,
    )
