from urllib.parse import parse_qs, urlencode, urlparse

from app.views import layout as layout_mod
from app.views.layout import escape_html, layout, format_value, display_name

ENTITY = "CategoryCode"
BASE = "/category-codes"
PROPERTIES = [
    {"name": "name", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": True},
    {"name": "description", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "codeValue", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": True},
    {"name": "url", "kind": "InlineScalar", "use": "URL", "cardinality": "one", "required": False},
    {"name": "inCodeSet", "kind": "Ref", "targets": ["CategoryCodeSet"], "cardinality": "one", "required": True},
]
EXTRA_COLS = ["url"]


def render(opts):
    api = opts["api"]
    user = opts.get("user")
    csrf = opts.get("csrf")
    url = opts.get("url") or BASE
    qs = urlparse(url).query
    parsed = parse_qs(qs)
    query = {k: parsed[k][0] for k in ("limit", "offset", "sort", "order") if k in parsed}
    r = api.list(ENTITY, query)
    if r["status"] != 200:
        msg = (r["body"] or {}).get("message", "unknown error") if isinstance(r["body"], dict) else "unknown error"
        return {
            "status": r["status"],
            "html": layout(
                title=ENTITY + "s",
                current_entity=ENTITY,
                user=user,
                csrf=csrf,
                body=f'<p role="alert">Failed to load: {escape_html(msg)}</p>',
            ),
        }
    headers = "".join(f'<th scope="col">{escape_html(h)}</th>' for h in ["Name", "Created"] + EXTRA_COLS + ["Actions"])
    prop_by_name = {p["name"]: p for p in PROPERTIES}
    rows = []
    for item in r["body"]["items"]:
        extras = "".join(
            f'<td>{format_value(item.get(c), prop_by_name[c]) if c in prop_by_name else escape_html(str(item.get(c, "")))}</td>'
            for c in EXTRA_COLS
        )
        rows.append(
            f'<tr>\n'
            f'<td><a href="{BASE}/{escape_html(item["id"])}">{escape_html(display_name(item, ENTITY))}</a></td>\n'
            f'<td><time datetime="{escape_html(item.get("dateCreated", ""))}">{escape_html(item.get("dateCreated", ""))}</time></td>\n'
            f'{extras}\n'
            f'<td><a href="{BASE}/{escape_html(item["id"])}/edit">Edit</a> · <a href="{BASE}/{escape_html(item["id"])}/delete">Delete</a></td>\n'
            f'</tr>'
        )
    if not rows:
        cols = 3 + len(EXTRA_COLS)
        body_rows = f'<tr><td colspan="{cols}"><em>No items.</em></td></tr>'
    else:
        body_rows = "".join(rows)
    limit = _page_int(parsed.get("limit", ["20"])[0], 20, minimum=1)
    offset = _page_int(parsed.get("offset", ["0"])[0], 0, minimum=0)

    def page_href(next_offset):
        params = {k: list(v) for k, v in parsed.items()}
        params["offset"] = [str(next_offset)]
        return f"{BASE}?{urlencode(params, doseq=True)}"

    prev_link = ""
    if offset > 0:
        prev_link = f'<a href="{escape_html(page_href(max(0, offset - limit)))}" rel="prev">Previous</a>'
    next_link = ""
    if offset + limit < r["body"]["total"]:
        next_link = f'<a href="{escape_html(page_href(offset + limit))}" rel="next">Next</a>'
    pagination = ""
    if prev_link or next_link:
        pagination = f'<nav aria-label="Pagination">{prev_link}{next_link}</nav>'
    return {
        "status": 200,
        "html": layout(
            title=ENTITY + "s",
            current_entity=ENTITY,
            user=user,
            csrf=csrf,
            body=(
                f'<p><a href="{BASE}/new">New {escape_html(ENTITY)}</a></p>\n'
                f'<p>Showing {len(r["body"]["items"])} of {r["body"]["total"]}.</p>\n'
                f'<table>\n'
                f'<caption>{escape_html(ENTITY)} list</caption>\n'
                f'<thead><tr>{headers}</tr></thead>\n'
                f'<tbody>{body_rows}</tbody>\n'
                f'</table>\n'
                f'{pagination}'
            ),
        ),
    }


def _page_int(raw, default, minimum):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else minimum
