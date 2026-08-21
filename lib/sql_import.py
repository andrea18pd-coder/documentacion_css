"""Parseo de archivos .sql subidos en bloque, con muchos queries sueltos separados por
comentarios tipo '-------- Título --------', como los usa el equipo en sus scripts de trabajo
diario (ver QUERY.sql de ejemplo)."""

import re

_HEADER_RE = re.compile(r"^-{3,}\s*(.*?)\s*-*\s*$")


def parse_sql_sections(text, fallback_title):
    """Divide `text` en tuplas (título, sql) según líneas separadoras tipo '----- Título -----'.

    Si el archivo no tiene ninguna línea separadora, devuelve una sola sección con todo el
    contenido bajo `fallback_title` (normalmente el nombre del archivo sin extensión).
    """
    current_title = None
    current_lines = []
    sections = []

    def flush():
        body = "\n".join(current_lines).strip()
        if body:
            title = current_title.strip() if current_title and current_title.strip() else fallback_title
            sections.append((title, body))

    for line in text.splitlines():
        m = _HEADER_RE.match(line)
        if m:
            flush()
            current_title = m.group(1)
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    if not sections:
        body = text.strip()
        if body:
            sections.append((fallback_title, body))
    return sections
