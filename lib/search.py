"""Búsqueda global de texto libre sobre el contenido documentado."""

from lib.db import fetch_df

RESULT_LIMIT_PER_TABLE = 8
SIMILARITY_THRESHOLD = 0.35


def _match_score(columns):
    """Expresión SQL: mayor similitud (tolerante a tildes y errores de tipeo) contra `:raw`
    entre las columnas dadas. Un match textual exacto (ILIKE) siempre puntúa cerca de 1.0,
    así que ordenar por esta expresión deja los resultados exactos primero de forma natural.
    """
    parts = [
        f"word_similarity(lower(unaccent(:raw)), lower(unaccent(coalesce({c}, ''))))" for c in columns
    ]
    return f"greatest({', '.join(parts)})"


def search_all(query):
    """Busca `query` en Funcionalidades, Desarrollos, Dimensiones, APIs, Queries,
    Biblioteca de desarrollos y Personalizaciones.

    Combina coincidencia exacta por substring (ILIKE) con similitud por palabra
    (pg_trgm), para tolerar tildes, errores de tipeo y variaciones de la palabra.

    Devuelve una lista de dicts {type, id, label, subtitle} lista para mostrar.
    """
    q = f"%{query.strip()}%"
    raw = query.strip()
    base_params = {"q": q, "raw": raw, "thr": SIMILARITY_THRESHOLD, "limit": RESULT_LIMIT_PER_TABLE}
    results = []

    func_score = _match_score(["name", "description", "activation_notes", "request_type"])
    func_df = fetch_df(
        f"""
        select id, name
        from functionalities
        where name ilike :q or description ilike :q or activation_notes ilike :q or request_type ilike :q
           or {func_score} > :thr
        order by {func_score} desc
        limit :limit
        """,
        base_params,
        ttl=5,
    )
    for r in func_df.itertuples():
        results.append({"type": "functionality", "id": int(r.id), "label": r.name, "subtitle": "Funcionalidad"})

    cd_score = _match_score(["name", "client", "description", "notes"])
    cd_df = fetch_df(
        f"""
        select id, name, client
        from custom_developments
        where name ilike :q or client ilike :q or description ilike :q or notes ilike :q
           or {cd_score} > :thr
        order by {cd_score} desc
        limit :limit
        """,
        base_params,
        ttl=5,
    )
    for r in cd_df.itertuples():
        subtitle = "Desarrollo personalizado" + (f" · {r.client}" if r.client else "")
        results.append({"type": "custom_development", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    dim_score = _match_score(["name", "description", "example_values"])
    dim_df = fetch_df(
        f"""
        select id, name
        from dimensions
        where name ilike :q or description ilike :q or example_values ilike :q
           or {dim_score} > :thr
        order by {dim_score} desc
        limit :limit
        """,
        base_params,
        ttl=5,
    )
    for r in dim_df.itertuples():
        results.append({"type": "dimension", "id": int(r.id), "label": r.name, "subtitle": "Dimensión"})

    api_score = _match_score(["name", "endpoint", "description"])
    api_df = fetch_df(
        f"""
        select id, name, method
        from apis
        where name ilike :q or endpoint ilike :q or description ilike :q
           or {api_score} > :thr
        order by {api_score} desc
        limit :limit
        """,
        base_params,
        ttl=5,
    )
    for r in api_df.itertuples():
        subtitle = "API" + (f" · {r.method}" if r.method else "")
        results.append({"type": "api", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    query_score = _match_score(["name", "tags", "description", "sql_text"])
    query_df = fetch_df(
        f"""
        select id, name, tags
        from queries
        where name ilike :q or tags ilike :q or description ilike :q or sql_text ilike :q
           or {query_score} > :thr
        order by {query_score} desc
        limit :limit
        """,
        base_params,
        ttl=5,
    )
    for r in query_df.itertuples():
        subtitle = "Query" + (f" · {r.tags}" if r.tags else "")
        results.append({"type": "query", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    dev_article_score = _match_score(["name", "description_html"])
    dev_article_df = fetch_df(
        f"""
        select id, name, kind
        from custom_development_articles
        where name ilike :q or description_html ilike :q
           or {dev_article_score} > :thr
        order by {dev_article_score} desc
        limit :limit
        """,
        base_params,
        ttl=5,
    )
    for r in dev_article_df.itertuples():
        results.append({"type": "dev_article", "id": int(r.id), "label": r.name, "subtitle": r.kind})

    pers_score = _match_score(["name", "description", "institution"])
    pers_df = fetch_df(
        f"""
        select id, name, institution
        from personalizations
        where name ilike :q or description ilike :q or institution ilike :q
           or {pers_score} > :thr
        order by {pers_score} desc
        limit :limit
        """,
        base_params,
        ttl=5,
    )
    for r in pers_df.itertuples():
        subtitle = "Personalización" + (f" · {r.institution}" if r.institution else "")
        results.append({"type": "personalization", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    return results
