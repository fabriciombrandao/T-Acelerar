import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.winthor.text_file_generator import generate_text_file, load_layout


def _base_product(**extra) -> dict:
    return {
        "external_id": "1", "sku": "1", "description": "PRODUTO TESTE",
        "unit": "UN", "barcode": "7891234567895", "ncm": "10063021", "weight": 5.5,
        "extra": {
            "EMBALAGEM": "PACOTE", "PESOBRUTO": 5.8, "CODEPTO": 10, "CODSEC": 1,
            "QTUNIT": 1, "CODFORNEC": 99, "LASTROPAL": 1, "ALTURAPAL": 1,
            "QTUNITCX": 1, "MODULO": 1, "RUA": 1, "NUMERO": 1, "APTO": 1,
            "UNIDADEMASTER": "CX", "CODNCMEX": "000", "NATUREZAPRODUTO": "OT",
            "UNIDADETRIBUTAVEL": "UN",
            **extra,
        },
    }


def test_load_layout_has_40_fields_in_order():
    layout = load_layout()
    assert len(layout["campos"]) == 40
    assert layout["campos"][0]["field"] == "CODPROD"
    assert layout["campos"][-1]["field"] == "UNIDADETRIBUTAVEL"


def test_generate_uses_default_separator_and_trailing_separator():
    result = generate_text_file([_base_product()], blocked_record_ids=set())
    line = result.content.strip("\n")
    assert line.endswith("#")
    assert result.records_included == 1


def test_generate_respects_custom_separator():
    result = generate_text_file([_base_product()], blocked_record_ids=set(), separator=";")
    assert ";" in result.content
    assert result.content.strip().endswith(";")
    assert "#" not in result.content


def test_number_field_no_leading_zero_and_correct_decimals():
    result = generate_text_file([_base_product()], blocked_record_ids=set())
    fields = result.content.strip().split("#")
    # seq 1 = CODPROD (decimais=0) deve ser "1", não "01" ou "1.0"
    assert fields[0] == "1"
    # seq 5 = PESOLIQ (decimais=3) deve ter 3 casas
    assert fields[4] == "5.500"


def test_date_field_formats_as_ddmmyyyy():
    product = _base_product(DTCADASTRO="2024-03-15")
    result = generate_text_file([product], blocked_record_ids=set())
    fields = result.content.strip().split("#")
    dtcadastro_idx = 13  # seq 14, índice 13
    assert fields[dtcadastro_idx] == "15/03/2024"


def test_empty_optional_field_renders_as_empty_between_separators():
    result = generate_text_file([_base_product()], blocked_record_ids=set())
    fields = result.content.strip().split("#")
    dtcadastro_idx = 13  # DTCADASTRO não foi informado neste teste
    assert fields[dtcadastro_idx] == ""


def test_missing_required_field_generates_warning():
    product = _base_product()
    del product["extra"]["CODFORNEC"]
    result = generate_text_file([product], blocked_record_ids=set())
    assert any(w.column == "CODFORNEC" for w in result.warnings)


def test_string_field_truncates_and_warns_over_max_length():
    product = _base_product()
    product["description"] = "X" * 60  # DESCRICAO tem tamanho 40
    result = generate_text_file([product], blocked_record_ids=set())
    fields = result.content.strip().split("#")
    assert len(fields[1]) == 40
    assert any(w.column == "DESCRICAO" for w in result.warnings)


def test_unidadetributavel_falls_back_to_unidade_when_missing():
    product = _base_product()
    del product["extra"]["UNIDADETRIBUTAVEL"]
    result = generate_text_file([product], blocked_record_ids=set())
    fields = result.content.strip().split("#")
    assert fields[39] == "UN"  # caiu no fallback_fonte core:unit


def test_blocked_records_are_skipped():
    products = [_base_product(), {**_base_product(), "external_id": "2", "sku": "2"}]
    result = generate_text_file(products, blocked_record_ids={"2"})
    assert result.records_included == 1
    assert result.records_skipped == ["2"]
