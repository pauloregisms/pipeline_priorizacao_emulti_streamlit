"""Etapa 13: compila um relatório Markdown com os principais artefatos do experimento."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.utils import setup_logging, stage_dir


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = common_parser("Gera relatório resumido de uma execução do pipeline.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("13_generate_report")
    root = stage_dir(config, args.run_id, "13_report")
    run_root = root.parent
    qc = _read_json(run_root / "03_quality_control" / "quality_summary.json")
    extraction = _read_json(run_root / "08_extraction_validation" / "validation_summary.json")
    priority = _read_json(run_root / "05_priority" / "priority_metadata.json")
    modeling_path = run_root / "10_modeling" / "modeling_summary.csv"
    modeling = pd.read_csv(modeling_path) if modeling_path.exists() else pd.DataFrame()
    priority_view = _read_json(run_root / "14_priority_view" / "priority_view_manifest.json")
    primary_extraction = next((item for item in extraction.get("extractors", []) if item.get("extractor") == "primary"), {})

    lines = [
        "# Relatório automático do pipeline sintético e-Multi",
        "",
        f"**Execução:** `{args.run_id}`",
        f"**Status dos parâmetros:** {config['project'].get('parameter_status', 'não informado')}",
        "",
        "## Delimitação",
        "Este relatório descreve uma prova de conceito inteiramente sintética. As métricas representam recuperação de uma prioridade de referência simulada, não validade clínica ou desempenho em pacientes reais.",
        "",
        "## Controle de qualidade",
        f"- Falhas estruturais: {qc.get('profiles', {}).get('n_failed', 'não disponível')}",
        f"- Falhas psicométricas: {qc.get('psychometrics', {}).get('n_failed', 'não disponível')}",
        f"- Alfa de Cronbach (inspeção sintética): {qc.get('psychometrics', {}).get('cronbach_alpha', 'não disponível')}",
        "",
        "## Prioridade de referência simulada",
        f"- Distribuição: {priority.get('class_distribution', 'não disponível')}",
        "",
        "## Extração",
        f"- F1 macro de presença contra a referência do gerador: {primary_extraction.get('macro_f1', 'não disponível')}",
        f"- F1 micro de presença: {primary_extraction.get('micro_f1', 'não disponível')}",
        f"- Taxa de omissão: {primary_extraction.get('omission_rate', 'não disponível')}",
        f"- Taxa de alucinação: {primary_extraction.get('hallucination_rate', 'não disponível')}",
        "- A validação com anotadores humanos deve ser reportada separadamente quando os arquivos de dupla anotação estiverem disponíveis.",
        "",
        "## Modelagem",
    ]
    if modeling.empty:
        lines.append("A etapa de modelagem ainda não foi executada.")
    else:
        lines.append(modeling.to_markdown(index=False))
    lines.extend([
        "",
        "## Tabela simplificada de classificação",
        (
            f"- Modelo selecionado: {priority_view.get('selected_model', 'não disponível')} "
            f"({priority_view.get('model_selection_criterion', 'critério não disponível')})."
            if priority_view else "- A tabela simplificada ainda não foi gerada."
        ),
        (
            f"- Artefato: `14_priority_view/{priority_view.get('csv', 'classification_queue.csv')}`."
            if priority_view else ""
        ),
        "- A tabela contém apenas perfis sintéticos e não deve ser interpretada como fila clínica.",
        "",
        "## Interpretação e limites",
        "Resultados elevados podem decorrer de relações estruturais programadas no próprio gerador. Antes de qualquer uso assistencial seriam necessários dados reais autorizados, validação externa, avaliação de equidade, governança e estudo de impacto.",
    ])
    report_path = root / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Relatório salvo em %s", report_path)


if __name__ == "__main__":
    main()
