from app.views import layout as layout_mod
from app.views.layout import escape_html, layout, render_field, parse_form_body, form_values_from_item, error_page, csrf_field

ENTITY = "SiteNavigationElement"
BASE = "/site-navigation-elements"
PROPERTIES = [
    {"name": "name", "kind": "InlineScalar", "use": "Text", "maxLength": 256, "cardinality": "one", "required": True},
    {"name": "url", "kind": "InlineScalar", "use": "URL", "maxLength": 2048, "cardinality": "one", "required": True},
    {"name": "description", "kind": "InlineScalar", "use": "Text", "maxLength": 5000, "multiline": True, "cardinality": "one", "required": False},
    {"name": "position", "kind": "InlineScalar", "use": "Integer", "cardinality": "one", "required": False},
    {"name": "isPartOf", "kind": "Ref", "targets": ["SiteNavigationElement"], "cardinality": "one", "required": False},
]


def _load_ref_options(api):
    out = {}
    for prop in PROPERTIES:
        if prop["kind"] != "Ref":
            continue
        collected = []
        for target in prop["targets"]:
            r = api.list(target, {"limit": 100})
            if r["status"] == 200 and isinstance(r["body"], dict):
                for item in r["body"].get("items", []):
                    collected.append({"value": item["id"], "label": f"{target}: {layout_mod.display_name(item, target)}"})
        out[prop["name"]] = collected
    return out


def _extract_error_list(body):
    if not body:
        return ["Request failed."]
    if isinstance(body, dict):
        details = body.get("details")
        if isinstance(details, list) and details:
            return details
        message = body.get("message")
        if isinstance(message, str):
            return [message]
    return ["Request failed."]


def render_form(opts):
    api = opts["api"]
    user = opts.get("user")
    csrf = opts.get("csrf")
    item_id = opts["id"]
    values = opts.get("values")
    errors = opts.get("errors") or []
    field_errors = opts.get("field_errors") or {}
    if values is None:
        r = api.get(ENTITY, item_id)
        if r["status"] == 404:
            return error_page(404, ENTITY + " not found.", user)
        if r["status"] != 200:
            msg = (r["body"] or {}).get("message", "Failed to load.") if isinstance(r["body"], dict) else "Failed to load."
            return error_page(r["status"], msg, user)
        values = form_values_from_item(r["body"], PROPERTIES)
    ref_options = _load_ref_options(api)
    fields = "\n".join(
        render_field(p, value=values.get(p["name"]), ref_options=ref_options, errors=field_errors.get(p["name"], []))
        for p in PROPERTIES
    )
    error_block = ""
    if errors:
        items = "".join(f"<li>{escape_html(e)}</li>" for e in errors)
        error_block = f'<div role="alert"><p>Could not save:</p><ul>{items}</ul></div>'
    body = (
        f'{error_block}\n'
        f'<form method="POST" action="{BASE}/{escape_html(item_id)}/edit">\n'
        f'{csrf_field(csrf)}\n'
        f'{fields}\n'
        f'<p><button type="submit">Save</button> · <a href="{BASE}/{escape_html(item_id)}">Cancel</a></p>\n'
        f'</form>'
    )
    return {
        "status": 400 if errors else 200,
        "html": layout(title="Edit " + ENTITY, current_entity=ENTITY, user=user, csrf=csrf, body=body),
    }


def handle_submit(opts):
    api = opts["api"]
    user = opts.get("user")
    item_id = opts["id"]
    payload = parse_form_body(opts.get("form") or "", PROPERTIES)
    r = api.update(ENTITY, item_id, payload)
    if r["status"] == 200:
        return {"status": 303, "redirect": BASE + "/" + item_id}
    if r["status"] == 404:
        return error_page(404, ENTITY + " not found.", user)
    return {"status": 400, "errors": _extract_error_list(r["body"]), "values": payload}
