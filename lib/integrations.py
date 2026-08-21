"""Integraciones salientes con servicios externos (Power Automate, etc.)."""

import requests
import streamlit as st


def notify_new_announcement(announcement):
    """Notifica a Power Automate que se publicó un anuncio nuevo (dispara correo/Teams desde el flujo).

    No hace nada si el webhook no está configurado en secrets, y si la llamada falla solo
    muestra una advertencia: el anuncio ya quedó publicado en la base de datos de todas formas.
    """
    webhook_url = st.secrets.get("power_automate", {}).get("anuncios_webhook_url")
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json=announcement, timeout=5)
    except requests.RequestException:
        st.warning(
            "El anuncio se publicó, pero no se pudo notificar a Power Automate "
            "(revisa la URL del webhook en Secrets)."
        )
