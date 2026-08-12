"""Demonstração acadêmica, somente leitura, da execução sintética congelada."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from urllib.parse import quote

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib.patches import Patch


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
PROJECT_REPOSITORY_URL = "https://github.com/pauloregisms/pipeline_priorizacao_emulti_streamlit"

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
        "metadata": "final_model_metadata.json",
    },
    "explanations": {
        "ordinal_coefficients": "ordinal_coefficients.csv",
        "shap_importance": "global_shap_importance_highurgent.csv",
    },
}

# O identificador é usado na URL e o texto é apresentado no menu lateral.
NAVIGATION_ITEMS = {
    "visao-geral": "Visão geral",
    "perfis-sinteticos": "Perfis sintéticos",
    "qualidade-extracao": "Qualidade e extração",
    "modelagem": "Modelagem",
    "interpretabilidade": "Interpretabilidade",
    "rastreabilidade": "Rastreabilidade",
}
DEFAULT_PAGE = "visao-geral"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from emulti_pipeline.demo import (  # noqa: E402
    DATASET_LABELS,
    DEMO_RUN_ID,
    MARKER_LABELS,
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


def coefficient_feature_label(feature: str) -> str:
    """Traduz variáveis transformadas do modelo ordinal para rótulos legíveis."""

    cleaned = feature
    for prefix in ("numeric__", "categorical__"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]

    direct_labels = {
        "phq9_total": "PHQ-9 — escore total",
        "gad7_total": "GAD-7 — escore total",
        "idate_estado_total": "IDATE-Estado — escore total",
        "age_years": "Idade",
        "income_brl": "Renda",
        "income_normalized": "Renda normalizada",
        "food_insecurity": "Insegurança alimentar",
        "poor_housing": "Moradia inadequada",
        "social_vulnerability": "Vulnerabilidade social",
        "mental_health_history": "Histórico de saúde mental",
        "chronic_condition": "Condição crônica",
        "recent_service_contact": "Contato recente com o serviço",
        "education_fundamental_ou_menos": "Escolaridade — fundamental ou menos",
        "education_medio": "Escolaridade — ensino médio",
        "education_superior": "Escolaridade — ensino superior",
        "gender_category_feminino": "Gênero — feminino",
        "gender_category_masculino": "Gênero — masculino",
        "gender_category_outro_ou_nao_informado": "Gênero — outro ou não informado",
    }
    if cleaned in direct_labels:
        return direct_labels[cleaned]

    qualifier_labels = {
        "present": "presença",
        "negated": "negação",
        "remote_present": "antecedente remoto",
        "severity_code": "código de gravidade",
        "severity_ausente": "gravidade ausente",
        "severity_leve": "gravidade leve",
        "severity_moderado": "gravidade moderada",
        "severity_importante": "gravidade importante",
        "severity_alto": "gravidade alta",
        "severity_nao_especificado": "gravidade não especificada",
        "temporality_atual": "temporalidade atual",
        "temporality_remoto": "temporalidade remota",
        "temporality_nao_especificado": "temporalidade não especificada",
        "certainty_afirmado": "achado afirmado",
        "certainty_incerto": "achado incerto",
        "experiencer_paciente": "referente ao paciente",
        "experiencer_terceiro": "referente a terceiro",
    }
    for marker, marker_label in MARKER_LABELS.items():
        marker_prefix = f"marker_{marker}_"
        if cleaned.startswith(marker_prefix):
            qualifier = cleaned[len(marker_prefix) :]
            qualifier_label = qualifier_labels.get(qualifier, qualifier.replace("_", " "))
            return f"{marker_label} — {qualifier_label}"

    return clean_feature_name(feature)


def ordinal_coefficient_chart(frame: pd.DataFrame):
    """Apresenta coeficientes com sinal, sem tratá-los como importância causal."""

    chart_data = frame.sort_values("Magnitude absoluta", ascending=True).copy()
    chart_data["Direção"] = chart_data["Coeficiente estimado"].map(
        lambda value: "Maior prioridade" if value >= 0 else "Menor prioridade"
    )
    colors = chart_data["Direção"].map(
        {"Maior prioridade": "#8ecfc9", "Menor prioridade": "#efb2bd"}
    )

    figure_height = max(6.0, 0.36 * len(chart_data))
    figure, axis = plt.subplots(figsize=(10.5, figure_height))
    bars = axis.barh(
        chart_data["Variável"],
        chart_data["Coeficiente estimado"],
        color=colors,
        edgecolor="white",
    )
    axis.axvline(0, color="#475569", linewidth=1)
    axis.set_xlabel("Coeficiente estimado")
    axis.set_ylabel("")
    axis.grid(axis="x", color="#e2e8f0", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.legend(
        handles=[
            Patch(color="#8ecfc9", label="Maior prioridade"),
            Patch(color="#efb2bd", label="Menor prioridade"),
        ],
        title="Direção no modelo",
        frameon=False,
        loc="lower right",
    )

    largest = max(chart_data["Magnitude absoluta"].max(), 0.1)
    for bar, value in zip(bars, chart_data["Coeficiente estimado"]):
        offset = largest * 0.025
        axis.text(
            value + (offset if value >= 0 else -offset),
            bar.get_y() + bar.get_height() / 2,
            f"{value:.2f}".replace(".", ","),
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=9,
            color="#334155",
        )

    axis.margins(x=0.14)
    figure.tight_layout()
    return figure


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
    st.link_button(
        "Acessar o repositório do projeto no GitHub",
        PROJECT_REPOSITORY_URL,
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
        frame["Variável"] = frame["feature"].map(coefficient_feature_label)
        frame["Coeficiente estimado"] = frame["coefficient"]
        frame["Magnitude absoluta"] = frame["abs_coefficient"]
        frame["Direção"] = frame["Coeficiente estimado"].map(
            lambda value: "Maior prioridade" if value >= 0 else "Menor prioridade"
        )

        top = frame.sort_values("Magnitude absoluta", ascending=False).head(20).copy()
        st.subheader("Coeficientes estimados do modelo ordinal")
        st.write(
            "O gráfico preserva o sinal dos coeficientes. Valores positivos acompanham o deslocamento "
            "para prioridades mais elevadas, enquanto valores negativos acompanham o deslocamento para "
            "prioridades mais baixas, mantidas as demais informações do modelo."
        )
        coefficient_figure = ordinal_coefficient_chart(top)
        st.pyplot(coefficient_figure, use_container_width=True)
        plt.close(coefficient_figure)

        coefficient_table = top[
            ["Variável", "Coeficiente estimado", "Magnitude absoluta", "Direção"]
        ].copy()
        coefficient_table["Coeficiente estimado"] = coefficient_table[
            "Coeficiente estimado"
        ].round(4)
        coefficient_table["Magnitude absoluta"] = coefficient_table[
            "Magnitude absoluta"
        ].round(4)
        st.dataframe(coefficient_table, hide_index=True, width="stretch")

        st.info(
            "A magnitude absoluta é usada somente para ordenar a apresentação. Ela não mede diretamente "
            "quanto o desempenho diminuiria com a retirada da variável."
        )

        metadata_path = (
            RUN_ROOT
            / "10_modeling"
            / dataset
            / model
            / DEMO_FILE_NAMES["modeling"]["metadata"]
        )
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("converged") is False:
                st.warning(
                    "O ajuste final deste modelo não alcançou convergência dentro do limite configurado. "
                    "Os coeficientes devem ser considerados provisórios até que o ajuste seja repetido e "
                    "sua estabilidade seja confirmada."
                )

        st.warning(
            "Os coeficientes descrevem relações internas do modelo no cenário sintético. Eles não "
            "representam causalidade, relevância clínica isolada nem adequação para decisões assistenciais."
        )
        return
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
    "rastreabilidade": render_traceability,
}
renderers[page](bundle)

st.divider()
st.markdown(
    '<p class="small-note">Pipeline de pesquisa com dados inteiramente sintéticos — demonstração acadêmica, '
    "sem validade clínica.</p>",
    unsafe_allow_html=True,
)
