"""Búsqueda global de texto libre sobre el contenido documentado."""

import re
import unicodedata

import pandas as pd

from lib.db import fetch_df

RESULT_LIMIT_PER_TABLE = 8
FUZZY_CANDIDATE_LIMIT = 15
FUZZY_LOOSE_THRESHOLD = 0.3
FUZZY_PREFIX_LEN = 3
MAX_KEYWORDS = 20
MIN_KEYWORD_LEN = 3
FUZZY_MIN_KEYWORD_LEN = 5

_STOPWORDS = {
    "que", "qué", "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "o", "a", "en",
    "con", "por", "para", "del", "al", "es", "son", "debe", "deben", "tener", "tengo", "necesito",
    "necesita", "quiero", "quisiera", "como", "cómo", "este", "esta", "estos", "estas", "ese", "esa",
    "esos", "esas", "eso", "esto", "se", "su", "sus", "lo", "le", "les", "sin", "sobre", "entre",
    "hay", "ya", "mas", "más", "muy", "mi", "tu", "si", "sí", "no", "será", "sería", "hace", "hacer",
    "puedo", "podría", "cual", "cuál", "cuales", "cuáles", "donde", "dónde", "cuando", "cuándo",
    "porque", "porqué", "pero", "desde", "hasta", "hacia", "cada", "algo", "todo", "toda", "todos",
    "todas", "aqui", "aquí", "ahi", "ahí", "alli", "allí",
    # Verbos de intención típicos de una pregunta de soporte ("necesito HABILITAR X",
    # "cómo ACTIVO X"): describen la acción de pedir, no el objeto que se busca, así que no
    # deben competir como palabra clave contra el término realmente distintivo de la pregunta.
    "habilitar", "habilito", "habilita", "activar", "activo", "activa", "configurar", "configuro",
    "configura", "requiere", "requiero", "requerimos",
}


def _strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _extract_keywords(raw):
    """Palabras significativas de la pregunta (sin tildes, sin stopwords, mín. 3 letras),
    priorizando las más largas/distintivas y acotadas a MAX_KEYWORDS. Se usan para la
    búsqueda exacta (ILIKE, palabra por palabra) y, filtradas a las más largas, también
    para la búsqueda por similitud."""
    words = re.findall(r"\w+", _strip_accents(raw.lower()))
    seen = []
    for w in words:
        if len(w) >= MIN_KEYWORD_LEN and w not in _STOPWORDS and w not in seen:
            seen.append(w)
    seen.sort(key=len, reverse=True)
    return seen[:MAX_KEYWORDS]


def _prefix_ok(keyword, text):
    """True si algún token de `text` comparte prefijo con `keyword`. Filtro de precisión:
    sin esto, dos palabras que solo coinciden en el sufijo (p. ej. "dimensiones" vs
    "pensiones") pasarían el umbral de similitud como si fueran la misma palabra escrita
    distinto."""
    prefix = keyword[:FUZZY_PREFIX_LEN]
    tokens = re.findall(r"\w+", _strip_accents(text.lower()))
    return any(len(t) >= FUZZY_MIN_KEYWORD_LEN and t[:FUZZY_PREFIX_LEN] == prefix for t in tokens)


def _ilike_params_and_clause(name_cols, body_cols, raw_query, keywords, q_param="q"):
    """Devuelve (params, clause, order_expr) para un OR-clause: `name_cols` (campos cortos,
    tipo nombre) se compara contra la pregunta completa y contra cada keyword por separado
    (una frase larga rara vez aparece literal en un campo, pero sus palabras sueltas sí, p.
    ej. "logo" en "Logo principal"); `body_cols` (texto largo/HTML) solo contra la pregunta
    completa, para no generar coincidencias masivas por una sola palabra común dentro de un
    bloque enorme de texto.

    `order_expr` cuenta cuántas keywords distintas aparecen en `name_cols`: con preguntas
    largas (tipo ticket) hay muchas keywords y por lo tanto muchas filas que matchean al
    menos una — ordenar alfabéticamente en ese caso es ruido puro, así que priorizamos las
    filas que matchean MÁS keywords (más específicas) antes que por nombre.

    Las keywords vienen sin tildes (para la comparación difusa), pero el contenido de la
    base sí las tiene — por eso todo el ILIKE compara con `unaccent()` en ambos lados, si no
    "practicas" nunca haría match literal con "prácticas"."""
    params = {q_param: f"%{raw_query}%"}
    parts = [f"unaccent({c}) ilike unaccent(:{q_param})" for c in name_cols + body_cols]
    order_terms = []
    for i, kw in enumerate(keywords):
        p = f"{q_param}_kw{i}"
        params[p] = f"%{kw}%"
        parts += [f"unaccent({c}) ilike unaccent(:{p})" for c in name_cols]
        name_hit = " or ".join(f"unaccent({c}) ilike unaccent(:{p})" for c in name_cols)
        order_terms.append(f"(case when {name_hit} then 1 else 0 end)")
    order_expr = f"({' + '.join(order_terms)})" if order_terms else "0"
    return params, " or ".join(parts), order_expr


def _fuzzy_match_ids(table, columns, keywords):
    """IDs de `table` cuyo mejor match por palabra (word_similarity, tolera tildes y errores
    de tipeo) supera el umbral laxo Y comparte prefijo con alguna keyword de la pregunta.
    Solo usa keywords de al menos FUZZY_MIN_KEYWORD_LEN letras: las palabras cortas generan
    demasiadas coincidencias de trigramas por azar (p. ej. "logo" vs "logro"/"login")."""
    fuzzy_keywords = [k for k in keywords if len(k) >= FUZZY_MIN_KEYWORD_LEN]
    if not fuzzy_keywords:
        return set()

    kw_params = {f"kw{i}": kw for i, kw in enumerate(fuzzy_keywords)}
    score_parts = [
        f"word_similarity(lower(unaccent(:kw{i})), lower(unaccent(coalesce({c}, ''))))"
        for i in range(len(fuzzy_keywords))
        for c in columns
    ]
    score = f"greatest({', '.join(score_parts)})"
    text_expr = " || ' ' || ".join(f"coalesce({c}, '')" for c in columns)

    df = fetch_df(
        f"""
        select id, ({text_expr}) as _match_text
        from {table}
        where {score} > :loose_thr
        order by {score} desc
        limit :cand_limit
        """,
        {**kw_params, "loose_thr": FUZZY_LOOSE_THRESHOLD, "cand_limit": FUZZY_CANDIDATE_LIMIT},
        ttl=5,
    )
    return {
        int(row["id"])
        for _, row in df.iterrows()
        if any(_prefix_ok(kw, row["_match_text"]) for kw in fuzzy_keywords)
    }


def _with_fuzzy_extras(table, select_cols, exact_df, fuzzy_ids, limit):
    """Completa `exact_df` (resultados ILIKE) con las filas encontradas solo por similitud,
    hasta `limit` filas en total, sin duplicar ids."""
    exact_ids = set(exact_df["id"].astype(int)) if not exact_df.empty else set()
    missing_ids = [i for i in fuzzy_ids if i not in exact_ids]
    if not missing_ids:
        return exact_df.head(limit)
    extra_df = fetch_df(
        f"select {select_cols} from {table} where id = any(:ids)",
        {"ids": missing_ids},
        ttl=5,
    )
    return pd.concat([exact_df, extra_df], ignore_index=True).head(limit)


def search_all(query):
    """Busca `query` en Funcionalidades, Desarrollos, Dimensiones, APIs, Queries,
    Biblioteca de desarrollos y Personalizaciones.

    Combina coincidencia exacta por substring (ILIKE, sobre la pregunta completa y sobre
    cada palabra clave por separado) con similitud por palabra (pg_trgm, tolera tildes y
    errores de tipeo), restringida a los campos de nombre/etiqueta y con un filtro de
    prefijo para evitar coincidencias falsas por parecido de sufijo entre palabras
    distintas (p. ej. "dimensiones" / "pensiones").

    Devuelve una lista de dicts {type, id, label, subtitle} lista para mostrar.
    """
    raw = query.strip()
    keywords = _extract_keywords(raw)

    results = []

    params, clause, order_expr = _ilike_params_and_clause(
        ["name", "request_type"], ["description", "activation_notes"], raw, keywords
    )
    func_df = fetch_df(
        f"select id, name from functionalities where {clause} order by {order_expr} desc, name limit :limit",
        {**params, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    fuzzy_ids = _fuzzy_match_ids("functionalities", ["name"], keywords)
    combined = _with_fuzzy_extras("functionalities", "id, name", func_df, fuzzy_ids, RESULT_LIMIT_PER_TABLE)
    for r in combined.itertuples():
        results.append({"type": "functionality", "id": int(r.id), "label": r.name, "subtitle": "Funcionalidad"})

    params, clause, order_expr = _ilike_params_and_clause(["name", "client"], ["description", "notes"], raw, keywords)
    cd_df = fetch_df(
        f"select id, name, client from custom_developments where {clause} order by {order_expr} desc, name limit :limit",
        {**params, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    fuzzy_ids = _fuzzy_match_ids("custom_developments", ["name", "client"], keywords)
    combined = _with_fuzzy_extras("custom_developments", "id, name, client", cd_df, fuzzy_ids, RESULT_LIMIT_PER_TABLE)
    for r in combined.itertuples():
        subtitle = "Desarrollo personalizado" + (f" · {r.client}" if r.client else "")
        results.append({"type": "custom_development", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    params, clause, order_expr = _ilike_params_and_clause(["name"], ["description", "example_values"], raw, keywords)
    dim_df = fetch_df(
        f"select id, name from dimensions where {clause} order by {order_expr} desc, name limit :limit",
        {**params, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    fuzzy_ids = _fuzzy_match_ids("dimensions", ["name"], keywords)
    combined = _with_fuzzy_extras("dimensions", "id, name", dim_df, fuzzy_ids, RESULT_LIMIT_PER_TABLE)
    for r in combined.itertuples():
        results.append({"type": "dimension", "id": int(r.id), "label": r.name, "subtitle": "Dimensión"})

    params, clause, order_expr = _ilike_params_and_clause(["name", "endpoint"], ["description"], raw, keywords)
    api_df = fetch_df(
        f"select id, name, method from apis where {clause} order by {order_expr} desc, name limit :limit",
        {**params, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    fuzzy_ids = _fuzzy_match_ids("apis", ["name", "endpoint"], keywords)
    combined = _with_fuzzy_extras("apis", "id, name, method", api_df, fuzzy_ids, RESULT_LIMIT_PER_TABLE)
    for r in combined.itertuples():
        subtitle = "API" + (f" · {r.method}" if r.method else "")
        results.append({"type": "api", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    params, clause, order_expr = _ilike_params_and_clause(["name", "tags"], ["description", "sql_text"], raw, keywords)
    query_df = fetch_df(
        f"select id, name, tags from queries where {clause} order by {order_expr} desc, name limit :limit",
        {**params, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    fuzzy_ids = _fuzzy_match_ids("queries", ["name", "tags"], keywords)
    combined = _with_fuzzy_extras("queries", "id, name, tags", query_df, fuzzy_ids, RESULT_LIMIT_PER_TABLE)
    for r in combined.itertuples():
        subtitle = "Query" + (f" · {r.tags}" if r.tags else "")
        results.append({"type": "query", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    params, clause, order_expr = _ilike_params_and_clause(["name"], ["description_html"], raw, keywords)
    dev_article_df = fetch_df(
        f"select id, name, kind from custom_development_articles where {clause} order by {order_expr} desc, name limit :limit",
        {**params, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    fuzzy_ids = _fuzzy_match_ids("custom_development_articles", ["name"], keywords)
    combined = _with_fuzzy_extras(
        "custom_development_articles", "id, name, kind", dev_article_df, fuzzy_ids, RESULT_LIMIT_PER_TABLE
    )
    for r in combined.itertuples():
        results.append({"type": "dev_article", "id": int(r.id), "label": r.name, "subtitle": r.kind})

    params, clause, order_expr = _ilike_params_and_clause(["name", "institution"], ["description"], raw, keywords)
    pers_df = fetch_df(
        f"select id, name, institution from personalizations where {clause} order by {order_expr} desc, name limit :limit",
        {**params, "limit": RESULT_LIMIT_PER_TABLE},
        ttl=5,
    )
    fuzzy_ids = _fuzzy_match_ids("personalizations", ["name", "institution"], keywords)
    combined = _with_fuzzy_extras(
        "personalizations", "id, name, institution", pers_df, fuzzy_ids, RESULT_LIMIT_PER_TABLE
    )
    for r in combined.itertuples():
        subtitle = "Personalización" + (f" · {r.institution}" if r.institution else "")
        results.append({"type": "personalization", "id": int(r.id), "label": r.name, "subtitle": subtitle})

    return results


_DETAIL_QUERIES = {
    "functionality": "select name, description, activation_notes, request_type from functionalities where id = :id",
    "custom_development": "select name, client, description, status, notes from custom_developments where id = :id",
    "dimension": "select name, description, data_type, example_values from dimensions where id = :id",
    "api": "select name, method, endpoint, description, auth_type from apis where id = :id",
    "query": "select name, description, tags, sql_text from queries where id = :id",
    "dev_article": "select name, kind, description_html from custom_development_articles where id = :id",
    "personalization": "select name, institution, description from personalizations where id = :id",
}


def _strip_html(raw):
    """Texto plano aproximado de un campo HTML (description_html), para no mandarle al LLM
    etiquetas y entidades que solo consumen tokens sin aportar información."""
    if not raw:
        return raw
    import html as html_module

    text = re.sub(r"<[^>]+>", " ", raw)
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_result_detail(result_type, result_id):
    """Contenido completo (no solo label/subtitle) de un resultado de search_all() — para
    darle al Asistente el SQL real de un query, el endpoint de una API, etc., en vez de solo
    el nombre, así puede responder con contenido concreto y no solo señalar que algo existe."""
    sql = _DETAIL_QUERIES.get(result_type)
    if not sql:
        return None
    df = fetch_df(sql, {"id": result_id}, ttl=15)
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    if result_type == "dev_article" and row.get("description_html"):
        row["description_html"] = _strip_html(row["description_html"])
    return row
