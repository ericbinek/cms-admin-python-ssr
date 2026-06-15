from app.views.layout import escape_html, layout, display_name, error_page, csrf_field

ENTITY = "WebPage"
BASE = "/web-pages"


def render_form(opts):
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
    body = (
        f'<form method="POST" action="{BASE}/{escape_html(item_id)}/delete">\n'
        f'{csrf_field(csrf)}\n'
        f'<p>Delete <strong>{escape_html(display_name(r["body"], ENTITY))}</strong>? This cannot be undone.</p>\n'
        f'<p><button type="submit">Confirm Delete</button> · <a href="{BASE}/{escape_html(item_id)}">Cancel</a></p>\n'
        f'</form>'
    )
    return {"status": 200, "html": layout(title="Delete " + ENTITY, current_entity=ENTITY, user=user, csrf=csrf, body=body)}


def handle_submit(opts):
    api = opts["api"]
    user = opts.get("user")
    r = api.remove(ENTITY, opts["id"])
    if r["status"] in (204, 404):
        return {"status": 303, "redirect": BASE}
    return error_page(r["status"], "Delete failed.", user)
