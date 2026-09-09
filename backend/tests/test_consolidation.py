import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.canonical.models import CanonicalParticipante, CanonicalProduct
from app.consolidation.consolidate import consolidate_participantes, consolidate_produtos
from app.pipeline import run_participante_pipeline, run_pipeline_multi_source

SPED_FIXTURE = Path(__file__).parent / "fixtures" / "sped_exemplo.txt"
NFE_DIR = Path(__file__).parent / "fixtures" / "nfe"
COMPANY_CNPJ = "11222333000181"


# ---------- consolidate_participantes ----------

def test_consolidate_participantes_merges_by_cnpj():
    p1 = CanonicalParticipante(external_id="1", nome="EMPRESA X", cnpj="11444777000161",
                                tipo={"fornecedor"})
    p2 = CanonicalParticipante(external_id="2", nome="EMPRESA X", cnpj="11444777000161",
                                tipo={"cliente"})
    consolidado = consolidate_participantes([[p1], [p2]])
    assert len(consolidado) == 1
    assert consolidado[0].tipo == {"fornecedor", "cliente"}


def test_consolidate_participantes_fills_empty_field_from_other_source():
    p1 = CanonicalParticipante(external_id="1", nome="EMPRESA X", cnpj="11444777000161",
                                tipo={"fornecedor"}, bairro=None)
    p2 = CanonicalParticipante(external_id="2", nome="EMPRESA X", cnpj="11444777000161",
                                tipo={"fornecedor"}, bairro="CENTRO")
    consolidado = consolidate_participantes([[p1], [p2]])
    assert consolidado[0].bairro == "CENTRO"


def test_consolidate_participantes_keeps_distinct_cnpj_separate():
    p1 = CanonicalParticipante(external_id="1", nome="A", cnpj="11444777000161", tipo={"cliente"})
    p2 = CanonicalParticipante(external_id="2", nome="B", cnpj="22666999000145", tipo={"cliente"})
    consolidado = consolidate_participantes([[p1], [p2]])
    assert len(consolidado) == 2


# ---------- consolidate_produtos ----------

def test_consolidate_produtos_merges_valid_ean():
    p1 = CanonicalProduct(external_id="1", sku="1", description_raw="A",
                           barcode="7891234567895")
    p2 = CanonicalProduct(external_id="2", sku="2", description_raw="A",
                           barcode="7891234567895")
    consolidado = consolidate_produtos([[p1], [p2]])
    assert len(consolidado) == 1


def test_consolidate_produtos_keeps_separate_without_ean():
    p1 = CanonicalProduct(external_id="1", sku="1", description_raw="PRODUTO A")
    p2 = CanonicalProduct(external_id="2", sku="2", description_raw="PRODUTO A")
    consolidado = consolidate_produtos([[p1], [p2]])
    assert len(consolidado) == 2  # sem EAN não funde, mesmo com descrição igual


def test_consolidate_produtos_ignores_invalid_ean_checksum():
    p1 = CanonicalProduct(external_id="1", sku="1", description_raw="A",
                           barcode="1234567890123")  # dígito verificador errado
    p2 = CanonicalProduct(external_id="2", sku="2", description_raw="A",
                           barcode="1234567890123")
    consolidado = consolidate_produtos([[p1], [p2]])
    assert len(consolidado) == 2  # EAN inválido não é chave de fusão


# ---------- run_pipeline_multi_source ----------

def test_run_pipeline_multi_source_requires_at_least_one_source():
    with pytest.raises(ValueError):
        run_pipeline_multi_source()


def test_run_pipeline_multi_source_requires_company_cnpj_for_xml():
    xml_paths = [NFE_DIR / "saida_cliente_a.xml"]
    with pytest.raises(ValueError):
        run_pipeline_multi_source(xml_paths=xml_paths)


def test_run_pipeline_multi_source_combines_sped_and_xml():
    sped_paths = [SPED_FIXTURE]
    xml_paths = [NFE_DIR / "saida_cliente_a.xml"]
    result = run_pipeline_multi_source(sped_paths=sped_paths, xml_paths=xml_paths,
                                        company_cnpj="11222333000181")
    # As duas fixtures usam o MESMO EAN (7891234567895) — funde por EAN
    # em 1 produto só. Prova que a consolidação cruza fonte SPED+XML de
    # verdade, não só concatena.
    assert len(result.products) == 1


def test_run_pipeline_multi_source_runs_downstream_stages():
    """Confirma que passa pelos mesmos estágios do CSV — validate_batch
    roda de verdade (não só ingestão crua)."""
    sped_paths = [SPED_FIXTURE]
    result = run_pipeline_multi_source(sped_paths=sped_paths)
    assert "data_readiness_score" in result.report


# ---------- run_participante_pipeline ----------

def test_run_participante_pipeline_requires_at_least_one_source():
    with pytest.raises(ValueError):
        run_participante_pipeline()


def test_run_participante_pipeline_extracts_and_validates():
    result = run_participante_pipeline(sped_paths=[SPED_FIXTURE])
    assert len(result.participantes) == 3  # fixture SPED tem 3 participantes (0150)
    assert result.exceptions == []  # todos com CNPJ válido e classificados


def test_run_participante_pipeline_combines_sped_and_xml_by_cnpj():
    sped_paths = [SPED_FIXTURE]
    xml_paths = [NFE_DIR / "entrada_fornecedor_a.xml"]
    result = run_participante_pipeline(sped_paths=sped_paths, xml_paths=xml_paths,
                                        company_cnpj="11222333000181")
    # fornecedor do XML (CNPJ 11444777000161) já existe no SPED fixture
    # como o mesmo CNPJ -> não deveria duplicar.
    fornecedor = next(p for p in result.participantes if p.cnpj == "11444777000161")
    assert "fornecedor" in fornecedor.tipo
