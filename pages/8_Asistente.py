import streamlit as st

from lib.auth import guard_page, current_user
from lib.ui import inject_css, page_header, top_bar, PAGE_BY_RESULT_TYPE, JUMP_KEY_BY_RESULT_TYPE, RESULT_TYPE_LABELS, RESULT_TYPE_ORDER
from lib.search import search_all, fetch_result_detail, _extract_keywords
from lib.db import fetch_df
from lib.activation_items import load_all_items, load_meta_query_ids, build_recipe, best_matches, KIND_LABELS
from lib import sys_catalog
from lib import llm

MAX_RESULTS_PER_TYPE = 3
MAX_ACTIONS = 3
MAX_ENRICHED_PER_TYPE = 2
TRUNCATE_LEN = 500

# Qué campos de detalle mostrarle al LLM por cada tipo de resultado, y con qué etiqueta —
# así puede responder con contenido real (el SQL de un query, el endpoint de una API...) en
# vez de solo confirmar que algo existe.
DETAIL_FIELDS = {
    "functionality": [("description", "Descripción"), ("request_type", "Tipo de petición")],
    "custom_development": [("client", "Cliente"), ("status", "Estado"), ("description", "Descripción"), ("notes", "Notas")],
    "dimension": [("description", "Descripción"), ("data_type", "Tipo de dato"), ("example_values", "Valores de ejemplo")],
    "api": [("method", "Método"), ("endpoint", "Endpoint"), ("auth_type", "Autenticación"), ("description", "Descripción")],
    "query": [("tags", "Etiquetas"), ("description", "Descripción"), ("sql_text", "SQL")],
    "dev_article": [("kind", "Tipo"), ("description_html", "Descripción")],
    "personalization": [("institution", "Institución"), ("description", "Descripción")],
}

RECIPE_COPY = {
    "funcion_codes": (
        "🔑",
        "Funciones / Permisos",
        "Asignar Permisos Roles",
        "pega estos códigos en `%Funcion%` (para el rol correspondiente)",
    ),
    "parametro_codes": (
        "🎛️",
        "Parámetros",
        "Actualizar parámetros institucionales",
        "activa este código en `%Código%`",
    ),
    "app_functionality_codes": (
        "🧩",
        "Funcionalidades",
        "Activar / InactivarFuncionalidades",
        "activa este código en `%funapl_codigoP%`",
    ),
}

inject_css()
guard_page()
top_bar(current_user())
page_header("Asistente", "Pregunta qué necesitas habilitar y te doy la receta completa lista para pegar")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if st.session_state.chat_history and st.button("🧹 Limpiar conversación"):
    st.session_state.chat_history = []
    st.rerun()

if not st.session_state.chat_history:
    st.caption(
        "Ejemplo: describe lo que necesitas habilitar (aunque sea un párrafo largo tipo "
        "ticket) y te doy la funcionalidad, su descripción y los códigos ya agrupados para "
        "pegar en los queries de activación."
    )
    if not llm.is_configured():
        st.caption("ℹ️ Respondiendo solo con búsqueda por palabras clave (sin IA configurada).")


def _fetch_functionality_detail(functionality_id):
    df = fetch_df(
        """
        select f.id, f.name, f.description, f.request_type, m.name as module_name
        from functionalities f
        left join modules m on m.id = f.module_id
        where f.id = :id
        """,
        {"id": functionality_id},
        ttl=30,
    )
    if df.empty:
        return None
    row = df.iloc[0]
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "request_type": row["request_type"],
        "module_name": row["module_name"],
    }


def _build_context(detail, recipe, actions, grouped):
    lines = []
    if detail:
        lines.append(f"Funcionalidad encontrada: «{detail['name']}»")
        if detail.get("module_name"):
            lines.append(f"Módulo: {detail['module_name']}")
        if detail.get("description"):
            lines.append(f"Descripción: {detail['description']}")
    if recipe:
        if recipe["funcion_codes"]:
            lines.append(f"Tiene {len(recipe['funcion_codes'])} función(es)/permiso(s) a asignar en el query Asignar Permisos Roles.")
        if recipe["parametro_codes"]:
            lines.append(f"Tiene {len(recipe['parametro_codes'])} parámetro(s) a activar en el query Actualizar parámetros institucionales.")
        if recipe["app_functionality_codes"]:
            lines.append(f"Tiene {len(recipe['app_functionality_codes'])} funcionalidad(es) a activar en el query Activar / InactivarFuncionalidades.")
    if actions and not detail:
        lines.append("\nFunciones/parámetros candidatos encontrados:")
        for a in actions:
            kind_label = KIND_LABELS.get(a["kind"], a["kind"])
            route = f" ({a['route']})" if a.get("route") else ""
            if a.get("functionality_name"):
                origin = f" — parte de la funcionalidad «{a['functionality_name']}»"
            else:
                origin = " — del catálogo maestro de Q10 (no documentado aún en una funcionalidad)"
            lines.append(f"- [{kind_label}] {a['code']}: {a['name']}{route}{origin}")
    if grouped:
        lines.append("\nOtros resultados relacionados en la documentación:")
        for result_type in RESULT_TYPE_ORDER:
            if result_type not in grouped:
                continue
            lines.append(f"{RESULT_TYPE_LABELS.get(result_type, result_type)}:")
            for idx, r in enumerate(grouped[result_type]):
                lines.append(f"- {r['label']} — {r['subtitle']}")
                if idx < MAX_ENRICHED_PER_TYPE:
                    detail = fetch_result_detail(result_type, r["id"])
                    for field, field_label in DETAIL_FIELDS.get(result_type, []):
                        value = (detail or {}).get(field)
                        if not value:
                            continue
                        value = str(value).strip()
                        if len(value) > TRUNCATE_LEN:
                            value = value[:TRUNCATE_LEN] + "…"
                        lines.append(f"  {field_label}: {value}")
    return "\n".join(lines)


def _render_recipe(i, detail, recipe, meta_ids):
    st.markdown(f"### 🎯 {detail['name']}")
    meta_bits = []
    if detail.get("module_name"):
        meta_bits.append(f"**Módulo:** {detail['module_name']}")
    if detail.get("request_type"):
        meta_bits.append(f"**Tipo de petición:** {detail['request_type']}")
    if meta_bits:
        st.caption(" · ".join(meta_bits))
    if detail.get("description"):
        st.write(detail["description"])

    has_codes = any(recipe[k] for k in RECIPE_COPY)
    if not has_codes:
        st.caption("Esta funcionalidad no tiene funciones, parámetros o códigos de activación documentados todavía.")

    for field, (icon, label, query_name, instruction) in RECIPE_COPY.items():
        codes = recipe[field]
        if not codes:
            continue
        st.markdown(f"{icon} **{label}** — en el query **{query_name}**, {instruction}:")
        st.code(",".join(codes), language=None)
        kind_key = {"funcion_codes": "funcion", "parametro_codes": "parametro", "app_functionality_codes": "app_functionality"}[field]
        query_id = meta_ids.get(kind_key)
        if query_id and st.button(f"Ver query «{query_name}» →", key=f"chat_recipe_{i}_{kind_key}"):
            st.session_state["jump_query_id"] = query_id
            st.switch_page("pages/6_Queries.py")

    if st.button(f"Ver ficha completa de «{detail['name']}» →", key=f"chat_detail_{i}_{detail['id']}"):
        st.session_state["jump_functionality_id"] = detail["id"]
        st.switch_page("pages/1_Funcionalidades.py")


def _render_sources(i, actions, grouped):
    if actions:
        st.write("Funciones/parámetros encontrados:")
        for a in actions:
            kind_label = KIND_LABELS.get(a["kind"], a["kind"])
            route = f" ({a['route']})" if a.get("route") else ""
            st.markdown(f"🔧 **{kind_label} {a['code']}: {a['name']}**{route}")
            if a.get("functionality_id"):
                st.caption(f"Parte de la funcionalidad: {a['functionality_name']}")
                if st.button(
                    f"Ver funcionalidad «{a['functionality_name']}» →",
                    key=f"chat_action_{i}_{a['functionality_id']}_{a['code']}",
                ):
                    st.session_state["jump_functionality_id"] = a["functionality_id"]
                    st.switch_page("pages/1_Funcionalidades.py")
            else:
                st.caption("Del catálogo maestro de Q10 (no documentado aún en una funcionalidad)")

    if grouped:
        if actions:
            st.divider()
        for result_type in RESULT_TYPE_ORDER:
            if result_type not in grouped:
                continue
            st.markdown(f"**{RESULT_TYPE_LABELS.get(result_type, result_type)}**")
            for r in grouped[result_type]:
                if st.button(
                    f"{r['label']} — {r['subtitle']}",
                    key=f"chat_{i}_{r['type']}_{r['id']}",
                    use_container_width=True,
                ):
                    st.session_state[JUMP_KEY_BY_RESULT_TYPE[r["type"]]] = r["id"]
                    st.switch_page(PAGE_BY_RESULT_TYPE[r["type"]])


for i, turn in enumerate(st.session_state.chat_history):
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        detail = turn.get("detail")
        recipe = turn.get("recipe")
        actions = turn.get("actions") or []
        grouped = turn.get("grouped") or {}
        llm_answer = turn.get("llm_answer")
        meta_ids = turn.get("meta_ids") or {}

        if not detail and not actions and not grouped:
            st.write(
                "No encontré nada relacionado con tu pregunta en la documentación. "
                "Prueba con otras palabras clave, o usa el buscador general en la parte superior."
            )
        else:
            if llm_answer:
                st.write(llm_answer)
            if detail:
                _render_recipe(i, detail, recipe, meta_ids)
                if grouped:
                    with st.expander("📎 También relacionado en la documentación"):
                        _render_sources(i, [], grouped)
            elif actions or grouped:
                if not actions and not llm_answer:
                    st.write("No encontré una función o parámetro exacto, pero esto es lo más relacionado:")
                _render_sources(i, actions, grouped)
                st.caption("¿No es lo que buscabas? Prueba con otras palabras o usa el buscador general.")

question = st.chat_input("Escribe tu pregunta…")
if question and question.strip():
    q = question.strip()

    items = load_all_items()
    meta_ids = load_meta_query_ids()

    results = search_all(q) if len(q) >= 2 else []
    grouped = {}
    for r in results:
        grouped.setdefault(r["type"], []).append(r)
    for result_type in grouped:
        grouped[result_type] = grouped[result_type][:MAX_RESULTS_PER_TYPE]

    detail = None
    recipe = None
    top_functionality = (grouped.get("functionality") or [None])[0]
    if top_functionality:
        # No basta con que search_all() haya encontrado ALGUNA funcionalidad: si la
        # pregunta trae varias palabras clave distintivas y esta funcionalidad solo coincide
        # por una de ellas (a veces la más genérica, p. ej. "estudiantes"), mostrarla como LA
        # respuesta confirmada —con receta y todo— sería engañoso. Solo la promovemos si
        # coincide con al menos 2 palabras clave, o con la única que había si solo hay una.
        n_keywords = len(_extract_keywords(q))
        confident = top_functionality.get("match_count", 0) >= min(2, n_keywords)
    else:
        confident = False
    if top_functionality and confident:
        top_functionality_id = top_functionality["id"]
        detail = _fetch_functionality_detail(top_functionality_id)
        if detail:
            recipe = build_recipe(items, top_functionality_id) or {
                "functionality_id": top_functionality_id,
                "functionality_name": detail["name"],
                "funcion_codes": [],
                "parametro_codes": [],
                "app_functionality_codes": [],
            }
            grouped["functionality"] = grouped["functionality"][1:]
            if not grouped["functionality"]:
                del grouped["functionality"]

    actions = []
    if not detail and len(q) >= 2:
        # Además de lo documentado a mano en activation_notes, buscamos en el catálogo
        # maestro real de Q10 (miles de funciones/parámetros/funcionalidades exportados del
        # sistema) — así encontramos cosas que existen en el sistema pero nadie documentó
        # todavía, en vez de forzar un match débil con lo poco que sí está documentado.
        combined_items = items + sys_catalog.load_all_items()
        actions = best_matches(q, combined_items, limit=MAX_ACTIONS)

    llm_answer = None
    if (detail or actions or grouped) and llm.is_configured():
        with st.spinner("Redactando respuesta…"):
            llm_answer = llm.answer(q, _build_context(detail, recipe, actions, grouped))

    st.session_state.chat_history.append(
        {
            "question": q,
            "detail": detail,
            "recipe": recipe,
            "actions": actions,
            "grouped": grouped,
            "llm_answer": llm_answer,
            "meta_ids": meta_ids,
        }
    )
    st.rerun()
