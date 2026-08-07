"""Visualização simplificada da classificação final de perfis sintéticos.

Este módulo consolida artefatos das etapas de perfis, escalas, extração e
modelagem em uma tabela ordenada. A tabela é destinada à inspeção de uma
execução sintética e não deve ser interpretada como fila clínica ou recomendação
assistencial.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .priority import PRIORITY_ORDER, PRIORITY_TO_CODE


# A ordenação é deliberadamente oposta ao código ordinal: a tabela deve iniciar
# pelas categorias de segurança e maior prioridade para facilitar a inspeção.
PRIORITY_DISPLAY_ORDER = {"urgente": 0, "alta": 1, "moderada": 2, "baixa": 3}

_PRIORITY_LABELS = {
    "baixa": "Baixa",
    "moderada": "Moderada",
    "alta": "Alta",
    "urgente": "Urgente",
}

_FUNCTIONAL_LABELS = {
    0: "Ausente",
    1: "Leve",
    2: "Moderado",
    3: "Importante",
}

_GENDER_LABELS = {
    "feminino": "Feminino",
    "masculino": "Masculino",
    "outro_ou_nao_informado": "Outro ou não informado",
}

_MARKER_LABELS = {
    "ideacao_suicida": "Ideação suicida atual",
    "planejamento_suicida": "Planejamento de autoagressão",
    "autoagressao_iminente": "Autoagressão iminente",
    "risco_violencia": "Risco de violência",
    "sintomas_psicoticos": "Sintomas psicóticos",
    "uso_problematico_substancias": "Uso problemático de substâncias",
    "internacao_previa": "Internação prévia",
    "agravamento_recente": "Agravamento recente",
    "suporte_social_baixo": "Suporte social baixo",
}


def _require_columns(frame: pd.DataFrame, required: Iterable[str], source_name: str) -> None:
    """Verifica as colunas mínimas de cada artefato antes de montar a tabela."""
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{source_name} não contém as colunas necessárias: {missing}")


def _label_priority(value: object) -> str:
    """Converte rótulo técnico de prioridade em texto destinado à tabela."""
    normalized = str(value).strip().lower()
    return _PRIORITY_LABELS.get(normalized, str(value))


def _priority_from_prediction(predictions: pd.DataFrame) -> pd.Series:
    """Obtém a prioridade prevista por rótulo ou, como contingência, por código."""
    if "prioridade_prevista" in predictions:
        return predictions["prioridade_prevista"].astype(str).str.lower()
    if "prioridade_prevista_codigo" in predictions:
        return predictions["prioridade_prevista_codigo"].map(lambda code: PRIORITY_ORDER[int(code)])
    raise ValueError("Previsões sem 'prioridade_prevista' ou 'prioridade_prevista_codigo'.")


def _reference_from_prediction(predictions: pd.DataFrame) -> pd.Series | None:
    """Obtém a prioridade de referência simulada quando ela existe no arquivo."""
    if "prioridade_referencia" in predictions:
        return predictions["prioridade_referencia"].astype(str).str.lower()
    if "prioridade_referencia_codigo" in predictions:
        return predictions["prioridade_referencia_codigo"].map(lambda code: PRIORITY_ORDER[int(code)])
    return None


def _marker_summary(row: pd.Series) -> str:
    """Resume marcadores extraídos em uma única coluna de inspeção rápida."""
    labels: list[str] = []
    for marker, label in _MARKER_LABELS.items():
        column = f"marcadores_extraidos_{marker}_present"
        if column in row.index and pd.notna(row[column]) and int(row[column]) == 1:
            labels.append(label)
    return "; ".join(labels) if labels else "Nenhum marcador extraído"


def _format_percent(value: object) -> str:
    """Formata probabilidades de 0--1 sem perder a leitura em CSV/HTML."""
    if pd.isna(value):
        return "Não disponível"
    return f"{100 * float(value):.1f}%"


def _numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    """Retorna coluna numérica ou uma série de valor-padrão alinhada ao índice."""
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def build_simplified_classification_table(
    profiles: pd.DataFrame,
    psychometrics: pd.DataFrame,
    extracted_markers: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    include_reference: bool = False,
) -> pd.DataFrame:
    """Cria uma tabela ordenada para visualização da classificação final.

    Parameters
    ----------
    profiles:
        Saída ``01_profiles/profiles.csv`` da execução corrente.
    psychometrics:
        Saída ``02_psychometrics/psychometrics.csv`` da execução corrente.
    extracted_markers:
        Saída ``06_extraction/marcadores_extraidos.csv`` da execução corrente.
    predictions:
        Arquivo ``final_test_predictions.csv`` do modelo selecionado. Cada linha
        precisa representar um perfil sintético do conjunto-teste final.
    include_reference:
        Quando ``True``, exibe ``prioridade_referencia`` e a concordância com a referência
        simulada. Esse campo é adequado apenas à avaliação experimental e deve
        permanecer oculto em uma visualização operacional hipotética.

    Returns
    -------
    pandas.DataFrame
        Tabela legível, ordenada por prioridade prevista e pelas probabilidades
        de alta/urgente. Os dados representam exclusivamente perfis sintéticos.
    """
    _require_columns(profiles, ["patient_id", "age_years", "gender_category", "social_vulnerability"], "profiles")
    _require_columns(psychometrics, ["patient_id", "phq9_total", "gad7_total", "idate_estado_total"], "psychometrics")
    _require_columns(extracted_markers, ["patient_id"], "marcadores_extraidos")
    _require_columns(predictions, ["patient_id"], "predictions")

    # Mantém somente as colunas de leitura rápida. O restante permanece disponível
    # nos artefatos originais para auditoria metodológica.
    profile_cols = ["patient_id", "age_years", "gender_category", "social_vulnerability"]
    score_cols = ["patient_id", "phq9_total", "gad7_total", "idate_estado_total"]
    extracted_cols = [
        "patient_id",
        "marcadores_extraidos_comprometimento_funcional_severity_code",
        *[f"marcadores_extraidos_{marker}_present" for marker in _MARKER_LABELS],
    ]
    available_extracted_cols = [column for column in extracted_cols if column in extracted_markers.columns]

    merged = predictions.copy()
    merged = merged.merge(profiles[profile_cols], on="patient_id", how="left", validate="one_to_one")
    merged = merged.merge(psychometrics[score_cols], on="patient_id", how="left", validate="one_to_one")
    merged = merged.merge(
        extracted_markers[available_extracted_cols], on="patient_id", how="left", validate="one_to_one"
    )

    missing_profile_data = merged["age_years"].isna().sum()
    if int(missing_profile_data) > 0:
        raise ValueError(
            f"Há {missing_profile_data} previsão(ões) sem perfil correspondente. "
            "Verifique se todos os artefatos usam o mesmo run_id."
        )

    predicted = _priority_from_prediction(merged)
    if {"proba_2", "proba_3"}.issubset(merged.columns):
        probability_high_urgent = _numeric_series(merged, "proba_2") + _numeric_series(merged, "proba_3")
        probability_urgent = _numeric_series(merged, "proba_3")
    else:
        probability_high_urgent = pd.Series(np.nan, index=merged.index)
        probability_urgent = pd.Series(np.nan, index=merged.index)

    functional_raw = _numeric_series(
        merged, "marcadores_extraidos_comprometimento_funcional_severity_code"
    ).astype(int)

    table = pd.DataFrame(
        {
            "ID do perfil sintético": merged["patient_id"],
            "Prioridade prevista": predicted.map(_label_priority),
            "Probabilidade alta/urgente": probability_high_urgent.map(_format_percent),
            "Probabilidade urgente": probability_urgent.map(_format_percent),
            "Idade": pd.to_numeric(merged["age_years"], errors="coerce").round().astype("Int64"),
            "Categoria de gênero": merged["gender_category"].map(_GENDER_LABELS).fillna(merged["gender_category"]),
            "Vulnerabilidade social": pd.to_numeric(merged["social_vulnerability"], errors="coerce").round(2),
            "PHQ-9": pd.to_numeric(merged["phq9_total"], errors="coerce").round().astype("Int64"),
            "GAD-7": pd.to_numeric(merged["gad7_total"], errors="coerce").round().astype("Int64"),
            "IDATE-Estado": pd.to_numeric(merged["idate_estado_total"], errors="coerce").round().astype("Int64"),
            "Comprometimento funcional extraído": functional_raw.map(_FUNCTIONAL_LABELS).fillna("Não disponível"),
            "Sinais de atenção extraídos": merged.apply(_marker_summary, axis=1),
        }
    )

    if include_reference:
        reference = _reference_from_prediction(merged)
        if reference is None:
            raise ValueError(
                "O arquivo de previsões não contém 'prioridade_referencia' ou 'prioridade_referencia_codigo'. "
                "Não é possível adicionar a referência simulada."
            )
        table.insert(2, "Prioridade de referência simulada", reference.map(_label_priority))
        table.insert(
            3,
            "Concorda com a referência simulada?",
            pd.Series(predicted.to_numpy() == reference.to_numpy(), index=table.index).map({True: "Sim", False: "Não"}),
        )

    # Colunas auxiliares não são exportadas: servem apenas à ordenação da fila de
    # inspeção, primeiro por urgência/alta e depois por probabilidades do modelo.
    table["__priority_rank"] = predicted.map(PRIORITY_DISPLAY_ORDER).fillna(len(PRIORITY_DISPLAY_ORDER))
    table["__probability_high_urgent"] = probability_high_urgent
    table["__probability_urgent"] = probability_urgent
    table = table.sort_values(
        by=["__priority_rank", "__probability_high_urgent", "__probability_urgent", "ID do perfil sintético"],
        ascending=[True, False, False, True],
        kind="stable",
    ).drop(columns=["__priority_rank", "__probability_high_urgent", "__probability_urgent"])
    table.insert(0, "Posição", range(1, len(table) + 1))
    return table.reset_index(drop=True)


def display_simplified_classification_table(table: pd.DataFrame, n_rows: int = 50) -> pd.DataFrame:
    """Exibe até ``n_rows`` no notebook e devolve o recorte para uso posterior.

    A função devolve um DataFrame para funcionar em Python puro. Em Jupyter/Colab,
    basta chamar a função em uma célula para que o ambiente apresente a tabela.
    """
    if n_rows <= 0:
        raise ValueError("n_rows deve ser maior que zero.")
    return table.head(n_rows).copy()


def save_simplified_classification_table(table: pd.DataFrame, output_dir: str | Path) -> tuple[Path, Path]:
    """Salva CSV e HTML autocontido da tabela simplificada.

    O HTML facilita a inspeção em navegador sem depender de um notebook. Não contém
    JavaScript e não deve ser tratado como interface clínica.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "classification_queue.csv"
    html_path = output_dir / "classification_queue.html"
    table.to_csv(csv_path, index=False, encoding="utf-8")

    title = "Tabela ordenada de classificação — perfis sintéticos"
    disclaimer = (
        "<p><strong>Aviso:</strong> esta tabela apresenta resultados de uma prova de conceito "
        "com dados inteiramente sintéticos. Não representa triagem, recomendação ou fila clínica.</p>"
    )
    table_html = table.to_html(index=False, escape=True, classes="classification-table")
    html = f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>{title}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.4; }}
h1 {{ font-size: 1.4rem; }}
.classification-table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
.classification-table th, .classification-table td {{ border: 1px solid #d1d5db; padding: 0.45rem; text-align: left; vertical-align: top; }}
.classification-table th {{ background: #f3f4f6; position: sticky; top: 0; }}
.classification-table tr:nth-child(even) {{ background: #fafafa; }}
</style>
</head>
<body>
<h1>{title}</h1>
{disclaimer}
{table_html}
</body>
</html>"""
    html_path.write_text(html, encoding="utf-8")
    return csv_path, html_path
