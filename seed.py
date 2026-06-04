from app import create_app
from extensions import db
from models import User, Member, Trainer, GymClass, Booking, Equipment

app = create_app()
from datetime import date, datetime


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
            ('anna.nowak',        'Anna',   'Nowak',        'Yoga i pilates',                     100.0),
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

        # ── Zajęcia ──────────────────────────────────────────────────────────
        classes_rows = [
            (jan.id,   'Trening Siłowy Podstawowy',   'Podstawy treningu z wolnymi ciężarami i maszynami.',         15, 'Poniedziałek', '10:00', 60),
            (jan.id,   'Trening Siłowy Zaawansowany', 'Zaawansowane techniki i periodyzacja treningu siłowego.',    10, 'Środa',        '11:00', 90),
            (anna.id,  'Yoga dla Początkujących',     'Podstawowe asany, praca z oddechem i relaksacja.',           20, 'Wtorek',       '09:00', 60),
            (anna.id,  'Pilates',                     'Wzmacnianie core i poprawa postawy ciała.',                  15, 'Czwartek',     '10:00', 60),
            (piotr.id, 'CrossFit',                    'Intensywny trening funkcjonalny łączący siłę i wydolność.',  12, 'Środa',        '18:00', 60),
            (piotr.id, 'Trening Obwodowy',            'Trening całego ciała w formie stacji obwodowych.',           16, 'Piątek',       '16:00', 45),
            (marta.id, 'Cardio Blast',                'Wysokointensywny trening cardio spalający kalorie.',         25, 'Piątek',       '17:00', 45),
            (marta.id, 'Aerobik',                     'Klasyczny aerobik przy muzyce — dla każdego.',              20, 'Sobota',       '10:00', 60),
        ]
        classes = []
        for row in classes_rows:
            c = GymClass(trainer_id=row[0], name=row[1], description=row[2],
                         max_capacity=row[3], schedule_day=row[4],
                         schedule_time=row[5], duration_minutes=row[6])
            db.session.add(c)
            db.session.flush()
            classes.append(c)

        sil_podst, sil_zaaw, yoga, pilates, crossfit, obwodowy, cardio, aerobik = classes

        # ── Klienci ───────────────────────────────────────────────────────────
        members_rows = [
            ('tomasz.krol',       'Tomasz',   'Król',       '500-100-200', 'monthly',  date(2026, 6, 30)),
            ('ewa.dabrowska',     'Ewa',      'Dąbrowska',  '500-200-300', 'annual',   date(2026, 12, 31)),
            ('michal.kowalczyk',  'Michał',   'Kowalczyk',  '500-300-400', 'monthly',  date(2026, 5, 31)),
            ('karolina.szymanska','Karolina', 'Szymańska',  '500-400-500', 'day_pass', date(2026, 5, 20)),
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

        # ── Rezerwacje ────────────────────────────────────────────────────────
        bookings_rows = [
            (tomasz.id,   sil_podst.id, 'confirmed'),
            (tomasz.id,   crossfit.id,  'confirmed'),
            (tomasz.id,   aerobik.id,   'cancelled'),   # anulowana — do demonstracji
            (ewa.id,      yoga.id,      'confirmed'),
            (ewa.id,      pilates.id,   'confirmed'),
            (ewa.id,      cardio.id,    'confirmed'),
            (michal.id,   crossfit.id,  'confirmed'),
            (michal.id,   sil_podst.id, 'confirmed'),
            (michal.id,   obwodowy.id,  'confirmed'),
            (karolina.id, yoga.id,      'confirmed'),
            (karolina.id, aerobik.id,   'confirmed'),
        ]
        for member_id, class_id, status in bookings_rows:
            db.session.add(Booking(member_id=member_id, class_id=class_id, status=status,
                                   booked_at=datetime(2026, 5, 10, 14, 30)))

        # ── Sprzęt ────────────────────────────────────────────────────────────
        equipment_rows = [
            ('Sztanga olimpijska 20kg',        'Siłownia',     'working',     date(2023, 1, 15)),
            ('Bieżnia ProForm 9000 (szt. 1)',   'Cardio',       'working',     date(2022, 6, 1)),
            ('Bieżnia ProForm 9000 (szt. 2)',   'Cardio',       'working',     date(2022, 6, 1)),
            ('Orbitrek Horizon EX-59',          'Cardio',       'maintenance', date(2021, 3, 20)),
            ('Maty do jogi (x10)',              'Yoga/Pilates', 'working',     date(2023, 9, 1)),
            ('Komplet hantli 2–40 kg',          'Siłownia',     'working',     date(2022, 1, 10)),
            ('Rower stacjonarny LifeFitness',   'Cardio',       'broken',      date(2020, 11, 5)),
            ('Klatka na wolne ciężary',         'Siłownia',     'working',     date(2023, 5, 1)),
            ('Zestaw TRX',                      'CrossFit',     'working',     date(2023, 7, 15)),
            ('Skakanki (x20)',                  'CrossFit',     'working',     date(2024, 1, 10)),
        ]
        for name, category, status, purchase_date in equipment_rows:
            db.session.add(Equipment(name=name, category=category,
                                     status=status, purchase_date=purchase_date))

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
