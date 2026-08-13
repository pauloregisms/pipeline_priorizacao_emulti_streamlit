"""Demonstração acadêmica, somente leitura, da execução sintética congelada."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"

# Nomes dos arquivos consumidos ou oferecidos para download pela demonstração.
# Alterações de nomenclatura devem ser feitas somente neste dicionário.
DEMO_FILE_NAMES = {
    "downloads": {
        "report": "relatorio_execucao_demo.md",
        "configuration": "configuracao_resolvida_demo.yaml",
        "artifacts": "artefatos_experimento_gemini31flash_lite.zip",
    },
    "modeling": {
        "metrics": "final_test_metrics.csv",
        "per_class": "final_test_per_class.csv",
        "calibration": "final_test_calibration_curves.csv",
    },
    "explanations": {
        "ordinal_coefficients": "ordinal_coefficients.csv",
        "shap_importance": "global_shap_importance_highurgent.csv",
    },
}

# Rótulos legíveis para as faixas psicométricas registradas pela etapa 2.
PSYCHOMETRIC_BAND_LABELS = {
    "phq9_band": {
        "minimo": "Mínimo",
        "leve": "Leve",
        "moderado": "Moderado",
        "moderadamente_grave": "Moderadamente grave",
        "grave": "Grave",
    },
    "gad7_band": {
        "minimo": "Mínimo",
        "leve": "Leve",
        "moderado": "Moderado",
        "grave": "Grave",
    },
}

# Faixas interpretativas adotadas para a apresentação do IDATE-Estado.
IDATE_ESTADO_BAND_LABELS = [
    "Baixo nível de ansiedade",
    "Nível médio ou moderado de ansiedade",
    "Alto nível de ansiedade",
]

# O identificador é usado na URL e o texto é apresentado no menu lateral.
NAVIGATION_ITEMS = {
    "visao-geral": "Visão geral",
    "perfis-sinteticos": "Perfis sintéticos",
    "qualidade-extracao": "Qualidade e extração",
    "modelagem": "Modelagem",
    "interpretabilidade": "Interpretabilidade",
    "fila-final": "Fila final de classificação",
    "rastreabilidade": "Rastreabilidade",
}
DEFAULT_PAGE = "visao-geral"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from emulti_pipeline.demo import (  # noqa: E402
    DATASET_LABELS,
    DEMO_RUN_ID,
    MODEL_LABELS,
    PRIORITY_LABELS,
    build_demo_archive,
    clean_feature_name,
    list_demo_artifacts,
    load_confusion_matrix,
    load_demo_bundle,
    marker_comparison,
    validate_demo_root,
)


RUN_ROOT = PROJECT_ROOT / "artifacts" / DEMO_RUN_ID

st.set_page_config(
    page_title="Pipeline e-Multi — Demonstração sintética usando Gemini 3.1 Flash Lite",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1380px;}
      .demo-banner {background:#fff7d6; border:1px solid #eab308; border-left:6px solid #ca8a04;
                    border-radius:.55rem; padding:.8rem 1rem; margin:.4rem 0 1.2rem 0; color:#422006;}
      .home-intro {background:#f0fdfa; border:1px solid #99f6e4; border-left:6px solid #0f766e;
                   border-radius:.55rem; padding:1rem 1.15rem; margin:.4rem 0 1.2rem 0;
                   color:#134e4a; line-height:1.6;}
      .academic-note {background:#f8fafc; border:1px solid #cbd5e1; border-radius:.55rem;
                      padding:.9rem 1.05rem; margin:.7rem 0 1.2rem 0; color:#334155;
                      line-height:1.55;}
      .narrative {background:#f8fafc; border:1px solid #cbd5e1; border-radius:.55rem;
                  padding:1rem 1.1rem; line-height:1.55; white-space:pre-wrap;}
      .small-note {color:#475569; font-size:.9rem;}
      .sidebar-menu {display:flex; flex-direction:column; gap:.3rem; margin:.2rem 0 .9rem 0;}
      .sidebar-menu a {display:block; padding:.58rem .72rem; border-radius:.45rem;
                       color:#334155; text-decoration:none; border:1px solid transparent;
                       font-weight:500; line-height:1.25;}
      .sidebar-menu a:hover {background:#f1f5f9; border-color:#cbd5e1; color:#0f172a;}
      .sidebar-menu a.active {background:#e6fffb; border-color:#5eead4; color:#115e59;
                              font-weight:700;}
      div[data-testid="stMetric"] {background:#f8fafc; border:1px solid #e2e8f0;
                                   padding:.75rem; border-radius:.55rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def cached_bundle(root: str) -> dict:
    return load_demo_bundle(Path(root))


@st.cache_data(show_spinner=False)
def cached_archive(root: str) -> bytes:
    return build_demo_archive(Path(root))


def percent(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.1%}"


def number(value: float | int | None, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}"


def one_row(frame: pd.DataFrame, patient_id: str) -> pd.Series:
    match = frame.loc[frame["patient_id"] == patient_id]
    if match.empty:
        raise KeyError(patient_id)
    return match.iloc[0]


def uniform_ordered_sample(frame: pd.DataFrame, sample_size: int = 30) -> pd.DataFrame:
    """Seleciona posições aproximadamente equidistantes sem alterar a ordenação."""

    if sample_size < 1:
        raise ValueError("O tamanho da amostra deve ser maior que zero.")
    if len(frame) <= sample_size:
        return frame.reset_index(drop=True)
    if sample_size == 1:
        return frame.iloc[[0]].reset_index(drop=True)

    last_index = len(frame) - 1
    indices = [round(step * last_index / (sample_size - 1)) for step in range(sample_size)]
    return frame.iloc[indices].reset_index(drop=True)


def classification_queue_with_bands(
    queue: pd.DataFrame,
    psychometrics: pd.DataFrame,
) -> pd.DataFrame:
    """Substitui escores da fila pelas faixas interpretativas adotadas."""

    required_psychometric_columns = {"patient_id", "phq9_band", "gad7_band"}
    missing_columns = sorted(required_psychometric_columns.difference(psychometrics.columns))
    if missing_columns:
        raise KeyError(
            "Colunas psicométricas ausentes: " + ", ".join(missing_columns)
        )

    bands = psychometrics[["patient_id", "phq9_band", "gad7_band"]].copy()
    bands["patient_id"] = bands["patient_id"].astype(str)
    bands = bands.drop_duplicates(subset="patient_id", keep="first")
    bands["Faixa do PHQ-9"] = (
        bands["phq9_band"]
        .map(PSYCHOMETRIC_BAND_LABELS["phq9_band"])
        .fillna("Não informada")
    )
    bands["Faixa do GAD-7"] = (
        bands["gad7_band"]
        .map(PSYCHOMETRIC_BAND_LABELS["gad7_band"])
        .fillna("Não informada")
    )

    result = queue.copy()
    result["ID do perfil sintético"] = result["ID do perfil sintético"].astype(str)
    idate_estado_scores = pd.to_numeric(result["IDATE-Estado"], errors="coerce")
    result["Faixa do IDATE-Estado"] = pd.cut(
        idate_estado_scores,
        bins=[19, 40, 60, 80],
        labels=IDATE_ESTADO_BAND_LABELS,
        include_lowest=True,
    ).astype("object")
    result["Faixa do IDATE-Estado"] = result["Faixa do IDATE-Estado"].fillna(
        "Não informada"
    )
    result = result.merge(
        bands[["patient_id", "Faixa do PHQ-9", "Faixa do GAD-7"]],
        how="left",
        left_on="ID do perfil sintético",
        right_on="patient_id",
        validate="many_to_one",
    ).drop(columns="patient_id")
    result[["Faixa do PHQ-9", "Faixa do GAD-7"]] = result[
        ["Faixa do PHQ-9", "Faixa do GAD-7"]
    ].fillna("Não informada")

    original_columns = [
        column for column in queue.columns if column not in {"PHQ-9", "GAD-7", "IDATE-Estado"}
    ]
    insertion_index = (
        original_columns.index("Vulnerabilidade social") + 1
        if "Vulnerabilidade social" in original_columns
        else len(original_columns)
    )
    display_columns = original_columns.copy()
    display_columns[insertion_index:insertion_index] = [
        "Faixa do PHQ-9",
        "Faixa do GAD-7",
        "Faixa do IDATE-Estado",
    ]
    return result[display_columns]


def demo_banner() -> None:
    st.markdown(
        """
        <div class="demo-banner">
          <strong>Demonstração acadêmica — dados exclusivamente sintéticos.</strong><br>
          Os parâmetros são ilustrativos e ainda dependem de validação de conteúdo. Esta aplicação não
          realiza triagem, não ordena pacientes reais e não oferece recomendação assistencial.
        </div>
        """,
        unsafe_allow_html=True,
    )


def selected_page_from_url() -> str:
    """Obtém uma página permitida da URL, usando a visão geral como padrão."""

    raw_page = st.query_params.get("pagina", DEFAULT_PAGE)
    if isinstance(raw_page, list):
        raw_page = raw_page[0] if raw_page else DEFAULT_PAGE
    page = str(raw_page).strip()
    return page if page in NAVIGATION_ITEMS else DEFAULT_PAGE


def render_navigation_menu() -> str:
    """Apresenta a navegação lateral como links e retorna a página selecionada."""

    selected_page = selected_page_from_url()
    links = []
    for page_id, label in NAVIGATION_ITEMS.items():
        active = page_id == selected_page
        css_class = "active" if active else ""
        current = ' aria-current="page"' if active else ""
        links.append(
            f'<a class="{css_class}" href="?pagina={quote(page_id)}" '
            f'target="_self"{current}>{html.escape(label)}</a>'
        )
    st.markdown(
        '<nav class="sidebar-menu" aria-label="Navegação">'
        + "".join(links)
        + "</nav>",
        unsafe_allow_html=True,
    )
    return selected_page


def render_overview(data: dict) -> None:
    st.title("Demonstração do pipeline sintético de priorização para e-Multi")
    st.markdown(
        """
        <div class="home-intro">
          <strong>Bem-vindo à versão de demonstração do projeto.</strong><br>
          Esta aplicação foi preparada para apresentar à banca de avaliação os principais resultados e
          artefatos computacionais da pesquisa. A interface permite explorar uma execução previamente
          concluída com 500 perfis inteiramente sintéticos, sem necessidade de instalar programas ou
          executar códigos.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Sobre o projeto")
    st.write(
        "O pipeline reproduz, em ambiente controlado, um possível fluxo de encaminhamento em saúde mental "
        "para a e-Multi. A execução apresentada inclui a criação de perfis e medidas psicométricas "
        "simuladas, a produção de narrativas clínicas sintéticas no formato SOAP, a identificação de "
        "marcadores presentes nessas narrativas e a comparação de métodos para classificar uma prioridade "
        "de referência simulada."
    )
    st.write(
        "Nesta demonstração, o Gemini 3.1 Flash-Lite foi utilizado para produzir as narrativas e extrair "
        "os marcadores clínicos. Os resultados já estão carregados no aplicativo e permanecem congelados "
        "para que todas as pessoas consultem exatamente a mesma execução. A aplicação não recebe arquivos, "
        "não chama serviços externos e não reexecuta o pipeline."
    )

    st.subheader("O que pode ser consultado")
    st.markdown(
        """
        Use o menu lateral para percorrer os resultados da demonstração:

        - **Perfis sintéticos:** dados simulados, narrativa clínica e comparação dos marcadores de cada perfil;
        - **Qualidade e extração:** verificações da base e desempenho da identificação de informações nos textos;
        - **Modelagem:** comparação dos métodos e resultados no conjunto final de teste;
        - **Interpretabilidade:** variáveis que mais contribuíram para as classificações dos modelos;
        - **Fila final de classificação:** ordenação resultante no conjunto final de teste, em versão completa ou em uma amostra uniforme de 30 perfis;
        - **Rastreabilidade:** configurações, relatórios e arquivos produzidos durante a execução.
        """
    )

    st.subheader("Vinculação acadêmica")
    st.markdown(
        """
        <div class="academic-note">
          Este aplicativo apresenta os artefatos computacionais da pesquisa de mestrado de
          <strong>Renata Alves dos Santos</strong>, desenvolvida no Mestrado Profissional em Saúde da
          Família, vinculado ao Programa de Pós-Graduação em Saúde da Família da Universidade Estadual
          Vale do Acaraú. A pesquisa é orientada pelo <strong>Professor Dr. Paulo Regis Menezes Sousa</strong>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Como interpretar os resultados")
    st.write(
        "A finalidade desta aplicação é demonstrar o funcionamento e a rastreabilidade do método. Valores "
        "elevados nas tabelas e nos gráficos indicam apenas que o pipeline conseguiu recuperar relações e "
        "regras programadas no cenário sintético. Eles não demonstram validade clínica, segurança ou "
        "efetividade para o atendimento de pessoas reais."
    )

    st.subheader("Resumo da execução apresentada")
    manifest = data["priority_view_manifest"]
    quality = data["quality"]
    cols = st.columns(4)
    cols[0].metric("Perfis sintéticos", f"{quality['profiles']['n_records']:,}".replace(",", "."))
    cols[1].metric("Conjunto final de teste", manifest["n_profiles_in_final_test"])
    cols[2].metric("Conjuntos analíticos", data["modeling_summary"]["dataset"].nunique())
    cols[3].metric("Comparadores por conjunto", data["modeling_summary"]["model"].nunique())

    left, right = st.columns([1, 1.25])
    with left:
        st.subheader("Distribuição da referência sintética")
        distribution = data["priority_metadata"]["class_distribution"]
        distribution_frame = pd.DataFrame(
            {
                "Prioridade": [label.capitalize() for label in distribution],
                "Perfis": list(distribution.values()),
            }
        ).set_index("Prioridade")
        st.bar_chart(distribution_frame, color="#0f766e")
        st.caption(
            "A referência é produzida por uma matriz simulada em versão preliminar; não corresponde a "
            "classificação clínica validada."
        )

    with right:
        st.subheader("Etapas materializadas")
        stages = pd.DataFrame(
            [
                ("1–3", "Perfis, psicometria e controle de qualidade", "Concluída"),
                ("4–6", "Narrativas, referência sintética e extração", "Concluída"),
                ("7–8", "Amostra de anotação e validação da extração", "Parcial — anotação humana pendente"),
                ("9–10", "Conjuntos analíticos e modelagem", "Concluída"),
                ("11–14", "Explicações, relatório e visão de inspeção", "Concluída"),
            ],
            columns=["Etapas", "Conteúdo", "Estado na execução"],
        )
        st.dataframe(stages, hide_index=True, width="stretch")

    st.subheader("Resultados comparativos")
    summary = data["modeling_summary"].copy()
    summary["Conjunto"] = summary["dataset"].map(DATASET_LABELS)
    summary["Modelo"] = summary["model"].map(MODEL_LABELS)
    summary["F1 macro — desenvolvimento"] = summary["development_f1_macro"].round(3)
    summary["F1 macro — teste final"] = summary["final_test_f1_macro"].round(3)
    st.dataframe(
        summary[["Conjunto", "Modelo", "F1 macro — desenvolvimento", "F1 macro — teste final"]],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "O teste final foi reservado durante o desenvolvimento. O modelo exibido na inspeção de perfis "
        "foi selecionado pelo F1 macro de desenvolvimento, não pelo resultado do teste final."
    )


def render_profiles(data: dict) -> None:
    st.title("Perfis sintéticos no teste final")
    st.write(
        "Explore os perfis que compõem o conjunto final reservado. A referência simulada aparece somente "
        "para auditoria metodológica da execução."
    )

    classification = data["classification"].copy()
    class_filter = st.selectbox(
        "Filtrar pela prioridade prevista",
        ["Todas"] + PRIORITY_LABELS,
    )
    if class_filter != "Todas":
        classification = classification.loc[classification["Prioridade prevista"] == class_filter]

    choices = classification["ID do perfil sintético"].astype(str).tolist()
    if not choices:
        st.info("Nenhum perfil corresponde ao filtro selecionado.")
        return
    patient_id = st.selectbox("Perfil sintético", choices)

    profile = one_row(data["profiles"], patient_id)
    psych = one_row(data["psychometrics"], patient_id)
    narrative = one_row(data["narratives"], patient_id)
    reference = one_row(data["priority"], patient_id)
    trace = one_row(data["traceability"], patient_id)

    cols = st.columns(5)
    cols[0].metric("Previsão", str(trace["prioridade_prevista"]).capitalize())
    cols[1].metric("Referência sintética", str(reference["prioridade_referencia"]).capitalize())
    cols[2].metric("Prob. alta/urgente", percent(float(trace["proba_2"]) + float(trace["proba_3"])))
    cols[3].metric("Prob. urgente", percent(trace["proba_3"]))
    cols[4].metric("Escore da regra simulada", number(reference["priority_score"], 2))

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Dados estruturados simulados")
        structured = pd.DataFrame(
            [
                ("Idade", f"{int(profile['age_years'])} anos"),
                ("Categoria de gênero", profile["gender_category"]),
                ("Escolaridade", profile["education"]),
                ("Insegurança alimentar", "Sim" if bool(profile["food_insecurity"]) else "Não"),
                ("Moradia inadequada", "Sim" if bool(profile["poor_housing"]) else "Não"),
                ("Vulnerabilidade social", number(profile["social_vulnerability"], 3)),
                ("Histórico de saúde mental", "Sim" if bool(profile["mental_health_history"]) else "Não"),
                ("Condição crônica", "Sim" if bool(profile["chronic_condition"]) else "Não"),
            ],
            columns=["Variável", "Valor"],
        )
        st.dataframe(structured, hide_index=True, width="stretch")

    with right:
        st.subheader("Indicadores psicométricos simulados")
        scales = pd.DataFrame(
            [
                ("PHQ-9", int(psych["phq9_total"]), psych["phq9_band"]),
                ("GAD-7", int(psych["gad7_total"]), psych["gad7_band"]),
                ("IDATE-Estado", int(psych["idate_estado_total"]), "escore simulado"),
            ],
            columns=["Indicador", "Escore", "Faixa/observação"],
        )
        st.dataframe(scales, hide_index=True, width="stretch")
        st.caption("Os instrumentos e seus escores integram a simulação; não representam avaliação real.")

    st.subheader("Narrativa sintética")
    st.markdown(
        f'<div class="narrative">{html.escape(str(narrative["narrativa_clinica"]))}</div>',
        unsafe_allow_html=True,
    )

    st.subheader("Auditoria dos marcadores")
    comparison = marker_comparison(data["profiles"], data["extracted"], patient_id)
    st.dataframe(comparison, hide_index=True, width="stretch", height=390)
    st.caption(
        "A coluna de origem pertence ao mecanismo gerador sintético. A extração recebeu somente a narrativa, "
        "conforme o contrato registrado no manifesto."
    )

    with st.expander("Rastreabilidade técnica deste perfil"):
        technical = {
            "patient_id": patient_id,
            "narrative_id": narrative["narrative_id"],
            "generator_id": narrative["generator_id"],
            "prompt_version": narrative["prompt_version"],
            "input_hash": narrative["input_hash"],
            "extractor_id": trace["extractor_id"],
            "ontology_version": trace["ontology_version"],
            "extraction_status": trace["extraction_status"],
            "run_id": trace["run_id"],
            "config_hash": trace["config_hash"],
            "dataset": trace["dataset"],
            "selected_model": trace["selected_model"],
        }
        st.json(technical)


def render_quality(data: dict) -> None:
    st.title("Qualidade da simulação e da extração")
    quality = data["quality"]
    alphas = quality["psychometrics"]["cronbach_alpha"]
    cols = st.columns(4)
    cols[0].metric("Registros reprovados", quality["profiles"]["n_failed"])
    cols[1].metric("α PHQ-9", number(alphas["phq9"]))
    cols[2].metric("α GAD-7", number(alphas["gad7"]))
    cols[3].metric("α IDATE-Estado", number(alphas["idate_estado"]))

    left, right = st.columns(2)
    with left:
        st.subheader("Correlação entre escores simulados")
        correlations = pd.DataFrame(quality["psychometrics"]["correlations"])
        correlations.index = ["PHQ-9", "GAD-7", "IDATE-Estado"]
        correlations.columns = ["PHQ-9", "GAD-7", "IDATE-Estado"]
        st.dataframe(correlations.round(3), width="stretch")

    with right:
        st.subheader("Contrato de extração")
        manifest = data["extraction_manifest"]
        st.write(f"**Extrator:** {manifest['extractor_id']}")
        st.write(f"**Ontologia:** {manifest['ontology_version']}")
        st.write(f"**Narrativas processadas:** {manifest['n_narratives']}")
        st.write(f"**Falhas:** {manifest['failure_count']}")
        st.write("**Entradas permitidas:** " + ", ".join(manifest["input_contract"]))
        st.write("**Entradas proibidas:** " + ", ".join(manifest["forbidden_inputs"]))

    validation = data["validation"]
    primary = validation["extractors"][0]
    st.subheader("Validação contra a referência geradora sintética")
    cols = st.columns(5)
    cols[0].metric("F1 macro — presença", percent(primary["macro_f1"]))
    cols[1].metric("F1 micro — presença", percent(primary["micro_f1"]))
    cols[2].metric("Omissão", percent(primary["omission_rate"]))
    cols[3].metric("Alucinação", percent(primary["hallucination_rate"]))
    cols[4].metric("Erro de qualificação", percent(primary["qualification_error_rate"]))
    st.warning(
        "A concordância perfeita de presença é uma propriedade deste ambiente controlado, não evidência de "
        "validade externa. A anotação humana independente ainda não está disponível."
    )

    st.subheader("Estado da matriz de prioridade")
    priority_meta = data["priority_metadata"]
    st.write(f"**Versão:** {priority_meta['rule_version']}")
    st.write(f"**Estado:** {priority_meta['validation_status']}")
    st.write(priority_meta["rule_parameters"]["source_note"])


def render_modeling(data: dict) -> None:
    st.title("Modelagem e avaliação")
    dataset_label = st.selectbox("Conjunto analítico", list(DATASET_LABELS.values()), index=2)
    model_label = st.selectbox("Comparador", list(MODEL_LABELS.values()), index=3)
    dataset = next(key for key, value in DATASET_LABELS.items() if value == dataset_label)
    model = next(key for key, value in MODEL_LABELS.items() if value == model_label)

    summary = data["modeling_summary"]
    selected = summary.loc[(summary["dataset"] == dataset) & (summary["model"] == model)].iloc[0]
    metrics_path = (
        RUN_ROOT
        / "10_modeling"
        / dataset
        / model
        / DEMO_FILE_NAMES["modeling"]["metrics"]
    )
    metrics = pd.read_csv(metrics_path).iloc[0]

    cols = st.columns(5)
    cols[0].metric("F1 macro — desenvolvimento", number(selected["development_f1_macro"]))
    cols[1].metric("F1 macro — teste final", number(selected["final_test_f1_macro"]))
    cols[2].metric("Kappa ponderado", number(metrics.get("weighted_kappa")))
    cols[3].metric("Erro ordinal médio", number(metrics.get("ordinal_mae")))
    cols[4].metric("Recall urgente", percent(metrics.get("recall_urgente")))

    left, right = st.columns([1, 1.15])
    with left:
        st.subheader("Matriz de confusão — teste final")
        matrix = load_confusion_matrix(RUN_ROOT, dataset, model)
        st.dataframe(matrix, width="stretch")
    with right:
        st.subheader("Desempenho por classe")
        per_class_path = (
            RUN_ROOT
            / "10_modeling"
            / dataset
            / model
            / DEMO_FILE_NAMES["modeling"]["per_class"]
        )
        per_class = pd.read_csv(per_class_path)
        per_class["Prioridade"] = per_class["class_code"].map(dict(enumerate(PRIORITY_LABELS)))
        per_class = per_class.rename(
            columns={"precision": "Precisão", "recall": "Recall", "f1": "F1", "support": "N"}
        )
        for column in ["Precisão", "Recall", "F1"]:
            per_class[column] = per_class[column].round(3)
        st.dataframe(
            per_class[["Prioridade", "Precisão", "Recall", "F1", "N"]],
            hide_index=True,
            width="stretch",
        )

    calibration_path = (
        RUN_ROOT
        / "10_modeling"
        / dataset
        / model
        / DEMO_FILE_NAMES["modeling"]["calibration"]
    )
    if calibration_path.exists():
        st.subheader("Curva de calibração")
        priority = st.selectbox("Classe da curva", PRIORITY_LABELS, index=3)
        target = f"class_{PRIORITY_LABELS.index(priority)}"
        calibration = pd.read_csv(calibration_path)
        calibration = calibration.loc[calibration["target"] == target].copy()
        chart = calibration[["mean_predicted", "observed_fraction"]].rename(
            columns={"mean_predicted": "Probabilidade prevista", "observed_fraction": "Fração observada"}
        )
        chart["Referência ideal"] = chart["Probabilidade prevista"]
        chart = chart.set_index("Probabilidade prevista")
        st.line_chart(chart[["Fração observada", "Referência ideal"]])
        st.dataframe(calibration.round(4), hide_index=True, width="stretch")
    else:
        st.info("Este comparador não produz probabilidades calibráveis.")

    st.caption(
        "As métricas descrevem apenas a população sintética desta execução. Elas não medem segurança, "
        "efetividade ou desempenho clínico."
    )


def render_explanations(data: dict) -> None:
    st.title("Interpretabilidade dos modelos")
    dataset_label = st.selectbox("Conjunto analítico", list(DATASET_LABELS.values()), index=2)
    explainable_models = {key: MODEL_LABELS[key] for key in ("ordinal_logit", "random_forest", "xgboost")}
    model_label = st.selectbox("Modelo", list(explainable_models.values()), index=2)
    dataset = next(key for key, value in DATASET_LABELS.items() if value == dataset_label)
    model = next(key for key, value in explainable_models.items() if value == model_label)

    explanation_root = RUN_ROOT / "11_explanations" / dataset / model
    if model == "ordinal_logit":
        frame = pd.read_csv(
            explanation_root / DEMO_FILE_NAMES["explanations"]["ordinal_coefficients"]
        )
        frame["Variável"] = frame["feature"].map(clean_feature_name)
        frame["Importância"] = frame["abs_coefficient"]
        frame["Coeficiente"] = frame["coefficient"]
        method = "magnitude dos coeficientes do modelo ordinal"
        table_columns = ["Variável", "Importância", "Coeficiente"]
    else:
        frame = pd.read_csv(
            explanation_root / DEMO_FILE_NAMES["explanations"]["shap_importance"]
        )
        frame["Variável"] = frame["feature"].map(clean_feature_name)
        frame["Importância"] = frame["mean_abs_shap_highurgent"]
        method = "média do valor SHAP absoluto para o agrupamento alta/urgente"
        table_columns = ["Variável", "Importância"]

    top = frame.sort_values("Importância", ascending=False).head(20).copy()
    st.write(f"Método exibido: **{method}**.")
    st.bar_chart(top.set_index("Variável")[["Importância"]], color="#0f766e")
    for column in ["Importância", "Coeficiente"]:
        if column in top:
            top[column] = top[column].round(4)
    st.dataframe(top[table_columns], hide_index=True, width="stretch")
    st.warning(
        "Importância e contribuição para a previsão não demonstram causalidade, relevância clínica ou "
        "adequação para decisões assistenciais."
    )


def render_final_queue(data: dict) -> None:
    st.title("Fila final de classificação")
    st.write(
        "Esta página apresenta a ordenação produzida para os perfis do conjunto final de teste. "
        "A posição 1 corresponde ao perfil colocado no início da fila simulada. A ordenação é um "
        "resultado experimental e não deve ser interpretada como indicação para o atendimento real."
    )

    queue = data["classification"].copy()
    if queue.empty:
        st.info("A fila final desta execução não contém perfis para apresentação.")
        return

    required_columns = {"Posição", "ID do perfil sintético", "Prioridade prevista"}
    missing_columns = sorted(required_columns.difference(queue.columns))
    if missing_columns:
        st.error(
            "Não foi possível apresentar a fila porque faltam as colunas: "
            + ", ".join(missing_columns)
        )
        return

    queue = queue.sort_values("Posição", kind="stable").reset_index(drop=True)
    try:
        queue = classification_queue_with_bands(queue, data["psychometrics"])
    except (KeyError, pd.errors.MergeError) as exc:
        st.error(f"Não foi possível associar as faixas dos instrumentos à fila: {exc}")
        return

    counts = queue["Prioridade prevista"].value_counts()
    summary_columns = st.columns(5)
    summary_columns[0].metric("Perfis na fila", len(queue))
    for column, priority in zip(summary_columns[1:], PRIORITY_LABELS):
        column.metric(priority, int(counts.get(priority, 0)))

    display_mode = st.selectbox(
        "Quantidade de perfis exibidos",
        ["Amostra uniforme de 30 perfis", "Fila completa"],
        help=(
            "A amostra seleciona posições aproximadamente equidistantes ao longo da fila e mantém "
            "a mesma ordenação do resultado completo."
        ),
    )

    st.info(
        "**O que os instrumentos avaliam:** o PHQ-9 avalia a intensidade de sintomas depressivos "
        "nas duas últimas semanas e varia de 0 a 27 pontos; o GAD-7 avalia sintomas de ansiedade "
        "nas duas últimas semanas e varia de 0 a 21 pontos; o IDATE-Estado avalia o nível de "
        "ansiedade percebido no momento da resposta e varia de 20 a 80 pontos. Em todos eles, "
        "pontuações maiores indicam maior intensidade dos sintomas ou da ansiedade avaliada."
    )

    st.caption(
        "Os valores numéricos do PHQ-9, do GAD-7 e do IDATE-Estado foram substituídos por faixas "
        "interpretativas. As faixas do PHQ-9 e do GAD-7 vêm dos artefatos da simulação. Para o "
        "IDATE-Estado, foram adotados os intervalos de 20 a 40 pontos para baixo nível de ansiedade, "
        "41 a 60 pontos para nível médio ou moderado e 61 a 80 pontos para alto nível."
    )

    if display_mode == "Amostra uniforme de 30 perfis":
        displayed_queue = uniform_ordered_sample(queue, sample_size=30)
        st.caption(
            "São mostrados 30 perfis distribuídos entre o início e o fim da fila. Essa seleção serve "
            "apenas para facilitar a leitura e não constitui uma nova amostra estatística."
        )
    else:
        displayed_queue = queue
        st.caption("A tabela apresenta todos os perfis do conjunto final de teste.")

    st.dataframe(
        displayed_queue,
        hide_index=True,
        width="stretch",
        height=650,
    )

    first_position = int(displayed_queue["Posição"].iloc[0])
    last_position = int(displayed_queue["Posição"].iloc[-1])
    st.caption(
        f"Perfis exibidos: {len(displayed_queue)}. Intervalo coberto: posições "
        f"{first_position} a {last_position}."
    )


def render_traceability(data: dict) -> None:
    st.title("Rastreabilidade e artefatos")
    metadata = data["run_metadata"]
    cols = st.columns(4)
    cols[0].metric("Identificador da execução", metadata["run_id"])
    cols[1].metric("Seed base", int(data["profiles"]["seed"].iloc[0]))
    cols[2].metric("Versão da regra", data["priority_metadata"]["rule_version"])
    cols[3].metric("Extrator", data["extraction_manifest"]["extractor_id"])

    st.code(f"config_hash: {metadata['config_hash']}", language="text")
    st.write(metadata["project"]["parameter_status"])

    st.subheader("Relatório automático da execução")
    with st.expander("Abrir relatório", expanded=False):
        st.markdown(data["report"])

    st.subheader("Downloads da execução congelada")
    st.caption(
        "O pacote de artefatos contém arquivos legíveis (CSV, JSON, YAML, Markdown e HTML). "
        "Binários de modelos são deliberadamente excluídos do download pela interface."
    )
    cols = st.columns(3)
    cols[0].download_button(
        "Baixar relatório (.md)",
        data["report"].encode("utf-8"),
        file_name=DEMO_FILE_NAMES["downloads"]["report"],
        mime="text/markdown",
        width="stretch",
    )
    cols[1].download_button(
        "Baixar configuração (.yaml)",
        data["config"].encode("utf-8"),
        file_name=DEMO_FILE_NAMES["downloads"]["configuration"],
        mime="text/yaml",
        width="stretch",
    )
    cols[2].download_button(
        "Baixar artefatos (.zip)",
        cached_archive(str(RUN_ROOT)),
        file_name=DEMO_FILE_NAMES["downloads"]["artifacts"],
        mime="application/zip",
        width="stretch",
    )

    st.subheader("Inventário")
    inventory = list_demo_artifacts(RUN_ROOT)
    artifact_type = st.multiselect(
        "Filtrar por tipo",
        sorted(inventory["Tipo"].unique()),
        default=["csv", "json", "md", "yaml"],
    )
    if artifact_type:
        inventory = inventory.loc[inventory["Tipo"].isin(artifact_type)]
    st.dataframe(inventory, hide_index=True, width="stretch", height=420)

    with st.expander("Metadados técnicos"):
        st.json(
            {
                "run": data["run_metadata"],
                "environment": data["environment"],
                "extraction": data["extraction_manifest"],
                "priority_view": data["priority_view_manifest"],
            }
        )


missing = validate_demo_root(RUN_ROOT)
if missing:
    st.error("A execução pré-carregada está incompleta. Artefatos ausentes: " + ", ".join(missing))
    st.stop()

try:
    bundle = cached_bundle(str(RUN_ROOT))
except Exception as exc:  # pragma: no cover - proteção da interface implantada
    st.error(f"Não foi possível carregar a execução pré-carregada: {exc}")
    st.stop()

with st.sidebar:
    st.header("Demonstração da dissertação")
    page = render_navigation_menu()
    st.divider()
    st.caption("Execução congelada: experimento_gemini31flash_lite")
    st.caption("Sem upload, sem reexecução e sem acesso a dados reais.")

demo_banner()

renderers = {
    "visao-geral": render_overview,
    "perfis-sinteticos": render_profiles,
    "qualidade-extracao": render_quality,
    "modelagem": render_modeling,
    "interpretabilidade": render_explanations,
    "fila-final": render_final_queue,
    "rastreabilidade": render_traceability,
}
renderers[page](bundle)

st.divider()
st.markdown(
    '<p class="small-note">Pipeline de pesquisa com dados inteiramente sintéticos — demonstração acadêmica, '
    "sem validade clínica.</p>",
    unsafe_allow_html=True,
)
