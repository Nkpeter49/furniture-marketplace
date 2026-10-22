"""Buyer and seller registration, sign-in, and account pages."""

import re
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from marketplace.database import get_db
from marketplace.security import current_user, login_required, public_user, role_required
from marketplace.media import InvalidImage, delete_image, prepare_image, store_image


auth_bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MIN_PASSWORD_LENGTH = 12


def _relative_time(stamp: str, now: datetime) -> str:
    parsed = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    seconds = max(0, int((now - parsed).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        amount = seconds // 60
        return f"{amount} minute{'s' if amount != 1 else ''} ago"
    if seconds < 86400:
        amount = seconds // 3600
        return f"{amount} hour{'s' if amount != 1 else ''} ago"
    amount = seconds // 86400
    return f"{amount} day{'s' if amount != 1 else ''} ago"


def valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(value)) and len(value) <= 254


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "")
        errors = []
        if not valid_email(email):
            errors.append("Enter a valid email address.")
        if not 2 <= len(display_name) <= 80:
            errors.append("Name must be between 2 and 80 characters.")
        if role not in {"buyer", "seller"}:
            errors.append("Choose buyer or seller account type.")
        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("auth/register.html", values=request.form), 400

        db = get_db()
        try:
            cursor = db.execute(
                """INSERT INTO users (email, display_name, password_hash, role, seller_approval)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    email,
                    display_name,
                    generate_password_hash(password),
                    role,
                    "pending" if role == "seller" else None,
                ),
            )
            if role == "seller":
                db.execute(
                    "INSERT INTO seller_profiles (user_id, business_name) VALUES (?, ?)",
                    (cursor.lastrowid, display_name),
                )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("An account could not be created with those details. Check the email and try again.", "error")
            return render_template("auth/register.html", values=request.form), 400

        if role == "seller":
            flash("Your seller account is ready. An administrator must approve it before you can publish listings.", "success")
        else:
            flash("Your buyer account is ready. Please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", values={})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if (
            user is None
            or user["account_status"] != "active"
            or not check_password_hash(user["password_hash"], password)
        ):
            flash("Email or password is incorrect, or the account is unavailable.", "error")
            return render_template("auth/login.html", email=email), 400

        session.clear()
        session["user_id"] = user["id"]
        session["csrf_token"] = current_app.extensions["new_csrf_token"]()
        flash("You are signed in.", "success")
        return redirect(url_for("auth.dashboard"))

    return render_template("auth/login.html", email="")


@auth_bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You are signed out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.get("/dashboard")
@login_required
def dashboard():
    return redirect(url_for(f"auth.{current_user()['role']}_dashboard"))


@auth_bp.get("/buyer/dashboard")
@role_required("buyer")
def buyer_dashboard():
    user = current_user()
    db = get_db()
    stats = {
        "favorites": db.execute("""SELECT COUNT(*) FROM favorites f JOIN listings l ON l.id = f.listing_id
            JOIN users s ON s.id = l.seller_id WHERE f.buyer_id = ? AND l.status = 'published'
            AND l.review_status = 'approved'
            AND s.account_status = 'active' AND s.seller_approval = 'approved'
            AND NOT EXISTS (SELECT 1 FROM listing_moderation lm WHERE lm.listing_id = l.id AND lm.status = 'hidden')""", (user["id"],)).fetchone()[0],
        "conversations": db.execute("""SELECT COUNT(*) FROM conversations c JOIN users s ON s.id = c.seller_id
            WHERE c.buyer_id = ? AND s.account_status = 'active' AND s.seller_approval = 'approved'""", (user["id"],)).fetchone()[0],
    }
    favorites = db.execute(
        """SELECT l.id, l.item_name, l.price, l.currency,
                  (SELECT id FROM listing_images WHERE listing_id = l.id ORDER BY id LIMIT 1) AS image_id
           FROM favorites f JOIN listings l ON l.id = f.listing_id
           JOIN users s ON s.id = l.seller_id
           WHERE f.buyer_id = ? AND l.status = 'published' AND l.review_status = 'approved'
             AND s.account_status = 'active' AND s.seller_approval = 'approved'
             AND NOT EXISTS (SELECT 1 FROM listing_moderation lm WHERE lm.listing_id = l.id AND lm.status = 'hidden')
           ORDER BY f.created_at DESC LIMIT 5""", (user["id"],),
    ).fetchall()
    recent_conversations = db.execute(
        """SELECT c.id, c.updated_at, l.item_name, sp.business_name,
                  (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS preview
           FROM conversations c JOIN listings l ON l.id = c.listing_id
           JOIN seller_profiles sp ON sp.user_id = c.seller_id JOIN users s ON s.id = c.seller_id
           WHERE c.buyer_id = ? AND s.account_status = 'active' AND s.seller_approval = 'approved'
           ORDER BY c.updated_at DESC LIMIT 5""", (user["id"],),
    ).fetchall()
    return render_template("buyer/dashboard.html", user=public_user(user), stats=stats,
                           favorites=favorites, recent_conversations=recent_conversations)


@auth_bp.get("/seller/dashboard")
@role_required("seller")
def seller_dashboard():
    user = current_user()
    db = get_db()
    profile = db.execute("SELECT business_name FROM seller_profiles WHERE user_id = ?", (user["id"],)).fetchone()
    stats = {
        "active": db.execute("""SELECT COUNT(*) FROM listings l WHERE l.seller_id = ? AND l.status = 'published'
            AND l.review_status = 'approved' AND NOT EXISTS (SELECT 1 FROM listing_moderation lm WHERE lm.listing_id = l.id AND lm.status = 'hidden')""", (user["id"],)).fetchone()[0],
        "inquiries": db.execute("SELECT COUNT(*) FROM conversations WHERE seller_id = ?", (user["id"],)).fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM listings WHERE seller_id = ? AND status <> 'removed' AND review_status = 'pending'", (user["id"],)).fetchone()[0],
    }
    listings = db.execute(
        """SELECT l.id, l.item_name, l.price, l.currency, l.availability, l.review_status,
                  l.review_reason, (SELECT id FROM listing_images li WHERE li.listing_id = l.id ORDER BY li.id LIMIT 1) AS image_id
           FROM listings l WHERE l.seller_id = ? AND l.status <> 'removed'
           ORDER BY l.updated_at DESC, l.id DESC LIMIT 5""", (user["id"],),
    ).fetchall()
    inquiries = db.execute(
        """SELECT c.id, b.display_name AS buyer_name, l.item_name,
                  m.body AS preview, m.created_at AS message_at
           FROM conversations c JOIN users b ON b.id = c.buyer_id
           JOIN listings l ON l.id = c.listing_id
           JOIN messages m ON m.id = (SELECT id FROM messages WHERE conversation_id = c.id AND author_id = c.buyer_id ORDER BY id DESC LIMIT 1)
           WHERE c.seller_id = ? AND ? = 'approved'
           ORDER BY m.created_at DESC, m.id DESC LIMIT 5""", (user["id"], user["seller_approval"]),
    ).fetchall()
    now = datetime.now(timezone.utc)
    inquiries = [{**dict(row), "relative_time": _relative_time(row["message_at"], now)} for row in inquiries]
    status_label = "Suspended" if user["account_status"] == "suspended" else ("Pending approval" if user["seller_approval"] == "pending" else "Approved & Active")
    return render_template("seller/dashboard.html", user=public_user(user), stats=stats,
                           business_name=profile["business_name"] if profile else user["display_name"],
                           account_status_label=status_label, listings=listings, inquiries=inquiries)


@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user = current_user()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        bio = request.form.get("bio", "").strip() if user["role"] == "buyer" else user["bio"]
        new_image = None
        old_image = user["profile_image"] if user["role"] == "buyer" else None
        image_changed = False
        errors = []
        if not valid_email(email):
            errors.append("Enter a valid email address.")
        if not 2 <= len(display_name) <= 80:
            errors.append("Name must be between 2 and 80 characters.")
        if user["role"] == "buyer" and len(bio) > 500:
            errors.append("Your short bio must be 500 characters or fewer.")

        upload = request.files.get("profile_photo") if user["role"] == "buyer" else None
        if upload is not None and upload.filename and not errors:
            try:
                encoded, suffix = prepare_image(upload)
                new_image = store_image(encoded, suffix, current_app.instance_path)
                image_changed = True
            except InvalidImage as exc:
                errors.append(str(exc))
            except OSError:
                current_app.logger.error("Could not store buyer profile image; exception details suppressed")
                errors.append("The image could not be saved. Please try again.")
        elif user["role"] == "buyer" and request.form.get("remove_profile_photo") == "on":
            image_changed = old_image is not None

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("auth/account.html", user=user), 400

        profile_image = new_image if new_image is not None else (
            None if image_changed else old_image
        )
        db = get_db()
        try:
            if user["role"] == "buyer":
                db.execute(
                    """UPDATE users SET email = ?, display_name = ?, bio = ?, profile_image = ?,
                       updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (email, display_name, bio, profile_image, user["id"]),
                )
            else:
                db.execute(
                    "UPDATE users SET email = ?, display_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (email, display_name, user["id"]),
                )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            if new_image:
                delete_image(new_image, current_app.instance_path)
            flash("That email address is already in use.", "error")
            user = get_db().execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
            return render_template("auth/account.html", user=user), 400
        except sqlite3.Error:
            db.rollback()
            if new_image:
                delete_image(new_image, current_app.instance_path)
            current_app.logger.error("Could not update account profile; exception details suppressed")
            flash("Your account could not be updated. Please try again.", "error")
            return render_template("auth/account.html", user=user), 500
        if image_changed and old_image != profile_image:
            delete_image(old_image, current_app.instance_path)
        flash("Your account details were updated.", "success")
        return redirect(url_for("auth.account"))
    return render_template("auth/account.html", user=user)


@auth_bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    user = current_user()
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        if not check_password_hash(user["password_hash"], current_password):
            flash("Current password was not correct.", "error")
        elif len(new_password) < MIN_PASSWORD_LENGTH:
            flash(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.", "error")
        else:
            db = get_db()
            db.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (generate_password_hash(new_password), user["id"]),
            )
            db.commit()
            session.clear()
            flash("Password changed. Please sign in again.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/password.html")


@auth_bp.get("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    from marketplace.admin import _marketplace_stats
    db = get_db()
    pending_listings = db.execute(
        """SELECT l.id, l.item_name, l.category, u.display_name AS seller_name
           FROM listings l JOIN users u ON u.id = l.seller_id
           WHERE l.status = 'published' AND l.review_status = 'pending'
           ORDER BY l.updated_at, l.id LIMIT 5"""
    ).fetchall()
    return render_template("admin/dashboard.html", stats=_marketplace_stats(), pending_listings=pending_listings)
