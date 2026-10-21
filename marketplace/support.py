"""Help, support, user reports, and privacy-request workflows for the local MVP."""

import sqlite3

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from marketplace.database import get_db
from marketplace.policies import POLICIES
from marketplace.security import current_user, login_required, role_required


support_bp = Blueprint("support", __name__)
TICKET_CATEGORIES = {
    "account": "Login or account access",
    "seller_approval": "Seller approval",
    "listing": "Listing management",
    "photo_upload": "Photo uploads",
    "privacy": "Privacy or data request",
    "copyright_trademark": "Copyright or trademark complaint or response",
    "suspicious_content": "Suspicious listing or user",
    "other": "Other",
}
TICKET_STATUSES = {"open", "in_progress", "waiting_for_user", "resolved"}
REPORT_REASONS = {
    "fraud": "Fraud or scam concern",
    "prohibited_item": "Prohibited or unsafe item",
    "copyright_trademark": "Copyright or trademark infringement",
    "misleading_content": "Misleading listing content",
    "harassment": "Harassment or abuse",
    "other": "Other concern",
}
REPORT_STATUSES = {"open", "in_review", "action_taken", "no_violation", "closed"}
PRIVACY_TYPES = {
    "access": "Access my information",
    "correction": "Correct my information",
    "export": "Request an export",
    "closure": "Request account closure",
}
PRIVACY_STATUSES = {"open", "in_progress", "completed", "declined"}

HELP_ARTICLES = [
    {"title": "I cannot sign in", "category": "Accounts", "text": "Check that the email address is the one used at registration. If the account is suspended, contact support for a review. Never send your password or a sign-in code in a support request."},
    {"title": "Seller approval", "category": "Selling", "text": "New seller accounts begin pending. An administrator must approve a seller before business-profile and listing-management actions are available. Approval time is not guaranteed in this local prototype."},
    {"title": "Create and manage a listing", "category": "Selling", "text": "Approved active sellers can create, edit, publish, mark unavailable, and remove their own listings. Only published listings appear on the seller's public profile. Availability is seller-reported."},
    {"title": "Photo upload requirements", "category": "Selling", "text": "Upload JPEG, PNG, or WebP files up to 5 MB each. Images are decoded and re-encoded locally, and animated or overly large images are rejected. Try reducing image dimensions if an upload fails."},
    {"title": "Your privacy and profile", "category": "Privacy", "text": "Buyer profiles, email addresses, support requests, and reports are private. Seller business fields are public only for active approved sellers; contact numbers are public only if the seller turns on contact publication."},
    {"title": "Report suspicious content", "category": "Safety", "text": "Use the Report listing or Report seller action and describe the concern. Reports are visible to authorized administrators for review. This prototype does not provide 24/7 human support."},
    {"title": "Suspended account", "category": "Accounts", "text": "A suspended account cannot use protected functions. Use Contact Support to request a review. Do not create another account to bypass a restriction."},
    {"title": "AI product drafts", "category": "AI", "text": "Product-description drafts use Ollama on the local computer. Review every draft and check it against seller-provided facts. The app has no cloud AI fallback and does not send drafts automatically."},
]


@support_bp.get("/help")
def help_center():
    query = request.args.get("q", "").strip()[:100]
    words = query.casefold().split()
    articles = [article for article in HELP_ARTICLES if all(
        word in (article["title"] + " " + article["category"] + " " + article["text"]).casefold()
        for word in words
    )]
    return render_template("support/help.html", articles=articles, query=query)


@support_bp.get("/policies")
def policy_index():
    return render_template("policies/index.html", policies=POLICIES)


@support_bp.get("/policies/<slug>")
def policy_page(slug: str):
    policy = POLICIES.get(slug)
    if policy is None:
        abort(404)
    return render_template("policies/page.html", slug=slug, policy=policy)


@support_bp.route("/support", methods=["GET", "POST"])
@login_required
def create_ticket():
    if request.method == "POST":
        category = request.form.get("category", "")
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        listing_reference = request.form.get("listing_reference", "").strip()
        errors = []
        if category not in TICKET_CATEGORIES:
            errors.append("Choose a support category.")
        if not 3 <= len(subject) <= 120:
            errors.append("Subject must be between 3 and 120 characters.")
        if not 10 <= len(description) <= 4000:
            errors.append("Description must be between 10 and 4,000 characters.")
        if len(listing_reference) > 80:
            errors.append("The listing reference must be 80 characters or fewer.")
        if errors:
            return _form_error("support/ticket_form.html", errors, categories=TICKET_CATEGORIES, values=request.form), 400
        db = get_db()
        cursor = db.execute(
            """INSERT INTO support_tickets (owner_id, category, subject, description, listing_reference)
               VALUES (?, ?, ?, ?, ?)""",
            (current_user()["id"], category, subject, description, listing_reference),
        )
        db.commit()
        flash("Your support request was recorded. This local prototype does not promise a response time.", "success")
        return redirect(url_for("support.ticket_detail", ticket_id=cursor.lastrowid))
    return render_template("support/ticket_form.html", categories=TICKET_CATEGORIES, values={})


@support_bp.get("/support/requests")
@login_required
def my_tickets():
    tickets = get_db().execute(
        """SELECT id, category, subject, status, created_at, updated_at FROM support_tickets
           WHERE owner_id = ? ORDER BY updated_at DESC, id DESC""",
        (current_user()["id"],),
    ).fetchall()
    return render_template("support/my_tickets.html", tickets=tickets)


@support_bp.route("/support/requests/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def ticket_detail(ticket_id: int):
    ticket = get_db().execute(
        "SELECT * FROM support_tickets WHERE id = ? AND owner_id = ?",
        (ticket_id, current_user()["id"]),
    ).fetchone()
    if ticket is None:
        abort(404)
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not 1 <= len(body) <= 4000:
            flash("Your response must be between 1 and 4,000 characters.", "error")
            return redirect(url_for("support.ticket_detail", ticket_id=ticket_id))
        db = get_db()
        db.execute("INSERT INTO support_replies (ticket_id, author_id, body) VALUES (?, ?, ?)",
                   (ticket_id, current_user()["id"], body))
        db.execute("UPDATE support_tickets SET status = 'open', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
        db.commit()
        flash("Your response was added to the support request.", "success")
        return redirect(url_for("support.ticket_detail", ticket_id=ticket_id))
    replies = get_db().execute(
        """SELECT r.id, r.body, r.created_at, u.role, u.display_name
           FROM support_replies r JOIN users u ON u.id = r.author_id
           WHERE r.ticket_id = ? ORDER BY r.id""", (ticket_id,),
    ).fetchall()
    return render_template("support/ticket_detail.html", ticket=ticket, replies=replies)


@support_bp.get("/admin/support")
@role_required("admin")
def admin_tickets():
    tickets = get_db().execute(
        """SELECT t.id, t.category, t.subject, t.status, t.updated_at, u.display_name AS requester
           FROM support_tickets t JOIN users u ON u.id = t.owner_id
           ORDER BY CASE t.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
                    t.updated_at DESC"""
    ).fetchall()
    return render_template("admin/support_list.html", tickets=tickets)


@support_bp.get("/admin/support/<int:ticket_id>")
@role_required("admin")
def admin_ticket(ticket_id: int):
    ticket = get_db().execute(
        """SELECT t.*, u.display_name AS requester, u.email AS requester_email
           FROM support_tickets t JOIN users u ON u.id = t.owner_id WHERE t.id = ?""", (ticket_id,),
    ).fetchone()
    if ticket is None:
        abort(404)
    replies = _ticket_replies(ticket_id)
    return render_template("admin/support_detail.html", ticket=ticket, replies=replies, statuses=TICKET_STATUSES)


@support_bp.post("/admin/support/<int:ticket_id>")
@role_required("admin")
def update_admin_ticket(ticket_id: int):
    ticket = get_db().execute("SELECT id FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
    if ticket is None:
        abort(404)
    action = request.form.get("action", "")
    db = get_db()
    if action == "assign":
        db.execute("UPDATE support_tickets SET assigned_admin_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (current_user()["id"], ticket_id))
        flash("Support request assigned to you.", "success")
    elif action == "status":
        status = request.form.get("status", "")
        if status not in TICKET_STATUSES:
            abort(400)
        db.execute("UPDATE support_tickets SET status = ?, assigned_admin_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (status, current_user()["id"], ticket_id))
        flash("Support request status updated.", "success")
    elif action == "reply":
        body = request.form.get("body", "").strip()
        if not 1 <= len(body) <= 4000:
            flash("Response must be between 1 and 4,000 characters.", "error")
            return redirect(url_for("support.admin_ticket", ticket_id=ticket_id))
        db.execute("INSERT INTO support_replies (ticket_id, author_id, body) VALUES (?, ?, ?)",
                   (ticket_id, current_user()["id"], body))
        db.execute("UPDATE support_tickets SET assigned_admin_id = ?, status = 'waiting_for_user', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (current_user()["id"], ticket_id))
        flash("Response sent to the user's request inbox.", "success")
    else:
        abort(400)
    db.commit()
    return redirect(url_for("support.admin_ticket", ticket_id=ticket_id))


@support_bp.route("/report/listing/<int:listing_id>", methods=["GET", "POST"])
@login_required
def report_listing(listing_id: int):
    listing = get_db().execute(
        """SELECT l.id, l.seller_id, l.item_name FROM listings l
           JOIN users u ON u.id = l.seller_id
           WHERE l.id = ? AND l.status = 'published' AND u.role = 'seller'
             AND u.account_status = 'active' AND u.seller_approval = 'approved'
             AND NOT EXISTS (SELECT 1 FROM listing_moderation lm WHERE lm.listing_id = l.id AND lm.status = 'hidden')""", (listing_id,),
    ).fetchone()
    if listing is None:
        abort(404)
    return _submit_report("listing", listing_id, target_label=listing["item_name"], target_user_id=listing["seller_id"])


@support_bp.route("/report/user/<int:user_id>", methods=["GET", "POST"])
@login_required
def report_user(user_id: int):
    if user_id == current_user()["id"]:
        abort(400, description="You cannot report your own account.")
    target = get_db().execute(
        """SELECT id, role, display_name FROM users WHERE id = ? AND role = 'seller'
           AND account_status = 'active' AND seller_approval = 'approved'""", (user_id,),
    ).fetchone()
    if target is None:
        abort(404)
    return _submit_report("user", user_id, target_label=target["display_name"], target_user_id=user_id)


def _submit_report(target_type: str, target_id: int, target_label: str, target_user_id: int):
    if request.method == "POST":
        reason = request.form.get("reason", "")
        details = request.form.get("details", "").strip()
        if reason not in REPORT_REASONS:
            flash("Choose a report reason.", "error")
        elif not 10 <= len(details) <= 4000:
            flash("Explain the concern in 10 to 4,000 characters.", "error")
        else:
            get_db().execute(
                "INSERT INTO user_reports (reporter_id, target_type, target_id, reason, details) VALUES (?, ?, ?, ?, ?)",
                (current_user()["id"], target_type, target_id, reason, details),
            )
            get_db().commit()
            flash("Your report was submitted for administrator review.", "success")
            return redirect(url_for("support.my_reports"))
    return render_template("support/report_form.html", target_type=target_type, target_id=target_id,
                           target_label=target_label, target_user_id=target_user_id, reasons=REPORT_REASONS)


@support_bp.get("/reports/mine")
@login_required
def my_reports():
    reports = get_db().execute(
        """SELECT id, target_type, reason, status, created_at FROM user_reports
           WHERE reporter_id = ? ORDER BY created_at DESC, id DESC""", (current_user()["id"],),
    ).fetchall()
    return render_template("support/my_reports.html", reports=reports)


@support_bp.get("/admin/reports")
@role_required("admin")
def admin_reports():
    reports = get_db().execute(
        """SELECT r.id, r.target_type, r.target_id, r.reason, r.status, r.created_at,
                  u.display_name AS reporter
           FROM user_reports r JOIN users u ON u.id = r.reporter_id
           ORDER BY CASE r.status WHEN 'open' THEN 0 WHEN 'in_review' THEN 1 ELSE 2 END, r.created_at DESC"""
    ).fetchall()
    return render_template("admin/reports.html", reports=reports)


@support_bp.get("/admin/reports/<int:report_id>")
@role_required("admin")
def admin_report(report_id: int):
    report = get_db().execute(
        """SELECT r.*, u.display_name AS reporter_name, u.email AS reporter_email
           FROM user_reports r JOIN users u ON u.id = r.reporter_id WHERE r.id = ?""", (report_id,),
    ).fetchone()
    if report is None:
        abort(404)
    target = _report_target(report)
    return render_template("admin/report_detail.html", report=report, target=target, statuses=REPORT_STATUSES)


@support_bp.post("/admin/reports/<int:report_id>")
@role_required("admin")
def update_admin_report(report_id: int):
    status = request.form.get("status", "")
    action = request.form.get("content_action", "none")
    note = request.form.get("admin_note", "").strip()
    if status not in REPORT_STATUSES or len(note) > 1000:
        abort(400)
    report = get_db().execute("SELECT * FROM user_reports WHERE id = ?", (report_id,)).fetchone()
    if report is None:
        abort(404)
    if action not in {"none", "hide_listing", "restore_listing", "suspend_seller"}:
        abort(400)
    if status == "action_taken" and (action == "none" or len(note) < 10):
        flash("Choose a moderation action and explain the decision (at least 10 characters).", "error")
        return redirect(url_for("support.admin_report", report_id=report_id))
    if status != "action_taken" and action != "none":
        abort(400)
    if action in {"hide_listing", "restore_listing"} and report["target_type"] != "listing":
        abort(400)

    db = get_db()
    try:
        if action == "hide_listing":
            target = db.execute("SELECT id FROM listings WHERE id = ?", (report["target_id"],)).fetchone()
            if target is None:
                abort(400)
            db.execute(
                """INSERT INTO listing_moderation (listing_id, moderator_id, reason)
                   VALUES (?, ?, ?) ON CONFLICT(listing_id) DO UPDATE SET
                   moderator_id = excluded.moderator_id, reason = excluded.reason, updated_at = CURRENT_TIMESTAMP""",
                (report["target_id"], current_user()["id"], note),
            )
            db.execute(
                "INSERT INTO listing_moderation_history (listing_id, report_id, moderator_id, action, reason) VALUES (?, ?, ?, 'hide', ?)",
                (report["target_id"], report_id, current_user()["id"], note),
            )
        elif action == "restore_listing":
            hidden = db.execute(
                "SELECT 1 FROM listing_moderation WHERE listing_id = ? AND status = 'hidden'",
                (report["target_id"],),
            ).fetchone()
            if hidden is None:
                flash("This listing is not under a moderation hold, so there is nothing to restore.", "error")
                return redirect(url_for("support.admin_report", report_id=report_id))
            db.execute("DELETE FROM listing_moderation WHERE listing_id = ?", (report["target_id"],))
            db.execute(
                "INSERT INTO listing_moderation_history (listing_id, report_id, moderator_id, action, reason) VALUES (?, ?, ?, 'restore', ?)",
                (report["target_id"], report_id, current_user()["id"], note),
            )
        elif action == "suspend_seller":
            seller_id = report["target_id"]
            if report["target_type"] == "listing":
                listing = db.execute("SELECT seller_id FROM listings WHERE id = ?", (report["target_id"],)).fetchone()
                if listing is None:
                    abort(400)
                seller_id = listing["seller_id"]
            seller = db.execute("SELECT id FROM users WHERE id = ? AND role = 'seller'", (seller_id,)).fetchone()
            if seller is None:
                abort(400)
            db.execute("UPDATE users SET account_status = 'suspended', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (seller_id,))
        db.execute(
            """UPDATE user_reports SET status = ?, admin_note = ?, reviewer_id = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""", (status, note, current_user()["id"], report_id),
        )
        if status == "action_taken" and action != "restore_listing":
            db.execute(
                """INSERT INTO moderation_events
                   (report_id, moderator_id, target_type, target_id, action, reason)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (report_id, current_user()["id"], report["target_type"], report["target_id"], action, note),
            )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.error("Report moderation update failed; exception details suppressed")
        flash("The moderation update could not be saved. No change was kept.", "error")
        return redirect(url_for("support.admin_report", report_id=report_id))
    flash("Report review saved.", "success")
    return redirect(url_for("support.admin_report", report_id=report_id))


@support_bp.route("/privacy/requests", methods=["GET", "POST"])
@login_required
def privacy_requests():
    if request.method == "POST":
        request_type = request.form.get("request_type", "")
        details = request.form.get("details", "").strip()
        if request_type not in PRIVACY_TYPES:
            flash("Choose a privacy request type.", "error")
        elif not 10 <= len(details) <= 2000:
            flash("Add 10 to 2,000 characters describing what you need.", "error")
        else:
            get_db().execute(
                "INSERT INTO privacy_requests (owner_id, request_type, details) VALUES (?, ?, ?)",
                (current_user()["id"], request_type, details),
            )
            get_db().commit()
            flash("Your request was recorded for review. This does not immediately delete or export account data.", "success")
            return redirect(url_for("support.privacy_requests"))
    requests = get_db().execute(
        """SELECT id, request_type, details, status, admin_note, created_at, updated_at
           FROM privacy_requests WHERE owner_id = ? ORDER BY created_at DESC, id DESC""",
        (current_user()["id"],),
    ).fetchall()
    return render_template("support/privacy_requests.html", requests=requests, request_types=PRIVACY_TYPES)


@support_bp.get("/admin/privacy-requests")
@role_required("admin")
def admin_privacy_requests():
    requests = get_db().execute(
        """SELECT p.id, p.request_type, p.status, p.created_at, u.display_name AS requester
           FROM privacy_requests p JOIN users u ON u.id = p.owner_id
           ORDER BY p.created_at"""
    ).fetchall()
    return render_template("admin/privacy_list.html", requests=requests)


@support_bp.get("/admin/privacy-requests/<int:request_id>")
@role_required("admin")
def admin_privacy_request(request_id: int):
    item = get_db().execute(
        """SELECT p.*, u.display_name AS requester, u.email AS requester_email
           FROM privacy_requests p JOIN users u ON u.id = p.owner_id WHERE p.id = ?""", (request_id,),
    ).fetchone()
    if item is None:
        abort(404)
    return render_template("admin/privacy_detail.html", item=item, statuses=PRIVACY_STATUSES)


@support_bp.post("/admin/privacy-requests/<int:request_id>")
@role_required("admin")
def update_admin_privacy_request(request_id: int):
    status = request.form.get("status", "")
    note = request.form.get("admin_note", "").strip()
    if status not in PRIVACY_STATUSES or len(note) > 2000:
        abort(400)
    cursor = get_db().execute(
        """UPDATE privacy_requests SET status = ?, admin_note = ?, reviewer_id = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""", (status, note, current_user()["id"], request_id),
    )
    if cursor.rowcount == 0:
        abort(404)
    get_db().commit()
    flash("Privacy request review saved. Complete any requested data action separately and record the outcome.", "success")
    return redirect(url_for("support.admin_privacy_request", request_id=request_id))


def _report_target(report):
    if report["target_type"] == "listing":
        return get_db().execute(
            """SELECT l.item_name AS label, lm.status AS moderation_status
               FROM listings l LEFT JOIN listing_moderation lm ON lm.listing_id = l.id WHERE l.id = ?""",
            (report["target_id"],),
        ).fetchone()
    return get_db().execute("SELECT display_name AS label FROM users WHERE id = ?", (report["target_id"],)).fetchone()


def _ticket_replies(ticket_id: int):
    return get_db().execute(
        """SELECT r.id, r.body, r.created_at, u.role, u.display_name
           FROM support_replies r JOIN users u ON u.id = r.author_id
           WHERE r.ticket_id = ? ORDER BY r.id""", (ticket_id,),
    ).fetchall()


def _form_error(template: str, errors: list[str], **context):
    for error in errors:
        flash(error, "error")
    return render_template(template, **context)
