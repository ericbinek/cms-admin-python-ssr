import hmac
import os
import secrets
from http.cookies import SimpleCookie
from urllib.parse import quote, unquote

# Cookie names are admin-frontend internal; the API never reads them. The session
# cookie carries the API bearer token, the csrf cookie the synchronizer token
# rendered into every form.
SESSION_COOKIE = "cms_session"
CSRF_COOKIE = "cms_csrf"

# Both cookies live at most as long as the API session cap (8h). Secure is on only
# behind HTTPS; set COOKIE_SECURE=true in production. SameSite=Strict and HttpOnly
# are always on — the server renders the csrf token into forms itself, so no client
# script needs to read either cookie.
MAX_AGE = 60 * 60 * 8


def _cookie_secure():
    return (os.environ.get("COOKIE_SECURE") or "").lower() == "true"


def parse_cookies(header):
    out = {}
    if not header:
        return out
    jar = SimpleCookie()
    try:
        jar.load(header)
    except Exception:
        return out
    for name, morsel in jar.items():
        out[name] = unquote(morsel.value)
    return out


def _serialize(name, value, max_age):
    parts = [
        f"{name}={quote(value, safe='')}",
        "Path=/",
        "HttpOnly",
        "SameSite=Strict",
        f"Max-Age={max_age}",
    ]
    if _cookie_secure():
        parts.append("Secure")
    return "; ".join(parts)


def set_session_cookie(token):
    return _serialize(SESSION_COOKIE, token, MAX_AGE)


def clear_session_cookie():
    return _serialize(SESSION_COOKIE, "", 0)


def set_csrf_cookie(token):
    return _serialize(CSRF_COOKIE, token, MAX_AGE)


def random_token():
    return secrets.token_hex(32)


def csrf_valid(cookie_token, form_token):
    # Constant-time comparison of the cookie token against the submitted form
    # token. Non-strings or unequal lengths fail closed without leaking timing.
    if not isinstance(cookie_token, str) or not isinstance(form_token, str):
        return False
    if cookie_token == "" or len(cookie_token) != len(form_token):
        return False
    return hmac.compare_digest(cookie_token, form_token)
