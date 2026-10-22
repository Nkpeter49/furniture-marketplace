import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from ai.ollama_client import LocalAIError
from ai.prompts import (
    build_product_fallback,
    build_product_prompt,
    product_output_uses_only_supplied_words,
    build_reply_fallback,
    build_reply_prompt,
    reply_output_uses_only_supplied_words,
    verified_product_result,
)
from marketplace.database import get_db
from marketplace.migrations import apply_migrations
from marketplace.media import MAX_IMAGE_BYTES, prepare_image


class MarketplaceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret-key",
            "DATABASE": str(self.database_path),
        })
        self.client = self.app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.csrf_token = session["csrf_token"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def post_form(self, client, path, data):
        with client.session_transaction() as session:
            token = session.get("csrf_token", "")
        response = None
        try:
            response = client.post(path, data={**data, "csrf_token": token})
            return response
        finally:
            if response is not None:
                input_stream = response.request.environ.get("wsgi.input")
                if input_stream is not None and hasattr(input_stream, "close"):
                    input_stream.close()
            for value in data.values():
                if isinstance(value, tuple) and value and hasattr(value[0], "close"):
                    value[0].close()

    def register(self, client, email, role, display_name=None, password="LongSamplePassword123!"):
        response = self.post_form(client, "/register", {
            "email": email,
            "display_name": display_name or role.title() + " Person",
            "role": role,
            "password": password,
        })
        return response

    def login(self, client, email, password="LongSamplePassword123!"):
        return self.post_form(client, "/login", {"email": email, "password": password})

    def create_admin(self, email="admin@example.test", password="LongAdminPassword123!"):
        runner = self.app.test_cli_runner()
        return runner.invoke(
            args=["init-admin"],
            input=f"{email}\n{password}\n{password}\n",
        )

    def register_seller(self, client, email, approved=False):
        response = self.register(client, email, "seller")
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            if approved:
                get_db().execute(
                    "UPDATE users SET seller_approval = 'approved' WHERE email = ?", (email,)
                )
                get_db().commit()
            user_id = get_db().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
        self.login(client, email)
        return user_id

    @staticmethod
    def image_file(name="upload.png", size=(32, 24), image_format="PNG", color=(25, 80, 40)):
        image = Image.new("RGB", size, color)
        content = BytesIO()
        image.save(content, format=image_format)
        content.seek(0)
        return (content, name)


class ProductFlowTests(MarketplaceTestCase):
    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/marketplace", response.headers["Location"])
        response = self.client.get("/tools/product-description")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Product description", response.data)
        self.assertIn(b"csrf-token", response.data)

    def test_missing_required_item_name_is_rejected(self):
        response = self.client.post(
            "/api/generate",
            json={"task": "product", "fields": {"category": "Sofa"}},
            headers={"X-CSRFToken": self.csrf_token},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Item name", response.json["error"])

    def test_missing_required_category_is_rejected(self):
        response = self.client.post(
            "/api/generate",
            json={"task": "product", "fields": {"item_name": "Oak table"}},
            headers={"X-CSRFToken": self.csrf_token},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Furniture category", response.json["error"])

    def test_prompt_includes_only_supplied_product_facts(self):
        prompt = build_product_prompt({
            "item_name": "Oak table",
            "category": "Dining table",
            "material": "",
            "dimensions": "",
            "price": "",
        })
        self.assertIn("Oak table", prompt)
        self.assertIn("Dining table", prompt)
        self.assertNotIn('"material": ""', prompt)
        self.assertNotIn('"dimensions": ""', prompt)
        self.assertNotIn('"price": ""', prompt)
        self.assertIn("Never infer", prompt)
        self.assertIn("Do not use marketing language", prompt)
        self.assertIn("Omit every missing detail", prompt)

    def test_product_output_gate_allows_seller_words_and_rejects_invented_descriptors(self):
        facts = {"item_name": "Blue chair", "category": "Chair", "material": "Linen", "condition": "Used"}
        self.assertTrue(product_output_uses_only_supplied_words(
            "The Blue chair is a used linen chair.", facts
        ))
        self.assertFalse(product_output_uses_only_supplied_words(
            "The Blue chair is a simple, elegant chair.", facts
        ))

    def test_exact_local_json_fact_echo_is_safely_formatted_and_changed_facts_are_rejected(self):
        facts = {"item_name": "Blue chair", "category": "Chair", "material": "Linen", "condition": "Used", "price": ""}
        exact = '{"item_name":"Blue chair","category":"Chair","material":"Linen","condition":"Used"}'
        self.assertEqual(
            verified_product_result(exact, facts),
            "Used Linen Blue chair.",
        )
        changed = '{"item_name":"Blue chair","category":"Chair","material":"Linen","condition":"New"}'
        self.assertIsNone(verified_product_result(changed, facts))

    @patch("app.generate_text", return_value="Dining table is a table with beech wood.")
    def test_success_returns_ai_result(self, generate_text):
        response = self.client.post("/api/generate", json={
            "task": "product",
            "fields": {"item_name": "Dining table", "category": "Table", "material": "Beech wood"},
        }, headers={"X-CSRFToken": self.csrf_token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["result"], "Dining table is a table with beech wood.")
        generate_text.assert_called_once()

    @patch("app.generate_text", return_value="The Blue chair has a simple, elegant design.")
    def test_unsupported_model_output_uses_labeled_safe_fallback(self, _generate_text):
        response = self.client.post("/api/generate", json={
            "task": "product",
            "fields": {"item_name": "Blue chair", "category": "Chair", "material": "Linen", "condition": "Used"},
        }, headers={"X-CSRFToken": self.csrf_token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "seller_facts_fallback")
        self.assertIn("not AI-generated", response.json["notice"])
        self.assertIn("outside the supplied facts", response.json["notice"])
        self.assertEqual(
            response.json["result"],
            "Used Linen Blue chair.",
        )
        self.assertNotIn("simple", response.json["result"])

    @patch("app.generate_text", side_effect=LocalAIError("offline"))
    def test_local_ai_unavailable_returns_labeled_facts_fallback(self, _generate_text):
        response = self.client.post("/api/generate", json={
            "task": "product",
            "fields": {"item_name": "Dining table", "category": "Table"},
        }, headers={"X-CSRFToken": self.csrf_token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "seller_facts_fallback")
        self.assertIn("not AI-generated", response.json["notice"])
        self.assertIn("could not provide", response.json["notice"])
        self.assertEqual(response.json["result"], "Dining table.")

    def test_deterministic_fallback_omits_blank_fields(self):
        result = build_product_fallback({
            "item_name": "Blue chair",
            "category": "Chair",
            "material": "Linen",
            "condition": "Used",
            "dimensions": "",
            "price": "",
        })
        self.assertEqual(result, "Used Linen Blue chair.")
        self.assertNotIn("Dimensions", result)
        self.assertNotIn("Price", result)

    def test_facts_fallback_uses_natural_sentence_and_currency_with_price(self):
        self.assertEqual(build_product_fallback({
            "item_name": "Dining chair", "category": "Dining chair", "material": "wooden",
            "condition": "Used", "colour": "cream", "price": "200", "currency": "USD",
        }), "Used wooden Dining chair in cream. Price: 200 USD.")


class AuthenticationAndRoleTests(MarketplaceTestCase):
    def test_buyer_registration_stores_a_password_hash_and_login_works(self):
        response = self.register(self.client, "buyer@example.test", "buyer", "Buyer One")
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = get_db().execute("SELECT * FROM users WHERE email = ?", ("buyer@example.test",)).fetchone()
            self.assertNotEqual(user["password_hash"], "LongSamplePassword123!")
            self.assertTrue(check_password_hash(user["password_hash"], "LongSamplePassword123!"))
            self.assertEqual(user["role"], "buyer")
            self.assertIsNone(user["seller_approval"])

        response = self.login(self.client, "buyer@example.test")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"].endswith("/dashboard"), True)
        self.assertEqual(self.client.get("/buyer/dashboard").status_code, 200)

    def test_seller_registration_starts_pending(self):
        self.register(self.client, "seller@example.test", "seller")
        with self.app.app_context():
            seller = get_db().execute("SELECT role, seller_approval FROM users WHERE email = ?", ("seller@example.test",)).fetchone()
        self.assertEqual(seller["role"], "seller")
        self.assertEqual(seller["seller_approval"], "pending")
        self.login(self.client, "seller@example.test")
        dashboard = self.client.get("/seller/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"waiting for administrator approval", dashboard.data)

    def test_registration_cannot_forge_admin_role(self):
        response = self.register(self.client, "forged@example.test", "admin")
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'").fetchone()["n"]
        self.assertEqual(count, 0)

    def test_role_checks_deny_buyer_seller_and_admin_pages(self):
        self.register(self.client, "buyer@example.test", "buyer")
        self.login(self.client, "buyer@example.test")
        self.assertEqual(self.client.get("/seller/dashboard").status_code, 403)
        self.assertEqual(self.client.get("/admin/users").status_code, 403)

    def test_state_changing_route_requires_csrf_token(self):
        response = self.client.post("/register", data={
            "email": "buyer@example.test",
            "display_name": "Buyer",
            "role": "buyer",
            "password": "LongSamplePassword123!",
        })
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        self.assertEqual(count, 0)

    def test_account_profile_and_password_change_are_owner_scoped(self):
        self.register(self.client, "buyer@example.test", "buyer")
        self.login(self.client, "buyer@example.test")
        response = self.post_form(self.client, "/account", {
            "display_name": "Updated Buyer",
            "email": "buyer@example.test",
        })
        self.assertEqual(response.status_code, 302)
        response = self.post_form(self.client, "/account/password", {
            "current_password": "LongSamplePassword123!",
            "new_password": "AnEvenLongerPassword123!",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/buyer/dashboard").status_code, 302)
        response = self.login(self.client, "buyer@example.test", "AnEvenLongerPassword123!")
        self.assertEqual(response.status_code, 302)

    def test_admin_cli_creates_only_first_admin_with_hashed_password(self):
        result = self.create_admin()
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            admin = get_db().execute("SELECT * FROM users WHERE role = 'admin'").fetchone()
            self.assertNotEqual(admin["password_hash"], "LongAdminPassword123!")
            self.assertTrue(check_password_hash(admin["password_hash"], "LongAdminPassword123!"))
        second = self.app.test_cli_runner().invoke(args=["init-admin"])
        self.assertNotEqual(second.exit_code, 0)
        self.assertIn("already exists", second.output)

    def test_admin_approves_and_suspends_seller_without_exposing_hash(self):
        self.register(self.client, "seller@example.test", "seller")
        self.create_admin()
        admin_client = self.app.test_client()
        admin_client.get("/login")
        self.login(admin_client, "admin@example.test", "LongAdminPassword123!")
        page = admin_client.get("/admin/users")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"seller@example.test", page.data)
        self.assertNotIn(b"password_hash", page.data)
        response = self.post_form(admin_client, "/admin/sellers/1/approve", {})
        self.assertEqual(response.status_code, 302)
        response = self.post_form(admin_client, "/admin/users/1/status", {
            "account_status": "suspended", "confirm_suspend": "yes",
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            seller = get_db().execute("SELECT seller_approval, account_status FROM users WHERE id = 1").fetchone()
        self.assertEqual(seller["seller_approval"], "approved")
        self.assertEqual(seller["account_status"], "suspended")

    def test_suspended_user_cannot_log_in_and_an_active_session_is_revoked(self):
        self.register(self.client, "buyer@example.test", "buyer")
        self.login(self.client, "buyer@example.test")
        with self.app.app_context():
            get_db().execute("UPDATE users SET account_status = 'suspended' WHERE email = ?", ("buyer@example.test",))
            get_db().commit()
        response = self.client.get("/buyer/dashboard")
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

        login_client = self.app.test_client()
        login_client.get("/login")
        response = self.login(login_client, "buyer@example.test")
        self.assertEqual(response.status_code, 400)


class ProfileAndListingTests(MarketplaceTestCase):
    def test_seller_can_set_optional_quantity_and_invalid_quantity_is_rejected(self):
        seller_id = self.register_seller(self.client, "seller@example.test", approved=True)
        created = self.post_form(self.client, "/seller/listings/new", {
            "item_name": "Blue chair", "category": "Chair", "quantity": "5",
            "availability": "available", "status": "published",
        })
        self.assertEqual(created.status_code, 302)
        with self.app.app_context():
            row = get_db().execute("SELECT id, quantity FROM listings WHERE seller_id = ?", (seller_id,)).fetchone()
        self.assertEqual(row["quantity"], 5)
        self.create_admin()
        admin = self.app.test_client(); admin.get("/")
        self.login(admin, "admin@example.test", "LongAdminPassword123!")
        self.assertEqual(self.post_form(admin, f"/admin/listings/{row['id']}/review", {"action": "approve"}).status_code, 302)
        buyer = self.app.test_client(); buyer.get("/")
        self.register(buyer, "buyer@example.test", "buyer"); self.login(buyer, "buyer@example.test")
        self.assertIn(b"quantity 5 reported", buyer.get(f"/listings/{row['id']}").data)
        invalid = self.post_form(self.client, "/seller/listings/new", {
            "item_name": "Empty chair", "category": "Chair", "quantity": "0",
            "availability": "available", "status": "published",
        })
        self.assertEqual(invalid.status_code, 400)
        self.assertIn(b"quantity of zero cannot be marked available", invalid.data.lower())
        with self.app.app_context():
            with self.assertRaises(sqlite3.IntegrityError):
                get_db().execute(
                    "INSERT INTO listings (seller_id,item_name,category,quantity) VALUES (?,?,?,-1)",
                    (seller_id, "Bad quantity", "Chair"),
                )

    def test_buyer_can_edit_private_profile_and_photo(self):
        self.register(self.client, "buyer@example.test", "buyer", "Buyer One")
        self.login(self.client, "buyer@example.test")
        response = self.post_form(self.client, "/account", {
            "display_name": "Buyer Updated", "email": "buyer@example.test",
            "bio": "I like vintage furniture.", "profile_photo": self.image_file(),
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = get_db().execute(
                "SELECT id, bio, profile_image, password_hash FROM users WHERE email = ?",
                ("buyer@example.test",),
            ).fetchone()
            image_name = user["profile_image"]
            self.assertEqual(user["bio"], "I like vintage furniture.")
            self.assertTrue(user["password_hash"])
        self.assertRegex(image_name, r"^[0-9a-f]{32}\.jpg$")
        photo = self.client.get("/account/profile-photo")
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo.mimetype, "image/jpeg")
        photo.close()

        other = self.app.test_client()
        self.assertEqual(other.get("/account/profile-photo").status_code, 302)
        public_seller = self.client.get("/sellers/9999")
        self.assertEqual(public_seller.status_code, 404)
        self.assertNotIn(b"I like vintage furniture", public_seller.data)

    def test_buyer_profile_photo_route_is_not_available_to_other_roles(self):
        self.register_seller(self.client, "seller@example.test", approved=True)
        self.assertEqual(self.client.get("/account/profile-photo").status_code, 403)

    def test_seller_business_profile_is_private_by_default_and_contact_is_opt_in(self):
        seller_id = self.register_seller(self.client, "seller@example.test", approved=True)
        response = self.post_form(self.client, "/seller/profile", {
            "business_name": "Northside Furniture",
            "bio": "A family furniture shop.",
            "specialties": "Tables and chairs",
            "contact_number": "+1 202 555 0101",
            "business_photo": self.image_file("seller.webp", image_format="WEBP"),
            "cover_photo": self.image_file("cover.png"),
        })
        self.assertEqual(response.status_code, 302)
        public = self.client.get(f"/sellers/{seller_id}")
        self.assertEqual(public.status_code, 200)
        self.assertIn(b"Northside Furniture", public.data)
        self.assertIn(b"A family furniture shop", public.data)
        self.assertNotIn(b"seller@example.test", public.data)
        self.assertNotIn(b"2025550101", public.data)
        self.assertNotIn(b"password_hash", public.data)
        self.assertNotIn(b"session", public.data.lower())

        response = self.post_form(self.client, "/seller/profile", {
            "business_name": "Northside Furniture",
            "bio": "A family furniture shop.",
            "specialties": "Tables and chairs",
            "contact_number": "+1 202 555 0101",
            "publish_contact": "on",
        })
        self.assertEqual(response.status_code, 302)
        public = self.client.get(f"/sellers/{seller_id}")
        self.assertIn(b"https://wa.me/12025550101", public.data)
        self.assertIn(b"opens WhatsApp", public.data)
        self.assertNotIn(b"seller@example.test", public.data)

    def test_seller_profile_edit_requires_approval_and_public_page_hides_pending_seller(self):
        seller_id = self.register_seller(self.client, "pending@example.test", approved=False)
        self.assertEqual(self.client.get("/seller/profile").status_code, 403)
        self.assertEqual(self.client.get("/seller/listings").status_code, 403)
        self.assertEqual(self.client.get(f"/sellers/{seller_id}").status_code, 404)

    def test_buyer_cannot_open_seller_profile_or_listing_management(self):
        self.register(self.client, "buyer@example.test", "buyer")
        self.login(self.client, "buyer@example.test")
        self.assertEqual(self.client.get("/seller/profile").status_code, 403)
        self.assertEqual(self.client.get("/seller/listings").status_code, 403)
        self.assertEqual(self.client.get("/seller/listings/new").status_code, 403)

    def test_approved_seller_can_create_edit_publish_and_remove_own_listing(self):
        seller_id = self.register_seller(self.client, "seller@example.test", approved=True)
        listing = {
            "item_name": "Oak chair", "category": "Chair", "material": "Oak",
            "condition": "Used", "dimensions": "80 x 45 cm", "price": "125.00",
            "currency": "usd", "colour": "Natural", "description": "Oak chair in used condition.",
            "additional_details": "", "availability": "available", "status": "published",
            "photos": self.image_file("../../unsafe.png"),
        }
        response = self.post_form(self.client, "/seller/listings/new", listing)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            row = get_db().execute("SELECT * FROM listings WHERE seller_id = ?", (seller_id,)).fetchone()
            image = get_db().execute(
                "SELECT id, filename FROM listing_images WHERE listing_id = ?", (row["id"],)
            ).fetchone()
        self.assertEqual(row["status"], "published")
        self.assertEqual(row["review_status"], "pending")
        self.assertEqual(row["currency"], "USD")
        self.assertRegex(image["filename"], r"^[0-9a-f]{32}\.jpg$")
        self.assertNotIn("unsafe", image["filename"])

        self.assertNotIn(b"Oak chair", self.client.get(f"/sellers/{seller_id}").data)
        self.assertEqual(self.client.get(f"/listings/{row['id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/media/listing/{image['id']}").status_code, 404)
        self.create_admin()
        admin = self.app.test_client()
        admin.get("/")
        self.login(admin, "admin@example.test", "LongAdminPassword123!")
        self.assertEqual(admin.get("/admin/listings").status_code, 200)
        self.assertEqual(self.post_form(admin, f"/admin/listings/{row['id']}/review", {"action": "approve"}).status_code, 302)
        public = self.client.get(f"/sellers/{seller_id}")
        self.assertIn(b"Oak chair", public.data)
        self.assertIn(b"125.00 USD", public.data)
        image_response = self.client.get(f"/media/listing/{image['id']}")
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.mimetype, "image/jpeg")
        image_response.close()

        listing_id = row["id"]
        updated = {key: value for key, value in listing.items() if key != "photos"}
        updated["availability"] = "unavailable"
        response = self.post_form(self.client, f"/seller/listings/{listing_id}/edit", updated)
        self.assertEqual(response.status_code, 302)
        public = self.client.get(f"/sellers/{seller_id}")
        self.assertIn(b"Seller reported: unavailable", public.data)

        self.assertEqual(self.post_form(self.client, f"/seller/listings/{listing_id}/remove", {}).status_code, 400)
        response = self.post_form(self.client, f"/seller/listings/{listing_id}/remove", {"confirm_remove": "yes"})
        self.assertEqual(response.status_code, 302)
        public = self.client.get(f"/sellers/{seller_id}")
        self.assertNotIn(b"Oak chair", public.data)
        self.assertEqual(self.client.get(f"/media/listing/{image['id']}").status_code, 404)
        with self.app.app_context():
            saved = get_db().execute("SELECT status FROM listings WHERE id = ?", (listing_id,)).fetchone()
        self.assertEqual(saved["status"], "removed")

    def test_seller_cannot_edit_or_remove_another_sellers_listing(self):
        first = self.register_seller(self.client, "first@example.test", approved=True)
        response = self.post_form(self.client, "/seller/listings/new", {
            "item_name": "First table", "category": "Table", "status": "draft",
            "availability": "available",
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            listing_id = get_db().execute("SELECT id FROM listings WHERE seller_id = ?", (first,)).fetchone()["id"]
        other = self.app.test_client()
        other.get("/")
        self.register_seller(other, "second@example.test", approved=True)
        self.assertEqual(other.get(f"/seller/listings/{listing_id}/edit").status_code, 404)
        self.assertEqual(self.post_form(other, f"/seller/listings/{listing_id}/remove", {}).status_code, 404)

    def test_invalid_spoofed_oversized_and_oversized_dimension_images_are_rejected(self):
        self.register(self.client, "buyer@example.test", "buyer")
        self.login(self.client, "buyer@example.test")

        response = self.post_form(self.client, "/account", {
            "display_name": "Buyer Person", "email": "buyer@example.test", "bio": "Should not save",
            "profile_photo": (BytesIO(b"not an image"), "fake.png"),
        })
        self.assertEqual(response.status_code, 400)

        response = self.post_form(self.client, "/account", {
            "display_name": "Buyer Person", "email": "buyer@example.test", "bio": "Too big",
            "profile_photo": (BytesIO(b"x" * (MAX_IMAGE_BYTES + 1)), "large.png"),
        })
        self.assertEqual(response.status_code, 400)

        response = self.post_form(self.client, "/account", {
            "display_name": "Buyer Person", "email": "buyer@example.test", "bio": "Too many pixels",
            "profile_photo": self.image_file("large-dimensions.png", size=(6001, 1)),
        })
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            user = get_db().execute("SELECT bio, profile_image FROM users WHERE email = ?", ("buyer@example.test",)).fetchone()
        self.assertEqual(user["bio"], "")
        self.assertIsNone(user["profile_image"])

    def test_valid_large_image_is_downscaled_to_1600_pixels_on_longest_side(self):
        source = self.image_file("large.jpg", size=(2400, 1200), image_format="JPEG")
        source[0].filename = source[1]
        encoded, suffix = prepare_image(source[0])
        with Image.open(BytesIO(encoded)) as stored:
            self.assertEqual(suffix, ".jpg")
            self.assertEqual(stored.size, (1600, 800))

    def test_missing_csrf_token_blocks_profile_and_listing_changes(self):
        self.register_seller(self.client, "seller@example.test", approved=True)
        response = self.client.post("/seller/profile", data={"business_name": "Changed"})
        self.assertEqual(response.status_code, 400)
        response.request.environ["wsgi.input"].close()
        response.close()
        response = self.client.post("/seller/listings/new", data={"item_name": "Chair"})
        self.assertEqual(response.status_code, 400)
        response.request.environ["wsgi.input"].close()
        response.close()


class MigrationSafetyTests(unittest.TestCase):
    def test_profile_migration_is_repeatable_and_preserves_existing_accounts(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "stage1.sqlite3"
            db = sqlite3.connect(db_path)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            schema = Path(__file__).resolve().parents[1] / "schema.sql"
            db.executescript(schema.read_text(encoding="utf-8"))
            buyer_hash = generate_password_hash("BuyerPassword123!")
            seller_hash = generate_password_hash("SellerPassword123!")
            admin_hash = generate_password_hash("AdminPassword123!")
            db.executemany(
                """INSERT INTO users (id, email, display_name, password_hash, role, account_status, seller_approval)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (12, "buyer@example.test", "Buyer", buyer_hash, "buyer", "active", None),
                    (21, "seller@example.test", "Seller Shop", seller_hash, "seller", "active", "approved"),
                    (33, "admin@example.test", "Administrator", admin_hash, "admin", "active", None),
                ],
            )
            db.commit()
            before = [tuple(row) for row in db.execute(
                "SELECT id, email, display_name, password_hash, role, account_status, seller_approval FROM users ORDER BY id"
            )]

            apply_migrations(db)
            apply_migrations(db)

            after = [tuple(row) for row in db.execute(
                "SELECT id, email, display_name, password_hash, role, account_status, seller_approval FROM users ORDER BY id"
            )]
            self.assertEqual(after, before)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 1").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 2").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 3").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 4").fetchone()[0], 1)
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'support_tickets'").fetchone())
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'user_reports'").fetchone())
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'privacy_requests'").fetchone())
            for table in ("favorites", "conversations", "messages"):
                self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone())
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE type = 'trigger' AND name = 'messages_author_must_participate'").fetchone())
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'listing_moderation_history'").fetchone())
            self.assertTrue(any(row["name"] == "quantity" for row in db.execute("PRAGMA table_info(listings)")))
            profile = db.execute("SELECT business_name FROM seller_profiles WHERE user_id = 21").fetchone()
            self.assertEqual(profile["business_name"], "Seller Shop")
            db.close()


class ListingApprovalTests(MarketplaceTestCase):
    def _listing(self):
        seller_id = self.register_seller(self.client, "review-seller@example.test", approved=True)
        response = self.post_form(self.client, "/seller/listings/new", {
            "item_name": "Review chair", "category": "Chair", "description": "Wooden chair.",
            "price": "200", "currency": "USD", "status": "published", "photos": self.image_file(),
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            listing_id = get_db().execute("SELECT id FROM listings WHERE seller_id = ?", (seller_id,)).fetchone()[0]
            image_id = get_db().execute("SELECT id FROM listing_images WHERE listing_id = ?", (listing_id,)).fetchone()[0]
        return seller_id, listing_id, image_id

    def _admin(self):
        self.create_admin()
        client = self.app.test_client()
        client.get("/")
        self.login(client, "admin@example.test", "LongAdminPassword123!")
        return client

    def test_pending_listing_is_invisible_and_approval_makes_it_visible(self):
        seller_id, listing_id, image_id = self._listing()
        anonymous = self.app.test_client()
        self.assertNotIn(b"Review chair", anonymous.get("/marketplace?q=Review").data)
        self.assertEqual(anonymous.get(f"/listings/{listing_id}").status_code, 404)
        self.assertEqual(anonymous.get(f"/media/listing/{image_id}").status_code, 404)
        self.assertNotIn(b"Review chair", anonymous.get(f"/sellers/{seller_id}").data)
        self.assertIn(b"Pending review", self.client.get("/seller/listings").data)
        admin = self._admin()
        self.assertIn(b"Review chair", admin.get("/admin/listings").data)
        self.assertEqual(self.post_form(admin, f"/admin/listings/{listing_id}/review", {"action": "approve"}).status_code, 302)
        self.assertEqual(anonymous.get(f"/listings/{listing_id}").status_code, 200)
        approved_image = anonymous.get(f"/media/listing/{image_id}")
        self.assertEqual(approved_image.status_code, 200)
        approved_image.close()

    def test_rejection_hides_listing_and_shows_reason_to_seller(self):
        _seller, listing_id, _image = self._listing()
        admin = self._admin()
        self.assertEqual(self.post_form(admin, f"/admin/listings/{listing_id}/review", {
            "action": "reject", "reason": "Please replace this photo."
        }).status_code, 302)
        self.assertEqual(self.client.get(f"/listings/{listing_id}").status_code, 404)
        page = self.client.get("/seller/listings")
        self.assertIn(b"Rejected", page.data)
        self.assertIn(b"Please replace this photo.", page.data)

    def test_non_admin_denied_and_description_edit_requires_rereview(self):
        _seller, listing_id, image_id = self._listing()
        self.assertEqual(self.client.get("/admin/listings").status_code, 403)
        admin = self._admin()
        self.assertEqual(self.post_form(admin, f"/admin/listings/{listing_id}/review", {"action": "approve"}).status_code, 302)
        edit = self.post_form(self.client, f"/seller/listings/{listing_id}/edit", {
            "item_name": "Review chair", "category": "Chair", "description": "Updated wooden chair.",
            "price": "200", "currency": "USD", "status": "published",
        })
        self.assertEqual(edit.status_code, 302)
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get(f"/media/listing/{image_id}").status_code, 404)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT review_status FROM listings WHERE id = ?", (listing_id,)).fetchone()[0], "pending")


class StorefrontAndConversationTests(MarketplaceTestCase):
    def setUp(self):
        super().setUp()
        self.seller_client = self.app.test_client()
        self.seller_client.get("/")
        self.seller_id = self.register_seller(self.seller_client, "furniture@example.test", approved=True)
        with self.app.app_context():
            rows = [
                ("Blue chair", "Chair", "Linen", "Used", "1200", "available", "published"),
                ("Oak dining table", "Table", "Oak", "New", "5000", "available", "published"),
                ("Storage cabinet", "Storage", "Pine", "Used", "", "unavailable", "published"),
                ("Private draft", "Chair", "Wood", "Used", "200", "available", "draft"),
            ]
            self.listing_ids = {}
            for name, category, material, condition, price, availability, status in rows:
                cursor = get_db().execute(
                    """INSERT INTO listings (seller_id, item_name, category, material, condition, price, currency, availability, status, review_status)
                       VALUES (?, ?, ?, ?, ?, ?, 'KES', ?, ?, CASE WHEN ? = 'published' THEN 'approved' ELSE 'pending' END)""",
                    (self.seller_id, name, category, material, condition, price, availability, status, status),
                )
                self.listing_ids[name] = cursor.lastrowid
            get_db().commit()
        self.register(self.client, "buyer-one@example.test", "buyer")
        self.login(self.client, "buyer-one@example.test")

    def test_browse_search_combined_filters_and_visibility_rules(self):
        response = self.client.get("/marketplace?q=linen&category=Chair&condition=Used&availability=available&min_price=1000&max_price=1500")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Blue chair", response.data)
        self.assertNotIn(b"Oak dining table", response.data)
        self.assertNotIn(b"Private draft", response.data)
        self.assertEqual(self.client.get("/marketplace?availability=unavailable").status_code, 200)
        unavailable = self.client.get("/marketplace?availability=unavailable")
        self.assertIn(b"Storage cabinet", unavailable.data)
        self.assertEqual(self.client.get("/marketplace?min_price=not-a-number").status_code, 200)
        self.assertIn(b"valid non-negative price range", self.client.get("/marketplace?min_price=not-a-number").data)
        self.create_admin()
        admin = self.app.test_client()
        admin.get("/login")
        self.login(admin, "admin@example.test", "LongAdminPassword123!")
        with self.app.app_context():
            get_db().execute(
                "INSERT INTO listing_moderation (listing_id, moderator_id, reason) VALUES (?, ?, ?)",
                (self.listing_ids["Oak dining table"], get_db().execute("SELECT id FROM users WHERE role='admin'").fetchone()[0], "Review hold"),
            )
            get_db().commit()
        self.assertEqual(self.client.get(f"/listings/{self.listing_ids['Private draft']}").status_code, 404)
        self.assertEqual(self.client.get(f"/listings/{self.listing_ids['Oak dining table']}").status_code, 404)
        self.assertEqual(self.client.get(f"/listings/{self.listing_ids['Blue chair']}").status_code, 200)

    def test_favorites_are_buyer_owned_and_toggle_with_csrf(self):
        listing_id = self.listing_ids["Blue chair"]
        saved = self.post_form(self.client, f"/listings/{listing_id}/favorite", {})
        self.assertEqual(saved.status_code, 302)
        self.assertIn(b"Blue chair", self.client.get("/favorites").data)
        second = self.app.test_client()
        second.get("/")
        self.register(second, "buyer-two@example.test", "buyer")
        self.login(second, "buyer-two@example.test")
        self.assertNotIn(b"Blue chair", second.get("/favorites").data)
        self.assertEqual(self.post_form(second, f"/listings/{listing_id}/favorite", {}).status_code, 302)
        self.assertIn(b"Blue chair", second.get("/favorites").data)
        self.assertEqual(self.seller_client.get("/favorites").status_code, 403)
        no_csrf = self.client.post(f"/listings/{listing_id}/favorite")
        self.assertEqual(no_csrf.status_code, 400)

    def _start_conversation(self):
        response = self.post_form(self.client, f"/listings/{self.listing_ids['Blue chair']}/inquire", {
            "body": "Is the chair still available? Please confirm."
        })
        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        conversation_id = int(location.rsplit("/", 1)[1])
        return conversation_id, location

    def test_private_messages_only_participants_can_read_or_send(self):
        conversation_id, location = self._start_conversation()
        buyer_view = self.client.get(location)
        self.assertEqual(buyer_view.status_code, 200)
        self.assertIn(b"Is the chair still available?", buyer_view.data)
        outsider = self.app.test_client()
        outsider.get("/")
        self.register(outsider, "outsider@example.test", "buyer")
        self.login(outsider, "outsider@example.test")
        self.assertEqual(outsider.get(location).status_code, 404)
        self.assertEqual(self.post_form(outsider, location, {"body": "Trying to intrude"}).status_code, 404)
        self.assertEqual(self.seller_client.get(location).status_code, 200)
        seller_reply = self.post_form(self.seller_client, location, {"body": "I will check and confirm."})
        self.assertEqual(seller_reply.status_code, 302)
        self.assertIn(b"I will check and confirm", self.client.get(location).data)
        self.create_admin()
        admin = self.app.test_client()
        admin.get("/login")
        self.login(admin, "admin@example.test", "LongAdminPassword123!")
        self.assertEqual(admin.get(location).status_code, 404)
        admin_overview = admin.get("/admin/dashboard")
        self.assertEqual(admin_overview.status_code, 200)
        self.assertNotIn(b"Is the chair still available?", admin_overview.data)
        other_seller = self.app.test_client()
        other_seller.get("/")
        self.register_seller(other_seller, "other-seller@example.test", approved=True)
        self.assertEqual(other_seller.get(location).status_code, 404)
        self.assertNotIn(b"Is the chair still available?", other_seller.get("/conversations").data)
        with self.app.app_context():
            foreign = get_db().execute(
                "INSERT INTO users (email, display_name, password_hash, role) VALUES (?, ?, ?, 'buyer')",
                ("nonparticipant@example.test", "Nonparticipant", generate_password_hash("SafePassword123!")),
            ).lastrowid
            with self.assertRaises(sqlite3.IntegrityError):
                get_db().execute(
                    "INSERT INTO messages (conversation_id, author_id, body) VALUES (?, ?, ?)",
                    (conversation_id, foreign, "database should reject this"),
                )

    @patch("marketplace.storefront.generate_text")
    def test_local_reply_draft_is_safe_and_never_automatically_sent(self, mocked_generate):
        conversation_id, location = self._start_conversation()
        mocked_generate.return_value = "Thank you for your question about Blue chair. I will confirm the details."
        response = self.seller_client.post(
            f"/api/conversations/{conversation_id}/reply-draft",
            json={"policies": {"delivery": "", "warranty": "", "returns": ""}},
            headers={"X-CSRFToken": self._csrf_for(self.seller_client)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "local_ai")
        self.assertIn("confirm", response.json["result"])
        self.assertNotIn("furniture@example.test", mocked_generate.call_args.args[0])
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (conversation_id,)).fetchone()[0], 1)

        mocked_generate.return_value = "This premium chair is excellent, available, and delivery is included."
        unsafe = self.seller_client.post(
            f"/api/conversations/{conversation_id}/reply-draft", json={"policies": {}},
            headers={"X-CSRFToken": self._csrf_for(self.seller_client)},
        )
        self.assertEqual(unsafe.status_code, 200)
        self.assertEqual(unsafe.json["source"], "safe_fallback")
        self.assertIn("not AI-generated", unsafe.json["notice"])
        self.assertIn("Blue chair", unsafe.json["result"])
        self.assertEqual(self.seller_client.post(
            f"/api/conversations/{conversation_id}/reply-draft", json={"policies": {"delivery": "x" * 601}},
            headers={"X-CSRFToken": self._csrf_for(self.seller_client)},
        ).status_code, 400)
        self.assertEqual(self.client.post(
            f"/api/conversations/{conversation_id}/reply-draft", json={"policies": {}},
            headers={"X-CSRFToken": self._csrf_for(self.client)},
        ).status_code, 403)

    @patch("marketplace.storefront.generate_text", side_effect=LocalAIError("offline"))
    def test_unavailable_local_reply_model_returns_deterministic_fallback(self, _mocked_generate):
        conversation_id, _location = self._start_conversation()
        response = self.seller_client.post(
            f"/api/conversations/{conversation_id}/reply-draft", json={"policies": {}},
            headers={"X-CSRFToken": self._csrf_for(self.seller_client)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["source"], "safe_fallback")
        self.assertIn("details related to your question", response.json["result"])

    def test_reply_safety_gate_rejects_invented_features_and_business_promises(self):
        listing = {"item_name": "Blue chair", "category": "Chair", "material": "Linen", "availability": "available"}
        question = "Does it have storage, and can you deliver tomorrow?"
        self.assertTrue(reply_output_uses_only_supplied_words(
            "Thank you for your question about Blue chair. I will confirm the details.", listing, question, {}
        ))
        self.assertFalse(reply_output_uses_only_supplied_words(
            "The Blue chair has storage and is excellent.", listing, question, {}
        ))
        self.assertFalse(reply_output_uses_only_supplied_words(
            "Delivery is included and it will arrive tomorrow.", listing, question, {}
        ))
        self.assertIn("Blue chair", build_reply_fallback(listing, question))

    @staticmethod
    def _csrf_for(client):
        with client.session_transaction() as session:
            return session["csrf_token"]


class SupportPrivacyAndPolicyTests(MarketplaceTestCase):
    def test_help_and_policy_pages_are_searchable_and_draft_placeholders_are_visible(self):
        response = self.client.get("/help?q=photo")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Photo upload requirements", response.data)
        self.assertNotIn(b"Seller approval", response.data)
        index = self.client.get("/policies")
        self.assertEqual(index.status_code, 200)
        self.assertIn(b"DRAFT ONLY", index.data)
        from marketplace.policies import POLICIES
        for slug in POLICIES:
            page = self.client.get(f"/policies/{slug}")
            self.assertEqual(page.status_code, 200, slug)
            self.assertIn(b"DRAFT", page.data)
        self.assertIn(b"[LEGAL OPERATOR NAME]", self.client.get("/policies/terms").data)
        self.assertNotIn(b"@example.com", index.data)

    def test_support_ticket_is_private_and_admin_can_assign_reply_and_resolve(self):
        self.register(self.client, "owner@example.test", "buyer")
        self.login(self.client, "owner@example.test")
        created = self.post_form(self.client, "/support", {
            "category": "listing", "subject": "Question about my listing", 
            "description": "I need help understanding the listing controls.",
            "listing_reference": "listing-42",
        })
        self.assertEqual(created.status_code, 302)
        ticket_location = created.headers["Location"]
        ticket_id = int(ticket_location.rsplit("/", 1)[1])
        self.assertEqual(self.client.get(ticket_location).status_code, 200)
        self.assertIn(b"listing-42", self.client.get(ticket_location).data)

        other = self.app.test_client()
        other.get("/")
        self.register(other, "other@example.test", "buyer")
        self.login(other, "other@example.test")
        self.assertEqual(other.get(ticket_location).status_code, 404)
        self.assertNotIn(b"Question about my listing", other.get("/support/requests").data)
        self.assertEqual(other.get("/admin/support").status_code, 403)

        self.create_admin()
        admin = self.app.test_client()
        admin.get("/login")
        self.login(admin, "admin@example.test", "LongAdminPassword123!")
        self.assertEqual(admin.get("/admin/support").status_code, 200)
        assigned = self.post_form(admin, f"/admin/support/{ticket_id}", {"action": "assign"})
        self.assertEqual(assigned.status_code, 302)
        replied = self.post_form(admin, f"/admin/support/{ticket_id}", {
            "action": "reply", "body": "Please open My listings and choose Edit."
        })
        self.assertEqual(replied.status_code, 302)
        self.assertIn(b"Please open My listings", self.client.get(ticket_location).data)
        with self.app.app_context():
            status = get_db().execute("SELECT status, assigned_admin_id FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
        self.assertEqual(status["status"], "waiting_for_user")
        self.assertIsNotNone(status["assigned_admin_id"])
        self.assertEqual(self.post_form(admin, f"/admin/support/{ticket_id}", {
            "action": "status", "status": "resolved"
        }).status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT status FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()[0], "resolved")

    def test_support_validation_csrf_and_rate_limit(self):
        self.register(self.client, "buyer@example.test", "buyer")
        self.login(self.client, "buyer@example.test")
        invalid = self.post_form(self.client, "/support", {
            "category": "unknown", "subject": "x", "description": "short",
        })
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.client.post("/support", data={
            "category": "other", "subject": "A subject", "description": "A sufficiently long help request."
        }).status_code, 400)
        self.app.config["RATE_LIMITS"] = {"support.create_ticket": (2, 3600)}
        data = {"category": "other", "subject": "One request", "description": "This is enough detail for a support request."}
        self.assertEqual(self.post_form(self.client, "/support", data).status_code, 302)
        limited = self.post_form(self.client, "/support", data)
        self.assertEqual(limited.status_code, 429)
        self.assertIn(b"Too many requests", limited.data)

    def test_reports_are_private_and_admin_can_review_copyright_complaint(self):
        seller_id = self.register_seller(self.client, "seller@example.test", approved=True)
        with self.app.app_context():
            cursor = get_db().execute(
                """INSERT INTO listings (seller_id, item_name, category, status, review_status)
                   VALUES (?, 'Oak table', 'Table', 'published', 'approved')""", (seller_id,),
            )
            listing_id = cursor.lastrowid
            get_db().commit()
        reporter = self.app.test_client()
        reporter.get("/")
        self.register(reporter, "reporter@example.test", "buyer")
        self.login(reporter, "reporter@example.test")
        response = self.post_form(reporter, f"/report/listing/{listing_id}", {
            "reason": "copyright_trademark",
            "details": "The photo appears to be my protected work; I can provide the original source.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(reporter.get("/reports/mine").status_code, 200)
        self.assertIn(b"copyright", reporter.get("/reports/mine").data.lower())
        self.assertNotIn(b"reporter@example.test", self.client.get(f"/sellers/{seller_id}").data)

        other = self.app.test_client()
        other.get("/")
        self.register(other, "other@example.test", "buyer")
        self.login(other, "other@example.test")
        self.assertNotIn(b"protected work", other.get("/reports/mine").data)
        self.assertEqual(other.get("/admin/reports").status_code, 403)

        self.create_admin()
        admin = self.app.test_client()
        admin.get("/login")
        self.login(admin, "admin@example.test", "LongAdminPassword123!")
        queue = admin.get("/admin/reports")
        self.assertEqual(queue.status_code, 200)
        report_id = None
        with self.app.app_context():
            report_id = get_db().execute("SELECT id FROM user_reports").fetchone()["id"]
        detail = admin.get(f"/admin/reports/{report_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"protected work", detail.data)
        reviewed = self.post_form(admin, f"/admin/reports/{report_id}", {
            "status": "in_review", "admin_note": "Reviewing source and permission evidence."
        })
        self.assertEqual(reviewed.status_code, 302)
        with self.app.app_context():
            row = get_db().execute("SELECT status, reviewer_id FROM user_reports WHERE id = ?", (report_id,)).fetchone()
        self.assertEqual(row["status"], "in_review")
        self.assertIsNotNone(row["reviewer_id"])
        restricted = self.post_form(admin, f"/admin/reports/{report_id}", {
            "status": "action_taken", "content_action": "hide_listing",
            "admin_note": "Verified rights evidence; temporarily hide while the complaint is resolved.",
        })
        self.assertEqual(restricted.status_code, 302)
        self.assertNotIn(b"Oak table", self.client.get(f"/sellers/{seller_id}").data)
        self.assertEqual(reporter.get(f"/report/listing/{listing_id}").status_code, 404)
        seller_listings = self.client.get("/seller/listings")
        self.assertIn(b"Temporarily hidden during administrator review", seller_listings.data)
        blocked_republish = self.post_form(self.client, f"/seller/listings/{listing_id}/edit", {
            "item_name": "Oak table", "category": "Table", "status": "published",
            "availability": "available",
        })
        self.assertEqual(blocked_republish.status_code, 400)
        with self.app.app_context():
            event = get_db().execute("SELECT action FROM moderation_events WHERE report_id = ?", (report_id,)).fetchone()
        self.assertEqual(event["action"], "hide_listing")
        restore = self.post_form(admin, f"/admin/reports/{report_id}", {
            "status": "action_taken", "content_action": "restore_listing",
            "admin_note": "Review completed; restore the published listing.",
        })
        self.assertEqual(restore.status_code, 302)
        self.assertIn(b"Oak table", self.client.get(f"/sellers/{seller_id}").data)
        with self.app.app_context():
            self.assertEqual(get_db().execute(
                "SELECT action FROM listing_moderation_history WHERE report_id = ? ORDER BY id", (report_id,)
            ).fetchall()[-1]["action"], "restore")

        second_seller_client = self.app.test_client()
        second_seller_client.get("/")
        second_seller_id = self.register_seller(second_seller_client, "second-seller@example.test", approved=True)
        seller_report = self.post_form(reporter, f"/report/user/{second_seller_id}", {
            "reason": "fraud", "details": "The seller appears to be impersonating a local business."
        })
        self.assertEqual(seller_report.status_code, 302)
        with self.app.app_context():
            seller_report_id = get_db().execute(
                "SELECT id FROM user_reports WHERE target_type = 'user' AND target_id = ?", (second_seller_id,)
            ).fetchone()["id"]
        suspended = self.post_form(admin, f"/admin/reports/{seller_report_id}", {
            "status": "action_taken", "content_action": "suspend_seller",
            "admin_note": "Identity evidence supported suspension pending appeal.",
        })
        self.assertEqual(suspended.status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT account_status FROM users WHERE id = ?", (second_seller_id,)).fetchone()[0], "suspended")
        self.assertEqual(reporter.get(f"/sellers/{second_seller_id}").status_code, 404)

    def test_privacy_requests_are_owner_scoped_and_closure_does_not_delete_user(self):
        self.register(self.client, "owner@example.test", "buyer")
        self.login(self.client, "owner@example.test")
        response = self.post_form(self.client, "/privacy/requests", {
            "request_type": "closure", "details": "Please review my account closure request and explain retention."
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(b"does not immediately delete", self.client.get("/privacy/requests").data)
        with self.app.app_context():
            owner_id = get_db().execute("SELECT id FROM users WHERE email = 'owner@example.test'").fetchone()["id"]
            request_id = get_db().execute("SELECT id FROM privacy_requests WHERE owner_id = ?", (owner_id,)).fetchone()["id"]
        other = self.app.test_client()
        other.get("/")
        self.register(other, "other@example.test", "buyer")
        self.login(other, "other@example.test")
        self.assertNotIn(b"account closure request", other.get("/privacy/requests").data)
        self.assertEqual(other.get(f"/admin/privacy-requests/{request_id}").status_code, 403)
        self.create_admin()
        admin = self.app.test_client()
        admin.get("/login")
        self.login(admin, "admin@example.test", "LongAdminPassword123!")
        self.assertEqual(admin.get(f"/admin/privacy-requests/{request_id}").status_code, 200)
        self.assertEqual(self.post_form(admin, f"/admin/privacy-requests/{request_id}", {
            "status": "in_progress", "admin_note": "We will review this request."
        }).status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0], 3)
            self.assertEqual(get_db().execute("SELECT status FROM privacy_requests WHERE id = ?", (request_id,)).fetchone()[0], "in_progress")

    def test_security_headers_safe_errors_and_session_cookie_configuration(self):
        response = self.app.test_client().get("/help")
        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")
        self.assertIn("HttpOnly", response.headers.get("Set-Cookie", ""))
        self.assertIn("SameSite=Lax", response.headers.get("Set-Cookie", ""))
        missing = self.client.get("/missing-page")
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn(b"Traceback", missing.data)
        oversized = self.client.post("/api/generate", data=b"x" * (65 * 1024))
        self.assertEqual(oversized.status_code, 413)
        self.assertNotIn(b"Traceback", oversized.data)
        self.assertNotIn(b"Users\\HP", missing.data)

        error_app = create_app({
            "TESTING": True,
            "PROPAGATE_EXCEPTIONS": False,
            "SECRET_KEY": "test-only-secret-key",
            "DATABASE": str(Path(self.temp_dir.name) / "errors.sqlite3"),
        })
        error_app.add_url_rule("/test-only-failure", view_func=lambda: (_ for _ in ()).throw(RuntimeError("private marker")))
        with self.assertLogs(error_app.logger, level="ERROR") as captured:
            failed = error_app.test_client().get("/test-only-failure")
        self.assertEqual(failed.status_code, 500)
        self.assertNotIn(b"private marker", failed.data)
        self.assertNotIn(b"Traceback", failed.data)
        self.assertNotIn("private marker", "\n".join(captured.output))
        self.assertNotIn("Traceback", "\n".join(captured.output))

    def test_login_rate_limit_and_production_cookie_flag_can_be_configured(self):
        self.app.config["RATE_LIMITS"] = {"auth.login": (1, 300)}
        first = self.login(self.client, "missing@example.test", "WrongPassword123!")
        self.assertEqual(first.status_code, 400)
        second = self.login(self.client, "missing@example.test", "WrongPassword123!")
        self.assertEqual(second.status_code, 429)
        secure_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret-key",
            "DATABASE": str(self.database_path),
            "SESSION_COOKIE_SECURE": True,
        })
        response = secure_app.test_client().get("/login")
        self.assertIn("Secure", response.headers.get("Set-Cookie", ""))


if __name__ == "__main__":
    unittest.main()
