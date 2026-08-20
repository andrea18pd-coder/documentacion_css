"""Mapa de dependencias entre APIs: construcción de datos y render del grafo interactivo.

El grafo agrupa endpoints (tabla `apis`) en recursos (`api_resources`). Cada endpoint
pertenece a una categoría (`api_categories`, par top/sub con un color asociado) y puede
depender de otro recurso a través de un parámetro (`api_connections`), lo que arma la
red de dependencias que se visualiza con vis-network.
"""

import colorsys
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from lib.db import execute, execute_returning_id, fetch_df

_ASSETS = Path(__file__).resolve().parent.parent / "assets"

TOP_BASE_COLORS = {
    "Colegios": "#5FB878",
    "ETDH": "#E2685F",
    "Transversal": "#5B9BD5",
}


# --- Slugs y colores ---------------------------------------------------------

def slugify(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "recurso"


def _unique_slug(name, existing_slugs):
    base = slugify(name)
    slug = base
    i = 2
    while slug in existing_slugs:
        slug = f"{base}-{i}"
        i += 1
    return slug


def _hex_to_hsl(hex_color):
    hex_color = (hex_color or "#8A94A6").lstrip("#")
    if len(hex_color) != 6:
        hex_color = "8A94A6"
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, l


def _hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, min(max(l, 0), 1), min(max(s, 0), 1))
    return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))


def top_category_color(top_category):
    if top_category in TOP_BASE_COLORS:
        return TOP_BASE_COLORS[top_category]
    digest = hashlib.md5(top_category.encode("utf-8")).hexdigest()
    hue = (int(digest[:8], 16) % 360) / 360
    return _hsl_to_hex(hue, 0.55, 0.58)


def _generate_sub_color(base_hex, index):
    if index == 0:
        return base_hex
    h, s, l = _hex_to_hsl(base_hex)
    step = (index + 1) // 2
    h = h + 0.13 * index
    l = l + (0.09 if index % 2 == 0 else -0.09) * step
    return _hsl_to_hex(h, max(0.35, s), min(0.78, max(0.32, l)))


# --- Catálogos -----------------------------------------------------------------

def list_resources():
    return fetch_df("select id, slug, name, description from api_resources order by name", ttl=10)


def list_categories():
    return fetch_df(
        "select id, top_category, sub_category, color from api_categories order by top_category, sub_category",
        ttl=10,
    )


def list_top_categories():
    df = fetch_df("select distinct top_category from api_categories order by top_category", ttl=10)
    return list(df["top_category"]) if not df.empty else []


def list_ops(resource_id=None):
    where = "where a.resource_id = :rid" if resource_id else ""
    return fetch_df(
        f"""
        select a.id, a.name, a.method, a.endpoint, a.description, a.resource_id,
               a.requires_list_of_id, r.name as resource_name
        from apis a
        join api_resources r on r.id = a.resource_id
        {where}
        order by r.name, a.name
        """,
        {"rid": resource_id} if resource_id else {},
        ttl=10,
    )


def get_or_create_category(top_category, sub_category):
    top_category = (top_category or "").strip() or "Sin categoría"
    sub_category = (sub_category or "").strip() or "General"
    df = fetch_df(
        "select id, color from api_categories where lower(top_category) = lower(:t) and lower(sub_category) = lower(:s)",
        {"t": top_category, "s": sub_category},
        ttl=0,
    )
    if not df.empty:
        return int(df.iloc[0]["id"]), df.iloc[0]["color"]

    count_df = fetch_df(
        "select count(*) as n from api_categories where lower(top_category) = lower(:t)", {"t": top_category}, ttl=0
    )
    index = int(count_df.iloc[0]["n"])
    color = _generate_sub_color(top_category_color(top_category), index)
    new_id = execute_returning_id(
        "insert into api_categories (top_category, sub_category, color) values (:t, :s, :c) returning id",
        {"t": top_category, "s": sub_category, "c": color},
    )
    return new_id, color


def get_or_create_resource(name, description=None, uid=None):
    name = (name or "").strip()
    if not name:
        return None
    df = fetch_df("select id from api_resources where lower(name) = lower(:n)", {"n": name}, ttl=0)
    if not df.empty:
        return int(df.iloc[0]["id"])
    existing_slugs = set(fetch_df("select slug from api_resources", ttl=0)["slug"])
    slug = _unique_slug(name, existing_slugs)
    return execute_returning_id(
        "insert into api_resources (slug, name, description, created_by, updated_by) "
        "values (:slug, :name, :description, :uid, :uid) returning id",
        {"slug": slug, "name": name, "description": (description or "").strip() or None, "uid": uid},
    )


# --- Construcción del grafo -----------------------------------------------------

def build_graph_data():
    resources_df = fetch_df("select id, slug, name from api_resources order by name", ttl=5)
    ops_df = fetch_df(
        """
        select a.id, a.name, a.method, a.endpoint, a.description, a.resource_id,
               a.requires_list_of_id, a.category_id,
               c.top_category, c.sub_category, c.color
        from apis a
        left join api_categories c on c.id = a.category_id
        where a.resource_id is not null
        order by a.id
        """,
        ttl=5,
    )
    conns_df = fetch_df(
        """
        select ac.id, ac.api_id, ac.target_resource_id, ac.param_name, ac.relationship_description,
               a.name as source_name, a.resource_id as source_resource_id,
               c.top_category, c.sub_category, c.color
        from api_connections ac
        join apis a on a.id = ac.api_id
        left join api_categories c on c.id = a.category_id
        where ac.target_resource_id is not null
        order by ac.id
        """,
        ttl=5,
    )

    ops_by_id = {int(r.id): r for r in ops_df.itertuples()}
    slug_by_resource_id = {int(r.id): r.slug for r in resources_df.itertuples()}

    ops_by_resource = {}
    for r in ops_df.itertuples():
        ops_by_resource.setdefault(int(r.resource_id), []).append(r)

    nodes = []
    legend_counter = {}
    top_categories_seen = set()

    for res in resources_df.itertuples():
        rid = int(res.id)
        ops_rows = ops_by_resource.get(rid, [])
        pair_counts = {}
        ops_list = []

        for op in ops_rows:
            top = op.top_category if pd.notna(op.top_category) else "Sin categoría"
            sub = op.sub_category if pd.notna(op.sub_category) else "Sin categoría"
            key = f"{top} | {sub}"
            pair_counts[key] = pair_counts.get(key, 0) + 1
            legend_counter[(top, sub)] = legend_counter.get((top, sub), 0) + 1
            top_categories_seen.add(top)

            requires_name = None
            if pd.notna(op.requires_list_of_id):
                req_op = ops_by_id.get(int(op.requires_list_of_id))
                if req_op is not None:
                    requires_name = req_op.name

            ops_list.append(
                {
                    "id": int(op.id),
                    "method": op.method if pd.notna(op.method) else "GET",
                    "name": op.name,
                    "desc": op.description if pd.notna(op.description) else "",
                    "url": op.endpoint if pd.notna(op.endpoint) else "",
                    "top": top,
                    "sub": sub,
                    "requires_list_of_same_resource": requires_name,
                }
            )

        if pair_counts:
            dominant_key = max(pair_counts, key=pair_counts.get)
            dom_top, dom_sub = dominant_key.split(" | ", 1)
            dom_color = next(
                (
                    op.color
                    for op in ops_rows
                    if (op.top_category if pd.notna(op.top_category) else "Sin categoría") == dom_top
                    and (op.sub_category if pd.notna(op.sub_category) else "Sin categoría") == dom_sub
                    and pd.notna(op.color)
                ),
                "#8A94A6",
            )
        else:
            dom_top, dom_sub, dom_color = "Sin categoría", "Sin categoría", "#8A94A6"

        nodes.append(
            {
                "id": res.slug,
                "resource_id": rid,
                "label": res.name,
                "top": dom_top,
                "sub": dom_sub,
                "color": dom_color,
                "size": 12 + 1.6 * len(ops_list),
                "pair_counts": pair_counts,
                "ops": ops_list,
            }
        )

    edges = []
    for c in conns_df.itertuples():
        source_rid = c.source_resource_id
        if pd.isna(source_rid) or int(source_rid) not in slug_by_resource_id:
            continue
        target_rid = int(c.target_resource_id)
        if target_rid not in slug_by_resource_id:
            continue
        edges.append(
            {
                "from": slug_by_resource_id[int(source_rid)],
                "to": slug_by_resource_id[target_rid],
                "label": c.param_name if pd.notna(c.param_name) else "",
                "color": c.color if pd.notna(c.color) else "#8A94A6",
                "op_top": c.top_category if pd.notna(c.top_category) else "Sin categoría",
                "op_sub": c.sub_category if pd.notna(c.sub_category) else "Sin categoría",
                "op_name": c.source_name,
            }
        )

    top_colors = {top: top_category_color(top) for top in top_categories_seen}

    cats_df = fetch_df(
        "select top_category, sub_category, color from api_categories order by top_category, sub_category", ttl=5
    )
    color_by_pair = {(r.top_category, r.sub_category): r.color for r in cats_df.itertuples()}

    legend_tree = {}
    for (top, sub), count in legend_counter.items():
        legend_tree.setdefault(top, []).append(
            {"sub": sub, "count": count, "color": color_by_pair.get((top, sub), "#8A94A6")}
        )
    for top in legend_tree:
        legend_tree[top].sort(key=lambda x: -x["count"])

    return {"nodes": nodes, "edges": edges, "top_colors": top_colors, "legend_tree": legend_tree}


# --- Render HTML -----------------------------------------------------------------

_BODY_TEMPLATE = """
<div id="app">
  <header>
    <h1>Mapa de dependencias &mdash; API Q10 <span id="counts"></span></h1>
    <div style="display:flex; gap:10px; align-items:center;">
      <div class="search-box">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8b98a9" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input id="search" placeholder="Buscar recurso u operación..." />
      </div>
      <button class="reset-btn" id="resetBtn">Restablecer vista</button>
    </div>
  </header>

  <div id="graph">
    <div id="network"></div>
    <div id="tooltip"></div>
  </div>

  <div id="sidebar">
    <div class="legend">
      <h2>Categorías</h2>
      <div id="legendList"></div>
    </div>
    <div class="filters">
      <h2>Cómo usar</h2>
      <div class="hint">
        Cada nodo es un <b>recurso</b> de la API, agrupado por modelo y categoría en la leyenda de abajo.
        Haz clic en el encabezado de un modelo para ocultar/mostrar todas sus categorías, o en una categoría individual.
        Haz doble clic en un nodo para centrarlo.
        <br><br>
        El marcador <b style="color:#e8c065">&#9888;</b> dentro de una tarjeta de operación indica que ese endpoint
        necesita un <b style="color:#e6edf3">id</b> que solo se obtiene llamando primero a la operación que
        aparece señalada, del mismo recurso.
      </div>
    </div>
    <div class="detail" id="detail">
      <div class="empty-state">
        Selecciona un nodo del mapa para ver sus operaciones y de qué otros recursos depende (o quién depende de él).
      </div>
    </div>
  </div>
</div>
"""


def render_graph_html(graph_data):
    css = (_ASSETS / "api_graph.css").read_text(encoding="utf-8")
    vis_js = (_ASSETS / "vis-network.min.js").read_text(encoding="utf-8")
    app_js = (_ASSETS / "api_graph.js").read_text(encoding="utf-8")
    data_json = json.dumps(graph_data, ensure_ascii=False).replace("</", "<\\/")

    parts = [
        "<style>",
        css,
        "</style>",
        _BODY_TEMPLATE,
        "<script>",
        vis_js,
        "</script>",
        "<script>",
        "const GRAPH_DATA = ",
        data_json,
        ";\n",
        app_js,
        "</script>",
    ]
    return "".join(parts)
