"""
Extração de Produto a partir do registro 0200 (Cadastro de Item) do SPED.

Diferente de XML de NF-e (item de transação), 0200 já É cadastro — uma
linha por produto, não por venda/compra. COD_ITEM é o código interno da
própria empresa e é CONSISTENTE entre livros fiscais diferentes da mesma
empresa (confirmado: 99 códigos de barra em comum entre SPED Fiscal
ICMS/IPI e SPED Contribuições PIS/COFINS reais, 0 divergência de
COD_ITEM) — ao contrário de COD_PART (0150), não precisa reconciliar
numeração entre arquivos: COD_ITEM sozinho já é a chave de consolidação.
"""

from __future__ import annotations

from app.canonical.models import CanonicalProduct, RecordStatus
from app.sped.parser import parse_sped_records


def extract_produtos_from_sped(paths: list, source_label: str | None = None) -> list[CanonicalProduct]:
    by_key: dict[str, CanonicalProduct] = {}

    for path in paths:
        from pathlib import Path
        path = Path(path)
        records = parse_sped_records(path)

        for campos in records.get("0200", []):
            campos = campos + [""] * (12 - len(campos))
            cod_item, descr_item, cod_barra, _cod_ant_item, unid_inv, \
                _tipo_item, cod_ncm, _ex_ipi, _cod_gen, _cod_lst, \
                _aliq_icms, cest = campos[:12]

            cod_item = cod_item.strip()
            if not cod_item:
                continue

            if cod_item not in by_key:
                product = CanonicalProduct(
                    external_id=cod_item, sku=cod_item,
                    description_raw=descr_item.strip(),
                    description=descr_item.strip(),
                    barcode=cod_barra.strip() or None,
                    ncm=cod_ncm.strip() or None,
                    cest=cest.strip() or None,
                    unit=unid_inv.strip() or None,
                    status=RecordStatus.PARSED,
                    source_file=source_label or path.name,
                )
                product.add_provenance(
                    field="*", origin=f"sped:{path.name}", rule="registro_0200", confidence=1.0,
                )
                by_key[cod_item] = product
            else:
                # Já visto num arquivo anterior — registra a segunda fonte
                # como evidência adicional (não sobrescreve, é o mesmo dado).
                by_key[cod_item].add_provenance(
                    field="*", origin=f"sped:{path.name}",
                    rule="registro_0200_confirmacao", confidence=1.0,
                )

    return list(by_key.values())
