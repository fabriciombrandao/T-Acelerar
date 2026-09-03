import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.canonical.models import CanonicalProduct
from app.winthor.adherence import apply_adherence, load_modules_config, preset_for_subsegment
from app.winthor.pis_cofins_monofasico import derive_pis_cofins_retido, is_monofasico


def _make_product(**extra_fields) -> CanonicalProduct:
    p = CanonicalProduct(
        external_id="P001", sku="P001", description_raw="PRODUTO TESTE",
        description="PRODUTO TESTE", ncm="22021000",
    )
    p.extra.update(extra_fields)
    return p


def test_preset_for_subsegment_loja_unica_disables_logistics_modules():
    preset = preset_for_subsegment("varejo", "loja_unica")
    assert preset["enderecamento"] is False
    assert preset["paletizacao"] is False


def test_preset_for_subsegment_distribuidor_fmcg_enables_logistics():
    preset = preset_for_subsegment("distribuicao", "distribuidor_fmcg")
    assert preset["enderecamento"] is True
    assert preset["paletizacao"] is True
    assert preset["comissao_produto"] is True


def test_module_not_applicable_fills_default_without_exception():
    product = _make_product()  # sem MODULO/RUA/NUMERO/APTO
    answers = {"enderecamento": False, "paletizacao": False,
               "comissao_produto": False, "compra_custos": False, "validade_lote": False}

    exceptions = apply_adherence([product], answers)

    address_exceptions = [e for e in exceptions if e.payload.get("module") == "enderecamento"]
    assert address_exceptions == []
    assert product.extra["MODULO"] == 1
    assert product.extra["RUA"] == 1


def test_module_applicable_and_missing_field_raises_blocker():
    product = _make_product()  # sem endereçamento
    answers = {"enderecamento": True, "paletizacao": False,
               "comissao_produto": False, "compra_custos": False, "validade_lote": False}

    exceptions = apply_adherence([product], answers)

    address_exceptions = [e for e in exceptions if e.payload.get("module") == "enderecamento"]
    assert len(address_exceptions) == 4  # MODULO, RUA, NUMERO, APTO
    assert all(e.severity == "BLOCKER" for e in address_exceptions)
    assert "MODULO" not in product.extra  # não preenche default quando é aplicável


def test_module_applicable_and_field_present_no_exception():
    product = _make_product(MODULO=1, RUA=2, NUMERO=3, APTO=1)
    answers = {"enderecamento": True, "paletizacao": False,
               "comissao_produto": False, "compra_custos": False, "validade_lote": False}

    exceptions = apply_adherence([product], answers)
    address_exceptions = [e for e in exceptions if e.payload.get("module") == "enderecamento"]
    assert address_exceptions == []


def test_pis_cofins_is_always_derived_never_asked():
    beer = _make_product()
    beer.ncm = "22030000"  # cerveja — monofásico
    rice = _make_product()
    rice.ncm = "10063021"  # arroz — não monofásico

    apply_adherence([beer, rice], answers={})

    assert beer.extra["PISCOFINSRETIDO"] == "S"
    assert rice.extra["PISCOFINSRETIDO"] == "N"


def test_is_monofasico_matches_by_prefix():
    assert is_monofasico("22030000") is True   # cerveja
    assert is_monofasico("10063021") is False  # arroz
    assert is_monofasico(None) is False


def test_derive_pis_cofins_retido_returns_s_or_n():
    assert derive_pis_cofins_retido("27101259") == "S"  # combustível
    assert derive_pis_cofins_retido("10063021") == "N"


def test_modules_config_loads_and_has_expected_ids():
    config = load_modules_config()
    ids = {m["id"] for m in config["modulos"]}
    assert "enderecamento" in ids
    assert "paletizacao" in ids
    assert "fiscal_pis_cofins_retido" in ids


def test_missing_field_with_no_default_and_module_inapplicable_is_high_not_blocker():
    product = _make_product()
    # QTTOTPAL não tem default_when_not_applicable e não é required_by_layout,
    # então não deve gerar exceção nenhuma quando módulo inaplicável.
    answers = {"enderecamento": False, "paletizacao": False,
               "comissao_produto": False, "compra_custos": False, "validade_lote": False}
    exceptions = apply_adherence([product], answers)
    palet_exceptions = [e for e in exceptions if e.payload.get("module") == "paletizacao"]
    assert palet_exceptions == []  # LASTROPAL/ALTURAPAL têm default; QTTOTPAL não é obrigatório
