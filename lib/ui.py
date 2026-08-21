"""Componentes de interfaz reutilizables: estilo Q10, header, selects e inputs comunes."""

import html
import re
from pathlib import Path

import pandas as pd
import streamlit as st

_CSS_PATH = Path(__file__).resolve().parent.parent / "assets" / "style.css"


def inject_css():
    if _CSS_PATH.exists():
        st.markdown(f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def page_header(title, subtitle=None):
    subtitle_html = f'<div class="q10-header-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="q10-header">
            <div class="q10-header-title">{title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


PAGE_BY_RESULT_TYPE = {
    "functionality": "pages/1_Funcionalidades.py",
    "custom_development": "pages/2_Desarrollos_Personalizados.py",
    "dimension": "pages/3_Dimensiones.py",
    "api": "pages/4_APIs.py",
    "query": "pages/6_Queries.py",
    "dev_article": "pages/7_Biblioteca_Desarrollos.py",
    "personalization": "pages/7_Biblioteca_Desarrollos.py",
}

JUMP_KEY_BY_RESULT_TYPE = {
    "functionality": "jump_functionality_id",
    "custom_development": "jump_custom_development_id",
    "dimension": "jump_dimension_id",
    "api": "jump_api_id",
    "query": "jump_query_id",
    "dev_article": "jump_dev_article_id",
    "personalization": "jump_personalization_id",
}

RESULT_TYPE_LABELS = {
    "functionality": "📋 Funcionalidades",
    "api": "🔌 APIs",
    "query": "🗄️ Queries",
    "dimension": "📐 Dimensiones",
    "custom_development": "🛠️ Desarrollos personalizados",
    "dev_article": "📚 Biblioteca de desarrollos",
    "personalization": "🏫 Personalizaciones",
}

RESULT_TYPE_ORDER = [
    "functionality",
    "api",
    "query",
    "dimension",
    "custom_development",
    "dev_article",
    "personalization",
]


def top_bar(user):
    from lib.auth import logout  # import local para evitar ciclo de módulos

    col_brand, col_user, col_logout = st.columns([6, 2, 1])
    with col_brand:
        st.markdown('<div class="q10-brand">Q10 <span>· Documentación CSS</span></div>', unsafe_allow_html=True)
    with col_user:
        if user:
            st.caption(f"{user['name']} · {user['role'].capitalize()}")
    with col_logout:
        if user and st.button("Salir", use_container_width=True):
            logout()

    if user:
        from lib.notifications import render_announcements_banner  # import local para evitar ciclo de módulos

        render_announcements_banner(user)

        render_global_search()
        from lib.assistant_widget import render_assistant_widget  # import local para evitar ciclo de módulos

        render_assistant_widget()


def render_global_search():
    """Barra de búsqueda de texto libre sobre funcionalidades, desarrollos, dimensiones y APIs."""
    from lib.search import search_all  # import local para evitar ciclo de módulos

    # No se puede tocar st.session_state["global_search_query"] después de que el widget ya
    # se instanció en este mismo run, así que la limpieza se aplica UN PASO ANTES de crearlo.
    if st.session_state.pop("_clear_search_query", False):
        st.session_state["global_search_query"] = ""

    query = st.text_input(
        "Buscar",
        key="global_search_query",
        placeholder="🔍 Buscar en toda la documentación (funcionalidades, desarrollos, dimensiones, APIs)…",
        label_visibility="collapsed",
    )
    if query and len(query.strip()) >= 2:
        results = search_all(query)
        if not results:
            st.caption("Sin resultados.")
        else:
            grouped = {}
            for r in results:
                grouped.setdefault(r["type"], []).append(r)

            with st.container(border=True, key="q10-global-search-results"):
                types_present = [t for t in RESULT_TYPE_ORDER if t in grouped]
                cols = st.columns(len(types_present))
                for col, result_type in zip(cols, types_present):
                    group = grouped[result_type]
                    with col:
                        st.markdown(
                            f"**{RESULT_TYPE_LABELS.get(result_type, result_type)}** &nbsp;·&nbsp; {len(group)}"
                        )
                        for r in group:
                            if st.button(
                                f"{r['label']} — {r['subtitle']}",
                                key=f"search_result_{r['type']}_{r['id']}",
                            ):
                                st.session_state["_clear_search_query"] = True
                                st.session_state[JUMP_KEY_BY_RESULT_TYPE[r["type"]]] = r["id"]
                                st.switch_page(PAGE_BY_RESULT_TYPE[r["type"]])
    st.write("")


def select_with_id(label, opts, current_id=None, allow_none=False, none_label="—", key=None):
    """Selectbox sobre una lista de tuplas (id, label)."""
    ids = ([None] if allow_none else []) + [o[0] for o in opts]
    labels = {o[0]: o[1] for o in opts}
    if allow_none:
        labels[None] = none_label
    index = ids.index(current_id) if current_id in ids else 0
    return st.selectbox(label, ids, index=index, format_func=lambda i: labels.get(i, none_label), key=key)


def multiselect_with_id(label, opts, current_ids=None, key=None):
    """Multiselect sobre una lista de tuplas (id, label)."""
    current_ids = current_ids or []
    labels = {o[0]: o[1] for o in opts}
    return st.multiselect(
        label,
        [o[0] for o in opts],
        default=[i for i in current_ids if i in labels],
        format_func=lambda i: labels.get(i, str(i)),
        key=key,
    )


def consume_jump(jump_key, detail_key, filter_resets=None):
    """Si venimos de la búsqueda global, limpia los filtros y preselecciona el resultado.

    `filter_resets` es un dict {clave_de_session_state: valor_al_que_resetear} para los
    widgets de filtro de la página, de forma que el resultado no quede oculto por un filtro
    dejado de una sesión anterior.
    """
    jump_id = st.session_state.pop(jump_key, None)
    if jump_id is not None:
        for filter_key, reset_value in (filter_resets or {}).items():
            st.session_state[filter_key] = reset_value
        st.session_state[detail_key] = jump_id
    return jump_id


def dataframe_to_markdown(df):
    """Convierte un DataFrame (p. ej. de st.data_editor) a una tabla en Markdown, sin filas vacías."""
    df = df.fillna("").astype(str)
    df = df[df.apply(lambda row: any(v.strip() for v in row), axis=1)]
    if df.empty or len(df.columns) == 0:
        return ""
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    separator = "|" + "|".join(["---"] * len(df.columns)) + "|"
    rows = ["| " + " | ".join(row) + " |" for row in df.values.tolist()]
    return "\n".join([header, separator] + rows)


def markdown_to_dataframe(md_text):
    """Convierte una tabla en Markdown (como la genera dataframe_to_markdown) a un DataFrame."""
    lines = [l for l in (md_text or "").strip().split("\n") if l.strip()]
    if len(lines) < 2:
        return None
    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        elif len(cells) > len(header):
            cells = cells[: len(header)]
        rows.append(cells)
    return pd.DataFrame(rows, columns=header)


def val_or_dash(value, dash="—"):
    """Formatea un valor para mostrar, convirtiendo None/NaN/vacío en un guion."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return dash
    if isinstance(value, str) and not value.strip():
        return dash
    return value


def field_card(label, value, key=None):
    """Tarjeta pequeña con una etiqueta y un valor, para mostrar campos en fila (estilo Q10).

    Se dibuja como HTML plano (no st.container) a propósito: el contenedor con borde de
    Streamlit trae su propio layout flex interno que gana el pulso al CSS incluso con
    !important, así que un alto fijo parejo entre tarjetas no se puede forzar ahí. Con un
    div propio no hay nada que pelear.
    """
    st.markdown(
        f'<div class="q10-field-card"><div class="q10-field-label">{html.escape(str(label))}</div>'
        f'<div class="q10-field-value">{html.escape(str(value))}</div></div>',
        unsafe_allow_html=True,
    )


def extract_activation_codes(text):
    """Extrae los códigos numéricos de la sección 'Funciones / Permisos' (ej. '894: Inicio - ...')
    de un texto de parámetros/pasos de activación, listos para copiar y pegar en la habilitación en BD.

    Los códigos de otras secciones (ej. 'Parámetros:') no aplican a la habilitación y se ignoran.
    """
    if not text or (isinstance(text, float) and pd.isna(text)):
        return []
    text = str(text)
    heading = re.search(r"(?im)^\s*funciones\s*/\s*permisos\s*:", text)
    if not heading:
        return []
    codes = []
    for line in text[heading.end():].splitlines():
        if not line.strip():
            continue
        m = re.match(r"^\s*[-*]?\s*(\d+)\s*:", line)
        if m:
            codes.append(m.group(1))
        elif not re.match(r"^\s*[-*]", line):
            break
    return codes


def confirm_delete_button(label, state_key):
    """Botón de eliminar con confirmación en dos pasos. Devuelve True solo cuando se confirma."""
    if not st.session_state.get(state_key):
        if st.button(label, key=state_key + "_btn"):
            st.session_state[state_key] = True
            st.rerun()
        return False

    st.warning("¿Confirmas que deseas eliminar? Esta acción no se puede deshacer.")
    c1, c2 = st.columns(2)
    confirmed = c1.button("Sí, eliminar", key=state_key + "_yes")
    cancelled = c2.button("Cancelar", key=state_key + "_no")
    if cancelled:
        st.session_state[state_key] = False
        st.rerun()
    return confirmed
