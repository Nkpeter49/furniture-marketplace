---
doc: launch-plan
status: draft
---

# Staged Implementation and Public Launch Plan

This roadmap records local implementation progress and future public-launch gates. Local MVP stages 2–5 are implemented and automatically tested; learner browser review remains pending. No deployment has occurred; public release requires all applicable gates below and explicit operator approval.

## Current Baseline

| Area | Present | Evidence / status |
|---|---|---|
| Flask app and local environment | Present | `app.py`, `marketplace/`, `requirements.txt`, `.venv/`; no environment changes made in this planning pass. |
| Authentication and roles | Present; browser foundation previously confirmed | Buyer/seller registration, login/logout, account/password, role-guarded pages, admin CLI and controls. Current complete suite covers these flows. |
| Seller approval | Present | Admin can approve/suspend; local seller is reported approved. Do not recreate account or reset DB. |
| Buyer/seller profiles and seller listings | Implemented locally; learner review pending | Private buyer profile; approved seller business profile with contact opt-in; seller listing management/photos and optional seller-reported quantity. |
| Buyer storefront and favorites | Implemented locally; learner review pending | Search, category/condition/availability/price filters, listing detail pages, safe photos, unknown-price labeling, buyer-owned favorites. |
| Private buyer-seller conversations | Implemented locally; learner review pending | Listing-linked inquiries and participant-only read/send; database trigger also prevents a nonparticipant author. Admin has no message-body inbox. |
| Product description + local AI replies | Implemented locally; learner review pending | Real product request passed the exact facts check and formatting. A real reply containing an unsupported delivery claim was rejected and replaced by a labeled fallback. No cloud AI or automatic sends. |
| Support, reports, privacy requests, and policy drafts | Implemented locally; automated tests passed, learner review pending | Searchable help, private owner/admin-scoped queues, copyright review, listing hide/restore history, seller suspension and 11 draft policy pages. No real support contact is configured. |
| Stage 1 manual buyer/seller/admin permission check | Confirmed passed | Learner confirmed all Stage 1 browser checks passed. |
| Marketplace features | Local MVP flows implemented; manual review pending | Storefront, favorites, participant-only messaging, seller inquiries, optional external WhatsApp, dashboards, quantity and basic report moderation are implemented. Full appeal/case management remains absent. |
| Production service | Not present | SQLite/local files, no public hosting/domain/TLS, production PostgreSQL, object storage, production/shared abuse controls, restore drill, monitoring, completed legal/privacy review, or independent security review. |

The repository has not been staged or committed. `devpost/learner-profile.md` is tracked and contains personal learning context; do not publish the repository in this state. Before any future public GitHub step, with the learner's explicit approval, remove that file from the Git index without deleting their local copy, inspect history and the intended tree for private data/secrets, and review the staged diff. Local SQLite data, uploads, and the pre-migration backup are stored under ignored `/instance/`; `.gitignore` excludes `.env` files except `.env.example`, `.venv`, Python cache, and `/instance/`. Ignoring does not remove already tracked data or historical copies.

## Hackathon MVP Build Stages

These vertical, testable slices match `checklist.md`. Stage 1 browser checks are confirmed. Stage 2 and support workflows remain open pending browser review; the buyer storefront, messaging, and AI draft slices are implemented and automated-tested, with learner checks still open.

| Stage | Deliverable and exit evidence | Dependencies / security focus | Safe rollback |
|---|---|---|---|
| 1. Authentication and roles (existing; verify) | Full test suite passes; learner confirms buyer can use buyer area and cannot open seller/admin routes; preserve original product page and local data. | Existing `.venv`, current DB. Verify CSRF, role checks, account suspension and no admin recreation. | Make no changes during verification. If a fix is needed, snapshot existing source/DB first and make a narrow reviewed fix; never reset the DB/admin. |
| 2. Buyer and seller profiles, seller listings and images | Implemented locally; browser review pending. Optional quantity is seller-reported and blank means unknown. | Additive migrations, owner/status checks, Pillow image re-encoding and private generated media names. | Verified database backup; preserve DB and media together; never reset users. |
| 3. Buyer storefront, search, filters, favorites | Implemented locally and covered by the complete suite; browser review pending. | Parameterized combined filters; public pages exclude drafts, hidden listings, and inactive or pending sellers; unknown prices stay unknown. | Additive schema and preserved backup; disable only feature routes if needed. |
| 4. Messaging, reports, WhatsApp | Implemented locally and covered by the full suite; browser review pending. Only buyer and listing seller can read or send. | CSRF, role/participant checks, length and rate limits, output escaping, and database participant trigger. Admin statistics do not read message bodies. | Preserve conversations; disable route access if needed, do not delete messages as rollback. |
| 5. Local AI product/reply drafts | Implemented locally and covered by tests. A real product request passed exact-facts formatting; a real reply containing an unsupported delivery claim was withheld and replaced by a fallback without sending. | Ollama loopback only; no cloud fallback; seller review and explicit send remain required. | Disable drafting while preserving listing and conversation data; do not switch providers. |
| 6. MVP verification and demo readiness | Complete suite passed 43 tests on 2026-10-21; browser review and final demo acceptance remain open. | Stages 1?5; keep accounts and private data out of screenshots and do not publish local files. | Preserve current DB and verified backups; use a reviewed recovery procedure. |

## Public-Launch Stages and Gates

Do not start these stages until the MVP has been reviewed and the operator explicitly chooses to pursue public launch. Provider, jurisdiction, budget, and service decisions require review before purchasing or transmitting data.

### A. Product policy and threat model

**Work:** choose legal operator, launch countries, audience/age policy, currencies/languages, data minimization, message/report retention, account export/deletion, backups expiry, moderation/appeals, support and incident contacts; threat-model account, upload, conversation, admin, and AI abuse. Obtain qualified legal review for privacy policy, terms, seller/buyer rules, and required notices.

**Acceptance:** policies match actual data flow and selected jurisdiction; contact/support and moderation owners are named; retention/deletion process is tested; no unresolved legal/privacy question is misrepresented as solved.

**Rollback:** do not open public registration or accept real user data until required policies and processes are ready. Pause onboarding and honor any accepted data/deletion obligations.

### B. Production data and image architecture

**Work:** select managed PostgreSQL and private image/object storage in a reviewed region. Write versioned migrations and a repeatable SQLite-to-PostgreSQL import. Define object lifecycle, encryption, backup retention and least privilege. Add database/object-store constraints and search indexes.

**Acceptance:** migration rehearsed from a copy of the actual SQLite data; user IDs, hashes, seller approval, and existing content validated; counts/references/media verified; integration and concurrent-write tests pass; restore tested from encrypted backup; no data path or permission leakage.

**Dependencies:** Stage 6, provider/data-processing review, budget, migration owner and recovery objectives.

**Rollback:** preserve an immutable pre-migration backup and untouched source DB; rehearse the cutover, rollback, and write reconciliation. Prefer additive/expand-contract schema changes; never point production back to an old schema after incompatible writes without a reviewed restore/reconciliation plan.

### C. Production security and abuse controls

**Work:** configure HTTPS-only secure cookies and trusted proxy handling; secret manager and rotation; CSRF on every mutation; rate limits and abuse controls; admin MFA; email verification/recovery if selected; security headers/CSP; upload scanning/processing; audit events; dependency updates; least-privilege service accounts; log redaction; incident response; admin access review. Add independently reviewed security/penetration testing.

**Acceptance:** full authorization matrix and object-ID tests pass; no critical/high finding remains open or has a documented approved mitigation; secrets scan is clean; upload abuse tests pass; admin MFA and recovery tested; error logs contain no secrets or message text; security alerts are demonstrated.

**Rollback:** disable the affected route/feature or close public access, rotate exposed credentials, deploy the last known-good artifact, preserve incident evidence safely, and notify users as required by the reviewed incident plan. A rollback must not restore known-exposed secrets.

### D. Private staging deployment and local Ollama capacity

**Target topology:** Internet → managed HTTPS edge → private Flask WSGI service → private PostgreSQL and private media storage. Flask calls Ollama over loopback/private service network. Database and Ollama ports are firewalled from the public internet; browser clients never call Ollama directly. No cloud AI fallback or AI content egress.

**Work:** choose host/region/vendor and domain; automate environment-specific deployment from reviewed artifacts; configure TLS, health checks, safe errors, logs/alerts, backups, and deployment identity. Keep Ollama on controlled hardware; measure target model latency, RAM/CPU, concurrency, queueing and failure behavior. Consider server capacity/cost before selecting a larger model. Do not expose model server or enable remote management publicly.

**Acceptance:** external scan cannot reach Ollama/database; app is HTTPS-only; AI calls observed only to private/loopback Ollama; load tests meet an operator-approved capacity target without exhausting app/model resources; staging backup restore and deployment rollback succeed; logs and alerts operate without sensitive payloads.

**Rollback:** remove public DNS/close ingress or put maintenance mode on; return to prior app image/config; keep data services and backups intact; never silently route AI to a cloud provider.

### E. Release rehearsal and controlled launch

**Work:** complete privacy/terms publication, user support and moderation runbooks, backup restore, incident rehearsal, deployment rollback, accessibility review, migration and smoke checks; decide invite-only/limited rollout, support staffing, and monitoring period. Establish cost/billing alerts and usage caps. Keep payments and automated transactions excluded.

**Acceptance:** all launch gates have named owner and dated evidence; no critical/high security issues remain; service and AI capacity/support meet approved targets; privacy documents match deployed behavior; restore, rollback, and incident contacts have been rehearsed; explicit launch authorization is recorded.

**Rollback:** stop registrations/listing publication or close ingress; preserve evidence and user data according to policy; notify users and fulfill incident/legal obligations; restore only using the rehearsed recovery plan.

## Production Readiness Checklist (all required before claiming launch-ready)

- [ ] Launch locations, legal entity, privacy/terms/moderation policies and support owner confirmed.
- [ ] Public database is PostgreSQL; migration from preserved local data rehearsed and validated.
- [ ] HTTPS, public-edge-only ingress, private app/database/media/Ollama network, and production secrets are verified.
- [ ] Role/ownership, CSRF, session, rate-limit, profile privacy/contact visibility, upload, AI safety, and abuse tests pass.
- [ ] Backups encrypted and retention defined; restore and recovery objectives demonstrated.
- [ ] Logs, alerts, incident process, user support and moderation are operational.
- [ ] Ollama model/resource/capacity tested; no cloud AI route exists; AI text stays draft-only.
- [ ] Security/dependency review complete; critical/high findings resolved or formally accepted with mitigation.
- [ ] Staging smoke, accessibility, load/capacity, deployment rollback and database recovery rehearsed.
- [ ] README and operator runbooks describe actual production services and costs; public repository/history has been reviewed for secrets and private data.
- [ ] Explicit launch approval given by the operator.

## Exact Next Action

The full automated suite has passed. The next step is for the learner to start the app in a PowerShell window from the project folder with ` .\.venv\Scripts\python.exe app.py `, then open `http://127.0.0.1:5000/` (which redirects to the marketplace). Exercise buyer browsing/search/filter/favorites/inquiries, seller listing/profile/reply-draft flows, participant-only messaging, and admin support/report/moderation views. Keep manual checks open until the learner reports results; do not stop any existing process without identifying it first. Payments and public deployment remain out of the local MVP. This build is not production-ready.

## Additional Public-Launch Gates: Support, Privacy, and IP

- Name the actual legal operator, launch jurisdiction(s), privacy contact, support contact/channel, support/moderation owner, operating hours, escalation process, and response targets. The application must not present placeholders as real contact details or promise 24/7 coverage.
- Have qualified counsel review terms, privacy, cookie/session notice, community and prohibited-item rules, seller terms, buyer safety, moderation/suspension/appeals, account closure, AI disclosure, and copyright/trademark notice/counter-notice procedures for each jurisdiction. Pages are drafts, not compliance evidence.
- Define retention/deletion/export rules for accounts, listings, uploaded photos, conversations, support tickets/replies, reports, moderation/audit records, logs, and backup copies. Rehearse access/correction/export/closure requests and legal holds before accepting public data.
- Establish staffed complaint review, evidence handling, content restriction/notification decisions, counter-notice routing, abuse escalation, appeals, and repeat-infringer process where applicable. Do not expose report/support content to ordinary users or log its contents.
- Replace process-local rate limits with shared production controls; configure secure cookies, HTTPS, secrets manager, CSP review, incident logging/alerts and independent security/dependency review. No penetration test or certification is claimed by this local work.
- Copyright notice uses the configured application name/year. Operator identity is omitted unless explicitly configured; do not claim registration or ownership of user content. Confirm code/design asset provenance and repository history before any public release.
