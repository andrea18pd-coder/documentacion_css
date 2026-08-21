from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from lib.auth import guard_page, can_edit, current_user
from lib.ui import inject_css, page_header, top_bar, select_with_id, confirm_delete_button, consume_jump, val_or_dash
from lib.db import fetch_df, execute
from lib.api_graph import (
    build_graph_data,
    render_graph_html,
    get_or_create_category,
    get_or_create_resource,
    list_resources,
    list_ops,
    list_top_categories,
)

inject_css()
guard_page()
top_bar(current_user())
page_header("APIs", "Mapa de dependencias entre recursos y endpoints")

jump_id = consume_jump("jump_api_id", "api_op_select", {"api_op_resource_filter": None})
if jump_id is not None:
    jump_row = fetch_df("select resource_id from apis where id = :id", {"id": jump_id}, ttl=0)
    if not jump_row.empty and jump_row.iloc[0]["resource_id"] is not None:
        st.session_state["api_op_resource_filter"] = int(jump_row.iloc[0]["resource_id"])

graph_data = build_graph_data()

if not graph_data["nodes"]:
    st.info(
        "Todavía no hay recursos ni endpoints registrados. Agrega el primero desde "
        "**➕ Agregar endpoint / operación** más abajo."
    )
else:
    components.html(render_graph_html(graph_data), height=780, scrolling=False)

st.divider()

# --- Detalle de una operación (selector nativo: útil para búsqueda global y para editar) ---
st.markdown("#### Detalle de una operación")

resources_df = list_resources()
resource_opts = [(int(r.id), r.name) for r in resources_df.itertuples()] if not resources_df.empty else []

if not resource_opts:
    st.caption("Sin recursos todavía.")
    selected_op = None
    ops_df = pd.DataFrame()
else:
    col_r, col_o = st.columns(2)
    with col_r:
        f_resource = select_with_id(
            "Recurso", resource_opts, allow_none=True, none_label="Todos", key="api_op_resource_filter"
        )
    ops_df = fetch_df(
        """
        select a.id, a.name, a.method, a.endpoint, a.description, a.resource_id, a.requires_list_of_id,
               r.name as resource_name, c.top_category, c.sub_category
        from apis a
        join api_resources r on r.id = a.resource_id
        left join api_categories c on c.id = a.category_id
        where (:rid is null or a.resource_id = :rid)
        order by r.name, a.name
        """,
        {"rid": f_resource},
        ttl=5,
    )
    with col_o:
        if ops_df.empty:
            st.caption("Sin operaciones para este filtro.")
            selected_op = None
        else:
            op_opts = [(int(r.id), f"{r.resource_name} · {r.name}") for r in ops_df.itertuples()]
            selected_op = select_with_id("Operación", op_opts, key="api_op_select")

if selected_op is not None:
    row = ops_df.set_index("id").loc[selected_op]

    st.markdown(f"**Método:** `{val_or_dash(row['method'])}` &nbsp;&nbsp; **Endpoint:** `{val_or_dash(row['endpoint'])}`")
    st.markdown(
        f"**Recurso:** {row['resource_name']} &nbsp;&nbsp; "
        f"**Categoría:** {val_or_dash(row['top_category'])} · {val_or_dash(row['sub_category'])}"
    )
    st.markdown(f"**Descripción:** {val_or_dash(row['description'])}")

    requires_id = row["requires_list_of_id"]
    if requires_id is not None and not pd.isna(requires_id):
        req_df = fetch_df("select name from apis where id = :id", {"id": int(requires_id)}, ttl=5)
        if not req_df.empty:
            st.warning(f"⚠️ Requiere llamar primero a: **{req_df.iloc[0]['name']}** (mismo recurso).")

    out_df = fetch_df(
        """
        select ac.id, ac.param_name, ac.relationship_description, r.name as target_name
        from api_connections ac
        join api_resources r on r.id = ac.target_resource_id
        where ac.api_id = :id
        order by r.name
        """,
        {"id": int(selected_op)},
        ttl=5,
    )
    in_df = fetch_df(
        """
        select ac.id, ac.param_name, a2.name as source_op, r2.name as source_resource
        from api_connections ac
        join apis a2 on a2.id = ac.api_id
        join api_resources r2 on r2.id = a2.resource_id
        where ac.target_resource_id = :rid
        order by r2.name
        """,
        {"rid": int(row["resource_id"])},
        ttl=5,
    )

    col_out, col_in = st.columns(2)
    with col_out:
        st.markdown("**Esta operación depende de →**")
        if out_df.empty:
            st.caption("Sin dependencias salientes.")
        else:
            for _, d in out_df.iterrows():
                desc = f" — {d['relationship_description']}" if d["relationship_description"] else ""
                st.markdown(f"- `{d['param_name']}` → **{d['target_name']}**{desc}")
    with col_in:
        st.markdown("**← Recursos que dependen de este recurso**")
        if in_df.empty:
            st.caption("Nadie depende de este recurso todavía (según lo registrado).")
        else:
            for _, d in in_df.iterrows():
                st.markdown(f"- **{d['source_resource']}** · {d['source_op']} — `{d['param_name']}`")

    if can_edit():
        with st.expander("🔗 Agregar dependencia desde esta operación"):
            target_opts = [(i, n) for i, n in resource_opts]
            with st.form(f"add_conn_{selected_op}", clear_on_submit=True):
                target_resource_id = select_with_id(
                    "Recurso del que depende", target_opts, allow_none=True, key=f"conn_target_{selected_op}"
                )
                new_target_name = st.text_input("...o escribe el nombre de un recurso nuevo", key=f"conn_new_target_{selected_op}")
                param_name = st.text_input("Nombre del parámetro (ej. Codigo_persona)")
                relationship_description = st.text_area("Descripción de la relación (opcional)")
                submitted = st.form_submit_button("Guardar dependencia")
            if submitted:
                final_target_id = target_resource_id
                if new_target_name.strip():
                    final_target_id = get_or_create_resource(new_target_name, uid=current_user()["id"])
                if not final_target_id:
                    st.error("Selecciona o escribe el recurso del que depende.")
                elif not param_name.strip():
                    st.error("El nombre del parámetro es obligatorio.")
                else:
                    execute(
                        "insert into api_connections (api_id, target_resource_id, param_name, relationship_description) "
                        "values (:api_id, :target_id, :param_name, :desc)",
                        {
                            "api_id": int(selected_op),
                            "target_id": final_target_id,
                            "param_name": param_name.strip(),
                            "desc": relationship_description.strip() or None,
                        },
                    )
                    st.success("Dependencia agregada.")
                    st.rerun()

        if not out_df.empty:
            with st.expander("🗑️ Eliminar una dependencia saliente"):
                conn_opts = [(int(c.id), f"{c.param_name} → {c.target_name}") for c in out_df.itertuples()]
                conn_to_delete = select_with_id("Dependencia", conn_opts, key=f"del_conn_select_{selected_op}")
                if confirm_delete_button("Eliminar dependencia seleccionada", f"del_conn_{selected_op}_{conn_to_delete}"):
                    execute("delete from api_connections where id = :id", {"id": conn_to_delete})
                    st.session_state[f"del_conn_{selected_op}_{conn_to_delete}"] = False
                    st.success("Dependencia eliminada.")
                    st.rerun()

        with st.expander("✏️ Editar / eliminar esta operación"):
            same_resource_ops = list_ops(resource_id=int(row["resource_id"]))
            requires_opts = [
                (int(o.id), o.name) for o in same_resource_ops.itertuples() if int(o.id) != int(selected_op)
            ]
            with st.form(f"edit_op_{selected_op}"):
                e_name = st.text_input("Nombre de la operación", value=row["name"])
                method_options = ["GET", "POST", "PUT", "PATCH", "DELETE", "N/A"]
                e_method = st.selectbox(
                    "Método", method_options, index=method_options.index(row["method"]) if row["method"] in method_options else 5
                )
                e_endpoint = st.text_input("Endpoint / URL", value=row["endpoint"] or "")
                e_description = st.text_area("Descripción", value=row["description"] or "")
                e_top = st.text_input("Categoría (modelo)", value=row["top_category"] or "")
                e_sub = st.text_input("Subcategoría", value=row["sub_category"] or "")
                e_requires = select_with_id(
                    "Requiere llamar antes a (mismo recurso)",
                    requires_opts,
                    current_id=int(requires_id) if requires_id is not None and not pd.isna(requires_id) else None,
                    allow_none=True,
                    key=f"edit_requires_{selected_op}",
                )
                save = st.form_submit_button("Guardar cambios")
            if save:
                if not e_name.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    category_id, _ = get_or_create_category(e_top, e_sub)
                    execute(
                        """
                        update apis
                        set name = :name, method = :method, endpoint = :endpoint, description = :description,
                            category_id = :category_id, requires_list_of_id = :requires_id,
                            updated_by = :uid, updated_at = now()
                        where id = :id
                        """,
                        {
                            "name": e_name.strip(),
                            "method": e_method,
                            "endpoint": e_endpoint.strip(),
                            "description": e_description.strip(),
                            "category_id": category_id,
                            "requires_id": e_requires,
                            "uid": current_user()["id"],
                            "id": int(selected_op),
                        },
                    )
                    st.success("Operación actualizada.")
                    st.rerun()

            if confirm_delete_button("🗑️ Eliminar esta operación", f"del_op_{selected_op}"):
                execute("delete from apis where id = :id", {"id": int(selected_op)})
                st.session_state[f"del_op_{selected_op}"] = False
                st.success("Operación eliminada.")
                st.rerun()

st.divider()

with st.expander("📤 Exportar a Excel"):
    st.caption(
        "Genera un archivo .xlsx con todas las operaciones (endpoints), sus dependencias "
        "(parámetros que conectan un recurso con otro) y el catálogo de recursos."
    )

    export_ops_df = fetch_df(
        """
        select r.name as recurso, a.name as operacion, a.method as metodo, a.endpoint,
               a.description as descripcion, c.top_category as categoria, c.sub_category as subcategoria,
               a.status as estado, req.name as requiere_antes
        from apis a
        join api_resources r on r.id = a.resource_id
        left join api_categories c on c.id = a.category_id
        left join apis req on req.id = a.requires_list_of_id
        order by r.name, a.name
        """,
        ttl=15,
    )
    export_deps_df = fetch_df(
        """
        select r2.name as recurso_origen, a2.name as operacion_origen, ac.param_name as parametro,
               r.name as recurso_destino, ac.relationship_description as descripcion_relacion
        from api_connections ac
        join apis a2 on a2.id = ac.api_id
        join api_resources r2 on r2.id = a2.resource_id
        join api_resources r on r.id = ac.target_resource_id
        order by r2.name, a2.name
        """,
        ttl=15,
    )
    export_resources_df = fetch_df(
        "select name as recurso, description as descripcion from api_resources order by name", ttl=15
    )

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        export_ops_df.to_excel(writer, sheet_name="Operaciones", index=False)
        export_deps_df.to_excel(writer, sheet_name="Dependencias", index=False)
        export_resources_df.to_excel(writer, sheet_name="Recursos", index=False)
        for sheet_name, sheet_df in (
            ("Operaciones", export_ops_df),
            ("Dependencias", export_deps_df),
            ("Recursos", export_resources_df),
        ):
            worksheet = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(sheet_df.columns, start=1):
                max_len = max([len(str(col_name))] + [len(str(v)) for v in sheet_df[col_name].head(200)])
                worksheet.column_dimensions[worksheet.cell(row=1, column=col_idx).column_letter].width = min(
                    max(max_len + 2, 10), 60
                )

    st.download_button(
        "⬇️ Descargar Excel",
        data=excel_buffer.getvalue(),
        file_name="apis_q10.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with st.expander("📋 Ver tabla completa de operaciones"):
    full_df = fetch_df(
        """
        select r.name as recurso, a.name as operacion, a.method as metodo, a.endpoint,
               c.top_category as categoria, c.sub_category as subcategoria
        from apis a
        join api_resources r on r.id = a.resource_id
        left join api_categories c on c.id = a.category_id
        order by r.name, a.name
        """,
        ttl=15,
    )
    st.dataframe(full_df, use_container_width=True, hide_index=True)

if can_edit():
    with st.expander("➕ Agregar endpoint / operación"):
        st.caption("Elige un recurso existente o escribe el nombre de uno nuevo para agruparlo en el mapa.")
        col_res, col_new = st.columns(2)
        with col_res:
            new_op_resource_id = select_with_id(
                "Recurso existente", resource_opts, allow_none=True, key="new_op_resource"
            )
        with col_new:
            new_op_resource_name = st.text_input("...o nombre de un recurso nuevo", key="new_op_resource_name")

        existing_ops_for_resource = []
        if new_op_resource_id and not new_op_resource_name.strip():
            existing_ops_for_resource = [
                (int(o.id), o.name) for o in list_ops(resource_id=new_op_resource_id).itertuples()
            ]

        with st.form("add_op", clear_on_submit=True):
            op_name = st.text_input("Nombre de la operación")
            op_method = st.selectbox("Método", ["GET", "POST", "PUT", "PATCH", "DELETE", "N/A"], key="new_op_method")
            op_endpoint = st.text_input("Endpoint / URL")
            op_description = st.text_area("Descripción")
            top_categories = list_top_categories()
            op_top = st.text_input(
                "Categoría (modelo)",
                help="Ej. Colegios, ETDH, Transversal. Existentes: " + (", ".join(top_categories) if top_categories else "—"),
            )
            op_sub = st.text_input("Subcategoría", help="Ej. Específico, Financiero: Facturas, CRM (Comercial)...")
            op_requires = select_with_id(
                "Requiere llamar antes a (opcional, mismo recurso)",
                existing_ops_for_resource,
                allow_none=True,
                key="new_op_requires",
            )
            submitted_op = st.form_submit_button("Guardar operación")
        if submitted_op:
            if not op_name.strip():
                st.error("El nombre de la operación es obligatorio.")
            elif not new_op_resource_id and not new_op_resource_name.strip():
                st.error("Selecciona un recurso existente o escribe el nombre de uno nuevo.")
            elif not op_top.strip() or not op_sub.strip():
                st.error("La categoría y la subcategoría son obligatorias (así se colorea y filtra en el mapa).")
            else:
                uid = current_user()["id"]
                resource_id = (
                    get_or_create_resource(new_op_resource_name, uid=uid)
                    if new_op_resource_name.strip()
                    else new_op_resource_id
                )
                category_id, _ = get_or_create_category(op_top, op_sub)
                execute(
                    """
                    insert into apis
                        (name, method, endpoint, description, status, resource_id, category_id, requires_list_of_id,
                         created_by, updated_by)
                    values
                        (:name, :method, :endpoint, :description, 'activo', :resource_id, :category_id, :requires_id,
                         :uid, :uid)
                    """,
                    {
                        "name": op_name.strip(),
                        "method": op_method,
                        "endpoint": op_endpoint.strip(),
                        "description": op_description.strip(),
                        "resource_id": resource_id,
                        "category_id": category_id,
                        "requires_id": op_requires,
                        "uid": uid,
                    },
                )
                st.success("Operación creada. Ya aparece en el mapa.")
                st.rerun()

    with st.expander("🗂️ Gestionar recursos (renombrar / eliminar)"):
        if not resource_opts:
            st.caption("Sin recursos todavía.")
        else:
            manage_resource_id = select_with_id("Recurso", resource_opts, key="manage_resource_select")
            res_row = resources_df.set_index("id").loc[manage_resource_id]
            with st.form(f"edit_resource_{manage_resource_id}"):
                r_name = st.text_input("Nombre", value=res_row["name"])
                r_description = st.text_area("Descripción", value=res_row["description"] or "")
                save_res = st.form_submit_button("Guardar cambios")
            if save_res:
                if not r_name.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    execute(
                        "update api_resources set name = :name, description = :description, "
                        "updated_by = :uid, updated_at = now() where id = :id",
                        {
                            "name": r_name.strip(),
                            "description": r_description.strip() or None,
                            "uid": current_user()["id"],
                            "id": int(manage_resource_id),
                        },
                    )
                    st.success("Recurso actualizado.")
                    st.rerun()

            st.caption("⚠️ Eliminar un recurso borra también todas sus operaciones y las dependencias asociadas.")
            if confirm_delete_button("🗑️ Eliminar este recurso", f"del_resource_{manage_resource_id}"):
                execute("delete from api_resources where id = :id", {"id": int(manage_resource_id)})
                st.session_state[f"del_resource_{manage_resource_id}"] = False
                st.success("Recurso eliminado.")
                st.rerun()
