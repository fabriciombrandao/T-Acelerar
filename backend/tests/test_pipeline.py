import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.normalization.rules import normalize_description, extract_unit
from app.validation.rules import validate_ean13
from app.pipeline import run_pipeline_csv

SAMPLE_CSV = Path(__file__).parent.parent.parent / "sample_data" / "produtos_exemplo.csv"


def test_normalize_description_collapses_and_standardizes():
    text, rules = normalize_description("REFRI COCA COLA 2 LT PET")
    assert text == "REFRI COCA-COLA 2L PET"
    assert any("brand_std" in r for r in rules)


def test_normalize_description_handles_spacing_variants():
    a, _ = normalize_description("COCA COLA 2 LT PET")
    b, _ = normalize_description("COCA-COLA 2 L PET")
    assert a == b


def test_extract_unit():
    assert extract_unit("REFRIGERANTE 2L PET") == "L"
    assert extract_unit("ARROZ 5KG") == "KG"
    assert extract_unit("SEM UNIDADE AQUI") is None


def test_validate_ean13_correct_checksum():
    # 7894900011517 é um EAN-13 real e válido (Coca-Cola 2L, dígito verificador correto).
    assert validate_ean13("7894900011517") is True


def test_validate_ean13_rejects_bad_checksum():
    assert validate_ean13("1234567890123") is False


def test_pipeline_end_to_end_flags_expected_exceptions():
    result = run_pipeline_csv(SAMPLE_CSV)

    reason_codes = {e.reason_code for e in result.exceptions}
    assert "CAMPO_OBRIGATORIO_VAZIO" in reason_codes   # P004 sem descrição
    assert "SKU_DUPLICADO" in reason_codes              # P003 duplicado
    assert "EAN_DUPLICADO" in reason_codes              # P001/P002 mesmo EAN
    assert "NCM_AUSENTE" in reason_codes                # P004/P005
    assert "PROVAVEL_DUPLICADO" in reason_codes         # P003 vs P006 (mesmo produto, grafia com espaço)

    assert result.report["total_registros"] == 7
    assert result.report["exception_rate"] > 0
