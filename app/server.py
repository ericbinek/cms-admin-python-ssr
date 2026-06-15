import os
import re
import sys
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from app.views.layout import escape_html, layout
from app.views.login import render_login
from app.api_client import api_for, login as api_login, logout as api_logout, me as api_me, SessionExpiredError
from app.auth import (
    parse_cookies,
    SESSION_COOKIE,
    CSRF_COOKIE,
    random_token,
    csrf_valid,
    set_session_cookie,
    clear_session_cookie,
    set_csrf_cookie,
)

from app.views.blog_posting.list_view import render as blog_posting_list
from app.views.blog_posting.detail_view import render as blog_posting_detail
from app.views.blog_posting.create_view import render_form as blog_posting_create_form, handle_submit as blog_posting_create_submit
from app.views.blog_posting.edit_view import render_form as blog_posting_edit_form, handle_submit as blog_posting_edit_submit
from app.views.blog_posting.delete_view import render_form as blog_posting_delete_form, handle_submit as blog_posting_delete_submit
from app.views.person.list_view import render as person_list
from app.views.person.detail_view import render as person_detail
from app.views.person.create_view import render_form as person_create_form, handle_submit as person_create_submit
from app.views.person.edit_view import render_form as person_edit_form, handle_submit as person_edit_submit
from app.views.person.delete_view import render_form as person_delete_form, handle_submit as person_delete_submit
from app.views.web_page.list_view import render as web_page_list
from app.views.web_page.detail_view import render as web_page_detail
from app.views.web_page.create_view import render_form as web_page_create_form, handle_submit as web_page_create_submit
from app.views.web_page.edit_view import render_form as web_page_edit_form, handle_submit as web_page_edit_submit
from app.views.web_page.delete_view import render_form as web_page_delete_form, handle_submit as web_page_delete_submit
from app.views.image_object.list_view import render as image_object_list
from app.views.image_object.detail_view import render as image_object_detail
from app.views.image_object.create_view import render_form as image_object_create_form, handle_submit as image_object_create_submit
from app.views.image_object.edit_view import render_form as image_object_edit_form, handle_submit as image_object_edit_submit
from app.views.image_object.delete_view import render_form as image_object_delete_form, handle_submit as image_object_delete_submit
from app.views.category_code.list_view import render as category_code_list
from app.views.category_code.detail_view import render as category_code_detail
from app.views.category_code.create_view import render_form as category_code_create_form, handle_submit as category_code_create_submit
from app.views.category_code.edit_view import render_form as category_code_edit_form, handle_submit as category_code_edit_submit
from app.views.category_code.delete_view import render_form as category_code_delete_form, handle_submit as category_code_delete_submit
from app.views.category_code_set.list_view import render as category_code_set_list
from app.views.category_code_set.detail_view import render as category_code_set_detail
from app.views.category_code_set.create_view import render_form as category_code_set_create_form, handle_submit as category_code_set_create_submit
from app.views.category_code_set.edit_view import render_form as category_code_set_edit_form, handle_submit as category_code_set_edit_submit
from app.views.category_code_set.delete_view import render_form as category_code_set_delete_form, handle_submit as category_code_set_delete_submit
from app.views.defined_term.list_view import render as defined_term_list
from app.views.defined_term.detail_view import render as defined_term_detail
from app.views.defined_term.create_view import render_form as defined_term_create_form, handle_submit as defined_term_create_submit
from app.views.defined_term.edit_view import render_form as defined_term_edit_form, handle_submit as defined_term_edit_submit
from app.views.defined_term.delete_view import render_form as defined_term_delete_form, handle_submit as defined_term_delete_submit
from app.views.defined_term_set.list_view import render as defined_term_set_list
from app.views.defined_term_set.detail_view import render as defined_term_set_detail
from app.views.defined_term_set.create_view import render_form as defined_term_set_create_form, handle_submit as defined_term_set_create_submit
from app.views.defined_term_set.edit_view import render_form as defined_term_set_edit_form, handle_submit as defined_term_set_edit_submit
from app.views.defined_term_set.delete_view import render_form as defined_term_set_delete_form, handle_submit as defined_term_set_delete_submit
from app.views.comment.list_view import render as comment_list
from app.views.comment.detail_view import render as comment_detail
from app.views.comment.create_view import render_form as comment_create_form, handle_submit as comment_create_submit
from app.views.comment.edit_view import render_form as comment_edit_form, handle_submit as comment_edit_submit
from app.views.comment.delete_view import render_form as comment_delete_form, handle_submit as comment_delete_submit
from app.views.web_site.list_view import render as web_site_list
from app.views.web_site.detail_view import render as web_site_detail
from app.views.web_site.create_view import render_form as web_site_create_form, handle_submit as web_site_create_submit
from app.views.web_site.edit_view import render_form as web_site_edit_form, handle_submit as web_site_edit_submit
from app.views.web_site.delete_view import render_form as web_site_delete_form, handle_submit as web_site_delete_submit

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"
MAX_BODY_SIZE = 1024 * 1024

ENTITY_ROUTES = [
    {"entity": "BlogPosting", "plural": "blog-postings", "list": blog_posting_list, "detail": blog_posting_detail, "create_form": blog_posting_create_form, "create_submit": blog_posting_create_submit, "edit_form": blog_posting_edit_form, "edit_submit": blog_posting_edit_submit, "delete_form": blog_posting_delete_form, "delete_submit": blog_posting_delete_submit},
    {"entity": "Person", "plural": "persons", "list": person_list, "detail": person_detail, "create_form": person_create_form, "create_submit": person_create_submit, "edit_form": person_edit_form, "edit_submit": person_edit_submit, "delete_form": person_delete_form, "delete_submit": person_delete_submit},
    {"entity": "WebPage", "plural": "web-pages", "list": web_page_list, "detail": web_page_detail, "create_form": web_page_create_form, "create_submit": web_page_create_submit, "edit_form": web_page_edit_form, "edit_submit": web_page_edit_submit, "delete_form": web_page_delete_form, "delete_submit": web_page_delete_submit},
    {"entity": "ImageObject", "plural": "image-objects", "list": image_object_list, "detail": image_object_detail, "create_form": image_object_create_form, "create_submit": image_object_create_submit, "edit_form": image_object_edit_form, "edit_submit": image_object_edit_submit, "delete_form": image_object_delete_form, "delete_submit": image_object_delete_submit},
    {"entity": "CategoryCode", "plural": "category-codes", "list": category_code_list, "detail": category_code_detail, "create_form": category_code_create_form, "create_submit": category_code_create_submit, "edit_form": category_code_edit_form, "edit_submit": category_code_edit_submit, "delete_form": category_code_delete_form, "delete_submit": category_code_delete_submit},
    {"entity": "CategoryCodeSet", "plural": "category-code-sets", "list": category_code_set_list, "detail": category_code_set_detail, "create_form": category_code_set_create_form, "create_submit": category_code_set_create_submit, "edit_form": category_code_set_edit_form, "edit_submit": category_code_set_edit_submit, "delete_form": category_code_set_delete_form, "delete_submit": category_code_set_delete_submit},
    {"entity": "DefinedTerm", "plural": "defined-terms", "list": defined_term_list, "detail": defined_term_detail, "create_form": defined_term_create_form, "create_submit": defined_term_create_submit, "edit_form": defined_term_edit_form, "edit_submit": defined_term_edit_submit, "delete_form": defined_term_delete_form, "delete_submit": defined_term_delete_submit},
    {"entity": "DefinedTermSet", "plural": "defined-term-sets", "list": defined_term_set_list, "detail": defined_term_set_detail, "create_form": defined_term_set_create_form, "create_submit": defined_term_set_create_submit, "edit_form": defined_term_set_edit_form, "edit_submit": defined_term_set_edit_submit, "delete_form": defined_term_set_delete_form, "delete_submit": defined_term_set_delete_submit},
    {"entity": "Comment", "plural": "comments", "list": comment_list, "detail": comment_detail, "create_form": comment_create_form, "create_submit": comment_create_submit, "edit_form": comment_edit_form, "edit_submit": comment_edit_submit, "delete_form": comment_delete_form, "delete_submit": comment_delete_submit},
    {"entity": "WebSite", "plural": "web-sites", "list": web_site_list, "detail": web_site_detail, "create_form": web_site_create_form, "create_submit": web_site_create_submit, "edit_form": web_site_edit_form, "edit_submit": web_site_edit_submit, "delete_form": web_site_delete_form, "delete_submit": web_site_delete_submit},
]

STATIC_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
}


def _index_page(user, csrf):
    items = "".join(f'<li><a href="/{r["plural"]}">{escape_html(r["entity"])}</a></li>' for r in ENTITY_ROUTES)
    return {
        "status": 200,
        "html": layout(
            title="Dashboard",
            user=user,
            csrf=csrf,
            body=f'<p>Manage content for {len(ENTITY_ROUTES)} entity types.</p><ul>{items}</ul>',
        ),
    }


def _not_found(user=None, csrf=None):
    return {"status": 404, "html": layout(title="Not Found", user=user, csrf=csrf, body='<p role="alert">Page not found.</p>')}


def _invalid_id(user=None, csrf=None):
    return {"status": 400, "html": layout(title="Invalid ID", user=user, csrf=csrf, body='<p role="alert">ID must be a valid UUID.</p>')}


def _match_entity_route(path):
    for r in ENTITY_ROUTES:
        base = "/" + r["plural"]
        if path == base:
            return r, "list", None
        if path == base + "/new":
            return r, "new", None
        if path.startswith(base + "/"):
            rest = path[len(base) + 1:]
            if "/" in rest:
                head, action = rest.split("/", 1)
                if action not in ("edit", "delete"):
                    continue
                return r, action, head
            return r, "detail", rest
    return None


def _require_user(token):
    # Resolves and validates the session by asking the API who we are. A 401 means
    # the session is gone — surfaced as SessionExpiredError so the caller redirects
    # to login. Doubles as the per-request principal lookup for the layout header.
    r = api_me(token)
    if r["status"] == 401 or not isinstance(r["body"], dict) or not r["body"].get("account"):
        raise SessionExpiredError()
    return r["body"]["account"]


class AdminHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self): self._dispatch()
    def do_POST(self): self._dispatch()
    def log_message(self, format, *args): pass

    # --- low-level senders, all carrying any pending Set-Cookie headers ---------

    def _send_html(self, status, html, set_cookies=None):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for cookie in (set_cookies or []):
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _send_redirect(self, location, status=303, set_cookies=None):
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        for cookie in (set_cookies or []):
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _send_response(self, response, set_cookies=None):
        if "redirect" in response:
            self._send_redirect(response["redirect"], response.get("status", 303), set_cookies)
            return
        self._send_html(response.get("status", 200), response["html"], set_cookies)

    def _send_static(self, rel_path):
        full = (PUBLIC_DIR / rel_path).resolve()
        try:
            full.relative_to(PUBLIC_DIR)
        except ValueError:
            self._send_html(404, _not_found()["html"])
            return
        if not full.is_file():
            self._send_html(404, _not_found()["html"])
            return
        ctype = STATIC_TYPES.get(full.suffix.lower(), "application/octet-stream")
        body = full.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def _read_form_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > MAX_BODY_SIZE:
            return ""
        if length == 0:
            return ""
        return self.rfile.read(length).decode("utf-8", errors="replace")

    # --- request lifecycle -----------------------------------------------------

    def _dispatch(self):
        start = time.time()
        url = urlparse(self.path)
        path = url.path
        method = self.command

        cookies = parse_cookies(self.headers.get("Cookie"))
        session_token = cookies.get(SESSION_COOKIE) or None
        # Issue a CSRF token if the browser has none yet; never rotate an existing
        # one (it would invalidate a form open in another tab).
        csrf = cookies.get(CSRF_COOKIE)
        set_cookies = []
        if not csrf:
            csrf = random_token()
            set_cookies.append(set_csrf_cookie(csrf))

        try:
            if method == "GET" and path == "/health":
                body = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if method == "GET" and path == "/style.css":
                self._send_static("style.css")
                return

            if method == "POST":
                form_raw = self._read_form_body()
                form = parse_qs(form_raw, keep_blank_values=True)
                # CSRF: the submitted token must match the cookie set on a prior GET.
                submitted = (form.get("_csrf", [""]) or [""])[0]
                if not csrf_valid(cookies.get(CSRF_COOKIE), submitted):
                    self._send_html(403, layout(title="Forbidden", body='<p role="alert">Invalid or missing CSRF token. Reload the form and try again.</p>'), set_cookies)
                    return
                self._handle_post(path, form, form_raw, session_token, csrf, set_cookies)
                return

            if method == "GET":
                self._handle_get(path, session_token, csrf, set_cookies)
                return

            self._send_html(404, _not_found()["html"], set_cookies)
        except SessionExpiredError:
            self._send_redirect("/login", 303, set_cookies + [clear_session_cookie()])
        except Exception as e:
            print(f"[{method} {path}] {e}", file=sys.stderr)
            self._send_html(500, layout(title="Error", body='<p role="alert">Internal server error.</p>'), set_cookies)
        finally:
            ms = int((time.time() - start) * 1000)
            print(f"{method} {path} {ms}ms", file=sys.stderr)

    def _handle_get(self, path, session_token, csrf, set_cookies):
        if path == "/login":
            # Already carrying a session: go to the dashboard. A stale cookie
            # bounces back here (cleared) on the first failing API call.
            if session_token:
                self._send_redirect("/", 303, set_cookies)
                return
            self._send_response(render_login(csrf=csrf), set_cookies)
            return

        if not session_token:
            self._send_redirect("/login", 303, set_cookies)
            return
        user = _require_user(session_token)
        api = api_for(session_token)

        if path == "/":
            self._send_response(_index_page(user, csrf), set_cookies)
            return

        match = _match_entity_route(path)
        if match is None:
            self._send_response(_not_found(user, csrf), set_cookies)
            return
        route, kind, item_id = match
        id_valid = item_id is None or bool(UUID_PATTERN.match(item_id))
        ctx = {"api": api, "csrf": csrf, "user": user}

        if kind == "list":
            self._send_response(route["list"]({**ctx, "url": self.path}), set_cookies)
            return
        if kind == "new":
            self._send_response(route["create_form"]({**ctx}), set_cookies)
            return
        if not id_valid:
            self._send_response(_invalid_id(user, csrf), set_cookies)
            return
        if kind == "detail":
            self._send_response(route["detail"]({**ctx, "id": item_id}), set_cookies)
            return
        if kind == "edit":
            self._send_response(route["edit_form"]({**ctx, "id": item_id}), set_cookies)
            return
        if kind == "delete":
            self._send_response(route["delete_form"]({**ctx, "id": item_id}), set_cookies)
            return
        self._send_response(_not_found(user, csrf), set_cookies)

    def _handle_post(self, path, form, form_raw, session_token, csrf, set_cookies):
        if path == "/login":
            username = (form.get("username", [""]) or [""])[0].strip()
            password = (form.get("password", [""]) or [""])[0]
            if not username or not password:
                self._send_response(render_login(csrf=csrf, error="Username and password are required.", username=username), set_cookies)
                return
            r = api_login(username, password)
            if r["status"] == 200 and isinstance(r["body"], dict) and r["body"].get("token"):
                self._send_redirect("/", 303, set_cookies + [set_session_cookie(r["body"]["token"])])
                return
            self._send_response(render_login(csrf=csrf, error="Invalid username or password.", username=username), set_cookies)
            return

        if path == "/logout":
            if session_token:
                try:
                    api_logout(session_token)
                except Exception:
                    pass  # best effort, cookie is cleared anyway
            self._send_redirect("/login", 303, set_cookies + [clear_session_cookie()])
            return

        if not session_token:
            self._send_redirect("/login", 303, set_cookies)
            return
        user = _require_user(session_token)
        api = api_for(session_token)

        match = _match_entity_route(path)
        if match is None:
            self._send_response(_not_found(user, csrf), set_cookies)
            return
        route, kind, item_id = match
        id_valid = item_id is None or bool(UUID_PATTERN.match(item_id))
        ctx = {"api": api, "csrf": csrf, "user": user}

        if kind == "new":
            result = route["create_submit"]({**ctx, "form": form_raw})
            if "redirect" in result:
                self._send_redirect(result["redirect"], result.get("status", 303), set_cookies)
                return
            if "html" in result:
                self._send_html(result.get("status", 400), result["html"], set_cookies)
                return
            self._send_response(route["create_form"]({**ctx, "errors": result.get("errors", []), "values": result.get("values", {})}), set_cookies)
            return
        if not id_valid:
            self._send_response(_invalid_id(user, csrf), set_cookies)
            return
        if kind == "edit":
            result = route["edit_submit"]({**ctx, "id": item_id, "form": form_raw})
            if "redirect" in result:
                self._send_redirect(result["redirect"], result.get("status", 303), set_cookies)
                return
            if "html" in result:
                self._send_html(result.get("status", 400), result["html"], set_cookies)
                return
            self._send_response(route["edit_form"]({**ctx, "id": item_id, "errors": result.get("errors", []), "values": result.get("values", {})}), set_cookies)
            return
        if kind == "delete":
            result = route["delete_submit"]({**ctx, "id": item_id})
            if "redirect" in result:
                self._send_redirect(result["redirect"], result.get("status", 303), set_cookies)
                return
            self._send_response(result, set_cookies)
            return
        self._send_response(_not_found(user, csrf), set_cookies)


def main():
    port = int(os.environ.get("PORT", "5004"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), AdminHandler)
    print(f"CMS admin running at http://{host}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Server closed.", file=sys.stderr)
