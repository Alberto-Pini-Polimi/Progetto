import os
import requests

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

def main():
    #TODO dai la possibilità di inserire da terminale origine/destinazione/data/ora/arriveBy/wheelchair/searchWindow
    variables = {
        "from": {"coordinates": {"latitude": 45.47437, "longitude": 9.183323}},
        "to":   {"coordinates": {"latitude": 45.48535, "longitude": 9.20944}},
        "dateTime": "2026-02-28T16:07:08.511Z",  # TODO: now
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

    #ordino per generalizedCost (costo generale) e prendo i primi 5
    patterns = sorted(
        patterns,
        key=lambda p: p.get("generalizedCost") if p.get("generalizedCost") is not None else float("inf")
    )[:5]

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

        #INFO SULLE SINGOLE LEGS
        legs = p.get("legs") or []
        for j, leg in enumerate(legs, 1):
            mode = (leg.get("mode") or "?").upper()
            fp = leg.get("fromPlace") or {}
            tp = leg.get("toPlace") or {}
            a_name = fp.get("name") or "?"
            b_name = tp.get("name") or "?"

            a_coord = fmt_coord(fp)
            b_coord = fmt_coord(tp)

            if mode == "WALK":
                print(f" {j}. 🚶 {a_name} {a_coord} → {b_name} {b_coord}")
            else:
                line = leg.get("line") or {}
                code = line.get("publicCode") or ""
                name = line.get("name") or ""
                line_str = (f"{code} {name}").strip() or "Linea sconosciuta"
                print(f" {j}. {mode} {a_name} {a_coord} → {b_name} {b_coord} ({line_str})")

    #DA QUA SI VUOLE PREPARARE IL COLLEGAMENTO CON SCRIPT DI ALBERTO
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

    def extract_walk_legs(patterns):
        """
        Ritorna una lista di dict, uno per ogni leg WALK: (isola le walking legs per darle a ors)
        [
        {"itinerary_idx": 1, "leg_idx": 2, "from_name": "...", "to_name": "...", "from": (lat,lon), "to": (lat,lon)},
        ...
        ]
        """
        walk_legs = []
        for it_idx, p in enumerate(patterns, 1):
            for leg_idx, leg in enumerate(p.get("legs") or [], 1):
                mode = (leg.get("mode") or "").upper()
                if mode != "WALK":
                    continue

                fp = leg.get("fromPlace") or {}
                tp = leg.get("toPlace") or {}

                a = get_place_coord(fp)
                b = get_place_coord(tp)
                if not a or not b:
                    continue

                walk_legs.append({
                    "itinerary_idx": it_idx,
                    "leg_idx": leg_idx,
                    "from_name": fp.get("name") or "?",
                    "to_name": tp.get("name") or "?",
                    "from": a,  # (lat, lon)
                    "to": b,    # (lat, lon)
                })
        return walk_legs
    
    #chiamo una funzione a cui passo le coordinate delle walking legs e i nomi delle linee con salita e discesa.
    #questa funzione chiama ORS per calcolare la polyline pedonale, poi applica il matching OSM e disegna
    def ORS_call_and_draw(patterns):
        walk_legs = extract_walk_legs(patterns)
        if not walk_legs:
            print("Nessuna WALK leg trovata.")
            return

        # import qui per evitare side effects all'import (chiavi/API ecc.)
        import routingProgram

        # Disegna tutte le walking legs trovate (anche da itinerari diversi)
        routingProgram.run_for_walk_legs(
            walk_legs=walk_legs,
            problematica_utente=routingProgram.ProblemiMobilità.MOTORIA
        )

    ORS_call_and_draw(patterns) #TODO valuta di dare la possibilita a un utente di scegliere quale itinerario disegnare




if __name__ == "__main__":
    main()