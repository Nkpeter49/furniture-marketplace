---
doc: prd
status: approved
---

# Furniture Marketplace — Product Requirements

This document defines the intended product behavior. The local prototype and the public-launch target have different readiness levels; implementation and release stages are tracked in `checklist.md` and `launch-plan.md`.

## Core Journey

1. A seller registers and sees that approval is pending. An administrator reviews and approves the account before the seller can publish.
2. The approved seller creates a furniture listing with seller-provided facts and photos, publishes it, and can later edit, mark unavailable, or remove it.
3. A buyer browses, searches, and filters public listings, sees the seller-reported facts and availability, and may save a favorite.
4. The buyer asks a question through a private in-app conversation. The seller sees and answers that conversation. Only its participants may access it.
5. The seller may use local Ollama to prepare a description or response draft based on actual listing and policy information. The seller reviews and explicitly publishes or sends it.
6. Administrators moderate listings and reports, manage account status, and see basic aggregate statistics without a general private-message inbox.

## Users and Experience

- **Public visitors and buyers:** clear responsive storefront; furniture categories; search; category, condition, seller-reported availability, and price filters; product cards/detail with photos, description, price when known, seller information, and reported availability; favorites and account area; private conversations and reports.
- **Sellers:** account approval status, dashboard, listing editor and inventory/availability controls, inquiry inbox limited to their conversations, reply editor, and optional WhatsApp settings. AI text is visibly a draft and requires human action.
- **Administrators:** separate protected area for buyer/seller management, seller approval/suspension, listing moderation, report handling, and aggregate statistics. Record moderation actions without exposing passwords, secrets, or unnecessary message content.
- Forms explain required fields and errors in plain language. Empty search results preserve selected filters. Access failures do not reveal whether another user's private record exists.

## Requirements and Acceptance Criteria

### Accounts and access

- Buyers and sellers register, sign in/out, and manage their own profile and password. Seller registration creates a pending account. No public registration flow can create an administrator.
- Authentication, role checks, ownership checks, and account status are enforced on the server for every protected route and record operation.
- Passwords are securely hashed. Session cookies use secure production settings; state-changing forms require CSRF protection; authentication endpoints resist automated guessing. Admin access has stronger authentication before public launch.
- Users can request account closure under a defined privacy/retention process before public launch.

Acceptance: forged role changes fail; pending/suspended sellers cannot publish; suspended users lose protected access; Buyer A cannot read Buyer B's profile/conversations/listings; seller and admin boundaries are tested by direct requests, not only hidden links.

### Buyer and seller profiles

- A buyer can edit their display name, optional profile photo, and short bio from signed-in account settings. Password changes continue through the existing secure password-hash flow and require the current password.
- A seller can edit a business profile containing a public display/business name, optional profile photo and cover image, biography, and furniture specialties. Login email and password hash stay in the private account record and are never copied into public profile fields.
- Seller contact preferences are optional. A phone number is private by default and appears publicly only when the seller explicitly enables publishing that number. A WhatsApp link is clearly external and only appears when configured.
- A public seller page is available only for an active, approved seller. It shows only explicitly public business fields and that seller's published, visible listings. The marketplace storefront provides general browsing and filters; the seller page remains a focused business profile.
- Pending or suspended sellers have no public profile visibility and cannot use seller profile or listing management actions. Server-side role, account status, approval, and record ownership are checked for every edit and upload.
- Profile photos, cover images, and listing photos use one safe upload policy: documented image formats, byte and pixel limits, content validation by an image decoder, server-generated filenames, storage outside source/executable paths, and visibility-aware serving. Preserve the previous image if an update fails.
- Profile forms and public pages are responsive and accessible, with labels, clear validation/success/error feedback, and useful empty states.

Acceptance: a buyer can edit their private fields and cannot expose them through public routes; a seller can edit only their own business profile; buyers/non-owners cannot edit or upload to another account; unapproved/suspended sellers cannot load a public seller page or manage data; public profile output excludes email, password hashes, sessions, and private conversations; unconfigured contact numbers remain hidden; unsafe/oversized/spoofed images are rejected; the public seller page lists only that seller's published items; migrations preserve existing user IDs, password hashes, account status, and seller approval; existing Stage 1 and product-description tests remain passing.

### Seller listings, inventory, and photos

- Sellers manage their own listing name, category, multiple photos, price/currency, condition, material, dimensions, colour, description, additional details, seller-reported availability, and an optional known quantity. Blank quantity means unknown; a zero quantity cannot be marked available.
- Listing state distinguishes draft, published/available, published/unavailable, seller-removed, and administrator-hidden. Only eligible published listings are public.
- Uploads accept only documented image formats and configured size/dimension limits. The service generates storage names, verifies file content, decodes/re-encodes with a trusted image library, and never uses a client path as a filesystem path.
- Admin moderation hides/restores listings and records who acted, when, and why.

Acceptance: a seller can change only their own listings; pending/suspended sellers cannot publish; invalid fields and files are rejected with useful errors; path traversal and mismatched file types cannot access or store arbitrary files; unpublished/hidden listings do not leak from pages or media routes.

### Buyer discovery, favorites, and reports

- Visitors can browse published listings. Search covers seller-provided name, category, material, and description. Filters combine and include category, condition, availability, and price range.
- Buyers can save/remove favorites and see only their own favorites.
- Unknown price is clearly unknown or “Ask seller”; it is never inferred. Availability is visibly seller-reported, not a live guarantee.
- Buyers can report a listing or account with a reason and receive confirmation.

Acceptance: search/filter results respect publication, seller approval/status, and moderation state; favorite routes are owner-scoped; direct record-ID guesses do not reveal other buyers' data; reports are visible only to the reporting user as appropriate and authorized moderators.

### Private conversations and external contact

- A signed-in buyer can start or continue a listing-linked text conversation with its seller. A seller can answer with an explicit send action. Users can view only conversations where they are a participant.
- Messages are escaped/rendered as text, validated for length, rate-limited, and retained only under the documented retention policy.
- Optional WhatsApp links are clearly external, user-initiated, and distinct from in-app messages. The seller controls whether a contact number is displayed.

Acceptance: unauthorized participants cannot list, read, or post to another thread; browser/direct-request tests prove object-level access control; messaging uses POST with CSRF protection; no automatic WhatsApp or message send occurs.

### Local AI writing assistance

- Ollama is the only AI provider. Inference runs on a machine/server controlled by the operator, is reachable only from the app over loopback/private networking, and is never a public web endpoint.
- Product descriptions and reply drafts use only the seller's supplied listing facts and policies. Do not invent features, quality/suitability claims, price, stock, delivery, warranty, returns, discounts, dates, or commitments.
- Missing requested information is clearly identified; reply drafts politely state that the seller will confirm it. Unknown prices/stock/policies stay unknown.
- Every AI result is a draft. It is never published or sent without seller review and explicit action. Product facts-only fallback is visibly labeled as not AI-generated; it remains available if Ollama is unavailable or output fails the safety gate. Reply generation must likewise fail safely without inventing an answer.
- Seller and customer content is not sent to cloud AI. WhatsApp disclosure is separate and visible to the user.

Acceptance tests cover: missing delivery details, missing warranty details, missing/unknown price, unknown availability, an unanswerable customer question, unsafe model output, Ollama unavailable, and product descriptions containing no unsupported claims. Verify network destinations remain local for inference. Preserve existing product-description tests.

### Administration and privacy

- Admin can manage buyer/seller status, approve/suspend sellers, hide/restore listings, review/resolve reports, and view aggregate user/listing/conversation/report counts.
- No password/hash/session secret is rendered or logged. Admins do not receive routine broad access to private message bodies. Any exceptional access for a report must be limited, justified, audited, and reviewed before release.
- Collect only necessary personal information. Define retention, deletion/export, support, incident response, and access processes for public launch.

Acceptance: all admin operations reject buyers/sellers server-side; management changes are auditable; stats are aggregate; tests check that private message bodies and credential fields are absent from admin views/logging.

### Help, support, and reports

- Public visitors can search the Help Center. Articles explain sign-in, seller approval, listing visibility, photo limits, privacy, suspicious content, suspension, and local AI behavior.
- Signed-in users can create support requests with category, subject, description, and optional listing reference; view/reply to only their own requests; and see Open, In Progress, Waiting for User, and Resolved states.
- Administrators can view the support queue, assign a request to themselves, respond, and update its status. The product does not claim 24/7 support, a response-time promise, or a support email unless one is configured.
- Authenticated users can report a published listing or approved seller with a reason and details. Only administrators can review and record outcomes; a user sees only reports they submitted.
- Copyright/trademark complaints have a reason and review path. Counter-notices and statutory deadlines require jurisdiction-specific operator/legal handling; the app is not a certified notice-and-takedown service.
- Forms are CSRF-protected, length-validated, escaped on display, and subject to local abuse limits. No report or support text is public.

Acceptance: two users cannot read each other's support requests, responses, reports, or private uploads; non-admins cannot access review queues or change outcomes; status/reply transitions persist; a copyright report reaches the admin queue; abuse limits and CSRF are tested.

### Privacy requests and policy pages

- Users can submit access, correction, export, and account-closure requests and see only their own request and admin response.
- Requests enter an administrator review queue. Submitting closure does not automatically erase an account or related records; an operator must review listings, messages, reports, support records, legal holds, and backups against a documented retention policy.
- Public policy pages cover Terms, Privacy, Cookies/Sessions, Community Standards, Seller Rules, Buyer Safety, IP Complaints, Moderation, Suspension/Appeals, Account Closure/Data Requests, and AI disclosure. Missing operator, jurisdiction, contact, date, and retention details remain visibly marked placeholders.
- The app discloses signed session cookies and local Ollama processing accurately. It makes no generic legal-compliance claim.

Acceptance: privacy requests are owner-scoped, admin outcomes do not delete unrelated users, every policy URL resolves, placeholders and draft/legal-review notices are visible, and public pages omit private account/support/report fields.

## Quality and Operational Requirements

- Responsive accessible pages; labels, keyboard use, readable contrast, clear errors, and no reliance on color alone.
- Shared navigation/footer links to support, privacy, safety, and policy pages. No fake reviews, ratings, trust badges, human-support availability, contact address, or security certification appears.
- Validate all input on the server; encode output; use parameterized database queries; apply request/body and upload limits; use secure production session/cookie settings; protect CSRF and rate-limit sensitive actions.
- Local in-memory throttling covers sign-in, registration, AI generation, support, replies, reports, and privacy requests. It is a single-process development control and must be replaced with shared production rate limiting.
- Safe errors do not show stack traces. Production secret, HTTPS, Secure-cookie, monitoring, dependency, backup, and independent security review controls must be configured and verified before launch.
- Public release requires HTTPS, environment-managed secrets, PostgreSQL, protected image storage, backups with a proven restore, health monitoring, useful redacted logs, dependency/security review, load/capacity checks, incident/support procedures, and a rollback rehearsal.
- Privacy policy, marketplace terms, moderation/report rules, and seller/buyer disclosures must be prepared and reviewed for the selected operating jurisdictions before public registration. This document is not legal advice or a completed policy.
- No payments, ordering, or automated transactions are part of this release.

## States and Error Handling

- Pending seller: may manage a profile and permitted drafts, sees approval state, cannot publish.
- Suspended account: cannot sign in or perform protected actions; public exposure of its listings follows moderation policy.
- No matches: preserve filters and offer a clear empty state.
- Missing listing fact: display it as unknown/omit it, never fill it in.
- Ollama timeout/offline/unsafe result: retain seller input and show labeled facts-only product fallback or a safe reply draft that requests seller confirmation.
- Invalid/oversized upload or form: reject safely, retain other entered values, and explain correction.
- Profile visibility: buyer profiles are private; pending/suspended seller profiles are not public; seller contact number is hidden unless explicitly published; public seller pages show a helpful empty state when no published listings exist.
- Database/object-store or messaging outage: show a generic recoverable message, log a correlation identifier without secrets/message bodies, and avoid partial writes.
- Authorization denial: use a consistent denial/not-found response that does not disclose private record existence.

## Assumptions and Open Product Decisions

- Launch countries, currencies, languages, legal operator, retention periods, support process, account deletion details, and age policy require operator decisions before launch.
- A seller-reported stock quantity is not independently verified. Decide whether the public product should show quantity or only a broad availability state.
- Moderation appeal process and whether reported private content can be reviewed need a documented, privacy-preserving policy.
- Public production capacity and acceptable AI response time require load tests on the chosen Ollama hardware/model.

## Non-Goals

Payments and checkout; escrow; delivery booking; automated business commitments; cloud AI; automatic message sending; real-time notifications; mobile applications; and any claim of production readiness before every launch gate is evidenced.

## Success Measures

**Hackathon MVP:** the end-to-end listing discovery and private inquiry flow works locally; seller/admin controls and access boundaries pass tests; preserved product AI flow and safe fallback work; learner tests the app; no unresolved critical security defect.

**Public launch:** all gates in `launch-plan.md` have named evidence and an owner; production restore and rollback have been rehearsed; privacy/legal materials and support process are live; operational and load tests pass; no critical/high security findings remain open; local AI stays private and within measured capacity. These are release criteria, not claims about current status.
