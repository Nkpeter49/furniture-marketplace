---
doc: scope
status: approved
---

# Furniture Marketplace: Scope and Release Boundaries

## Problem and Objective

Furniture sellers often have to create listings and answer questions using information spread across notes, messages, and memory. Buyers need a clear way to find furniture and ask the seller about it. This project is intended to grow from a local learning prototype into a trustworthy public marketplace, while keeping seller control over listings and replies and keeping AI inference on infrastructure controlled by the project owner.

The objective is to deliver a useful marketplace in reviewed, testable stages, then meet explicit security, privacy, operational, and legal launch gates before real public use. A passing local demo is not evidence of production readiness.

## The Unique Kernel

A buyer finds a seller-reported furniture listing and privately asks its seller about it. The seller controls the facts and availability, and may use local AI for a factual draft. The seller decides what to publish or send. No payment or business commitment is made automatically.

## Target Users and Needs

- **Buyers:** manage a private profile with display name, optional photo and short bio; find furniture by type, price, and other listing facts; see photos and seller-reported availability; ask a seller a question; manage favorites and only their own conversations.
- **Independent sellers and small furniture retailers:** maintain a public business profile with display/business name, optional profile photo and cover image, biography, furniture specialties and seller-controlled contact choices; create and maintain listings with photos, price, condition, material, dimensions, stock/availability, and descriptions; answer inquiries; use optional local AI drafts without surrendering control.
- **Administrators:** approve or suspend sellers, manage accounts, moderate listings, handle reports, and view aggregate activity without routine access to private conversations or credentials.
- **Marketplace operator:** protect accounts and private content, respond to abuse and incidents, maintain service and backups, and comply with the law that applies to the chosen launch locations.
- **Support and trust:** offer searchable automated help, private support tracking, report workflows, and privacy-request intake without promising 24/7 human support or legal certification.

## Main User Workflows

1. A buyer registers, signs in, edits a private profile and password, browses/searches/filters furniture, views a listing, saves a favorite, and starts a private seller conversation.
2. A seller registers and waits for approval; after approval, the seller edits a business profile, chooses which contact details to publish, creates and manages listings, marks availability, receives inquiries, and replies manually or with a reviewed local AI draft.
3. An administrator signs in through a protected route, approves or suspends sellers, moderates listings, processes reports, and views aggregate statistics.
4. A seller can optionally show a WhatsApp contact link. It opens an external service and is separate from marketplace messaging.
5. The operator prepares a private staging deployment, verifies restore/rollback, security and privacy controls, and completes launch reviews before inviting the public.

## Product Boundary and Stages

The project has two distinct targets:

1. **Hackathon MVP:** a modest, demonstrable marketplace built and exercised locally in small slices. It can show account roles, private buyer profiles, approved-seller business profiles, listings, an individual seller page with only that seller's published listings, full discovery in Stage 3, private messaging, optional external WhatsApp, local-only AI drafts, and basic moderation. Stage 2 does not add the general searchable/filterable buyer storefront. It uses local SQLite and local files and is not for public production data.
2. **Public launch:** a later, separately gated release that requires a production database, managed deployment, secure image storage, HTTPS, operational controls, privacy/legal review, capacity checks, and recovery/rollback evidence. Public-launch work is described in `launch-plan.md`; it is not implied by completion of the MVP checklist.

## MVP Success

On one controlled demo environment, a buyer can find an approved seller's listing, ask a question, and see only their own conversation; the seller can answer; an unauthorized user is denied; admins can manage approval and moderation; and a seller can request an Ollama draft or a clearly labeled facts-only fallback. Existing product-description behavior remains intact. All documented automated tests pass, and the learner completes the manual role/ownership checks. No public launch claim is made.

## Explicitly Out of Scope

- Payments, escrow, orders, refunds, delivery booking, or any automated transaction or business commitment.
- Cloud AI or sending seller/customer content to a cloud model. There is no cloud fallback.
- Automatic sending or publishing of AI output, messages, WhatsApp messages, or email.
- Real-time chat, push notifications, attachments in messages, inventory-system integrations, mobile apps, or reviews in the MVP.
- Treating seller-reported availability as verified live stock.
- Automated account deletion/export, support guarantees without a staffed service, or policy pages represented as jurisdictionally approved.
- General administrator access to private conversation contents.
- Public use of the local SQLite/local-file prototype, or calling the application production-ready before launch gates pass.

## Constraints and Assumptions

- Keep Flask and Python; use SQLite and local files only for the learning prototype. Plan PostgreSQL for public multi-user use and do not migrate in this planning pass.
- Keep Ollama local to a controlled computer or private server. Never publish the Ollama port or route user traffic directly to it.
- The learner is a beginner and wants step-by-step explanations, hands-on checks, and to understand the application.
- The existing account, role, seller-approval, and product-description code/tests are working baseline material to preserve, subject to future review and testing.
- The initial administrator already exists in the local data. Never recreate/reset it or reset the database as part of later implementation.
- Email, password hashes, session data, and conversations are private and never appear on public profiles. Buyer profile fields remain private in the MVP. Seller business fields are public only for an active, approved seller; optional phone/WhatsApp contact is hidden unless the seller explicitly enables publication.
- Profile and listing images require trusted image decoding/validation, size and dimension limits, generated storage names, and storage outside source/publicly executable paths. Profile edits and uploads require current account ownership and role checks.
- Launch jurisdiction, hosting region/provider, expected volume, recovery objectives, operating budget, support owner, and legal entity are not established. They are launch blockers, not assumptions to silently fill in.
- WhatsApp is optional external contact; a user opening the link may disclose the seller's number to WhatsApp.

## Risk Summary

Public marketplace risks include account takeover, broken object-level authorization, abusive listings/messages, unsafe uploads, exposure of private records or secrets, malicious or oversized input, database contention/loss, Ollama overload, service outages, and legal/privacy obligations. The local MVP mitigates only a subset. Stage-specific controls and release gates are in `launch-plan.md` and `spec.md`.
