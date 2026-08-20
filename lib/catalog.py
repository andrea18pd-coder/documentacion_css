"""Catálogos compartidos y administrables: módulos, planes, tipos."""

import streamlit as st

from lib.db import fetch_df, execute
from lib.ui import confirm_delete_button

_ALLOWED_TABLES = {"modules", "plans", "types"}


def _check_table(table):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Tabla de catálogo no permitida: {table}")


def list_catalog(table):
    _check_table(table)
    return fetch_df(f"select id, name, description from {table} order by name", ttl=15)


def list_modules():
    return list_catalog("modules")


def list_plans():
    return list_catalog("plans")


def list_types():
    return list_catalog("types")


def options(df):
    if df is None or df.empty:
        return []
    return [(int(row.id), row.name) for row in df.itertuples()]


def render_catalog_manager(title, table):
    """UI de alta/edición/borrado para un catálogo simple (id, name, description)."""
    _check_table(table)
    st.subheader(title)
    df = list_catalog(table)
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander(f"➕ Agregar en {title.lower()}"):
        with st.form(f"add_{table}", clear_on_submit=True):
            name = st.text_input("Nombre", key=f"add_{table}_name")
            description = st.text_area("Descripción", key=f"add_{table}_desc")
            submitted = st.form_submit_button("Guardar")
        if submitted:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            else:
                execute(
                    f"insert into {table} (name, description) values (:name, :description)",
                    {"name": name.strip(), "description": description.strip()},
                )
                st.success("Creado correctamente.")
                st.rerun()

    if df.empty:
        return

    st.markdown("#### Editar / eliminar")
    selected_id = st.selectbox(
        "Elemento", df["id"], format_func=lambda i: df.set_index("id").loc[i, "name"], key=f"select_{table}"
    )
    row = df.set_index("id").loc[selected_id]

    with st.form(f"edit_{table}_{selected_id}"):
        name = st.text_input("Nombre", value=row["name"])
        description = st.text_area("Descripción", value=row["description"] or "")
        save = st.form_submit_button("Guardar cambios")
    if save:
        execute(
            f"update {table} set name = :name, description = :description where id = :id",
            {"name": name.strip(), "description": description.strip(), "id": int(selected_id)},
        )
        st.success("Actualizado.")
        st.rerun()

    if confirm_delete_button(f"🗑️ Eliminar «{row['name']}»", f"del_{table}_{selected_id}"):
        try:
            execute(f"delete from {table} where id = :id", {"id": int(selected_id)})
            st.session_state[f"del_{table}_{selected_id}"] = False
            st.success("Eliminado.")
            st.rerun()
        except Exception:
            st.error(
                "No se pudo eliminar: probablemente está siendo usado por otros registros "
                "(funcionalidades, desarrollos, dimensiones o APIs)."
            )
