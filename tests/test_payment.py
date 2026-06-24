"""Testy PaymentService (services.py)."""
import pytest
import calendar
from datetime import date, datetime
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


class TestPayablePeriods:
    def test_returns_three_forward_periods(self, db, member):
        periods = PaymentService.payable_periods(member, count=3)
        assert len(periods) == 3
        assert periods[0]['key'] == date.today().strftime('%Y-%m')   # bieżący
        keys = [p['key'] for p in periods]
        assert keys == sorted(keys)                                  # rosnąco do przodu

    def test_unpaid_by_default(self, db, member):
        periods = PaymentService.payable_periods(member)
        assert all(p['status'] == 'unpaid' for p in periods)
        assert periods[0]['payment_id'] is None

    def test_full_price_when_joined_first_of_month(self, db, member):
        assert PaymentService.payable_periods(member)[0]['amount'] == 99.0

    def test_proration_for_mid_month_join(self, db):
        u = make_user(db, 'k.pro', 'pass', 'client')
        m = make_member(db, u)
        today = date.today()
        dim = calendar.monthrange(today.year, today.month)[1]
        join_day = min(dim, 20)
        m.joined_at = datetime(today.year, today.month, join_day)
        db.session.commit()
        remaining = dim - join_day + 1
        expected = round(99.0 * remaining / dim, 2)
        assert PaymentService.payable_periods(m)[0]['amount'] == expected
        assert expected < 99.0

    def test_annual_shows_full_price_year_periods(self, db):
        u = make_user(db, 'k.ann', 'pass', 'client')
        m = make_member(db, u)
        m.subscription_type = 'annual'
        db.session.commit()
        periods = PaymentService.payable_periods(m, count=3)
        assert len(periods) == 3
        assert all(p['amount'] == 799.0 for p in periods)           # pełna cena, bez proporcji
        assert len({int(p['key'][5:7]) for p in periods}) == 1       # ten sam miesiąc co rok

    def test_daypass_has_no_period_list(self, db):
        u = make_user(db, 'k.day', 'pass', 'client')
        m = make_member(db, u)
        m.subscription_type = 'day_pass'
        db.session.commit()
        assert PaymentService.payable_periods(m) == []


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


class TestPaymentsPage:
    def test_renders_periods_for_monthly(self, client, db):
        u = make_user(db, 'klient', 'pass', 'client'); make_member(db, u); db.session.commit()
        client.post('/login', data={'username': 'klient', 'password': 'pass'})
        resp = client.get('/client/payments')
        assert resp.status_code == 200
        assert 'Okresy do opłacenia' in resp.data.decode()

    def test_renders_daypass_buy_button(self, client, db):
        u = make_user(db, 'kd', 'pass', 'client'); m = make_member(db, u)
        m.subscription_type = 'day_pass'; db.session.commit()
        client.post('/login', data={'username': 'kd', 'password': 'pass'})
        resp = client.get('/client/payments')
        assert resp.status_code == 200
        assert 'wejściówk' in resp.data.decode().lower()


class TestSettlePeriod:
    def test_creates_completed_payment(self, db, member):
        p = PaymentService.settle_period(member, '2026-09', 99.0)
        assert p.status == 'completed'
        assert p.paid_at is not None
        assert p.amount == 99.0
        assert p.transfer_number.startswith('TRF-')

    def test_extends_subscription_to_period_end(self, db, member):
        member.subscription_end = date(2026, 1, 31)
        db.session.commit()
        PaymentService.settle_period(member, '2026-09', 99.0)
        assert member.subscription_end == date(2026, 9, 30)   # koniec opłaconego okresu

    def test_upserts_existing_pending(self, db, member):
        _, data = PaymentService.initiate(member.id, '2026-09')   # pending
        p = PaymentService.settle_period(member, '2026-09')
        assert p.id == data['payment_id']        # ten sam wiersz, nie duplikat
        assert p.status == 'completed'
        assert Payment.query.filter_by(member_id=member.id, month_year='2026-09').count() == 1

    def test_no_duplicate_on_repeat(self, db, member):
        PaymentService.settle_period(member, '2026-09', 99.0)
        PaymentService.settle_period(member, '2026-09', 99.0)
        assert Payment.query.filter_by(member_id=member.id, month_year='2026-09').count() == 1

    def test_duplicate_month_rejected_by_constraint(self, db, member):
        from sqlalchemy.exc import IntegrityError
        db.session.add(Payment(member_id=member.id, amount=99.0, month_year='2026-07',
                               status='completed', transfer_number='TRF-1111-1111-1111'))
        db.session.commit()
        db.session.add(Payment(member_id=member.id, amount=99.0, month_year='2026-07',
                               status='pending', transfer_number='TRF-2222-2222-2222'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
