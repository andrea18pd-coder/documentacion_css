"""Búsqueda global de texto libre sobre el contenido documentado."""

from lib.db import fetch_df

RESULT_LIMIT_PER_TABLE = 8


def search_all(query):
    """Busca `query` en Funcionalidades, Desarrollos, Dimensiones y APIs.

    Devuelve una lista de dicts {type, id, label, subtitle} lista para mostrar.
    """
    q = f"%{query.strip()}%"
    results = []

    func_df = fetch_df(
        """
        select id, name
        from functionalities
        where name ilike :q or description ilike :q or activation_notes ilike :q or request_type ilike :q
        order by name
        limit :limit
        """,
        {"q": q, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    for r in func_df.itertuples():
        results.append({"type": "functionality", "id": int(r.id), "label": r.name, "subtitle": "Funcionalidad"})

    cd_df = fetch_df(
        """
        select id, name, client
        from custom_developments
        where name ilike :q or client ilike :q or description ilike :q or notes ilike :q
        order by name
        limit :limit
        """,
        {"q": q, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    for r in cd_df.itertuples():
        subtitle = "Desarrollo personalizado" + (f" · {r.client}" if r.client else "")
        results.append({"type": "custom_development", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    dim_df = fetch_df(
        """
        select id, name
        from dimensions
        where name ilike :q or description ilike :q or example_values ilike :q
        order by name
        limit :limit
        """,
        {"q": q, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    for r in dim_df.itertuples():
        results.append({"type": "dimension", "id": int(r.id), "label": r.name, "subtitle": "Dimensión"})

    api_df = fetch_df(
        """
        select id, name, method
        from apis
        where name ilike :q or endpoint ilike :q or description ilike :q
        order by name
        limit :limit
        """,
        {"q": q, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    for r in api_df.itertuples():
        subtitle = "API" + (f" · {r.method}" if r.method else "")
        results.append({"type": "api", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    query_df = fetch_df(
        """
        select id, name, tags
        from queries
        where name ilike :q or tags ilike :q or description ilike :q or sql_text ilike :q
        order by name
        limit :limit
        """,
        {"q": q, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    for r in query_df.itertuples():
        subtitle = "Query" + (f" · {r.tags}" if r.tags else "")
        results.append({"type": "query", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    dev_article_df = fetch_df(
        """
        select id, name, kind
        from custom_development_articles
        where name ilike :q or description_html ilike :q
        order by name
        limit :limit
        """,
        {"q": q, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    for r in dev_article_df.itertuples():
        results.append({"type": "dev_article", "id": int(r.id), "label": r.name, "subtitle": r.kind})

    pers_df = fetch_df(
        """
        select id, name, institution
        from personalizations
        where name ilike :q or description ilike :q or institution ilike :q
        order by name
        limit :limit
        """,
        {"q": q, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    for r in pers_df.itertuples():
        subtitle = "Personalización" + (f" · {r.institution}" if r.institution else "")
        results.append({"type": "personalization", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    return results
