import streamlit as st

from lib.auth import guard_page, can_edit, current_user
from lib.ui import inject_css, page_header, top_bar, select_with_id, confirm_delete_button, consume_jump, val_or_dash
from lib.db import fetch_df, execute
from lib.catalog import list_modules, options

inject_css()
guard_page()
top_bar(current_user())
page_header("Dimensiones", "Dimensiones disponibles en las distintas partes de Q10")

consume_jump("jump_dimension_id", "dim_detail_select", {"dim_filter_module": None})

modules_df = list_modules()
module_opts = options(modules_df)

f_module = select_with_id("Módulo", module_opts, allow_none=True, none_label="Todos", key="dim_filter_module")

query = """
    select d.id, d.name, d.module_id, d.description, d.data_type, d.example_values, m.name as module_name
    from dimensions d
    left join modules m on m.id = d.module_id
    where (:module_id is null or d.module_id = :module_id)
    order by m.name nulls last, d.name
"""
df = fetch_df(query, {"module_id": f_module}, ttl=15)

if df.empty:
    st.info("No hay dimensiones que coincidan con el filtro.")
else:
    selected_id = select_with_id(
        "Selecciona una dimensión", [(int(r.id), r["name"]) for _, r in df.iterrows()], key="dim_detail_select"
    )
    row = df.set_index("id").loc[selected_id]

    st.markdown(f"**Módulo:** {val_or_dash(row['module_name'])}")
    st.markdown(f"**Descripción:** {val_or_dash(row['description'])}")
    st.markdown(f"**Tipo de dato:** {val_or_dash(row['data_type'])}")
    st.markdown(f"**Valores de ejemplo:** {val_or_dash(row['example_values'])}")

    if can_edit():
        with st.expander("✏️ Editar / eliminar esta dimensión"):
            with st.form(f"edit_dim_{selected_id}"):
                e_name = st.text_input("Nombre", value=row["name"])
                e_module_id = select_with_id(
                    "Módulo", module_opts, current_id=row["module_id"], allow_none=True, key=f"edit_dim_module_{selected_id}"
                )
                e_description = st.text_area("Descripción", value=row["description"] or "")
                e_data_type = st.text_input("Tipo de dato", value=row["data_type"] or "")
                e_example_values = st.text_area("Valores de ejemplo", value=row["example_values"] or "")
                save = st.form_submit_button("Guardar cambios")
            if save:
                execute(
                    """
                    update dimensions
                    set name = :name, module_id = :module_id, description = :description,
                        data_type = :data_type, example_values = :example_values,
                        updated_by = :uid, updated_at = now()
                    where id = :id
                    """,
                    {
                        "name": e_name.strip(),
                        "module_id": e_module_id,
                        "description": e_description.strip(),
                        "data_type": e_data_type.strip(),
                        "example_values": e_example_values.strip(),
                        "uid": current_user()["id"],
                        "id": int(selected_id),
                    },
                )
                st.success("Dimensión actualizada.")
                st.rerun()

            if confirm_delete_button("🗑️ Eliminar dimensión", f"del_dim_{selected_id}"):
                execute("delete from dimensions where id = :id", {"id": int(selected_id)})
                st.session_state[f"del_dim_{selected_id}"] = False
                st.success("Dimensión eliminada.")
                st.rerun()

st.divider()

with st.expander("📋 Ver tabla completa de dimensiones"):
    st.dataframe(
        df[["name", "module_name", "data_type"]] if not df.empty else df,
        use_container_width=True,
        hide_index=True,
    )

if can_edit():
    with st.expander("➕ Agregar dimensión"):
        with st.form("add_dimension", clear_on_submit=True):
            name = st.text_input("Nombre de la dimensión")
            module_id = select_with_id("Módulo", module_opts, allow_none=True, key="new_dim_module")
            description = st.text_area("Descripción")
            data_type = st.text_input("Tipo de dato")
            example_values = st.text_area("Valores de ejemplo")
            submitted = st.form_submit_button("Guardar dimensión")
        if submitted:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            else:
                execute(
                    """
                    insert into dimensions (name, module_id, description, data_type, example_values, created_by, updated_by)
                    values (:name, :module_id, :description, :data_type, :example_values, :uid, :uid)
                    """,
                    {
                        "name": name.strip(),
                        "module_id": module_id,
                        "description": description.strip(),
                        "data_type": data_type.strip(),
                        "example_values": example_values.strip(),
                        "uid": current_user()["id"],
                    },
                )
                st.success("Dimensión creada.")
                st.rerun()
