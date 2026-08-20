"""Extrae y busca las funciones/parámetros/funcionalidades individuales dentro de las notas
de activación de cada funcionalidad. `activation_notes` trae un formato consistente, con
hasta tres secciones:

    Funciones:
      - 2161: Tipos de programas (TiposProgramas/InicioTipoPrograma)
      - 2162: Crear Tipos de Programas (TiposProgramas/Crear)
    Parámetros:
      - 638: Tipo de programa
    Funcionalidades:
      - 185
      - 9214: Nombre opcional

Cada tipo de código se pega en un query de activación distinto:
  - Funciones/Permisos  -> query "Asignar Permisos Roles" (placeholder %Funcion%, + %Rol%)
  - Parámetros          -> query "Actualizar parámetros institucionales" (placeholder %Código%)
  - Funcionalidades     -> query "Activar / InactivarFuncionalidades" (placeholder %funapl_codigoP%)

Esto permite responder una pregunta como "necesito habilitar X" con la receta completa y
lista para pegar en esos queries, en vez de solo señalar la funcionalidad que la contiene.
"""

import difflib
import re

from lib.db import fetch_df
from lib.search import FUZZY_MIN_KEYWORD_LEN, FUZZY_PREFIX_LEN, _extract_keywords, _strip_accents

_SECTION_RE = re.compile(r"^(funciones(?:\s*/\s*permisos)?|par[aá]metros|funcionalidades)\s*:?\s*$", re.IGNORECASE)
_ITEM_WITH_NAME_RE = re.compile(r"^-\s*(\d+)\s*:\s*(.+?)(?:\s*\(([^()]+)\))?\s*$")
_ITEM_CODE_ONLY_RE = re.compile(r"^-\s*(\d+)\s*(?::\s*(.+))?\s*$")

KIND_LABELS = {"funcion": "Función", "parametro": "Parámetro", "app_functionality": "Funcionalidad"}

# Nombres reales de los 3 queries de activación en el catálogo de Queries — se buscan por
# nombre (no por id) porque el id puede variar si la base se reimporta.
META_QUERY_NAMES = {
    "funcion": "Asignar Permisos Roles",
    "parametro": "Actualizar parámetros institucionales",
    "app_functionality": "Activar / InactivarFuncionalidades",
}


def _parse_activation_notes(text):
    """`activation_notes` -> lista de {kind, code, name, route}."""
    if not text:
        return []
    items = []
    kind = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SECTION_RE.match(line)
        if m:
            header = _strip_accents(m.group(1).lower())
            if header.startswith("funcionalidades"):
                kind = "app_functionality"
            elif header.startswith("funciones"):
                kind = "funcion"
            else:
                kind = "parametro"
            continue
        if kind is None:
            continue
        if kind == "app_functionality":
            # Esta sección casi siempre trae solo el código, sin nombre ni ruta.
            m = _ITEM_CODE_ONLY_RE.match(line)
            if m:
                code, name = m.groups()
                items.append({"kind": kind, "code": code, "name": (name or "").strip(), "route": None})
        else:
            m = _ITEM_WITH_NAME_RE.match(line)
            if m:
                code, name, route = m.groups()
                items.append({"kind": kind, "code": code, "name": name.strip(), "route": route})
    return items


def load_all_items(ttl=60):
    """Todas las funciones/parámetros/funcionalidades de todas las funcionalidades
    documentadas, con su funcionalidad padre. Deduplicadas por (funcionalidad, tipo, código,
    nombre) — dentro de UNA misma funcionalidad no debería repetirse un código, pero SÍ es
    normal y esperado que el mismo código aparezca en varias funcionalidades distintas (hay
    funcionalidades duplicadas/relacionadas que documentan los mismos permisos); no podemos
    deduplicar eso globalmente o build_recipe() perdería códigos reales de una funcionalidad
    solo porque otra funcionalidad los mencionó primero."""
    df = fetch_df(
        """
        select id, name, activation_notes
        from functionalities
        where activation_notes is not null and activation_notes <> ''
        """,
        ttl=ttl,
    )
    items = []
    seen = set()
    for _, row in df.iterrows():
        fid = int(row["id"])
        for it in _parse_activation_notes(row["activation_notes"]):
            dedupe_key = (fid, it["kind"], it["code"], it["name"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append({"functionality_id": fid, "functionality_name": row["name"], **it})
    return items


def load_meta_query_ids(ttl=300):
    """IDs reales de los 3 queries de activación (Asignar Permisos Roles, Actualizar
    parámetros institucionales, Activar / InactivarFuncionalidades), buscados por nombre."""
    names = list(META_QUERY_NAMES.values())
    df = fetch_df("select id, name from queries where name = any(:names)", {"names": names}, ttl=ttl)
    by_name = {row["name"]: int(row["id"]) for _, row in df.iterrows()}
    return {kind: by_name.get(name) for kind, name in META_QUERY_NAMES.items()}


def build_recipe(items, functionality_id):
    """Agrupa por tipo todos los códigos de UNA funcionalidad, para armar la receta completa
    de habilitación: qué pegar en cada uno de los 3 queries de activación."""
    by_kind = {"funcion": [], "parametro": [], "app_functionality": []}
    functionality_name = None
    for it in items:
        if it["functionality_id"] != functionality_id:
            continue
        functionality_name = it["functionality_name"]
        by_kind[it["kind"]].append(it["code"])
    if functionality_name is None:
        return None
    return {
        "functionality_id": functionality_id,
        "functionality_name": functionality_name,
        "funcion_codes": by_kind["funcion"],
        "parametro_codes": by_kind["parametro"],
        "app_functionality_codes": by_kind["app_functionality"],
    }


def _keyword_weights(keywords, items):
    """Qué tan distintiva es cada keyword dentro del catálogo (estilo TF-IDF): una palabra
    que aparece en pocas entradas (p. ej. "consolidado") pesa casi 1; una que aparece en
    muchas (p. ej. "cursos", "habilitar") pesa poco, para que no le gane a la palabra
    realmente relevante de la pregunta."""
    n = max(len(items), 1)
    weights = {}
    for kw in keywords:
        df = sum(1 for it in items if kw in _strip_accents(it["name"].lower()))
        weights[kw] = 1.0 - min(df / n, 0.9)
    return weights


def _score_entry(keywords, weights, target_name):
    """Similitud de `target_name` contra las keywords de la pregunta, ponderada por qué tan
    distintiva es cada keyword. Substring exacto puntúa alto de forma directa; si no,
    similitud por palabra con guarda de prefijo (evita falsos positivos por parecido de
    sufijo, p. ej. "dimensiones" vs "pensiones").

    Los aportes de cada keyword que sí matchea se combinan (OR probabilístico:
    1 - producto de (1 - aporte)) en vez de quedarse solo con el mejor — si no, un item que
    coincide con DOS palabras de la pregunta (p. ej. "importación" Y "créditos") puede perder
    por un margen mínimo contra otro que solo coincide con una palabra más "rara"
    (p. ej. "financieros"), cuando en realidad el primero es el match correcto."""
    target = _strip_accents(target_name.lower())
    target_tokens = target.split()
    combined = 0.0
    for kw in keywords:
        w = weights.get(kw, 0.5)
        component = 0.0
        if kw in target:
            component = 0.5 + 0.5 * w
        elif len(kw) >= FUZZY_MIN_KEYWORD_LEN:
            prefix = kw[:FUZZY_PREFIX_LEN]
            for tok in target_tokens:
                if len(tok) < FUZZY_MIN_KEYWORD_LEN or tok[:FUZZY_PREFIX_LEN] != prefix:
                    continue
                ratio = difflib.SequenceMatcher(None, kw, tok).ratio()
                component = max(component, ratio * (0.5 + 0.5 * w))
        if component > 0:
            combined = 1 - (1 - combined) * (1 - component)
    return combined


def best_matches(raw_query, items, limit=3, min_score=0.5):
    """Las funciones/parámetros/funcionalidades más relacionadas con la pregunta, mejor
    puntaje primero. Solo considera items con nombre (los códigos "Funcionalidades:" sin
    nombre no se pueden buscar por texto; se llega a ellos vía build_recipe una vez se
    identifica la funcionalidad padre)."""
    keywords = _extract_keywords(raw_query.strip())
    if not keywords:
        return []
    named_items = [it for it in items if it["name"]]
    weights = _keyword_weights(keywords, named_items)
    scored = [(_score_entry(keywords, weights, it["name"]), it) for it in named_items]
    scored = [(s, it) for s, it in scored if s >= min_score]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [it for _, it in scored[:limit]]
