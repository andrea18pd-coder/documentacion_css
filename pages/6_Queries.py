import streamlit as st

from lib.auth import guard_page, can_edit, current_user
from lib.ui import inject_css, page_header, top_bar, select_with_id, confirm_delete_button, consume_jump, val_or_dash
from lib.db import fetch_df, execute

inject_css()
guard_page()
top_bar(current_user())
page_header("Queries", "Queries de soporte para habilitar funciones y funcionalidades")

consume_jump("jump_query_id", "query_detail_select", {"query_search": ""})

search = st.text_input(
    "Buscar", key="query_search", placeholder="🔍 Buscar por nombre, etiqueta, descripción o texto del query…"
)

if search and search.strip():
    q = f"%{search.strip()}%"
    df = fetch_df(
        """
        select id, name, description, tags, sql_text, active
        from queries
        where name ilike :q or tags ilike :q or description ilike :q or sql_text ilike :q
        order by name
        """,
        {"q": q},
        ttl=15,
    )
else:
    df = fetch_df("select id, name, description, tags, sql_text, active from queries order by name", ttl=15)

if df.empty:
    st.info("No hay queries que coincidan con la búsqueda.")
else:
    st.caption(f"{len(df)} query(s)")
    selected_id = select_with_id(
        "Selecciona un query", [(int(r.id), r["name"]) for _, r in df.iterrows()], key="query_detail_select"
    )
    row = df.set_index("id").loc[selected_id]

    status_label = "🟢 Activo" if row["active"] else "⚪ Inactivo"
    st.markdown(f"**Estado:** {status_label} &nbsp;&nbsp; **Etiquetas:** {val_or_dash(row['tags'])}")
    st.markdown(f"**Descripción:** {val_or_dash(row['description'])}")
    st.markdown("**SQL**")
    st.code(row["sql_text"], language="sql")

    st.markdown("#### Funcionalidades que se habilitan con este query")
    linked_df = fetch_df(
        """
        select f.id, f.name
        from notes n
        join functionalities f on f.id = n.functionality_id
        where n.query_id = :id
        order by f.name
        """,
        {"id": int(selected_id)},
        ttl=15,
    )
    if linked_df.empty:
        st.caption(
            "Ninguna funcionalidad enlaza a este query todavía. Se enlaza automáticamente al agregar una nota "
            "de tipo «Query» en una funcionalidad y seleccionar este query."
        )
    else:
        for _, f in linked_df.iterrows():
            if st.button(f"📋 {f['name']}", key=f"goto_func_{f['id']}"):
                st.session_state["jump_functionality_id"] = int(f["id"])
                st.switch_page("pages/1_Funcionalidades.py")

    if can_edit():
        with st.expander("✏️ Editar / eliminar este query"):
            with st.form(f"edit_query_{selected_id}"):
                e_name = st.text_input("Nombre", value=row["name"])
                e_description = st.text_area("Descripción", value=row["description"] or "")
                e_tags = st.text_input("Etiquetas", value=row["tags"] or "")
                e_sql = st.text_area("SQL", value=row["sql_text"], height=220)
                e_active = st.checkbox("Activo", value=bool(row["active"]))
                save = st.form_submit_button("Guardar cambios")
            if save:
                if not e_name.strip() or not e_sql.strip():
                    st.error("El nombre y el SQL son obligatorios.")
                else:
                    execute(
                        """
                        update queries
                        set name = :name, description = :description, tags = :tags, sql_text = :sql_text,
                            active = :active, updated_by = :uid, updated_at = now()
                        where id = :id
                        """,
                        {
                            "name": e_name.strip(),
                            "description": e_description.strip() or None,
                            "tags": e_tags.strip() or None,
                            "sql_text": e_sql.strip(),
                            "active": e_active,
                            "uid": current_user()["id"],
                            "id": int(selected_id),
                        },
                    )
                    st.success("Query actualizado.")
                    st.rerun()

            if not linked_df.empty:
                st.caption("⚠️ Eliminar este query deja sin enlace las notas de las funcionalidades listadas arriba.")
            if confirm_delete_button("🗑️ Eliminar este query", f"del_query_{selected_id}"):
                execute("delete from queries where id = :id", {"id": int(selected_id)})
                st.session_state[f"del_query_{selected_id}"] = False
                st.success("Query eliminado.")
                st.rerun()

st.divider()

with st.expander("📋 Ver tabla completa de queries"):
    full_df = fetch_df("select name, tags, active from queries order by name", ttl=15)
    st.dataframe(full_df, use_container_width=True, hide_index=True)

if can_edit():
    with st.expander("➕ Agregar query"):
        with st.form("add_query", clear_on_submit=True):
            name = st.text_input("Nombre")
            description = st.text_area("Descripción")
            tags = st.text_input("Etiquetas (separadas por coma)")
            sql_text = st.text_area("SQL", height=220)
            active = st.checkbox("Activo", value=True, key="new_query_active")
            submitted = st.form_submit_button("Guardar query")
        if submitted:
            if not name.strip() or not sql_text.strip():
                st.error("El nombre y el SQL son obligatorios.")
            else:
                execute(
                    """
                    insert into queries (name, description, tags, sql_text, active, created_by, updated_by)
                    values (:name, :description, :tags, :sql_text, :active, :uid, :uid)
                    """,
                    {
                        "name": name.strip(),
                        "description": description.strip() or None,
                        "tags": tags.strip() or None,
                        "sql_text": sql_text.strip(),
                        "active": active,
                        "uid": current_user()["id"],
                    },
                )
                st.success("Query creado.")
                st.rerun()
