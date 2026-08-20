"""Catálogo maestro real de Q10 (funciones, parámetros, funcionalidades de aplicación),
importado directo de exportaciones del sistema (tablas sys_functions / sys_parameters /
sys_app_functionalities). Es de solo lectura y mucho más completo que lo que se documenta a
mano en activation_notes — se usa como respaldo de búsqueda para el Asistente cuando algo
existe en el sistema real pero nadie lo ha documentado todavía en una funcionalidad."""

from lib.db import fetch_df


def load_all_items(ttl=600):
    """Todo el catálogo maestro, en el mismo formato que lib.activation_items
    (kind/code/name/route/functionality_id/functionality_name), para poder buscarse junto
    con los ítems documentados manualmente usando la misma lógica de puntaje."""
    items = []

    df = fetch_df(
        "select fun_codigo, fun_nombre, fun_controlador, fun_accion, fun_area from sys_functions",
        ttl=ttl,
    )
    for _, row in df.iterrows():
        if row["fun_controlador"] and row["fun_accion"]:
            route = f"{row['fun_controlador']}/{row['fun_accion']}"
        else:
            route = row["fun_controlador"] or None
        items.append({
            "kind": "funcion",
            "code": str(int(row["fun_codigo"])),
            "name": row["fun_nombre"] or "",
            "route": route,
            "functionality_id": None,
            "functionality_name": None,
        })

    df = fetch_df("select par_codigo, par_nombre from sys_parameters", ttl=ttl)
    for _, row in df.iterrows():
        items.append({
            "kind": "parametro",
            "code": str(int(row["par_codigo"])),
            "name": row["par_nombre"] or "",
            "route": None,
            "functionality_id": None,
            "functionality_name": None,
        })

    df = fetch_df(
        "select funapl_codigo, funapl_funcionalidad, funapl_seccion, funapl_categoria from sys_app_functionalities",
        ttl=ttl,
    )
    for _, row in df.iterrows():
        route = " / ".join(v for v in (row["funapl_seccion"], row["funapl_categoria"]) if v) or None
        items.append({
            "kind": "app_functionality",
            "code": str(int(row["funapl_codigo"])),
            "name": row["funapl_funcionalidad"] or "",
            "route": route,
            "functionality_id": None,
            "functionality_name": None,
        })

    return items
