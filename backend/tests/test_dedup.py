import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.canonical.models import CanonicalProduct
from app.dedup.dedup import find_probable_duplicates


def _product(external_id, sku, description, brand=None) -> CanonicalProduct:
    return CanonicalProduct(
        external_id=external_id, sku=sku, description_raw=description,
        description=description, brand=brand,
    )


def test_finds_duplicate_within_same_bucket():
    products = [
        _product("1", "P1", "ARROZ BRANCO TIPO 1 5KG", brand="TIO JOAO"),
        _product("2", "P2", "ARROZ BRANCO TIPO 1 5 KG", brand="TIO JOAO"),  # 1 espaço a mais
    ]
    exceptions = find_probable_duplicates(products)
    assert len(exceptions) == 1
    assert exceptions[0].payload["sku_a"] == "P1"
    assert exceptions[0].payload["sku_b"] == "P2"


def test_different_brand_never_compared_even_if_description_identical():
    products = [
        _product("1", "P1", "REFRIGERANTE 2L PET", brand="MARCA A"),
        _product("2", "P2", "REFRIGERANTE 2L PET", brand="MARCA B"),
    ]
    exceptions = find_probable_duplicates(products)
    assert exceptions == []  # marcas diferentes = baldes diferentes, nunca comparados


def test_same_sku_never_flagged_as_duplicate_of_itself():
    products = [
        _product("1", "P1", "ARROZ BRANCO 5KG", brand="TIO JOAO"),
        _product("2", "P1", "ARROZ BRANCO 5KG", brand="TIO JOAO"),  # mesmo SKU, registros diferentes
    ]
    exceptions = find_probable_duplicates(products)
    assert exceptions == []


def test_products_without_description_are_ignored():
    products = [
        _product("1", "P1", "", brand="X"),
        _product("2", "P2", "", brand="X"),
    ]
    assert find_probable_duplicates(products) == []


def test_large_bucket_uses_sorted_neighborhood_and_still_finds_adjacent_match():
    """Balde grande o bastante pra passar do limite de comparação exaustiva.
    O par verdadeiro fica isolado alfabeticamente (prefixo 'ESPECIAL' não
    colide com o preenchimento 'GENERICO'), então cai na mesma vizinhança
    depois de ordenado — sorted neighborhood pega mesmo em balde grande."""
    filler = [
        _product(f"filler-{i}", f"F{i}", f"PRODUTO GENERICO TIPO {i:05d} PREENCHIMENTO",
                  brand="SEM MARCA")
        for i in range(500)  # > FULL_COMPARISON_BUCKET_LIMIT (300)
    ]
    dup_a = _product("dup-a", "DA", "PRODUTO ESPECIAL DUPLICADO AQUI XPTO", brand="SEM MARCA")
    dup_b = _product("dup-b", "DB", "PRODUTO ESPECIAL DUPLICADO AQUI XPTO", brand="SEM MARCA")

    exceptions = find_probable_duplicates([*filler, dup_a, dup_b])
    pairs = {(e.payload["sku_a"], e.payload["sku_b"]) for e in exceptions}
    assert ("DA", "DB") in pairs


def test_scales_to_20k_products_in_reasonable_time():
    """Prova que blocking evita o custo O(n²) puro: 20k produtos distribuídos
    em centenas de marcas distintas deve rodar em segundos, não minutos."""
    products = [
        _product(f"id-{i}", f"SKU{i}", f"PRODUTO {i:06d} VARIANTE UNICA TESTE ITEM {i:06d}",
                  brand=f"MARCA{i % 500}")
        for i in range(20_000)
    ]

    start = time.time()
    exceptions = find_probable_duplicates(products)
    elapsed = time.time() - start

    assert elapsed < 10, f"dedup em 20k produtos levou {elapsed:.1f}s — blocking não está efetivo"
    assert isinstance(exceptions, list)


def test_scales_to_one_pathological_oversized_bucket():
    """Pior caso: 20 mil produtos TODOS na mesma marca/primeira-palavra
    (um balde só, gigante). Sem sorted neighborhood isso seria O(n²) puro
    (~200 milhões de comparações). Com a janela, deve terminar em segundos."""
    products = [
        _product(f"id-{i}", f"SKU{i}", f"PRODUTO GENERICO ITEM NUMERO {i:06d} DIVERSOS",
                  brand="SEM MARCA")
        for i in range(20_000)
    ]

    start = time.time()
    find_probable_duplicates(products)
    elapsed = time.time() - start

    assert elapsed < 10, f"balde único de 20k levou {elapsed:.1f}s — sorted neighborhood não ativou"
