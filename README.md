# VentureBridge

A secure, full-stack startup collaboration platform connecting Founders, Investors, and Job
Seekers — built entirely in **Python (Flask)**, with SQLAlchemy (SQLite by default, MySQL-ready),
HTML/CSS/vanilla JS. "Liquid glass" (glassy + glossy) UI in blue/green, built around the
VentureBridge logo.

## Features implemented

- Registration/login/logout with hashed passwords, rate-limited login (5 attempts / 15 min,
  tracked in DB), session regeneration on login/registration, HttpOnly/SameSite cookies.
- Forgot/reset password with single-use, 1-hour tokens (reset link shown on-page since no SMTP is
  configured — fully testable without an email server).
- Role-based dashboards (Founder / Investor / Job Seeker / Admin) with live Chart.js charts.
- Profile management with a live completion-percentage indicator.
- **Founder identity verification is required** before a founder can list a startup or post a job
  — an unverified founder is redirected straight to the live-photo verification page.
- **Startup listings** — a Trade License upload is mandatory to publish; additional documents
  (Certificate of Incorporation, Tax Registration, Other) can be added anytime. A startup is only
  "Documents Verified" once every submitted document is admin-approved, and **only then does it
  appear in the public directory, landing-page features, or job listings** — unverified startups
  are invisible to everyone except their own founder and admins.
- Public startup & job directories with keyword search, filters, and pagination (both scoped to
  verified/active startups only).
- Job postings, applications with **required CV upload**, duplicate-application prevention, and a
  Submitted → Reviewing → Shortlisted → Rejected/Accepted status pipeline.
- **Investment negotiation workflow** (multi-step, not a single "accept" click):
  1. Investor sends interest with a message.
  2. Founder accepts and submits a **financial distribution proposal** — total amount requested
     plus a line-item breakdown of exactly what it's for.
  3. The investor reviews it and either **accepts** the terms or **sends back changes** (a revised
     total + breakdown); this can go back and forth any number of rounds, with full version
     history preserved.
  4. Once either party accepts the other's current terms, the founder builds a **milestone
     schedule** (amounts must sum to the agreed total) and VentureBridge generates a formal,
     contract-structured **Investment & Funding Agreement** — parties, background, use-of-funds
     breakdown, milestone schedule, benefit terms, representations, a breach/dispute/governing-law
     clause, and platform-role disclosure.
  5. **Both the founder and the investor must individually sign** the agreement (typed legal name
     + explicit confirmation, timestamped) before it becomes active.
  6. Only once **both signatures are in** does VentureBridge create the connection between them and
     unlock messaging — "the journey starts together."
- **Milestone fund release**: only an Admin releases each milestone's funds (never a lump sum,
  and never before the agreement is fully signed); a platform fee percentage is applied and logged
  on every release.
- **Identity verification with 3 required live-captured photos** (via device camera, not file
  upload) for National ID / Passport / Driving License, with a full submission history and
  admin approve/reject-with-reason queue.
- Messaging restricted server-side to users who share a connection (which, per the flow above, only
  exists after a fully-signed agreement).
- Admin panel: user/startup/job activate-deactivate (with confirmation dialogs), document review
  queue, verification review queue, and a full audit log.
- CSRF protection on every form (Flask-WTF), parameterized queries throughout (SQLAlchemy ORM),
  randomized upload filenames, extension + magic-byte file validation, security headers
  (X-Frame-Options, X-Content-Type-Options, Referrer-Policy), graceful error pages.
- Light/dark/system theme toggle, applied before first paint (no flash), glassy+glossy panels in
  both themes, logo watermark, responsive layout.
- Two real AI algorithms — a CSP-based milestone scheduler and a KNN-based startup recommender —
  see the **AI Algorithms** section below for details.

## AI Algorithms

Two genuine, working AI algorithms are implemented (in `algorithms/`), each solving a real
problem in the platform rather than being decorative:

### 1. Constraint Satisfaction Problem (CSP) — Milestone Scheduler
`algorithms/csp_scheduler.py`. When a founder needs to split a funding total into milestone
payments, they can click **"Auto-Generate with CSP Solver"** on the milestone-builder page
instead of doing the arithmetic by hand. This is formulated as a genuine CSP:

- **Variables:** the dollar amount of each milestone
- **Domains:** integers between 10% and 50% of the total (configurable), so no single milestone
  is trivially small or unreasonably large
- **Constraints:** all milestone amounts must sum exactly to the agreed total

It's solved with **backtracking search + forward checking**: before assigning each variable, the
solver computes the feasible interval for that value given what's left to allocate and how many
milestones remain, pruning the domain rather than discovering infeasibility after the fact. If a
requested milestone count is mathematically unsatisfiable (e.g. 11 milestones at a 10% minimum
each, which is already 110%), the solver correctly reports that rather than returning a bad
answer. Candidate values are shuffled so repeated runs surface different valid schedules, not one
fixed even split.

### 2. K-Nearest Neighbors (KNN) — Similar Startups Recommender
`algorithms/knn_recommender.py`. Every startup's public profile page shows a "Similar Startups"
section, ranked by a real KNN search over mixed-type features:

- Industry (categorical), business stage (ordinal), team size and founding year (numeric,
  min-max normalized across the candidate pool), and required skills (compared via Jaccard
  similarity on the skill sets)
- Since the features are mixed types, plain Euclidean distance doesn't apply — the solver uses a
  **Gower distance** (the standard technique for KNN over mixed categorical/numeric data): each
  attribute contributes a distance normalized to [0, 1], averaged into one overall distance
- The K=3 nearest (lowest-distance) startups are shown with a similarity percentage

Both are demonstrated with real data-dependent behavior in the seed data — e.g. GreenTech Solutions
(CleanTech) is recommended alongside SolarGrid Energy (also CleanTech, similar skills) with a much
higher similarity score than MediConnect (HealthTech).

## Setup

1. **Install Python 3.10+** and create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Database — SQLite (default, zero setup):** nothing to configure. A file
   `venturebridge.db` will be created automatically.

   **Or MySQL:** create a database and set an environment variable before running the app/seed:
   ```bash
   # macOS/Linux
   export DATABASE_URL="mysql+pymysql://USER:PASSWORD@localhost/venturebridge"
   # Windows (PowerShell)
   $env:DATABASE_URL="mysql+pymysql://USER:PASSWORD@localhost/venturebridge"
   ```
   Then create the empty database first: `CREATE DATABASE venturebridge;`

4. **Seed the database** (creates all tables + realistic demo data):
   ```bash
   python seed.py
   ```

5. **Run the app:**
   ```bash
   python app.py
   ```
   Visit **http://localhost:5000**

6. **For production**, set a real `SECRET_KEY` environment variable, run behind HTTPS (so the
   Secure cookie flag applies), and use a production WSGI server (e.g. `gunicorn app:app`).

## Demo credentials

Password for every demo account: **`Demo@1234`**

| Role       | Email                          | Notes |
|------------|---------------------------------|-------|
| Admin      | admin@venturebridge.demo        | Review queues, user/startup/job management |
| Founder    | aisha@venturebridge.demo        | Identity-verified. Owns GreenTech Solutions (documents verified) + AgriLink Marketplace (pending) |
| Founder    | farhan@venturebridge.demo       | Identity-verified. Owns MediConnect (documents verified) + SolarGrid Energy (documents verified) |
| Investor   | david@venturebridge.demo        | Has a fully signed, active agreement with Aisha (GreenTech), and a separate pending interest sent to Farhan (MediConnect) awaiting his first response. His own identity verification is intentionally **pending** — sending a *new* interest requires an admin to approve it first. |
| Investor   | meera@venturebridge.demo        | Identity-verified. Has a request mid-negotiation with Aisha (GreenTech) — she countered the founder's proposal and it's awaiting Aisha's decision |
| Job Seeker | sara@venturebridge.demo         | Has one application already submitted |

## Try the end-to-end story

1. Log in as **Aisha** (founder) → try Dashboard → "List a Startup" — since Aisha is verified this
   works; a brand-new unverified founder would be redirected to identity verification first.
2. Browse Startups while logged out — **GreenTech Solutions, MediConnect, and SolarGrid Energy**
   all appear (documents approved); **AgriLink Marketplace** does not, since it's still pending
   admin review.
3. Open **GreenTech Solutions'** public page and scroll to **"Similar Startups"** — the KNN
   recommender ranks SolarGrid Energy (same CleanTech industry, overlapping skills) noticeably
   higher than MediConnect (different industry).
4. Log in as **Meera** (investor) → Investment Requests → her request to GreenTech is mid-negotiation
   (she sent back a counter-proposal). Log in as **Aisha** to see it from the founder's side —
   accept it, then on the milestone-builder page click **"Auto-Generate with CSP Solver"** to see
   the backtracking solver produce a valid split, before generating the agreement. Then have both
   **Aisha** and **Meera** sign it (in two separate logins) to watch messaging unlock only once
   both signatures are in.
5. Log in as **David** (investor) → My Requests → his GreenTech agreement is already fully signed
   and active — open the Investment & Funding Agreement document. Its 3 milestones are seeded at
   different stages of the fund-flow pipeline: one **released** (with a proof-of-use document
   already attached), one **held by VentureBridge** (ready for an admin to release), and one
   **sent by the investor** (ready for an admin to confirm receipt). Log in as **Admin** to try
   "Confirm Funds Received" and "Release to Founder" on the latter two.
6. Log in as **David** or **Aisha** → Messages — they're already connected with sample messages
   (because their agreement was fully signed in the seed data).
7. David's own identity verification is intentionally left **pending** in the seed data — try
   sending a new investment interest as David to a startup he hasn't requested yet (e.g. SolarGrid
   Energy) and you'll be redirected to verification first. Log in as **Admin** → Verification Queue
   to approve David's submission, then the interest can be sent.
8. Log in as **Farhan** (founder) → Investment Requests → David's pending interest in MediConnect
   is still waiting for Farhan's initial response — click "Accept & Send Proposal" to try the
   financial-distribution proposal form yourself, then optionally use the CSP solver again when
   you reach the milestone step.
9. Log in as **Aisha** or **David** → Dashboard → **Transaction History**, to see every milestone
   payment across their agreements and its current fund-flow stage in one ledger.
10. As Admin → Audit Log to see every action recorded, including proposal submissions, revisions,
    signatures, and every milestone fund-flow event.

## Project structure

```
venturebridge/
  app.py              # App factory, security headers, error handlers
  config.py           # Env-driven configuration (SQLite/MySQL)
  extensions.py       # Flask extension instances
  models.py           # SQLAlchemy models (full schema)
  forms.py            # WTForms (validation + CSRF)
  decorators.py       # Role-based access control
  utils.py            # Secure upload handling, audit logging
  seed.py             # Demo data seeding script
  blueprints/          # auth, main, startups, jobs, investment, messaging, admin
  algorithms/          # CSP milestone scheduler, KNN startup recommender
  templates/           # Jinja2 templates (glassy-glossy UI for the app, plain document
                        #   layout for generated legal documents like the agreement)
  static/
    css/style.css      # Liquid-glass theme (app pages)
    css/document.css   # Plain black-on-white theme (generated documents only)
    js/                # theme toggle, webcam capture, misc UI
    img/logo.png        # VentureBridge logo
    uploads/            # Runtime file uploads (documents, cv, verification, logos)
```

## Recent changes (this revision)

**Bug fixes (previous revision):**
- Identity verification (3 live photos) is now embedded directly on the **Edit Profile** page —
  there's no separate verification page to navigate to. It also now counts toward your profile's
  completion percentage; you can't reach 100% without it.
- Live-photo capture shows on-screen pose instructions ("Look straight ahead," "Turn slightly
  left," "Turn slightly right") instead of generic "Photo 1/2/3" labels.
- **Profile** is now a read-only view with a clear **Edit Profile** button, rather than opening
  straight into a form.
- Removed "About" from the top navbar (still reachable from the footer) and removed the separate
  "Admin" navbar link for admin users (all admin tools are already one click away from their
  Dashboard).
- Removed the "skills" field from startup listings and the `Startup` model entirely (Jobs still
  have a required-skills field, since that's a normal recruiting field).
- The generated **Investment & Funding Agreement** document now renders on its own plain
  black-on-white page — no site navbar, footer, or translucent styling — so it stays fully
  legible and looks like an actual document rather than a themed app screen. The contract
  language was also rewritten to be more precise and professional.
- The navbar now shows a clear active/hover state so you always know which page you're on.

**Critical bug fix (this revision) — profile save silently losing data:**
- Root cause found: the profile page had **two separate `<form>` elements** (profile fields, and
  identity verification) with two separate submit buttons. If someone filled in both sections but
  clicked the verification button, the browser only sent that form's fields — the profile fields
  (phone, experience, etc.) were silently never submitted, and any typed text was lost. This is
  exactly what caused the "saves fine with a photo, errors with just text" and "0% completion"
  reports.
- **Fixed** by merging both sections into one `<form>` with one **Save Profile** button. Profile
  fields always save; identity verification is processed in the same request only if you provided
  it (an NID/ID upload *and* all 3 live photos). If you only provide some of the verification data,
  your profile fields still save and you get a clear message about what's missing for verification
  specifically — nothing is silently dropped anymore.
- Added a **separate "Upload NID / ID Card" section** distinct from the live-photo capture, since
  verification now requires both an uploaded ID document and 3 live photos together.
- **Investors can no longer send investment interest before their identity is verified** — this
  was previously only enforced for founders creating startups/jobs, not investors.
- The **startup detail page now shows the founder's name (and email, once logged in)** — this was
  completely missing before, so investors had no way to identify who they were dealing with.
- Fixed a leftover bug from an earlier refactor: the investor dashboard's "Accepted" stat was
  silently stuck at 0 because it checked for an old status value (`"accepted"`) that no longer
  exists in the current negotiation flow (`"active"` is the correct value now).

**New: full milestone fund-flow tracking (previously missing entirely):**
Previously, "releasing a milestone" was a single admin button click with no record of the investor
actually sending money, and founders had no visibility into payments beyond that one click. Each
milestone now goes through four explicit, auditable stages:
1. **Investor marks funds as sent** — with a required reference/transaction note (`Mark as Sent`
   button on the agreement page, investor-only).
2. **Admin confirms receipt** — VentureBridge now explicitly "holds" the funds in custody before
   releasing them (`Confirm Funds Received`, admin-only).
3. **Admin releases to the founder** — same as before, but now only possible after step 2, and
   the platform fee is calculated at this point.
4. **Founder uploads proof of use** — after release, the founder can attach a document (e.g. an
   equipment purchase receipt) with a description, visible to both the investor and admin on the
   agreement page.
- **Transaction History** (`/investment/transactions`) — a new page for founders and investors
  showing every milestone across every agreement they're party to, with its current stage and
  last-updated date, so it's clear at a glance whether an investor has paid and whether a founder
  has actually received funds.
- **Payment summary stat cards** on both dashboards: founders see Total Expected / Received So Far
  / Pending Release / Not Yet Sent; investors see Total Committed / Sent So Far / Still Owed.
- All of these actions are logged to the audit trail (`milestone_marked_sent`,
  `milestone_receipt_confirmed`, `milestone_released`, `milestone_proof_uploaded`).

## Recent changes (latest revision)

**1. Signatures are now uploaded files, not typed text — and gate the download:**
- `SignatureForm` no longer takes a typed "legal name" — both the founder and the investor must
  **upload their signed copy** (a PDF, or a photo/scan of a wet signature, PNG/JPG) on the Sign
  Agreement page. Files are saved with randomized server-side filenames under
  `static/uploads/signatures/`.
- `Agreement.founder_signature_filename` / `Agreement.investor_signature_filename` replace the old
  `founder_signed_name` / `investor_signed_name` text columns.
- The **agreement document (print/PDF view) is now fully locked until both signatures are in**:
  before that, the page only shows a signing-status banner and a "Sign Now" link — the full
  contract body, the "Print / Save as PDF" button, and any fund-deposit/milestone controls are not
  rendered at all. Once `agreement.is_fully_signed()` is true, the full document renders, uploaded
  signatures are shown inline (an image preview for PNG/JPG, a "View signed PDF" link for PDFs),
  and the Print/Save-as-PDF button becomes active.

**2. Navbar notification center, for every role:**
- New `Notification` model + `notify(user_id, title, message, url)` helper (`utils.py`) that
  creates an in-app notification without ever raising — a notification failure never breaks the
  action that triggered it.
- A 🔔 bell icon now sits in the navbar for every logged-in user, with an unread-count badge and a
  dropdown (`/notifications/feed`) showing the most recent notifications; **"View all"** opens the
  full, paginated `/notifications` page. Clicking a notification marks it read and opens its link.
- Wired into every major event across the app: account activated/deactivated, identity verification
  approved/rejected, startup document approved/rejected, new investment interest sent/declined, a
  funding proposal submitted/revised/accepted, an agreement generated/awaiting a signature/fully
  signed, an investor's deposit sent/confirmed, a milestone released, a new job application, and a
  job application status change.
- **Every active admin is notified the moment something lands in a review queue**, not just the
  other roles: a founder/investor submitting NID + live-photo identity verification notifies every
  admin with a link straight to the **Verification Queue**, and a founder submitting a startup
  document (the initial Trade License, or any later document from the startup's Documents page)
  notifies every admin with a link straight to the **Document Review Queue**. Admins no longer have
  to remember to manually check those queues on every login — the bell tells them there's work
  waiting.

**3. Dashboard is now the first navbar link:**
- For logged-in users the navbar order is now **Dashboard → Startups → Jobs → Messages → Profile →
  🔔 → Logout**, instead of Startups coming first.

**4. Strong password requirements:**
- Passwords (registration and password reset) must now contain at least one uppercase letter, one
  lowercase letter, one digit, and one special character, in addition to the existing 8-character
  minimum. Each missing requirement is reported individually (e.g. "Password must contain at least
  one special character").
- Demo account passwords were updated accordingly — see **Demo credentials** below.

**Also fixed in this revision:**
- A crash (`AttributeError: 'str' object has no attribute 'filename'`) when saving the profile, or
  creating/editing a startup, with an existing photo/logo and no new file chosen. WTForms can leave
  a `FileField`'s `.data` populated with the already-stored filename (a plain string) rather than
  leaving it empty; the three call sites that pass a FileField's data into `save_upload()` (profile
  photo, startup logo on create, startup logo on edit) now guard with `hasattr(data, "filename")`
  first, and `save_upload()` itself was hardened the same way as a second line of defense.
- The navbar notification dropdown was being visually clipped by the navbar's own glass-effect
  container (`overflow:hidden`, needed for its glossy sheen). The navbar now uses `overflow:visible`
  with the sheen's rounding moved onto the sheen element itself, so the dropdown panel floats
  properly below the bell instead of being trapped inside the navbar's box.
- Static assets (`style.css`, `main.js`, `theme-init.js`) are now served with a cache-busting
  `?v=<last-modified-time>` query string (see `asset_url()` in `app.py`), so a browser that already
  has the site open always picks up the latest CSS/JS after a deploy instead of silently continuing
  to run a stale cached copy.
- Clicking a notification in the dropdown silently did nothing: the list was built by concatenating
  an `onclick="vbOpenNotification(..., "/some/url")"` string, and the double quotes from
  `JSON.stringify()` collided with the attribute's own double quotes, corrupting the markup. The
  dropdown is now built as real DOM nodes with an attached click listener instead of an HTML string,
  which also makes it safe for any future notification title/message/URL regardless of what
  characters it contains.

## Notes on scope

- This is not a real payment/financial transaction system — the milestone "funding" workflow
  records amounts, terms, and release events for transparency and trust-building; it does not move
  real money. Wire actual payment rails in only with proper regulatory/legal review.
- No social login, no automated government ID verification, no AI/ML matching — per the original
  brief, out of scope for this build.
- The camera-based live-photo capture requires the browser to grant camera permission; VentureBridge
  requests it only on the verification page (see the `Permissions-Policy` header in `app.py`).
