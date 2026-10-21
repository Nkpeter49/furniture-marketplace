"""Server-side sign-in, role, and CSRF checks."""

from functools import wraps

from flask import abort, g, redirect, request, url_for


def current_user():
    return getattr(g, "user", None)


def public_user(user):
    """Return only account fields templates are allowed to display."""
    if user is None:
        return None
    return {
        key: user[key]
        for key in ("id", "email", "display_name", "role", "account_status", "seller_approval")
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user()["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def approved_seller_required(view):
    """Require an active seller approved by an administrator."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        user = current_user()
        if user["role"] != "seller":
            abort(403)
        if user["account_status"] != "active" or user["seller_approval"] != "approved":
            abort(403)
        return view(*args, **kwargs)

    return wrapped
