import os
import sqlite3
import time
import requests
import sys
import bcrypt
from datetime import datetime, timezone

from app.DB.database import (
    get_connection,
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_user_favourites,
    add_favourite,
)

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
                break
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
# Auth / User helpers
# =========================

def sign_up(conn: sqlite3.Connection):
    print("\n=== SIGN UP ===")
    username = input("Username: ").strip()
    email = input("Email: ").strip().lower()
    password = input("Password: ").strip()
    mobility_problem = input("Mobility problem (opzionale): ").strip() or None

    if not username or not email or not password:
        print("Username, email e password sono obbligatori.")
        return None

    # opzionale: controllo preventivo
    if get_user_by_username(conn, username):
        print("Username già esistente.")
        return None

    if get_user_by_email(conn, email):
        print("Email già esistente.")
        return None

    password_hash = hash_password(password)

    try:
        user_id = create_user(
            conn=conn,
            username=username,
            email=email,
            password_hash=password_hash,
            mobility_problem=mobility_problem,
        )
        user = get_user_by_username(conn, username)
        print(f"✅ Utente creato con successo. ID: {user_id}")
        return user
    except sqlite3.IntegrityError as e:
        print(f"Errore di integrità nel database: {e}")
        return None

def sign_in(conn: sqlite3.Connection):
    print("\n=== SIGN IN ===")
    username = input("Username: ").strip()
    password = input("Password: ").strip()

    user = get_user_by_username(conn, username)
    if not user:
        print("Utente non trovato.")
        return None

    if not verify_password(password, user["password_hash"]):
        print("Password errata.")
        return None

    print(f"✅ Bentornato, {user['username']}!")
    return user


# =========================
# Favourites helpers
# =========================

def choose_favourite(conn: sqlite3.Connection, user_id: int):
    favourites = get_user_favourites(conn, user_id)

    if not favourites:
        print("Nessun preferito salvato.")
        return None

    print("\nPreferiti disponibili:")
    for i, fav in enumerate(favourites, start=1):
        print(f"{i}: {fav['label']} ({fav['latitude']}, {fav['longitude']})")

    while True:
        scelta = input("Seleziona un preferito: ").strip()
        if scelta.isdigit():
            idx = int(scelta)
            if 1 <= idx <= len(favourites):
                return favourites[idx - 1]
        print("Scelta non valida, riprova.")

def maybe_save_favourite(conn: sqlite3.Connection, user_id: int, point: dict):
    """
    Salva un singolo punto nei preferiti.
    """
    save = input("Vuoi salvare questo punto tra i preferiti? (y/N) ").strip().lower()
    if save != "y":
        return

    label = input("Inserisci un nome per questo preferito: ").strip()
    if not label:
        print("Label non valida.")
        return

    lat = point["coordinates"]["latitude"]
    lon = point["coordinates"]["longitude"]

    try:
        add_favourite(conn, user_id, label, lat, lon)
        print("✅ Preferito salvato.")
    except sqlite3.IntegrityError:
        print("Esiste già un preferito con questa label.")


# =========================
# Main
# =========================
def main():
    print("\n======================================")
    print("||  Avvio del Container di Python   ||")
    print("======================================\n")

    # Recupera l'URL di OTP dalle variabili d'ambiente (settato in docker-compose.yml)
    # Se non lo trova, usa localhost come fallback di sicurezza
    otp_url = os.getenv("OTP_URL", "http://localhost:8080/otp/transmodel/v3")
    
    # aspettiamo che OTP sia pronto
    attendi_otp(otp_url)

    conn = get_connection()

    WHEELCHAIR = True
    #TODO dai la possibilità di inserire da terminale origine/destinazione/data/ora/arriveBy/wheelchair/searchWindow
    variables = { #variabili default debug
        "from": {"coordinates": {"latitude": 45.47437, "longitude": 9.183323}},
        "to":   {"coordinates": {"latitude": 45.48535, "longitude": 9.20944}},
        "dateTime": "2026-02-28T16:07:08.511Z",  # TODO: mettici now
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
        "wheelchair": WHEELCHAIR,
        "arriveBy": False,
        "searchWindow": 40,
    }

    # IDEALMENTE:

    # faccio partire l'interfaccia web con cui l'utente può fare le sue richieste
    # questo diventerebbe un semplice server flask

    # all'arrivo di ogni richiesta si esegue OTP_routing (e quindi anche OSM_routing)
    # e si risponde con la mappa.html

    # questo script fa partire un azione periodica che esegue "dailyGTFSzipUpdater.py"
    # dopodiché blocco il container python e il server andrà in down
    # trovo un modo di lanciare il comando per ribuildare tutto col nuovo file Milano-gtfs.zip (updatato con la nuova accessibilità)
    
    # in tutto ciò c'è anche un'altra azione che esegue ogni ora per confrontare la
    # baseline che è stata scritta al tempo dell'update del GTFS con i nuovi dati sull'accessibilità
    # creando quindi un nuovo file "inaccessible_stations_till_last_GTFSzip_file_update.txt"
    # contenente i nomi delle stazioni che sono diventate inaccessibili


    print("Hello, please digit a number and press enter")
    print("1: sign up")
    print("2: sign in")
    print("3: use debug default path")

    logged_user = None

    while True:
        choice = input("> ").strip()

        if choice == "1":
            logged_user = sign_up(conn)
            if not logged_user:
                print("Please reselect one of the options and retry.")
                continue
            break

        elif choice == "2":
            logged_user = sign_in(conn)
            if not logged_user:
                print("Please reselect one of the options and retry.")
                continue
            break

        elif choice == "3":
            logged_user = None
            break

        else:
            print("Scelta non valida.")
            print("Please select one of the options")

    if logged_user is not None:
        user_id = logged_user["id"]

        def choose_point(conn, user_id: int, point_name: str) -> dict | None:
            """
            Chiede all'utente come impostare un punto (FROM o TO):
            1) da preferiti
            2) manualmente

            Ritorna un dict nel formato:
            {"coordinates": {"latitude": ..., "longitude": ...}}
            """
            print(f"\n{point_name}: come vuoi inserirlo?")
            print("1: usa un preferito salvato")
            print("2: inserisci manualmente")

            choice = input("> ").strip()
            while choice not in ["1", "2"]:
                print("Scelta non valida, riprova.")
                choice = input("> ").strip()

            if choice == "1":
                fav = choose_favourite(conn, user_id)
                if not fav:
                    return None

                return {
                    "coordinates": {
                        "latitude": fav["latitude"],
                        "longitude": fav["longitude"],
                    }
                }

            # choice == "2"
            point = input_coords(point_name)

            save = input(f"Vuoi salvare {point_name} tra i preferiti? (y/N) ").strip().lower()
            if save == "y":
                maybe_save_favourite(conn, user_id, point)

            return point

        print("\nImpostazione percorso")

        from_obj = choose_point(conn, user_id, "FROM")
        if not from_obj:
            conn.close()
            return

        to_obj = choose_point(conn, user_id, "TO")
        if not to_obj:
            conn.close()
            return

        variables["from"] = from_obj
        variables["to"] = to_obj

    # eseguo finalmente il programma
    try:
        import OTP_routing
        
        print("pronti, partenza, viaa 🚀 ...")
        OTP_routing.main(variables=variables)
        
    except ImportError as e:
        print(f"\n❌ Errore: Non trovo lo script OTP_routing.py. Errore: {e}")
    

if __name__ == "__main__":
    main()