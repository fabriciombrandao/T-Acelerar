"""
Winthor Adapter — arquivo texto delimitado (formato oficial de migração).

Segunda opção de exportação, ao lado de oracle_generator.py (INSERT SQL).
Este é o formato que o documento DA.RPI.010 realmente descreve: campos
separados por # ou ;, separador também no fim da linha, sem padding de
espaço, sem zero à esquerda, datas DD/MM/YYYY, decimal com ponto.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

DEFAULT_LAYOUT_PATH = Path(__file__).resolve().parents[3] / "mappings" / "winthor" / "pcprodut_layout.json"


@dataclass
class GenerationWarning:
    record_id: str
    column: str
    message: str


@dataclass
class TextFileResult:
    content: str
    records_included: int
    records_skipped: list[str] = field(default_factory=list)
    warnings: list[GenerationWarning] = field(default_factory=list)


def load_layout(path: str | Path = DEFAULT_LAYOUT_PATH) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def _resolve_value(product: dict, field_cfg: dict):
    """Lê o valor pela 'fonte' declarada no layout (core:<campo> ou extra:<campo>),
    com fallback_fonte quando o valor primário está vazio."""
    def _read(source: str):
        kind, name = source.split(":", 1)
        if kind == "core":
            return product.get(name)
        return (product.get("extra") or {}).get(name)

    value = _read(field_cfg["fonte"])
    if (value is None or value == "") and field_cfg.get("fallback_fonte"):
        value = _read(field_cfg["fallback_fonte"])
    return value


def _format_number(value, decimais: int, record_id: str, field_name: str,
                    warnings: list[GenerationWarning]) -> str:
    if value is None or value == "":
        return ""
    try:
        num = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        warnings.append(GenerationWarning(
            record_id, field_name, f"Valor '{value}' não numérico; gravado vazio."
        ))
        return ""

    if decimais == 0:
        return str(int(round(num)))
    # Formato 9999.99 — ponto decimal, sem zero à esquerda no inteiro,
    # sem padding artificial de casas além do necessário para o valor.
    return f"{num:.{decimais}f}"


def _format_date(value, field_name: str, record_id: str,
                  warnings: list[GenerationWarning]) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    warnings.append(GenerationWarning(
        record_id, field_name, f"Data '{value}' em formato não reconhecido; gravada vazia."
    ))
    return ""


def _format_string(value, max_length: int | None, field_name: str,
                    record_id: str, warnings: list[GenerationWarning]) -> str:
    if value is None:
        return ""
    text = str(value)  # sem strip: layout proíbe padding, mas conteúdo real não é alterado
    if max_length and len(text) > max_length:
        warnings.append(GenerationWarning(
            record_id, field_name,
            f"Valor truncado de {len(text)} para {max_length} caracteres: '{text}'",
        ))
        text = text[:max_length]
    return text


def generate_text_file(products: list[dict], blocked_record_ids: set[str],
                        layout: dict | None = None, separator: str | None = None) -> TextFileResult:
    """Gera o arquivo texto delimitado para PCPRODUT.

    `products` é uma lista de dicts com os campos "core" (external_id, sku,
    description, unit, barcode, ncm, weight, department, ...) e um sub-dict
    `extra` com os campos Winthor-específicos (CODSEC, LASTROPAL, etc.),
    já resolvidos pelo motor de aderência (app/winthor/adherence.py) antes
    de chegar aqui — este módulo só formata, não decide default nem bloqueio.
    """
    layout = layout or load_layout()
    sep = separator or layout.get("separador_padrao", "#")
    fields_cfg = layout["campos"]

    warnings: list[GenerationWarning] = []
    skipped: list[str] = []
    lines: list[str] = []

    for p in products:
        record_id = p.get("external_id", "")
        if record_id in blocked_record_ids:
            skipped.append(record_id)
            continue

        rendered_fields = []
        for cfg in fields_cfg:
            raw_value = _resolve_value(p, cfg)

            if cfg.get("required") and (raw_value is None or raw_value == ""):
                warnings.append(GenerationWarning(
                    record_id, cfg["field"],
                    "Campo obrigatório vazio no momento da geração — deveria ter sido "
                    "bloqueado antes (Exception Queue / motor de aderência).",
                ))

            if cfg["tipo"] == "NUMBER":
                rendered = _format_number(raw_value, cfg.get("decimais", 0),
                                           record_id, cfg["field"], warnings)
            elif cfg["tipo"] == "DATE":
                rendered = _format_date(raw_value, cfg["field"], record_id, warnings)
            else:  # VARCHAR2
                rendered = _format_string(raw_value, cfg.get("tamanho"),
                                           cfg["field"], record_id, warnings)

            rendered_fields.append(rendered)

        # Separador entre campos E no final da linha (exigência do documento).
        line = sep.join(rendered_fields) + sep
        lines.append(line)

    return TextFileResult(
        content="\n".join(lines),
        records_included=len(lines),
        records_skipped=skipped,
        warnings=warnings,
    )
