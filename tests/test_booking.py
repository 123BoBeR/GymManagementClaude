"""Testy serwisu rezerwacji (BookingService)."""

import pytest
from datetime import date
from models import db, User, Member, GymClass, Booking
from services import BookingService


class TestBookingService:

    def test_book_success(self, seeded):
        member = seeded["member"]
        gym_class = seeded["gym_class"]
        ok, msg = BookingService.book(member.id, gym_class.id)
        assert ok is True
        assert gym_class.name in msg

    def test_book_creates_confirmed_booking(self, seeded):
        member = seeded["member"]
        gym_class = seeded["gym_class"]
        BookingService.book(member.id, gym_class.id)
        booking = Booking.query.filter_by(member_id=member.id,
                                          class_id=gym_class.id).first()
        assert booking is not None
        assert booking.status == "confirmed"

    def test_book_duplicate_rejected(self, seeded):
        member = seeded["member"]
        gym_class = seeded["gym_class"]
        BookingService.book(member.id, gym_class.id)
        ok, msg = BookingService.book(member.id, gym_class.id)
        assert ok is False
        assert "już" in msg

    def test_book_full_class_rejected(self, seeded):
        gym_class = seeded["gym_class"]
        gym_class.max_capacity = 1
        db.session.commit()

        member = seeded["member"]
        BookingService.book(member.id, gym_class.id)

        # drugi klient
        u2 = User(username="klient2", role="client")
        u2.set_password("x")
        db.session.add(u2)
        db.session.flush()
        m2 = Member(user_id=u2.id, first_name="Anna", last_name="X",
                    subscription_type="monthly", subscription_end=date(2027, 1, 1))
        db.session.add(m2)
        db.session.commit()

        ok, msg = BookingService.book(m2.id, gym_class.id)
        assert ok is False
        assert "miejsc" in msg

    def test_book_nonexistent_class_rejected(self, seeded):
        ok, msg = BookingService.book(seeded["member"].id, 9999)
        assert ok is False

    def test_cancel_success(self, seeded):
        member = seeded["member"]
        gym_class = seeded["gym_class"]
        BookingService.book(member.id, gym_class.id)
        booking = Booking.query.filter_by(member_id=member.id).first()

        ok, msg = BookingService.cancel(booking.id, member.id)
        assert ok is True
        assert booking.status == "cancelled"

    def test_cancel_wrong_member_rejected(self, seeded):
        member = seeded["member"]
        gym_class = seeded["gym_class"]
        BookingService.book(member.id, gym_class.id)
        booking = Booking.query.filter_by(member_id=member.id).first()

        ok, msg = BookingService.cancel(booking.id, member.id + 999)
        assert ok is False
        assert "dostępu" in msg

    def test_cancel_already_cancelled_rejected(self, seeded):
        member = seeded["member"]
        gym_class = seeded["gym_class"]
        BookingService.book(member.id, gym_class.id)
        booking = Booking.query.filter_by(member_id=member.id).first()

        BookingService.cancel(booking.id, member.id)
        ok, msg = BookingService.cancel(booking.id, member.id)
        assert ok is False
        assert "już" in msg

    def test_cancel_nonexistent_booking_rejected(self, seeded):
        ok, msg = BookingService.cancel(9999, seeded["member"].id)
        assert ok is False
