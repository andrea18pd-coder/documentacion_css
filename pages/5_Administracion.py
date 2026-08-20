import streamlit as st
import bcrypt

from lib.auth import guard_page, current_user
from lib.ui import inject_css, page_header, top_bar, confirm_delete_button
from lib.db import fetch_df, execute
from lib.catalog import render_catalog_manager

inject_css()
guard_page(["admin"])
top_bar(current_user())
page_header("Administración", "Gestión de usuarios y catálogos base (módulos, planes, tipos)")

tab_users, tab_modules, tab_plans, tab_types = st.tabs(["Usuarios", "Módulos", "Planes", "Tipos"])

with tab_users:
    st.subheader("Usuarios registrados")
    users_df = fetch_df("select id, email, name, role, active, created_at from users order by name", ttl=5)
    st.dataframe(users_df, use_container_width=True, hide_index=True)

    st.markdown("#### Crear nuevo usuario")
    with st.form("new_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            new_email = st.text_input("Correo")
            new_name = st.text_input("Nombre")
        with c2:
            new_role = st.selectbox("Rol", ["lector", "editor", "admin"], key="new_user_role")
            new_password = st.text_input("Contraseña temporal", type="password")
        create_submitted = st.form_submit_button("Crear usuario")

    if create_submitted:
        if not (new_email.strip() and new_name.strip() and new_password):
            st.error("Completa correo, nombre y contraseña.")
        else:
            existing = fetch_df("select id from users where email = :email", {"email": new_email.strip().lower()}, ttl=0)
            if not existing.empty:
                st.error("Ya existe un usuario con ese correo.")
            else:
                hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                execute(
                    "insert into users (email, name, password_hash, role, active) values (:email, :name, :hash, :role, true)",
                    {"email": new_email.strip().lower(), "name": new_name.strip(), "hash": hashed, "role": new_role},
                )
                st.success(f"Usuario {new_email} creado.")
                st.rerun()

    st.markdown("#### Editar / desactivar / eliminar usuario")
    if users_df.empty:
        st.caption("No hay usuarios para editar.")
    else:
        target_id = st.selectbox(
            "Usuario",
            users_df["id"],
            format_func=lambda i: users_df.set_index("id").loc[i, "email"],
            key="edit_user_select",
        )
        target = users_df.set_index("id").loc[target_id]

        with st.form("edit_user_form"):
            e_name = st.text_input("Nombre", value=target["name"])
            e_role = st.selectbox(
                "Rol", ["lector", "editor", "admin"], index=["lector", "editor", "admin"].index(target["role"])
            )
            e_active = st.checkbox("Activo", value=bool(target["active"]))
            e_password = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password")
            save = st.form_submit_button("Guardar cambios")

        if save:
            is_self = int(target_id) == current_user()["id"]
            if is_self and (e_role != "admin" or not e_active):
                st.error("No puedes quitarte a ti mismo el rol de administrador ni desactivarte.")
            else:
                if e_password:
                    hashed = bcrypt.hashpw(e_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                    execute(
                        "update users set name = :name, role = :role, active = :active, password_hash = :hash where id = :id",
                        {"name": e_name.strip(), "role": e_role, "active": e_active, "hash": hashed, "id": int(target_id)},
                    )
                else:
                    execute(
                        "update users set name = :name, role = :role, active = :active where id = :id",
                        {"name": e_name.strip(), "role": e_role, "active": e_active, "id": int(target_id)},
                    )
                st.success("Usuario actualizado.")
                st.rerun()

        if int(target_id) == current_user()["id"]:
            st.caption("No puedes eliminar tu propio usuario.")
        elif confirm_delete_button("🗑️ Eliminar usuario", f"del_user_{target_id}"):
            execute("delete from users where id = :id", {"id": int(target_id)})
            st.session_state[f"del_user_{target_id}"] = False
            st.success("Usuario eliminado.")
            st.rerun()

with tab_modules:
    render_catalog_manager("Módulos", "modules")

with tab_plans:
    render_catalog_manager("Planes", "plans")

with tab_types:
    render_catalog_manager("Tipos", "types")
