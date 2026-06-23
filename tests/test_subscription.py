"""Testy wzorców Strategy + Factory dla karnetów (services.py)."""
import pytest
from datetime import date, timedelta
from services import (
    SubscriptionFactory, SubscriptionStrategy,
    MonthlySubscription, AnnualSubscription, DayPassSubscription,
)


class TestSubscriptionStrategy:
    def test_monthly_properties(self):
        s = MonthlySubscription()
        assert s.code == 'monthly'
        assert s.label() == 'Miesięczny'
        assert s.price() == 99.0
        assert s.duration_days() == 30

    def test_annual_properties(self):
        s = AnnualSubscription()
        assert s.label() == 'Roczny'
        assert s.price() == 799.0
        assert s.duration_days() == 365

    def test_day_pass_properties(self):
        s = DayPassSubscription()
        assert s.label() == 'Dzienny'
        assert s.price() == 29.0
        assert s.duration_days() == 1

    def test_end_date_uses_duration(self):
        s = MonthlySubscription()
        start = date(2026, 1, 1)
        assert s.end_date(start) == start + timedelta(days=30)

    def test_end_date_defaults_to_today(self):
        s = DayPassSubscription()
        assert s.end_date() == date.today() + timedelta(days=1)

    def test_all_strategies_are_subclasses(self):
        for cls in (MonthlySubscription, AnnualSubscription, DayPassSubscription):
            assert issubclass(cls, SubscriptionStrategy)


class TestSubscriptionFactory:
    def test_create_monthly(self):
        assert isinstance(SubscriptionFactory.create('monthly'), MonthlySubscription)

    def test_create_annual(self):
        assert isinstance(SubscriptionFactory.create('annual'), AnnualSubscription)

    def test_create_day_pass(self):
        assert isinstance(SubscriptionFactory.create('day_pass'), DayPassSubscription)

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError):
            SubscriptionFactory.create('platinum')

    def test_all_types_returns_three(self):
        types = SubscriptionFactory.all_types()
        assert len(types) == 3
        assert {t.code for t in types} == {'monthly', 'annual', 'day_pass'}
