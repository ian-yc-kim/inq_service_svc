import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from inq_service_svc.models import (
    User,
    Inquiry,
    Message,
    UserRole,
    InquiryStatus,
    MessageSenderType,
)


def test_create_and_retrieve_user(db_session):
    # create
    user = User(email="alice@example.com", hashed_password="hash", name="Alice", role=UserRole.Admin)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # retrieve
    stmt = select(User).where(User.email == "alice@example.com")
    result = db_session.execute(stmt).scalar_one()
    assert result.email == "alice@example.com"
    assert result.name == "Alice"
    assert result.role == UserRole.Admin


def test_inquiry_assigned_to_user(db_session):
    user = User(email="bob@example.com", hashed_password="hash2", name="Bob", role=UserRole.Staff)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    inquiry = Inquiry(title="Help", content="Please help", customer_email="cust@example.com", assigned_user_id=user.id)
    db_session.add(inquiry)
    db_session.commit()
    db_session.refresh(inquiry)

    stmt = select(Inquiry).where(Inquiry.id == inquiry.id)
    fetched = db_session.execute(stmt).scalar_one()
    assert fetched.assigned_user is not None
    assert fetched.assigned_user.email == "bob@example.com"


def test_message_linked_to_inquiry(db_session):
    user = User(email="carol@example.com", hashed_password="h3", name="Carol", role=UserRole.Staff)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    inquiry = Inquiry(title="Issue", content="There is an issue", customer_email="cust2@example.com", assigned_user=user)
    db_session.add(inquiry)
    db_session.commit()
    db_session.refresh(inquiry)

    message = Message(inquiry_id=inquiry.id, content="We are on it", sender_type=MessageSenderType.Staff)
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    stmt_msg = select(Message).where(Message.id == message.id)
    fetched_msg = db_session.execute(stmt_msg).scalar_one()
    assert fetched_msg.inquiry.id == inquiry.id

    # relationship backref
    stmt_inq = select(Inquiry).where(Inquiry.id == inquiry.id)
    fetched_inq = db_session.execute(stmt_inq).scalar_one()
    assert len(fetched_inq.messages) >= 1
    assert any(m.id == message.id for m in fetched_inq.messages)


def test_inquiry_status_default_and_enum(db_session):
    inquiry = Inquiry(title="NewQ", content="Content", customer_email="newcust@example.com")
    db_session.add(inquiry)
    db_session.commit()
    db_session.refresh(inquiry)

    assert inquiry.status == InquiryStatus.New


def test_user_email_unique_constraint(db_session):
    user1 = User(email="unique@example.com", hashed_password="p1", name="U1", role=UserRole.Staff)
    db_session.add(user1)
    db_session.commit()

    user2 = User(email="unique@example.com", hashed_password="p2", name="U2", role=UserRole.Admin)
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
