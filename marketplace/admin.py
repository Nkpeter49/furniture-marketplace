"""Administrator-only seller approval and account management."""

import click
import sqlite3
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for
from werkzeug.security import generate_password_hash

from marketplace.database import get_db, init_db
from marketplace.security import current_user, role_required
from marketplace.auth import MIN_PASSWORD_LENGTH, valid_email
from marketplace.media import image_path


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _marketplace_stats():
    db = get_db()
    return {
        "buyers": db.execute("SELECT COUNT(*) FROM users WHERE role = 'buyer' AND account_status = 'active'").fetchone()[0],
        "sellers": db.execute("SELECT COUNT(*) FROM users WHERE role = 'seller' AND account_status = 'active'").fetchone()[0],
        "pending_sellers": db.execute("SELECT COUNT(*) FROM users WHERE role = 'seller' AND account_status = 'active' AND seller_approval = 'pending'").fetchone()[0],
        "pending_listings": db.execute("SELECT COUNT(*) FROM listings WHERE status = 'published' AND review_status = 'pending'").fetchone()[0],
        "published_listings": db.execute("SELECT COUNT(*) FROM listings l JOIN users u ON u.id = l.seller_id WHERE l.status = 'published' AND l.review_status = 'approved' AND u.account_status = 'active' AND u.seller_approval = 'approved' AND NOT EXISTS (SELECT 1 FROM listing_moderation lm WHERE lm.listing_id = l.id AND lm.status = 'hidden')").fetchone()[0],
        "conversations": db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
        "open_reports": db.execute("SELECT COUNT(*) FROM user_reports WHERE status IN ('open', 'in_review')").fetchone()[0],
        "open_support": db.execute("SELECT COUNT(*) FROM support_tickets WHERE status <> 'resolved'").fetchone()[0],
    }


@admin_bp.get("/dashboard")
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html", stats=_marketplace_stats())


@admin_bp.get("/listings")
@role_required("admin")
def listings_to_review():
    rows = get_db().execute(
        """SELECT l.*, u.display_name AS seller_name, u.email AS seller_email, sp.business_name,
                  (SELECT id FROM listing_images WHERE listing_id = l.id ORDER BY id LIMIT 1) AS cover_image_id
           FROM listings l JOIN users u ON u.id = l.seller_id
           LEFT JOIN seller_profiles sp ON sp.user_id = u.id
           WHERE l.status = 'published' AND l.review_status = 'pending'
           ORDER BY l.updated_at, l.id"""
    ).fetchall()
    image_rows = {row["id"]: get_db().execute("SELECT id FROM listing_images WHERE listing_id = ? ORDER BY id", (row["id"],)).fetchall() for row in rows}
    return render_template("admin/listings.html", listings=rows, review_images=image_rows)


@admin_bp.get("/listing-images/<int:image_id>")
@role_required("admin")
def listing_review_image(image_id: int):
    row = get_db().execute("SELECT filename FROM listing_images WHERE id = ?", (image_id,)).fetchone()
    if row is None:
        abort(404)
    path = image_path(row["filename"], current_app.instance_path)
    if path is None:
        abort(404)
    return send_file(path, conditional=True, max_age=0, download_name=path.name)


@admin_bp.post("/listings/<int:listing_id>/review")
@role_required("admin")
def review_listing(listing_id: int):
    action = request.form.get("action", "")
    reason = request.form.get("reason", "").strip()
    if action not in {"approve", "reject"} or len(reason) > 300 or (action == "reject" and not 5 <= len(reason) <= 300):
        abort(400, description="Choose approve, or provide a rejection reason of 5 to 300 characters.")
    db = get_db()
    row = db.execute("SELECT id FROM listings WHERE id = ? AND status = 'published' AND review_status = 'pending'", (listing_id,)).fetchone()
    if row is None:
        abort(404)
    db.execute(
        "UPDATE listings SET review_status = ?, review_reason = ?, reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?",
        ("approved" if action == "approve" else "rejected", reason if action == "reject" else "", current_user()["id"], listing_id),
    )
    db.commit()
    flash("Listing approved." if action == "approve" else "Listing rejected with your reason.", "success")
    return redirect(url_for("admin.listings_to_review"))


@admin_bp.get("/users")
@role_required("admin")
def users():
    rows = get_db().execute(
        """SELECT id, email, display_name, role, account_status, seller_approval, created_at
           FROM users WHERE role IN ('buyer', 'seller') ORDER BY created_at, id"""
    ).fetchall()
    return render_template("admin/users.html", users=rows)


@admin_bp.post("/sellers/<int:user_id>/approve")
@role_required("admin")
def approve_seller(user_id: int):
    db = get_db()
    seller = db.execute(
        "SELECT id, account_status, seller_approval FROM users WHERE id = ? AND role = 'seller'",
        (user_id,),
    ).fetchone()
    if seller is None:
        abort(404)
    if seller["account_status"] != "active":
        flash("Reactivate this seller account before approving it.", "error")
    else:
        db.execute(
            "UPDATE users SET seller_approval = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,),
        )
        db.commit()
        flash("Seller approved. They can now manage and publish their furniture listings.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/status")
@role_required("admin")
def change_user_status(user_id: int):
    new_status = request.form.get("account_status", "")
    if new_status not in {"active", "suspended"}:
        abort(400)
    if new_status == "suspended" and request.form.get("confirm_suspend") != "yes":
        abort(400, description="Confirm that you want to suspend this account.")
    db = get_db()
    target = db.execute(
        "SELECT id, role FROM users WHERE id = ? AND role IN ('buyer', 'seller')",
        (user_id,),
    ).fetchone()
    if target is None:
        abort(404)
    db.execute(
        "UPDATE users SET account_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, user_id),
    )
    db.commit()
    flash(f"Account status changed to {new_status}.", "success")
    return redirect(url_for("admin.users"))


def register_admin_commands(app) -> None:
    @app.cli.command("init-admin")
    def init_admin_command():
        """Initialize the database and safely prompt for the first admin."""
        init_db()
        db = get_db()
        exists = db.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if exists:
            raise click.ClickException("An administrator already exists; no account was created.")

        email = click.prompt("Administrator email").strip().lower()
        if not valid_email(email):
            raise click.ClickException("Enter a valid email address and run the command again.")
        password = click.prompt(
            "Administrator password",
            hide_input=True,
            confirmation_prompt=True,
        )
        if len(password) < MIN_PASSWORD_LENGTH:
            raise click.ClickException(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters; run the command again."
            )
        try:
            db.execute(
                """INSERT INTO users (email, display_name, password_hash, role, seller_approval)
                   VALUES (?, 'Administrator', ?, 'admin', NULL)""",
                (email, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            if "users.role" in str(exc):
                raise click.ClickException("An administrator already exists; no account was created.") from exc
            if "users.email" in str(exc):
                raise click.ClickException("That email address is already in use.") from exc
            raise
        click.echo("Administrator created. Sign in through the local website.")
