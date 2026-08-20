"""Notificaciones por correo (SMTP) cuando se publica un anuncio nuevo.

Opcional: si no hay credenciales SMTP configuradas, se omite en silencio (igual que
`lib/llm.py` con Gemini) — la publicación del anuncio nunca debe fallar por esto.
Envía desde una casilla real (Outlook/Office 365, Gmail, etc.) con una "contraseña de
aplicación", sin necesidad de verificar un dominio propio.
"""

import smtplib
import ssl
import sys
from email.mime.text import MIMEText

import streamlit as st

_DEFAULT_HOST = "smtp.office365.com"
_DEFAULT_PORT = 587


def is_configured():
    cfg = st.secrets.get("smtp", {})
    return bool(cfg.get("email") and cfg.get("app_password"))


def notify_new_announcement(title, priority_label, module_name, author_name):
    """Envía un correo a cada usuario activo avisando del anuncio nuevo. Devuelve cuántos
    correos se enviaron con éxito (0 si SMTP no está configurado o falla por completo)."""
    cfg = st.secrets.get("smtp", {})
    email_addr = cfg.get("email")
    app_password = cfg.get("app_password")
    if not (email_addr and app_password):
        return 0

    from lib.db import fetch_df  # import local para evitar ciclo de módulos

    users_df = fetch_df("select email, name from users where active = true", ttl=0)
    if users_df.empty:
        return 0

    subject = f"📢 Nuevo anuncio: {title}"
    detail_bits = [priority_label]
    if module_name:
        detail_bits.append(module_name)
    detail_line = " · ".join(detail_bits)

    host = cfg.get("host", _DEFAULT_HOST)
    port = int(cfg.get("port", _DEFAULT_PORT))

    sent = 0
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(email_addr, app_password)
            for _, row in users_df.iterrows():
                html_body = (
                    f"<p>Hola {row['name']},</p>"
                    f"<p>Se publicó un nuevo anuncio en la Documentación CSS de Q10:</p>"
                    f"<p><strong>{title}</strong><br>{detail_line}</p>"
                    f"<p>Publicado por {author_name}.</p>"
                    f"<p>Ingresa a la app, sección <strong>Anuncios</strong>, para ver el detalle completo.</p>"
                )
                msg = MIMEText(html_body, "html", "utf-8")
                msg["Subject"] = subject
                msg["From"] = email_addr
                msg["To"] = row["email"]
                try:
                    server.sendmail(email_addr, [row["email"]], msg.as_string())
                    sent += 1
                except Exception as exc:
                    print(f"[notifications] error enviando a {row['email']}: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"[notifications] error de conexión SMTP: {exc}", file=sys.stderr)

    return sent
