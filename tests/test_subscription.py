"""Testy wzorców Strategy + Factory dla karnetów (model miesięczny)."""
import pytest
from datetime import date
from services import (
    SubscriptionFactory, SubscriptionStrategy,
    MonthlySubscription, AnnualSubscription, DayPassSubscription,
)

TODAY = date(2026, 6, 24)   # czerwiec ma 30 dni


class TestSubscriptionStrategy:
    def test_labels_and_prices(self):
        assert (MonthlySubscription().label(), MonthlySubscription().price()) == ('Miesięczny', 99.0)
        assert (AnnualSubscription().label(), AnnualSubscription().price()) == ('Roczny', 799.0)
        assert (DayPassSubscription().label(), DayPassSubscription().price()) == ('Dzienny', 29.0)

    def test_monthly_new_covers_current_month(self):
        # brak karnetu → aktywny do końca bieżącego miesiąca
        assert MonthlySubscription().extend(None, TODAY) == date(2026, 6, 30)

    def test_monthly_active_stacks_to_next_month(self):
        # karnet do czerwca + miesiąc = do końca lipca
        assert MonthlySubscription().extend(date(2026, 6, 30), TODAY) == date(2026, 7, 31)

    def test_monthly_expired_resets_to_current_month(self):
        # wygasły (kwiecień) → znów aktywny do końca bieżącego miesiąca
        assert MonthlySubscription().extend(date(2026, 4, 30), TODAY) == date(2026, 6, 30)

    def test_annual_new_covers_twelve_months(self):
        assert AnnualSubscription().extend(None, TODAY) == date(2027, 5, 31)

    def test_annual_active_stacks_twelve_months(self):
        assert AnnualSubscription().extend(date(2026, 6, 30), TODAY) == date(2027, 6, 30)

    def test_day_pass_valid_today_only(self):
        assert DayPassSubscription().extend(None, TODAY) == TODAY
        assert DayPassSubscription().extend(date(2026, 1, 1), TODAY) == TODAY

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
