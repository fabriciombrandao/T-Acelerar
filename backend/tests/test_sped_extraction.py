import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.sped.parser import parse_sped_records
from app.sped.participante_extractor import extract_participantes_from_sped
from app.sped.produto_extractor import extract_produtos_from_sped
from app.validation.br_documents import validate_cnpj, validate_cpf

FIXTURE = Path(__file__).parent / "fixtures" / "sped_exemplo.txt"


# ---------- Parser genérico ----------

def test_parse_sped_records_groups_by_registro_type():
    records = parse_sped_records(FIXTURE)
    assert "0150" in records
    assert "C100" in records
    assert "0200" in records


def test_parse_sped_records_strips_leading_trailing_pipes():
    records = parse_sped_records(FIXTURE)
    # 0150 tem 12 campos após o REG (COD_PART até BAIRRO) — nem a barra
    # inicial nem a final devem sobrar como elemento vazio na lista.
    campos = records["0150"][0]
    assert campos[0] == "100"  # COD_PART do primeiro participante do fixture
    assert campos != [""] and campos[-1] != ""


def test_parse_sped_records_correct_field_count_per_0150():
    records = parse_sped_records(FIXTURE)
    for campos in records["0150"]:
        assert len(campos) == 12  # COD_PART..BAIRRO


# ---------- Validadores CNPJ/CPF ----------

def test_validate_cnpj_accepts_real_valid_cnpj():
    assert validate_cnpj("11222333000181") is True


def test_validate_cnpj_rejects_wrong_check_digit():
    assert validate_cnpj("11222333000199") is False


def test_validate_cnpj_rejects_all_same_digit():
    assert validate_cnpj("11111111111111") is False


def test_validate_cnpj_tolerates_formatting():
    assert validate_cnpj("11.222.333/0001-81") is True


def test_validate_cpf_accepts_known_valid_cpf():
    assert validate_cpf("11144477735") is True


def test_validate_cpf_rejects_all_same_digit():
    assert validate_cpf("11111111111") is False


# ---------- Extração de participante (cliente/fornecedor) ----------

def test_extract_classifies_pure_fornecedor():
    participantes = extract_participantes_from_sped([FIXTURE])
    fornecedor = next(p for p in participantes if p.cnpj == "11444777000161")
    assert fornecedor.tipo == {"fornecedor"}


def test_extract_classifies_pure_cliente():
    participantes = extract_participantes_from_sped([FIXTURE])
    cliente = next(p for p in participantes if p.cnpj == "22666999000145")
    assert cliente.tipo == {"cliente"}


def test_extract_classifies_participante_como_cliente_e_fornecedor():
    participantes = extract_participantes_from_sped([FIXTURE])
    misto = next(p for p in participantes if p.cnpj == "33888111000135")
    assert misto.tipo == {"cliente", "fornecedor"}


def test_extract_consolidates_by_cnpj_not_by_cod_part():
    """Simula dois arquivos SPED (numeração de COD_PART independente entre
    eles) com o MESMO CNPJ aparecendo sob COD_PART diferente em cada um —
    tem que consolidar num registro só, não duplicar."""
    import tempfile

    arquivo_a = (
        "|0000|020|0|01082026|31082026|EMPRESA A|11222333000181||TO|1|1721000|ISENTO||A|1|\n"
        "|0150|500|PARCEIRO COMUM|01058|11444777000161||987654321|1721000||RUA X|1||CENTRO|\n"
        "|C100|0|1|500|55|00|001|1|CHAVE1|01082026|01082026|10,00|0|0,00|0,00|10,00|9|"
        "0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|\n"
    )
    arquivo_b = (
        "|0000|020|0|01082026|31082026|EMPRESA A|11222333000181||TO|1|1721000|ISENTO||A|1|\n"
        "|0150|999|PARCEIRO COMUM|01058|11444777000161||987654321|1721000||RUA X|1||CENTRO|\n"
        "|C100|1|0|999|55|00|001|2|CHAVE2|02082026|02082026|20,00|1|0,00|0,00|20,00|9|"
        "0,00|0,00|0,00|20,00|4,00|0,00|0,00|0,00|0,33|1,52|0,00|0,00|\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                      encoding="iso-8859-1") as fa:
        fa.write(arquivo_a)
        path_a = fa.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                      encoding="iso-8859-1") as fb:
        fb.write(arquivo_b)
        path_b = fb.name

    participantes = extract_participantes_from_sped([path_a, path_b])
    assert len(participantes) == 1  # não duplicou por COD_PART diferente
    assert participantes[0].tipo == {"fornecedor", "cliente"}  # info dos 2 arquivos combinada


def test_extract_ignores_c100_referencing_unknown_cod_part():
    """C100 apontando pra COD_PART sem 0150 correspondente não deve quebrar
    nem criar participante fantasma."""
    import tempfile

    conteudo = (
        "|0000|020|0|01082026|31082026|EMPRESA A|11222333000181||TO|1|1721000|ISENTO||A|1|\n"
        "|C100|0|1|999999|55|00|001|1|CHAVE1|01082026|01082026|10,00|0|0,00|0,00|10,00|9|"
        "0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                      encoding="iso-8859-1") as f:
        f.write(conteudo)
        path = f.name

    participantes = extract_participantes_from_sped([path])
    assert participantes == []


# ---------- Extração de produto (registro 0200) ----------

def test_extract_produto_from_sped_maps_fields_correctly():
    produtos = extract_produtos_from_sped([FIXTURE])
    assert len(produtos) == 1
    p = produtos[0]
    assert p.sku == "1"
    assert p.description == "PRODUTO TESTE UM"
    assert p.barcode == "7891234567895"
    assert p.unit == "UN"
    assert p.ncm == "10063021"


def test_extract_produto_from_sped_consolidates_by_cod_item_across_files():
    """Mesmo COD_ITEM em 2 arquivos (ex: livro ICMS + livro PIS/COFINS da
    mesma empresa) -> um produto só, não duplica."""
    produtos = extract_produtos_from_sped([FIXTURE, FIXTURE])
    assert len(produtos) == 1
    assert len(produtos[0].provenance) == 2  # registrou as duas fontes


def test_extract_produto_from_sped_skips_blank_cod_item():
    import tempfile
    conteudo = "|0200|  |DESCRICAO SEM CODIGO|||UN|00|10063021|||||\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                      encoding="iso-8859-1") as f:
        f.write(conteudo)
        path = f.name

    produtos = extract_produtos_from_sped([path])
    assert produtos == []
