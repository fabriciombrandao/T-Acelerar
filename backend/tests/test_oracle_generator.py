import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.winthor.oracle_generator import generate_insert_script, load_mapping


def test_load_mapping_has_required_keys():
    mapping = load_mapping()
    assert "table" in mapping
    assert "columns" in mapping
    assert len(mapping["columns"]) > 0


def test_generate_insert_escapes_single_quotes():
    products = [{
        "external_id": "P001", "sku": "P001",
        "description": "PARAFUSO 1/2' ROSCA D'AGUA",
        "barcode": None, "ncm": "73181500", "cest": None, "unit": "UN",
        "brand": None, "family": None, "department": None, "weight": None,
    }]
    result = generate_insert_script(products, blocked_record_ids=set())
    assert "ROSCA D''AGUA" in result.sql
    assert result.records_included == 1
    assert not result.records_skipped


def test_generate_insert_skips_blocked_records():
    products = [
        {"external_id": "P001", "sku": "P001", "description": "PRODUTO A",
         "barcode": None, "ncm": None, "cest": None, "unit": None,
         "brand": None, "family": None, "department": None, "weight": None},
        {"external_id": "P002", "sku": "P002", "description": "PRODUTO B",
         "barcode": None, "ncm": None, "cest": None, "unit": None,
         "brand": None, "family": None, "department": None, "weight": None},
    ]
    result = generate_insert_script(products, blocked_record_ids={"P002"})
    assert result.records_included == 1
    assert result.records_skipped == ["P002"]
    assert "PRODUTO B" not in result.sql
    assert "PRODUTO A" in result.sql


def test_generate_insert_truncates_and_warns_on_max_length():
    long_desc = "X" * 200
    products = [{
        "external_id": "P001", "sku": "P001", "description": long_desc,
        "barcode": None, "ncm": None, "cest": None, "unit": None,
        "brand": None, "family": None, "department": None, "weight": None,
    }]
    result = generate_insert_script(products, blocked_record_ids=set())
    assert len(result.warnings) == 1
    assert "truncado" in result.warnings[0].message.lower()


def test_generate_insert_null_for_missing_optional_field():
    products = [{
        "external_id": "P001", "sku": "P001", "description": "PRODUTO SEM EAN",
        "barcode": None, "ncm": None, "cest": None, "unit": None,
        "brand": None, "family": None, "department": None, "weight": None,
    }]
    result = generate_insert_script(products, blocked_record_ids=set())
    assert "NULL" in result.sql
