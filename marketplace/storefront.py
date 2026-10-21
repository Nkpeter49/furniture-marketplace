"""Public furniture discovery and participant-scoped buyer/seller conversations."""

import re
import sqlite3
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for

from ai.ollama_client import generate_text
from ai.prompts import build_reply_fallback, build_reply_prompt, reply_output_uses_only_supplied_words
from marketplace.database import get_db
from marketplace.security import approved_seller_required, current_user, login_required, role_required


storefront_bp = Blueprint("storefront", __name__)
PAGE_SIZE = 24
MESSAGE_MAX_LENGTH = 4000
POLICY_FIELDS = {
    "delivery": 600,
    "warranty": 600,
    "returns": 600,
    "other_policy": 800,
}


def _public_listing_query():
    return """FROM listings l
        JOIN users seller ON seller.id = l.seller_id
        JOIN seller_profiles sp ON sp.user_id = seller.id
        WHERE l.status = 'published' AND seller.account_status = 'active'
          AND seller.seller_approval = 'approved'
          AND NOT EXISTS (SELECT 1 FROM listing_moderation lm
                          WHERE lm.listing_id = l.id AND lm.status = 'hidden')"""


def _listing_images(listing_id: int):
    return get_db().execute(
        "SELECT id FROM listing_images WHERE listing_id = ? ORDER BY id", (listing_id,)
    ).fetchall()


@storefront_bp.get("/marketplace")
def browse():
    query = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:80]
    condition = request.args.get("condition", "").strip()[:80]
    availability = request.args.get("availability", "").strip()
    minimum = request.args.get("min_price", "").strip()[:24]
    maximum = request.args.get("max_price", "").strip()[:24]
    page = min(max(request.args.get("page", 1, type=int) or 1, 1), 10000)
    filters = []
    params: list[object] = []

    if query:
        like = f"%{query}%"
        filters.append("(l.item_name LIKE ? OR l.category LIKE ? OR l.material LIKE ? OR l.description LIKE ? OR l.additional_details LIKE ? OR sp.business_name LIKE ?)")
        params.extend([like] * 6)
    if category:
        filters.append("l.category = ?")
        params.append(category)
    if condition:
        filters.append("l.condition = ?")
        params.append(condition)
    if availability in {"available", "unavailable"}:
        filters.append("l.availability = ?")
        params.append(availability)
    else:
        availability = ""
    try:
        min_value = Decimal(minimum) if minimum else None
        max_value = Decimal(maximum) if maximum else None
        if any(value is not None and (not value.is_finite() or value < 0) for value in (min_value, max_value)):
            raise InvalidOperation
        if min_value is not None and max_value is not None and min_value > max_value:
            raise InvalidOperation
    except InvalidOperation:
        flash("Enter a valid non-negative price range with the minimum no higher than the maximum.", "error")
        minimum = maximum = ""
        min_value = max_value = None
    if min_value is not None:
        filters.append("l.price <> '' AND CAST(l.price AS REAL) >= ?")
        params.append(float(min_value))
    if max_value is not None:
        filters.append("l.price <> '' AND CAST(l.price AS REAL) <= ?")
        params.append(float(max_value))

    where = " AND ".join(filters)
    suffix = f" AND {where}" if where else ""
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) {_public_listing_query()}{suffix}", params).fetchone()[0]
    rows = db.execute(
        f"""SELECT l.*, sp.business_name,
                   (SELECT id FROM listing_images li WHERE li.listing_id = l.id ORDER BY li.id LIMIT 1) AS cover_image_id
            {_public_listing_query()}{suffix}
            ORDER BY l.updated_at DESC, l.id DESC LIMIT ? OFFSET ?""",
        [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
    ).fetchall()
    categories = [row[0] for row in db.execute(
        f"SELECT DISTINCT l.category {_public_listing_query()} ORDER BY l.category COLLATE NOCASE"
    )]
    conditions = [row[0] for row in db.execute(
        f"SELECT DISTINCT l.condition {_public_listing_query()} AND l.condition <> '' ORDER BY l.condition COLLATE NOCASE"
    )]
    favorite_ids = set()
    if current_user() and current_user()["role"] == "buyer":
        favorite_ids = {row[0] for row in db.execute("SELECT listing_id FROM favorites WHERE buyer_id = ?", (current_user()["id"],))}
    return render_template(
        "buyer/storefront.html", listings=rows, categories=categories, conditions=conditions,
        favorite_ids=favorite_ids, filters={"q": query, "category": category, "condition": condition,
        "availability": availability, "min_price": minimum, "max_price": maximum},
        page=page, page_count=max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE), total=total,
    )


@storefront_bp.get("/listings/<int:listing_id>")
def listing_detail(listing_id: int):
    listing = get_db().execute(
        f"""SELECT l.*, seller.id AS public_seller_id, sp.business_name, sp.contact_number,
                   sp.publish_contact, sp.profile_image AS seller_photo
            {_public_listing_query()} AND l.id = ?""",
        (listing_id,),
    ).fetchone()
    if listing is None:
        abort(404)
    images = _listing_images(listing_id)
    is_favorite = bool(current_user() and current_user()["role"] == "buyer" and get_db().execute(
        "SELECT 1 FROM favorites WHERE buyer_id = ? AND listing_id = ?",
        (current_user()["id"], listing_id),
    ).fetchone())
    phone = listing["contact_number"] if listing["publish_contact"] else ""
    whatsapp_digits = re.sub(r"\D", "", phone)
    return render_template("buyer/listing_detail.html", listing=listing, images=images, is_favorite=is_favorite, whatsapp_digits=whatsapp_digits)


@storefront_bp.route("/listings/<int:listing_id>/favorite", methods=["POST"])
@role_required("buyer")
def toggle_favorite(listing_id: int):
    if get_db().execute(
        f"SELECT l.id {_public_listing_query()} AND l.id = ?", (listing_id,)
    ).fetchone() is None:
        abort(404)
    db = get_db()
    buyer_id = current_user()["id"]
    if db.execute("SELECT 1 FROM favorites WHERE buyer_id = ? AND listing_id = ?", (buyer_id, listing_id)).fetchone():
        db.execute("DELETE FROM favorites WHERE buyer_id = ? AND listing_id = ?", (buyer_id, listing_id))
        flash("Removed from your saved furniture.", "success")
    else:
        db.execute("INSERT INTO favorites (buyer_id, listing_id) VALUES (?, ?)", (buyer_id, listing_id))
        flash("Saved to your favorites.", "success")
    db.commit()
    referrer = request.referrer or ""
    return redirect(referrer if referrer.startswith("/") and not referrer.startswith("//") else url_for("storefront.favorites"))


@storefront_bp.get("/favorites")
@role_required("buyer")
def favorites():
    listings = get_db().execute(
        f"""SELECT l.*, sp.business_name,
                   (SELECT id FROM listing_images li WHERE li.listing_id = l.id ORDER BY li.id LIMIT 1) AS cover_image_id
            FROM favorites f JOIN listings l ON l.id = f.listing_id
            JOIN users seller ON seller.id = l.seller_id JOIN seller_profiles sp ON sp.user_id = seller.id
            WHERE f.buyer_id = ? AND l.status = 'published' AND seller.account_status = 'active'
              AND seller.seller_approval = 'approved'
              AND NOT EXISTS (SELECT 1 FROM listing_moderation lm WHERE lm.listing_id = l.id AND lm.status = 'hidden')
            ORDER BY f.created_at DESC""",
        (current_user()["id"],),
    ).fetchall()
    return render_template("buyer/favorites.html", listings=listings)


@storefront_bp.route("/listings/<int:listing_id>/inquire", methods=["POST"])
@role_required("buyer")
def start_inquiry(listing_id: int):
    listing = get_db().execute(
        f"SELECT l.id, l.seller_id, l.item_name {_public_listing_query()} AND l.id = ?",
        (listing_id,),
    ).fetchone()
    if listing is None:
        abort(404)
    if listing["seller_id"] == current_user()["id"]:
        abort(403)
    body = request.form.get("body", "").strip()
    if not 5 <= len(body) <= MESSAGE_MAX_LENGTH:
        flash("Write an inquiry between 5 and 4,000 characters.", "error")
        return redirect(url_for("storefront.listing_detail", listing_id=listing_id))
    db = get_db()
    try:
        db.execute(
            "INSERT OR IGNORE INTO conversations (listing_id, buyer_id, seller_id) VALUES (?, ?, ?)",
            (listing_id, current_user()["id"], listing["seller_id"]),
        )
        conversation = db.execute(
            "SELECT id FROM conversations WHERE listing_id = ? AND buyer_id = ?",
            (listing_id, current_user()["id"]),
        ).fetchone()
        db.execute(
            "INSERT INTO messages (conversation_id, author_id, body) VALUES (?, ?, ?)",
            (conversation["id"], current_user()["id"], body),
        )
        db.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation["id"],))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.error("Could not create inquiry; details suppressed")
        flash("Your inquiry could not be saved. Please try again.", "error")
        return redirect(url_for("storefront.listing_detail", listing_id=listing_id))
    return redirect(url_for("storefront.conversation_detail", conversation_id=conversation["id"]))


def _conversation_for_participant(conversation_id: int):
    user = current_user()
    if user["role"] == "buyer":
        column = "buyer_id"
    elif user["role"] == "seller" and user["seller_approval"] == "approved":
        column = "seller_id"
    else:
        abort(404)
    conversation = get_db().execute(
        f"""SELECT c.*, l.item_name, l.category, l.material, l.condition, l.dimensions,
                   l.price, l.currency, l.colour, l.description, l.availability, l.quantity,
                   buyer.display_name AS buyer_name, seller.display_name AS seller_name,
                   sp.business_name
            FROM conversations c JOIN listings l ON l.id = c.listing_id
            JOIN users buyer ON buyer.id = c.buyer_id JOIN users seller ON seller.id = c.seller_id
            LEFT JOIN seller_profiles sp ON sp.user_id = seller.id
            WHERE c.id = ? AND c.{column} = ? AND buyer.account_status = 'active'
              AND seller.account_status = 'active' AND seller.seller_approval = 'approved'""",
        (conversation_id, user["id"]),
    ).fetchone()
    if conversation is None:
        abort(404)
    return conversation


@storefront_bp.get("/conversations")
@login_required
def conversations():
    user = current_user()
    if user["role"] == "buyer":
        column = "c.buyer_id"
    elif user["role"] == "seller" and user["seller_approval"] == "approved":
        column = "c.seller_id"
    else:
        abort(403)
    rows = get_db().execute(
        f"""SELECT c.id, c.updated_at, l.item_name,
                   CASE WHEN c.buyer_id = ? THEN sp.business_name ELSE buyer.display_name END AS other_party,
                   (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_message
            FROM conversations c JOIN listings l ON l.id = c.listing_id
            JOIN users buyer ON buyer.id = c.buyer_id JOIN seller_profiles sp ON sp.user_id = c.seller_id
            WHERE {column} = ? AND buyer.account_status = 'active'
            ORDER BY c.updated_at DESC, c.id DESC""",
        (user["id"], user["id"]),
    ).fetchall()
    return render_template("buyer/conversations.html", conversations=rows, role=user["role"])


@storefront_bp.route("/conversations/<int:conversation_id>", methods=["GET", "POST"])
@login_required
def conversation_detail(conversation_id: int):
    conversation = _conversation_for_participant(conversation_id)
    user = current_user()
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not 1 <= len(body) <= MESSAGE_MAX_LENGTH:
            flash("Message must be between 1 and 4,000 characters.", "error")
        else:
            db = get_db()
            db.execute(
                "INSERT INTO messages (conversation_id, author_id, body) VALUES (?, ?, ?)",
                (conversation_id, user["id"], body),
            )
            db.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
            db.commit()
            flash("Your message was sent.", "success")
            return redirect(url_for("storefront.conversation_detail", conversation_id=conversation_id))
    messages = get_db().execute(
        """SELECT m.id, m.author_id, m.body, m.created_at, u.display_name, u.role
           FROM messages m JOIN users u ON u.id = m.author_id
           WHERE m.conversation_id = ? ORDER BY m.id""", (conversation_id,),
    ).fetchall()
    return render_template("buyer/conversation_detail.html", conversation=conversation, messages=messages, user=user)


@storefront_bp.post("/api/conversations/<int:conversation_id>/reply-draft")
@approved_seller_required
def generate_reply_draft(conversation_id: int):
    conversation = _conversation_for_participant(conversation_id)
    if current_user()["role"] != "seller":
        abort(403)
    latest = get_db().execute(
        "SELECT body FROM messages WHERE conversation_id = ? AND author_id = ? ORDER BY id DESC LIMIT 1",
        (conversation_id, conversation["buyer_id"]),
    ).fetchone()
    customer_message = latest["body"] if latest else ""
    policies = {}
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and isinstance(payload.get("policies"), dict):
        for key, limit in POLICY_FIELDS.items():
            value = str(payload["policies"].get(key, "")).strip()
            if len(value) > limit:
                return jsonify(error=f"{key.replace('_', ' ').title()} information is too long."), 400
            policies[key] = value
    listing = {
        key: conversation[key]
        for key in ("item_name", "category", "material", "condition", "dimensions", "price", "currency", "colour", "description", "availability", "quantity")
    }
    try:
        candidate = generate_text(build_reply_prompt(listing, customer_message, policies))
    except Exception:
        current_app.logger.info("Local reply draft unavailable; using facts-only draft")
        return jsonify(
            result=build_reply_fallback(listing, customer_message), source="safe_fallback",
            notice="Ollama did not provide a safe draft. This deterministic text is not AI-generated; review and edit before sending.",
        )
    if not reply_output_uses_only_supplied_words(candidate, listing, customer_message, policies):
        return jsonify(
            result=build_reply_fallback(listing, customer_message), source="safe_fallback",
            notice="The local model used wording that could not be verified, so it was withheld. This deterministic text is not AI-generated; review and edit before sending.",
        )
    return jsonify(
        result=candidate, source="local_ai",
        notice="Draft generated by local Ollama. Review every fact and edit before you choose to send it.",
    )
