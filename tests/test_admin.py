"""Testy operacji administracyjnych: CRUD trenerów/klientów, eksport płatności."""
import pytest
from datetime import date, timedelta
from models import User, Trainer, Member, Payment, ContactOption, WaitlistEntry
from services import UserService, SubscriptionFactory
from tests.conftest import make_user, make_member, make_trainer, make_class, make_session


def login_admin(client, db):
    u = make_user(db, 'admin', 'admin123', 'admin')
    db.session.commit()
    client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    return u


class TestTrainerCrud:
    def test_create_trainer_autogenerates_username(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/trainers/new', data={
            'first_name': 'Jan', 'last_name': 'Nowak',
            'password': 'trener123', 'specialization': 'Boks', 'hourly_rate': '150',
        }, follow_redirects=True)
        assert 'dodany' in resp.data.decode()
        t = User.query.filter_by(username='t.jan.nowak').first()
        assert t is not None and t.role == 'trainer'
        assert t.trainer.specialization == 'Boks'

    def test_create_rejects_short_password(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/trainers/new', data={
            'first_name': 'Anna', 'last_name': 'Krotka', 'password': '123',
        }, follow_redirects=True)
        assert '6 znaków' in resp.data.decode()
        assert User.query.filter_by(username='t.anna.krotka').first() is None

    def test_delete_trainer_without_classes(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'dousuniecia', 'pass123', 'trainer')
        t = make_trainer(db, u)
        db.session.commit()
        tid = t.id
        resp = client.post(f'/admin/trainers/{tid}/delete', follow_redirects=True)
        assert 'usunięty' in resp.data.decode()
        assert db.session.get(Trainer, tid) is None
        assert User.query.filter_by(username='dousuniecia').first() is None

    def test_delete_trainer_with_classes_blocked(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'zajety2', 'pass123', 'trainer')
        t = make_trainer(db, u)
        make_class(db, t, status='approved')
        db.session.commit()
        tid = t.id
        resp = client.post(f'/admin/trainers/{tid}/delete', follow_redirects=True)
        assert 'Nie można usunąć' in resp.data.decode()
        assert db.session.get(Trainer, tid) is not None


class TestUsernameGeneration:
    def test_client_username_basic(self, db):
        assert UserService.generate_client_username('Jan', 'Kowalski') == 'j.kowalski'

    def test_client_username_strips_polish_chars(self, db):
        assert UserService.generate_client_username('Łukasz', 'Wójcik') == 'l.wojcik'

    def test_client_username_collision_takes_more_letters(self, db):
        u = make_user(db, 'j.kowalski', 'pass123', 'client')
        make_member(db, u)
        db.session.commit()
        assert UserService.generate_client_username('Jan', 'Kowalski') == 'ja.kowalski'

    def test_client_username_double_collision(self, db):
        for uname in ('j.kowalski', 'ja.kowalski'):
            u = make_user(db, uname, 'pass123', 'client')
            make_member(db, u)
        db.session.commit()
        assert UserService.generate_client_username('Jan', 'Kowalski') == 'jan.kowalski'

    def test_trainer_username_format(self, db):
        assert UserService.generate_trainer_username('Jan', 'Kowalski') == 't.jan.kowalski'

    def test_trainer_username_collision_appends_number(self, db):
        u = make_user(db, 't.jan.kowalski', 'pass123', 'trainer')
        make_trainer(db, u)
        db.session.commit()
        assert UserService.generate_trainer_username('Jan', 'Kowalski') == 't.jan.kowalski2'


class TestClientCreation:
    def test_create_autogenerates_username_and_expiry(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/members/new', data={
            'first_name': 'Ewa', 'last_name': 'Nowak', 'password': 'klient123',
            'phone': '500', 'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert 'Login: e.nowak' in resp.data.decode()
        m = User.query.filter_by(username='e.nowak').first().member
        # nowy karnet miesięczny = aktywny do końca bieżącego miesiąca
        assert m.subscription_end == SubscriptionFactory.create('monthly').extend(None)

    def test_create_annual_expiry(self, client, db):
        login_admin(client, db)
        client.post('/admin/members/new', data={
            'first_name': 'Adam', 'last_name': 'Roczny', 'password': 'klient123',
            'subscription_type': 'annual',
        }, follow_redirects=True)
        m = User.query.filter_by(username='a.roczny').first().member
        assert m.subscription_end == SubscriptionFactory.create('annual').extend(None)

    def test_create_rejects_short_password(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/members/new', data={
            'first_name': 'X', 'last_name': 'Y', 'password': '123',
            'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert '6 znaków' in resp.data.decode()

    def test_edit_type_change_recomputes_expiry(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'k.test', 'pass123', 'client')
        m = make_member(db, u)   # monthly
        m.subscription_end = date(2020, 1, 1)
        db.session.commit()
        mid = m.id
        client.post(f'/admin/members/{mid}/edit', data={
            'first_name': 'K', 'last_name': 'Test', 'phone': '',
            'subscription_type': 'annual',
        }, follow_redirects=True)
        assert db.session.get(Member, mid).subscription_end == SubscriptionFactory.create('annual').extend(None)

    def test_renew_extends_to_next_period(self, client, db):
        import calendar
        login_admin(client, db)
        u = make_user(db, 'k.renew', 'pass123', 'client')
        m = make_member(db, u)
        today = date.today()
        # aktywny do końca bieżącego miesiąca (realny stan = koniec okresu)
        m.subscription_end = SubscriptionFactory.create('monthly').extend(None)
        db.session.commit()
        mid = m.id
        client.post(f'/admin/members/{mid}/renew', data={
            'subscription_type': 'monthly',
        }, follow_redirects=True)
        # przedłużono o jeden okres → koniec następnego miesiąca
        ny, nm = (today.year + today.month // 12), (today.month % 12 + 1)
        expected = date(ny, nm, calendar.monthrange(ny, nm)[1])
        assert db.session.get(Member, mid).subscription_end == expected

    def test_renew_records_payment(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'k.pay', 'pass123', 'client')
        m = make_member(db, u)
        db.session.commit()
        mid = m.id
        client.post(f'/admin/members/{mid}/renew', data={
            'subscription_type': 'monthly',
        }, follow_redirects=True)
        assert Payment.query.filter_by(member_id=mid, status='completed').count() == 1


class TestContact:
    def test_admin_can_add_and_delete(self, client, db):
        login_admin(client, db)
        resp = client.post('/admin/contact/new', data={
            'label': 'Recepcja', 'value': '+48 500', 'icon': 'telephone',
        }, follow_redirects=True)
        assert 'dodana' in resp.data.decode()
        opt = ContactOption.query.filter_by(label='Recepcja').first()
        assert opt is not None
        resp = client.post(f'/admin/contact/{opt.id}/delete', follow_redirects=True)
        assert 'usunięta' in resp.data.decode()
        assert ContactOption.query.count() == 0

    def test_add_requires_label_and_value(self, client, db):
        login_admin(client, db)
        client.post('/admin/contact/new', data={'label': '', 'value': ''},
                    follow_redirects=True)
        assert ContactOption.query.count() == 0

    def test_client_sees_contact_without_admin_controls(self, client, db):
        cu = make_user(db, 'klient', 'pass123', 'client')
        make_member(db, cu)
        db.session.add(ContactOption(label='Email', value='a@b.pl', icon='envelope'))
        db.session.commit()
        client.post('/login', data={'username': 'klient', 'password': 'pass123'})
        resp = client.get('/contact')
        body = resp.data.decode()
        assert resp.status_code == 200
        assert 'a@b.pl' in body
        assert 'Dodaj opcję kontaktu' not in body

    def test_client_cannot_add_contact(self, client, db):
        cu = make_user(db, 'klient', 'pass123', 'client')
        make_member(db, cu)
        db.session.commit()
        client.post('/login', data={'username': 'klient', 'password': 'pass123'})
        client.post('/admin/contact/new', data={'label': 'X', 'value': 'Y'},
                    follow_redirects=True)
        assert ContactOption.query.count() == 0


class TestMemberDeleteCascade:
    def test_delete_member_removes_waitlist_and_payments(self, client, db):
        login_admin(client, db)
        cu = make_user(db, 'k.del', 'pass123', 'client')
        m = make_member(db, cu)
        tu = make_user(db, 't.del', 'pass123', 'trainer')
        t = make_trainer(db, tu)
        c = make_class(db, t)
        s = make_session(db, c, delta_days=3)
        db.session.add(WaitlistEntry(member_id=m.id, session_id=s.id))
        db.session.add(Payment(member_id=m.id, amount=99.0, month_year='2026-06',
                               status='completed', transfer_number='TRF-0000-0000-0000'))
        db.session.commit()
        mid = m.id
        resp = client.post(f'/admin/members/{mid}/delete', follow_redirects=True)
        assert 'usunięty' in resp.data.decode()
        assert db.session.get(Member, mid) is None
        assert WaitlistEntry.query.filter_by(member_id=mid).count() == 0
        assert Payment.query.filter_by(member_id=mid).count() == 0

    def test_delete_class_with_waitlist_ok(self, client, db):
        login_admin(client, db)
        cu = make_user(db, 'k.w', 'pass123', 'client')
        m = make_member(db, cu)
        tu = make_user(db, 't.w', 'pass123', 'trainer')
        t = make_trainer(db, tu)
        c = make_class(db, t)
        s = make_session(db, c, delta_days=3)
        db.session.add(WaitlistEntry(member_id=m.id, session_id=s.id))
        db.session.commit()
        cid = c.id
        resp = client.post(f'/admin/classes/{cid}/delete', follow_redirects=True)
        assert 'usunięte' in resp.data.decode()
        assert WaitlistEntry.query.count() == 0


class TestPaymentsExport:
    def test_export_returns_csv(self, client, db):
        login_admin(client, db)
        cu = make_user(db, 'klient', 'pass123', 'client')
        m = make_member(db, cu)
        db.session.add(Payment(member_id=m.id, amount=99.0, month_year='2026-05',
                               status='completed', transfer_number='TRF-1234-5678-9012'))
        db.session.commit()
        resp = client.get('/admin/payments/export')
        assert resp.status_code == 200
        assert 'text/csv' in resp.headers['Content-Type']
        body = resp.data.decode('utf-8-sig')
        assert 'Numer przelewu' in body
        assert 'TRF-1234-5678-9012' in body


class TestPayroll:
    def test_payroll_computes_cost(self, db):
        from services import trainer_payroll
        u = make_user(db, 't.pay', 'pass123', 'trainer')
        t = make_trainer(db, u)                        # hourly_rate=100
        c = make_class(db, t, status='approved')       # duration=60 min
        make_session(db, c, delta_days=-2)
        make_session(db, c, delta_days=-1)
        make_session(db, c, delta_days=3)              # przyszła → nieliczona
        db.session.commit()
        row = next(r for r in trainer_payroll() if r['trainer'].id == t.id)
        assert row['sessions'] == 2
        assert row['hours'] == 2.0                     # 2 sesje × 60 min
        assert row['cost'] == 200.0                    # 2 h × 100 zł

    def test_payroll_page_renders(self, client, db):
        login_admin(client, db)
        u = make_user(db, 't.pay2', 'pass123', 'trainer'); make_trainer(db, u)
        db.session.commit()
        resp = client.get('/admin/payroll')
        assert resp.status_code == 200
        assert 'Wynagrodzenia' in resp.data.decode()


class TestPagination:
    def test_payments_split_across_pages(self, client, db):
        login_admin(client, db)
        u = make_user(db, 'k.pg', 'pass123', 'client'); m = make_member(db, u)
        for i in range(18):                                  # 18 płatności, unikalne month_year
            year, month = 2024 + i // 12, i % 12 + 1
            db.session.add(Payment(member_id=m.id, amount=99.0,
                                   month_year=f'{year:04d}-{month:02d}', status='completed',
                                   transfer_number=f'TRF-{i:04d}-0000-0000'))
        db.session.commit()
        page1 = client.get('/admin/payments').data.decode()
        page2 = client.get('/admin/payments?page=2').data.decode()
        assert page1.count('TRF-') == 15                     # per_page=15
        assert page2.count('TRF-') == 3
