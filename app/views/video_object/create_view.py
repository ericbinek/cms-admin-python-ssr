from app.views import layout as layout_mod
from app.views.layout import escape_html, layout, render_field, parse_form_body, csrf_field

ENTITY = "VideoObject"
BASE = "/video-objects"
PROPERTIES = [
    {"name": "name", "kind": "InlineScalar", "use": "Text", "maxLength": 256, "cardinality": "one", "required": False},
    {"name": "description", "kind": "InlineScalar", "use": "Text", "maxLength": 5000, "multiline": True, "cardinality": "one", "required": False},
    {"name": "contentUrl", "kind": "InlineScalar", "use": "URL", "maxLength": 2048, "cardinality": "one", "required": True},
    {"name": "embedUrl", "kind": "InlineScalar", "use": "URL", "maxLength": 2048, "cardinality": "one", "required": False},
    {"name": "encodingFormat", "kind": "InlineScalar", "use": "Text", "maxLength": 128, "cardinality": "one", "required": False},
    {"name": "duration", "kind": "InlineScalar", "use": "Duration", "cardinality": "one", "required": False},
    {"name": "videoQuality", "kind": "InlineScalar", "use": "Text", "maxLength": 128, "cardinality": "one", "required": False},
    {"name": "transcript", "kind": "InlineScalar", "use": "Text", "maxLength": 65536, "multiline": True, "cardinality": "one", "required": False},
    {"name": "caption", "kind": "InlineScalar", "use": "Text", "maxLength": 1024, "cardinality": "one", "required": False},
    {"name": "uploadDate", "kind": "InlineScalar", "use": "DateTime", "cardinality": "one", "required": False},
    {"name": "creator", "kind": "Ref", "targets": ["Person"], "cardinality": "one", "required": False},
    {"name": "thumbnail", "kind": "Ref", "targets": ["ImageObject"], "cardinality": "one", "required": False},
    {"name": "productionCompany", "kind": "Ref", "targets": ["Organization"], "cardinality": "one", "required": False},
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
    values = opts.get("values") or {}
    errors = opts.get("errors") or []
    field_errors = opts.get("field_errors") or {}
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
        f'<form method="POST" action="{BASE}/new">\n'
        f'{csrf_field(csrf)}\n'
        f'{fields}\n'
        f'<p><button type="submit">Create</button> · <a href="{BASE}">Cancel</a></p>\n'
        f'</form>'
    )
    return {
        "status": 400 if errors else 200,
        "html": layout(title="New " + ENTITY, current_entity=ENTITY, user=user, csrf=csrf, body=body),
    }


def handle_submit(opts):
    api = opts["api"]
    payload = parse_form_body(opts.get("form") or "", PROPERTIES)
    r = api.create(ENTITY, payload)
    if r["status"] == 201 and isinstance(r["body"], dict) and r["body"].get("id"):
        return {"status": 303, "redirect": BASE + "/" + r["body"]["id"]}
    return {"status": 400, "errors": _extract_error_list(r["body"]), "values": payload}
