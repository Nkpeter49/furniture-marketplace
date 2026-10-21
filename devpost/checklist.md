---
doc: checklist
status: approved
---

# Hackathon MVP Build Checklist

Build mode: learn

This checklist covers the local hackathon MVP only. Public-production preparation is separately gated in `launch-plan.md`. Stage 1 browser permission checks were completed and confirmed. Local Stages 2–5 and support workflows are implemented and automated tests pass; their browser review remains pending. Public deployment is not part of this checklist.

## Slices

- [x] **1. Verify existing accounts, roles, and product-description flow**
  Becomes usable: The current buyer, seller, and admin access boundaries and preserved product-description page have been mechanically checked and the learner has tried buyer restrictions.
  Why now: This is the existing foundation and a known unverified permission check; later marketplace work depends on it.
  PRD ref: `prd.md > Accounts and access`; `prd.md > Local AI writing assistance`
  Spec ref: `spec.md > Current State: Inspected, Tested, and Unverified`; `spec.md > Authorization and Security Design`
  Build: Inspect and run the existing app/tests first. Do not rewrite working code unless a verified failure requires a documented, approved repair. Preserve the existing database/admin account and use the existing virtual environment.
  Verify (mechanical): Run the complete existing test suite; confirm product description and facts-only fallback; verify a buyer direct request to seller/admin routes is denied; check role/session/CSRF tests. Record actual output and any Ollama test separately.
  Learner check: Completed. The learner confirmed that buyer pages worked, buyers could not open seller/admin pages, the approved seller could open the seller dashboard, and non-admin users could not open admin pages.
  Commit: `Verify Stage 1 account permissions`

- [ ] **2. Buyers and approved sellers can manage safe profiles and seller listings (browser review pending)**
  Becomes usable: A buyer can edit a private display name, optional photo, and short bio; an approved seller can manage a public business profile and their own listing/photos; an eligible public seller page shows only public fields and that seller's published listings.
  Why now: Profiles let buyers and sellers present themselves safely and make seller-owned listings attributable to public marketplace pages.
  PRD ref: `prd.md > Buyer and seller profiles`; `prd.md > Seller listings, inventory, and photos`
  Spec ref: `spec.md > Data Design`; `spec.md > Stage 2 profile migration and serving rules`; `spec.md > Authorization and Security Design`
  Build: Private buyer profile editing; owner-scoped seller business profile and explicit contact publication; safe images; approved seller listing CRUD, seller-reported availability and optional quantity; limited public seller page. These features are implemented. Migration and existing-account preservation are verified; the learner's browser review is still pending.
  Verify (mechanical): Run the full suite; test profile owner/role/status access, public-field privacy, opt-in contact visibility, published-listing visibility, valid and rejected/spoofed/oversized/too-large-dimension images, generated filenames, path traversal, migration re-run, and unchanged existing user IDs/password hashes/roles/approval. Verify migration on a temporary copy before applying it to the working database. Record Pillow installation approval/status separately; do not substitute unsafe signature-only upload handling.
  Learner check: Edit the buyer profile and confirm its bio/photo do not appear publicly; edit the approved seller business profile, enable/disable contact publication, create a sample listing, and inspect the public seller page. Confirm a pending/suspended or other seller cannot edit it.
  Commit: `Add private buyer and public seller profiles`

- [x] **3. Buyers can discover listings and save favorites (automated verification passed)**
  Becomes usable: Visitors browse public listing details; signed-in buyers search/filter and save only their own favorites.
  Why now: This completes the discovery side of the marketplace using the seller listings from Slice 2.
  PRD ref: `prd.md > Buyer discovery, favorites, and reports`
  Spec ref: `spec.md > Data Design`; `spec.md > Authorization and Security Design`
  Build: Responsive storefront and listing detail pages with search and combined category, condition, availability, and price filters; seller-reported availability/quantity and unknown-price labels; buyer-scoped favorites.
  Verify (mechanical): Test filters combined and individually; ensure draft/hidden/unavailable and suspended-seller results follow policy; test unknown price and cross-buyer favorite access.
  Learner check: Pending. Search for sample furniture, apply category/price/availability filters, open details, and save/remove a favorite as a buyer.
  Commit: `Add buyer storefront and favorites`

- [x] **4. Buyers and sellers can message privately and use reports/WhatsApp safely (automated verification passed)**
  Becomes usable: Buyer starts an inquiry; only buyer and seller can read/send in that thread; reports enter a limited admin queue; optional WhatsApp remains visibly external.
  Why now: Inquiry is the marketplace kernel, and participant boundaries must be proven before adding AI reply assistance.
  PRD ref: `prd.md > Private conversations and external contact`; `prd.md > Administration and privacy`
  Spec ref: `spec.md > Data Design`; `spec.md > Authorization and Security Design`
  Build: Listing-linked inquiry creation; bounded plain-text conversations scoped to buyer and listing seller; optional published external WhatsApp contact; report review including audited hide/restore; participant trigger in SQLite. Implemented.
  Verify (mechanical): Test direct guessed conversation IDs, wrong participant reads/posts, cross-account reports, CSRF, rate/length limits, script-as-text output, and WhatsApp optional/valid link behavior.
  Learner check: Pending. Ask about a sample listing as one buyer, reply as the seller, and confirm another buyer and an admin cannot open the messages.
  Commit: `Add private marketplace inquiries`

- [x] **5. Sellers can request safe local AI drafts (automated and local-model verification passed)**
  Becomes usable: Seller generates a product-description or inquiry-reply draft from allowed seller facts, reviews it, and explicitly publishes/sends only after editing/confirmation.
  Why now: The human-controlled inquiry flow exists first; AI must not bypass ownership, privacy, or send confirmation.
  PRD ref: `prd.md > Local AI writing assistance`
  Spec ref: `spec.md > AI Data Flow and Guardrails`
  Build: Preserve current product generation/safety/fallback; add reply prompts grounded in seller-provided listing/policies and the relevant inquiry; use local Ollama only; clearly mark draft/fallback/unknown facts.
  Verify (mechanical): With tests and a real local request when Ollama is available, cover unsupported product claims, unsafe/unavailable AI, missing delivery and warranty, unknown price/stock, unanswerable questions, no auto-send, and local-only network destination. Do not claim a real-model result unless observed.
  Learner check: Pending. Request product and reply drafts, check facts and missing information, and confirm reply text is not sent until the seller presses the separate send button.
  Commit: `Add local-only seller AI drafts`

- [ ] **6. Complete MVP security checks and demo review**
  Becomes usable: The local MVP's end-to-end demo path and documented limitations are verified; no critical known issue is hidden behind a production-ready claim.
  Why now: Integration failures and privacy gaps must be found before the hackathon demo; this does not authorize public launch.
  PRD ref: `prd.md > Quality and Operational Requirements`; `prd.md > Success Measures`
  Spec ref: `spec.md > Test Strategy and Release Evidence`; `spec.md > Known Limitations`
  Build: Run and repair the MVP suite; inspect access boundaries, ignored local data, dependency list, README/setup steps, and demo fixtures. Keep real accounts and private data out of screenshots/source control.
  Verify (mechanical): Run the complete test suite, check `git status` and staged diff for secrets/private data before any commit, verify setup steps in the existing Windows environment, and manually exercise the core seller-to-buyer inquiry flow. Record checks and failures accurately.
  Learner check: Follow the demo journey as buyer, seller, and admin using designated demo accounts and report confusing or broken behavior; never share credentials in chat or the public demo.
  Commit: `Verify and prepare local marketplace demo`

- [x] **7. Support, privacy, policies, and trust controls (local implementation)**
  Becomes usable: Users find searchable help, create and track only their own support/privacy requests and reports, and read plain-language draft policies; administrators alone assign/respond/review/update statuses. Errors and rate limits fail safely.
  Build: Add owner-scoped support/replies, report and copyright/trademark review, access/correction/export/closure request intake without auto-deletion, 11 visibly draft policy pages, footer navigation, safe 403/404/413/429/500 handling, environment-configured app identity/secrets/cookie setting, CSP/security headers, local abuse throttles, and destructive-action confirmations.
  Verify (mechanical): Full suite checks ownership, admin-only review, workflow statuses, policy links/placeholders, no unrequested deletion, CSRF, validation, rate limits, output privacy/log sanitization, cookie/security headers, safe errors, seller/media/product/storefront/conversation functionality, and repeatable migrations through v4.
  Learner check: Pending. Submit test support/report/privacy requests with local test content; inspect owner views and public policy pages; sign in as admin to review/respond; confirm another account cannot see the records. Do not enter private real-world content.
  Risk/limits: Local limiter is per-process and resets on restart; no human support channel or response guarantee is configured; policy drafts still need legal identity, jurisdiction, contact, retention, and counter-notice review. No compliance or security certification is claimed.
  Commit: `Add local support and privacy workflows`

## Hands-on Checkpoints

- [x] Early usable behavior explored — Slice 1 buyer/seller/admin browser permission checks; learner confirmed all passed.
- [ ] Final kick-the-tires exploration and feedback completed — Slice 6 core journey after implementation.

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms the local MVP is ready for hackathon demo; this is not public-launch approval.

## Code Tour and App Map

- [ ] Learning activity complete — guided route, focused alternative, prior practice connected, or brief recap
- [ ] Optional edit and transfer reflection addressed — offered/declined/already covered/not applicable as appropriate
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: Stage 1 buyer/seller/admin browser permission checks completed and learner-confirmed. On 2026-10-21, ` .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v ` ran 43 tests: all passed, no failures/errors. Temporary test databases covered authentication, profiles/uploads, storefront filters/favorites, participant messaging, reply safety/fallback, support/report/privacy workflows, moderation hide/restore, policies, CSRF, rate limiting, and safe errors. Real local Qwen product request returned an exact seller-facts JSON echo; the app formatted it safely. Real reply output with an unsupported delivery claim was rejected; the labeled fallback was returned and the message count did not change. Local DB migrations 2–4 were applied after verified SQLite backups; all 3 user rows, password hashes, roles/status/approvals and existing table counts were unchanged; integrity and foreign-key checks passed. Browser review of the current source and manual end-to-end flows remains outstanding.
Route and stops: Not recorded.
Edit outcome: Not applicable yet.
Reflection: Not offered yet.
Activity mode: Not started.

## Revisions

- The target was clarified as a future public marketplace. Public-launch infrastructure and gates are tracked separately in `launch-plan.md`; local MVP completion will not imply production readiness.
