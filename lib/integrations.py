"""Integraciones salientes con servicios externos (Power Automate, Teams, etc.)."""

import requests
import streamlit as st


def _post_webhook(url, payload, service_label, timeout=10):
    """Hace el POST y avisa en pantalla si falla (por conexión o por código de error HTTP)."""
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException:
        st.warning(
            f"El anuncio se publicó, pero no se pudo notificar a {service_label} "
            "(revisa la URL del webhook en Secrets)."
        )


def notify_new_announcement_email(announcement):
    """Llama al flujo de Power Automate configurado para notificar el anuncio por correo.

    No hace nada si el webhook no está configurado en secrets.
    """
    webhook_url = st.secrets.get("power_automate", {}).get("anuncios_webhook_url")
    if not webhook_url:
        return
    _post_webhook(webhook_url, announcement, "Power Automate (correo)")


def notify_new_announcement_teams(announcement):
    """Publica el anuncio como tarjeta adaptable en el canal de Teams configurado.

    No hace nada si el webhook no está configurado en secrets.
    """
    webhook_url = st.secrets.get("teams", {}).get("anuncios_webhook_url")
    if not webhook_url:
        return
    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"{announcement['priority_label']} · {announcement['title']}",
                            "weight": "Bolder",
                            "size": "Medium",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": announcement["description"],
                            "wrap": True,
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Módulo", "value": announcement.get("module") or "—"},
                                {"title": "Autor", "value": announcement["author"]},
                                {"title": "Fecha", "value": announcement["created_at"]},
                            ],
                        },
                    ],
                },
            }
        ],
    }
    _post_webhook(webhook_url, card, "Teams")
