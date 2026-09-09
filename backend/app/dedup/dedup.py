"""
Deduplicação — detecta produtos semanticamente iguais com SKU/EAN diferentes.

Duas técnicas combinadas para funcionar em volume grande (testado até 20k+
produtos; desenhado para escalar a centenas de milhares):

1. BLOCKING — só compara produtos que caem no mesmo balde (marca + primeira
   palavra da descrição). Produtos em baldes diferentes nunca são
   comparados. Isso já reduz o grosso do custo: O(n²) global vira
   O(soma dos k_i²) por balde, muito menor na prática.

2. SORTED NEIGHBORHOOD — dentro de um balde grande, em vez de comparar
   todo mundo contra todo mundo (ainda O(k²) se o balde for grande — ex:
   "SEM MARCA" concentrando dezenas de milhares de produtos), ordena o
   balde por descrição e compara cada item só com uma janela de vizinhos
   próximos na ordem alfabética. Descrições quase-duplicadas tendem a ficar
   adjacentes (ou muito perto) depois de ordenadas, então isso captura a
   esmagadora maioria dos casos reais com custo O(k log k + k·W) em vez de
   O(k²). É uma técnica clássica e determinística (nada de hash aleatório
   que faria o resultado variar entre execuções).

Trade-off aceito: um balde patologicamente grande com janela pequena pode
deixar passar um par duplicado que ficou longe na ordenação alfabética
apesar de ser semanticamente parecido (ex: descrição começa muito diferente
mas o miolo é idêntico). Isso é detectável/mitigável aumentando a janela ou
melhorando a normalização de descrição antes do dedup — não é perda muda:
o comportamento é documentado e testado.

LIMITAÇÃO CONHECIDA, NÃO RESOLVIDA: o filtro de medida (número+unidade)
pega variação de peso/tamanho de embalagem, mas não pega variação de
SABOR/VARIANTE com a mesma medida — ex: "PAO DE QUEIJO RECHEADO DE
FRANGO 1KG" vs "...RECHEADO DE REQUEIJAO 1KG" ainda bate >90% de
similaridade (medida igual nos dois, só a palavra do meio muda) e seria
sinalizado como possível duplicata, sendo na verdade produtos diferentes.
Confirmado com dado real. Resolver isso exigiria dicionário de
variante/sabor por categoria — não implementado, fica pra quando for
um problema real (hoje é 1 falso positivo entre exceções, não travou
nada, só some na Exception Queue precisando de "rejeitar").
"""

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher

from app.canonical.models import CanonicalProduct, ExceptionRecord

SIMILARITY_THRESHOLD = 0.90

# Padrão número+unidade (peso, volume, embalagem) — usado pra impedir que
# duas variantes de peso/tamanho do MESMO produto base sejam marcadas como
# duplicata só porque o resto do texto é quase idêntico. Achado real:
# testado contra catálogo real de alimentos, "PAO DE QUEIJO 90G PCT 5KG"
# vs "PAO DE QUEIJO 30G PCT 1KG" batia 93%+ de similaridade (são produtos
# DIFERENTES — pesos e tamanhos de embalagem diferentes, nunca duplicata).
_MEASURE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s?(KG|G|MG|ML|L|UN|PCT|CX)\b", re.IGNORECASE)

# Métrica usada em baldes grandes (sorted neighborhood): Jaccard de tokens
# é O(nº de palavras) por comparação, ordens de magnitude mais barato que
# SequenceMatcher (que é O(len_a * len_b) na prática para strings deste
# tamanho). Trade-off deliberado: menos preciso a nível de caractere
# (não pega diferença de 1 letra numa palavra), mas é o que torna dedup
# viável quando um balde tem dezenas de milhares de itens — SequenceMatcher
# nessa escala não termina em tempo aceitável mesmo com blocking.
JACCARD_SIMILARITY_THRESHOLD = 0.85

# Até este tamanho, comparação exaustiva com SequenceMatcher (caro, mas
# preciso a nível de caractere) dentro do balde é barata o bastante pra
# valer a pena. ACIMA disso, mesmo com poucas dezenas de itens, catálogos de
# distribuição costumam ter descrição paramétrica quase-idêntica (ex:
# "PARAFUSO M6 X 20MM" vs "PARAFUSO M6 X 25MM" — comum em ferragens,
# autopeças, etc.), que é o pior caso de custo pra SequenceMatcher. Por
# isso o limite é baixo: prioriza terminar rápido em escala real sobre
# precisão de caractere em baldes maiores.
FULL_COMPARISON_BUCKET_LIMIT = 30

# Tamanho da janela de vizinhos comparados após ordenar um balde grande.
SORTED_NEIGHBORHOOD_WINDOW = 20


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _extract_measures(description: str) -> frozenset[str]:
    """Extrai todo par número+unidade da descrição (ex: '90G', '5KG').
    Duas descrições com medidas DIFERENTES nunca são a mesma coisa,
    não importa quão parecido o resto do texto seja — é o achado real
    documentado acima."""
    matches = _MEASURE_RE.findall(description.upper())
    return frozenset(f"{num}{unit}" for num, unit in matches)


def _measures_conflict(a: str, b: str) -> bool:
    """True quando as duas descrições têm medida extraível E ela difere —
    nesse caso o par nunca é duplicata, sem precisar calcular similaridade
    nenhuma. Se uma das duas (ou as duas) não tem medida extraível, não
    veta nada aqui — segue pra comparação textual normal."""
    measures_a = _extract_measures(a)
    measures_b = _extract_measures(b)
    return bool(measures_a) and bool(measures_b) and measures_a != measures_b


def _blocking_key(product: CanonicalProduct) -> str:
    """Chave de balde: marca normalizada + primeira palavra significativa
    da descrição. Produtos em baldes diferentes nunca são comparados."""
    brand = (product.brand or "").strip().upper()
    description = (product.description or "").strip().upper()
    first_word = description.split(" ")[0] if description else ""
    return f"{brand}::{first_word}"


def _make_exception(p1: CanonicalProduct, p2: CanonicalProduct, score: float) -> ExceptionRecord:
    return ExceptionRecord(
        record_id=p1.external_id, entity="Product",
        reason_code="PROVAVEL_DUPLICADO",
        description=(
            f"'{p1.description}' (SKU {p1.sku}) é {score:.0%} similar a "
            f"'{p2.description}' (SKU {p2.sku})."
        ),
        severity="MEDIUM",
        payload={"sku_a": p1.sku, "sku_b": p2.sku, "similarity": round(score, 4)},
    )


def _compare_pair(p1: CanonicalProduct, p2: CanonicalProduct) -> ExceptionRecord | None:
    if p1.sku == p2.sku:
        return None
    a, b = p1.description, p2.description

    if _measures_conflict(a, b):
        return None

    # Filtro barato antes do cálculo completo de similaridade: quick_ratio()
    # é um limite superior garantido (sempre >= ratio() real) e muito mais
    # barato de computar. Se nem o limite superior bate o threshold, o par
    # não pode ser duplicado — pula o cálculo caro sem perder nenhum
    # verdadeiro positivo. Isso é o que torna dedup em massa viável: a
    # esmagadora maioria dos pares comparados NÃO é duplicada, então a
    # maior parte do custo vira só esse filtro rápido.
    matcher = SequenceMatcher(None, a, b)
    if matcher.quick_ratio() < SIMILARITY_THRESHOLD:
        return None

    score = matcher.ratio()
    if score >= SIMILARITY_THRESHOLD:
        return _make_exception(p1, p2, score)
    return None


def _compare_bucket_full(bucket: list[CanonicalProduct]) -> list[ExceptionRecord]:
    exceptions = []
    n = len(bucket)
    for i in range(n):
        for j in range(i + 1, n):
            result = _compare_pair(bucket[i], bucket[j])
            if result:
                exceptions.append(result)
    return exceptions


def _compare_bucket_sorted_neighborhood(bucket: list[CanonicalProduct]) -> list[ExceptionRecord]:
    """Baldes grandes usam Jaccard de tokens (barato) em vez de SequenceMatcher
    (caro), dentro de uma janela de vizinhos ordenados alfabeticamente."""
    exceptions = []
    ordered = sorted(bucket, key=lambda p: p.description)
    token_sets = [set(p.description.split()) for p in ordered]
    n = len(ordered)

    for i in range(n):
        for j in range(i + 1, min(i + 1 + SORTED_NEIGHBORHOOD_WINDOW, n)):
            p1, p2 = ordered[i], ordered[j]
            if p1.sku == p2.sku:
                continue
            if _measures_conflict(p1.description, p2.description):
                continue
            a_tokens, b_tokens = token_sets[i], token_sets[j]
            if not a_tokens or not b_tokens:
                continue
            union = a_tokens | b_tokens
            score = len(a_tokens & b_tokens) / len(union) if union else 0.0
            if score >= JACCARD_SIMILARITY_THRESHOLD:
                exceptions.append(_make_exception(p1, p2, score))

    return exceptions


def find_probable_duplicates(products: list[CanonicalProduct]) -> list[ExceptionRecord]:
    """Agrupa por blocking key; compara exaustivamente baldes pequenos e usa
    sorted neighborhood em baldes grandes."""
    buckets: dict[str, list[CanonicalProduct]] = defaultdict(list)
    for p in products:
        if not p.description:
            continue
        buckets[_blocking_key(p)].append(p)

    exceptions: list[ExceptionRecord] = []
    for bucket in buckets.values():
        if len(bucket) <= 1:
            continue
        if len(bucket) <= FULL_COMPARISON_BUCKET_LIMIT:
            exceptions.extend(_compare_bucket_full(bucket))
        else:
            exceptions.extend(_compare_bucket_sorted_neighborhood(bucket))

    return exceptions
