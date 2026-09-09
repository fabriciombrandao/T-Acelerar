import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline import run_pipeline_csv
from app.winthor.text_file_generator import extra_pcprodut_field_names, generate_text_file

SAMPLE_CSV = Path(__file__).parent.parent.parent / "sample_data" / "produtos_exemplo.csv"


def test_pipeline_without_adherence_answers_skips_adherence_entirely():
    """adherence_answers=None (comportamento default) não roda o motor —
    usado pelo CLI standalone, que não tem projeto/wizard."""
    result = run_pipeline_csv(SAMPLE_CSV)
    reason_codes = {e.reason_code for e in result.exceptions}
    assert "CAMPO_ADERENCIA_AUSENTE" not in reason_codes


def test_pipeline_with_empty_adherence_answers_still_flags_always_required_fields():
    """{} (wizard nunca preenchido) não é o mesmo que None — cadastro básico
    e fiscal NCM são sempre exigidos, independente de resposta de wizard."""
    result = run_pipeline_csv(SAMPLE_CSV, adherence_answers={},
                               extra_field_names=extra_pcprodut_field_names())
    reason_codes = {e.reason_code for e in result.exceptions}
    assert "CAMPO_ADERENCIA_AUSENTE" in reason_codes


def test_pipeline_applies_module_defaults_when_module_not_applicable():
    """Endereçamento marcado como não aplicável -> MODULO/RUA/NUMERO/APTO
    recebem default (1), não viram exceção."""
    answers = {"enderecamento": False, "paletizacao": False, "comissao_produto": False,
               "compra_custos": False, "validade_lote": False}
    result = run_pipeline_csv(SAMPLE_CSV, adherence_answers=answers,
                               extra_field_names=extra_pcprodut_field_names())

    address_exceptions = [
        e for e in result.exceptions
        if e.reason_code == "CAMPO_ADERENCIA_AUSENTE" and e.payload.get("module") == "enderecamento"
    ]
    assert address_exceptions == []

    produto_com_default = next(p for p in result.products if p.extra.get("MODULO") == 1)
    assert produto_com_default.extra["RUA"] == 1


def test_pipeline_blocks_when_module_applicable_and_field_missing():
    """Endereçamento marcado como aplicável -> campo ausente vira BLOCKER
    de verdade (não default silencioso)."""
    answers = {"enderecamento": True, "paletizacao": False, "comissao_produto": False,
               "compra_custos": False, "validade_lote": False}
    result = run_pipeline_csv(SAMPLE_CSV, adherence_answers=answers,
                               extra_field_names=extra_pcprodut_field_names())

    address_exceptions = [
        e for e in result.exceptions
        if e.reason_code == "CAMPO_ADERENCIA_AUSENTE" and e.payload.get("module") == "enderecamento"
    ]
    assert len(address_exceptions) > 0
    assert all(e.severity == "BLOCKER" for e in address_exceptions)


def test_extra_field_captured_from_csv_reaches_final_generated_file():
    """Ponta a ponta: coluna extra no CSV de origem -> CanonicalProduct.extra
    -> arquivo texto gerado. Prova que a captura de ingestão realmente
    alimenta o gerador, não só fica presa no meio do pipeline."""
    import tempfile
    csv_content = (
        "codigo,descricao,unidade,codepto,codsec,codfornec,embalagem,"
        "pesoliq,pesobruto,qtunit,qtunitcx,unidademaster,codncmex,"
        "naturezaproduto,unidadetributavel,ncm\n"
        "1,PRODUTO COMPLETO,UN,10,5,99,PACOTE,1.0,1.2,1,12,CX,000,OT,UN,10063021\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False,
                                      encoding="utf-8") as f:
        f.write(csv_content)
        tmp_path = f.name

    answers = {"enderecamento": False, "paletizacao": False, "comissao_produto": False,
               "compra_custos": False, "validade_lote": False}
    result = run_pipeline_csv(tmp_path, adherence_answers=answers,
                               extra_field_names=extra_pcprodut_field_names())

    assert result.products[0].extra["CODSEC"] == "5"

    product_dicts = [{
        "external_id": p.external_id, "sku": p.sku, "description": p.description,
        "unit": p.unit, "barcode": p.barcode, "ncm": p.ncm, "weight": p.weight,
        "extra": p.extra,
    } for p in result.products]
    text_result = generate_text_file(product_dicts, blocked_record_ids=set())

    fields = text_result.content.strip().split("#")
    assert fields[7] == "5"  # seq 8 = CODSEC, índice 7
