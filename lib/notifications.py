"""Notificaciones por correo (Resend) cuando se publica un anuncio nuevo.

Opcional: si no hay una API key de Resend configurada, se omite en silencio (igual que
`lib/llm.py` con Gemini) — la publicación del anuncio nunca debe fallar por esto.
"""

import sys

import requests
import streamlit as st

RESEND_API_URL = "https://api.resend.com/emails"
_DEFAULT_FROM = "onboarding@resend.com"


def is_configured():
    return bool(st.secrets.get("resend", {}).get("api_key"))


def _send(api_key, from_email, to_email, subject, html_body):
    try:
        response = requests.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"from": from_email, "to": [to_email], "subject": subject, "html": html_body},
            timeout=10,
        )
        if response.status_code >= 300:
            print(f"[notifications] Resend respondió {response.status_code} para {to_email}: {response.text}", file=sys.stderr)
        return response.status_code < 300
    except Exception as exc:
        print(f"[notifications] error enviando a {to_email}: {exc}", file=sys.stderr)
        return False


def notify_new_announcement(title, priority_label, module_name, author_name):
    """Envía un correo a cada usuario activo avisando del anuncio nuevo. Devuelve cuántos
    correos se enviaron con éxito (0 si Resend no está configurado o falla por completo)."""
    resend_cfg = st.secrets.get("resend", {})
    api_key = resend_cfg.get("api_key")
    if not api_key:
        return 0
    from_email = resend_cfg.get("from_email", _DEFAULT_FROM)

    from lib.db import fetch_df  # import local para evitar ciclo de módulos

    users_df = fetch_df("select email, name from users where active = true", ttl=0)
    if users_df.empty:
        return 0

    subject = f"📢 Nuevo anuncio: {title}"
    detail_bits = [priority_label]
    if module_name:
        detail_bits.append(module_name)
    detail_line = " · ".join(detail_bits)

    sent = 0
    for _, row in users_df.iterrows():
        html_body = (
            f"<p>Hola {row['name']},</p>"
            f"<p>Se publicó un nuevo anuncio en la Documentación CSS de Q10:</p>"
            f"<p><strong>{title}</strong><br>{detail_line}</p>"
            f"<p>Publicado por {author_name}.</p>"
            f"<p>Ingresa a la app, sección <strong>Anuncios</strong>, para ver el detalle completo.</p>"
        )
        if _send(api_key, from_email, row["email"], subject, html_body):
            sent += 1
    return sent
