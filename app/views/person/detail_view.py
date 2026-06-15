from app.views.layout import escape_html, layout, format_value, display_name, error_page

ENTITY = "Person"
BASE = "/persons"
PROPERTIES = [
    {"name": "name", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": True},
    {"name": "givenName", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "familyName", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "alternateName", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "email", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "url", "kind": "InlineScalar", "use": "URL", "cardinality": "one", "required": False},
    {"name": "description", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "image", "kind": "Ref", "targets": ["ImageObject"], "cardinality": "one", "required": False},
    {"name": "jobTitle", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "sameAs", "kind": "InlineScalar", "use": "URL", "cardinality": "many", "required": False},
]


def render(opts):
    api = opts["api"]
    user = opts.get("user")
    csrf = opts.get("csrf")
    item_id = opts["id"]
    r = api.get(ENTITY, item_id)
    if r["status"] == 404:
        return error_page(404, ENTITY + " not found.", user)
    if r["status"] != 200:
        msg = (r["body"] or {}).get("message", "Failed to load.") if isinstance(r["body"], dict) else "Failed to load."
        return error_page(r["status"], msg, user)
    item = r["body"]
    rows = "".join(
        f'<dt>{escape_html(p["name"])}</dt><dd>{format_value(item.get(p["name"]), p)}</dd>'
        for p in PROPERTIES
    )
    meta = (
        f'<dt>id</dt><dd><code>{escape_html(item["id"])}</code></dd>'
        f'<dt>dateCreated</dt><dd><time datetime="{escape_html(item.get("dateCreated", ""))}">{escape_html(item.get("dateCreated", ""))}</time></dd>'
        f'<dt>dateModified</dt><dd><time datetime="{escape_html(item.get("dateModified", ""))}">{escape_html(item.get("dateModified", ""))}</time></dd>'
    )
    body = (
        f'<article>\n'
        f'<dl>{rows}{meta}</dl>\n'
        f'<p>\n'
        f'<a href="{BASE}/{escape_html(item["id"])}/edit">Edit</a> ·\n'
        f'<a href="{BASE}/{escape_html(item["id"])}/delete">Delete</a> ·\n'
        f'<a href="{BASE}">Back to list</a>\n'
        f'</p>\n'
        f'</article>'
    )
    return {"status": 200, "html": layout(title=display_name(item, ENTITY), current_entity=ENTITY, user=user, csrf=csrf, body=body)}
