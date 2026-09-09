#!/usr/bin/env python3
"""
Uso:
    python cli.py sample_data/produtos_exemplo.csv --out output/
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.pipeline import run_pipeline_csv  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="T-Acelerar (módulo Winthor) — pipeline de produtos")
    parser.add_argument("input_csv", help="Caminho do CSV de produtos")
    parser.add_argument("--out", default="output", help="Diretório de saída")
    args = parser.parse_args()

    result = run_pipeline_csv(args.input_csv)
    result.save(args.out)

    print(f"Registros processados: {len(result.products)}")
    print(f"Exceções geradas:      {len(result.exceptions)}")
    print("\nRelatório de qualidade:")
    print(json.dumps(result.report, ensure_ascii=False, indent=2))
    print(f"\nSaída gravada em: {args.out}/")


if __name__ == "__main__":
    main()
