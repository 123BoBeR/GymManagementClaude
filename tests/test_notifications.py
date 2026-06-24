"""Testy warstwy powiadomień (B42)."""
import pytest
from models import Notification, WaitlistEntry
from services import NotificationService, BookingService, PaymentService
from tests.conftest import (make_user, make_member, make_trainer, make_class,
                            make_session, make_booking)


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


class TestNotificationService:
    def test_push_and_unread_count(self, db):
        u = make_user(db, 'k', 'pass', 'client'); make_member(db, u); db.session.commit()
        NotificationService.push(u.id, 'Test')
        db.session.commit()
        assert NotificationService.unread_count(u.id) == 1

    def test_mark_all_read(self, db):
        u = make_user(db, 'k', 'pass', 'client'); make_member(db, u); db.session.commit()
        NotificationService.push(u.id, 'A'); NotificationService.push(u.id, 'B')
        db.session.commit()
        NotificationService.mark_all_read(u.id)
        assert NotificationService.unread_count(u.id) == 0

    def test_notify_expiring_creates_and_dedups(self, db):
        u = make_user(db, 'k', 'pass', 'client'); m = make_member(db, u); db.session.commit()
        NotificationService.notify_expiring(m, 3)
        NotificationService.notify_expiring(m, 3)        # dedup: bez drugiego wpisu
        assert Notification.query.filter_by(user_id=u.id).count() == 1

    def test_notify_expiring_skips_when_far(self, db):
        u = make_user(db, 'k', 'pass', 'client'); m = make_member(db, u); db.session.commit()
        NotificationService.notify_expiring(m, 30)
        assert Notification.query.filter_by(user_id=u.id).count() == 0


class TestNotificationHooks:
    def test_waitlist_promotion_notifies(self, db):
        hu = make_user(db, 'holder', 'pass', 'client'); holder = make_member(db, hu)
        wu = make_user(db, 'waiter', 'pass', 'client'); waiter = make_member(db, wu)
        tu = make_user(db, 't', 'pass', 'trainer'); t = make_trainer(db, tu)
        c = make_class(db, t, capacity=1)
        s = make_session(db, c, delta_days=3)
        b = make_booking(db, holder, s)
        db.session.add(WaitlistEntry(member_id=waiter.id, session_id=s.id))
        db.session.commit()
        BookingService.cancel(holder.id, b.id)
        assert NotificationService.unread_count(wu.id) >= 1

    def test_payment_confirm_notifies(self, db):
        u = make_user(db, 'k', 'pass', 'client'); m = make_member(db, u); db.session.commit()
        _, data = PaymentService.initiate(m.id, '2026-07')
        PaymentService.confirm(data['payment_id'], m.id)
        assert NotificationService.unread_count(u.id) >= 1


class TestNotificationRoutes:
    def test_page_and_mark_read(self, client, db):
        u = make_user(db, 'klient', 'pass', 'client'); make_member(db, u); db.session.commit()
        NotificationService.push(u.id, 'Witaj w GymApp!'); db.session.commit()
        login(client, 'klient', 'pass')
        resp = client.get('/notifications')
        assert 'Witaj w GymApp!' in resp.data.decode()
        client.post('/notifications/read')
        assert NotificationService.unread_count(u.id) == 0
