# -*- coding: utf-8 -*-
"""Executa configurações do pipeline de priorização e-Multi no Google Colab.

O roteiro é orientado por YAML. Ele não possui modos vinculados a um provedor,
a um modelo ou a uma demonstração específica. A mesma versão pode executar um
cenário local, um teste curto com API ou um experimento completo apenas pela
troca do arquivo informado em ``--config``.

Uso recomendado no Google Colab
-------------------------------
1. Coloque no Google Drive o ZIP atual do projeto.
2. Envie este roteiro e o YAML desejado para ``/content``.
3. Execute, por exemplo:

   %run /content/pipeline_priorizacao_emulti_colab.py \
       --config /content/demo.yaml

O YAML pode definir uma seção opcional ``execution`` com ``action``, ``run_id``,
``stop_after``, ``models``, ``run_tests``, ``validate_streamlit_artifacts``,
``replace_existing_run``, ``save_results`` e ``package_project``.

Também é possível sobrescrever parâmetros sem editar arquivos:

   %run /content/pipeline_priorizacao_emulti_colab.py \
       --config config/llm_smoke.yaml \
       --backend-narrativas "openai" \
       --backend-extracao "openai" \
       --modelo-narrativas "IDENTIFICADOR_DO_MODELO" \
       --modelo-extracao "IDENTIFICADOR_DO_MODELO" \
       --variavel-chave-narrativas "OPENAI_API_KEY" \
       --variavel-chave-extracao "OPENAI_API_KEY" \
       --temperatura-narrativas 0.7 \
       --temperatura-extracao 0.0

Para qualquer chave YAML, use ``--parametro caminho.chave=valor``. Exemplos:

   --parametro extraction.stability.enabled=false
   --parametro modeling.n_jobs=1
   --parametro narrative.llm.max_output_tokens=700

Segurança metodológica
----------------------
Todos os dados processados por este roteiro devem ser sintéticos. Os resultados
constituem uma prova de conceito, sem validade clínica ou uso assistencial.
Segredos são lidos do ambiente ou solicitados por entrada oculta. Nunca devem
ser escritos no YAML, no notebook ou no projeto.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tomllib
import zipfile
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Any, Iterable, Mapping


# ---------------------------------------------------------------------------
# Valores padrão. Todos podem ser substituídos pela linha de comando ou YAML.
# ---------------------------------------------------------------------------

PROJECT_ZIP = Path(
    "/content/drive/MyDrive/Projetos/eMulti/"
    "pipeline_priorizacao_emulti-streamlit-demo.zip"
)
CONFIG_REFERENCE = Path("demo.yaml")
DRIVE_OUTPUT_DIR = Path("/content/drive/MyDrive/Projetos/eMulti/resultados_colab")
WORKSPACE_PARENT = Path("/content")

EXPECTED_PYTHON_VERSION = "3.12.13"
REQUIRE_EXACT_PYTHON = False
INSTALL_DEPENDENCIES = True
SAVE_RESULTS = True

LOCAL_PROVIDERS = frozenset({"template", "rules", "local", "random", "synthetic"})
VALID_ACTIONS = ("executar", "validar", "smoke", "llm_smoke")


def timestamp() -> str:
    """Retorna uma marca temporal adequada para arquivos e execuções."""

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run_command(
    command: Iterable[str | Path],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Executa um comando, registra a chamada e interrompe se houver falha."""

    normalized = [str(item) for item in command]
    print(f"\n$ {shlex.join(normalized)}", flush=True)
    subprocess.run(normalized, cwd=cwd, env=env, check=True)


def mount_google_drive(skip_drive: bool) -> None:
    """Monta o Google Drive quando o roteiro estiver em um notebook Colab."""

    if skip_drive:
        print("Montagem do Google Drive ignorada por opção de execução.")
        return

    try:
        from google.colab import drive  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "O módulo google.colab não está disponível. Execute no Colab ou use "
            "--sem-drive para uma verificação local."
        ) from exc
    drive.mount("/content/drive")


def check_python_version(strict: bool) -> None:
    """Registra a versão do Python e, opcionalmente, exige a versão planejada."""

    current = platform.python_version()
    print(f"Python em uso: {current}")
    print(f"Python registrado no protocolo: {EXPECTED_PYTHON_VERSION}")
    if current == EXPECTED_PYTHON_VERSION:
        return

    message = (
        f"O ambiente usa Python {current}, enquanto o protocolo informa "
        f"Python {EXPECTED_PYTHON_VERSION}. O pipeline aceita versões entre 3.10 "
        "e 3.13, mas a versão efetivamente utilizada deve constar no relatório."
    )
    if strict:
        raise RuntimeError(message)
    print(f"AVISO: {message}")


def _safe_member_destination(root: Path, member_name: str) -> Path:
    """Impede que um membro do ZIP seja extraído fora da pasta temporária."""

    destination = (root / member_name).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Caminho inseguro encontrado no ZIP: {member_name}") from exc
    return destination


def extract_project(zip_path: Path, workspace_parent: Path) -> Path:
    """Extrai o ZIP em uma pasta temporal e identifica a raiz do projeto."""

    zip_path = zip_path.expanduser().resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(f"Arquivo do projeto não encontrado: {zip_path}")
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"O arquivo informado não é um ZIP válido: {zip_path}")

    workspace_parent.mkdir(parents=True, exist_ok=True)
    workspace = workspace_parent / f"emulti_colab_{timestamp()}"
    workspace.mkdir(parents=False, exist_ok=False)

    print(f"Extraindo o projeto para: {workspace}")
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            _safe_member_destination(workspace, member.filename)
        archive.extractall(workspace)

    candidates = [
        path.parent
        for path in workspace.rglob("streamlit_app.py")
        if (path.parent / "pyproject.toml").is_file()
        and (path.parent / "scripts" / "run_pipeline.py").is_file()
        and (path.parent / "config" / "base.yaml").is_file()
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "Não foi possível identificar uma única raiz do projeto atual. "
            f"Candidatos: {[str(item) for item in candidates]}"
        )

    project_dir = candidates[0].resolve()
    print(f"Raiz do projeto identificada: {project_dir}")
    return project_dir


def install_project(project_dir: Path) -> None:
    """Instala o projeto e todos os extras opcionais declarados por ele."""

    pyproject_path = project_dir / "pyproject.toml"
    metadata = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    optional = metadata.get("project", {}).get("optional-dependencies", {})
    extras = sorted(str(name) for name in optional)
    target = f".[{','.join(extras)}]" if extras else "."
    print(
        "Extras opcionais identificados: "
        + (", ".join(extras) if extras else "nenhum")
    )
    run_command(
        [sys.executable, "-m", "pip", "install", "-q", "-e", target],
        cwd=project_dir,
    )


def locate_configuration(reference: Path, project_dir: Path) -> Path:
    """Localiza um YAML externo ou um YAML já incluído no projeto."""

    reference = reference.expanduser()
    candidates: list[Path] = []
    if reference.is_absolute():
        candidates.append(reference)
    else:
        candidates.extend(
            [
                Path.cwd() / reference,
                project_dir / reference,
                project_dir / "config" / reference,
                project_dir / "config" / reference.name,
            ]
        )

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            print(f"Configuração selecionada: {resolved}")
            return resolved

    raise FileNotFoundError(
        f"Configuração {reference!s} não encontrada. Foram examinados: "
        + ", ".join(str(item) for item in seen)
    )


def stage_configuration(source: Path, project_dir: Path) -> Path:
    """Coloca YAML externo ao lado de base.yaml para resolver herança relativa."""

    config_dir = (project_dir / "config").resolve()
    source = source.resolve()
    if source.parent == config_dir:
        return source

    suffix = source.suffix if source.suffix.lower() in {".yaml", ".yml"} else ".yaml"
    destination = config_dir / f"colab_input_{timestamp()}{suffix}"
    shutil.copy2(source, destination)
    print(f"Cópia de trabalho da configuração: {destination}")
    return destination


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Combina dicionários recursivamente sem modificar os objetos de origem."""

    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _load_yaml_tree(path: Path, visited: set[Path] | None = None) -> dict[str, Any]:
    """Lê YAML e resolve ``extends`` seguindo a mesma regra do pipeline."""

    import yaml

    path = path.resolve()
    visited = set() if visited is None else visited
    if path in visited:
        raise ValueError(f"Ciclo detectado na herança YAML envolvendo {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo YAML não encontrado: {path}")

    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise ValueError(f"O YAML precisa conter um dicionário no nível superior: {path}")

    content = copy.deepcopy(content)
    parent_reference = content.pop("extends", None)
    if parent_reference is None:
        return content
    if not isinstance(parent_reference, str) or not parent_reference.strip():
        raise ValueError("A chave extends deve conter o caminho de um arquivo YAML.")

    parent_path = Path(parent_reference)
    if not parent_path.is_absolute():
        parent_path = path.parent / parent_path
    parent = _load_yaml_tree(parent_path, visited | {path})
    return _deep_merge(parent, content)


def _parse_override_value(raw_value: str) -> Any:
    """Interpreta o valor de uma sobrescrita com a sintaxe escalar do YAML."""

    import yaml

    return yaml.safe_load(raw_value)


def set_nested_value(configuration: dict[str, Any], dotted_path: str, value: Any) -> None:
    """Define uma chave arbitrária usando caminho como ``grupo.subgrupo.chave``."""

    keys = [item.strip() for item in dotted_path.split(".") if item.strip()]
    if not keys:
        raise ValueError("O caminho da sobrescrita não pode ser vazio.")

    current: dict[str, Any] = configuration
    for key in keys[:-1]:
        existing = current.get(key)
        if existing is None:
            current[key] = {}
        elif not isinstance(existing, dict):
            raise ValueError(
                f"Não é possível criar uma chave dentro de {key!r}: valor atual não é um dicionário."
            )
        current = current[key]
    current[keys[-1]] = value


def _activate_llm_block(
    configuration: dict[str, Any], section_name: str
) -> dict[str, Any]:
    """Ativa o provedor genérico ``llm`` e retorna seu bloco de configuração."""

    section = configuration.setdefault(section_name, {})
    if not isinstance(section, dict):
        raise ValueError(f"A seção {section_name!r} deve ser um dicionário YAML.")
    section["provider"] = "llm"
    block = section.setdefault("llm", {})
    if not isinstance(block, dict):
        raise ValueError(f"O bloco {section_name}.llm deve ser um dicionário.")
    return block


def apply_command_line_overrides(
    configuration: dict[str, Any], args: argparse.Namespace
) -> dict[str, Any]:
    """Aplica opções amigáveis e sobrescritas genéricas à configuração."""

    result = copy.deepcopy(configuration)

    if args.provider_narrativas is not None:
        result.setdefault("narrative", {})["provider"] = args.provider_narrativas
    if args.provider_extracao is not None:
        result.setdefault("extraction", {})["provider"] = args.provider_extracao

    if args.backend_narrativas is not None:
        _activate_llm_block(result, "narrative")["backend"] = args.backend_narrativas
    if args.backend_extracao is not None:
        _activate_llm_block(result, "extraction")["backend"] = args.backend_extracao
    if args.variavel_chave_narrativas is not None:
        _activate_llm_block(result, "narrative")["api_key_env"] = args.variavel_chave_narrativas
    if args.variavel_chave_extracao is not None:
        _activate_llm_block(result, "extraction")["api_key_env"] = args.variavel_chave_extracao

    if args.modelo_narrativas is not None:
        block = _activate_llm_block(result, "narrative")
        block["model_id"] = args.modelo_narrativas
        if args.id_gerador is None:
            block["generator_id"] = f"llm-{block.get('backend', 'backend')}-{args.modelo_narrativas}"
    if args.modelo_extracao is not None:
        block = _activate_llm_block(result, "extraction")
        block["model_id"] = args.modelo_extracao
        if args.id_extrator is None:
            generated_id = f"llm-{block.get('backend', 'backend')}-{args.modelo_extracao}-extractor"
            block["extractor_id"] = generated_id
            result["extraction"]["extractor_id"] = generated_id

    if args.temperatura_narrativas is not None:
        _activate_llm_block(result, "narrative")["temperature"] = args.temperatura_narrativas
    if args.temperatura_extracao is not None:
        _activate_llm_block(result, "extraction")["temperature"] = args.temperatura_extracao
    if args.id_gerador is not None:
        _activate_llm_block(result, "narrative")["generator_id"] = args.id_gerador
    if args.id_extrator is not None:
        _activate_llm_block(result, "extraction")["extractor_id"] = args.id_extrator
        result.setdefault("extraction", {})["extractor_id"] = args.id_extrator
    if args.n_registros is not None:
        result.setdefault("simulation", {})["n_records"] = args.n_registros
    if args.seed is not None:
        result.setdefault("simulation", {})["base_seed"] = args.seed
        result.setdefault("modeling", {})["random_state"] = args.seed

    for expression in args.overrides:
        if "=" not in expression:
            raise ValueError(
                f"Sobrescrita inválida {expression!r}. Use caminho.chave=valor."
            )
        path, raw_value = expression.split("=", 1)
        set_nested_value(result, path.strip(), _parse_override_value(raw_value.strip()))

    return result


def write_resolved_configuration(
    configuration: dict[str, Any], project_dir: Path
) -> Path:
    """Registra o YAML completamente resolvido que será entregue ao pipeline."""

    import yaml

    destination = project_dir / "config" / f"colab_resolved_{timestamp()}.yaml"
    destination.write_text(
        yaml.safe_dump(configuration, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Configuração resolvida para execução: {destination}")
    return destination


def _execution_value(configuration: Mapping[str, Any], key: str, default: Any) -> Any:
    execution = configuration.get("execution", {})
    if not isinstance(execution, Mapping):
        raise ValueError("A seção execution deve ser um dicionário YAML.")
    return execution.get(key, default)


def resolve_action(configuration: Mapping[str, Any], cli_action: str | None) -> str:
    """Escolhe entre executar o pipeline e validar artefatos já existentes."""

    raw = cli_action or str(_execution_value(configuration, "action", "executar"))
    aliases = {
        "run": "executar",
        "execute": "executar",
        "validate": "validar",
        "llm-smoke": "llm_smoke",
    }
    action = aliases.get(raw.strip().lower(), raw.strip().lower())
    if action not in VALID_ACTIONS:
        raise ValueError(
            f"Ação desconhecida {raw!r}. Use executar, validar, smoke ou llm_smoke."
        )
    return action


def resolve_run_id(configuration: Mapping[str, Any], cli_run_id: str | None) -> str:
    """Obtém um identificador de execução a partir da CLI, YAML ou relógio."""

    run_id = cli_run_id or str(
        _execution_value(configuration, "run_id", f"execucao_{timestamp()}")
    )
    run_id = run_id.strip()
    if not run_id or run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
        raise ValueError(f"run_id inválido: {run_id!r}")
    return run_id


def resolve_run_root(
    project_dir: Path, configuration: Mapping[str, Any], run_id: str
) -> Path:
    """Calcula a pasta de artefatos sem pressupor o nome demo_artifacts."""

    paths = configuration.get("paths", {})
    if not isinstance(paths, Mapping):
        raise ValueError("A seção paths deve ser um dicionário YAML.")
    artifacts_reference = Path(str(paths.get("artifacts_dir", "artifacts"))).expanduser()
    artifacts_root = (
        artifacts_reference
        if artifacts_reference.is_absolute()
        else project_dir / artifacts_reference
    ).resolve()
    run_root = (artifacts_root / run_id).resolve()
    if run_root.parent != artifacts_root:
        raise ValueError(f"Pasta de execução inesperada: {run_root}")
    return run_root


def _read_secret_from_colab(name: str) -> str | None:
    """Tenta recuperar um segredo homônimo cadastrado no Google Colab."""

    try:
        from google.colab import userdata  # type: ignore[import-not-found]

        value = userdata.get(name)
    except Exception:
        return None
    return str(value).strip() if value else None


def required_secret_names(configuration: Mapping[str, Any]) -> list[str]:
    """Descobre variáveis secretas declaradas pelos provedores ativos."""

    names: set[str] = set()
    for section_name in ("narrative", "extraction"):
        section = configuration.get(section_name, {})
        if not isinstance(section, Mapping):
            continue
        provider = str(section.get("provider", "")).strip().lower()
        if not provider or provider in LOCAL_PROVIDERS:
            continue
        provider_config = section.get(provider, {})
        if isinstance(provider_config, Mapping):
            name = str(provider_config.get("api_key_env", "")).strip()
            if name:
                names.add(name)

    configured_names = _execution_value(configuration, "secret_env_vars", [])
    if configured_names:
        if not isinstance(configured_names, list):
            raise ValueError("execution.secret_env_vars deve ser uma lista.")
        names.update(str(name).strip() for name in configured_names if str(name).strip())
    return sorted(names)


def validate_llm_configuration(configuration: Mapping[str, Any]) -> None:
    """Falha cedo quando um backend LLM ativo ainda contém placeholders."""

    for section_name in ("narrative", "extraction"):
        section = configuration.get(section_name, {})
        if not isinstance(section, Mapping):
            raise ValueError(f"A seção {section_name!r} deve ser um dicionário YAML.")
        if str(section.get("provider", "")).strip().lower() != "llm":
            continue
        block = section.get("llm", {})
        if not isinstance(block, Mapping):
            raise ValueError(f"O bloco {section_name}.llm deve ser um dicionário YAML.")
        missing = []
        for key in ("backend", "model_id", "api_key_env"):
            value = str(block.get(key, "")).strip()
            if not value or value.upper().startswith("CONFIGURE_"):
                missing.append(f"{section_name}.llm.{key}")
        if missing:
            raise ValueError(
                "A configuração LLM ainda possui campos pendentes: "
                + ", ".join(missing)
                + ". Defina-os no YAML ou pelos parâmetros do executor."
            )


def require_llm_api_keys(configuration: Mapping[str, Any]) -> None:
    """Carrega ou solicita as chaves declaradas pelos backends LLM ativos."""

    for name in required_secret_names(configuration):
        if os.environ.get(name, "").strip():
            print(f"Variável secreta {name} já está definida no ambiente.")
            continue
        value = _read_secret_from_colab(name)
        if value:
            os.environ[name] = value
            print(f"Variável secreta {name} carregada dos Secrets do Colab.")
            continue
        value = getpass(f"Informe {name}. A entrada permanecerá oculta: ").strip()
        if not value:
            raise RuntimeError(f"O segredo necessário {name} não foi informado.")
        os.environ[name] = value


def remove_previous_run(project_dir: Path, run_root: Path) -> None:
    """Remove somente uma execução anterior da cópia temporária do projeto."""

    if not run_root.exists():
        return
    try:
        run_root.relative_to(project_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(
            "Por segurança, o roteiro não remove execuções localizadas fora da cópia "
            f"temporária do projeto: {run_root}"
        ) from exc
    if run_root == project_dir.resolve() or run_root.parent == project_dir.resolve():
        raise RuntimeError(f"Destino amplo demais para remoção: {run_root}")
    print(f"Removendo somente a execução anterior da cópia temporária: {run_root}")
    shutil.rmtree(run_root)


def execute_pipeline(
    project_dir: Path,
    *,
    config_path: Path,
    run_id: str,
    stop_after: str | None,
    models: str,
    skip_explanations: bool,
    skip_report: bool,
) -> None:
    """Executa o orquestrador do projeto com parâmetros independentes do provedor."""

    command: list[str | Path] = [
        sys.executable,
        "scripts/run_pipeline.py",
        "--config",
        config_path.relative_to(project_dir),
        "--run-id",
        run_id,
        "--models",
        models,
    ]
    if stop_after:
        command.extend(["--stop-after", stop_after])
    if skip_explanations:
        command.append("--skip-explanations")
    if skip_report:
        command.append("--skip-report")
    run_command(command, cwd=project_dir, env=os.environ.copy())


def execute_selected_mode(
    project_dir: Path,
    *,
    config_path: Path,
    configuration: Mapping[str, Any],
    mode: str,
    run_id: str,
    run_root: Path,
    stop_after: str | None,
    models: str,
    skip_explanations: bool,
    skip_report: bool,
    replace_existing: bool,
) -> None:
    """Executa o modo escolhido usando o arquivo YAML recebido como parâmetro."""

    if mode == "validar":
        return
    if run_root.exists():
        if replace_existing:
            remove_previous_run(project_dir, run_root)
        else:
            raise FileExistsError(
                f"A execução {run_id!r} já existe. Altere o run_id ou defina "
                "execution.replace_existing_run: true no YAML."
            )

    validate_llm_configuration(configuration)
    require_llm_api_keys(configuration)
    execute_pipeline(
        project_dir,
        config_path=config_path,
        run_id=run_id,
        stop_after=stop_after,
        models=models,
        skip_explanations=skip_explanations,
        skip_report=skip_report,
    )


def run_tests(project_dir: Path) -> None:
    """Executa os contratos automatizados presentes no projeto."""

    run_command([sys.executable, "-m", "pytest", "-q"], cwd=project_dir)


def validate_result_artifacts(
    project_dir: Path,
    run_root: Path,
    require_streamlit_bundle: bool,
) -> dict[str, Any] | None:
    """Valida a pasta produzida e, quando solicitado, os artefatos do Streamlit."""

    if not run_root.is_dir():
        raise FileNotFoundError(f"Pasta de resultados não encontrada: {run_root}")
    if not require_streamlit_bundle:
        files = sum(1 for path in run_root.rglob("*") if path.is_file())
        print(f"Pasta de resultados encontrada com {files} arquivo(s): {run_root}")
        return None

    src_dir = project_dir / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from emulti_pipeline import demo as artifact_reader

    missing = artifact_reader.validate_demo_root(run_root)
    if missing:
        raise FileNotFoundError(
            "A execução não contém todos os artefatos exigidos pelo Streamlit: "
            + ", ".join(missing)
        )
    bundle = artifact_reader.load_demo_bundle(run_root)
    print("\nArtefatos compatíveis com a interface Streamlit.")
    print(f"Perfis sintéticos: {len(bundle['profiles'])}")
    print(f"Perfis no teste final: {len(bundle['classification'])}")
    print(f"Conjuntos analíticos: {bundle['modeling_summary']['dataset'].nunique()}")
    print(f"Modelos comparados: {bundle['modeling_summary']['model'].nunique()}")
    return bundle


def display_results(run_root: Path) -> None:
    """Apresenta a fila final ou um resumo da etapa mais avançada disponível."""

    queue_path = run_root / "14_priority_view" / "classification_queue.csv"
    if queue_path.is_file():
        import pandas as pd

        queue = pd.read_csv(queue_path)
        print("\nPrimeiros registros da classificação final:")
        try:
            from IPython.display import display

            display(queue.head(30))
        except ImportError:
            print(queue.head(30).to_string(index=False))
        return

    validation_path = run_root / "08_extraction_validation" / "validation_summary.json"
    if validation_path.is_file():
        summary = json.loads(validation_path.read_text(encoding="utf-8"))
        print("\nResumo da validação da extração:")
        print(json.dumps(summary, ensure_ascii=False, indent=2)[:8000])
        return

    manifest_path = run_root / "run_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        print("\nManifesto da execução:")
        print(json.dumps(manifest, ensure_ascii=False, indent=2)[:4000])
        return

    print(f"Não foi encontrada uma visualização resumida em {run_root}")


def zip_tree(source: Path, destination: Path, archive_root: str) -> None:
    """Compacta uma árvore preservando um diretório-raiz identificável."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = path.relative_to(source)
            archive.write(path, arcname=(Path(archive_root) / relative).as_posix())


def _is_inside(relative: Path, parent: Path) -> bool:
    try:
        relative.relative_to(parent)
        return True
    except ValueError:
        return False


def build_project_archive(project_dir: Path, run_root: Path, destination: Path) -> None:
    """Cria um pacote implantável contendo apenas a execução selecionada."""

    try:
        active_run = run_root.resolve().relative_to(project_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(
            "Não é possível incorporar ao projeto uma execução externa à sua raiz."
        ) from exc
    if active_run.parent == Path("."):
        raise RuntimeError(
            "Para empacotar o projeto, paths.artifacts_dir deve apontar para uma "
            "subpasta própria, como artifacts ou demo_artifacts."
        )

    excluded_parts = {
        ".git",
        ".venv",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
    }
    generated_roots = {
        Path("artifacts"),
        Path("demo_artifacts"),
        active_run.parent,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in project_dir.rglob("*") if item.is_file()):
            relative = path.relative_to(project_dir)
            if any(part in excluded_parts for part in relative.parts):
                continue
            if any(part.endswith(".egg-info") for part in relative.parts):
                continue
            if any(_is_inside(relative, root) for root in generated_roots):
                if not _is_inside(relative, active_run):
                    continue
            archive.write(
                path,
                arcname=(Path("pipeline_priorizacao_emulti-main") / relative).as_posix(),
            )


def save_result_files(
    project_dir: Path,
    run_root: Path,
    output_dir: Path,
    *,
    package_project: bool,
) -> list[Path]:
    """Salva artefatos com marca temporal sem apagar arquivos anteriores."""

    if not run_root.is_dir():
        raise FileNotFoundError(f"Pasta de resultados não encontrada: {run_root}")
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = timestamp()
    artifacts_zip = output_dir / f"artefatos_{run_root.name}_{suffix}.zip"
    zip_tree(run_root, artifacts_zip, run_root.name)
    saved = [artifacts_zip]

    if package_project:
        project_zip = output_dir / f"pipeline_emulti_{run_root.name}_{suffix}.zip"
        build_project_archive(project_dir, run_root, project_zip)
        saved.append(project_zip)

    print("\nArquivos preservados:")
    for path in saved:
        print(f"- {path}")
    return saved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa qualquer configuração YAML do pipeline e-Multi no Colab."
    )
    parser.add_argument("--config", type=Path, default=CONFIG_REFERENCE)
    parser.add_argument("--acao", choices=VALID_ACTIONS, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--zip-path", type=Path, default=PROJECT_ZIP)
    parser.add_argument("--output-dir", type=Path, default=DRIVE_OUTPUT_DIR)
    parser.add_argument("--workspace-dir", type=Path, default=WORKSPACE_PARENT)
    parser.add_argument("--provider-narrativas", default=None)
    parser.add_argument("--provider-extracao", default=None)
    parser.add_argument("--backend-narrativas", default=None)
    parser.add_argument("--backend-extracao", default=None)
    parser.add_argument("--modelo-narrativas", default=None)
    parser.add_argument("--modelo-extracao", default=None)
    parser.add_argument("--variavel-chave-narrativas", default=None)
    parser.add_argument("--variavel-chave-extracao", default=None)
    parser.add_argument("--temperatura-narrativas", type=float, default=None)
    parser.add_argument("--temperatura-extracao", type=float, default=None)
    parser.add_argument("--id-gerador", default=None)
    parser.add_argument("--id-extrator", default=None)
    parser.add_argument("--n-registros", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--parar-apos", default=None)
    parser.add_argument("--modelos", default=None)
    parser.add_argument(
        "--parametro",
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="CAMINHO=VALOR",
    )
    parser.add_argument("--sem-drive", action="store_true")
    parser.add_argument("--nao-instalar", action="store_true")
    parser.add_argument("--nao-testar", action="store_true")
    parser.add_argument("--nao-salvar", action="store_true")
    parser.add_argument("--exigir-python-exato", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Pipeline sintético de priorização e-Multi")
    print("Executor genérico orientado por configuração YAML.")
    print("Dados exclusivamente sintéticos. Uso somente metodológico.")

    mount_google_drive(args.sem_drive)
    check_python_version(REQUIRE_EXACT_PYTHON or args.exigir_python_exato)
    project_dir = extract_project(args.zip_path, args.workspace_dir)

    if INSTALL_DEPENDENCIES and not args.nao_instalar:
        install_project(project_dir)

    source_config = locate_configuration(args.config, project_dir)
    staged_config = stage_configuration(source_config, project_dir)
    configuration = _load_yaml_tree(staged_config)
    configuration = apply_command_line_overrides(configuration, args)
    resolved_config = write_resolved_configuration(configuration, project_dir)

    action = resolve_action(configuration, args.acao)
    run_id = resolve_run_id(configuration, args.run_id)
    run_root = resolve_run_root(project_dir, configuration, run_id)
    stop_after = args.parar_apos or _execution_value(configuration, "stop_after", None)
    if action in {"smoke", "llm_smoke"} and not stop_after:
        stop_after = "08_validate_extraction.py"
    models = args.modelos or str(_execution_value(configuration, "models", "all"))
    skip_explanations = bool(
        _execution_value(configuration, "skip_explanations", bool(stop_after))
    )
    skip_report = bool(_execution_value(configuration, "skip_report", bool(stop_after)))
    validate_streamlit = bool(
        _execution_value(configuration, "validate_streamlit_artifacts", not stop_after)
    ) and not bool(stop_after)
    run_tests_now = bool(_execution_value(configuration, "run_tests", True))
    replace_existing = bool(
        _execution_value(configuration, "replace_existing_run", False)
    )
    save_results_now = bool(_execution_value(configuration, "save_results", SAVE_RESULTS))
    package_project = bool(
        _execution_value(configuration, "package_project", False)
    ) and not bool(stop_after)

    print(f"Ação: {action}")
    print(f"Execução: {run_id}")
    print(f"Artefatos: {run_root}")
    print(f"Provedor de narrativas: {configuration['narrative']['provider']}")
    print(f"Provedor de extração: {configuration['extraction']['provider']}")

    execute_selected_mode(
        project_dir,
        config_path=resolved_config,
        configuration=configuration,
        mode=action,
        run_id=run_id,
        run_root=run_root,
        stop_after=str(stop_after) if stop_after else None,
        models=models,
        skip_explanations=skip_explanations,
        skip_report=skip_report,
        replace_existing=replace_existing,
    )

    if run_tests_now and not args.nao_testar:
        run_tests(project_dir)

    validate_result_artifacts(
        project_dir,
        run_root,
        require_streamlit_bundle=validate_streamlit,
    )
    display_results(run_root)

    if save_results_now and not args.nao_salvar:
        save_result_files(
            project_dir,
            run_root,
            args.output_dir,
            package_project=package_project,
        )

    print("\nExecução concluída.")
    print(f"Projeto temporário: {project_dir}")
    print(f"Configuração efetivamente usada: {resolved_config}")
    print(f"Artefatos examinados: {run_root}")


if __name__ == "__main__":
    main()
