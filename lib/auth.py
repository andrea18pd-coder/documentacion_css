"""Login propio y control de acceso por rol (admin / editor / lector)."""

import secrets as secrets_lib
from datetime import datetime, timedelta, timezone

import streamlit as st
import bcrypt
from streamlit_cookies_controller import CookieController

from lib.db import fetch_df, execute

ROLES = ["admin", "editor", "lector"]
SESSION_TTL_DAYS = 30
_COOKIE_NAME = "css_session"


def _cookies():
    # Se instancia en cada llamada a propósito: por dentro se apoya en
    # st.session_state, así que es barato, y evita cachear en un global de módulo
    # (que se compartiría entre usuarios distintos del mismo proceso del servidor).
    return CookieController()


def _get_user_by_email(email):
    df = fetch_df(
        "select id, email, name, password_hash, role, active from users where email = :email",
        {"email": email},
        ttl=0,
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def _create_session(user_id):
    """Crea un token de sesión persistente y lo devuelve (sin guardarlo aún en la cookie)."""
    token = secrets_lib.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    execute(
        "insert into sessions (token, user_id, expires_at) values (:token, :user_id, :expires_at)",
        {"token": token, "user_id": user_id, "expires_at": expires_at},
    )
    return token


def _get_session_user(token):
    df = fetch_df(
        """
        select u.id, u.email, u.name, u.role
        from sessions s
        join users u on u.id = s.user_id
        where s.token = :token and s.expires_at > now() and u.active
        """,
        {"token": token},
        ttl=0,
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def _delete_session(token):
    execute("delete from sessions where token = :token", {"token": token})


def restore_session():
    """Si el navegador trae la cookie de sesión y todavía no hay usuario en session_state
    (p. ej. justo después de un refresh o al navegar a otra página), restaura la sesión sin
    pedir credenciales de nuevo. A diferencia de un query param en la URL, la cookie sobrevive
    cualquier tipo de navegación entre páginas de la app."""
    if "user" in st.session_state:
        return
    token = _cookies().get(_COOKIE_NAME)
    if not token:
        return
    try:
        user = _get_session_user(token)
    except Exception:
        return
    if user:
        st.session_state.user = {
            "id": int(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        }
        st.session_state["_session_token"] = token


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
        token = _create_session(user["id"])
        st.session_state.user = {
            "id": int(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        }
        st.session_state["_session_token"] = token
        _cookies().set(
            _COOKIE_NAME,
            token,
            max_age=SESSION_TTL_DAYS * 86400,
            same_site="lax",
        )
        # Sin st.rerun() a propósito: el controlador de cookies vive en un iframe y necesita
        # un instante para que el mensaje de "set cookie" llegue al navegador. Un rerun
        # inmediato aquí interrumpe esa llamada antes de que se alcance a escribir la cookie
        # de verdad — la sesión "funciona" en esta pestaña (queda en session_state) pero
        # nunca sobrevive a un refresh, porque la cookie nunca se guardó. Dejamos que el
        # script actual siga su curso normal: como session_state.user ya quedó asignado,
        # el resto de app.py (más abajo) renderiza la navegación normalmente sin necesitar
        # un rerun aparte.
    else:
        st.error("Contraseña incorrecta.")


def current_user():
    return st.session_state.get("user")


def is_logged_in():
    return "user" in st.session_state


def logout():
    token = st.session_state.get("_session_token") or _cookies().get(_COOKIE_NAME)
    if token:
        _delete_session(token)
    st.session_state.pop("user", None)
    st.session_state.pop("_session_token", None)
    _cookies().remove(_COOKIE_NAME, same_site="lax")
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
