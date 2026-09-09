"""
Validadores de documento brasileiro (CNPJ/CPF) — dígito verificador via
módulo 11, algoritmo padrão da Receita Federal. Genérico, usado pra
validar Cliente/Fornecedor extraído de SPED/XML — mesmo princípio do
validate_ean13 em app/validation/rules.py (checksum real, não regex de
tamanho).
"""

from __future__ import annotations

import re


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _mod11_digit(digits: str, weights: list[int]) -> int:
    total = sum(int(d) * w for d, w in zip(digits, weights))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def validate_cpf(value: str) -> bool:
    digits = _only_digits(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False

    dv1 = _mod11_digit(digits[:9], [10, 9, 8, 7, 6, 5, 4, 3, 2])
    dv2 = _mod11_digit(digits[:9] + str(dv1), [11, 10, 9, 8, 7, 6, 5, 4, 3, 2])
    return digits[9:] == f"{dv1}{dv2}"


def validate_cnpj(value: str) -> bool:
    digits = _only_digits(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False

    dv1 = _mod11_digit(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    dv2 = _mod11_digit(digits[:12] + str(dv1), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return digits[12:] == f"{dv1}{dv2}"
