import json
import os
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Tiny in-memory mock of the CMS API for admin conformance tests. It mirrors the
# real API's wire envelope ({items, total}, {id, ...item}, {status, error, message,
# details, path}) AND its auth contract: /auth/login issues an opaque bearer token,
# /auth/me and /auth/logout validate it, and every entity route requires a live
# session (401 without). RBAC is the real API's job; here the seeded admin has full
# access, which is enough to prove the admin frontend's cookie-to-bearer proxy and
# CSRF handling.

SCHEMAS = {
    "BlogPosting": {"plural": "blog-postings", "required": ["headline", "articleBody", "author"]},
    "Person": {"plural": "persons", "required": ["name"]},
    "Organization": {"plural": "organizations", "required": ["name"]},
    "WebPage": {"plural": "web-pages", "required": ["headline"]},
    "ImageObject": {"plural": "image-objects", "required": ["contentUrl"]},
    "VideoObject": {"plural": "video-objects", "required": ["contentUrl"]},
    "AudioObject": {"plural": "audio-objects", "required": ["contentUrl"]},
    "CategoryCode": {"plural": "category-codes", "required": ["name", "codeValue", "inCodeSet"]},
    "CategoryCodeSet": {"plural": "category-code-sets", "required": ["name"]},
    "DefinedTerm": {"plural": "defined-terms", "required": ["name", "termCode", "inDefinedTermSet"]},
    "DefinedTermSet": {"plural": "defined-term-sets", "required": ["name"]},
    "Comment": {"plural": "comments", "required": ["text", "author", "about"]},
    "WebSite": {"plural": "web-sites", "required": ["name", "url"]},
    "SiteNavigationElement": {"plural": "site-navigation-elements", "required": ["name", "url"]},
}

ENTITY_BY_PLURAL = {s["plural"]: name for name, s in SCHEMAS.items()}

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin-password"

_LOCK = threading.Lock()
_STORE = {name: {} for name in SCHEMAS}
_SESSIONS = {}  # token -> account
_ADMIN = {"id": str(uuid.uuid4()), "username": ADMIN_USERNAME, "role": "admin"}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _error(status, code, message, details, path):
    return {"status": status, "error": code, "message": message, "details": details, "path": path}


def _unauthorized(request_path):
    return _error(401, "UNAUTHORIZED", "Authentication is required, or the session is invalid or expired.", [], request_path)


def _validate_required(entity, data, partial):
    if partial:
        return []
    missing = []
    for f in SCHEMAS[entity]["required"]:
        v = data.get(f)
        if v is None or v == "" or (isinstance(v, list) and not v):
            missing.append(f'Field "{f}" is required.')
    return missing


def _bearer_token(handler):
    header = handler.headers.get("Authorization")
    if not header:
        return None
    parts = header.strip().split(" ", 1)
    if len(parts) == 2 and parts[0] == "Bearer":
        return parts[1]
    return None


def _send_json(handler, status, data):
    handler.send_response(status)
    if status == 204 or data is None:
        handler.end_headers()
        return
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self): self._dispatch()
    def do_POST(self): self._dispatch()
    def do_PUT(self): self._dispatch()
    def do_DELETE(self): self._dispatch()
    def log_message(self, format, *args): pass

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            raise json.JSONDecodeError("not an object", "", 0)
        return data

    def _account_for(self):
        token = _bearer_token(self)
        if not token:
            return None
        return _SESSIONS.get(token)

    def _dispatch(self):
        url = urlparse(self.path)
        path = url.path
        method = self.command
        request_path = f"{method} {path}"
        try:
            with _LOCK:
                self._handle(method, path, url, request_path)
        except json.JSONDecodeError:
            _send_json(self, 400, _error(400, "INVALID_JSON", "Request body is not valid JSON.", [], request_path))
        except Exception as e:
            _send_json(self, 500, _error(500, "INTERNAL_ERROR", f"Internal server error: {e}", [], request_path))

    def _handle(self, method, path, url, request_path):
        if method == "GET" and path == "/health":
            _send_json(self, 200, {"status": "ok"})
            return

        if path == "/auth/login":
            if method != "POST":
                _send_json(self, 405, _error(405, "METHOD_NOT_ALLOWED", "Method not allowed.", [], request_path))
                return
            data = self._read_json()
            if not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
                _send_json(self, 400, _error(400, "VALIDATION_ERROR", "Invalid request data.", ['Fields "username" and "password" are required.'], request_path))
                return
            if data["username"] != ADMIN_USERNAME or data["password"] != ADMIN_PASSWORD:
                _send_json(self, 401, _unauthorized(request_path))
                return
            token = str(uuid.uuid4())
            _SESSIONS[token] = _ADMIN
            _send_json(self, 200, {
                "token": token,
                "account": {"id": _ADMIN["id"], "username": _ADMIN["username"], "role": _ADMIN["role"]},
                "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            return

        if path == "/auth/logout":
            if method != "POST":
                _send_json(self, 405, _error(405, "METHOD_NOT_ALLOWED", "Method not allowed.", [], request_path))
                return
            token = _bearer_token(self)
            if not token or token not in _SESSIONS:
                _send_json(self, 401, _unauthorized(request_path))
                return
            del _SESSIONS[token]
            _send_json(self, 204, None)
            return

        if path == "/auth/me":
            if method != "GET":
                _send_json(self, 405, _error(405, "METHOD_NOT_ALLOWED", "Method not allowed.", [], request_path))
                return
            account = self._account_for()
            if not account:
                _send_json(self, 401, _unauthorized(request_path))
                return
            _send_json(self, 200, {"account": {"id": account["id"], "username": account["username"], "role": account["role"]}})
            return

        # Every entity route requires a live session.
        account = self._account_for()
        if not account:
            _send_json(self, 401, _unauthorized(request_path))
            return

        seg = [s for s in path.split("/") if s]
        if not (1 <= len(seg) <= 2):
            _send_json(self, 404, _error(404, "ROUTE_NOT_FOUND", "No route matches this request.", [], request_path))
            return
        entity = ENTITY_BY_PLURAL.get(seg[0])
        if entity is None:
            _send_json(self, 404, _error(404, "ROUTE_NOT_FOUND", "No route matches this request.", [], request_path))
            return

        collection = _STORE[entity]

        if len(seg) == 1:
            if method == "GET":
                items = list(collection.values())
                qs = parse_qs(url.query)
                sort = qs.get("sort", ["dateCreated"])[0]
                order = qs.get("order", ["desc"])[0]
                items.sort(key=lambda i: i.get(sort) or "", reverse=order != "asc")
                total = len(items)
                limit = min(int(qs.get("limit", ["20"])[0]), 100)
                offset = int(qs.get("offset", ["0"])[0])
                _send_json(self, 200, {"items": items[offset:offset + limit], "total": total})
                return
            if method == "POST":
                data = self._read_json()
                errs = _validate_required(entity, data, False)
                if errs:
                    _send_json(self, 400, _error(400, "VALIDATION_ERROR", "Invalid request data.", errs, request_path))
                    return
                now = _now()
                item = {"@context": "https://schema.org", "@type": entity, **data,
                        "id": str(uuid.uuid4()), "dateCreated": now, "dateModified": now}
                collection[item["id"]] = item
                _send_json(self, 201, item)
                return
            _send_json(self, 405, _error(405, "METHOD_NOT_ALLOWED", "Method not allowed.", [], request_path))
            return

        item_id = seg[1].lower()
        current = collection.get(item_id)

        if method == "GET":
            if current is None:
                _send_json(self, 404, _error(404, "NOT_FOUND", f"{entity} not found.", [], request_path))
                return
            _send_json(self, 200, current)
            return
        if method == "PUT":
            if current is None:
                _send_json(self, 404, _error(404, "NOT_FOUND", f"{entity} not found.", [], request_path))
                return
            data = self._read_json()
            errs = _validate_required(entity, data, True)
            if errs:
                _send_json(self, 400, _error(400, "VALIDATION_ERROR", "Invalid request data.", errs, request_path))
                return
            updated = {**current, **data, "id": current["id"], "dateCreated": current["dateCreated"],
                       "dateModified": _now(), "@context": current.get("@context", "https://schema.org"),
                       "@type": current.get("@type", entity)}
            collection[item_id] = updated
            _send_json(self, 200, updated)
            return
        if method == "DELETE":
            if current is None:
                _send_json(self, 404, _error(404, "NOT_FOUND", f"{entity} not found.", [], request_path))
                return
            del collection[item_id]
            _send_json(self, 204, None)
            return
        _send_json(self, 405, _error(405, "METHOD_NOT_ALLOWED", "Method not allowed.", [], request_path))


def main():
    port = int(os.environ.get("PORT", "0"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), MockHandler)
    actual_port = server.server_address[1]
    if os.environ.get("MOCK_REPORT_PORT_FILE"):
        Path(os.environ["MOCK_REPORT_PORT_FILE"]).write_text(str(actual_port))
    print(f"mock api ready on {actual_port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
