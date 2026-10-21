---
doc: spec
status: approved
---

# Furniture Marketplace — Technical Specification and Readiness

This blueprint separates the local Windows prototype from a future public service. Profiles, listings, buyer discovery, participant-scoped messaging, support workflows, and local AI drafts are implemented and automatically tested; public-production architecture remains a target, not a claim of readiness.

## How It Works in Plain Language

Flask receives browser requests, checks the signed-in user's role and ownership, reads/writes marketplace records, and returns pages. SQLite and files currently live on the developer's computer. Ollama currently listens on the same computer. For public use, the browser must connect through HTTPS to a protected web entry point; the application, PostgreSQL, private image storage, and Ollama should communicate over private connections, with only the web entry point publicly reachable.

## Current State: Inspected, Tested, and Unverified

### Present in the repository

- Python/Flask application factory in `app.py`; auth and admin blueprints in `marketplace/`.
- SQLite user schema and database initialization in `schema.sql` and `marketplace/database.py`.
- Buyer/seller registration, login/logout, private buyer profile/password page, approved seller business profile, seller-owned listing management, limited public seller pages, role-protected dashboards, admin initialization CLI, seller approval, and account suspend/reactivate controls.
- Pillow-based upload decoding and re-encoding with byte, format, animation, dimension, and pixel limits; generated private local filenames and protected media routes.
- Additive SQLite migrations 1–4 for profiles/listings, support and moderation, favorites/conversations, optional inventory quantity, and listing hide/restore history. The existing database was backed up before each new schema addition; account/password/status rows were compared and database/foreign-key integrity checked after migration.
- `requirements.txt` records Pillow 13.x. Automated tests cover Stage 2 routes, authorization, privacy, upload rejection, CSRF, migration repeatability, and Stage 1/product behavior.
- Searchable Help Center, private owner-scoped support requests/replies, administrator assignment/status/replies, private user reports with administrator review, and privacy access/correction/export/closure request intake.
- Public marketplace search, category/condition/availability/price filters, product detail pages, private buyer-owned favorites, buyer listing inquiries, participant-only conversations, and seller inquiry management. Admin dashboard displays aggregate counts and no message bodies.
- Seller listings allow optional seller-reported quantity. Admin report review can hide or restore a listing with an explicit history event.
- Draft policy pages for Terms, Privacy, Cookies/Sessions, Community Standards, Seller Rules, Buyer Safety, IP Complaints, Moderation, Suspension/Appeals, Account Data Requests, and AI disclosure. Operator/jurisdiction/contact/date/retention placeholders remain visible.
- Security additions include configurable app identity/secret/cookie settings, safe generic errors, sanitized exception logging, CSP and other security headers, local in-process throttling, no-store for private pages, and confirmation prompts for suspension/listing removal.
- Session-bound CSRF protection, Werkzeug password hashing, persistent development secret and database under ignored `instance/`.
- Local product descriptions and seller reply drafts use Ollama at `127.0.0.1:11434`, conservative output checks, and deterministic safe fallbacks labeled as not AI-generated. Reply drafts remain editable and are not inserted into message history until the seller submits the separate send form.
- `tests/test_app.py` exercises the product-description flow and Stage 1 authentication/roles. Test fixtures use temporary databases.

### Verification in the current local build

On 2026-10-21, ` .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v ` ran 43 tests and all passed with no failures or errors. Tests use temporary databases and do not contact Ollama. Separate real requests to local `qwen3:0.6b` confirmed the product flow safely formatted an exact JSON echo of seller facts. A reply output with an unsupported delivery claim was rejected and replaced by a safe labeled fallback; it did not send a message. The current database migration was applied after backup; three existing accounts, their password hashes, statuses and roles, and existing table counts were unchanged; SQLite integrity and foreign-key checks passed. Browser review remains pending.

### Explicitly unverified or absent

- Stage 1 browser permission checks were completed and the learner confirmed they all passed.
- Stage 2 has not yet been reviewed by the learner in a browser. Its seller page is a limited profile page, not a general storefront.
- Learner browser review of the current storefront, messaging, profiles, support, and admin pages remains pending. Moderation is a small local workflow without full case management, restoration appeals, or notifications.
- No public deployment, TLS, domain, production secret management, shared production rate limiting, email verification/recovery, MFA, production backups/restore, monitoring, completed legal review, or independent security/load review has been verified.
- No production database migration has been designed. Existing local `instance/` data must be preserved.
- Automated support/privacy/report-policy checks pass, but learner browser review is pending. Current moderation is a small local workflow (hide a listing or suspend a seller with an audit event), not a full appeals or case-management system.

## Proposed Architecture

### Local learning and demo environment

- Flask remains the application framework; use the existing `.venv` on Windows.
- SQLite remains suitable for the single-computer prototype, with user/listing/message records on local disk. It is not the production choice for a public marketplace with concurrent writers, multiple app workers, operational failover, and managed backups.
- Existing `instance/` holds the local secret/database; future local uploads belong under a dedicated ignored upload directory there. Do not commit databases, upload data, logs, secrets, or real seller/customer records.
- Ollama remains bound to `127.0.0.1:11434` on the local computer. Model output is untrusted input and goes through the app's safety/fallback path.

### Public deployment target (not configured)

1. **Public edge:** domain DNS points to a managed HTTPS reverse proxy/load balancer. Only web ports 80/443 are public; redirect HTTP to HTTPS, apply request limits, and forward trusted proxy headers correctly.
2. **Web application:** Flask application served by a production WSGI server, isolated from the public network. No Flask development server or debugger in production. Use separate development/staging/production configuration.
3. **Database:** PostgreSQL in a private network with least-privilege app credentials, encrypted transport/storage where supported, automated backups, and restore verification. SQLite remains local-only; write and test a controlled migration before production cutover.
4. **Images:** private object storage or equivalently isolated media storage, separate from executable app files. Enforce size/type/dimension limits; verify content, decode/re-encode safe formats, generate opaque keys, never concatenate user paths, and serve only images for currently public listings through an authorization-aware route or short-lived read access. Private/unpublished images must not be world-readable.
5. **Local AI:** Ollama runs on the same controlled private host or a private service network. Bind only to loopback/private interfaces, firewall its port, allow requests only from the app, use timeouts/concurrency and prompt-size limits, and do not route to a cloud model. Public requests never connect directly to Ollama. Measure CPU/RAM/latency and constrain request volume before inviting users.
6. **Operations:** managed secret storage, redacted structured logs, health checks, error monitoring without message bodies, alerts, encrypted database/media backups, documented retention, restore drills, and incident response.

Hosting vendor, region, domain/DNS, PostgreSQL service, object storage, email provider, model host, and recurring budget remain undecided. Compare total cost and privacy/data-processing terms before selecting them; no provider or price is assumed here.

## Data Design

The local schema currently contains only users. The following is a target logical model, not a migration script:

- `users`: unique normalized email, display name, password hash, role, account status, seller approval, timestamps; never return hashes to templates/API.
- `users` profile fields: buyer display name, short private bio, optional profile image key; never include email, password hash, sessions, or private conversations in a public profile projection.
- `seller_profiles`: one-to-one user FK; public business display name, biography, specialties, profile and cover image keys; optional contact number plus an explicit `publish_contact` choice; only active/approved sellers are publicly queryable.
- `listings`: seller owner FK, title/category, material/condition/dimensions/colour, price plus currency, description/additional details, availability state/quantity, publication/moderation state, timestamps.
- `listing_images`: listing FK, opaque object key, safe detected media type, size/dimensions, order, timestamps; file bytes live outside the relational DB.
- `favorites`: buyer/listing unique pair.
- `conversations`: listing, buyer, seller IDs, state, created/updated timestamps; enforce participant consistency and uniqueness policy.
- `messages`: conversation FK, sender FK, bounded plain-text body, timestamps; index by conversation/time. Keep access by participant query, not guessed IDs.
- `reports`: reporter, target listing/account, reason, status, reviewer/action timestamps; limit access to reporter and authorized moderators.
- `moderation_events` and `audit_events`: actor, action, target, reason and timestamp; no credentials or unnecessary message contents.

Use foreign keys, constraints, indexes for search/ownership/date, parameterized queries/ORM statements, and transactions. Decide whether PostgreSQL full-text search or simple indexed matching is enough after measuring dataset needs. Message and personal-data retention and account deletion must be explicitly designed before public release.

### Stage 2 profile migration and serving rules

- Add a numbered, additive SQLite migration recorded in a `schema_migrations` table. It adds only nullable/defaulted profile fields and a one-to-one seller profile table; it never drops/recreates `users`, changes IDs/password hashes/roles/approval, or manufactures accounts.
- Make the migration repeatable and transactional: detect an applied migration version, inspect existing columns before adding them, create indexes/tables idempotently, and fail without partial writes. Run tests against a synthetic Stage 1 database and a temporary copy of the current DB before applying to the local working database. Preserve an untouched backup and verify row counts and account statuses before/after.
- Keep profile text and visibility settings in SQLite; image bytes live in a private local media directory outside templates/static/source. Store random generated filenames, never client paths. Store only server-generated opaque keys in the database.
- Pillow 13.x is installed in `.venv` and recorded in `requirements.txt`. The implementation allow-lists JPEG/PNG/WebP input, decodes and re-encodes it, strips source metadata, rejects animated files, and enforces 5 MB, 6000-pixel-side, and 16-megapixel limits. Generated names and media routes avoid using a user-supplied filesystem path.
- Buyer profile routes require the signed-in buyer owner; buyer profile details/photos are not public in Stage 2. Seller edit/upload routes require the matching seller account and active/approved status. Public seller route queries only approved, active seller business fields and that seller's published listings. A separate public-field projection prevents accidental rendering of email/password/session values.
- Buyer storefront reads are separate from seller-owner listing management. Favorites and conversations are owner/participant-scoped on every query. Price filters exclude listings whose price is blank.

## Authorization and Security Design

- Centralize authentication/role/ownership checks; every route and object lookup checks the current account status, role, and owner/participant scope. An obscured UI control is not a permission control.
- Use secure password hashing, generic login failures, reauthentication for sensitive account/security changes, session rotation on login/password changes, logout invalidation, and production cookie flags `Secure`, `HttpOnly`, and appropriate `SameSite`.
- Use CSRF protection on every state-changing browser form/request, including JSON endpoints; validate content type, field lengths, numeric/currency ranges, and request size server-side; encode user content when rendering.
- Add throttling for login, registration, password-reset, message, report, and AI endpoints; protect against enumeration and abuse. Admin MFA is a public-launch requirement. Email verification/reset requires a selected service and carefully scoped one-time tokens.
- Image upload: allow-list formats, check actual file signatures and decoded image, cap bytes/pixels/count, assign random server keys, store outside webroot/private bucket, strip metadata where feasible, prevent path traversal, and add malware scanning if risk/vendor capability warrants it. Never trust extension or browser MIME alone.
- Profile privacy: use separate private account and explicitly public seller-profile projections; default phone contact to private; never expose buyer bio/photo publicly; require seller active+approved state for public profile and listing visibility; verify access control on both HTML and image routes.
- Keep secrets in managed production configuration; local `.env` can be used only if ignored. Maintain a secret-free `.env.example`; rotate any secret suspected exposed. Never include real credentials in docs/logs or Git.
- Do not log passwords, session cookies, reset tokens, message bodies, or full AI prompts. Use request IDs and minimal security events; restrict log access/retention.
- Add security headers, CSP appropriate to actual templates, safe proxy/TLS configuration, dependency review/updates, backup encryption, access audit, and an incident response path before launch.

## AI Data Flow and Guardrails

1. A seller explicitly asks for a draft from a listing/reply editor.
2. The server selects only that seller's listing facts, configured policy facts, and the relevant inquiry; it validates authorization and payload size.
3. The server calls the local/private Ollama endpoint. There is no cloud credential, fallback, DNS route, or provider code.
4. Output is treated as untrusted; product output passes the conservative safety check or uses a deterministic seller-facts fallback. Reply output must have an equivalent safety strategy and must state unknowns for seller confirmation.
5. The result is shown as a draft. Only a separate seller-confirmed publish/send operation changes marketplace state.

Prompts and model limits are not a security boundary by themselves. Tests must check semantic claims and known unsupported cases; manual review remains necessary. Apply inference timeouts, concurrency limits, and safe errors so model failure cannot expose request content or block the web service indefinitely.

## Database Migration and Rollback Design

- Do not alter or reset the current database while planning. First inventory it read-only and make a verified backup before any future migration.
- Add schema versioning and migrations; test upgrades against a copy of the current SQLite database and synthetic fixtures. Preserve admin/seller IDs and hashes; do not create another admin. Compare row counts/constraints and verify sign-in/authorization after import.
- For cutover, stop writes or use a documented sync window, export SQLite to PostgreSQL with a reviewed script, validate data and media keys, take a pre-cutover snapshot, and run smoke checks. Keep original DB untouched/read-only until acceptance.
- Prefer backward-compatible expand-and-contract changes. Roll application back to the previous artifact if needed; if a migration is destructive or incompatible, restore the pre-migration database and reconcile writes under the approved recovery procedure. Never claim a rollback is safe until rehearsed.
- Define recovery-point/recovery-time objectives and data-loss communications with the operator before choosing backup frequency or cutover plan.

## Test Strategy and Release Evidence

- Preserve and run the current complete suite on each application slice; add isolated test databases and no real account data to tests.
- Unit/functional tests: authentication, CSRF, role and owner checks, seller approval, validation, session revocation, product AI safety/fallback.
- Listing/media tests: invalid and spoofed type, oversized file, traversal filename, dimension/pixel cap, ownership, moderation visibility, unavailable/draft state, and cleanup on failed database write.
- Profile tests: buyer profile create/edit and privacy, seller profile owner-only edit, seller approval/suspension visibility, explicit contact publishing, no email/hash/session fields in public responses, valid/rejected/oversized images, safe generated storage keys, repeatable migration and unchanged existing account hashes/statuses.
- Buyer/messaging tests: combined filters, unknown price, favorites isolation, participant-only read/write, guessed IDs, abuse limits, HTML/script-as-text behavior, report visibility, WhatsApp optional URL behavior.
- AI tests: delivery/warranty/price/stock unknown, unanswerable inquiries, unsafe/empty/offline response, known facts only, no auto-send, and app-to-local-Ollama network boundary. Preserve seller input on failures.
- Browser/manual checks: keyboard/responsive behavior, clipboard only if retained, account flows, role denial, and learner-provided end-to-end checks.
- Prelaunch: PostgreSQL migration rehearsal, restore drill, staging smoke test, TLS/header checks, independent security review/penetration test proportionate to exposure, dependency review, load test including Ollama contention, log/alert test, rollback rehearsal, and privacy-deletion process test. Record command, date, result, and environment; never backfill claims.

## Current File Structure and Future Areas

Current files inspected: `app.py`, `marketplace/auth.py`, `marketplace/admin.py`, `marketplace/security.py`, `marketplace/database.py`, `schema.sql`, `ai/ollama_client.py`, `ai/prompts.py`, `templates/`, `static/`, and `tests/test_app.py`.

Local Stages 2–5 now include `marketplace/profiles.py`, `marketplace/media.py`, `marketplace/storefront.py`, profile/listing/storefront/messaging templates, additive SQLite migrations through v4, local-only Ollama product and reply drafts, and automated tests. The storefront, search, filters, favorites, private conversations, and inquiry management have automated coverage; learner browser review remains pending. Production deployment assets remain deferred to reviewed launch stages.

## Runtime and Costs

Local run uses the existing virtual environment and local Flask/Ollama arrangement. Start from the project root with ` .\\.venv\\Scripts\\python.exe app.py ` and open `http://127.0.0.1:5000/`. Product-description generation uses only local Ollama and a deterministic facts-only fallback. Support/report/policy routes do not call AI. Optional environment settings are `MARKETPLACE_SECRET_KEY`, `MARKETPLACE_COOKIE_SECURE`, `MARKETPLACE_APP_NAME`, and `MARKETPLACE_APP_OWNER`. Public deployment will incur hosting, database, image storage/egress, email/domain, logging/backup, and potentially hardware costs. No provider or price is assumed.

## Open Decisions Before Public Launch

- Launch jurisdiction/legal entity and required privacy/consumer/marketplace policies; legal review owner.
- Provider/region for HTTPS edge, app, PostgreSQL, image storage, email, logs/backups; budget and data-processing agreements.
- Expected traffic/catalog/photo sizes; Ollama host/model/concurrency and service target after load tests.
- Support/moderation staffing and response times; appeals, incident escalation, account deletion, retention and backup expiry.
- Recovery objectives, rollout/maintenance window, and whether public registration is invite-only at first.

## Known Limitations

This remains a local prototype, not a production-ready marketplace. Buyer discovery, seller listings/profiles, safe uploads, favorites, private buyer-seller conversations, local-only AI drafts, support/report queues, privacy-request intake, and policy drafts are implemented and covered by automated tests; current browser review and the end-to-end demo review remain pending. Human-staffed support, automatic privacy export/deletion, complete appeals/case management, production database adapter, deployment, and launch operations are absent. Local rate limits reset on restart and are unsuitable for multiple workers. Local HTTP does not use Secure cookies. Policy placeholders, jurisdiction-specific retention and complaint procedures, operator/contact identity, and legal review remain outstanding. SQLite/local files are not production infrastructure. No professional penetration test, independent security/dependency audit, legal review, staging deployment, or SQLite-to-PostgreSQL migration has occurred. The learner must verify the current server and browser flows before marking the local stage reviewed.
