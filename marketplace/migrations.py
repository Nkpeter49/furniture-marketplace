"""Small, repeatable SQLite migrations for the local marketplace."""

import sqlite3


def _has_column(db: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row["name"] == column for row in db.execute(f"PRAGMA table_info({table})"))


def _stage_2_profiles_and_listings(db: sqlite3.Connection) -> None:
    if not _has_column(db, "users", "bio"):
        db.execute("ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''")
    if not _has_column(db, "users", "profile_image"):
        db.execute("ALTER TABLE users ADD COLUMN profile_image TEXT")

    db.execute(
        """CREATE TABLE IF NOT EXISTS seller_profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            business_name TEXT NOT NULL DEFAULT '',
            bio TEXT NOT NULL DEFAULT '',
            specialties TEXT NOT NULL DEFAULT '',
            profile_image TEXT,
            cover_image TEXT,
            contact_number TEXT NOT NULL DEFAULT '',
            publish_contact INTEGER NOT NULL DEFAULT 0 CHECK (publish_contact IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute(
        """INSERT OR IGNORE INTO seller_profiles (user_id, business_name)
           SELECT id, display_name FROM users WHERE role = 'seller'"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL REFERENCES users(id),
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            material TEXT NOT NULL DEFAULT '',
            condition TEXT NOT NULL DEFAULT '',
            dimensions TEXT NOT NULL DEFAULT '',
            price TEXT NOT NULL DEFAULT '',
            currency TEXT NOT NULL DEFAULT '',
            colour TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            additional_details TEXT NOT NULL DEFAULT '',
            availability TEXT NOT NULL DEFAULT 'available'
                CHECK (availability IN ('available', 'unavailable')),
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'removed')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_listings_seller_status ON listings (seller_id, status, updated_at)"
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS listing_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
            filename TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_listing_images_listing ON listing_images (listing_id, id)")


def _support_reports_and_privacy_requests(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL REFERENCES users(id),
            category TEXT NOT NULL CHECK (category IN
                ('account', 'seller_approval', 'listing', 'photo_upload', 'privacy', 'suspicious_content', 'copyright_trademark', 'other')),
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            listing_reference TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN
                ('open', 'in_progress', 'waiting_for_user', 'resolved')),
            assigned_admin_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_support_owner_updated ON support_tickets (owner_id, updated_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_support_status_updated ON support_tickets (status, updated_at)")
    db.execute(
        """CREATE TABLE IF NOT EXISTS support_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES users(id),
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_support_replies_ticket ON support_replies (ticket_id, id)")
    db.execute(
        """CREATE TABLE IF NOT EXISTS user_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER NOT NULL REFERENCES users(id),
            target_type TEXT NOT NULL CHECK (target_type IN ('listing', 'user')),
            target_id INTEGER NOT NULL,
            reason TEXT NOT NULL CHECK (reason IN
                ('fraud', 'prohibited_item', 'copyright_trademark', 'misleading_content', 'harassment', 'other')),
            details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN
                ('open', 'in_review', 'action_taken', 'no_violation', 'closed')),
            reviewer_id INTEGER REFERENCES users(id),
            admin_note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_reports_status_created ON user_reports (status, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_reports_owner_created ON user_reports (reporter_id, created_at)")
    db.execute(
        """CREATE TABLE IF NOT EXISTS privacy_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL REFERENCES users(id),
            request_type TEXT NOT NULL CHECK (request_type IN ('access', 'correction', 'export', 'closure')),
            details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'completed', 'declined')),
            admin_note TEXT NOT NULL DEFAULT '',
            reviewer_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_privacy_owner_created ON privacy_requests (owner_id, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_privacy_status_created ON privacy_requests (status, created_at)")
    db.execute(
        """CREATE TABLE IF NOT EXISTS listing_moderation (
            listing_id INTEGER PRIMARY KEY REFERENCES listings(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'hidden' CHECK (status IN ('hidden')),
            moderator_id INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS moderation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL REFERENCES user_reports(id),
            moderator_id INTEGER NOT NULL REFERENCES users(id),
            target_type TEXT NOT NULL CHECK (target_type IN ('listing', 'user')),
            target_id INTEGER NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('hide_listing', 'suspend_seller', 'no_restriction')),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_moderation_events_target ON moderation_events (target_type, target_id, created_at)")


def _storefront_favorites_and_conversations(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS favorites (
            buyer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (buyer_id, listing_id)
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_favorites_listing ON favorites (listing_id)")
    db.execute(
        """CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL REFERENCES listings(id),
            buyer_id INTEGER NOT NULL REFERENCES users(id),
            seller_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (listing_id, buyer_id),
            CHECK (buyer_id <> seller_id)
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_buyer_updated ON conversations (buyer_id, updated_at DESC)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_seller_updated ON conversations (seller_id, updated_at DESC)")
    db.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES users(id),
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id, id)")
    db.execute(
        """CREATE TRIGGER IF NOT EXISTS messages_author_must_participate
           BEFORE INSERT ON messages
           WHEN NOT EXISTS (
               SELECT 1 FROM conversations c
               WHERE c.id = NEW.conversation_id AND NEW.author_id IN (c.buyer_id, c.seller_id)
           )
           BEGIN SELECT RAISE(ABORT, 'message author must be a conversation participant'); END"""
    )


def _inventory_quantity_and_listing_history(db: sqlite3.Connection) -> None:
    if not _has_column(db, "listings", "quantity"):
        db.execute("ALTER TABLE listings ADD COLUMN quantity INTEGER CHECK (quantity IS NULL OR quantity >= 0)")
    db.execute(
        """CREATE TABLE IF NOT EXISTS listing_moderation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL REFERENCES listings(id),
            report_id INTEGER NOT NULL REFERENCES user_reports(id),
            moderator_id INTEGER NOT NULL REFERENCES users(id),
            action TEXT NOT NULL CHECK (action IN ('hide', 'restore')),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_listing_moderation_history_listing ON listing_moderation_history (listing_id, created_at)")


def _listing_approval(db: sqlite3.Connection) -> None:
    added_review_status = not _has_column(db, "listings", "review_status")
    if added_review_status:
        db.execute("ALTER TABLE listings ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected'))")
    if not _has_column(db, "listings", "review_reason"):
        db.execute("ALTER TABLE listings ADD COLUMN review_reason TEXT NOT NULL DEFAULT ''")
    if not _has_column(db, "listings", "reviewer_id"):
        db.execute("ALTER TABLE listings ADD COLUMN reviewer_id INTEGER REFERENCES users(id)")
    if not _has_column(db, "listings", "reviewed_at"):
        db.execute("ALTER TABLE listings ADD COLUMN reviewed_at TEXT")
    if added_review_status:
        db.execute("UPDATE listings SET review_status = 'approved' WHERE status = 'published'")
    db.execute("CREATE INDEX IF NOT EXISTS idx_listings_review_status ON listings (review_status, status, updated_at)")


MIGRATIONS = (
    (1, "stage_2_profiles_and_listings", _stage_2_profiles_and_listings),
    (2, "support_reports_and_privacy_requests", _support_reports_and_privacy_requests),
    (3, "storefront_favorites_and_conversations", _storefront_favorites_and_conversations),
    (4, "inventory_quantity_and_listing_history", _inventory_quantity_and_listing_history),
    (5, "listing_approval", _listing_approval),
)


def apply_migrations(db: sqlite3.Connection) -> None:
    """Apply each migration once, atomically, without replacing existing rows."""
    db.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    db.commit()
    for version, name, migration in MIGRATIONS:
        if db.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
            continue
        db.execute("BEGIN IMMEDIATE")
        try:
            migration(db)
            db.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, name),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
