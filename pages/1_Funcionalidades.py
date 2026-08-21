import pandas as pd
import streamlit as st

from lib.auth import guard_page, can_edit, current_user
from lib.ui import (
    inject_css,
    page_header,
    top_bar,
    select_with_id,
    multiselect_with_id,
    confirm_delete_button,
    consume_jump,
    val_or_dash,
    dataframe_to_markdown,
    markdown_to_dataframe,
    field_card,
    extract_activation_codes,
)
from lib.db import fetch_df, execute, execute_returning_id
from lib.catalog import list_modules, list_plans, list_types, options

inject_css()
guard_page()
top_bar(current_user())
page_header("Funcionalidades", "¿Qué hay que habilitar? Parámetros, funciones y pasos de activación por petición")

consume_jump(
    "jump_functionality_id",
    "detail_select",
    {"filter_module": None, "filter_type": None, "filter_plan": None},
)

modules_df, plans_df, types_df = list_modules(), list_plans(), list_types()
module_opts, plan_opts, type_opts = options(modules_df), options(plans_df), options(types_df)

if not module_opts or not type_opts:
    st.info(
        "Todavía no hay módulos o tipos registrados. Un administrador debe crearlos primero "
        "en la página **Administración**."
    )

# --- Filtros ---
col1, col2, col3 = st.columns(3)
with col1:
    f_module = select_with_id("Módulo", module_opts, allow_none=True, none_label="Todos", key="filter_module")
with col2:
    f_type = select_with_id("Tipo", type_opts, allow_none=True, none_label="Todos", key="filter_type")
with col3:
    f_plan = select_with_id("Plan", plan_opts, allow_none=True, none_label="Todos", key="filter_plan")

query = """
    select f.id, f.name, f.description, f.request_type, f.activation_notes, f.status,
           f.module_id, f.type_id,
           m.name as module_name, t.name as type_name
    from functionalities f
    left join modules m on m.id = f.module_id
    left join types t on t.id = f.type_id
    where (:module_id is null or f.module_id = :module_id)
      and (:type_id is null or f.type_id = :type_id)
      and (
        :plan_id is null or exists (
            select 1 from functionality_plans fp
            where fp.functionality_id = f.id and fp.plan_id = :plan_id
        )
      )
    order by f.name
"""
df = fetch_df(query, {"module_id": f_module, "type_id": f_type, "plan_id": f_plan}, ttl=15)

if df.empty:
    st.info("No hay funcionalidades que coincidan con el filtro.")
else:
    selected_id = select_with_id(
        "Selecciona una funcionalidad",
        [(int(r.id), r["name"]) for _, r in df.iterrows()],
        key="detail_select",
    )
    row = df.set_index("id").loc[selected_id]

    item_plans_df = fetch_df(
        "select p.id, p.name from functionality_plans fp join plans p on p.id = fp.plan_id where fp.functionality_id = :id order by p.name",
        {"id": int(selected_id)},
        ttl=15,
    )
    plans_value = ", ".join(item_plans_df["name"]) if not item_plans_df.empty else "—"

    col_desc, col_module, col_type, col_request, col_plans = st.columns([2, 1, 1, 1, 1])
    with col_desc:
        field_card("Descripción", val_or_dash(row["description"]), key=f"q10-field-card-desc-{selected_id}")
    with col_module:
        field_card("Módulo", val_or_dash(row["module_name"]), key=f"q10-field-card-modulo-{selected_id}")
    with col_type:
        field_card("Tipo", val_or_dash(row["type_name"]), key=f"q10-field-card-tipo-{selected_id}")
    with col_request:
        field_card(
            "Tipo de petición", val_or_dash(row["request_type"]), key=f"q10-field-card-peticion-{selected_id}"
        )
    with col_plans:
        field_card("Planes", plans_value, key=f"q10-field-card-planes-{selected_id}")

    st.markdown("**Pasos de activación**")
    activation_notes = row["activation_notes"]
    if pd.notna(activation_notes) and str(activation_notes).strip():
        st.markdown(activation_notes)
        codes = extract_activation_codes(activation_notes)
        if codes:
            st.caption("Códigos listos para copiar y pegar (habilitación en BD):")
            st.code(",".join(codes), language=None)
    else:
        st.caption("—")

    st.markdown("#### Consideraciones y notas")
    notes_df = fetch_df(
        """
        select n.id, n.note_text, n.note_type, n.query_id, n.created_at, u.name as author
        from notes n
        left join users u on u.id = n.created_by
        where n.functionality_id = :id
        order by n.created_at desc
        """,
        {"id": int(selected_id)},
        ttl=15,
    )
    if notes_df.empty:
        st.caption("Sin notas registradas todavía.")
    else:
        for _, n in notes_df.iterrows():
            if n["note_type"] == "Tabla":
                st.markdown("**[Tabla]**")
                st.markdown(n["note_text"])
                st.caption(f"{n['author'] or 'Usuario'} · {n['created_at']}")
            elif n["note_type"] == "Query" and pd.notna(n["query_id"]):
                col_q, col_btn = st.columns([5, 1])
                with col_q:
                    st.markdown(
                        f"- **[Query]** {n['note_text']}  \n"
                        f"  <span style='color:#6B7280;font-size:0.85em'>{n['author'] or 'Usuario'} · {n['created_at']}</span>",
                        unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("Ver query →", key=f"goto_query_{n['id']}"):
                        st.session_state["jump_query_id"] = int(n["query_id"])
                        st.switch_page("pages/6_Queries.py")
            else:
                st.markdown(
                    f"- **[{n['note_type'] or 'Nota'}]** {n['note_text']}  \n"
                    f"  <span style='color:#6B7280;font-size:0.85em'>{n['author'] or 'Usuario'} · {n['created_at']}</span>",
                    unsafe_allow_html=True,
                )

            if can_edit():
                with st.expander(f"✏️ Editar / eliminar esta nota ({n['note_type'] or 'Nota'})"):
                    if n["note_type"] == "Query":
                        queries_df = fetch_df("select id, name from queries order by name", ttl=15)
                        if queries_df.empty:
                            st.warning("No hay queries registrados.")
                        else:
                            query_opts_edit = [(int(r.id), r["name"]) for _, r in queries_df.iterrows()]
                            e_query_id = select_with_id(
                                "Query",
                                query_opts_edit,
                                current_id=int(n["query_id"]) if pd.notna(n["query_id"]) else None,
                                key=f"edit_note_query_{n['id']}",
                            )
                            if st.button("Guardar cambios", key=f"save_note_{n['id']}"):
                                e_name = queries_df.set_index("id").loc[e_query_id, "name"]
                                execute(
                                    "update notes set query_id = :qid, note_text = :text where id = :id",
                                    {"qid": e_query_id, "text": e_name, "id": int(n["id"])},
                                )
                                st.success("Nota actualizada.")
                                st.rerun()
                    elif n["note_type"] == "Tabla":
                        existing_df = markdown_to_dataframe(n["note_text"])
                        if existing_df is None or existing_df.empty:
                            existing_df = pd.DataFrame([{"Columna A": "", "Columna B": ""} for _ in range(3)])

                        columns_key = f"edit_note_table_cols_{n['id']}"
                        columns_input = st.text_input(
                            "Columnas (separadas por coma)",
                            value=st.session_state.get(columns_key, ", ".join(existing_df.columns)),
                            key=columns_key,
                        )
                        columns = [c.strip() for c in columns_input.split(",") if c.strip()]

                        edited_df = None
                        if not columns:
                            st.warning("Define al menos una columna.")
                        else:
                            base_df = existing_df.reindex(columns=columns, fill_value="")
                            edited_df = st.data_editor(
                                base_df,
                                num_rows="dynamic",
                                use_container_width=True,
                                key=f"edit_note_table_editor_{n['id']}_{len(columns)}_{columns_input}",
                            )

                        if st.button("Guardar cambios", key=f"save_note_{n['id']}"):
                            md_table = dataframe_to_markdown(edited_df) if edited_df is not None else ""
                            if not md_table:
                                st.error("Completa al menos una fila con datos.")
                            else:
                                execute(
                                    "update notes set note_text = :text where id = :id",
                                    {"text": md_table, "id": int(n["id"])},
                                )
                                st.success("Nota actualizada.")
                                st.rerun()
                    else:
                        e_type_options = ["Consideración", "Advertencia", "Limitación", "Tip"]
                        current_type = n["note_type"] if n["note_type"] in e_type_options else e_type_options[0]
                        e_note_type = st.selectbox(
                            "Tipo de nota",
                            e_type_options,
                            index=e_type_options.index(current_type),
                            key=f"edit_note_type_{n['id']}",
                        )
                        e_text = st.text_area("Nota", value=n["note_text"], key=f"edit_note_text_{n['id']}")
                        if st.button("Guardar cambios", key=f"save_note_{n['id']}"):
                            if not e_text.strip():
                                st.error("El texto de la nota es obligatorio.")
                            else:
                                execute(
                                    "update notes set note_text = :text, note_type = :type where id = :id",
                                    {"text": e_text.strip(), "type": e_note_type, "id": int(n["id"])},
                                )
                                st.success("Nota actualizada.")
                                st.rerun()

                    if confirm_delete_button("🗑️ Eliminar nota", f"del_note_{n['id']}"):
                        execute("delete from notes where id = :id", {"id": int(n["id"])})
                        st.session_state[f"del_note_{n['id']}"] = False
                        st.success("Nota eliminada.")
                        st.rerun()

    if can_edit():
        with st.expander("➕ Agregar nota"):
            note_type = st.selectbox(
                "Tipo de nota",
                ["Consideración", "Advertencia", "Limitación", "Tip", "Tabla", "Query"],
                key=f"note_type_{selected_id}",
            )

            if note_type == "Query":
                queries_df = fetch_df("select id, name from queries order by name", ttl=15)
                if queries_df.empty:
                    st.warning(
                        "Todavía no hay queries registrados. Créalos primero en la página **Queries**."
                    )
                else:
                    query_opts = [(int(r.id), r["name"]) for _, r in queries_df.iterrows()]
                    picked_query_id = select_with_id("Query", query_opts, key=f"note_query_pick_{selected_id}")
                    if st.button("Guardar nota", key=f"save_note_query_{selected_id}"):
                        picked_name = queries_df.set_index("id").loc[picked_query_id, "name"]
                        execute(
                            "insert into notes (functionality_id, note_text, note_type, query_id, created_by) "
                            "values (:fid, :text, 'Query', :qid, :uid)",
                            {
                                "fid": int(selected_id),
                                "text": picked_name,
                                "qid": picked_query_id,
                                "uid": current_user()["id"],
                            },
                        )
                        st.success("Nota de query agregada.")
                        st.rerun()
            elif note_type == "Tabla":
                st.caption(
                    "Útil para funcionalidades que dependen de modelo académico, modelo financiero o plan. "
                    "Escribe los nombres de columnas separados por coma, luego llena las filas (puedes agregar/quitar filas "
                    "con los botones + / 🗑️ de la tabla)."
                )
                columns_key = f"note_table_cols_{selected_id}"
                columns_input = st.text_input(
                    "Columnas (separadas por coma)",
                    value=st.session_state.get(columns_key, "Columna A, Columna B"),
                    key=columns_key,
                )
                columns = [c.strip() for c in columns_input.split(",") if c.strip()]

                edited_df = None
                if not columns:
                    st.warning("Define al menos una columna.")
                else:
                    empty_df = pd.DataFrame([{c: "" for c in columns} for _ in range(3)])
                    edited_df = st.data_editor(
                        empty_df,
                        num_rows="dynamic",
                        use_container_width=True,
                        key=f"note_table_editor_{selected_id}_{len(columns)}_{columns_input}",
                    )

                if st.button("Guardar tabla", key=f"save_note_table_{selected_id}"):
                    md_table = dataframe_to_markdown(edited_df) if edited_df is not None else ""
                    if not md_table:
                        st.error("Completa al menos una fila con datos.")
                    else:
                        execute(
                            "insert into notes (functionality_id, note_text, note_type, created_by) values (:fid, :text, 'Tabla', :uid)",
                            {"fid": int(selected_id), "text": md_table, "uid": current_user()["id"]},
                        )
                        st.success("Tabla agregada.")
                        st.rerun()
            else:
                with st.form(f"add_note_{selected_id}", clear_on_submit=True):
                    note_text = st.text_area("Nota")
                    submitted = st.form_submit_button("Guardar nota")
                if submitted:
                    if not note_text.strip():
                        st.error("El texto de la nota es obligatorio.")
                    else:
                        execute(
                            "insert into notes (functionality_id, note_text, note_type, created_by) values (:fid, :text, :type, :uid)",
                            {
                                "fid": int(selected_id),
                                "text": note_text.strip(),
                                "type": note_type,
                                "uid": current_user()["id"],
                            },
                        )
                        st.success("Nota agregada.")
                        st.rerun()

        with st.expander("✏️ Editar / eliminar esta funcionalidad"):
            with st.form(f"edit_func_{selected_id}"):
                e_name = st.text_input("Nombre", value=row["name"])
                e_description = st.text_area("Descripción", value=row["description"] or "")
                e_request_type = st.text_input("Tipo de petición", value=row["request_type"] or "")
                e_activation_notes = st.text_area("Pasos de activación", value=row["activation_notes"] or "")
                e_module_id = select_with_id(
                    "Módulo", module_opts, current_id=row["module_id"], allow_none=True, key=f"edit_module_{selected_id}"
                )
                e_type_id = select_with_id(
                    "Tipo", type_opts, current_id=row["type_id"], allow_none=True, key=f"edit_type_{selected_id}"
                )
                e_plan_ids = multiselect_with_id(
                    "Planes", plan_opts, current_ids=list(item_plans_df["id"]), key=f"edit_plans_{selected_id}"
                )
                e_status = st.selectbox(
                    "Estado", ["activo", "deprecado"], index=0 if row["status"] == "activo" else 1, key=f"edit_status_{selected_id}"
                )
                save = st.form_submit_button("Guardar cambios")
            if save:
                execute(
                    """
                    update functionalities
                    set name = :name, description = :description, module_id = :module_id, type_id = :type_id,
                        request_type = :request_type, activation_notes = :activation_notes, status = :status,
                        updated_by = :uid, updated_at = now()
                    where id = :id
                    """,
                    {
                        "name": e_name.strip(),
                        "description": e_description.strip(),
                        "module_id": e_module_id,
                        "type_id": e_type_id,
                        "request_type": e_request_type.strip(),
                        "activation_notes": e_activation_notes.strip(),
                        "status": e_status,
                        "uid": current_user()["id"],
                        "id": int(selected_id),
                    },
                )
                execute("delete from functionality_plans where functionality_id = :id", {"id": int(selected_id)})
                for plan_id in e_plan_ids:
                    execute(
                        "insert into functionality_plans (functionality_id, plan_id) values (:fid, :pid)",
                        {"fid": int(selected_id), "pid": plan_id},
                    )
                st.success("Funcionalidad actualizada.")
                st.rerun()

            if confirm_delete_button("🗑️ Eliminar funcionalidad", f"del_func_{selected_id}"):
                execute("delete from functionalities where id = :id", {"id": int(selected_id)})
                st.session_state[f"del_func_{selected_id}"] = False
                st.success("Funcionalidad eliminada.")
                st.rerun()

st.divider()

with st.expander("📋 Ver tabla completa de funcionalidades"):
    st.dataframe(
        df[["name", "module_name", "type_name", "request_type", "status"]] if not df.empty else df,
        use_container_width=True,
        hide_index=True,
    )

if can_edit():
    with st.expander("➕ Agregar nueva funcionalidad"):
        with st.form("add_functionality", clear_on_submit=True):
            name = st.text_input("Nombre")
            description = st.text_area("Descripción")
            request_type = st.text_input("Tipo de petición que la requiere")
            activation_notes = st.text_area("Pasos de activación")
            module_id = select_with_id("Módulo", module_opts, allow_none=True, key="new_func_module")
            type_id = select_with_id("Tipo", type_opts, allow_none=True, key="new_func_type")
            plan_ids = multiselect_with_id("Planes en los que aplica", plan_opts, key="new_func_plans")
            status = st.selectbox("Estado", ["activo", "deprecado"], key="new_func_status")
            submitted = st.form_submit_button("Guardar funcionalidad")
        if submitted:
            if not name.strip():
                st.error("El nombre es obligatorio.")
            else:
                new_id = execute_returning_id(
                    """
                    insert into functionalities
                        (name, description, module_id, type_id, request_type, activation_notes, status, created_by, updated_by)
                    values
                        (:name, :description, :module_id, :type_id, :request_type, :activation_notes, :status, :uid, :uid)
                    returning id
                    """,
                    {
                        "name": name.strip(),
                        "description": description.strip(),
                        "module_id": module_id,
                        "type_id": type_id,
                        "request_type": request_type.strip(),
                        "activation_notes": activation_notes.strip(),
                        "status": status,
                        "uid": current_user()["id"],
                    },
                )
                for plan_id in plan_ids:
                    execute(
                        "insert into functionality_plans (functionality_id, plan_id) values (:fid, :pid)",
                        {"fid": new_id, "pid": plan_id},
                    )
                st.success("Funcionalidad creada.")
                st.rerun()
