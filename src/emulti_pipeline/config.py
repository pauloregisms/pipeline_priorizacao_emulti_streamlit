"""Leitura e validação leve da configuração do pipeline."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Combina dicionários recursivamente, preservando valores não sobrescritos."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _load_config(path: Path, visited: set[Path]) -> dict[str, Any]:
    """Carrega YAML e resolve opcionalmente ``extends`` de forma rastreável."""
    path = path.resolve()
    if path in visited:
        cycle = " -> ".join(str(item) for item in [*visited, path])
        raise ValueError(f"Foi detectado ciclo de herança entre arquivos YAML: {cycle}")
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {path}")

    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("A configuração YAML deve conter um objeto/dicionário no nível superior.")

    parent_reference = config.pop("extends", None)
    if parent_reference is None:
        return config
    if not isinstance(parent_reference, str) or not parent_reference.strip():
        raise ValueError("A chave YAML 'extends' deve apontar para um arquivo não vazio.")

    parent_path = Path(parent_reference)
    if not parent_path.is_absolute():
        parent_path = path.parent / parent_path
    parent_config = _load_config(parent_path, visited | {path})
    return _deep_merge(parent_config, config)


def load_config(path: str | Path) -> dict[str, Any]:
    """Lê um YAML, resolve ``extends`` e devolve uma cópia independente.

    O mecanismo permite criar configurações de provedor, como ``config/gemini.yaml``,
    sem duplicar todos os parâmetros científicos de ``config/base.yaml``.
    """
    return copy.deepcopy(_load_config(Path(path), set()))
