import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.canonical.models import CanonicalParticipante
from app.winthor.participante_generator import generate_pccliente_file, generate_pcfornec_file


def _participante(external_id, nome, tipo, cnpj=None, cpf=None, **kwargs) -> CanonicalParticipante:
    return CanonicalParticipante(
        external_id=external_id, nome=nome, cnpj=cnpj, cpf=cpf, tipo=tipo, **kwargs
    )


def test_pccliente_only_includes_participantes_com_papel_cliente():
    participantes = [
        _participante("1", "CLIENTE A", {"cliente"}, cnpj="11222333000181"),
        _participante("2", "FORNECEDOR B", {"fornecedor"}, cnpj="11444777000161"),
    ]
    result = generate_pccliente_file(participantes)
    assert result.records_included == 1
    assert "CLIENTE A" in result.content
    assert "FORNECEDOR B" not in result.content


def test_pcfornec_only_includes_participantes_com_papel_fornecedor():
    participantes = [
        _participante("1", "CLIENTE A", {"cliente"}, cnpj="11222333000181"),
        _participante("2", "FORNECEDOR B", {"fornecedor"}, cnpj="11444777000161"),
    ]
    result = generate_pcfornec_file(participantes)
    assert result.records_included == 1
    assert "FORNECEDOR B" in result.content
    assert "CLIENTE A" not in result.content


def test_participante_ambos_papeis_aparece_nos_dois_arquivos():
    participantes = [
        _participante("1", "EMPRESA MISTA", {"cliente", "fornecedor"}, cnpj="11222333000181"),
    ]
    cli = generate_pccliente_file(participantes)
    forn = generate_pcfornec_file(participantes)
    assert cli.records_included == 1
    assert forn.records_included == 1


def test_tipofj_deriva_j_para_cnpj():
    participantes = [_participante("1", "EMPRESA LTDA", {"cliente"}, cnpj="11222333000181")]
    result = generate_pccliente_file(participantes)
    campos = result.content.strip().split("#")
    # seq 36 = TIPOFJ, índice 35
    assert campos[35] == "J"


def test_tipofj_deriva_f_para_cpf():
    participantes = [_participante("1", "FULANO DA SILVA", {"cliente"}, cpf="11144477735")]
    result = generate_pccliente_file(participantes)
    campos = result.content.strip().split("#")
    assert campos[35] == "F"


def test_tipopessoa_pcfornec_deriva_igual():
    participantes = [_participante("1", "FORNECEDOR LTDA", {"fornecedor"}, cnpj="11222333000181")]
    result = generate_pcfornec_file(participantes)
    campos = result.content.strip().split("#")
    # seq 25 = TIPOPESSOA, último campo (índice 24)
    assert campos[24] == "J"


def test_codcli_sequencial_por_ordem_de_entrada():
    participantes = [
        _participante("1", "PRIMEIRO", {"cliente"}, cnpj="11222333000181"),
        _participante("2", "SEGUNDO", {"cliente"}, cnpj="22666999000145"),
    ]
    result = generate_pccliente_file(participantes)
    linhas = result.content.strip().split("\n")
    assert linhas[0].split("#")[0] == "1"
    assert linhas[1].split("#")[0] == "2"


def test_endereco_mapeado_para_cobranca_e_entrega():
    participantes = [_participante(
        "1", "EMPRESA X", {"cliente"}, cnpj="11222333000181",
        endereco="RUA TESTE", numero="100", bairro="CENTRO",
        municipio="PALMAS", uf="TO", cep="77000000",
    )]
    result = generate_pccliente_file(participantes)
    campos = result.content.strip().split("#")
    # ENDERCOB (seq 3, idx 2) e ENDERENT (seq 10, idx 9) devem ter o mesmo endereço
    assert campos[2] == "RUA TESTE"
    assert campos[9] == "RUA TESTE"
    # ESTCOB (seq 8, idx 7) e ESTENT (seq 15, idx 14)
    assert campos[7] == "TO"
    assert campos[14] == "TO"


def test_ie_ausente_gera_aviso_sem_aplicar_default_sozinho():
    """default_when_not_applicable no layout só é consumido pelo motor de
    ADERÊNCIA (app/winthor/adherence.py) — que ainda não existe pra
    participante (documentado como pendente). O gerador sozinho NÃO
    aplica esse default automaticamente: campo ausente fica vazio +
    warning, não vira 'ISENTO' sozinho. Este teste prova o comportamento
    real, não o que o layout torna possível no futuro."""
    participantes = [_participante("1", "EMPRESA X", {"cliente"}, cnpj="11222333000181", ie=None)]
    result = generate_pccliente_file(participantes)
    campos = result.content.strip().split("#")
    assert campos[17] == ""  # seq 18 = IEENT, idx 17 — vazio, não "ISENTO"
    assert any(w.column == "IEENT" for w in result.warnings)
