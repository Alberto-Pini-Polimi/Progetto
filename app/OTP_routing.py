import os
import requests
import ORS_routing

URL = os.getenv("OTP_URL", "http://localhost:8080/otp/transmodel/v3")
HEADERS = {"Content-Type": "application/json"}

QUERY = """
query trip(
  $dateTime: DateTime,
  $from: Location!,
  $to: Location!,
  $modes: Modes,
  $wheelchair: Boolean,
  $searchWindow: Int,
  $arriveBy: Boolean
) {
  trip(
    dateTime: $dateTime,
    from: $from,
    to: $to,
    modes: $modes,
    wheelchairAccessible: $wheelchair,
    searchWindow: $searchWindow,
    arriveBy: $arriveBy
  ) {
    tripPatterns {
      duration
      distance
      generalizedCost
      systemNotices { tag text }
      legs {
        mode
        fromPlace {
            name
            latitude
            longitude
            quay { id name latitude longitude }
        }
        toPlace {
            name
            latitude
            longitude
            quay { id name latitude longitude }
        }
        line { publicCode name id presentation { colour } }
      }
    }
  }
}
"""

# ALTRE FUNZIONI

def sign_up(users: dict) -> str | None:
    username = input("Scegli username: ").strip()
    if not username:
        print("Username vuoto.")
        return None
    if username in users:
        print("Username già esistente.")
        return None
    users[username] = {"favorite": None}
    print("Registrazione OK.")
    return username

def sign_in(users: dict) -> str | None:
    username = input("Username: ").strip()
    if username not in users:
        print("Utente non trovato.")
        return None
    print("Login OK.")
    return username

def set_favorite(users: dict, username: str, from_obj: dict, to_obj: dict) -> None:
    users[username]["favorite"] = {"from": from_obj, "to": to_obj}




















# HELPER FUNCTIONS PER route()

def format_coordinates(place: dict) -> str: #formatta coordinate
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lat is None or lon is None:
        return "(?,?)"
    return f"({lat:.6f},{lon:.6f})"

def get_place_coord(place: dict):
    """
    Ritorna (lat, lon) preferendo le coordinate della quay (fermata) se presenti.
    """
    if not place:
        return None

    quay = place.get("quay") or {}
    lat = quay.get("latitude")
    lon = quay.get("longitude")
    if lat is None or lon is None:
        lat = place.get("latitude")
        lon = place.get("longitude")

    if lat is None or lon is None:
        return None

    return (float(lat), float(lon))

def extractLegs(patterns):
    """
    Estrae la lista delle legs dal primo tripPattern.
    Ritorna una lista di dict, ciascuna rappresentante una leg.
    """
    if not patterns:
        return []
    p = patterns[0]
    legs = p.get("legs") or []
    return legs 


# FUNZIONE PRINCIPALE!! CHIAMATA DA main.py (server)

def route(variables):
    """
    Funzione principale chiamata da main.py per calcolare il percorso completo.
    Effettua la chiamata a OTP con le variables, ottiene i tripPatterns,
    ordina per generalizedCost, prende il migliore, estrae le legs,
    crea e popola la mappa con percorsi pedonali (via ORS) e segmenti di mezzi pubblici,
    salva la mappa in HTML e ritorna il contenuto HTML.
    """

    # variabile locale per capire se l'utente è in sedia a rotelle
    wheelchair = variables["wheelchair"]

    # Effettua la chiamata HTTP a OTP (POST GraphQL) per ottenere gli itinerari
    richiesta_otp = requests.post(
        url=URL,  # URL del server OTP
        json={"query": QUERY, "variables": variables},  # Payload GraphQL con query e variabili
        headers=HEADERS,  # Headers con Content-Type application/json
        timeout=60  # Timeout di 60 secondi per la richiesta
    )
    richiesta_otp.raise_for_status()  # Solleva eccezione se la risposta ha status code di errore
    dati_risposta = richiesta_otp.json()  # Parso la risposta JSON

    # Gestione errori nella risposta GraphQL
    if dati_risposta.get("errors"):
        print("GraphQL errors:")
        for errore in dati_risposta["errors"]:
            print(" -", errore.get("message"))
        return None  # Ritorna None in caso di errori

    # Estrai i tripPatterns dalla risposta
    patterns = (
        (dati_risposta.get("data") or {}).get("trip") or {}
    ).get("tripPatterns") or []
    if not patterns:
        print("Nessun tripPattern trovato.")
        return None

    # Ordina i patterns per generalizedCost (costo generale) e prendi i top 3 per debug
    patterns_ordinati = sorted(
        patterns,
        key=lambda p: p.get("generalizedCost") if p.get("generalizedCost") is not None else float("inf")
    )[:2] # prendo i due migliori pattern

    # SVARIATE RIGHE SOLTANTO PER STAMPARE!!
    stringaOutput = ""
    print(f"Top {len(patterns_ordinati)} itinerari (wheelchair={wheelchair}):")
    for idx, p in enumerate(patterns_ordinati, 1):
        # cose per il print
        costo_secondi = p.get("generalizedCost")
        durata_secondi = p.get("duration")

        costo_minuti = (costo_secondi / 60.0) if isinstance(costo_secondi, (int, float)) else None
        durata_minuti = int(durata_secondi / 60) if isinstance(durata_secondi, (int, float)) else None

        costo_str = f"{costo_minuti:.1f} min" if costo_minuti is not None else "n/d"
        durata_str = f"{durata_minuti} min" if durata_minuti is not None else "n/d"

        stringaOutput += f"\n--- Itinerario #{idx} ---\n"
        stringaOutput += f"Generalized cost: {costo_str} | Durata prevista: {durata_str}\n"

        # STAMPO LE INFO SULLE SINGOLE LEGS
        legs = p.get("legs") or []
        for j, leg in enumerate(legs, 1):
            mode = (leg.get("mode") or "?").upper()
            fp = leg.get("fromPlace") or {}
            tp = leg.get("toPlace") or {}
            nome_partenza = fp.get("name") or "?"
            nome_arrivo = tp.get("name") or "?"

            coordinate_partenza = format_coordinates(fp)
            coordinate_arrivo = format_coordinates(tp)

            if mode == "FOOT":
                stringaOutput += f"\t{j}. 🚶 {nome_partenza} {coordinate_partenza} --> {nome_arrivo} {coordinate_arrivo}\n"
            else:
                line = leg.get("line") or {}
                codice_linea = line.get("publicCode") or ""
                nome_linea = line.get("name") or ""
                linea_completa = (f"{codice_linea} {nome_linea}").strip() or "Linea sconosciuta"
                stringaOutput += f"\t{j}. {mode} {nome_partenza} {coordinate_partenza} --> {nome_arrivo} {coordinate_arrivo} ({linea_completa})\n"

    print(stringaOutput) # questa la posso usare dopo per mostrarlo nel risultato


    # Creo la mappa vuota da ritornare come risultato
    mappa = ORS_routing.Map()
    # a cui ci aggiungerò tutte le legs...

    # Lavoro sul migliore itinerario trovato da OTP
    miglior_itinerario = patterns_ordinati[0]

    # Estrai le legs dal miglior itinerario
    legs = extractLegs([miglior_itinerario])

    # Itera ogni leg per popolare la mappa
    for leg in legs:
        modalita = (leg.get("mode") or "").upper()  # Modalità di trasporto (FOOT, BUS, ecc.)
        luogo_partenza = leg.get("fromPlace") or {}
        luogo_arrivo = leg.get("toPlace") or {}

        coordinate_partenza = get_place_coord(luogo_partenza)  # (lat, lon) di partenza
        coordinate_arrivo = get_place_coord(luogo_arrivo)  # (lat, lon) di arrivo
        nome_partenza = luogo_partenza.get("name") or "?"  # Nome del luogo di partenza
        nome_arrivo = luogo_arrivo.get("name") or "?"  # Nome del luogo di arrivo

        if modalita == "FOOT":
            # Chiama ORS per calcolare il percorso pedonale e aggiungere dettagli alla mappa
            mappa = ORS_routing.calculateWalkingLegAndAddResultToMap(
                coordinateInizio=coordinate_partenza,  # Coordinate di inizio del segmento pedonale
                coordinateFine=coordinate_arrivo,  # Coordinate di fine del segmento pedonale
                mappaACuiAggiungereLaLegCalcolata=mappa,  # Oggetto mappa da aggiornare
                wheelchair=wheelchair  # Flag per considerare accessibilità wheelchair
            )
        else:
            # Aggiungi il segmento del mezzo pubblico alla mappa
            linea = leg.get("line") or {}
            codice_linea = linea.get("publicCode") or ""  # Codice della linea (es. M1)
            nome_linea = linea.get("name") or ""  # Nome della linea
            nome_linea_completo = (f"{codice_linea} {nome_linea}").strip() or "Linea sconosciuta"  # Nome completo della linea
            tipologia_mezzo = modalita.lower()  # Tipo di mezzo in minuscolo (bus, metro, ecc.)

            # Chiama il metodo della mappa per aggiungere il mezzo pubblico
            mappa = mappa.aggiungiMezzoPubblico(
                inizio=coordinate_partenza,  # Coordinate di inizio del segmento del mezzo
                fine=coordinate_arrivo,  # Coordinate di fine del segmento del mezzo
                nome_inizio=nome_partenza,  # Nome della fermata di partenza
                nome_fine=nome_arrivo,  # Nome della fermata di arrivo
                tipologia_mezzo=tipologia_mezzo,  # Tipo di mezzo (bus, metro, tram, treno)
                nome_linea=nome_linea_completo  # Nome completo della linea
            )

    return mappa, stringaOutput # ritorna la mappa

