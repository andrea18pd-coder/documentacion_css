import pandas as pd
import streamlit as st

from lib.auth import guard_page, can_edit, current_user
from lib.ui import inject_css, page_header, top_bar, select_with_id, confirm_delete_button
from lib.db import fetch_df, execute
from lib.catalog import list_modules, options
from lib import notifications

inject_css()
guard_page()
notifications.mark_announcements_seen(current_user()["id"])
top_bar(current_user())
page_header("Anuncios", "Notas de proceso a tener en cuenta al ejecutar ciertas tareas")

PRIORITY_ORDER = ["critico", "importante", "normal"]
PRIORITY_LABELS = {"critico": "Crítico", "importante": "Importante", "normal": "Normal"}
PRIORITY_ICONS = {"critico": "🔴", "importante": "🟠", "normal": "🔵"}

modules_df = list_modules()
module_opts = options(modules_df)

col1, col2, col3 = st.columns(3)
with col1:
    f_module = select_with_id("Módulo", module_opts, allow_none=True, none_label="Todos", key="pn_filter_module")
with col2:
    f_status = st.selectbox("Vigencia", ["Vigentes", "Archivados", "Todos"], key="pn_filter_status")
with col3:
    f_priority = st.selectbox(
        "Prioridad",
        ["Todos"] + [PRIORITY_LABELS[p] for p in PRIORITY_ORDER],
        key="pn_filter_priority",
    )
priority_value = None
if f_priority != "Todos":
    priority_value = next(p for p, label in PRIORITY_LABELS.items() if label == f_priority)

query = """
    select pn.id, pn.title, pn.description, pn.module_id, pn.priority, pn.active, pn.created_by,
           pn.created_at, pn.updated_at, m.name as module_name, u.name as author
    from process_notes pn
    left join modules m on m.id = pn.module_id
    left join users u on u.id = pn.created_by
    where (:module_id is null or pn.module_id = :module_id)
      and (:status = 'Todos' or (:status = 'Vigentes' and pn.active) or (:status = 'Archivados' and not pn.active))
      and (:priority is null or pn.priority = :priority)
    order by case pn.priority when 'critico' then 0 when 'importante' then 1 else 2 end, pn.created_at desc
"""
df = fetch_df(
    query,
    {"module_id": f_module, "status": f_status, "priority": priority_value},
    ttl=15,
)

if can_edit():
    with st.expander("➕ Agregar anuncio"):
        with st.form("add_process_note", clear_on_submit=True):
            title = st.text_input("Título")
            description = st.text_area("Descripción — qué se debe tener en cuenta al ejecutar el proceso")
            module_id = select_with_id("Módulo (opcional)", module_opts, allow_none=True, key="new_pn_module")
            priority = st.selectbox(
                "Prioridad",
                PRIORITY_ORDER,
                index=PRIORITY_ORDER.index("normal"),
                format_func=lambda p: PRIORITY_LABELS[p],
                key="new_pn_priority",
            )
            submitted = st.form_submit_button("Publicar anuncio")
        if submitted:
            if not title.strip() or not description.strip():
                st.error("El título y la descripción son obligatorios.")
            else:
                execute(
                    """
                    insert into process_notes (title, description, module_id, priority, created_by, updated_by)
                    values (:title, :description, :module_id, :priority, :uid, :uid)
                    """,
                    {
                        "title": title.strip(),
                        "description": description.strip(),
                        "module_id": module_id,
                        "priority": priority,
                        "uid": current_user()["id"],
                    },
                )
                st.success("Anuncio publicado. El resto del equipo lo verá como anuncio nuevo al entrar a la app.")
                st.rerun()

st.divider()

if df.empty:
    st.info("No hay anuncios que coincidan con el filtro.")
else:
    for _, row in df.iterrows():
        with st.container(border=True):
            badge_bits = [f"{PRIORITY_ICONS[row['priority']]} **{PRIORITY_LABELS[row['priority']]}**"]
            if pd.notna(row["module_name"]):
                badge_bits.append(row["module_name"])
            if not row["active"]:
                badge_bits.append("📦 Archivado")
            st.markdown(" · ".join(badge_bits))
            st.markdown(f"### {row['title']}")
            st.write(row["description"])
            st.caption(f"{row['author'] or 'Usuario'} · {row['created_at']}")

            is_owner = row["created_by"] == current_user()["id"]
            if can_edit() and is_owner:
                with st.expander("✏️ Editar / eliminar este anuncio"):
                    with st.form(f"edit_pn_{row['id']}"):
                        e_title = st.text_input("Título", value=row["title"])
                        e_description = st.text_area("Descripción", value=row["description"])
                        e_module_id = select_with_id(
                            "Módulo", module_opts, current_id=row["module_id"], allow_none=True, key=f"edit_pn_module_{row['id']}"
                        )
                        e_priority = st.selectbox(
                            "Prioridad",
                            PRIORITY_ORDER,
                            index=PRIORITY_ORDER.index(row["priority"]),
                            format_func=lambda p: PRIORITY_LABELS[p],
                            key=f"edit_pn_priority_{row['id']}",
                        )
                        e_active = st.checkbox("Vigente", value=row["active"], key=f"edit_pn_active_{row['id']}")
                        save = st.form_submit_button("Guardar cambios")
                    if save:
                        if not e_title.strip() or not e_description.strip():
                            st.error("El título y la descripción son obligatorios.")
                        else:
                            execute(
                                """
                                update process_notes
                                set title = :title, description = :description, module_id = :module_id,
                                    priority = :priority, active = :active, updated_by = :uid, updated_at = now()
                                where id = :id
                                """,
                                {
                                    "title": e_title.strip(),
                                    "description": e_description.strip(),
                                    "module_id": e_module_id,
                                    "priority": e_priority,
                                    "active": e_active,
                                    "uid": current_user()["id"],
                                    "id": int(row["id"]),
                                },
                            )
                            st.success("Anuncio actualizado.")
                            st.rerun()

                    if confirm_delete_button("🗑️ Eliminar anuncio", f"del_pn_{row['id']}"):
                        execute("delete from process_notes where id = :id", {"id": int(row["id"])})
                        st.session_state[f"del_pn_{row['id']}"] = False
                        st.success("Anuncio eliminado.")
                        st.rerun()
