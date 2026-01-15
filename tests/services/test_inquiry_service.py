import pytest

from inq_service_svc.models import User, Inquiry, UserRole, InquiryStatus
from inq_service_svc.services.inquiry_service import assign_staff


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
