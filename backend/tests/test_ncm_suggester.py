import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.ai.ncm_suggester import _strip_markdown_fences, suggest_ncm


# ---------- Unidade: parsing e fallback, sem rede ----------

def test_strip_markdown_fences_removes_json_fence():
    text = '```json\n{"ncm": "12345678"}\n```'
    assert _strip_markdown_fences(text) == '{"ncm": "12345678"}'


def test_strip_markdown_fences_passes_through_plain_json():
    text = '{"ncm": "12345678"}'
    assert _strip_markdown_fences(text) == text


@pytest.mark.anyio
async def test_suggest_ncm_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = await suggest_ncm("ARROZ BRANCO TIPO 1 5KG")
    assert result is None


@pytest.mark.anyio
async def test_suggest_ncm_returns_none_for_empty_description(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-de-teste")
    result = await suggest_ncm("")
    assert result is None


@pytest.mark.anyio
async def test_suggest_ncm_parses_successful_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-de-teste")

    class _FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"content": [{"text": '{"ncm": "10063021", "justificativa": "arroz"}'}]}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _FakeResponse()

    import app.ai.ncm_suggester as mod
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    result = await suggest_ncm("ARROZ BRANCO TIPO 1 5KG")
    assert result == {"ncm": "10063021", "justificativa": "arroz"}


@pytest.mark.anyio
async def test_suggest_ncm_discards_malformed_ncm_from_ai(monkeypatch):
    """IA devolveu algo que não é NCM válido (formato errado) — não repassa
    lixo pra tela, vira None no campo ncm mas ainda devolve a justificativa."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-de-teste")

    class _FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"content": [{"text": '{"ncm": "123", "justificativa": "incerto"}'}]}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _FakeResponse()

    import app.ai.ncm_suggester as mod
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    result = await suggest_ncm("PRODUTO QUALQUER")
    assert result["ncm"] is None


@pytest.mark.anyio
async def test_suggest_ncm_returns_none_on_network_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-de-teste")

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): raise ConnectionError("timeout simulado")

    import app.ai.ncm_suggester as mod
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **kw: _FakeClient())

    result = await suggest_ncm("ARROZ BRANCO TIPO 1 5KG")
    assert result is None
