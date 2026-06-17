import atexit
import json
import os
import random
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie
from pathlib import Path

# Cookie names the admin server sets — kept in sync with app/auth.py.
SESSION_COOKIE = "cms_session"
CSRF_COOKIE = "cms_csrf"

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

SAMPLES = {
    "BlogPosting": {
        "headline": "sample",
        "articleBody": "sample",
        "author": {"__ref": "Person"},
    },
    "Person": {
        "name": "sample",
    },
    "Organization": {
        "name": "sample",
    },
    "WebPage": {
        "headline": "sample",
    },
    "ImageObject": {
        "contentUrl": "https://example.com/x",
    },
    "VideoObject": {
        "contentUrl": "https://example.com/x",
    },
    "AudioObject": {
        "contentUrl": "https://example.com/x",
    },
    "CategoryCode": {
        "name": "sample",
        "codeValue": "sample",
        "inCodeSet": {"__ref": "CategoryCodeSet"},
    },
    "CategoryCodeSet": {
        "name": "sample",
    },
    "DefinedTerm": {
        "name": "sample",
        "termCode": "sample",
        "inDefinedTermSet": {"__ref": "DefinedTermSet"},
    },
    "DefinedTermSet": {
        "name": "sample",
    },
    "Comment": {
        "text": "sample",
        "author": {"__ref": "Person"},
        "about": {"__ref": "BlogPosting"},
    },
    "WebSite": {
        "name": "sample",
        "url": "https://example.com/x",
    },
    "SiteNavigationElement": {
        "name": "sample",
        "url": "https://example.com/x",
    },
}

ENTITIES = ["BlogPosting", "Person", "Organization", "WebPage", "ImageObject", "VideoObject", "AudioObject", "CategoryCode", "CategoryCodeSet", "DefinedTerm", "DefinedTermSet", "Comment", "WebSite", "SiteNavigationElement"]

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin-password"

REPO_ROOT = Path(__file__).resolve().parents[1]
_stack = None
_seeded = {}


def _free_port():
    while True:
        port = random.randint(15000, 17999)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue


def _wait_for_health(base_url, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionResetError, ConnectionRefusedError):
            pass
        time.sleep(0.05)
    return False


class _Stack:
    def __init__(self):
        self.mock_port = _free_port()
        self.admin_port = _free_port()
        env_mock = {**os.environ, "PORT": str(self.mock_port), "PYTHONPATH": str(REPO_ROOT)}
        env_admin = {**os.environ, "PORT": str(self.admin_port),
                     "API_BASE_URL": f"http://127.0.0.1:{self.mock_port}", "PYTHONPATH": str(REPO_ROOT)}
        self.mock_proc = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "tests" / "_mock_api.py")],
            cwd=str(REPO_ROOT), env=env_mock,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.api_base_url = f"http://127.0.0.1:{self.mock_port}"
        if not _wait_for_health(self.api_base_url):
            self.stop()
            raise RuntimeError("Mock API did not become healthy")
        self.admin_proc = subprocess.Popen(
            [sys.executable, "-m", "app"],
            cwd=str(REPO_ROOT), env=env_admin,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.admin_base_url = f"http://127.0.0.1:{self.admin_port}"
        if not _wait_for_health(self.admin_base_url):
            self.stop()
            raise RuntimeError("Admin did not become healthy")

    def stop(self):
        for proc in (getattr(self, "admin_proc", None), getattr(self, "mock_proc", None)):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


def get_stack():
    global _stack
    if _stack is None:
        _stack = _Stack()
        atexit.register(_stack.stop)
    return _stack


def reset_seed_cache():
    _seeded.clear()


# --- HTTP without auto-redirect, returning headers verbatim -------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

    def http_error_303(self, req, fp, code, msg, headers):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_303
    http_error_302 = http_error_303
    http_error_307 = http_error_303
    http_error_308 = http_error_303


def _http_request(method, url, body=None, headers=None):
    final_headers = headers.copy() if headers else {}
    data = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(url, data=data, method=method, headers=final_headers)
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=10) as r:
            raw = r.read()
            return {"status": r.status, "headers": r.headers, "body": raw.decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as e:
        raw = e.read()
        return {"status": e.code, "headers": e.headers, "body": raw.decode("utf-8", errors="replace")}


# --- Cookie jar (a plain name -> value map) -----------------------------------

def _apply_set_cookies(jar, headers):
    for raw in headers.get_all("Set-Cookie") or []:
        jar_part = SimpleCookie()
        try:
            jar_part.load(raw)
        except Exception:
            continue
        for name, morsel in jar_part.items():
            if morsel.value == "":
                jar.pop(name, None)  # Max-Age=0 clears with an empty value
            else:
                jar[name] = morsel.value


def _cookie_header(jar):
    return "; ".join(f"{k}={v}" for k, v in jar.items())


def get_set_cookies(headers):
    return headers.get_all("Set-Cookie") or []


def api_token(jar):
    return jar.get(SESSION_COOKIE)


def admin_get(stack, path, jar=None):
    headers = {"Cookie": _cookie_header(jar)} if jar is not None else {}
    r = _http_request("GET", stack.admin_base_url + path, headers=headers)
    if jar is not None:
        _apply_set_cookies(jar, r["headers"])
    return r


def admin_post_form(stack, path, body, jar=None, with_csrf=True):
    final_body = body or ""
    if with_csrf and jar is not None and jar.get(CSRF_COOKIE) and "_csrf=" not in final_body:
        final_body = (final_body + "&" if final_body else "") + "_csrf=" + urllib.parse.quote(jar[CSRF_COOKIE], safe="")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if jar is not None:
        headers["Cookie"] = _cookie_header(jar)
    r = _http_request("POST", stack.admin_base_url + path, body=final_body, headers=headers)
    if jar is not None:
        _apply_set_cookies(jar, r["headers"])
    return r


# Full browser-like login: GET /login to obtain the csrf cookie, then POST the
# credentials. Returns a cookie jar carrying the session and csrf cookies.
def login_admin(stack):
    jar = {}
    admin_get(stack, "/login", jar)
    r = admin_post_form(
        stack, "/login",
        "username=" + urllib.parse.quote(ADMIN_USERNAME) + "&password=" + urllib.parse.quote(ADMIN_PASSWORD),
        jar,
    )
    if r["status"] != 303:
        raise RuntimeError(f"login_admin failed: expected 303, got {r['status']}")
    return jar


# --- Seeding goes straight to the mock API with the admin bearer token --------

def _encode_one(v):
    if v is None:
        return ""
    if isinstance(v, dict):
        if "__ref" in v:
            return "__needs_resolve__"
        if v.get("@type") == "Language":
            return str(v.get("alternateName", ""))
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _resolve_refs(stack, jar, sample):
    resolved = {}
    for key, value in sample.items():
        if isinstance(value, list):
            out = []
            for v in value:
                if isinstance(v, dict) and "__ref" in v:
                    out.append(ensure_entity(stack, v["__ref"], jar))
                else:
                    out.append(v)
            resolved[key] = out
        elif isinstance(value, dict) and "__ref" in value:
            resolved[key] = ensure_entity(stack, value["__ref"], jar)
        else:
            resolved[key] = value
    return resolved


def _seed_to_mock(stack, jar, entity, payload):
    url = stack.api_base_url + "/" + PLURALS[entity]
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_token(jar),
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"seed({entity}) failed: {e.code} {e.read().decode()}")
    return body["id"]


def ensure_entity(stack, entity, jar):
    if entity in _seeded:
        return _seeded[entity]
    sample = _resolve_refs(stack, jar, SAMPLES[entity])
    item_id = _seed_to_mock(stack, jar, entity, sample)
    _seeded[entity] = item_id
    return item_id


def seed_with(stack, entity, overrides, jar):
    sample = _resolve_refs(stack, jar, SAMPLES[entity])
    sample.update(overrides)
    return _seed_to_mock(stack, jar, entity, sample)


def form_body_for(stack, entity, jar):
    sample = _resolve_refs(stack, jar, SAMPLES[entity])
    pairs = []
    for key, value in sample.items():
        if isinstance(value, list):
            for vv in value:
                pairs.append((key, _encode_one(vv)))
        else:
            pairs.append((key, _encode_one(value)))
    return urllib.parse.urlencode(pairs)
