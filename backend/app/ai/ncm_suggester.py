"""
Sugestão de NCM por IA — mesmo padrão de chamada já usado no TNORTEANDO:
model claude-haiku-4-5-20251001, httpx.AsyncClient cru (sem SDK), header
anthropic-version 2023-06-01, timeout de 5s, fallback silencioso (nunca
levanta exceção pro chamador — se a IA falhar, a tela mostra 'sem
sugestão', não quebra o fluxo de correção manual que já existe).

IMPORTANTE: isso é só SUGESTÃO. Nunca aplica o NCM sozinho — quem decide
é sempre o humano, via o mesmo endpoint de correção manual que já existe
(PATCH .../products/{id}). NCM tem implicação fiscal/legal real; uma IA
errando aqui tem custo de verdade, não é só cosmético.
"""

from __future__ import annotations

import json
import os

import httpx

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
MODEL = "claude-haiku-4-5-20251001"

_PROMPT_TEMPLATE = """Você é especialista em classificação fiscal NCM (Nomenclatura Comum \
do Mercosul) para produtos brasileiros.

Produto: "{description}"

Responda APENAS com um objeto JSON, sem markdown, sem texto antes ou depois:
{{"ncm": "12345678", "justificativa": "explicação breve"}}

Se não conseguir determinar com confiança razoável, responda:
{{"ncm": null, "justificativa": "motivo de não conseguir determinar"}}

O campo ncm, quando preenchido, precisa ter exatamente 8 dígitos numéricos."""


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


async def suggest_ncm(description: str) -> dict | None:
    """Devolve {'ncm': str|None, 'justificativa': str} ou None se a IA
    não estiver disponível (sem chave configurada, erro de rede, timeout,
    resposta não-parseável). None é o sinal de 'sem sugestão agora',
    não é erro pro chamador tratar como exceção."""
    api_key = os.environ.get(ANTHROPIC_API_KEY_ENV)
    if not api_key or not description:
        return None

    prompt = _PROMPT_TEMPLATE.format(description=description[:300])

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MODEL,
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
            parsed = json.loads(_strip_markdown_fences(text))

            ncm = parsed.get("ncm")
            if ncm is not None and (not isinstance(ncm, str) or not ncm.isdigit() or len(ncm) != 8):
                ncm = None  # a IA "alucinou" um formato errado — não repassa lixo

            return {"ncm": ncm, "justificativa": parsed.get("justificativa", "")}
    except Exception:
        return None  # silencioso de propósito — ver docstring do módulo
