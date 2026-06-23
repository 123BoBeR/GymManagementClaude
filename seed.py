from app import create_app
from extensions import db
from models import User, Member, Trainer, GymClass, ClassSession, Booking, Equipment, Payment
from services import PaymentService, SubscriptionFactory
from blueprints.sessions import generate_sessions
from datetime import date, datetime

app = create_app()


def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # ── Admin ────────────────────────────────────────────────────────────
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)

        # ── Trenerzy ─────────────────────────────────────────────────────────
        trainer_rows = [
            ('jan.kowalski',      'Jan',    'Kowalski',    'Trening siłowy i kulturystyka',       120.0),
            ('anna.nowak',        'Anna',   'Nowak',       'Yoga i pilates',                      100.0),
            ('piotr.wisniewski',  'Piotr',  'Wiśniewski',  'CrossFit i trening funkcjonalny',     130.0),
            ('marta.wojcik',      'Marta',  'Wójcik',      'Cardio i aerobik',                    90.0),
        ]
        trainers = []
        for username, first, last, spec, rate in trainer_rows:
            u = User(username=username, role='trainer')
            u.set_password('trener123')
            db.session.add(u)
            db.session.flush()
            t = Trainer(user_id=u.id, first_name=first, last_name=last,
                        specialization=spec, hourly_rate=rate)
            db.session.add(t)
            db.session.flush()
            trainers.append(t)

        jan, anna, piotr, marta = trainers

        # ── Zajęcia (zatwierdzone) ────────────────────────────────────────────
        # start_date: pierwszy poniedziałek / wtorek itd. od 2026-06-01
        classes_rows = [
            # (trainer, name, desc, capacity, day, time, duration, freq, start)
            (jan.id,   'Trening Siłowy Podstawowy',   'Podstawy treningu z wolnymi ciężarami.',          15, 'Poniedziałek', '10:00', 60,  1, date(2026, 6, 1)),
            (jan.id,   'Trening Siłowy Zaawansowany', 'Zaawansowane techniki i periodyzacja.',           10, 'Środa',        '11:00', 90,  1, date(2026, 6, 1)),
            (anna.id,  'Yoga dla Początkujących',     'Podstawowe asany, oddech i relaksacja.',          20, 'Wtorek',       '09:00', 60,  1, date(2026, 6, 1)),
            (anna.id,  'Pilates',                     'Wzmacnianie core i poprawa postawy.',             15, 'Czwartek',     '10:00', 60,  1, date(2026, 6, 1)),
            (piotr.id, 'CrossFit',                    'Intensywny trening łączący siłę i wydolność.',    12, 'Środa',        '18:00', 60,  1, date(2026, 6, 1)),
            (piotr.id, 'Trening Obwodowy',            'Trening całego ciała w formie stacji.',           16, 'Piątek',       '16:00', 45,  2, date(2026, 6, 1)),
            (marta.id, 'Cardio Blast',                'Wysokointensywny trening spalający kalorie.',     25, 'Piątek',       '17:00', 45,  1, date(2026, 6, 1)),
            (marta.id, 'Aerobik',                     'Klasyczny aerobik przy muzyce.',                 20, 'Sobota',       '10:00', 60,  1, date(2026, 6, 1)),
        ]
        classes = []
        for row in classes_rows:
            c = GymClass(
                trainer_id=row[0], name=row[1], description=row[2],
                max_capacity=row[3], schedule_day=row[4], schedule_time=row[5],
                duration_minutes=row[6], frequency_weeks=row[7], start_date=row[8],
                status='approved',
            )
            db.session.add(c)
            db.session.flush()
            classes.append(c)

        sil_podst, sil_zaaw, yoga, pilates, crossfit, obwodowy, cardio, aerobik = classes

        # ── Przykładowa oczekująca propozycja trenera ─────────────────────────
        pending = GymClass(
            trainer_id=jan.id,
            name='Trening Mobilności',
            description='Rozciąganie i poprawa zakresu ruchu.',
            max_capacity=12,
            schedule_day='Wtorek',
            schedule_time='17:00',
            duration_minutes=60,
            frequency_weeks=1,
            start_date=date(2026, 7, 1),
            status='pending',
        )
        db.session.add(pending)

        # Przykładowo odrzucona propozycja
        rejected = GymClass(
            trainer_id=anna.id,
            name='Zaawansowana Yoga',
            description='Dla osób z min. rocznym doświadczeniem.',
            max_capacity=8,
            schedule_day='Piątek',
            schedule_time='08:00',
            duration_minutes=90,
            frequency_weeks=2,
            start_date=date(2026, 7, 4),
            status='rejected',
            rejection_note='Zbyt mała przewidywana frekwencja o tej godzinie. Proponuję przesunąć na 18:00.',
        )
        db.session.add(rejected)
        db.session.flush()

        # ── Generuj sesje dla zatwierdzonych zajęć ────────────────────────────
        for c in classes:
            for s in generate_sessions(c, weeks=12):
                db.session.add(s)
        db.session.flush()

        # ── Klienci ───────────────────────────────────────────────────────────
        members_rows = [
            ('tomasz.krol',        'Tomasz',   'Król',       '500-100-200', 'monthly',  date(2026, 6, 30)),
            ('ewa.dabrowska',      'Ewa',      'Dąbrowska',  '500-200-300', 'annual',   date(2026, 12, 31)),
            ('michal.kowalczyk',   'Michał',   'Kowalczyk',  '500-300-400', 'monthly',  date(2026, 5, 31)),
            ('karolina.szymanska', 'Karolina', 'Szymańska',  '500-400-500', 'day_pass', date(2026, 5, 20)),
        ]
        members = []
        for username, first, last, phone, sub_type, sub_end in members_rows:
            u = User(username=username, role='client')
            u.set_password('klient123')
            db.session.add(u)
            db.session.flush()
            m = Member(user_id=u.id, first_name=first, last_name=last, phone=phone,
                       subscription_type=sub_type, subscription_end=sub_end,
                       joined_at=datetime(2026, 1, 15))
            db.session.add(m)
            db.session.flush()
            members.append(m)

        tomasz, ewa, michal, karolina = members

        # ── Rezerwacje (na pierwszą dostępną sesję każdych zajęć) ─────────────
        def first_session(gym_class):
            return ClassSession.query.filter_by(class_id=gym_class.id).order_by(ClassSession.session_date).first()

        bookings_rows = [
            (tomasz.id,   sil_podst, 'confirmed'),
            (tomasz.id,   crossfit,  'confirmed'),
            (tomasz.id,   aerobik,   'cancelled'),
            (ewa.id,      yoga,      'confirmed'),
            (ewa.id,      pilates,   'confirmed'),
            (ewa.id,      cardio,    'confirmed'),
            (michal.id,   crossfit,  'confirmed'),
            (michal.id,   sil_podst, 'confirmed'),
            (michal.id,   obwodowy,  'confirmed'),
            (karolina.id, yoga,      'confirmed'),
            (karolina.id, aerobik,   'confirmed'),
        ]
        for member_id, gym_class, status in bookings_rows:
            s = first_session(gym_class)
            if s:
                db.session.add(Booking(
                    member_id=member_id,
                    session_id=s.id,
                    status=status,
                    booked_at=datetime(2026, 5, 10, 14, 30),
                ))

        # ── Sprzęt ────────────────────────────────────────────────────────────
        equipment_rows = [
            ('Sztanga olimpijska 20kg',       'Siłownia',     'working',     date(2023, 1, 15)),
            ('Bieżnia ProForm 9000 (szt. 1)', 'Cardio',       'working',     date(2022, 6, 1)),
            ('Bieżnia ProForm 9000 (szt. 2)', 'Cardio',       'working',     date(2022, 6, 1)),
            ('Orbitrek Horizon EX-59',        'Cardio',       'maintenance', date(2021, 3, 20)),
            ('Maty do jogi (x10)',            'Yoga/Pilates', 'working',     date(2023, 9, 1)),
            ('Komplet hantli 2-40 kg',        'Siłownia',     'working',     date(2022, 1, 10)),
            ('Rower stacjonarny LifeFitness', 'Cardio',       'broken',      date(2020, 11, 5)),
            ('Klatka na wolne ciężary',       'Siłownia',     'working',     date(2023, 5, 1)),
            ('Zestaw TRX',                    'CrossFit',     'working',     date(2023, 7, 15)),
            ('Skakanki (x20)',                'CrossFit',     'working',     date(2024, 1, 10)),
        ]
        for name, category, status, purchase_date in equipment_rows:
            db.session.add(Equipment(name=name, category=category,
                                     status=status, purchase_date=purchase_date))

        # ── Płatności (kilka opłaconych + jedna oczekująca) ──────────────────
        payments_rows = [
            # (member, month_year, status)
            (tomasz,   '2026-04', 'completed'),
            (tomasz,   '2026-05', 'completed'),
            (ewa,      '2026-04', 'completed'),
            (ewa,      '2026-05', 'completed'),
            (ewa,      '2026-06', 'completed'),
            (michal,   '2026-05', 'completed'),
            (michal,   '2026-06', 'pending'),
            (karolina, '2026-05', 'completed'),
        ]
        for member, my, status in payments_rows:
            amount = SubscriptionFactory.create(member.subscription_type).price()
            paid_at = datetime(int(my[:4]), int(my[5:7]), 10, 12, 0) if status == 'completed' else None
            db.session.add(Payment(
                member_id=member.id, amount=amount, month_year=my, status=status,
                transfer_number=PaymentService.generate_transfer_number(),
                paid_at=paid_at,
            ))

        db.session.commit()

        print('Baza danych wypelniona!\n')
        print('Dane logowania:')
        print('  Admin     admin            / admin123')
        print('  Trener    jan.kowalski     / trener123')
        print('  Trener    anna.nowak       / trener123')
        print('  Trener    piotr.wisniewski / trener123')
        print('  Trener    marta.wojcik     / trener123')
        print('  Klient    tomasz.krol      / klient123')
        print('  Klient    ewa.dabrowska    / klient123')
        print('  Klient    michal.kowalczyk / klient123')
        print('  Klient    karolina.szymanska / klient123')


if __name__ == '__main__':
    seed()
