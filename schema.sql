CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('buyer', 'seller', 'admin')),
    account_status TEXT NOT NULL DEFAULT 'active'
        CHECK (account_status IN ('active', 'suspended')),
    seller_approval TEXT
        CHECK (seller_approval IS NULL OR seller_approval IN ('pending', 'approved')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (role = 'seller' AND seller_approval IS NOT NULL)
        OR (role IN ('buyer', 'admin') AND seller_approval IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_users_role_status
    ON users (role, account_status, seller_approval);

CREATE UNIQUE INDEX IF NOT EXISTS idx_single_admin_account
    ON users (role) WHERE role = 'admin';
