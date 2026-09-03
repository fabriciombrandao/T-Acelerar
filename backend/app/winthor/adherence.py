"""
Adherence Engine — aplica o resultado do wizard de aderência (por projeto)
sobre os produtos canônicos, ANTES de considerar um lote pronto para gerar
o arquivo de migração.

Regra central (decidida em conversa com o time): o layout do Winthor é
posicional e fixo — o wizard não remove campo do arquivo. O que ele decide,
por módulo (grupo de campos que reflete um processo de negócio):

  - Se o módulo é aplicável ao cliente E o campo obrigatório está ausente
    -> BLOCKER na Exception Queue (alguém precisa decidir/informar).
  - Se o módulo NÃO é aplicável ao cliente -> aplica o default do módulo
    automaticamente (quando existir), com proveniência "wizard_aderencia".
  - Módulos "sempre_aplicavel" (cadastro básico, fiscal NCM) não passam
    pelo wizard — são obrigatórios para todo cliente, sempre.
  - Módulos "derivado_do_ncm" (PIS/COFINS retido) nunca são perguntados;
    são calculados (ver pis_cofins_monofasico.py).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.canonical.models import CanonicalProduct, ExceptionRecord
from app.winthor.pis_cofins_monofasico import derive_pis_cofins_retido

MODULES_PATH = Path(__file__).resolve().parents[3] / "mappings" / "winthor" / "pcprodut_modules.json"
SEGMENTS_PATH = Path(__file__).resolve().parents[3] / "mappings" / "winthor" / "segments.json"


def load_modules_config(path: str | Path = MODULES_PATH) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def load_segments_config(path: str | Path = SEGMENTS_PATH) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def preset_for_subsegment(segment_id: str, subsegment_id: str,
                           segments_config: dict | None = None) -> dict:
    """Retorna o dict {module_id: bool} pré-marcado para um subsegmento."""
    segments_config = segments_config or load_segments_config()
    for seg in segments_config["segmentos"]:
        if seg["id"] != segment_id:
            continue
        for sub in seg["subsegmentos"]:
            if sub["id"] == subsegment_id:
                return dict(sub["preset"])
    return {}


def is_module_applicable(module: dict, answers: dict) -> bool:
    if module.get("sempre_aplicavel"):
        return True
    if module.get("derivado_do_ncm"):
        return False  # nunca "aplicável" via wizard — é calculado à parte
    return bool(answers.get(module["id"], False))


def apply_adherence(products: list[CanonicalProduct], answers: dict,
                     modules_config: dict | None = None) -> list[ExceptionRecord]:
    """Aplica módulos de aderência a um lote de produtos.

    `answers` é o dict salvo no projeto: {module_id: True/False}, tipicamente
    inicializado a partir de um preset de subsegmento e depois ajustado à mão.

    Muta `products` in-place (preenche defaults em `.extra`) e retorna as
    exceções BLOCKER para campos obrigatórios ausentes em módulo aplicável.
    """
    modules_config = modules_config or load_modules_config()
    exceptions: list[ExceptionRecord] = []

    for product in products:
        # PIS/COFINS retido: sempre derivado do NCM, nunca do wizard.
        product.extra["PISCOFINSRETIDO"] = derive_pis_cofins_retido(product.ncm)
        product.add_provenance(
            field="PISCOFINSRETIDO", origin="derivado_ncm",
            rule="pis_cofins_monofasico", confidence=0.7,
            evidence=product.ncm,
        )

        for module in modules_config["modulos"]:
            if module.get("derivado_do_ncm"):
                continue

            applicable = is_module_applicable(module, answers)

            for field_cfg in module["campos"]:
                field = field_cfg["field"]
                required = field_cfg.get("required_by_layout", False)
                has_value = field in product.extra and product.extra[field] not in (None, "")

                if has_value:
                    continue

                if applicable:
                    if required:
                        exceptions.append(ExceptionRecord(
                            record_id=product.external_id, entity="Product",
                            reason_code="CAMPO_ADERENCIA_AUSENTE",
                            description=(
                                f"Campo '{field}' (módulo '{module['nome']}') é obrigatório "
                                f"pelo layout Winthor e o módulo está marcado como aplicável "
                                f"para este cliente, mas está ausente no cadastro de origem."
                            ),
                            severity="BLOCKER",
                            payload={"field": field, "module": module["id"]},
                        ))
                else:
                    default = field_cfg.get("default_when_not_applicable")
                    if default is not None:
                        product.extra[field] = default
                        product.add_provenance(
                            field=field, origin="wizard_aderencia",
                            rule=f"modulo_nao_aplicavel:{module['id']}",
                            confidence=1.0,
                        )
                    elif required:
                        # Obrigatório pelo layout mas módulo marcado como não aplicável
                        # e sem default configurado — ainda precisa de decisão humana,
                        # só que com severidade menor (é decisão de configuração, não
                        # dado ausente inesperado).
                        exceptions.append(ExceptionRecord(
                            record_id=product.external_id, entity="Product",
                            reason_code="CAMPO_SEM_DEFAULT_CONFIGURADO",
                            description=(
                                f"Campo '{field}' (módulo '{module['nome']}') é obrigatório "
                                f"pelo layout, módulo marcado como não aplicável, mas não há "
                                f"default configurado em pcprodut_modules.json."
                            ),
                            severity="HIGH",
                            payload={"field": field, "module": module["id"]},
                        ))

    return exceptions
