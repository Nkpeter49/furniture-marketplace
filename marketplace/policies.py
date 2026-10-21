"""Plain-language draft policies for the current local MVP.

Every page is explicitly marked as a draft. Placeholders are intentional and
must be completed by the actual operator after jurisdiction-specific review.
"""


POLICIES = {
    "terms": {
        "title": "Terms of Service",
        "sections": [
            ("Draft status", "Draft only. Operator: [LEGAL OPERATOR NAME]. Jurisdiction: [GOVERNING JURISDICTION]. Effective date: [DATE]. Obtain qualified local legal review before public launch."),
            ("Using this local prototype", "The service is a learning-stage furniture marketplace prototype. Listings and availability are seller-reported. No payment, escrow, delivery booking, or transaction guarantee is provided."),
            ("Accounts and conduct", "Keep account details accurate, protect your password, and use the service lawfully. Do not impersonate another person, evade a suspension, scrape private information, or interfere with the service."),
            ("No professional certification", "These draft terms are not legal advice, a compliance certification, or a promise that the service is suitable for public commercial use."),
        ],
    },
    "privacy": {
        "title": "Privacy Policy",
        "sections": [
            ("Draft and operator", "Draft only. Data controller/operator: [LEGAL OPERATOR NAME]. Privacy contact: [CONFIGURE REAL CONTACT]. Jurisdictions served: [DECIDE BEFORE LAUNCH]. Effective date: [DATE]. Local legal review is required."),
            ("Information and purposes", "The prototype stores account email, display name, password hash, role and approval state; optional profile and seller-business details; listing details and images; and, when enabled, support requests, reports, and privacy requests. This data supports sign-in, marketplace pages, safety review, support, and requested account administration."),
            ("Storage and sharing", "Local MVP data is stored in SQLite and files on the operator's computer. Public seller fields and published listings are visible to visitors; buyer profiles, account email, support content, reports, and private records are restricted to their owner and authorized administrators as needed for review. No advertising trackers or analytics are configured."),
            ("Local AI", "Product-description drafting may send the seller's entered product facts to Ollama running on the same controlled computer. No cloud AI fallback is configured. Drafts require human review. Do not enter sensitive personal information into AI prompts."),
            ("Retention and requests", "Retention periods are not yet configured: [SET RETENTION PERIODS]. Use Privacy & data requests to ask for access, correction, export, or account closure. Requests are reviewed; closure is not an instant hard delete because records may need to be retained for safety, disputes, backups, or legal obligations. Applicable rights depend on the user's location and require jurisdiction-specific review."),
            ("Cookies and contact", "The app uses a signed browser session cookie for sign-in and CSRF protection. It is HttpOnly and SameSite=Lax in the local setup; the local HTTP cookie is not Secure. Production must use HTTPS and Secure cookies. Privacy contact: [CONFIGURE REAL CONTACT BEFORE LAUNCH]."),
        ],
    },
    "cookies": {
        "title": "Cookie and Session Notice",
        "sections": [
            ("Draft status", "Draft only. Effective date: [DATE]. Have this notice reviewed for the chosen launch jurisdiction."),
            ("Essential session cookie", "A signed session cookie keeps the current sign-in and CSRF token between requests. The cookie is HttpOnly and SameSite=Lax. Local development uses HTTP, so the Secure flag is off locally. A public deployment must use HTTPS and Secure cookies."),
            ("No tracking cookies", "This local prototype does not intentionally use advertising trackers or third-party analytics cookies. Review dependencies and deployed pages before making a public claim."),
        ],
    },
    "community": {
        "title": "Community Standards and Prohibited Items",
        "sections": [
            ("Respect and honesty", "Use accurate descriptions and seller-reported availability. Do not threaten, harass, discriminate, impersonate, scam, or publish another person's private information."),
            ("Prohibited content and goods", "Do not list counterfeit or stolen goods, stolen photos, illegal or dangerous items, recalled items where prohibited, stolen property, or content that infringes copyright, trademarks, privacy, or other rights. Applicable item rules vary by jurisdiction."),
            ("Review", "Use Report listing or Report seller when you see a concern. Reports enter an administrator review queue; this prototype has no staffed 24/7 moderation service."),
        ],
    },
    "seller-terms": {
        "title": "Seller Terms and Listing Rules",
        "sections": [
            ("Approval and listings", "A seller must be active and approved to manage listings. Provide accurate furniture details, prices, condition, photos, and seller-reported availability. The platform does not independently verify stock or claims."),
            ("Rights to content", "You must have the rights or permissions needed for photos, descriptions, logos, and other content you upload. You retain ownership of your content to the extent provided by law. You grant the operator a limited, non-exclusive permission to host, store, process, and display content as needed to operate and secure the service, including showing published seller pages and listings."),
            ("No transaction guarantee", "This prototype does not process payment, arrange delivery, or guarantee a sale. Do not promise a service feature that is not available."),
        ],
    },
    "buyer-safety": {
        "title": "Buyer Safety and Fraud Prevention",
        "sections": [
            ("Before arranging a purchase", "Inspect furniture where practical, independently confirm seller identity and item condition, and agree directly on collection or delivery details. Listings and availability are seller-reported."),
            ("Avoid fraud", "Be cautious of advance-payment pressure, unusually low prices, requests for verification codes, suspicious links, or requests to share passwords or identity documents. Keep communication on-platform when available. The current prototype does not include in-app messaging or payments."),
            ("Report concerns", "Use Report seller or Report listing. Do not send money based solely on a listing or an AI-generated draft."),
        ],
    },
    "ip-complaints": {
        "title": "Intellectual Property and Copyright Complaints",
        "sections": [
            ("Our materials", "Original code, written content, design assets, and brand assets are protected to the extent permitted by applicable law. No claim is made that a copyright or trademark is registered. App name: [CONFIGURE APP NAME]. Operator: [CONFIGURE OWNER]. Do not copy another marketplace's logo, protected visual identity, proprietary text, or distinctive branding."),
            ("User content and permission", "Users must have rights or permission to submit photos, descriptions, logos, and other material. Users retain their content rights; they grant only the limited service-operation license described in Seller Terms. The operator does not automatically own uploaded user content."),
            ("Complaint process", "Submit a Report listing and choose Copyright or trademark infringement. Include the affected listing, the work or mark, your relationship to the rights holder, a description of the alleged use, and a safe way to follow up. Do not include passwords or unnecessary sensitive data. An administrator reviews the report and may restrict content when justified, records the decision, and notifies affected users where appropriate."),
            ("Counter-notices and repeat reports", "If content is restricted, use Contact Support and choose Copyright or trademark complaint or response to provide a response or counter-notice. Applicable statutory procedures, timelines, required declarations, and repeat-infringer rules depend on jurisdiction and are not implemented as a certified legal process. A qualified operator/legal reviewer must configure and follow the applicable process before public launch."),
        ],
    },
    "moderation": {
        "title": "Reporting and Moderation Policy",
        "sections": [
            ("Reports", "Authenticated users can report published listings or seller accounts with a reason and details. Only administrators can access the review queue and record a moderation outcome."),
            ("Review limits", "Reports are reviewed by an authorized administrator when available. This prototype does not provide a 24/7 human response, defined service level, or appeal deadline. Use Contact Support to request a review of a decision."),
            ("Privacy", "Reports are not public. Report contents are visible to the reporter and authorized administrators who need them for review."),
        ],
    },
    "suspension": {
        "title": "Account Suspension and Appeals",
        "sections": [
            ("Restrictions", "An administrator may suspend an account or restrict content to protect users, review a report, or address a policy concern. Suspended accounts cannot use protected functions; an affected account may use Contact Support to ask for review."),
            ("Review", "Explain the account or content affected and provide relevant information without sending passwords or payment details. No fixed response time is promised in this prototype. Suspended accounts cannot sign in to the in-app support form; the operator must configure and monitor this contact before launch: [CONFIGURE REAL SUPPORT CONTACT]."),
        ],
    },
    "account-data": {
        "title": "Account Closure and Data Requests",
        "sections": [
            ("Submit a request", "Use Privacy & data requests while signed in to request access, correction, export, or account closure. If you cannot sign in, use the configured privacy contact: [CONFIGURE REAL CONTACT]."),
            ("What closure means", "A closure request is reviewed; it does not instantly delete the account. Listings may be unpublished or anonymized after review. Conversations, support/report records, audit events, and backup copies may need limited retention for safety, dispute resolution, security, or legal obligations. The actual retention periods and deletion process are not yet configured: [DEFINE BEFORE LAUNCH]."),
            ("Scope", "Requests are handled according to applicable law after the operator and jurisdiction are identified. This draft does not guarantee GDPR or other legal compliance."),
        ],
    },
    "ai-disclosure": {
        "title": "AI Assistance Disclosure",
        "sections": [
            ("Local processing", "Product descriptions and optional seller reply drafts are generated by Ollama on the controlled local computer. For a reply draft, the listing facts, latest buyer message, and policy details entered for that draft are sent to local Ollama only; there is no cloud AI fallback."),
            ("Review and limits", "AI output may be incorrect or incomplete. Review and edit every draft. A reply draft stays in the message form and is never sent automatically. If Ollama is unavailable or output cannot pass the conservative wording check, the app shows a clearly labeled deterministic fallback."),
        ],
    },
}
