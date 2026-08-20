import streamlit as st

from lib.auth import guard_page, can_edit, current_user
from lib.ui import inject_css, page_header, top_bar, select_with_id, confirm_delete_button, val_or_dash
from lib.db import fetch_df, execute

inject_css()
guard_page()
top_bar(current_user())
page_header(
    "Biblioteca de desarrollos",
    "Recetas reutilizables para habilitar funciones y códigos de personalización por institución",
)

jump_article = st.session_state.pop("jump_dev_article_id", None)
jump_pers = st.session_state.pop("jump_personalization_id", None)
if jump_article is not None:
    st.session_state["biblioteca_section"] = "Biblioteca de desarrollos"
    st.session_state["dev_article_search"] = ""
    st.session_state["dev_article_kind_filter"] = "Todos"
    st.session_state["dev_article_detail_select"] = jump_article
if jump_pers is not None:
    st.session_state["biblioteca_section"] = "Personalizaciones"
    st.session_state["personalization_search"] = ""
    st.session_state["personalization_inst_filter"] = "Todas"
    st.session_state["personalization_detail_select"] = jump_pers

section = st.radio(
    "Sección",
    ["Biblioteca de desarrollos", "Personalizaciones"],
    key="biblioteca_section",
    horizontal=True,
    label_visibility="collapsed",
)

KIND_ICONS = {"Personalización": "🧩", "Funcionalidad": "⚙️", "Eventualidad": "🚨"}
KIND_OPTIONS = ["Personalización", "Funcionalidad", "Eventualidad"]

if section == "Biblioteca de desarrollos":
    st.caption(
        "Catálogo interno: cómo habilitar una personalización (🧩), cambios estándar (⚙️) "
        "o procedimientos ante una eventualidad (🚨)."
    )

    col_search, col_kind = st.columns([3, 1])
    with col_search:
        search = st.text_input(
            "Buscar", key="dev_article_search", placeholder="🔍 Buscar por nombre o contenido…"
        )
    with col_kind:
        kind_filter = st.selectbox("Tipo", ["Todos"] + KIND_OPTIONS, key="dev_article_kind_filter")

    where = []
    params = {}
    if search and search.strip():
        where.append("(name ilike :q or description_html ilike :q)")
        params["q"] = f"%{search.strip()}%"
    if kind_filter != "Todos":
        where.append("kind = :kind")
        params["kind"] = kind_filter
    where_sql = f"where {' and '.join(where)}" if where else ""

    df = fetch_df(
        f"""
        select id, external_id, name, description_html, kind
        from custom_development_articles
        {where_sql}
        order by name
        """,
        params,
        ttl=15,
    )

    if df.empty:
        st.info("No hay artículos que coincidan con la búsqueda.")
    else:
        st.caption(f"{len(df)} artículo(s)")
        selected_id = select_with_id(
            "Selecciona un artículo",
            [(int(r.id), f"{KIND_ICONS.get(r['kind'], '')} {r['name']}") for _, r in df.iterrows()],
            key="dev_article_detail_select",
        )
        row = df.set_index("id").loc[selected_id]

        st.markdown(
            f"**Tipo:** {KIND_ICONS.get(row['kind'], '')} {row['kind']} &nbsp;&nbsp; "
            f"**Código original:** {val_or_dash(row['external_id'])}"
        )
        st.markdown(row["description_html"], unsafe_allow_html=True)

        if can_edit():
            with st.expander("✏️ Editar / eliminar este artículo"):
                with st.form(f"edit_dev_article_{selected_id}"):
                    e_name = st.text_input("Nombre", value=row["name"])
                    e_kind = st.selectbox("Tipo", KIND_OPTIONS, index=KIND_OPTIONS.index(row["kind"]))
                    e_desc = st.text_area("Descripción (HTML)", value=row["description_html"], height=220)
                    save = st.form_submit_button("Guardar cambios")
                if save:
                    if not e_name.strip() or not e_desc.strip():
                        st.error("El nombre y la descripción son obligatorios.")
                    else:
                        execute(
                            """
                            update custom_development_articles
                            set name = :name, kind = :kind, description_html = :desc,
                                updated_by = :uid, updated_at = now()
                            where id = :id
                            """,
                            {
                                "name": e_name.strip(),
                                "kind": e_kind,
                                "desc": e_desc.strip(),
                                "uid": current_user()["id"],
                                "id": int(selected_id),
                            },
                        )
                        st.success("Artículo actualizado.")
                        st.rerun()

                if confirm_delete_button("🗑️ Eliminar este artículo", f"del_dev_article_{selected_id}"):
                    execute("delete from custom_development_articles where id = :id", {"id": int(selected_id)})
                    st.session_state[f"del_dev_article_{selected_id}"] = False
                    st.success("Artículo eliminado.")
                    st.rerun()

    st.divider()

    with st.expander("📋 Ver tabla completa"):
        full_df = fetch_df(
            "select name, kind, external_id from custom_development_articles order by name", ttl=15
        )
        st.dataframe(full_df, use_container_width=True, hide_index=True)

    if can_edit():
        with st.expander("➕ Agregar artículo"):
            with st.form("add_dev_article", clear_on_submit=True):
                name = st.text_input("Nombre")
                kind = st.selectbox("Tipo", KIND_OPTIONS, key="new_dev_article_kind")
                desc = st.text_area("Descripción (HTML)", height=220)
                submitted = st.form_submit_button("Guardar artículo")
            if submitted:
                if not name.strip() or not desc.strip():
                    st.error("El nombre y la descripción son obligatorios.")
                else:
                    execute(
                        """
                        insert into custom_development_articles (name, kind, description_html, created_by, updated_by)
                        values (:name, :kind, :desc, :uid, :uid)
                        """,
                        {"name": name.strip(), "kind": kind, "desc": desc.strip(), "uid": current_user()["id"]},
                    )
                    st.success("Artículo creado.")
                    st.rerun()

else:
    st.caption(
        'Códigos de personalización por institución, referenciados desde notas de funcionalidades '
        '("Personalización: NNN").'
    )

    col_search, col_inst = st.columns([3, 1])
    with col_search:
        search = st.text_input(
            "Buscar", key="personalization_search", placeholder="🔍 Buscar por nombre, código o descripción…"
        )

    df_inst = fetch_df(
        "select distinct institution from personalizations where institution is not null order by institution",
        ttl=60,
    )
    institutions = ["Todas"] + df_inst["institution"].tolist()
    with col_inst:
        inst_filter = st.selectbox("Institución", institutions, key="personalization_inst_filter")

    where = []
    params = {}
    if search and search.strip():
        s = search.strip()
        if s.isdigit():
            where.append("(external_id = :ext or name ilike :q or description ilike :q)")
            params["ext"] = int(s)
            params["q"] = f"%{s}%"
        else:
            where.append("(name ilike :q or description ilike :q)")
            params["q"] = f"%{s}%"
    if inst_filter != "Todas":
        where.append("institution = :inst")
        params["inst"] = inst_filter
    where_sql = f"where {' and '.join(where)}" if where else ""

    df = fetch_df(
        f"""
        select id, external_id, name, description, institution
        from personalizations
        {where_sql}
        order by external_id
        """,
        params,
        ttl=15,
    )

    if df.empty:
        st.info("No hay personalizaciones que coincidan con la búsqueda.")
    else:
        st.caption(f"{len(df)} personalización(es)")
        selected_id = select_with_id(
            "Selecciona una personalización",
            [(int(r.id), f"#{r['external_id']} — {r['name']}") for _, r in df.iterrows()],
            key="personalization_detail_select",
        )
        row = df.set_index("id").loc[selected_id]

        st.markdown(
            f"**Código:** {val_or_dash(row['external_id'])} &nbsp;&nbsp; "
            f"**Institución:** {val_or_dash(row['institution'])}"
        )
        st.markdown(f"**Descripción:** {val_or_dash(row['description'])}")

        if can_edit():
            with st.expander("✏️ Editar / eliminar esta personalización"):
                with st.form(f"edit_personalization_{selected_id}"):
                    e_name = st.text_input("Nombre", value=row["name"])
                    e_inst = st.text_input("Institución", value=row["institution"] or "")
                    e_desc = st.text_area("Descripción", value=row["description"] or "")
                    save = st.form_submit_button("Guardar cambios")
                if save:
                    if not e_name.strip():
                        st.error("El nombre es obligatorio.")
                    else:
                        execute(
                            """
                            update personalizations
                            set name = :name, institution = :inst, description = :desc,
                                updated_by = :uid, updated_at = now()
                            where id = :id
                            """,
                            {
                                "name": e_name.strip(),
                                "inst": e_inst.strip() or None,
                                "desc": e_desc.strip() or None,
                                "uid": current_user()["id"],
                                "id": int(selected_id),
                            },
                        )
                        st.success("Personalización actualizada.")
                        st.rerun()

                if confirm_delete_button("🗑️ Eliminar esta personalización", f"del_personalization_{selected_id}"):
                    execute("delete from personalizations where id = :id", {"id": int(selected_id)})
                    st.session_state[f"del_personalization_{selected_id}"] = False
                    st.success("Personalización eliminada.")
                    st.rerun()

    st.divider()

    with st.expander("📋 Ver tabla completa"):
        full_df = fetch_df(
            "select external_id, name, institution from personalizations order by external_id", ttl=15
        )
        st.dataframe(full_df, use_container_width=True, hide_index=True)

    if can_edit():
        with st.expander("➕ Agregar personalización"):
            with st.form("add_personalization", clear_on_submit=True):
                name = st.text_input("Nombre")
                inst = st.text_input("Institución")
                desc = st.text_area("Descripción")
                submitted = st.form_submit_button("Guardar personalización")
            if submitted:
                if not name.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    execute(
                        """
                        insert into personalizations (name, institution, description, created_by, updated_by)
                        values (:name, :inst, :desc, :uid, :uid)
                        """,
                        {
                            "name": name.strip(),
                            "inst": inst.strip() or None,
                            "desc": desc.strip() or None,
                            "uid": current_user()["id"],
                        },
                    )
                    st.success("Personalización creada.")
                    st.rerun()
