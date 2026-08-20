import streamlit as st

from lib.auth import guard_page, can_edit, current_user
from lib.ui import inject_css, page_header, top_bar, select_with_id, confirm_delete_button, consume_jump, val_or_dash
from lib.db import fetch_df, execute
from lib.catalog import list_modules, options

inject_css()
guard_page()
top_bar(current_user())
page_header("Desarrollos personalizados", "Catálogo de desarrollos a la medida solicitados por clientes")

consume_jump(
    "jump_custom_development_id",
    "cd_detail_select",
    {"cd_filter_module": None, "cd_filter_status": "Todos"},
)

modules_df = list_modules()
module_opts = options(modules_df)

functionalities_df = fetch_df("select id, name from functionalities order by name", ttl=30)
functionality_opts = [(int(r.id), r.name) for r in functionalities_df.itertuples()] if not functionalities_df.empty else []

col1, col2 = st.columns(2)
with col1:
    f_module = select_with_id("Módulo", module_opts, allow_none=True, none_label="Todos", key="cd_filter_module")
with col2:
    f_status = st.selectbox("Estado", ["Todos", "solicitado", "en desarrollo", "entregado", "cancelado"], key="cd_filter_status")

query = """
    select cd.id, cd.name, cd.client, cd.description, cd.module_id, cd.related_functionality_id,
           cd.status, cd.requested_by, cd.developed_by, cd.request_date, cd.delivery_date, cd.notes,
           m.name as module_name
    from custom_developments cd
    left join modules m on m.id = cd.module_id
    where (:module_id is null or cd.module_id = :module_id)
      and (:status = 'Todos' or cd.status = :status)
    order by cd.request_date desc nulls last, cd.name
"""
df = fetch_df(query, {"module_id": f_module, "status": f_status}, ttl=15)

if df.empty:
    st.info("No hay desarrollos personalizados que coincidan con el filtro.")
else:
    selected_id = select_with_id(
        "Selecciona un desarrollo", [(int(r.id), r["name"]) for _, r in df.iterrows()], key="cd_detail_select"
    )
    row = df.set_index("id").loc[selected_id]

    st.markdown(f"**Cliente:** {val_or_dash(row['client'])}")
    st.markdown(f"**Descripción:** {val_or_dash(row['description'])}")
    st.markdown(f"**Módulo:** {val_or_dash(row['module_name'])} &nbsp;&nbsp; **Estado:** {row['status']}")
    st.markdown(f"**Solicitado por:** {val_or_dash(row['requested_by'])} &nbsp;&nbsp; **Desarrollado por:** {val_or_dash(row['developed_by'])}")
    st.markdown(f"**Fecha de solicitud:** {val_or_dash(row['request_date'])} &nbsp;&nbsp; **Fecha de entrega:** {val_or_dash(row['delivery_date'])}")
    st.markdown(f"**Notas:** {val_or_dash(row['notes'])}")

    if can_edit():
        with st.expander("✏️ Editar / eliminar este desarrollo"):
            with st.form(f"edit_cd_{selected_id}"):
                e_name = st.text_input("Nombre", value=row["name"])
                e_client = st.text_input("Cliente", value=row["client"] or "")
                e_description = st.text_area("Descripción", value=row["description"] or "")
                e_module_id = select_with_id(
                    "Módulo", module_opts, current_id=row["module_id"], allow_none=True, key=f"edit_cd_module_{selected_id}"
                )
                e_related = select_with_id(
                    "Funcionalidad relacionada",
                    functionality_opts,
                    current_id=row["related_functionality_id"],
                    allow_none=True,
                    key=f"edit_cd_func_{selected_id}",
                )
                status_options = ["solicitado", "en desarrollo", "entregado", "cancelado"]
                e_status = st.selectbox(
                    "Estado", status_options, index=status_options.index(row["status"]), key=f"edit_cd_status_{selected_id}"
                )
                e_requested_by = st.text_input("Solicitado por", value=row["requested_by"] or "")
                e_developed_by = st.text_input("Desarrollado por", value=row["developed_by"] or "")
                e_request_date = st.date_input("Fecha de solicitud", value=row["request_date"], key=f"edit_cd_reqdate_{selected_id}")
                e_delivery_date = st.date_input("Fecha de entrega", value=row["delivery_date"], key=f"edit_cd_deldate_{selected_id}")
                e_notes = st.text_area("Notas adicionales", value=row["notes"] or "")
                save = st.form_submit_button("Guardar cambios")
            if save:
                execute(
                    """
                    update custom_developments
                    set name = :name, client = :client, description = :description, module_id = :module_id,
                        related_functionality_id = :related_functionality_id, status = :status,
                        requested_by = :requested_by, developed_by = :developed_by,
                        request_date = :request_date, delivery_date = :delivery_date, notes = :notes,
                        updated_by = :uid, updated_at = now()
                    where id = :id
                    """,
                    {
                        "name": e_name.strip(),
                        "client": e_client.strip(),
                        "description": e_description.strip(),
                        "module_id": e_module_id,
                        "related_functionality_id": e_related,
                        "status": e_status,
                        "requested_by": e_requested_by.strip(),
                        "developed_by": e_developed_by.strip(),
                        "request_date": e_request_date,
                        "delivery_date": e_delivery_date,
                        "notes": e_notes.strip(),
                        "uid": current_user()["id"],
                        "id": int(selected_id),
                    },
                )
                st.success("Desarrollo actualizado.")
                st.rerun()

            if confirm_delete_button("🗑️ Eliminar desarrollo", f"del_cd_{selected_id}"):
                execute("delete from custom_developments where id = :id", {"id": int(selected_id)})
                st.session_state[f"del_cd_{selected_id}"] = False
                st.success("Desarrollo eliminado.")
                st.rerun()

st.divider()

with st.expander("📋 Ver tabla completa de desarrollos"):
    st.dataframe(
        df[["name", "client", "module_name", "status", "request_date", "delivery_date"]] if not df.empty else df,
        use_container_width=True,
        hide_index=True,
    )

if can_edit():
    with st.expander("➕ Agregar desarrollo personalizado"):
        with st.form("add_custom_dev", clear_on_submit=True):
            name = st.text_input("Nombre del desarrollo")
            client = st.text_input("Cliente")
            description = st.text_area("Descripción")
            module_id = select_with_id("Módulo", module_opts, allow_none=True, key="new_cd_module")
            related_functionality_id = select_with_id(
                "Funcionalidad relacionada (opcional)", functionality_opts, allow_none=True, key="new_cd_func"
            )
            status = st.selectbox("Estado", ["solicitado", "en desarrollo", "entregado", "cancelado"], key="new_cd_status")
            requested_by = st.text_input("Solicitado por")
            developed_by = st.text_input("Desarrollado por")
            request_date = st.date_input("Fecha de solicitud", value=None, key="new_cd_reqdate")
            delivery_date = st.date_input("Fecha de entrega", value=None, key="new_cd_deldate")
            notes = st.text_area("Notas adicionales")
            submitted = st.form_submit_button("Guardar desarrollo")
        if submitted:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            else:
                execute(
                    """
                    insert into custom_developments
                        (name, client, description, module_id, related_functionality_id, status,
                         requested_by, developed_by, request_date, delivery_date, notes, created_by, updated_by)
                    values
                        (:name, :client, :description, :module_id, :related_functionality_id, :status,
                         :requested_by, :developed_by, :request_date, :delivery_date, :notes, :uid, :uid)
                    """,
                    {
                        "name": name.strip(),
                        "client": client.strip(),
                        "description": description.strip(),
                        "module_id": module_id,
                        "related_functionality_id": related_functionality_id,
                        "status": status,
                        "requested_by": requested_by.strip(),
                        "developed_by": developed_by.strip(),
                        "request_date": request_date,
                        "delivery_date": delivery_date,
                        "notes": notes.strip(),
                        "uid": current_user()["id"],
                    },
                )
                st.success("Desarrollo creado.")
                st.rerun()
