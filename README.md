# VluchtWinkel — Flask-app voor vluchtverkoop

Een complete, compacte Flask-app waarmee je vluchten kunt aanmaken, als concept kunt bewaren, te koop kunt zetten en boekingen kunt verwerken.

## Functies

- Publieke vluchtwinkel met alleen vluchten die **te koop** staan
- Zoeken op vertrekplaats, bestemming en vertrekdatum
- Vluchtdetail met actuele stoelbeschikbaarheid
- Boeken van 1 t/m 9 stoelen met unieke boekingsreferentie
- Beveiligde boekingsopzoeking met boekingsreferentie én e-mailadres
- Beheerlogin
- Vluchten aanmaken en bewerken
- Statussen: **Concept**, **Te koop** en **Gepauzeerd**
- Capaciteitscontrole en bescherming tegen overboeking via een database-transactie
- Boekingsoverzicht en annuleren van boekingen
- CSRF-beveiliging voor formulieren
- SQLite-database; geen externe database nodig
- Responsieve vormgeving

## Snel starten

> Vereist Python 3.10 of hoger.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="een-lange-willekeurige-geheime-sleutel"
$env:ADMIN_PASSWORD="jouw-sterke-wachtwoord"
python seed.py
python run.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="een-lange-willekeurige-geheime-sleutel"
export ADMIN_PASSWORD="jouw-sterke-wachtwoord"
python seed.py
python run.py
```

Open daarna http://127.0.0.1:5000.

Je kunt ook `start_windows.bat` (Windows) of `sh start_linux_mac.sh` (macOS/Linux) gebruiken om de virtuele omgeving, afhankelijkheden en eerste voorbeelddata automatisch klaar te zetten.

## Beheer

Ga naar http://127.0.0.1:5000/admin/login.

Zonder omgevingsvariabele is het demonstratiewachtwoord `admin123`. Gebruik dit alleen lokaal. Stel vóór echt gebruik altijd `SECRET_KEY` en `ADMIN_PASSWORD` in.

## Tests uitvoeren

```bash
pytest -q
```

## Belangrijk voor productie

Dit is een degelijk MVP, maar voordat je echte betalingen of persoonsgegevens verwerkt, moet je onder meer:

- een productie-WSGI-server gebruiken, bijvoorbeeld Gunicorn of Waitress;
- HTTPS, logging, back-ups, monitoring en rate limiting instellen;
- beheeraccounts met gehashte wachtwoorden en rollen gebruiken;
- een echte e-maildienst en betaalprovider koppelen;
- AVG/privacyvoorwaarden, bewaartermijnen en toestemming juridisch inrichten;
- vlucht-, belasting-, tarief-, bagage- en annuleringsregels toevoegen;
- de SQLite-database vervangen door bijvoorbeeld PostgreSQL bij meerdere processen/servers;
- tijdzones expliciet opslaan en tonen.

## Projectstructuur

```text
vluchtwinkel/
├── app/
│   ├── __init__.py
│   ├── db.py
│   ├── routes.py
│   ├── static/style.css
│   └── templates/*.html
├── tests/test_app.py
├── .env.example
├── requirements.txt
├── run.py
├── seed.py
└── README.md
```
