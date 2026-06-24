"""Testy PaymentService (services.py)."""
import pytest
from datetime import date
from models import Payment
from services import PaymentService, BANK_ACCOUNT
from tests.conftest import make_user, make_member


@pytest.fixture
def member(db):
    u = make_user(db, 'klient', 'pass', 'client')
    m = make_member(db, u)   # subscription_type='monthly'
    db.session.commit()
    return m


class TestAmountAndTransfer:
    def test_amount_for_monthly(self, db, member):
        assert PaymentService.amount_for(member) == 99.0

    def test_amount_for_annual(self, db, member):
        member.subscription_type = 'annual'
        db.session.commit()
        assert PaymentService.amount_for(member) == 799.0

    def test_amount_for_unknown_is_zero(self, db, member):
        member.subscription_type = 'bogus'
        db.session.commit()
        assert PaymentService.amount_for(member) == 0.0

    def test_transfer_number_format(self):
        trn = PaymentService.generate_transfer_number()
        parts = trn.split('-')
        assert parts[0] == 'TRF'
        assert len(parts) == 4
        assert all(len(p) == 4 for p in parts[1:])

    def test_transfer_numbers_vary(self):
        nums = {PaymentService.generate_transfer_number() for _ in range(20)}
        assert len(nums) > 1


class TestMonthsForMember:
    def test_returns_six_months(self, db, member):
        months = PaymentService.months_for_member(member)
        assert len(months) == 6

    def test_current_month_pending_by_default(self, db, member):
        today = date.today().strftime('%Y-%m')
        months = PaymentService.months_for_member(member)
        current = next(m for m in months if m['month_year'] == today)
        assert current['status'] == 'pending'
        assert current['payment_id'] is None
        assert current['amount'] == 99.0


class TestInitiate:
    def test_creates_pending(self, db, member):
        today = date.today().strftime('%Y-%m')
        ok, data = PaymentService.initiate(member.id, today)
        assert ok is True
        assert data['transfer_number'].startswith('TRF-')
        assert data['bank_account'] == BANK_ACCOUNT
        assert db.session.get(Payment, data['payment_id']).status == 'pending'

    def test_repeat_returns_same_payment(self, db, member):
        today = date.today().strftime('%Y-%m')
        _, d1 = PaymentService.initiate(member.id, today)
        _, d2 = PaymentService.initiate(member.id, today)
        assert d1['payment_id'] == d2['payment_id']

    def test_rejects_already_completed(self, db, member):
        today = date.today().strftime('%Y-%m')
        db.session.add(Payment(member_id=member.id, amount=99.0, month_year=today,
                               status='completed', transfer_number='TRF-1111-2222-3333'))
        db.session.commit()
        ok, data = PaymentService.initiate(member.id, today)
        assert ok is False
        assert 'error' in data

    def test_rejects_nonexistent_member(self, db):
        ok, data = PaymentService.initiate(9999, '2026-01')
        assert ok is False


class TestConfirm:
    def test_marks_completed_with_timestamp(self, db, member):
        today = date.today().strftime('%Y-%m')
        _, data = PaymentService.initiate(member.id, today)
        ok, msg = PaymentService.confirm(data['payment_id'], member.id)
        assert ok is True
        p = db.session.get(Payment, data['payment_id'])
        assert p.status == 'completed'
        assert p.paid_at is not None

    def test_rejects_wrong_member(self, db, member):
        today = date.today().strftime('%Y-%m')
        _, data = PaymentService.initiate(member.id, today)
        ok, msg = PaymentService.confirm(data['payment_id'], member.id + 999)
        assert ok is False
        assert 'dostępu' in msg

    def test_rejects_nonexistent_payment(self, db, member):
        ok, msg = PaymentService.confirm(9999, member.id)
        assert ok is False

    def test_rejects_double_confirm(self, db, member):
        today = date.today().strftime('%Y-%m')
        _, data = PaymentService.initiate(member.id, today)
        PaymentService.confirm(data['payment_id'], member.id)
        ok, msg = PaymentService.confirm(data['payment_id'], member.id)
        assert ok is False

    def test_total_revenue_counts_completed_only(self, db, member):
        today = date.today().strftime('%Y-%m')
        _, data = PaymentService.initiate(member.id, today)
        assert PaymentService.total_revenue() == 0.0
        PaymentService.confirm(data['payment_id'], member.id)
        assert PaymentService.total_revenue() == 99.0


class TestRecordCompleted:
    def test_creates_completed_payment(self, db, member):
        p = PaymentService.record_completed(member, '2026-06')
        assert p.status == 'completed'
        assert p.paid_at is not None
        assert p.amount == 99.0
        assert p.transfer_number.startswith('TRF-')

    def test_upserts_existing_pending(self, db, member):
        _, data = PaymentService.initiate(member.id, '2026-06')   # pending
        p = PaymentService.record_completed(member, '2026-06')
        assert p.id == data['payment_id']        # ten sam wiersz, nie duplikat
        assert p.status == 'completed'
        assert Payment.query.filter_by(member_id=member.id, month_year='2026-06').count() == 1

    def test_no_duplicate_on_repeat(self, db, member):
        PaymentService.record_completed(member, '2026-06')
        PaymentService.record_completed(member, '2026-06')
        assert Payment.query.filter_by(member_id=member.id, month_year='2026-06').count() == 1
        assert PaymentService.total_revenue() == 99.0
