"""Código compartilhado pelos scripts executáveis.

Executar scripts diretamente com ``python scripts/arquivo.py`` exige inserir ``src`` no
PYTHONPATH. Este módulo centraliza essa preparação e os argumentos comuns.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", default="config/base.yaml", help="Caminho para o YAML de configuração.")
    parser.add_argument("--run-id", default="baseline", help="Identificador da execução dentro de artifacts/.")
    return parser
