"""Utilitários de caminho, logs, hash e reprodutibilidade."""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def project_root() -> Path:
    """Resolve a raiz do projeto a partir da localização deste módulo."""
    return Path(__file__).resolve().parents[2]


def resolve_path(path_value: str | Path) -> Path:
    """Resolve caminhos da configuração em relação à raiz do projeto."""
    path = Path(path_value)
    return path if path.is_absolute() else project_root() / path


def run_dir(config: dict[str, Any], run_id: str) -> Path:
    """Retorna o diretório de artefatos de uma execução específica."""
    root = resolve_path(config["paths"]["artifacts_dir"])
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def stage_dir(config: dict[str, Any], run_id: str, stage_name: str) -> Path:
    """Cria e retorna o diretório de uma etapa metodológica."""
    directory = run_dir(config, run_id) / stage_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def setup_logging(stage_name: str) -> logging.Logger:
    """Configura um logger simples, reutilizável por todos os scripts."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # Evita duplicação das mensagens informativas emitidas internamente pelo
    # LiteLLM. Avisos do provedor continuam visíveis, assim como os logs de
    # progresso padronizados pelo próprio pipeline.
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    return logging.getLogger(stage_name)


def json_hash(payload: Any) -> str:
    """Calcula hash SHA-256 de uma estrutura serializável em JSON."""
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    """Calcula SHA-256 de um arquivo sem carregá-lo integralmente na memória."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_tree_snapshot() -> dict[str, Any]:
    """Registra hash do código/configuração e, quando disponível, estado Git."""
    root = project_root()
    selected = []
    for pattern in ("src/**/*.py", "scripts/*.py", "config/*.yaml", "requirements*.txt", "pyproject.toml"):
        selected.extend(root.glob(pattern))
    files = {
        str(path.relative_to(root)): file_sha256(path)
        for path in sorted(set(selected))
        if path.is_file()
    }
    git: dict[str, Any] = {"available": False}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.splitlines()
        git = {"available": True, "commit": commit, "dirty": bool(status), "changed_paths": status}
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return {"tree_hash": json_hash(files), "files": files, "git": git}


def write_json(path: str | Path, payload: Any) -> None:
    """Grava JSON legível, criando diretórios quando necessário."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)


def read_json(path: str | Path) -> Any:
    """Lê arquivo JSON."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_csv(frame: pd.DataFrame, path: str | Path) -> None:
    """Grava CSV UTF-8 preservando valores ausentes padronizados."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8")


def set_global_seed(seed: int) -> None:
    """Fixa sementes dos geradores aleatórios usados diretamente no projeto."""
    random.seed(seed)
    np.random.seed(seed)


def effective_seed(config: dict[str, Any], extra_offset: int = 0) -> int:
    """Combina semente-base, réplica e deslocamento de cenário de maneira explícita."""
    simulation = config["simulation"]
    return int(simulation["base_seed"]) + int(simulation.get("replicate_index", 0)) + int(extra_offset)


def environment_snapshot() -> dict[str, Any]:
    """Captura informações mínimas para reprodutibilidade computacional."""
    versions: dict[str, str] = {}
    for module_name in ["numpy", "pandas", "scipy", "sklearn", "xgboost", "shap", "yaml"]:
        try:
            module = __import__(module_name)
            versions[module_name] = getattr(module, "__version__", "desconhecida")
        except Exception:  # pragma: no cover - depende do ambiente do usuário
            versions[module_name] = "não instalado"

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "libraries": versions,
    }


def sigmoid(value: np.ndarray | float) -> np.ndarray | float:
    """Implementação numericamente estável da função logística."""
    value_array = np.asarray(value, dtype=float)
    clipped = np.clip(value_array, -35, 35)
    result = 1.0 / (1.0 + np.exp(-clipped))
    if np.isscalar(value):
        return float(result)
    return result


def logit(probability: np.ndarray | float, epsilon: float = 1e-6) -> np.ndarray | float:
    """Transformação logit com proteção para probabilidades extremas."""
    p = np.clip(np.asarray(probability, dtype=float), epsilon, 1 - epsilon)
    result = np.log(p / (1 - p))
    if np.isscalar(probability):
        return float(result)
    return result
