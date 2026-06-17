import json
import os
import urllib.error
import urllib.parse
import urllib.request

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


def _base_url():
    return (os.environ.get("API_BASE_URL") or "http://localhost:3004").rstrip("/")


def plural_of(entity):
    if entity not in PLURALS:
        raise ValueError(f"Unknown entity for plural lookup: {entity}")
    return PLURALS[entity]


class SessionExpiredError(Exception):
    # Raised when a bound request gets 401 from the API — the session is invalid or
    # expired upstream. The server catches it, clears the cookie, and redirects to
    # the login page.
    def __init__(self):
        super().__init__("Session expired.")


def _request(method, path, token=None, body=None):
    url = _base_url() + path
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return {"status": r.status, "body": json.loads(raw) if raw else None, "etag": r.headers.get("ETag")}
    except urllib.error.HTTPError as e:
        raw = e.read()
        return {"status": e.code, "body": json.loads(raw) if raw else None, "etag": e.headers.get("ETag")}
    except urllib.error.URLError as e:
        return {"status": 0, "body": {"message": f"ApiClient request failed: {e}"}, "etag": None}


# Auth routes — driven by the server's login/logout flow, not by the views. They
# return the raw status so the server can map credentials to cookies.
def login(username, password):
    return _request("POST", "/auth/login", body={"username": username, "password": password})


def logout(token):
    return _request("POST", "/auth/logout", token=token)


def me(token):
    return _request("GET", "/auth/me", token=token)


class _BoundClient:
    # A session-bound client. Every entity call carries the bearer token; a 401
    # becomes a SessionExpiredError.
    def __init__(self, token):
        self._token = token

    def _authed(self, method, path, body=None):
        r = _request(method, path, token=self._token, body=body)
        if r["status"] == 401:
            raise SessionExpiredError()
        return r

    def list(self, entity, query=None):
        query = {k: v for k, v in (query or {}).items() if v not in (None, "")}
        qs = urllib.parse.urlencode(query)
        path = "/" + plural_of(entity) + (("?" + qs) if qs else "")
        return self._authed("GET", path)

    def get(self, entity, id):
        return self._authed("GET", "/" + plural_of(entity) + "/" + urllib.parse.quote(id, safe=""))

    def create(self, entity, payload):
        return self._authed("POST", "/" + plural_of(entity), payload)

    def update(self, entity, id, payload):
        return self._authed("PUT", "/" + plural_of(entity) + "/" + urllib.parse.quote(id, safe=""), payload)

    def remove(self, entity, id):
        return self._authed("DELETE", "/" + plural_of(entity) + "/" + urllib.parse.quote(id, safe=""))


def api_for(token):
    return _BoundClient(token)
