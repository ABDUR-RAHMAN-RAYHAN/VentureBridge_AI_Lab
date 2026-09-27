"""
Run this once after installing dependencies to create the database schema
and populate it with realistic demo data:

    python seed.py

Demo login credentials (password is the same for every demo account):
    Password: Demo@1234

    admin@venturebridge.demo        (Admin)
    aisha@venturebridge.demo        (Founder - GreenTech Solutions, verified)
    farhan@venturebridge.demo       (Founder - MediConnect, verified)
    david@venturebridge.demo        (Investor - has an active signed agreement + a pending request)
    meera@venturebridge.demo        (Investor - has a request mid-negotiation)
    sara@venturebridge.demo         (Job Seeker)
"""
import json
from datetime import datetime, timedelta, date
from app import create_app
from extensions import db
from models import (User, Profile, Startup, StartupDocument, Job, JobApplication,
                     InvestmentRequest, Agreement, FundingMilestone, FundingProposal, FundingProposalItem,
                     Connection, Message, IdentityVerification, VerificationPhoto)

DEMO_PASSWORD = "Demo@1234"


def make_user(full_name, email, role):
    u = User(full_name=full_name, email=email, role=role)
    u.set_password(DEMO_PASSWORD)
    db.session.add(u)
    db.session.flush()
    db.session.add(Profile(user_id=u.id, bio=f"Demo {role} account.", industry="Technology",
                            location="Dhaka, Bangladesh", skills="Communication, Strategy",
                            interests="Startups, Innovation"))
    return u


def run():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = make_user("Platform Admin", "admin@venturebridge.demo", "admin")
        aisha = make_user("Aisha Rahman", "aisha@venturebridge.demo", "founder")
        farhan = make_user("Farhan Kabir", "farhan@venturebridge.demo", "founder")
        david = make_user("David Chen", "david@venturebridge.demo", "investor")
        sara = make_user("Sara Islam", "sara@venturebridge.demo", "jobseeker")
        db.session.commit()

        # ---- Startups ----
        greentech = Startup(
            founder_id=aisha.id, name="GreenTech Solutions",
            description="Solar-powered irrigation systems for smallholder farmers across South Asia.",
            industry="CleanTech", stage="Early Stage", location="Dhaka, Bangladesh",
            website="https://greentech.example.com", founded_year=2023,
            business_model="B2B hardware + subscription monitoring", team_size=8,
        )
        mediconnect = Startup(
            founder_id=farhan.id, name="MediConnect",
            description="Telemedicine platform connecting rural patients with urban specialists.",
            industry="HealthTech", stage="MVP", location="Chattogram, Bangladesh",
            website="https://mediconnect.example.com", founded_year=2024,
            business_model="Per-consultation commission", team_size=4,
        )
        agrilink = Startup(
            founder_id=aisha.id, name="AgriLink Marketplace",
            description="A B2B marketplace connecting farmers directly with wholesale buyers.",
            industry="AgriTech", stage="Idea", location="Rajshahi, Bangladesh",
            founded_year=2025, business_model="Transaction fee marketplace", team_size=2,
        )
        solargrid = Startup(
            founder_id=farhan.id, name="SolarGrid Energy",
            description="Grid-scale solar battery storage systems for rural micro-grids.",
            industry="CleanTech", stage="Growth", location="Rajshahi, Bangladesh",
            founded_year=2021, business_model="B2B hardware + long-term service contracts", team_size=12,
        )
        db.session.add_all([greentech, mediconnect, agrilink, solargrid])
        db.session.flush()

        # Documents: GreenTech + MediConnect + SolarGrid fully approved (so KNN has candidates to compare),
        # AgriLink still pending (so the "hidden until verified" behavior is also demonstrable)
        gt_doc = StartupDocument(startup_id=greentech.id, doc_type="Trade License",
                                  filename="documents/demo_trade_license_greentech.pdf",
                                  status="approved", reviewed_by=admin.id, reviewed_at=datetime.utcnow())
        gt_doc2 = StartupDocument(startup_id=greentech.id, doc_type="Certificate of Incorporation",
                                   filename="documents/demo_incorporation_greentech.pdf",
                                   status="approved", reviewed_by=admin.id, reviewed_at=datetime.utcnow())
        mc_doc = StartupDocument(startup_id=mediconnect.id, doc_type="Trade License",
                                  filename="documents/demo_trade_license_mediconnect.pdf",
                                  status="approved", reviewed_by=admin.id, reviewed_at=datetime.utcnow())
        sg_doc = StartupDocument(startup_id=solargrid.id, doc_type="Trade License",
                                  filename="documents/demo_trade_license_solargrid.pdf",
                                  status="approved", reviewed_by=admin.id, reviewed_at=datetime.utcnow())
        al_doc = StartupDocument(startup_id=agrilink.id, doc_type="Trade License",
                                  filename="documents/demo_trade_license_agrilink.pdf",
                                  status="pending")
        db.session.add_all([gt_doc, gt_doc2, mc_doc, sg_doc, al_doc])
        db.session.commit()
        greentech.refresh_document_status()
        mediconnect.refresh_document_status()
        solargrid.refresh_document_status()
        agrilink.refresh_document_status()

        # ---- Jobs ----
        job1 = Job(startup_id=greentech.id, title="Embedded Systems Engineer",
                   description="Design firmware for our solar irrigation controllers.",
                   required_skills="C, Embedded Linux, IoT", experience_level="2-4 years",
                   job_type="Full-time", location="Dhaka, Bangladesh", salary_min=60000, salary_max=90000,
                   deadline=date.today() + timedelta(days=30), status="open")
        job2 = Job(startup_id=greentech.id, title="Field Sales Associate",
                   description="Visit farming communities and onboard new customers.",
                   required_skills="Sales, Bengali/English", experience_level="1+ years",
                   job_type="Contract", location="Rangpur, Bangladesh", status="open")
        job3 = Job(startup_id=mediconnect.id, title="React Native Developer",
                   description="Build our patient-facing mobile app.",
                   required_skills="React Native, TypeScript", experience_level="2+ years",
                   job_type="Remote", location="Remote", salary_min=50000, salary_max=80000, status="open")
        db.session.add_all([job1, job2, job3])
        db.session.commit()

        # ---- One sample job application ----
        application = JobApplication(job_id=job1.id, applicant_id=sara.id,
                                      cv_filename="cv/demo_sara_islam_cv.pdf",
                                      cover_message="I'd love to bring my embedded systems background to GreenTech.",
                                      status="reviewing")
        db.session.add(application)

        # ---- Investment requests: full lifecycle demo ----
        # REQ1 (david -> greentech): smooth path all the way to a fully signed, active agreement
        req1 = InvestmentRequest(investor_id=david.id, startup_id=greentech.id,
                                  message="Impressed by your traction with smallholder farmers — "
                                          "I'd like to discuss backing your next expansion phase.",
                                  status="active", decided_at=datetime.utcnow())
        db.session.add(req1)
        db.session.commit()

        proposal1 = FundingProposal(request_id=req1.id, version=1, proposed_by_id=aisha.id,
                                     total_amount=50000, status="accepted",
                                     notes="Funding to manufacture our next hardware batch, run a 3-district "
                                           "field pilot, and hire sales associates to support the rollout.")
        db.session.add(proposal1)
        db.session.flush()
        db.session.add_all([
            FundingProposalItem(proposal_id=proposal1.id, reason="Prototype hardware batch (50 units)", amount=20000),
            FundingProposalItem(proposal_id=proposal1.id, reason="Field pilot in 3 districts", amount=20000),
            FundingProposalItem(proposal_id=proposal1.id, reason="Sales & marketing scale-up", amount=10000),
        ])

        agreement1 = Agreement(request_id=req1.id, reference_no=f"VB-AGR-{req1.id:06d}-DEMO",
                                funding_amount=50000, platform_fee_percent=2.5, status="active",
                                benefit_terms="8% equity stake in GreenTech Solutions in exchange for "
                                              "$50,000 in milestone-based funding.",
                                founder_signed_name=aisha.full_name, founder_signed_at=datetime.utcnow() - timedelta(days=2),
                                investor_signed_name=david.full_name, investor_signed_at=datetime.utcnow() - timedelta(days=1),
                                investor_deposited_at=datetime.utcnow() - timedelta(days=1),
                                investor_deposit_note="Bank transfer #TXN-88213 (full amount)",
                                admin_confirmed_deposit_at=datetime.utcnow() - timedelta(hours=20),
                                admin_confirmed_deposit_by=admin.id)
        db.session.add(agreement1)
        db.session.flush()
        db.session.add_all([
            FundingMilestone(agreement_id=agreement1.id, title="Prototype hardware batch (50 units)",
                              description="Funds cover component sourcing and assembly.",
                              amount=20000, status="released", order_index=0,
                              released_at=datetime.utcnow() - timedelta(hours=18), released_by=admin.id,
                              proof_document_filename="proof/demo_hardware_receipt.pdf",
                              proof_description="Invoice from supplier for 50 controller units.",
                              proof_uploaded_at=datetime.utcnow() - timedelta(hours=6)),
            FundingMilestone(agreement_id=agreement1.id, title="Field pilot in 3 districts",
                              description="Deployment, farmer training, and monitoring.",
                              amount=20000, status="pending", order_index=1),
            FundingMilestone(agreement_id=agreement1.id, title="Sales & marketing scale-up",
                              description="Hiring field sales associates and marketing materials.",
                              amount=10000, status="pending", order_index=2),
        ])

        # Connection + sample messages for the fully-signed pair
        a, b = sorted([david.id, aisha.id])
        connection = Connection(user_a_id=a, user_b_id=b, source="investment")
        db.session.add(connection)
        db.session.flush()
        db.session.add_all([
            Message(connection_id=connection.id, sender_id=david.id, receiver_id=aisha.id,
                    body="Thanks for signing! Excited to see the pilot rollout.",
                    created_at=datetime.utcnow() - timedelta(hours=2)),
            Message(connection_id=connection.id, sender_id=aisha.id, receiver_id=david.id,
                    body="Likewise! We'll share the first milestone report next week.",
                    created_at=datetime.utcnow() - timedelta(hours=1)),
        ])

        # REQ2 (david -> mediconnect): simple, still awaiting the founder's initial response
        req2 = InvestmentRequest(investor_id=david.id, startup_id=mediconnect.id,
                                  message="Interested in learning more about your telemedicine model.",
                                  status="pending")
        db.session.add(req2)

        # REQ3 (meera -> greentech): mid-negotiation, showing the counter-proposal loop
        meera = make_user("Meera Chowdhury", "meera@venturebridge.demo", "investor")
        db.session.commit()
        req3 = InvestmentRequest(investor_id=meera.id, startup_id=greentech.id,
                                  message="Would love to help fund your expansion into new regions.",
                                  status="awaiting_founder_review")
        db.session.add(req3)
        db.session.commit()

        proposal3a = FundingProposal(request_id=req3.id, version=1, proposed_by_id=aisha.id,
                                      total_amount=30000, status="superseded",
                                      notes="Expansion funding for entering the Sylhet region market.")
        db.session.add(proposal3a)
        db.session.flush()
        db.session.add_all([
            FundingProposalItem(proposal_id=proposal3a.id, reason="Second manufacturing line", amount=18000),
            FundingProposalItem(proposal_id=proposal3a.id, reason="Regional certification & compliance", amount=12000),
        ])

        proposal3b = FundingProposal(request_id=req3.id, version=2, proposed_by_id=meera.id,
                                      total_amount=25000, status="pending",
                                      notes="Reduced scope for phase one — let's revisit the full amount "
                                            "once the pilot region proves out.")
        db.session.add(proposal3b)
        db.session.flush()
        db.session.add_all([
            FundingProposalItem(proposal_id=proposal3b.id, reason="Second manufacturing line", amount=15000),
            FundingProposalItem(proposal_id=proposal3b.id, reason="Regional certification & compliance", amount=10000),
        ])

        # REQ4 (farhan -> meera): founder-initiated direct funding ask, showing the
        # equity/share negotiation flow (amount + equity%, no item breakdown).
        req4 = InvestmentRequest(investor_id=meera.id, startup_id=mediconnect.id,
                                  message="We're ready to scale MediConnect to two more districts — "
                                          "would you be open to backing this round?",
                                  initiated_by="founder", status="awaiting_investor_review")
        db.session.add(req4)
        db.session.commit()

        proposal4 = FundingProposal(request_id=req4.id, version=1, proposed_by_id=farhan.id,
                                     total_amount=40000, equity_percent=6.0, status="pending",
                                     notes="We're ready to scale MediConnect to two more districts — "
                                           "would you be open to backing this round?")
        db.session.add(proposal4)
        db.session.flush()
        db.session.add(FundingProposalItem(proposal_id=proposal4.id, reason="Total funding requested", amount=40000))


        # ---- Identity verification samples ----
        v1 = IdentityVerification(user_id=aisha.id, doc_type="National ID", status="approved",
                                   id_document_filename="verification/demo_nid_aisha.pdf",
                                   reviewed_by=admin.id, reviewed_at=datetime.utcnow())
        db.session.add(v1)
        db.session.flush()
        db.session.add_all([
            VerificationPhoto(verification_id=v1.id, filename="verification/demo_aisha_1.jpg", slot=1),
            VerificationPhoto(verification_id=v1.id, filename="verification/demo_aisha_2.jpg", slot=2),
            VerificationPhoto(verification_id=v1.id, filename="verification/demo_aisha_3.jpg", slot=3),
        ])
        v2 = IdentityVerification(user_id=david.id, doc_type="Passport", status="pending",
                                   id_document_filename="verification/demo_nid_david.pdf")
        db.session.add(v2)
        db.session.flush()
        db.session.add_all([
            VerificationPhoto(verification_id=v2.id, filename="verification/demo_david_1.jpg", slot=1),
            VerificationPhoto(verification_id=v2.id, filename="verification/demo_david_2.jpg", slot=2),
            VerificationPhoto(verification_id=v2.id, filename="verification/demo_david_3.jpg", slot=3),
        ])
        v3 = IdentityVerification(user_id=farhan.id, doc_type="National ID", status="approved",
                                   id_document_filename="verification/demo_nid_farhan.pdf",
                                   reviewed_by=admin.id, reviewed_at=datetime.utcnow())
        db.session.add(v3)
        db.session.flush()
        db.session.add_all([
            VerificationPhoto(verification_id=v3.id, filename="verification/demo_farhan_1.jpg", slot=1),
            VerificationPhoto(verification_id=v3.id, filename="verification/demo_farhan_2.jpg", slot=2),
            VerificationPhoto(verification_id=v3.id, filename="verification/demo_farhan_3.jpg", slot=3),
        ])
        v4 = IdentityVerification(user_id=meera.id, doc_type="National ID", status="approved",
                                   id_document_filename="verification/demo_nid_meera.pdf",
                                   reviewed_by=admin.id, reviewed_at=datetime.utcnow())
        db.session.add(v4)
        db.session.flush()
        db.session.add_all([
            VerificationPhoto(verification_id=v4.id, filename="verification/demo_meera_1.jpg", slot=1),
            VerificationPhoto(verification_id=v4.id, filename="verification/demo_meera_2.jpg", slot=2),
            VerificationPhoto(verification_id=v4.id, filename="verification/demo_meera_3.jpg", slot=3),
        ])

        db.session.commit()
        print("Database seeded successfully.")
        print(f"Demo password for all accounts: {DEMO_PASSWORD}")


if __name__ == "__main__":
    run()
