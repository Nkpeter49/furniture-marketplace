# Furniture Marketplace Local Prototype

This project is a local learning-stage marketplace prototype for furniture buyers and sellers. It is not a public service and is not production-ready.

## What is included

- Buyer and seller accounts with hashed passwords, role checks, CSRF-protected forms, private buyer profile settings, seller approval, and administrator account controls.
- Approved sellers can manage their business profile and their own furniture listings, photos, availability, and optional seller-reported quantity. Published items also appear in a searchable, filterable buyer storefront with listing details, private buyer-owned favorites, and seller contact/inquiry actions.
- Buyer inquiries create private buyer/seller conversations. Only participants can read or send messages; a database trigger also rejects a message author who is not a participant. Admin statistics count conversations without exposing message content.
- Pillow validates, decodes, and re-encodes profile and listing images. JPEG, PNG, and WebP input are supported, up to 5 MB, 6000 pixels per side, and 16 megapixels. Images are stored under the ignored local `instance/` directory.
- Searchable local Help Center, private support requests/replies, private user reports, copyright/trademark complaint review, and privacy/access/correction/export/closure request workflows for an administrator.
- Plain-language policy drafts with explicit placeholders and legal-review warnings.
- Product-description drafts through Ollama on this computer, including an action in the seller listing form. Sellers can request local AI reply drafts using listing facts and policy details they enter. Drafts are editable; they are not sent or published until the seller explicitly acts. Unsafe or unavailable model output produces a labeled facts-only fallback. No cloud AI fallback is configured.

The current local MVP does not include payments, automated account deletion/export, email support, 24/7 human support, real-time notifications, public deployment, or legal/security certification. The buyer experience is an MVP storefront, not a large-scale marketplace service.

## Run on Windows 11

From PowerShell in the project directory:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000/` (it redirects to `/marketplace`). Keep the PowerShell window open while using the app. The local development server binds to loopback and must not be exposed directly to the internet.

Useful pages: `/marketplace` for browsing; `/tools/product-description` for the standalone description tool; `/seller/dashboard` for sellers; `/conversations` for buyer conversations or approved-seller inquiries; `/admin/dashboard` for platform statistics. Sign in with the existing accounts; do not recreate or reset them.

## Trying the demo

Create buyer and seller accounts from **Create account** in the browser at `http://127.0.0.1:5000/`. Choose the buyer or seller account type in the registration form. Seller accounts need administrator approval before they can publish listings.

For a first-time setup with no administrator account, run `flask --app app init-admin` in the project environment and follow the prompts to create one. This command refuses to create another admin if one already exists. Sign in as an administrator, open `/admin/users`, and approve the pending seller. If an administrator already exists, sign in to that account and use `/admin/users` directly.

After approval, the seller can create a listing. New listings start as drafts; choose **Publish on my seller page** before saving so buyers can find the listing in the marketplace.

The app initializes missing tables and applies additive SQLite migrations at startup. Version 1 adds profiles/listings; version 2 adds support/report/privacy and listing-moderation tables; version 3 adds favorites and participant-scoped conversations/messages; version 4 adds optional listing quantity and a hide/restore history table. Migrations preserve existing user rows. Do not delete `instance/` to troubleshoot.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use temporary SQLite databases and do not require Ollama. A real local-model check is separate and should be reported only when it was actually run.

Latest recorded local result (2026-10-21): `43 tests passed` with no failures or errors. A separate real local Ollama product request returned an exact JSON echo of seller facts; the app formatted only those verified facts. A real reply request produced unsupported delivery wording, which the app withheld and replaced with a labeled safe fallback. Browser review of the current app remains pending.

## Local AI and privacy

Ensure Ollama is running locally and `qwen3:0.6b` is installed. The server targets `127.0.0.1:11434`; do not expose that port to the public internet. Product text is accepted only if it passes the facts check or exactly echoes the supplied JSON fields; exact echoes are rendered using a deterministic safe formatter. Reply drafts pass a conservative vocabulary/commitment check. If output is uncertain, a clearly labeled deterministic response is shown. Automated replies are never sent. The privacy and AI policy pages are drafts and need operator, retention, jurisdiction, and legal review before public launch. Avoid entering sensitive personal data in prompts.

## Configuration and secrets

The app reads these optional environment settings:

| Variable | Purpose | Local default |
|---|---|---|
| `MARKETPLACE_SECRET_KEY` | Flask session signing secret | A random secret is created in ignored `instance/secret_key` if unset. Set an environment secret for deployments. |
| `MARKETPLACE_COOKIE_SECURE` | Set to `1` to require Secure cookies | `0` for local HTTP. Public HTTPS hosting must set `1`. |
| `MARKETPLACE_APP_NAME` | Display name | `Furniture Marketplace` |
| `MARKETPLACE_APP_OWNER` | Configured operator name for the footer | Empty; the UI says the operator is not configured. Do not invent an owner. |

Do not commit secrets, `.env` files, SQLite databases, uploaded media, logs, or backups. Review `.gitignore` and `git status` before any future publication. `devpost/learner-profile.md` contains personal learning context and is git-ignored.

## Support, privacy, and moderation

Help articles are automated guidance. Signed-in users may submit support requests and track their own requests; administrator accounts can assign, answer, and change their status. No support email or human-response time is configured.

Users may report published listings or sellers. Only an administrator sees the review queue and records a moderation outcome. An admin can hide or restore a reported listing, or suspend a reported seller, with an audit record. This is a basic local review workflow, without a complete appeal/case-management system. Copyright/trademark complaints use a report reason and enter the admin queue; statutory notice, counter-notice, and repeat-infringer procedures need jurisdiction-specific legal review.

Users can request access, correction, export, or account closure. The local workflow records and routes a request; it does not automatically export or erase data. An administrator must assess linked listings, conversations, reports, support records, safety/legal holds, and backup retention before acting. Retention periods are not yet set.

Policy pages are starter drafts with placeholders for the actual operator, jurisdiction, contact method, effective date, retention periods, and applicable process. They do not establish GDPR or other legal compliance. Have qualified counsel review them for each actual launch jurisdiction.

## Security controls and limitations

The local app uses Werkzeug password hashing, signed sessions, HttpOnly/SameSite cookies, session-bound CSRF tokens, server-side role/ownership/participant checks, a SQLite trigger that rejects nonparticipant message authors, Jinja autoescaping, bounded image processing, generated media names, request-size limits, local in-memory rate limits, security headers, and generic error pages. Local HTTP cookies do not use the Secure flag; configure HTTPS and `MARKETPLACE_COOKIE_SECURE=1` for deployment. The current in-memory limiter resets on restart and does not coordinate multiple workers. It is not a production abuse-control system.

No professional penetration test, independent security review, dependency audit, accessibility audit, load test, or legal certification has been completed. Before public launch, select a production database (PostgreSQL is recommended), private image storage, HTTPS edge, secrets management, shared rate limiting, monitoring, incident response, retention/deletion process, backup/restore and rollback procedures, jurisdiction-specific terms/privacy policies, support/moderation ownership, and qualified security/legal review.

## Backups and recovery

Before a schema upgrade or manual database work, stop only the known application process and make a timestamped copy of `instance/marketplace.sqlite3` to a protected backup location outside Git. Preserve `instance/media/` with the database because records refer to generated image files. Keep the backup private and verify its SQLite integrity with a read-only `PRAGMA integrity_check` against the copy. Verified backups were created before this implementation's migrations under ignored `instance/backups/`. Do not reset or restore over the working database without reviewing what changed since the backup. Production backup frequency, encryption, retention, and recovery objectives are not configured.

## Dependency maintenance

Dependencies are listed in `requirements.txt`; the project currently uses Flask and Pillow. Before updating, review release notes and compatibility, update the requirement range deliberately, install only into `.venv`, and run the full suite. Before public release, run a dependency vulnerability audit in an isolated environment, record findings, and resolve or explicitly mitigate them. No independent dependency audit has been performed yet.

## Public-launch checklist

See [`devpost/launch-plan.md`](devpost/launch-plan.md). Public deployment, domain setup, real support contact, company/operator identity, jurisdiction, legal review, data-retention schedule, PostgreSQL migration, secure image storage, backup/restore rehearsal, and independent production security review remain outstanding.
