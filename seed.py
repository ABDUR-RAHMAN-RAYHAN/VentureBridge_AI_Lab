"""
Week 1 milestone: DB schema + auth system + role-based dashboards + base
glass UI theme. Run once after installing dependencies:

    python seed.py

Demo login credentials (same password for every account):
    Password: Demo@1234

    admin@venturebridge.demo        (Admin)
    aisha@venturebridge.demo        (Founder)
    david@venturebridge.demo        (Investor)
    sara@venturebridge.demo         (Job Seeker)

Startup listings, job postings, investment/funding workflows, messaging,
identity verification, and the audit log are Week 2 / Week 3 features and
are intentionally NOT part of this build.
"""
from app import create_app
from extensions import db
from models import User, Profile

DEMO_PASSWORD = "Demo@1234"


def make_user(full_name, email, role, **profile_kwargs):
    u = User(full_name=full_name, email=email, role=role)
    u.set_password(DEMO_PASSWORD)
    db.session.add(u)
    db.session.flush()
    db.session.add(Profile(user_id=u.id, **profile_kwargs))
    return u


def run():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        make_user("Platform Admin", "admin@venturebridge.demo", "admin",
                   bio="Platform administrator account.")
        make_user("Aisha Rahman", "aisha@venturebridge.demo", "founder",
                   bio="Building GreenTech Solutions — solar irrigation for smallholder farmers.",
                   location="Dhaka, Bangladesh", industry="CleanTech")
        make_user("David Chen", "david@venturebridge.demo", "investor",
                   bio="Looking to back early-stage climate and health startups.",
                   location="Singapore", industry="Venture Capital")
        make_user("Sara Islam", "sara@venturebridge.demo", "jobseeker",
                   bio="Embedded systems engineer looking for an early-stage role.",
                   location="Dhaka, Bangladesh", industry="Technology")

        db.session.commit()
        print("Week 1 database seeded successfully.")
        print(f"Demo password for all accounts: {DEMO_PASSWORD}")


if __name__ == "__main__":
    run()
