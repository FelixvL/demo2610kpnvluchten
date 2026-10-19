from datetime import datetime, timedelta
import pytest

from app import create_app
from app.db import get_db


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.sqlite"),
        "SECRET_KEY": "test",
        "ADMIN_PASSWORD": "testpass",
    })
    with app.app_context():
        db = get_db()
        departure = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
        arrival = departure + timedelta(hours=2)
        db.execute(
            """INSERT INTO flights
            (flight_number, origin, destination, departure_at, arrival_at, price_cents, capacity, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("TS100", "Amsterdam (AMS)", "Madrid (MAD)", departure.isoformat(timespec="minutes"), arrival.isoformat(timespec="minutes"), 10000, 3, "ON_SALE", "Test"),
        )
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_storefront_shows_on_sale_flight(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"TS100" in response.data


def test_booking_creates_reference_and_reserves_seats(client, app):
    response = client.post("/vluchten/1/boeken", data={
        "passenger_name": "Test Reiziger",
        "passenger_email": "test@example.com",
        "seats": "2",
    })
    assert response.status_code == 200
    assert b"Boeking bevestigd" in response.data
    with app.app_context():
        booking = get_db().execute("SELECT * FROM bookings").fetchone()
        assert booking["seats"] == 2
        assert booking["total_price_cents"] == 20000


def test_overbooking_is_rejected(client):
    response = client.post("/vluchten/1/boeken", data={
        "passenger_name": "Test Reiziger",
        "passenger_email": "test@example.com",
        "seats": "4",
    }, follow_redirects=True)
    assert b"voldoende stoelen" in response.data


def test_draft_flight_is_not_public(client, app):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE flights SET status = 'DRAFT' WHERE id = 1")
    response = client.get("/")
    assert b"TS100" not in response.data
    assert client.get("/vluchten/1").status_code == 404


def test_admin_can_login_and_create_flight(client):
    login = client.post("/admin/login", data={"password": "testpass"}, follow_redirects=True)
    assert b"Beheerdersdashboard" in login.data

    departure = (datetime.now() + timedelta(days=20)).replace(microsecond=0)
    arrival = departure + timedelta(hours=1, minutes=30)
    response = client.post("/admin/vluchten/nieuw", data={
        "flight_number": "TS200",
        "origin": "Eindhoven (EIN)",
        "destination": "Praag (PRG)",
        "departure_at": departure.isoformat(timespec="minutes"),
        "arrival_at": arrival.isoformat(timespec="minutes"),
        "price": "89,50",
        "capacity": "120",
        "status": "DRAFT",
        "notes": "Nieuwe vlucht",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"TS200" in response.data
