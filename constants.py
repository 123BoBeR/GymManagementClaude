"""Wspólne stałe domenowe (bez duplikowania po blueprintach)."""

# Kolejność dni tygodnia — do sortowania harmonogramu i mapowania na numer dnia.
DAY_ORDER = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek',
             'Piątek', 'Sobota', 'Niedziela']

# Mapowanie nazwy dnia -> numer dnia tygodnia (0 = poniedziałek).
DAY_MAP = {name: i for i, name in enumerate(DAY_ORDER)}
