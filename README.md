# VentureBridge — Week 1 Build

This build covers **only** the Week 1 milestone from the roadmap:

> **Week 1 — Core Foundation:** DB schema + auth system, role-based dashboards, base glass UI theme
> **Milestone:** Working login + role dashboards

Nothing from Week 2 (startup & job listings, document upload + admin review, investment interest
request flow) or Week 3 (milestone funding + agreement doc, live-photo verification, testing, audit
log, deployment) is included here on purpose. Those are separate deliverables.

## What's actually in this build

- **Database schema:** `User`, `Profile`, `LoginAttempt` (for rate limiting), `PasswordReset`. No
  Startup, Job, Investment, Verification, Message, or AuditLog tables — those belong to later weeks.
- **Auth system:**
  - Registration with role selection (Founder / Investor / Job Seeker — Admin is seeded directly,
    no public self-registration)
  - Login with **rate limiting**: 5 failed attempts from the same email + IP within 15 minutes
    triggers a lockout, tracked in the database
  - **Session fixation protection**: the session is cleared and a fresh one issued on every
    successful login/registration
  - Password hashing via bcrypt — plaintext passwords are never stored
  - Forgot/reset password with a single-use, 1-hour token (the reset link is shown directly on the
    page since no email server is configured — fully testable without one)
  - CSRF protection on every form (Flask-WTF), security headers (`X-Frame-Options`,
    `X-Content-Type-Options`, `Referrer-Policy`)
- **Role-based dashboards:** every one of the four roles (Founder, Investor, Job Seeker, Admin)
  logs in and lands on a dashboard built for that role. The Admin dashboard shows real platform
  stats (total users, users by role) since that data already exists at this stage; the other three
  roles get a clear "here's what's coming in Week 2/3" dashboard rather than fake placeholder stats
  for features that don't exist yet.
- **Base glass UI theme:** the full "liquid glass" (glassy + glossy) visual system — translucent
  blurred panels, gloss highlights, light/dark/system theme toggle applied before first paint, the
  VentureBridge logo as navbar mark + page watermark, responsive layout.
- **Profile management:** every role can edit their profile (photo, phone, bio, location,
  education, experience, industry, skills, interests) with a live completion-percentage indicator.

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

3. **Database** — SQLite by default, zero setup required. A file `venturebridge_week1.db` is
   created automatically. To use MySQL instead, set `DATABASE_URL` before running the app/seed:
   ```bash
   export DATABASE_URL="mysql+pymysql://USER:PASSWORD@localhost/venturebridge_week1"
   ```

4. **Seed the database** (creates all tables + one demo user per role):
   ```bash
   python seed.py
   ```

5. **Run the app:**
   ```bash
   python app.py
   ```
   Visit **http://localhost:5000**

## Demo credentials

Password for every account: **`Demo@1234`**

| Role       | Email                          |
|------------|---------------------------------|
| Admin      | admin@venturebridge.demo        |
| Founder    | aisha@venturebridge.demo        |
| Investor   | david@venturebridge.demo        |
| Job Seeker | sara@venturebridge.demo         |

## Verifying the Week 1 milestone

- [ ] Register a new account as each role, and log in/out
- [ ] 5 wrong-password attempts in a row locks out further tries for 15 minutes
- [ ] Forgot/reset password works end to end
- [ ] Each of the 4 roles lands on a dashboard built for that role after login
- [ ] Admin dashboard shows real user counts, broken down by role
- [ ] Editing your profile updates the completion percentage live
- [ ] Light/dark/system theme toggle works and persists across a reload
- [ ] A CSRF-missing form submission is rejected (400)

## Project structure

```
venturebridge_week1/
  app.py              # App factory, security headers, error handlers
  config.py           # Env-driven configuration (SQLite/MySQL)
  extensions.py       # Flask extension instances
  models.py           # User, Profile, LoginAttempt, PasswordReset ONLY
  forms.py            # Auth + profile + contact forms
  decorators.py       # Role-based access control
  utils.py            # Secure file upload handling (profile photos)
  seed.py             # Demo data — one user per role
  blueprints/
    auth.py            # register, login, logout, forgot/reset password
    main.py            # public pages, dashboard, profile
  templates/
  static/
    css/style.css      # The Week 1 "base glass UI theme" deliverable
    js/                # Theme toggle, misc UI
    img/logo.png
    uploads/logos/     # Profile photo uploads
```
