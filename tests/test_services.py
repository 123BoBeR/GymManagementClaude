"""Testy serwisów MemberService i TrainerService."""

from datetime import date
from models import db, User, Member, Trainer
from services import MemberService, TrainerService


class TestMemberService:

    def test_create_member_success(self, seeded):
        ok, msg = MemberService.create(
            username="nowy.klient",
            password="haslo123",
            first_name="Nowy",
            last_name="Klient",
            phone="500-000-000",
            sub_type="monthly",
            sub_end=date(2027, 6, 30),
        )
        assert ok is True
        assert Member.query.filter_by(first_name="Nowy").first() is not None

    def test_create_member_duplicate_username(self, seeded):
        ok, msg = MemberService.create(
            username="klient1",   # już istnieje
            password="haslo",
            first_name="X", last_name="X",
            phone="", sub_type="monthly", sub_end=None,
        )
        assert ok is False
        assert "istnieje" in msg

    def test_update_member(self, seeded):
        member = seeded["member"]
        ok, msg = MemberService.update(
            member=member,
            first_name="Zmieniony",
            last_name=member.last_name,
            phone="111-222-333",
            sub_type="annual",
            sub_end=date(2027, 12, 31),
        )
        assert ok is True
        assert member.first_name == "Zmieniony"
        assert member.subscription_type == "annual"

    def test_delete_member_removes_user(self, seeded):
        member = seeded["member"]
        user_id = member.user_id
        MemberService.delete(member)
        assert db.session.get(User, user_id) is None

    def test_is_active_valid_subscription(self, seeded):
        assert MemberService.is_active(seeded["member"]) is True

    def test_is_active_no_end_date(self, seeded):
        member = seeded["member"]
        member.subscription_end = None
        db.session.commit()
        assert MemberService.is_active(member) is False


class TestTrainerService:

    def test_create_trainer_success(self, seeded):
        ok, msg = TrainerService.create(
            username="nowy.trener",
            password="trener123",
            first_name="Nowy",
            last_name="Trener",
            specialization="Crossfit",
            hourly_rate=110.0,
        )
        assert ok is True
        assert Trainer.query.filter_by(first_name="Nowy").first() is not None

    def test_create_trainer_duplicate_username(self, seeded):
        ok, msg = TrainerService.create(
            username="trener1",   # już istnieje
            password="x",
            first_name="X", last_name="X",
            specialization="", hourly_rate=0,
        )
        assert ok is False
        assert "istnieje" in msg

    def test_update_trainer(self, seeded):
        trainer = seeded["trainer"]
        ok, _ = TrainerService.update(
            trainer=trainer,
            first_name=trainer.first_name,
            last_name=trainer.last_name,
            specialization="Yoga",
            hourly_rate=90.0,
        )
        assert ok is True
        assert trainer.specialization == "Yoga"
        assert trainer.hourly_rate == 90.0

    def test_delete_trainer_removes_user(self, seeded):
        trainer = seeded["trainer"]
        user_id = trainer.user_id
        TrainerService.delete(trainer)
        assert db.session.get(User, user_id) is None
