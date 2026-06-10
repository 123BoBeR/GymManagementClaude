"""Testy serwisu płatności (PaymentService)."""

from datetime import date, datetime
from models import db, Payment
from services import PaymentService, BANK_ACCOUNT


class TestPaymentService:

    def test_months_for_member_contains_current_month(self, seeded):
        member = seeded["member"]
        months = PaymentService.months_for_member(member)
        assert len(months) >= 1
        assert any(m["month_year"] == date.today().strftime("%Y-%m") for m in months)

    def test_months_for_member_pending_when_no_payment(self, seeded):
        member = seeded["member"]
        today_str = date.today().strftime("%Y-%m")
        months = PaymentService.months_for_member(member)
        current = next(m for m in months if m["month_year"] == today_str)
        assert current["status"] == "pending"
        assert current["payment_id"] is None
        assert current["amount"] == 99.0

    def test_months_for_member_shows_completed_status(self, seeded):
        member = seeded["member"]
        today_str = date.today().strftime("%Y-%m")
        db.session.add(Payment(member_id=member.id, amount=99.0,
                               month_year=today_str, status="completed",
                               transfer_number="TRF-0000-0000-0000",
                               paid_at=datetime.utcnow()))
        db.session.commit()
        months = PaymentService.months_for_member(member)
        current = next(m for m in months if m["month_year"] == today_str)
        assert current["status"] == "completed"
        assert current["payment_id"] is not None

    def test_amount_for_monthly(self, seeded):
        assert PaymentService.amount_for(seeded["member"]) == 99.0

    def test_amount_for_annual(self, seeded):
        member = seeded["member"]
        member.subscription_type = "annual"
        db.session.commit()
        assert PaymentService.amount_for(member) == 799.0

    def test_amount_for_day_pass(self, seeded):
        member = seeded["member"]
        member.subscription_type = "day_pass"
        db.session.commit()
        assert PaymentService.amount_for(member) == 29.0

    def test_generate_transfer_number_format(self):
        trn = PaymentService.generate_transfer_number()
        parts = trn.split("-")
        assert parts[0] == "TRF"
        assert len(parts) == 4
        assert all(len(p) == 4 for p in parts[1:])

    def test_generate_transfer_number_is_unique(self):
        nums = {PaymentService.generate_transfer_number() for _ in range(20)}
        assert len(nums) > 1

    def test_initiate_creates_pending_payment(self, seeded):
        member = seeded["member"]
        today_str = date.today().strftime("%Y-%m")
        ok, data = PaymentService.initiate(member.id, today_str)
        assert ok is True
        assert "payment_id" in data
        assert data["transfer_number"].startswith("TRF-")
        assert data["bank_account"] == BANK_ACCOUNT
        payment = db.session.get(Payment, data["payment_id"])
        assert payment.status == "pending"

    def test_initiate_returns_same_payment_on_repeat(self, seeded):
        member = seeded["member"]
        today_str = date.today().strftime("%Y-%m")
        _, d1 = PaymentService.initiate(member.id, today_str)
        _, d2 = PaymentService.initiate(member.id, today_str)
        assert d1["payment_id"] == d2["payment_id"]

    def test_initiate_rejects_already_completed(self, seeded):
        member = seeded["member"]
        today_str = date.today().strftime("%Y-%m")
        db.session.add(Payment(member_id=member.id, amount=99.0,
                               month_year=today_str, status="completed",
                               transfer_number="TRF-1111-2222-3333",
                               paid_at=datetime.utcnow()))
        db.session.commit()
        ok, data = PaymentService.initiate(member.id, today_str)
        assert ok is False
        assert "error" in data

    def test_initiate_rejects_nonexistent_member(self, seeded):
        ok, data = PaymentService.initiate(9999, "2026-01")
        assert ok is False

    def test_confirm_marks_completed_with_timestamp(self, seeded):
        member = seeded["member"]
        today_str = date.today().strftime("%Y-%m")
        _, init_data = PaymentService.initiate(member.id, today_str)
        ok, msg = PaymentService.confirm(init_data["payment_id"], member.id)
        assert ok is True
        payment = db.session.get(Payment, init_data["payment_id"])
        assert payment.status == "completed"
        assert payment.paid_at is not None

    def test_confirm_rejects_wrong_member(self, seeded):
        member = seeded["member"]
        today_str = date.today().strftime("%Y-%m")
        _, init_data = PaymentService.initiate(member.id, today_str)
        ok, msg = PaymentService.confirm(init_data["payment_id"], member.id + 999)
        assert ok is False
        assert "dostępu" in msg

    def test_confirm_rejects_nonexistent_payment(self, seeded):
        ok, msg = PaymentService.confirm(9999, seeded["member"].id)
        assert ok is False

    def test_confirm_rejects_already_completed(self, seeded):
        member = seeded["member"]
        today_str = date.today().strftime("%Y-%m")
        _, init_data = PaymentService.initiate(member.id, today_str)
        PaymentService.confirm(init_data["payment_id"], member.id)
        ok, msg = PaymentService.confirm(init_data["payment_id"], member.id)
        assert ok is False
        assert "już" in msg
