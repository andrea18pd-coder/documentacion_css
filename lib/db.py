"""Acceso a la base de datos Supabase (Postgres) vía st.connection."""

import streamlit as st
from sqlalchemy import text


def get_connection():
    """Conexión SQL cacheada por Streamlit (misma instancia entre reruns)."""
    return st.connection("supabase", type="sql")


def fetch_df(sql, params=None, ttl=30):
    """Ejecuta un SELECT y devuelve un DataFrame. ttl en segundos (0 = sin cache)."""
    conn = get_connection()
    return conn.query(sql, params=params or {}, ttl=ttl)


def execute(sql, params=None):
    """Ejecuta un INSERT/UPDATE/DELETE dentro de una transacción."""
    conn = get_connection()
    with conn.session as session:
        session.execute(text(sql), params or {})
        session.commit()


def execute_returning_id(sql, params=None):
    """Ejecuta un INSERT ... RETURNING id y devuelve ese id."""
    conn = get_connection()
    with conn.session as session:
        result = session.execute(text(sql), params or {})
        session.commit()
        row = result.fetchone()
        return row[0] if row else None
