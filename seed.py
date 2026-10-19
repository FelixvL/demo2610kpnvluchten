from datetime import datetime, timedelta
from app import create_app
from app.db import get_db

app = create_app()

with app.app_context():
    db = get_db()
    if db.execute("SELECT COUNT(*) AS n FROM flights").fetchone()["n"]:
        print("Er staan al vluchten in de database; er is niets toegevoegd.")
    else:
        base = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=14)
        flights = [
            ("VW101", "Amsterdam (AMS)", "Barcelona (BCN)", base.replace(hour=9), base.replace(hour=11, minute=20), 12900, 180, "ON_SALE", "Rechtstreekse vlucht"),
            ("VW205", "Eindhoven (EIN)", "Rome (FCO)", (base + timedelta(days=2)).replace(hour=13), (base + timedelta(days=2)).replace(hour=15, minute=10), 9900, 156, "ON_SALE", ""),
            ("VW330", "Rotterdam (RTM)", "Lissabon (LIS)", (base + timedelta(days=5)).replace(hour=7), (base + timedelta(days=5)).replace(hour=9, minute=55), 15900, 120, "DRAFT", "Nog niet zichtbaar voor klanten"),
        ]
        db.execute("BEGIN")
        db.executemany(
            """INSERT INTO flights
               (flight_number, origin, destination, departure_at, arrival_at, price_cents, capacity, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(n, o, d, dep.isoformat(timespec="minutes"), arr.isoformat(timespec="minutes"), p, c, s, notes)
             for n, o, d, dep, arr, p, c, s, notes in flights],
        )
        db.execute("COMMIT")
        print("3 voorbeeldvluchten toegevoegd.")
