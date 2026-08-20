"""Notificaciones dentro de la app cuando hay anuncios nuevos (sin correo).

Cada usuario tiene un `last_seen_announcements_at`: cualquier anuncio vigente publicado
después de esa marca cuenta como "nuevo" para él. Visitar la página Anuncios actualiza esa
marca a "ahora", así que deja de contar como nuevo la próxima vez.
"""

import streamlit as st


def get_unread_announcements(user_id):
    from lib.db import fetch_df  # import local para evitar ciclo de módulos

    df = fetch_df(
        """
        select pn.id, pn.title, pn.created_at
        from process_notes pn
        join users u on u.id = :user_id
        where pn.active
          and (u.last_seen_announcements_at is null or pn.created_at > u.last_seen_announcements_at)
        order by pn.created_at desc
        """,
        {"user_id": user_id},
        ttl=20,
    )
    return df.to_dict("records")


def mark_announcements_seen(user_id):
    from lib.db import execute  # import local para evitar ciclo de módulos

    execute("update users set last_seen_announcements_at = now() where id = :id", {"id": user_id})
    # get_unread_announcements() tiene un caché corto (ttl=20s): sin este aviso, el banner
    # de esta misma ejecución podría seguir mostrando el conteo de antes de marcar como visto.
    st.session_state["_skip_announcements_banner_once"] = True


def render_announcements_banner(user):
    """Aviso en la parte superior de cualquier página cuando hay anuncios nuevos sin ver."""
    if st.session_state.pop("_skip_announcements_banner_once", False):
        return
    unread = get_unread_announcements(user["id"])
    if not unread:
        return

    titles = "; ".join(f"«{a['title']}»" for a in unread[:3])
    extra = len(unread) - 3
    if extra > 0:
        titles += f" y {extra} más"

    with st.container(border=True):
        st.markdown(f"🔔 **{len(unread)} anuncio(s) nuevo(s):** {titles}")
        if st.button("Ver anuncios →", key="ann_banner_view"):
            st.switch_page("pages/0_Anuncios.py")
