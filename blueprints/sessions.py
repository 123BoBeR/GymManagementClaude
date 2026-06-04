from datetime import date, timedelta
from models import ClassSession

DAY_MAP = {
    'Poniedziałek': 0, 'Wtorek': 1, 'Środa': 2, 'Czwartek': 3,
    'Piątek': 4, 'Sobota': 5, 'Niedziela': 6,
}


def generate_sessions(gym_class, weeks=12):
    """Generuje sesje dla zajęć na 'weeks' tygodni do przodu."""
    if not gym_class.start_date:
        return []

    target_weekday = DAY_MAP.get(gym_class.schedule_day, 0)
    start = gym_class.start_date

    # Pierwsze wystąpienie docelowego dnia tygodnia >= start_date
    days_ahead = (target_weekday - start.weekday()) % 7
    current = start + timedelta(days=days_ahead)

    end_date = date.today() + timedelta(weeks=weeks)
    # Uwzględnij też przeszłe sesje od start_date
    if current > end_date:
        end_date = current + timedelta(weeks=weeks)

    sessions = []
    while current <= end_date:
        sessions.append(ClassSession(class_id=gym_class.id, session_date=current))
        current += timedelta(weeks=gym_class.frequency_weeks)
    return sessions
