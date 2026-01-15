import pytest

from inq_service_svc.models import User, Inquiry, UserRole, InquiryStatus
from inq_service_svc.services.inquiry_service import assign_staff, create_inquiry
from inq_service_svc.services.classifier import ClassificationResult
from inq_service_svc.schemas.inquiry import InquiryCreate
from unittest.mock import patch


def test_no_staff_returns_none(db_session):
    # Only create an admin user
    admin = User(email="admin@example.com", hashed_password="h", name="Admin", role=UserRole.Admin)
    db_session.add(admin)
    db_session.commit()

    assert assign_staff(db_session) is None


def test_staff_with_zero_inquiries_returns_staff_id(db_session):
    staff = User(email="staff1@example.com", hashed_password="h", name="Staff1", role=UserRole.Staff)
    db_session.add(staff)
    db_session.commit()
    db_session.refresh(staff)

    res = assign_staff(db_session)
    assert res == staff.id


def test_multiple_staff_different_workloads_returns_lowest(db_session):
    staff_a = User(email="a@example.com", hashed_password="h", name="A", role=UserRole.Staff)
    staff_b = User(email="b@example.com", hashed_password="h", name="B", role=UserRole.Staff)
    db_session.add_all([staff_a, staff_b])
    db_session.commit()
    db_session.refresh(staff_a)
    db_session.refresh(staff_b)

    # Assign two active inquiries to staff_a
    inq1 = Inquiry(title="Q1", content="C1", customer_email="c1@example.com", status=InquiryStatus.New, assigned_user_id=staff_a.id)
    inq2 = Inquiry(title="Q2", content="C2", customer_email="c2@example.com", status=InquiryStatus.On_Hold, assigned_user_id=staff_a.id)
    # Assign a completed inquiry to staff_b (should be ignored)
    inq3 = Inquiry(title="Q3", content="C3", customer_email="c3@example.com", status=InquiryStatus.Completed, assigned_user_id=staff_b.id)

    db_session.add_all([inq1, inq2, inq3])
    db_session.commit()

    res = assign_staff(db_session)
    assert res == staff_b.id


def test_multiple_staff_equal_workloads_returns_any(db_session):
    staff_x = User(email="x@example.com", hashed_password="h", name="X", role=UserRole.Staff)
    staff_y = User(email="y@example.com", hashed_password="h", name="Y", role=UserRole.Staff)
    db_session.add_all([staff_x, staff_y])
    db_session.commit()
    db_session.refresh(staff_x)
    db_session.refresh(staff_y)

    # No active inquiries for either staff -> equal workload
    res = assign_staff(db_session)
    assert res in {staff_x.id, staff_y.id}


# New tests for create_inquiry service

def test_create_inquiry_persists_sets_status_and_classification(db_session):
    # create one staff to be assigned
    staff = User(email="svcstaff@example.com", hashed_password="h", name="S", role=UserRole.Staff)
    db_session.add(staff)
    db_session.commit()
    db_session.refresh(staff)

    with patch("inq_service_svc.services.inquiry_service.classify_inquiry") as mock_classify:
        mock_classify.return_value = ClassificationResult(category="Billing", urgency="High")

        payload = InquiryCreate(title="Billing issue", content="Charged twice", customer_email="c@test.com", customer_name="C")
        created = create_inquiry(db_session, payload)

        assert created.id is not None
        assert created.status == InquiryStatus.New
        assert created.category == "Billing"
        assert created.urgency == "High"

        # verify persisted in DB
        fetched = db_session.get(Inquiry, created.id)
        assert fetched is not None
        assert fetched.title == "Billing issue"
        assert fetched.customer_email == "c@test.com"


def test_create_inquiry_assigns_lowest_workload_staff_integration(db_session):
    # create two staff users
    staff_a = User(email="a2@example.com", hashed_password="h", name="A2", role=UserRole.Staff)
    staff_b = User(email="b2@example.com", hashed_password="h", name="B2", role=UserRole.Staff)
    db_session.add_all([staff_a, staff_b])
    db_session.commit()
    db_session.refresh(staff_a)
    db_session.refresh(staff_b)

    # assign an active inquiry to staff_a to increase workload
    inq_existing = Inquiry(title="Old", content="x", customer_email="old@example.com", status=InquiryStatus.New, assigned_user_id=staff_a.id)
    db_session.add(inq_existing)
    db_session.commit()

    with patch("inq_service_svc.services.inquiry_service.classify_inquiry") as mock_classify:
        mock_classify.return_value = ClassificationResult(category="Technical", urgency="Low")

        payload = InquiryCreate(title="New problem", content="doesn't work", customer_email="n@test.com", customer_name="N")
        created = create_inquiry(db_session, payload)

        # assigned should favor staff_b (lower workload)
        assert created.assigned_user_id == staff_b.id


def test_create_inquiry_no_staff_results_in_none_assignment(db_session):
    # create only an admin user
    admin = User(email="onlyadmin@example.com", hashed_password="h", name="AdminOnly", role=UserRole.Admin)
    db_session.add(admin)
    db_session.commit()

    with patch("inq_service_svc.services.inquiry_service.classify_inquiry") as mock_classify:
        mock_classify.return_value = ClassificationResult(category="General", urgency="Medium")

        payload = InquiryCreate(title="No staff", content="help", customer_email="ns@test.com", customer_name=None)
        created = create_inquiry(db_session, payload)

        assert created.assigned_user_id is None
