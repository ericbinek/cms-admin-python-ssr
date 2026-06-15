import unittest

from tests._helpers import (
    admin_get,
    admin_post_form,
    ensure_entity,
    form_body_for,
    get_stack,
    login_admin,
    reset_seed_cache,
    seed_with,
)

ENTITY = "CategoryCodeSet"
BASE = "/category-code-sets"


class CategoryCodeSetAdminTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = get_stack()
        cls.jar = login_admin(cls.stack)

    def setUp(self):
        reset_seed_cache()

    def test_unauthenticated_list_redirects_to_login(self):
        r = admin_get(self.stack, BASE)  # no jar -> no session cookie
        self.assertEqual(r["status"], 303)
        self.assertEqual(r["headers"].get("Location"), "/login")

    def test_get_list_renders_semantic_page(self):
        ensure_entity(self.stack, ENTITY, self.jar)
        r = admin_get(self.stack, BASE, self.jar)
        self.assertEqual(r["status"], 200)
        self.assertRegex(r["body"], r"<table\b")
        self.assertRegex(r["body"], r"<caption>")
        self.assertIn(ENTITY, r["body"])

    def test_get_new_renders_a_form_with_a_csrf_field(self):
        r = admin_get(self.stack, BASE + "/new", self.jar)
        self.assertEqual(r["status"], 200)
        self.assertRegex(r["body"], r'<form[^>]+method="POST"')
        self.assertIn('name="_csrf"', r["body"])
        self.assertIn(f'action="{BASE}/new"', r["body"])

    def test_post_new_with_valid_form_redirects_to_detail(self):
        body = form_body_for(self.stack, ENTITY, self.jar)
        r = admin_post_form(self.stack, BASE + "/new", body, self.jar)
        self.assertEqual(r["status"], 303)
        loc = r["headers"].get("Location", "")
        self.assertTrue(loc.startswith(BASE + "/"), f"expected redirect to {BASE}/<id>, got {loc}")

    def test_post_new_with_empty_form_returns_400_or_303(self):
        r = admin_post_form(self.stack, BASE + "/new", "", self.jar)
        if r["status"] == 303:
            return
        self.assertEqual(r["status"], 400)
        self.assertRegex(r["body"], r'role="alert"')

    def test_get_detail_returns_200_with_article_markup(self):
        item_id = ensure_entity(self.stack, ENTITY, self.jar)
        r = admin_get(self.stack, BASE + "/" + item_id, self.jar)
        self.assertEqual(r["status"], 200)
        self.assertRegex(r["body"], r"<article\b")
        self.assertRegex(r["body"], r"<dl>")
        self.assertIn(item_id, r["body"])

    def test_get_edit_renders_pre_filled_form(self):
        item_id = ensure_entity(self.stack, ENTITY, self.jar)
        r = admin_get(self.stack, BASE + "/" + item_id + "/edit", self.jar)
        self.assertEqual(r["status"], 200)
        self.assertRegex(r["body"], r'<form[^>]+method="POST"')
        self.assertIn('name="_csrf"', r["body"])

    def test_post_edit_redirects_back_to_detail(self):
        item_id = ensure_entity(self.stack, ENTITY, self.jar)
        body = form_body_for(self.stack, ENTITY, self.jar)
        r = admin_post_form(self.stack, BASE + "/" + item_id + "/edit", body, self.jar)
        self.assertEqual(r["status"], 303)
        self.assertEqual(r["headers"].get("Location"), BASE + "/" + item_id)

    def test_get_delete_renders_confirmation_form(self):
        item_id = ensure_entity(self.stack, ENTITY, self.jar)
        r = admin_get(self.stack, BASE + "/" + item_id + "/delete", self.jar)
        self.assertEqual(r["status"], 200)
        self.assertRegex(r["body"], r'<form[^>]+method="POST"')
        self.assertIn("Confirm Delete", r["body"])

    def test_post_delete_redirects_to_list(self):
        item_id = ensure_entity(self.stack, ENTITY, self.jar)
        r = admin_post_form(self.stack, BASE + "/" + item_id + "/delete", "", self.jar)
        self.assertEqual(r["status"], 303)
        self.assertEqual(r["headers"].get("Location"), BASE)

    def test_get_detail_with_non_uuid_id_returns_400_with_alert(self):
        r = admin_get(self.stack, BASE + "/not-a-uuid", self.jar)
        self.assertEqual(r["status"], 400)
        self.assertRegex(r["body"], r'role="alert"')

    def test_get_detail_of_missing_id_renders_404_page(self):
        r = admin_get(self.stack, BASE + "/00000000-0000-0000-0000-000000000000", self.jar)
        self.assertEqual(r["status"], 404)
        self.assertRegex(r["body"], r'role="alert"')

    def test_navigation_includes_self_link_with_aria_current(self):
        ensure_entity(self.stack, ENTITY, self.jar)
        r = admin_get(self.stack, BASE, self.jar)
        self.assertRegex(r["body"], r'aria-current="page"')

    def test_list_view_paginates_with_previous_and_next_navigation(self):
        seed_with(self.stack, ENTITY, {}, self.jar)
        seed_with(self.stack, ENTITY, {}, self.jar)
        seed_with(self.stack, ENTITY, {}, self.jar)
        first = admin_get(self.stack, BASE + "?limit=2&offset=0", self.jar)
        self.assertEqual(first["status"], 200)
        self.assertIn('rel="next"', first["body"])
        self.assertIn("offset=2", first["body"])
        self.assertNotIn('rel="prev"', first["body"])
        second = admin_get(self.stack, BASE + "?limit=2&offset=2", self.jar)
        self.assertEqual(second["status"], 200)
        self.assertIn('rel="prev"', second["body"])

    def test_stored_dangerous_urls_render_as_inert_text_never_as_links(self):
        js_id = seed_with(self.stack, ENTITY, {"url": "javascript:alert(1)"}, self.jar)
        js_html = admin_get(self.stack, BASE + "/" + js_id, self.jar)["body"]
        self.assertIn("javascript:alert(1)", js_html)
        self.assertNotIn('href="javascript:', js_html)

        data_id = seed_with(self.stack, ENTITY, {"url": "data:text/html,x"}, self.jar)
        data_html = admin_get(self.stack, BASE + "/" + data_id, self.jar)["body"]
        self.assertIn("data:text/html,x", data_html)
        self.assertNotIn('href="data:', data_html)

    def test_stored_http_url_renders_as_a_clickable_link(self):
        item_id = seed_with(self.stack, ENTITY, {"url": "https://example.com/profile"}, self.jar)
        html = admin_get(self.stack, BASE + "/" + item_id, self.jar)["body"]
        self.assertIn('href="https://example.com/profile"', html)


if __name__ == "__main__":
    unittest.main()
