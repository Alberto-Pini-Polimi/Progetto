import os
import sqlite3
import time
import requests
import sys
import bcrypt
import importlib
from datetime import datetime, timezone

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

from DB.database import (
    get_connection,
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_user_favourites,
    add_favourite,
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me") #TODO : usare una chiave segreta reale in produzione

OTP_URL = os.getenv("OTP_URL", "http://localhost:8080/otp/transmodel/v3")

# =========================
# OTP helpers
# =========================

def attendi_otp(url_otp, timeout_minuti=10):
    """
    Mette in pausa lo script finché OTP non risponde correttamente.
    """
    print(f"⏳ Attendo che OpenTripPlanner sia pronto all'indirizzo: {url_otp}")

    inizio = time.time()
    timeout_secondi = timeout_minuti * 60

    while True:
        try:
            response = requests.get("http://otp:8080/otp/", timeout=5)
            if response.status_code < 500:
                print("✅ OTP pronto.")
                return True
        except requests.RequestException:
            pass

        tempo_trascorso = time.time() - inizio
        if tempo_trascorso > timeout_secondi:
            print("\n❌ Timeout: OTP non sembra essere partito o c'è un errore")
            sys.exit(1)

        time.sleep(10)

def input_float(prompt: str) -> float:
    while True:
        s = input(prompt).strip().replace(",", ".")
        try:
            return float(s)
        except ValueError:
            print("Valore non valido, riprova.")

def input_coords(label: str) -> dict:
    lat = input_float(f"{label} latitude: ")
    lon = input_float(f"{label} longitude: ")
    return {"coordinates": {"latitude": lat, "longitude": lon}}

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# =========================
# Password helpers
# =========================

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        password_bytes = password.encode("utf-8")
        stored_hash_bytes = stored_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, stored_hash_bytes)
    except Exception:
        return False


# =========================
# Utils
# =========================

def get_logged_user():
    user_id = session.get("user_id")
    username = session.get("username")
    if not user_id:
        return None
    return {"id": user_id, "username": username}

def build_point_from_form(prefix: str):
    lat = request.form.get(f"{prefix}_lat", "").strip().replace(",", ".")
    lon = request.form.get(f"{prefix}_lon", "").strip().replace(",", ".")

    if not lat or not lon:
        raise ValueError(f"Coordinate mancanti per {prefix}")

    return {
        "coordinates": {
            "latitude": float(lat),
            "longitude": float(lon),
        }
    }

def point_from_favourite(fav):
    return {
        "coordinates": {
            "latitude": fav["latitude"],
            "longitude": fav["longitude"],
        }
    }

def get_default_variables(wheelchair=True):
    return {
        "from": {"coordinates": {"latitude": 45.47437, "longitude": 9.183323}},
        "to": {"coordinates": {"latitude": 45.48535, "longitude": 9.20944}},
        #"dateTime": now_utc_iso(), #TODO usalo in produzione
        "dateTime": "2026-02-28T16:07:08.511Z",
        "modes": {
            "transportModes": [
                {"transportMode": "bus"},
                {"transportMode": "metro"},
                {"transportMode": "tram"},
                {"transportMode": "rail"},
            ],
            "accessMode": "foot",
            "egressMode": "foot",
            "directMode": "foot",
        },
        "wheelchair": wheelchair,
        "arriveBy": False,
        "searchWindow": 40,
    }


# =========================
# Routes
# =========================

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_connection()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = get_user_by_username(conn, username)
        conn.close()

        if not user:
            flash("Utente non trovato.", "error")
            return render_template("login.html")

        if not verify_password(password, user["password_hash"]):
            flash("Password errata.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        flash(f"Benvenuto, {user['username']}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        conn = get_connection()

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        mobility_problem = request.form.get("mobility_problem", "").strip() or None

        if not username or not email or not password:
            flash("Username, email e password sono obbligatori.", "error")
            conn.close()
            return render_template("signup.html")

        if get_user_by_username(conn, username):
            flash("Username già esistente.", "error")
            conn.close()
            return render_template("signup.html")

        if get_user_by_email(conn, email):
            flash("Email già esistente.", "error")
            conn.close()
            return render_template("signup.html")

        password_hash = hash_password(password)

        try:
            create_user(
                conn=conn,
                username=username,
                email=email,
                password_hash=password_hash,
                mobility_problem=mobility_problem,
            )
            conn.close()
            flash("Utente creato con successo. Ora puoi fare login.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError as e:
            conn.close()
            flash(f"Errore database: {e}", "error")
            return render_template("signup.html")

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logout effettuato.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    user = get_logged_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_connection()
    favourites = get_user_favourites(conn, user["id"])

    if request.method == "POST":
        try:
            variables = get_default_variables(wheelchair=True)

            from_mode = request.form.get("from_mode", "manual")
            if from_mode == "favourite":
                from_fav_id = request.form.get("from_favourite")
                selected = next((f for f in favourites if str(f["id"]) == str(from_fav_id)), None)
                if not selected:
                    raise ValueError("Preferito FROM non valido.")
                from_obj = point_from_favourite(selected)
            else:
                from_obj = build_point_from_form("from")

                save_from = request.form.get("save_from")
                from_label = request.form.get("from_label", "").strip()
                if save_from and from_label:
                    try:
                        add_favourite(
                            conn,
                            user["id"],
                            from_label,
                            from_obj["coordinates"]["latitude"],
                            from_obj["coordinates"]["longitude"],
                        )
                    except sqlite3.IntegrityError:
                        flash("Label FROM già esistente tra i preferiti.", "error")

            to_mode = request.form.get("to_mode", "manual")
            if to_mode == "favourite":
                to_fav_id = request.form.get("to_favourite")
                selected = next((f for f in favourites if str(f["id"]) == str(to_fav_id)), None)
                if not selected:
                    raise ValueError("Preferito TO non valido.")
                to_obj = point_from_favourite(selected)
            else:
                to_obj = build_point_from_form("to")

                save_to = request.form.get("save_to")
                to_label = request.form.get("to_label", "").strip()
                if save_to and to_label:
                    try:
                        add_favourite(
                            conn,
                            user["id"],
                            to_label,
                            to_obj["coordinates"]["latitude"],
                            to_obj["coordinates"]["longitude"],
                        )
                    except sqlite3.IntegrityError:
                        flash("Label TO già esistente tra i preferiti.", "error")

            variables["from"] = from_obj
            variables["to"] = to_obj
            variables["dateTime"] = request.form.get("date_time") or now_utc_iso()
            variables["arriveBy"] = request.form.get("arrive_by") == "on"
            variables["wheelchair"] = request.form.get("wheelchair") == "on"

            search_window = request.form.get("search_window", "40").strip()
            variables["searchWindow"] = int(search_window) if search_window.isdigit() else 40

            otp_ready = attendi_otp(OTP_URL, timeout_minuti=3)
            if not otp_ready:
                conn.close()
                flash("OTP non è raggiungibile al momento.", "error")
                return render_template("dashboard.html", user=user, favourites=favourites)

            try:
                OTP_routing = importlib.import_module("OTP_routing")
                result = OTP_routing.main(variables=variables)
            except ImportError as e:
                conn.close()
                flash(f"Non trovo OTP_routing.py: {e}", "error")
                return render_template("dashboard.html", user=user, favourites=favourites)
            except Exception as e:
                conn.close()
                flash(f"Errore durante il routing: {e}", "error")
                return render_template("dashboard.html", user=user, favourites=favourites)

            conn.close()
            return render_template("result.html", variables=variables, result=result)

        except ValueError as e:
            conn.close()
            flash(str(e), "error")
            return render_template("dashboard.html", user=user, favourites=favourites)

        except Exception as e:
            conn.close()
            flash(f"Errore imprevisto: {e}", "error")
            return render_template("dashboard.html", user=user, favourites=favourites)

    conn.close()
    return render_template("dashboard.html", user=user, favourites=favourites)


@app.route("/debug-route")
def debug_route():
    variables = get_default_variables(wheelchair=True)

    otp_ready = attendi_otp(OTP_URL, timeout_minuti=3)
    if not otp_ready:
        flash("OTP non è raggiungibile al momento.", "error")
        return redirect(url_for("login"))

    try:
        OTP_routing = importlib.import_module("OTP_routing")
        result = OTP_routing.main(variables=variables)
        return render_template("result.html", variables=variables, result=result)
    except Exception as e:
        flash(f"Errore durante il routing di debug: {e}", "error")
        return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)