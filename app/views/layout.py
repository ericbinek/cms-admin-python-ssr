import json
import re

ENTITIES = ["BlogPosting", "Person", "Organization", "WebPage", "ImageObject", "VideoObject", "AudioObject", "CategoryCode", "CategoryCodeSet", "DefinedTerm", "DefinedTermSet", "Comment", "WebSite", "SiteNavigationElement"]

PLURALS = {
    "BlogPosting": "blog-postings",
    "Person": "persons",
    "Organization": "organizations",
    "WebPage": "web-pages",
    "ImageObject": "image-objects",
    "VideoObject": "video-objects",
    "AudioObject": "audio-objects",
    "CategoryCode": "category-codes",
    "CategoryCodeSet": "category-code-sets",
    "DefinedTerm": "defined-terms",
    "DefinedTermSet": "defined-term-sets",
    "Comment": "comments",
    "WebSite": "web-sites",
    "SiteNavigationElement": "site-navigation-elements",
}

DISPLAY_KEYS = {
    "BlogPosting": ("headline", "alternativeHeadline",),
    "Person": ("name", "givenName", "familyName",),
    "Organization": ("name", "legalName",),
    "WebPage": ("headline",),
    "ImageObject": ("name", "caption", "contentUrl",),
    "VideoObject": ("name", "caption", "contentUrl",),
    "AudioObject": ("name", "contentUrl",),
    "CategoryCode": ("name", "codeValue",),
    "CategoryCodeSet": ("name",),
    "DefinedTerm": ("name", "termCode",),
    "DefinedTermSet": ("name",),
    "Comment": ("text",),
    "WebSite": ("name",),
    "SiteNavigationElement": ("name",),
}

LONG_TEXT_HINT = {"articleBody", "description", "text"}

_FORM_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")

_HTML_ESCAPE_MAP = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})


def plural_of(entity):
    return PLURALS.get(entity) or (entity.lower() + "s")


def escape_html(s):
    if s is None or s == "":
        return ""
    return str(s).translate(_HTML_ESCAPE_MAP)


def csrf_field(token):
    # The hidden CSRF synchronizer field carried by every state-changing form.
    return f'<input type="hidden" name="_csrf" value="{escape_html(token)}">'


def _is_safe_href(value):
    # Only http(s), mailto and site-relative values may become clickable links. A
    # stored "javascript:" or "data:" URL is rendered as inert escaped text, so a
    # bad value in the data store cannot turn into stored XSS when a user clicks.
    if not isinstance(value, str):
        return False
    v = value.strip().lower()
    return v.startswith(("http://", "https://", "mailto:", "/"))


def layout(title="CMS Admin", body="", current_entity=None, user=None, csrf=None, flash=None):
    if user:
        nav_items = []
        for e in ENTITIES:
            current = ' aria-current="page"' if e == current_entity else ""
            nav_items.append(f'<li><a href="/{PLURALS[e]}"{current}>{escape_html(e)}</a></li>')
        nav = "".join(nav_items)
        logout = (
            f'<form method="POST" action="/logout" class="logout">{csrf_field(csrf)}'
            f'<button type="submit">Sign out</button></form>'
        )
        header = (
            f'<header>\n'
            f'<nav aria-label="Primary">\n'
            f'<ul>{nav}</ul>\n'
            f'</nav>\n'
            f'<p class="session">Signed in as <strong>{escape_html(user["username"])}</strong> '
            f'({escape_html(user["role"])}) {logout}</p>\n'
            f'</header>'
        )
    else:
        header = "<header><p><strong>CMS Admin</strong></p></header>"
    flash_el = f'<p role="status">{escape_html(flash)}</p>' if flash else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape_html(title)} — CMS Admin</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
{header}
<main>
<h1>{escape_html(title)}</h1>
{flash_el}
{body}
</main>
</body>
</html>
"""


def display_name(item, entity):
    if not item:
        return ""
    for k in DISPLAY_KEYS.get(entity, ("name", "headline")):
        v = item.get(k)
        if isinstance(v, str) and v:
            return v
    return item.get("id", "")


def error_page(status, message, user=None):
    return {
        "status": status,
        "html": layout(
            title="Not Found" if status == 404 else "Error",
            user=user,
            body=f'<p role="alert">{escape_html(message)}</p>',
        ),
    }


def _format_scalar(value, use):
    if use == "URL":
        if not _is_safe_href(value):
            return escape_html(value)
        v = escape_html(value)
        return f'<a href="{v}" rel="noopener noreferrer">{v}</a>'
    if use in ("DateTime", "Date", "Time"):
        v = escape_html(value)
        return f'<time datetime="{v}">{v}</time>'
    if use == "Boolean":
        return "Yes" if value else "No"
    return escape_html(str(value))


def format_value(value, prop):
    if value is None or value == "":
        return "<em>—</em>"
    if isinstance(value, list):
        if not value:
            return "<em>—</em>"
        single = {**prop, "cardinality": "one"}
        items = "".join(f"<li>{format_value(v, single)}</li>" for v in value)
        return f"<ul>{items}</ul>"
    if prop["kind"] == "Ref":
        target = prop["targets"][0]
        plural = PLURALS.get(target, target.lower() + "s")
        return f'<a href="/{plural}/{escape_html(value)}">{escape_html(target)}: {escape_html(value)}</a>'
    if prop["kind"] == "Embed":
        if prop.get("use") == "Language" and isinstance(value, dict):
            code = value.get("alternateName") or value.get("name") or ""
            return f'<span lang="{escape_html(code)}">{escape_html(code)}</span>'
        return f"<code>{escape_html(json.dumps(value, ensure_ascii=False))}</code>"
    if prop["kind"] == "Enum":
        return escape_html(str(value))
    return _format_scalar(value, prop.get("use"))


def render_field(prop, value=None, ref_options=None, errors=None):
    ref_options = ref_options or {}
    errors = errors or []
    field_id = f"field-{prop['name']}"
    required_attr = " required" if prop["required"] else ""
    required_mark = ' <span aria-hidden="true">*</span>' if prop["required"] else ""
    aria_invalid = ' aria-invalid="true"' if errors else ""
    label_text = escape_html(prop["name"]) + required_mark
    help_html = (f'<small role="alert">{"; ".join(escape_html(e) for e in errors)}</small>') if errors else ""
    input_html = _render_input(prop, value, field_id, required_attr, aria_invalid, ref_options)
    return f"<p>\n<label for=\"{field_id}\">{label_text}</label><br>\n{input_html}\n{help_html}\n</p>"


def _render_input(prop, value, field_id, required_attr, aria_invalid, ref_options):
    name = escape_html(prop["name"])
    kind = prop["kind"]
    if kind == "Enum":
        opts = "".join(
            f'<option value="{escape_html(v)}"{" selected" if v == value else ""}>{escape_html(v)}</option>'
            for v in prop["values"]
        )
        placeholder = "" if prop["required"] else '<option value="">—</option>'
        return f'<select id="{field_id}" name="{name}"{required_attr}{aria_invalid}>{placeholder}{opts}</select>'
    if kind == "Ref":
        if prop["cardinality"] == "many":
            current = value if isinstance(value, list) else ([value] if value else [])
        else:
            current = value[0] if isinstance(value, list) else value
        opts = []
        for o in ref_options.get(prop["name"], []):
            sel = (o["value"] in current) if prop["cardinality"] == "many" else (current == o["value"])
            opts.append(f'<option value="{escape_html(o["value"])}"{" selected" if sel else ""}>{escape_html(o["label"])}</option>')
        multiple = " multiple" if prop["cardinality"] == "many" else ""
        placeholder = '<option value="">—</option>' if prop["cardinality"] == "one" and not prop["required"] else ""
        return f'<select id="{field_id}" name="{name}"{multiple}{required_attr}{aria_invalid}>{placeholder}{"".join(opts)}</select>'
    if kind == "Embed" and prop.get("use") == "Language":
        v = value.get("alternateName", "") if isinstance(value, dict) else (value or "")
        return f'<input id="{field_id}" name="{name}" type="text" value="{escape_html(v)}"{required_attr}{aria_invalid}>'
    if prop["cardinality"] == "many":
        v = "\n".join(value) if isinstance(value, list) else (value or "")
        return f'<textarea id="{field_id}" name="{name}" rows="3"{required_attr}{aria_invalid}>{escape_html(v)}</textarea>'
    use = prop.get("use")
    if use == "Text" and prop["name"] in LONG_TEXT_HINT:
        return f'<textarea id="{field_id}" name="{name}" rows="6"{required_attr}{aria_invalid}>{escape_html(value)}</textarea>'
    if use == "URL":
        return f'<input id="{field_id}" name="{name}" type="url" value="{escape_html(value)}"{required_attr}{aria_invalid}>'
    if use == "Integer":
        v = "" if value is None else escape_html(str(value))
        return f'<input id="{field_id}" name="{name}" type="number" step="1" value="{v}"{required_attr}{aria_invalid}>'
    if use == "Number":
        v = "" if value is None else escape_html(str(value))
        return f'<input id="{field_id}" name="{name}" type="number" step="any" value="{v}"{required_attr}{aria_invalid}>'
    if use == "Boolean":
        checked = " checked" if value in (True, "true", "on") else ""
        return f'<input id="{field_id}" name="{name}" type="checkbox" value="true"{checked}{aria_invalid}>'
    if use in ("DateTime", "Date", "Time"):
        v = value.rstrip("Z")[:16] if isinstance(value, str) else ""
        return f'<input id="{field_id}" name="{name}" type="datetime-local" value="{escape_html(v)}"{required_attr}{aria_invalid}>'
    return f'<input id="{field_id}" name="{name}" type="text" value="{escape_html(value)}"{required_attr}{aria_invalid}>'


def _coerce_form_value(raw, prop):
    if raw in (None, ""):
        return None
    if prop["kind"] in ("Enum", "Ref"):
        return str(raw)
    if prop["kind"] == "Embed" and prop.get("use") == "Language":
        return {"@type": "Language", "alternateName": str(raw)}
    use = prop.get("use")
    if use == "Integer":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if use == "Number":
        try:
            return float(raw)
        except (TypeError, ValueError):
            return raw
    if use == "Boolean":
        return raw in ("true", "on", "1")
    if use in ("DateTime", "Date", "Time"):
        if isinstance(raw, str) and _FORM_ISO_PATTERN.match(raw):
            return raw + ":00Z"
        return str(raw)
    return str(raw)


def _parse_form_pairs(raw):
    import urllib.parse as _up
    if not raw:
        return {}
    out = {}
    for pair in raw.split("&"):
        if not pair:
            continue
        k, _, v = pair.partition("=")
        key = _up.unquote_plus(k)
        value = _up.unquote_plus(v) if _ else ""
        if key in out:
            if not isinstance(out[key], list):
                out[key] = [out[key]]
            out[key].append(value)
        else:
            out[key] = value
    return out


def parse_form_body(raw, properties):
    pairs = _parse_form_pairs(raw)
    out = {}
    for prop in properties:
        name = prop["name"]
        if prop["cardinality"] == "many":
            if prop["kind"] == "Ref":
                values = pairs.get(name, [])
                if not isinstance(values, list):
                    values = [values]
                values = [v for v in values if v != ""]
            else:
                single = pairs.get(name, "")
                if isinstance(single, list):
                    single = "\n".join(single)
                values = [v.strip() for v in re.split(r"\r?\n", single) if v.strip()]
            coerced = [c for c in (_coerce_form_value(v, prop) for v in values) if c is not None]
            if coerced:
                out[name] = coerced
        elif prop["kind"] == "InlineScalar" and prop.get("use") == "Boolean":
            out[name] = name in pairs
        else:
            raw_value = pairs.get(name)
            v = _coerce_form_value(raw_value, prop)
            if v is not None:
                out[name] = v
    return out


def form_values_from_item(item, properties):
    out = {}
    if not item:
        return out
    for p in properties:
        if p["name"] in item:
            out[p["name"]] = item[p["name"]]
    return out
