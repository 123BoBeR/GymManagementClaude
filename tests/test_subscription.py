"""
Testy jednostkowe wzorców Strategy i Factory dla karnetów.
Nie wymagają bazy danych — testują czystą logikę OOP.
"""

import pytest
from datetime import date, timedelta
from services import (SubscriptionFactory, SubscriptionStrategy,
                      MonthlySubscription, AnnualSubscription, DayPassSubscription)


# ── Factory ───────────────────────────────────────────────────────────────────

class TestSubscriptionFactory:

    def test_creates_monthly(self):
        s = SubscriptionFactory.create("monthly")
        assert isinstance(s, MonthlySubscription)

    def test_creates_annual(self):
        s = SubscriptionFactory.create("annual")
        assert isinstance(s, AnnualSubscription)

    def test_creates_day_pass(self):
        s = SubscriptionFactory.create("day_pass")
        assert isinstance(s, DayPassSubscription)

    def test_unknown_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Nieznany typ"):
            SubscriptionFactory.create("vip_gold")

    def test_available_types_contains_all(self):
        types = SubscriptionFactory.available_types()
        assert "monthly" in types
        assert "annual" in types
        assert "day_pass" in types

    def test_label_for_monthly(self):
        assert SubscriptionFactory.label_for("monthly") == "Miesięczny"

    def test_label_for_unknown_returns_key(self):
        assert SubscriptionFactory.label_for("xyz") == "xyz"


# ── Strategy — implementacje ──────────────────────────────────────────────────

class TestMonthlySubscription:

    def test_label(self):
        assert MonthlySubscription().label() == "Miesięczny"

    def test_duration_days(self):
        assert MonthlySubscription().duration_days() == 30

    def test_end_date(self):
        start = date(2026, 6, 1)
        assert MonthlySubscription().end_date(start) == date(2026, 7, 1)


class TestAnnualSubscription:

    def test_label(self):
        assert AnnualSubscription().label() == "Roczny"

    def test_duration_days(self):
        assert AnnualSubscription().duration_days() == 365

    def test_end_date(self):
        start = date(2026, 1, 1)
        assert AnnualSubscription().end_date(start) == date(2027, 1, 1)


class TestDayPassSubscription:

    def test_label(self):
        assert DayPassSubscription().label() == "Karnet dzienny"

    def test_duration_days(self):
        assert DayPassSubscription().duration_days() == 1

    def test_end_date(self):
        start = date(2026, 6, 10)
        assert DayPassSubscription().end_date(start) == date(2026, 6, 11)


# ── Strategy — wspólna logika z SubscriptionStrategy ─────────────────────────

class TestSubscriptionStrategyMethods:

    def _make_member(self, sub_end):
        """Pomocniczy mock obiektu Member."""
        class FakeMember:
            subscription_type = "monthly"
            subscription_end = sub_end
        return FakeMember()

    def test_is_active_when_valid(self):
        member = self._make_member(date.today() + timedelta(days=10))
        assert MonthlySubscription().is_active(member) is True

    def test_is_not_active_when_expired(self):
        member = self._make_member(date.today() - timedelta(days=1))
        assert MonthlySubscription().is_active(member) is False

    def test_is_not_active_when_no_end_date(self):
        member = self._make_member(None)
        assert MonthlySubscription().is_active(member) is False

    def test_days_remaining_positive(self):
        member = self._make_member(date.today() + timedelta(days=15))
        assert MonthlySubscription().days_remaining(member) == 15

    def test_days_remaining_none_when_no_date(self):
        member = self._make_member(None)
        assert MonthlySubscription().days_remaining(member) is None

    def test_all_strategies_implement_interface(self):
        for sub_type in SubscriptionFactory.available_types():
            s = SubscriptionFactory.create(sub_type)
            assert isinstance(s, SubscriptionStrategy)
            assert callable(s.label)
            assert callable(s.end_date)
