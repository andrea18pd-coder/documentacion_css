import pandas as pd
import streamlit as st

from lib.auth import guard_page, can_edit, current_user
from lib.ui import inject_css, page_header, top_bar, select_with_id, confirm_delete_button
from lib.db import fetch_df, execute
from lib.sql_import import parse_sql_sections

inject_css()
guard_page()
top_bar(current_user())
page_header(
    "Sentencias - Nivel II",
    "Queries SQL de uso frecuente, subidos en bloque desde archivos .sql y organizados por archivo",
)

files_df = fetch_df(
    "select distinct source_file from sql_statements where source_file is not null order by source_file",
    ttl=30,
)
file_opts = ["Todos"] + files_df["source_file"].tolist()

col_search, col_file = st.columns([3, 1])
with col_search:
    search = st.text_input(
        "Buscar", key="sql_stmt_search", placeholder="🔍 Buscar por título, etiqueta o contenido del SQL…"
    )
with col_file:
    file_filter = st.selectbox("Archivo de origen", file_opts, key="sql_stmt_file_filter")

where = []
params = {}
if search and search.strip():
    where.append("(title ilike :q or tags ilike :q or sql_text ilike :q)")
    params["q"] = f"%{search.strip()}%"
if file_filter != "Todos":
    where.append("source_file = :file")
    params["file"] = file_filter
where_sql = f"where {' and '.join(where)}" if where else ""

df = fetch_df(
    f"select id, title, sql_text, source_file, tags from sql_statements {where_sql} order by title",
    params,
    ttl=15,
)

if df.empty:
    st.info("No hay sentencias que coincidan con el filtro. Sube un archivo .sql más abajo para empezar.")
else:
    st.caption(f"{len(df)} sentencia(s)")
    selected_id = select_with_id(
        "Selecciona una sentencia",
        [(int(r.id), r["title"]) for _, r in df.iterrows()],
        key="sql_stmt_detail_select",
    )
    row = df.set_index("id").loc[selected_id]

    badge_bits = []
    if pd.notna(row["source_file"]) and str(row["source_file"]).strip():
        badge_bits.append(f"📄 {row['source_file']}")
    if pd.notna(row["tags"]) and str(row["tags"]).strip():
        badge_bits.append(f"🏷️ {row['tags']}")
    if badge_bits:
        st.caption(" · ".join(badge_bits))
    st.code(row["sql_text"], language="sql")

    if can_edit():
        with st.expander("✏️ Editar / eliminar esta sentencia"):
            with st.form(f"edit_stmt_{selected_id}"):
                e_title = st.text_input("Título", value=row["title"])
                e_tags = st.text_input("Etiquetas", value=row["tags"] or "")
                e_sql = st.text_area("SQL", value=row["sql_text"], height=220)
                save = st.form_submit_button("Guardar cambios")
            if save:
                if not e_title.strip() or not e_sql.strip():
                    st.error("El título y el SQL son obligatorios.")
                else:
                    execute(
                        """
                        update sql_statements
                        set title = :title, tags = :tags, sql_text = :sql_text, updated_by = :uid, updated_at = now()
                        where id = :id
                        """,
                        {
                            "title": e_title.strip(),
                            "tags": e_tags.strip() or None,
                            "sql_text": e_sql.strip(),
                            "uid": current_user()["id"],
                            "id": int(selected_id),
                        },
                    )
                    st.success("Sentencia actualizada.")
                    st.rerun()

            if confirm_delete_button("🗑️ Eliminar sentencia", f"del_stmt_{selected_id}"):
                execute("delete from sql_statements where id = :id", {"id": int(selected_id)})
                st.session_state[f"del_stmt_{selected_id}"] = False
                st.success("Sentencia eliminada.")
                st.rerun()

st.divider()

with st.expander("📋 Ver tabla completa de sentencias"):
    full_df = fetch_df(
        "select title, source_file, tags from sql_statements order by source_file, title", ttl=15
    )
    st.dataframe(full_df, use_container_width=True, hide_index=True)

if can_edit():
    with st.expander("⬆️ Subir archivo(s) .sql"):
        st.caption(
            "Cada archivo se divide automáticamente en sentencias usando los comentarios tipo "
            "«-------- Título --------» (como en un script de trabajo con varios queries sueltos). "
            "Si el archivo no tiene ese formato, se guarda completo como una sola sentencia. "
            "Si vuelves a subir un archivo con el mismo nombre, se reemplazan las sentencias que "
            "ya tenías de ese archivo."
        )
        uploaded_files = st.file_uploader(
            "Archivos .sql", type=["sql", "txt"], accept_multiple_files=True, key="sql_upload"
        )
        tags_for_upload = st.text_input("Etiquetas para estas sentencias (opcional)", key="sql_upload_tags")
        if st.button("Procesar e importar", key="sql_upload_submit"):
            if not uploaded_files:
                st.error("Selecciona al menos un archivo.")
            else:
                total_sections = 0
                for f in uploaded_files:
                    raw = f.getvalue()
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        text = raw.decode("latin-1")
                    fallback_title = f.name.rsplit(".", 1)[0]
                    sections = parse_sql_sections(text, fallback_title)
                    execute("delete from sql_statements where source_file = :f", {"f": f.name})
                    for title, sql_text in sections:
                        execute(
                            """
                            insert into sql_statements (title, sql_text, source_file, tags, created_by, updated_by)
                            values (:title, :sql_text, :file, :tags, :uid, :uid)
                            """,
                            {
                                "title": title[:200],
                                "sql_text": sql_text,
                                "file": f.name,
                                "tags": tags_for_upload.strip() or None,
                                "uid": current_user()["id"],
                            },
                        )
                    total_sections += len(sections)
                st.success(f"Se importaron {total_sections} sentencia(s) de {len(uploaded_files)} archivo(s).")
                st.rerun()
