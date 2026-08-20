"""Componentes de interfaz reutilizables: estilo Q10, header, selects e inputs comunes."""

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
        render_global_search()


def render_global_search():
    """Barra de búsqueda de texto libre sobre funcionalidades, desarrollos, dimensiones y APIs."""
    from lib.search import search_all  # import local para evitar ciclo de módulos

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

            with st.container(border=True):
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
                                use_container_width=True,
                            ):
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


def val_or_dash(value, dash="—"):
    """Formatea un valor para mostrar, convirtiendo None/NaN/vacío en un guion."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return dash
    if isinstance(value, str) and not value.strip():
        return dash
    return value


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
