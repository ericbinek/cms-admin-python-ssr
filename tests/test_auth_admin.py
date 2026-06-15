import re
import unittest

from tests._helpers import (
    admin_get,
    admin_post_form,
    form_body_for,
    get_set_cookies,
    get_stack,
    login_admin,
    SESSION_COOKIE,
)

ENTITY = "BlogPosting"
BASE = "/blog-postings"


class AdminAuthConformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = get_stack()

    def test_unauthenticated_dashboard_redirects_to_login(self):
        r = admin_get(self.stack, "/")
        self.assertEqual(r["status"], 303)
        self.assertEqual(r["headers"].get("Location"), "/login")

    def test_unauthenticated_entity_route_redirects_to_login(self):
        r = admin_get(self.stack, BASE)
        self.assertEqual(r["status"], 303)
        self.assertEqual(r["headers"].get("Location"), "/login")

    def test_get_login_renders_a_sign_in_form(self):
        r = admin_get(self.stack, "/login")
        self.assertEqual(r["status"], 200)
        self.assertRegex(r["body"], r'<form[^>]+method="POST"[^>]+action="/login"')
        self.assertIn('type="password"', r["body"])
        self.assertIn('name="_csrf"', r["body"])

    def test_login_with_wrong_credentials_returns_401_with_an_alert(self):
        jar = {}
        admin_get(self.stack, "/login", jar)
        r = admin_post_form(self.stack, "/login", "username=admin&password=wrong", jar)
        self.assertEqual(r["status"], 401)
        self.assertRegex(r["body"], r'role="alert"')

    def test_login_sets_an_httponly_samesite_strict_session_cookie_and_redirects(self):
        jar = {}
        admin_get(self.stack, "/login", jar)
        r = admin_post_form(self.stack, "/login", "username=admin&password=admin-password", jar)
        self.assertEqual(r["status"], 303)
        self.assertEqual(r["headers"].get("Location"), "/")
        set_cookies = "\n".join(get_set_cookies(r["headers"]))
        self.assertRegex(set_cookies, SESSION_COOKIE + "=")
        self.assertRegex(set_cookies, r"(?i)HttpOnly")
        self.assertRegex(set_cookies, r"(?i)SameSite=Strict")

    def test_authenticated_dashboard_renders_after_login(self):
        jar = login_admin(self.stack)
        r = admin_get(self.stack, "/", jar)
        self.assertEqual(r["status"], 200)
        self.assertIn("Dashboard", r["body"])
        self.assertIn("Sign out", r["body"])

    def test_state_changing_post_without_a_csrf_token_is_rejected_with_403(self):
        jar = login_admin(self.stack)
        body = form_body_for(self.stack, ENTITY, jar)
        r = admin_post_form(self.stack, BASE + "/new", body, jar, with_csrf=False)
        self.assertEqual(r["status"], 403)

    def test_state_changing_post_with_a_wrong_csrf_token_is_rejected_with_403(self):
        jar = login_admin(self.stack)
        body = form_body_for(self.stack, ENTITY, jar) + "&_csrf=not-the-real-token"
        r = admin_post_form(self.stack, BASE + "/new", body, jar, with_csrf=False)
        self.assertEqual(r["status"], 403)

    def test_logout_clears_the_session_and_protected_routes_redirect_again(self):
        jar = login_admin(self.stack)
        out = admin_post_form(self.stack, "/logout", "", jar)
        self.assertEqual(out["status"], 303)
        self.assertEqual(out["headers"].get("Location"), "/login")
        after = admin_get(self.stack, "/", jar)
        self.assertEqual(after["status"], 303)
        self.assertEqual(after["headers"].get("Location"), "/login")


if __name__ == "__main__":
    unittest.main()
