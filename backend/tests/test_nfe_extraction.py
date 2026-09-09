import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.nfe.parser import classify_direction, parse_nfe_xml
from app.nfe.participante_extractor import extract_participantes_from_nfe
from app.nfe.produto_extractor import extract_produtos_from_nfe

FIXTURES = Path(__file__).parent / "fixtures" / "nfe"
COMPANY_CNPJ = "11222333000181"

ENTRADA_A1 = FIXTURES / "entrada_fornecedor_a.xml"
ENTRADA_A2 = FIXTURES / "entrada_fornecedor_a_segunda_nota.xml"
ENTRADA_B = FIXTURES / "entrada_fornecedor_b_mesmo_cprod.xml"
SAIDA_A1 = FIXTURES / "saida_cliente_a.xml"
SAIDA_A2 = FIXTURES / "saida_cliente_a_segunda_nota.xml"


# ---------- Parser ----------

def test_parse_nfe_xml_extracts_emit_dest_itens():
    doc = parse_nfe_xml(ENTRADA_A1)
    assert doc["emit"]["cnpj"] == "11444777000161"
    assert doc["dest"]["cnpj"] == COMPANY_CNPJ
    assert len(doc["itens"]) == 1
    assert doc["itens"][0]["xProd"] == "PRODUTO A DO FORNECEDOR"


def test_parse_nfe_xml_normalizes_sem_gtin_to_none():
    doc = parse_nfe_xml(ENTRADA_A1)
    assert doc["itens"][0]["cEAN"] is None


def test_parse_nfe_xml_keeps_real_ean():
    doc = parse_nfe_xml(SAIDA_A1)
    assert doc["itens"][0]["cEAN"] == "7891234567895"


def test_classify_direction_entrada():
    doc = parse_nfe_xml(ENTRADA_A1)
    assert classify_direction(doc, COMPANY_CNPJ) == "entrada"


def test_classify_direction_saida():
    doc = parse_nfe_xml(SAIDA_A1)
    assert classify_direction(doc, COMPANY_CNPJ) == "saida"


def test_classify_direction_none_when_cnpj_not_involved():
    doc = parse_nfe_xml(ENTRADA_A1)
    assert classify_direction(doc, "99999999000199") is None


# ---------- Extração de participante ----------

def test_extract_participantes_classifies_fornecedor_from_entrada():
    participantes = extract_participantes_from_nfe([ENTRADA_A1], COMPANY_CNPJ)
    assert len(participantes) == 1
    assert participantes[0].tipo == {"fornecedor"}
    assert participantes[0].cnpj == "11444777000161"


def test_extract_participantes_classifies_cliente_from_saida():
    participantes = extract_participantes_from_nfe([SAIDA_A1], COMPANY_CNPJ)
    assert len(participantes) == 1
    assert participantes[0].tipo == {"cliente"}


def test_extract_participantes_consolidates_repeated_cnpj_across_notas():
    participantes = extract_participantes_from_nfe([SAIDA_A1, SAIDA_A2], COMPANY_CNPJ)
    assert len(participantes) == 1  # mesmo cliente em 2 notas, não duplica


# ---------- Extração de produto ----------

def test_extract_produto_from_saida_uses_own_cprod_as_key():
    produtos = extract_produtos_from_nfe([SAIDA_A1, SAIDA_A2], COMPANY_CNPJ)
    assert len(produtos) == 1  # mesmo cProd nas 2 notas -> consolida
    assert produtos[0].sku == "900"
    assert "FORNECEDOR_CNPJ" not in produtos[0].extra


def test_extract_produto_from_entrada_uses_fornecedor_plus_cprod_as_key():
    produtos = extract_produtos_from_nfe([ENTRADA_A1, ENTRADA_A2], COMPANY_CNPJ)
    assert len(produtos) == 1  # mesmo fornecedor+cProd nas 2 notas -> consolida
    assert produtos[0].extra["FORNECEDOR_CNPJ"] == "11444777000161"


def test_extract_produto_same_cprod_different_fornecedor_not_merged():
    """cProd '50' aparece em fornecedor A e fornecedor B — são produtos
    DIFERENTES (o número só coincide), não pode virar um registro só."""
    produtos = extract_produtos_from_nfe([ENTRADA_A1, ENTRADA_B], COMPANY_CNPJ)
    assert len(produtos) == 2
    descricoes = {p.description for p in produtos}
    assert descricoes == {"PRODUTO A DO FORNECEDOR", "PRODUTO TOTALMENTE DIFERENTE"}


def test_extract_produto_captures_ncm_and_unit():
    produtos = extract_produtos_from_nfe([SAIDA_A1], COMPANY_CNPJ)
    assert produtos[0].ncm == "10063021"
    assert produtos[0].unit == "UN"
    assert produtos[0].barcode == "7891234567895"
