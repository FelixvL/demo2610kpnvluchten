import re
import secrets
import string
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, session, url_for,
)

from .db import get_db

bp = Blueprint("main", __name__)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
STATUS_LABELS = {"DRAFT": "Concept", "ON_SALE": "Te koop", "PAUSED": "Gepauzeerd"}


def admin_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if not session.get("is_admin"):
            flash("Log eerst in als beheerder.", "error")
            return redirect(url_for("main.admin_login", next=request.path))
        return view(**kwargs)
    return wrapped


def flight_with_availability(flight_id, public_only=False):
    clauses = ["f.id = ?"]
    params = [flight_id]
    if public_only:
        clauses += ["f.status = 'ON_SALE'", "f.departure_at > ?"]
        params.append(datetime.now().isoformat(timespec="minutes"))
    return get_db().execute(
        f"""SELECT f.*,
        f.capacity - COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN b.seats ELSE 0 END), 0) AS available_seats,
        COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN b.seats ELSE 0 END), 0) AS booked_seats
        FROM flights f
        LEFT JOIN bookings b ON b.flight_id = f.id
        WHERE {' AND '.join(clauses)}
        GROUP BY f.id""",
        params,
    ).fetchone()


def make_booking_reference(db):
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        reference = "VW-" + "".join(secrets.choice(alphabet) for _ in range(7))
        exists = db.execute("SELECT 1 FROM bookings WHERE booking_reference = ?", (reference,)).fetchone()
        if not exists:
            return reference
    raise RuntimeError("Kon geen unieke boekingsreferentie maken")


def parse_price_to_cents(raw):
    normalized = raw.strip().replace("€", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    else:
        normalized = normalized.replace(",", ".")
    try:
        value = Decimal(normalized)
        if not value.is_finite():
            raise InvalidOperation
        return int((value * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        raise ValueError("Ongeldige prijs")


def validate_flight_form(form, booked_seats=0):
    data = {
        "flight_number": form.get("flight_number", "").strip().upper(),
        "origin": form.get("origin", "").strip(),
        "destination": form.get("destination", "").strip(),
        "departure_at": form.get("departure_at", "").strip(),
        "arrival_at": form.get("arrival_at", "").strip(),
        "status": form.get("status", "DRAFT").strip(),
        "notes": form.get("notes", "").strip(),
    }
    errors = []
    if not re.fullmatch(r"[A-Z0-9]{2,4}[ -]?[0-9]{1,4}", data["flight_number"]):
        errors.append("Gebruik een geldig vluchtnummer, bijvoorbeeld VW101.")
    if len(data["origin"]) < 3 or len(data["destination"]) < 3:
        errors.append("Vul een geldige vertrekplaats en bestemming in.")
    if data["origin"].casefold() == data["destination"].casefold():
        errors.append("Vertrekplaats en bestemming moeten verschillend zijn.")
    try:
        departure = datetime.fromisoformat(data["departure_at"])
        arrival = datetime.fromisoformat(data["arrival_at"])
        if arrival <= departure:
            errors.append("De aankomsttijd moet na de vertrektijd liggen.")
        if data["status"] == "ON_SALE" and departure <= datetime.now():
            errors.append("Alleen een toekomstige vlucht kan te koop worden gezet.")
    except ValueError:
        errors.append("Vul geldige vertrek- en aankomsttijden in.")
    try:
        data["price_cents"] = parse_price_to_cents(form.get("price", ""))
        if data["price_cents"] < 0:
            raise ValueError
    except (ValueError, TypeError):
        errors.append("Vul een geldige, niet-negatieve prijs in.")
        data["price_cents"] = 0
    try:
        data["capacity"] = int(form.get("capacity", ""))
        if data["capacity"] < 1 or data["capacity"] > 1000:
            raise ValueError
        if data["capacity"] < booked_seats:
            errors.append(f"De capaciteit kan niet lager zijn dan de {booked_seats} reeds geboekte stoelen.")
    except (ValueError, TypeError):
        errors.append("De capaciteit moet tussen 1 en 1000 liggen.")
        data["capacity"] = max(booked_seats, 1)
    if data["status"] not in STATUS_LABELS:
        errors.append("Kies een geldige verkoopstatus.")
        data["status"] = "DRAFT"
    return data, errors


@bp.route("/")
def index():
    origin = request.args.get("origin", "").strip()
    destination = request.args.get("destination", "").strip()
    travel_date = request.args.get("date", "").strip()
    clauses = ["f.status = 'ON_SALE'", "f.departure_at > ?"]
    params = [datetime.now().isoformat(timespec="minutes")]
    if origin:
        clauses.append("f.origin LIKE ?")
        params.append(f"%{origin}%")
    if destination:
        clauses.append("f.destination LIKE ?")
        params.append(f"%{destination}%")
    if travel_date:
        clauses.append("substr(f.departure_at, 1, 10) = ?")
        params.append(travel_date)
    flights = get_db().execute(
        f"""SELECT f.*,
        f.capacity - COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN b.seats ELSE 0 END), 0) AS available_seats
        FROM flights f
        LEFT JOIN bookings b ON b.flight_id = f.id
        WHERE {' AND '.join(clauses)}
        GROUP BY f.id
        HAVING available_seats > 0
        ORDER BY f.departure_at""",
        params,
    ).fetchall()
    return render_template("index.html", flights=flights, origin=origin, destination=destination, travel_date=travel_date)


@bp.route("/vluchten/<int:flight_id>")
def flight_detail(flight_id):
    flight = flight_with_availability(flight_id, public_only=True)
    if not flight:
        abort(404)
    return render_template("flight_detail.html", flight=flight)


@bp.post("/vluchten/<int:flight_id>/boeken")
def book_flight(flight_id):
    name = request.form.get("passenger_name", "").strip()
    email = request.form.get("passenger_email", "").strip().lower()
    try:
        seats = int(request.form.get("seats", "0"))
    except ValueError:
        seats = 0
    errors = []
    if len(name) < 2:
        errors.append("Vul de volledige naam van de hoofdreiziger in.")
    if not EMAIL_RE.fullmatch(email):
        errors.append("Vul een geldig e-mailadres in.")
    if seats < 1 or seats > 9:
        errors.append("Je kunt per boeking 1 tot en met 9 stoelen reserveren.")
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("main.flight_detail", flight_id=flight_id))

    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        flight = db.execute(
            """SELECT f.*,
            f.capacity - COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN b.seats ELSE 0 END), 0) AS available_seats
            FROM flights f LEFT JOIN bookings b ON b.flight_id = f.id
            WHERE f.id = ? GROUP BY f.id""",
            (flight_id,),
        ).fetchone()
        if not flight or flight["status"] != "ON_SALE" or flight["departure_at"] <= datetime.now().isoformat(timespec="minutes"):
            db.execute("ROLLBACK")
            abort(404)
        if seats > flight["available_seats"]:
            db.execute("ROLLBACK")
            flash(f"Er zijn niet voldoende stoelen beschikbaar. Nog beschikbaar: {flight['available_seats']}.", "error")
            return redirect(url_for("main.flight_detail", flight_id=flight_id))
        reference = make_booking_reference(db)
        total = seats * flight["price_cents"]
        cursor = db.execute(
            """INSERT INTO bookings
            (booking_reference, flight_id, passenger_name, passenger_email, seats, total_price_cents)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (reference, flight_id, name, email, seats, total),
        )
        booking_id = cursor.lastrowid
        db.execute("COMMIT")
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise

    booking = db.execute(
        """SELECT b.*, f.flight_number, f.origin, f.destination, f.departure_at, f.arrival_at
        FROM bookings b JOIN flights f ON f.id = b.flight_id WHERE b.id = ?""",
        (booking_id,),
    ).fetchone()
    return render_template("booking_success.html", booking=booking)


@bp.route("/boeking-opzoeken", methods=["GET", "POST"])
def booking_lookup():
    booking = None
    searched = False
    if request.method == "POST":
        searched = True
        reference = request.form.get("booking_reference", "").strip().upper()
        email = request.form.get("passenger_email", "").strip().lower()
        booking = get_db().execute(
            """SELECT b.*, f.flight_number, f.origin, f.destination, f.departure_at, f.arrival_at
            FROM bookings b JOIN flights f ON f.id = b.flight_id
            WHERE b.booking_reference = ? AND lower(b.passenger_email) = ?""",
            (reference, email),
        ).fetchone()
        if not booking:
            flash("Geen boeking gevonden met deze combinatie.", "error")
    return render_template("booking_lookup.html", booking=booking, searched=searched)


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if secrets.compare_digest(password, current_app.config["ADMIN_PASSWORD"]):
            session.clear()
            session["is_admin"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            flash("Je bent ingelogd.", "success")
            next_url = request.args.get("next", "")
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("main.admin_dashboard")
            return redirect(next_url)
        flash("Onjuist wachtwoord.", "error")
    return render_template("admin_login.html")


@bp.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    flash("Je bent uitgelogd.", "success")
    return redirect(url_for("main.index"))


@bp.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    flights = db.execute(
        """SELECT f.*,
        COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN b.seats ELSE 0 END), 0) AS booked_seats,
        f.capacity - COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN b.seats ELSE 0 END), 0) AS available_seats,
        COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN b.total_price_cents ELSE 0 END), 0) AS revenue_cents
        FROM flights f LEFT JOIN bookings b ON b.flight_id = f.id
        GROUP BY f.id ORDER BY f.departure_at DESC"""
    ).fetchall()
    stats = db.execute(
        """SELECT
        (SELECT COUNT(*) FROM flights) AS flights,
        (SELECT COUNT(*) FROM flights WHERE status = 'ON_SALE') AS on_sale,
        (SELECT COUNT(*) FROM bookings WHERE status = 'CONFIRMED') AS bookings,
        (SELECT COALESCE(SUM(total_price_cents), 0) FROM bookings WHERE status = 'CONFIRMED') AS revenue_cents"""
    ).fetchone()
    return render_template("admin_dashboard.html", flights=flights, stats=stats, labels=STATUS_LABELS)


@bp.route("/admin/vluchten/nieuw", methods=["GET", "POST"])
@admin_required
def admin_flight_new():
    if request.method == "POST":
        data, errors = validate_flight_form(request.form)
        if not errors:
            db = get_db()
            db.execute(
                """INSERT INTO flights
                (flight_number, origin, destination, departure_at, arrival_at, price_cents, capacity, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["flight_number"], data["origin"], data["destination"], data["departure_at"], data["arrival_at"], data["price_cents"], data["capacity"], data["status"], data["notes"]),
            )
            flash("Vlucht aangemaakt.", "success")
            return redirect(url_for("main.admin_dashboard"))
        for error in errors:
            flash(error, "error")
    return render_template("admin_flight_form.html", flight=None, labels=STATUS_LABELS)


@bp.route("/admin/vluchten/<int:flight_id>/bewerken", methods=["GET", "POST"])
@admin_required
def admin_flight_edit(flight_id):
    flight = flight_with_availability(flight_id)
    if not flight:
        abort(404)
    if request.method == "POST":
        data, errors = validate_flight_form(request.form, flight["booked_seats"])
        if not errors:
            get_db().execute(
                """UPDATE flights SET flight_number = ?, origin = ?, destination = ?, departure_at = ?,
                arrival_at = ?, price_cents = ?, capacity = ?, status = ?, notes = ? WHERE id = ?""",
                (data["flight_number"], data["origin"], data["destination"], data["departure_at"], data["arrival_at"], data["price_cents"], data["capacity"], data["status"], data["notes"], flight_id),
            )
            flash("Vlucht bijgewerkt.", "success")
            return redirect(url_for("main.admin_dashboard"))
        for error in errors:
            flash(error, "error")
    return render_template("admin_flight_form.html", flight=flight, labels=STATUS_LABELS)


@bp.post("/admin/vluchten/<int:flight_id>/status")
@admin_required
def admin_flight_status(flight_id):
    status = request.form.get("status", "")
    if status not in STATUS_LABELS:
        abort(400)
    flight = flight_with_availability(flight_id)
    if not flight:
        abort(404)
    if status == "ON_SALE" and flight["departure_at"] <= datetime.now().isoformat(timespec="minutes"):
        flash("Een vertrokken vlucht kan niet te koop worden gezet.", "error")
    else:
        get_db().execute("UPDATE flights SET status = ? WHERE id = ?", (status, flight_id))
        flash(f"Status gewijzigd naar {STATUS_LABELS[status].lower()}.", "success")
    return redirect(url_for("main.admin_dashboard"))


@bp.route("/admin/boekingen")
@admin_required
def admin_bookings():
    bookings = get_db().execute(
        """SELECT b.*, f.flight_number, f.origin, f.destination, f.departure_at
        FROM bookings b JOIN flights f ON f.id = b.flight_id
        ORDER BY b.created_at DESC, b.id DESC"""
    ).fetchall()
    return render_template("admin_bookings.html", bookings=bookings)


@bp.post("/admin/boekingen/<int:booking_id>/annuleren")
@admin_required
def admin_booking_cancel(booking_id):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        abort(404)
    if booking["status"] == "CONFIRMED":
        db.execute("UPDATE bookings SET status = 'CANCELLED' WHERE id = ?", (booking_id,))
        flash("Boeking geannuleerd; de stoelen zijn weer beschikbaar.", "success")
    return redirect(url_for("main.admin_bookings"))


@bp.app_errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Ongeldig verzoek.")), 400


@bp.app_errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="Deze pagina of vlucht bestaat niet (meer)."), 404


@bp.app_errorhandler(500)
def server_error(_error):
    return render_template("error.html", code=500, message="Er ging onverwacht iets mis. Probeer het later opnieuw."), 500
