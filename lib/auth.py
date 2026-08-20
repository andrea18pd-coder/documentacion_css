"""Login propio y control de acceso por rol (admin / editor / lector)."""

import streamlit as st
import bcrypt

from lib.db import fetch_df

ROLES = ["admin", "editor", "lector"]


def _get_user_by_email(email):
    df = fetch_df(
        "select id, email, name, password_hash, role, active from users where email = :email",
        {"email": email},
        ttl=0,
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def login_form():
    with st.form("login_form"):
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar", use_container_width=True)

    if not submitted:
        return

    if not email or not password:
        st.error("Ingresa correo y contraseña.")
        return

    try:
        user = _get_user_by_email(email.strip().lower())
    except Exception:
        st.error("No fue posible conectar con la base de datos. Verifica la configuración de `secrets.toml`.")
        return

    if not user or not user["active"]:
        st.error("Usuario no encontrado o inactivo.")
        return

    if bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        st.session_state.user = {
            "id": int(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        }
        st.rerun()
    else:
        st.error("Contraseña incorrecta.")


def current_user():
    return st.session_state.get("user")


def is_logged_in():
    return "user" in st.session_state


def logout():
    st.session_state.pop("user", None)
    st.rerun()


def has_role(allowed_roles):
    user = current_user()
    return bool(user and user["role"] in allowed_roles)


def can_edit():
    return has_role(["admin", "editor"])


def is_admin():
    return has_role(["admin"])


def guard_page(allowed_roles=None):
    """Detiene la ejecución de la página si el usuario no está logueado o no tiene el rol requerido."""
    if not is_logged_in():
        st.warning("Debes iniciar sesión para ver esta página.")
        st.stop()
    if allowed_roles and not has_role(allowed_roles):
        st.error("No tienes permisos para ver esta página.")
        st.stop()
