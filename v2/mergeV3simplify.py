import os
import requests
import routingProgram

URL = os.getenv("OTP_URL", "http://localhost:8080/otp/transmodel/v3")
HEADERS = {"Content-Type": "application/json"}

WHEELCHAIR = True  # metti False se non ti serve

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

def fmt_coord(place: dict) -> str: #formatta coordinate
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

def extract_walk_legs_and_print_public_transports(patterns):
    """
    Ritorna una lista di dict, uno per ogni leg WALK: (isola le walking legs per darle a ors)
    e stampa le altre legs (trasporto pubblico)
    TODO per ora solo stampa, poi potrei provare a passare a routingProgram.aggiungiMezzoPubblico(...))
    [
    {"itinerary_idx": 1, "leg_idx": 2, "from_name": "...", "to_name": "...", "from": (lat,lon), "to": (lat,lon)},
    ...
    ]
    """
    walk_legs = []

    if not patterns:
        return walk_legs

    p = patterns[0]   # ← solo primo path
    itinerary_idx = 1

    for leg_idx, leg in enumerate(p.get("legs") or [], 1):
        fp = leg.get("fromPlace") or {}
        tp = leg.get("toPlace") or {}

        a = get_place_coord(fp)
        b = get_place_coord(tp)
        if not a or not b:
            print(f"Leg {leg_idx} manca di coordinate valide")
            exit(-1)
        
        mode = (leg.get("mode") or "").upper()

        if mode != "FOOT":
            #per ogni leg che non è di tipo WALK, stampo solo una linea del mezzo pubblico
            print(f"\nLeg {leg_idx} non è FOOT: {mode} quindi la stampo ma non la passo a ORS.")
            #TODO avvia la funzione routingProgram.aggiungiMezzoPubblico(...)
            if a and b:
                line = leg.get("line") or {}
                code = line.get("publicCode") or ""
                name = line.get("name") or ""
                nome_linea = (f"{code} {name}").strip() or "Linea sconosciuta"

                # tipologia mezzo: metro/bus/tram/rail ecc. (usa mode lowercase)
                tipologia_mezzo = mode.lower()

                routingProgram.aggiungiMezzoPubblico(
                    inizio=a,
                    fine=b,
                    tipologia_mezzo=tipologia_mezzo,
                    nome_linea=nome_linea
                )
            continue

        walk_legs.append({
            "itinerary_idx": itinerary_idx,
            "leg_idx": leg_idx,
            "from_name": fp.get("name") or "?",
            "to_name": tp.get("name") or "?",
            "from": a,
            "to": b,
        })

    return walk_legs

def ORS_call_and_draw(patterns):
    """
    Per ogni leg di tipo WALK del primo pattern,
    chiama ORS per calcolare il percorso pedonale e disegna.
    """
    walk_legs = extract_walk_legs_and_print_public_transports(patterns) #estrae solo dal primo path
    if not walk_legs:
        print("Nessuna WALK leg trovata.")
        return

    Ultima_Leg=0 #0 per non far aprire il browser, diventa 1 nell'ultima leg WALK
    #le wl sono coppie di coordinate (lat, lon) con i nomi dei posti di partenza e arrivo
    for k, wl in enumerate(walk_legs, 1): 
        a = wl["from"]  # (lat, lon)
        b = wl["to"]    # (lat, lon)

        print(f"\n[{k}/{len(walk_legs)}] WALK leg: {wl['from_name']} -> {wl['to_name']} | {a} -> {b}")
        if k==len(walk_legs):
            #Questa è l'ultima leg WALK, apro browser con tutte le leg WALK precedenti
            Ultima_Leg=1

        # passa (lat, lon) a ORS e disegna
        routingProgram.run_with_coordinates(
            COORDINATE_INIZIO_input=a,
            COORDINATE_FINE_input=b,
            #NOME_UTENTE_input="Utente",
            PROBLEMATICA_UTENTE_input=routingProgram.ProblemiMobilità.MOTORIA,
            Ultima_Leg_input=Ultima_Leg
        )

def main():
    #TODO dai la possibilità di inserire da terminale origine/destinazione/data/ora/arriveBy/wheelchair/searchWindow
    variables = {
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

    #Chiamata HTTP a OTP (POST GraphQL)
    r = requests.post(URL, json={"query": QUERY, "variables": variables}, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()

    #gestione errori e stampa risultati
    if data.get("errors"):
        print("GraphQL errors:")
        for e in data["errors"]:
            print(" -", e.get("message"))
        return

    patterns = ((data.get("data") or {}).get("trip") or {}).get("tripPatterns") or []
    if not patterns:
        print("Nessun tripPattern trovato.")
        return

    #ordino per generalizedCost (costo generale) e prendo i primi 3
    patterns = sorted(
        patterns,
        key=lambda p: p.get("generalizedCost") if p.get("generalizedCost") is not None else float("inf")
    )[:3]

    #SVARIATE RIGHE SOLTANTO PER STAMPARE. LA LOGICA CONTINUA DOVE DICO CHE MI COLLEGO CON ALBERTO
    print(f"Top {len(patterns)} itinerari (wheelchair={WHEELCHAIR}):")
    for idx, p in enumerate(patterns, 1):
        #INFO GENERALI DEL PATH
        cost_sec = p.get("generalizedCost")
        dur_sec = p.get("duration")

        cost_min = (cost_sec / 60.0) if isinstance(cost_sec, (int, float)) else None
        dur_min = int(dur_sec / 60) if isinstance(dur_sec, (int, float)) else None

        cost_str = f"{cost_min:.1f} min" if cost_min is not None else "n/d"
        dur_str = f"{dur_min} min" if dur_min is not None else "n/d"

        print(f"\n--- Itinerario #{idx} ---")
        print(f"Generalized cost: {cost_str} | Durata prevista: {dur_str}")

        #STAMPO LE INFO SULLE SINGOLE LEGS
        legs = p.get("legs") or []
        for j, leg in enumerate(legs, 1):
            mode = (leg.get("mode") or "?").upper()
            fp = leg.get("fromPlace") or {}
            tp = leg.get("toPlace") or {}
            a_name = fp.get("name") or "?"
            b_name = tp.get("name") or "?"

            a_coord = fmt_coord(fp)
            b_coord = fmt_coord(tp)

            if mode == "FOOT":
                print(f" {j}. 🚶 {a_name} {a_coord} → {b_name} {b_coord}")
            else:
                line = leg.get("line") or {}
                code = line.get("publicCode") or ""
                name = line.get("name") or ""
                line_str = (f"{code} {name}").strip() or "Linea sconosciuta"
                print(f" {j}. {mode} {a_name} {a_coord} → {b_name} {b_coord} ({line_str})")


    #DA QUA AVVIENE IL COLLEGAMENTO CON SCRIPT DI ALBERTO
    #chiamo una funzione a cui passo le coordinate delle legs e i nomi delle linee con salita e discesa.
    #questa funzione chiama ORS per calcolare la polyline pedonale, poi applica il matching OSM e disegna
    ORS_call_and_draw(patterns) #TODO dare la possibilita a un utente di scegliere quale itinerario scegliere tra i path di osm

if __name__ == "__main__":
    main()