"""Buyer profile, seller business profile, and seller-owned listing routes."""

from decimal import Decimal, InvalidOperation
import re
import sqlite3
from pathlib import Path

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template,
    request, send_file, url_for,
)

from marketplace.database import get_db
from marketplace.media import InvalidImage, delete_image, image_path, prepare_image, store_image
from marketplace.security import approved_seller_required, current_user, role_required


profiles_bp = Blueprint("profiles", __name__)
MAX_BIO_LENGTH = 500
MAX_SELLER_BIO_LENGTH = 1800
MAX_SPECIALTIES_LENGTH = 500
MAX_LISTING_PHOTOS = 5
MAX_PHONE_LENGTH = 25
FIELD_LIMITS = {
    "item_name": 120,
    "category": 80,
    "material": 120,
    "condition": 80,
    "dimensions": 120,
    "price": 24,
    "currency": 3,
    "colour": 80,
    "description": 2400,
    "additional_details": 1200,
    "quantity": 12,
}


def _seller_profile(user_id: int):
    return get_db().execute(
        "SELECT * FROM seller_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()


def _uploads_dir() -> Path:
    path = Path(current_app.instance_path) / "media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remove_new_files(names: list[str]) -> None:
    for name in names:
        delete_image(name, current_app.instance_path)


def _image_from_form(field: str) -> tuple[str | None, list[str]]:
    upload = request.files.get(field)
    if upload is None or not upload.filename:
        return None, []
    data, suffix = prepare_image(upload)
    return store_image(data, suffix, current_app.instance_path), []


def _flash_validation(message: str, template: str, **context):
    flash(message, "error")
    return render_template(template, **context), 400


@profiles_bp.route("/seller/profile", methods=["GET", "POST"])
@approved_seller_required
def edit_seller_profile():
    user = current_user()
    profile = _seller_profile(user["id"])
    if profile is None:
        abort(500)

    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip()
        bio = request.form.get("bio", "").strip()
        specialties = request.form.get("specialties", "").strip()
        phone_raw = request.form.get("contact_number", "").strip()
        publish_contact = request.form.get("publish_contact") == "on"
        phone = re.sub(r"[\s()-]", "", phone_raw)
        if not 2 <= len(business_name) <= 100:
            return _flash_validation("Business name must be between 2 and 100 characters.", "seller/profile_form.html", user=user, profile=profile)
        if len(bio) > MAX_SELLER_BIO_LENGTH:
            return _flash_validation("Business biography must be 1,800 characters or fewer.", "seller/profile_form.html", user=user, profile=profile)
        if len(specialties) > MAX_SPECIALTIES_LENGTH:
            return _flash_validation("Furniture specialties must be 500 characters or fewer.", "seller/profile_form.html", user=user, profile=profile)
        if len(phone) > MAX_PHONE_LENGTH or (phone and not re.fullmatch(r"\+?[0-9]{8,15}", phone)):
            return _flash_validation("Enter a phone number with 8 to 15 digits, optionally beginning with +.", "seller/profile_form.html", user=user, profile=profile)
        if publish_contact and not phone:
            return _flash_validation("Enter a contact number before choosing to publish it.", "seller/profile_form.html", user=user, profile=profile)

        new_files: list[str] = []
        values = {
            "business_name": business_name,
            "bio": bio,
            "specialties": specialties,
            "contact_number": phone,
            "publish_contact": 1 if publish_contact else 0,
        }
        try:
            for field, column in (("business_photo", "profile_image"), ("cover_photo", "cover_image")):
                if request.form.get(f"remove_{field}") == "on":
                    values[column] = None
                uploaded = request.files.get(field)
                if uploaded is not None and uploaded.filename:
                    filename, _ = _image_from_form(field)
                    new_files.append(filename)
                    values[column] = filename
        except InvalidImage as exc:
            _remove_new_files(new_files)
            return _flash_validation(str(exc), "seller/profile_form.html", user=user, profile=profile)
        except OSError:
            _remove_new_files(new_files)
            current_app.logger.error("Could not store seller profile image; exception details suppressed")
            return _flash_validation("The image could not be saved. Please try again.", "seller/profile_form.html", user=user, profile=profile)

        db = get_db()
        try:
            db.execute(
                """UPDATE seller_profiles SET business_name = ?, bio = ?, specialties = ?,
                   contact_number = ?, publish_contact = ?, profile_image = ?, cover_image = ?,
                   updated_at = CURRENT_TIMESTAMP WHERE user_id = ?""",
                (business_name, bio, specialties, phone, values["publish_contact"],
                 values.get("profile_image", profile["profile_image"]),
                 values.get("cover_image", profile["cover_image"]), user["id"]),
            )
            db.commit()
        except sqlite3.Error:
            db.rollback()
            _remove_new_files(new_files)
            current_app.logger.error("Could not update seller profile; exception details suppressed")
            return _flash_validation("Your profile could not be saved. Please try again.", "seller/profile_form.html", user=user, profile=profile)

        for column in ("profile_image", "cover_image"):
            new_name = values.get(column, profile[column])
            if new_name != profile[column]:
                delete_image(profile[column], current_app.instance_path)
        flash("Your business profile was saved.", "success")
        return redirect(url_for("profiles.edit_seller_profile"))

    return render_template("seller/profile_form.html", user=user, profile=profile)


@profiles_bp.get("/sellers/<int:seller_id>")
def public_seller_profile(seller_id: int):
    profile = get_db().execute(
        """SELECT sp.user_id, sp.business_name, sp.bio, sp.specialties,
                  sp.profile_image, sp.cover_image, sp.contact_number, sp.publish_contact
           FROM seller_profiles sp JOIN users u ON u.id = sp.user_id
           WHERE sp.user_id = ? AND u.role = 'seller' AND u.account_status = 'active'
             AND u.seller_approval = 'approved' AND sp.business_name <> ''""",
        (seller_id,),
    ).fetchone()
    if profile is None:
        abort(404)
    listings = get_db().execute(
        """SELECT l.*, (SELECT id FROM listing_images li
                         WHERE li.listing_id = l.id ORDER BY li.id LIMIT 1) AS cover_image_id
           FROM listings l JOIN users u ON u.id = l.seller_id
           WHERE l.seller_id = ? AND l.status = 'published'
             AND NOT EXISTS (SELECT 1 FROM listing_moderation lm WHERE lm.listing_id = l.id AND lm.status = 'hidden')
             AND u.account_status = 'active'
             AND u.seller_approval = 'approved'
           ORDER BY l.updated_at DESC, l.id DESC""",
        (seller_id,),
    ).fetchall()
    phone = profile["contact_number"] if profile["publish_contact"] else ""
    whatsapp_digits = re.sub(r"\D", "", phone)
    return render_template(
        "seller/public_profile.html", profile=profile, listings=listings,
        whatsapp_digits=whatsapp_digits,
    )


@profiles_bp.get("/media/seller/<int:seller_id>/<kind>")
def seller_profile_image(seller_id: int, kind: str):
    column = {"profile": "profile_image", "cover": "cover_image"}.get(kind)
    if column is None:
        abort(404)
    profile = get_db().execute(
        """SELECT sp.profile_image, sp.cover_image FROM seller_profiles sp
           JOIN users u ON u.id = sp.user_id
           WHERE sp.user_id = ? AND u.role = 'seller' AND u.account_status = 'active'
             AND u.seller_approval = 'approved'""",
        (seller_id,),
    ).fetchone()
    if profile is None:
        abort(404)
    path = image_path(profile[column], current_app.instance_path)
    if path is None:
        abort(404)
    return send_file(path, conditional=True, max_age=300, download_name=path.name)


@profiles_bp.get("/account/profile-photo")
@role_required("buyer")
def buyer_profile_image():
    path = image_path(current_user()["profile_image"], current_app.instance_path)
    if path is None:
        abort(404)
    return send_file(path, conditional=True, max_age=0, download_name=path.name)


def _listing_form_values(source):
    values = {}
    for key in FIELD_LIMITS:
        value = source.get(key, "")
        values[key] = str(value).strip() if value is not None else ""
    values["availability"] = str(source.get("availability", "available"))
    values["status"] = str(source.get("status", "draft"))
    return values


def _validate_listing(values: dict[str, str]) -> str | None:
    for key, limit in FIELD_LIMITS.items():
        if len(values[key]) > limit:
            return f"{key.replace('_', ' ').title()} must be {limit} characters or fewer."
    if not values["item_name"] or not values["category"]:
        return "Enter both an item name and a furniture category."
    if values["availability"] not in {"available", "unavailable"}:
        return "Choose a valid availability status."
    if values.get("quantity", ""):
        if not re.fullmatch(r"\d{1,9}", values["quantity"]):
            return "Seller-reported quantity must be a whole number from 0 to 999,999,999 or blank."
        if int(values["quantity"]) == 0 and values["availability"] == "available":
            return "A quantity of zero cannot be marked available. Set it to unavailable or update the quantity."
    if values["status"] not in {"draft", "published"}:
        return "Choose draft or published status."
    if values["price"]:
        try:
            amount = Decimal(values["price"])
        except InvalidOperation:
            return "Enter a valid non-negative price or leave the price blank."
        if not amount.is_finite() or amount < 0 or amount > Decimal("999999999999.99"):
            return "Enter a valid non-negative price or leave the price blank."
    if values["currency"] and not re.fullmatch(r"[A-Za-z]{3}", values["currency"]):
        return "Currency must be a three-letter code, such as USD or KES."
    values["currency"] = values["currency"].upper()
    return None


def _listing_or_404(listing_id: int):
    listing = get_db().execute(
        """SELECT l.*, lm.status AS moderation_status FROM listings l
           LEFT JOIN listing_moderation lm ON lm.listing_id = l.id
           WHERE l.id = ? AND l.seller_id = ? AND l.status <> 'removed'""",
        (listing_id, current_user()["id"]),
    ).fetchone()
    if listing is None:
        abort(404)
    return listing


def _render_listing_form(user, listing=None, values=None, status=200):
    images = []
    if listing is not None:
        images = get_db().execute(
            "SELECT id, filename FROM listing_images WHERE listing_id = ? ORDER BY id",
            (listing["id"],),
        ).fetchall()
    return render_template(
        "seller/listing_form.html", user=user, listing=listing,
        values=values or (dict(listing) if listing is not None else {
            "item_name": "", "category": "", "material": "", "condition": "",
            "dimensions": "", "price": "", "currency": "", "colour": "",
            "description": "", "additional_details": "", "availability": "available",
            "status": "draft", "quantity": "",
        }), images=images,
    ), status


@profiles_bp.get("/media/listing/<int:image_id>")
def listing_image(image_id: int):
    row = get_db().execute(
        """SELECT li.filename FROM listing_images li JOIN listings l ON l.id = li.listing_id
           JOIN users u ON u.id = l.seller_id
           WHERE li.id = ? AND l.status = 'published'
             AND NOT EXISTS (SELECT 1 FROM listing_moderation lm WHERE lm.listing_id = l.id AND lm.status = 'hidden')
             AND u.role = 'seller'
             AND u.account_status = 'active' AND u.seller_approval = 'approved'""",
        (image_id,),
    ).fetchone()
    if row is None:
        abort(404)
    path = image_path(row["filename"], current_app.instance_path)
    if path is None:
        abort(404)
    return send_file(path, conditional=True, max_age=300, download_name=path.name)


@profiles_bp.get("/seller/listings/<int:listing_id>/photos/<int:image_id>")
@approved_seller_required
def seller_listing_photo(listing_id: int, image_id: int):
    row = get_db().execute(
        """SELECT li.filename FROM listing_images li JOIN listings l ON l.id = li.listing_id
           WHERE li.id = ? AND li.listing_id = ? AND l.seller_id = ? AND l.status <> 'removed'""",
        (image_id, listing_id, current_user()["id"]),
    ).fetchone()
    if row is None:
        abort(404)
    path = image_path(row["filename"], current_app.instance_path)
    if path is None:
        abort(404)
    return send_file(path, conditional=True, max_age=0, download_name=path.name)


@profiles_bp.get("/seller/listings")
@approved_seller_required
def seller_listings():
    user = current_user()
    listings = get_db().execute(
        """SELECT l.*, (SELECT COUNT(*) FROM listing_images li WHERE li.listing_id = l.id) AS photo_count,
                  lm.status AS moderation_status
           FROM listings l LEFT JOIN listing_moderation lm ON lm.listing_id = l.id
           WHERE l.seller_id = ? AND l.status <> 'removed'
           ORDER BY l.updated_at DESC, l.id DESC""",
        (user["id"],),
    ).fetchall()
    return render_template("seller/listings.html", user=user, listings=listings)


def _save_listing(user, listing=None):
    values = _listing_form_values(request.form)
    error = _validate_listing(values)
    if error:
        return _flash_validation(error, "seller/listing_form.html", user=user, listing=listing, values=values, images=[])
    if listing is not None and values["status"] == "published":
        hidden = get_db().execute(
            "SELECT 1 FROM listing_moderation WHERE listing_id = ? AND status = 'hidden'",
            (listing["id"],),
        ).fetchone()
        if hidden:
            return _flash_validation(
                "This listing is hidden during administrator review and cannot be republished yet.",
                "seller/listing_form.html", user=user, listing=listing, values=values,
                images=get_db().execute("SELECT id, filename FROM listing_images WHERE listing_id = ?", (listing["id"],)).fetchall(),
            )
    uploads = [f for f in request.files.getlist("photos") if f and f.filename]
    existing_count = 0
    if listing is not None:
        existing_count = get_db().execute(
            "SELECT COUNT(*) AS count FROM listing_images WHERE listing_id = ?", (listing["id"],)
        ).fetchone()["count"]
    if existing_count + len(uploads) > MAX_LISTING_PHOTOS:
        return _flash_validation(
            f"A listing can have at most {MAX_LISTING_PHOTOS} photos.",
            "seller/listing_form.html", user=user, listing=listing, values=values, images=[],
        )

    new_files: list[str] = []
    try:
        for upload in uploads:
            encoded, suffix = prepare_image(upload)
            new_files.append(store_image(encoded, suffix, current_app.instance_path))
    except InvalidImage as exc:
        _remove_new_files(new_files)
        return _flash_validation(str(exc), "seller/listing_form.html", user=user, listing=listing, values=values, images=[])
    except OSError:
        _remove_new_files(new_files)
        current_app.logger.error("Could not save listing photo; exception details suppressed")
        return _flash_validation("The photos could not be saved. Please try again.", "seller/listing_form.html", user=user, listing=listing, values=values, images=[])

    db = get_db()
    try:
        if listing is None:
            cursor = db.execute(
                """INSERT INTO listings
                   (seller_id, item_name, category, material, condition, dimensions, price, currency,
                    colour, description, additional_details, availability, status, quantity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user["id"], values["item_name"], values["category"], values["material"],
                 values["condition"], values["dimensions"], values["price"], values["currency"],
                 values["colour"], values["description"], values["additional_details"],
                 values["availability"], values["status"], int(values["quantity"]) if values.get("quantity") else None),
            )
            listing_id = cursor.lastrowid
        else:
            listing_id = listing["id"]
            db.execute(
                """UPDATE listings SET item_name = ?, category = ?, material = ?, condition = ?,
                   dimensions = ?, price = ?, currency = ?, colour = ?, description = ?,
                   additional_details = ?, availability = ?, status = ?, quantity = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND seller_id = ?""",
                (values["item_name"], values["category"], values["material"], values["condition"],
                 values["dimensions"], values["price"], values["currency"], values["colour"],
                 values["description"], values["additional_details"], values["availability"],
                 values["status"], int(values["quantity"]) if values.get("quantity") else None, listing_id, user["id"]),
            )
        for filename in new_files:
            db.execute("INSERT INTO listing_images (listing_id, filename) VALUES (?, ?)", (listing_id, filename))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        _remove_new_files(new_files)
        current_app.logger.error("Could not save seller listing; exception details suppressed")
        return _flash_validation("The listing could not be saved. Please try again.", "seller/listing_form.html", user=user, listing=listing, values=values, images=[])
    flash("Listing saved.", "success")
    return redirect(url_for("profiles.seller_listings"))


@profiles_bp.route("/seller/listings/new", methods=["GET", "POST"])
@approved_seller_required
def create_listing():
    user = current_user()
    if request.method == "POST":
        return _save_listing(user)
    return _render_listing_form(user)


@profiles_bp.route("/seller/listings/<int:listing_id>/edit", methods=["GET", "POST"])
@approved_seller_required
def edit_listing(listing_id: int):
    user = current_user()
    listing = _listing_or_404(listing_id)
    if request.method == "POST":
        return _save_listing(user, listing)
    return _render_listing_form(user, listing)


@profiles_bp.post("/seller/listings/<int:listing_id>/remove")
@approved_seller_required
def remove_listing(listing_id: int):
    listing = _listing_or_404(listing_id)
    if request.form.get("confirm_remove") != "yes":
        abort(400, description="Confirm that you want to remove this listing.")
    db = get_db()
    db.execute(
        "UPDATE listings SET status = 'removed', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND seller_id = ?",
        (listing["id"], current_user()["id"]),
    )
    db.commit()
    flash("Listing removed from your seller page.", "success")
    return redirect(url_for("profiles.seller_listings"))


@profiles_bp.post("/seller/listings/<int:listing_id>/photos/<int:image_id>/remove")
@approved_seller_required
def remove_listing_photo(listing_id: int, image_id: int):
    _listing_or_404(listing_id)
    if request.form.get("confirm_remove") != "yes":
        abort(400, description="Confirm that you want to remove this photo.")
    row = get_db().execute(
        """SELECT li.filename FROM listing_images li JOIN listings l ON l.id = li.listing_id
           WHERE li.id = ? AND li.listing_id = ? AND l.seller_id = ?""",
        (image_id, listing_id, current_user()["id"]),
    ).fetchone()
    if row is None:
        abort(404)
    db = get_db()
    db.execute("DELETE FROM listing_images WHERE id = ? AND listing_id = ?", (image_id, listing_id))
    db.commit()
    delete_image(row["filename"], current_app.instance_path)
    flash("Photo removed.", "success")
    return redirect(url_for("profiles.edit_listing", listing_id=listing_id))
