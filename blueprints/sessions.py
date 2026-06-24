from datetime import date, timedelta
from extensions import db
from models import ClassSession

DAY_MAP = {
    'Poniedziałek': 0, 'Wtorek': 1, 'Środa': 2, 'Czwartek': 3,
    'Piątek': 4, 'Sobota': 5, 'Niedziela': 6,
}


def _first_occurrence(gym_class):
    """Pierwsze wystąpienie docelowego dnia tygodnia >= start_date."""
    target_weekday = DAY_MAP.get(gym_class.schedule_day, 0)
    start = gym_class.start_date
    return start + timedelta(days=(target_weekday - start.weekday()) % 7)


def generate_sessions(gym_class, weeks=12):
    """Generuje sesje dla zajęć na 'weeks' tygodni do przodu."""
    if not gym_class.start_date:
        return []

    current = _first_occurrence(gym_class)
    end_date = date.today() + timedelta(weeks=weeks)
    # Uwzględnij też przeszłe sesje od start_date
    if current > end_date:
        end_date = current + timedelta(weeks=weeks)

    step = max(gym_class.frequency_weeks or 1, 1)
    sessions = []
    while current <= end_date:
        sessions.append(ClassSession(class_id=gym_class.id, session_date=current))
        current += timedelta(weeks=step)
    return sessions


def ensure_future_sessions(gym_class, horizon_weeks=12):
    """Idempotentnie dogenerowuje brakujące PRZYSZŁE sesje do horyzontu.

    - nie tworzy duplikatów istniejących dat (także odwołanych),
    - nie cofa się w przeszłość,
    - dodaje obiekty do sesji DB, ale NIE commituje (robi to wołający).

    Zwraca liczbę dodanych sesji.
    """
    if gym_class.status != 'approved' or not gym_class.start_date:
        return 0

    existing = {s.session_date for s in gym_class.sessions}
    today = date.today()
    end_date = today + timedelta(weeks=horizon_weeks)
    step = max(gym_class.frequency_weeks or 1, 1)

    current = _first_occurrence(gym_class)
    added = 0
    while current <= end_date:
        if current >= today and current not in existing:
            db.session.add(ClassSession(class_id=gym_class.id, session_date=current))
            existing.add(current)
            added += 1
        current += timedelta(weeks=step)
    return added


def refresh_all_future_sessions(horizon_weeks=12):
    """Dogenerowuje brakujące sesje dla wszystkich zatwierdzonych zajęć."""
    from models import GymClass
    total = sum(ensure_future_sessions(c, horizon_weeks)
                for c in GymClass.query.filter_by(status='approved').all())
    if total:
        db.session.commit()
    return total
