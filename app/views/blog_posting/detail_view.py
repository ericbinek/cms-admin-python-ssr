from app.views.layout import escape_html, layout, format_value, display_name, error_page

ENTITY = "BlogPosting"
BASE = "/blog-postings"
PROPERTIES = [
    {"name": "headline", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": True},
    {"name": "alternativeHeadline", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "description", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": False},
    {"name": "articleBody", "kind": "InlineScalar", "use": "Text", "cardinality": "one", "required": True},
    {"name": "author", "kind": "Ref", "targets": ["Person"], "cardinality": "one", "required": True},
    {"name": "image", "kind": "Ref", "targets": ["ImageObject"], "cardinality": "many", "required": False},
    {"name": "keywords", "kind": "Ref", "targets": ["DefinedTerm"], "cardinality": "many", "required": False},
    {"name": "about", "kind": "Ref", "targets": ["CategoryCode"], "cardinality": "many", "required": False},
    {"name": "datePublished", "kind": "InlineScalar", "use": "DateTime", "cardinality": "one", "required": False},
    {"name": "dateModified", "kind": "InlineScalar", "use": "DateTime", "cardinality": "one", "required": False},
    {"name": "dateCreated", "kind": "InlineScalar", "use": "DateTime", "cardinality": "one", "required": False},
    {"name": "url", "kind": "InlineScalar", "use": "URL", "cardinality": "one", "required": False},
    {"name": "inLanguage", "kind": "Embed", "use": "Language", "cardinality": "one", "required": False},
    {"name": "isAccessibleForFree", "kind": "InlineScalar", "use": "Boolean", "cardinality": "one", "required": False},
    {"name": "wordCount", "kind": "InlineScalar", "use": "Integer", "cardinality": "one", "required": False},
    {"name": "creativeWorkStatus", "kind": "Enum", "values": ["Draft", "Pending", "Published", "Archived"], "cardinality": "one", "required": False},
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
