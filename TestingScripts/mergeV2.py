# File: scripts/transmodel_trip_debug.py
import os
import json
import requests
from typing import Any, Dict, List

URL = os.getenv("OTP_URL", "http://localhost:8080/otp/transmodel/v3")
HEADERS = {"Content-Type": "application/json"}

# Toggle rapido: prova prima con wheelchair=True; se non trovi transit, riprova False.
WHEELCHAIR_PROBE = True  # imposta a False se vuoi forzare solo la variante "non wheelchair"

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
    arriveBy: $arriveBy,
    debugItineraryFilter: true
  ) {
    tripPatterns {
      aimedStartTime
      aimedEndTime
      expectedStartTime
      expectedEndTime
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

def build_variables(wheelchair: bool) -> Dict[str, Any]:
    return {
        "from": {"coordinates": {"latitude": 45.47437, "longitude": 9.183323}},  # Cadorna (accessibile)
        "to":   {"coordinates": {"latitude": 45.48535, "longitude": 9.20944}},  # Sant'Agostino (accessibile)
        "dateTime": "2026-02-28T16:07:08.511Z",  #TODO FIXA A NOW
        "modes": {
            "transportModes": [
                {"transportMode": "bus"},
                {"transportMode": "metro"},
                {"transportMode": "tram"},
                {"transportMode": "rail"}  # S/regionale
            ],
            "accessMode": "foot",
            "egressMode": "foot",
            "directMode": "foot"  # permette di avere anche i percorsi a piedi completi
        },
        "wheelchair": wheelchair,
        "arriveBy": False,
        "searchWindow": 40  # minuti
    }

def call_trip(variables: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"query": QUERY, "variables": variables}
    r = requests.post(URL, json=payload, headers=HEADERS, timeout=60)
    print("HTTP Status:", r.status_code)
    try:
        return r.json()
    except json.JSONDecodeError:
        print("❌ Risposta non JSON:")
        print(r.text[:1000])
        return {}

def print_results(label: str, data: Dict[str, Any]) -> None:
    errors = data.get("errors") or []
    if errors:
        print(f"\n[{label}] GraphQL errors:")
        for e in errors:
            print(" -", e.get("message"))
    trip = (data.get("data") or {}).get("trip") or {}
    patterns: List[Dict[str, Any]] = trip.get("tripPatterns") or []

    if not patterns:
        print(f"\n[{label}] ❌ Nessun tripPattern trovato.")
        return

    # Ordina gli itinerari per generalized cost crescente; quelli senza costo vanno in fondo
    sorted_patterns = sorted(
        patterns,
        key=lambda p: p.get("generalizedCost") if p.get("generalizedCost") is not None else float("inf"),
    )

    print(f"\n[{label}] ✅ {len(sorted_patterns)} itinerari (tripPatterns)")
    for idx, p in enumerate(sorted_patterns[:5], 1):  # mostra i primi 5
        dur_min = int((p.get("duration") or 0) / 60)
        dist_km = (p.get("distance") or 0) / 1000
        cost_m  = (p.get("generalizedCost") or 0) / 60
        notices = p.get("systemNotices") or []
        modes   = [leg.get("mode") for leg in (p.get("legs") or [])]

        print(f"\n--- Itinerario #{idx} ---")
        print(f"Durata: {dur_min} min | Distanza: {dist_km:.2f} km | Costo gen.: {cost_m:.1f} m")
        print(f"Modalità: {' → '.join(modes) if modes else '(n/d)'}")
        if notices:
            print("Notices:")
            for n in notices:
                print(f"  - [{n.get('tag')}] {n.get('text')}")

        # Stampa sintetica delle legs
        for i, leg in enumerate(p.get("legs") or [], 1):
            mode = leg.get("mode", "").upper()
            f = leg.get("fromPlace", {}).get("name") or "?"
            t = leg.get("toPlace", {}).get("name") or "?"
            line = leg.get("line")
            if mode == "WALK":
                print(f"   {i}. 🚶 {f} → {t}")
            else:
                li = f"{line.get('publicCode')} - {line.get('name')}" if line else "Linea sconosciuta"
                print(f"   {i}. {mode} {f} → {t} ({li})")

def main():
    # 1) Primo tentativo: wheelchair=True (come avevi)
    if WHEELCHAIR_PROBE:
        vars_true = build_variables(True)
        data_true = call_trip(vars_true)
        print_results("wheelchair=True", data_true)

        # 2) Se non trovi transit o 0 risultati, prova subito con wheelchair=False
        trip_true = ((data_true.get("data") or {}).get("trip") or {}).get("tripPatterns") or []
        has_transit = any(
            any(leg.get("mode", "").upper() not in ("WALK", "BICYCLE", "SCOOTER") for leg in (p.get("legs") or []))
            for p in trip_true
        )
        if not trip_true or not has_transit:
            print("\nℹ️  Provo una seconda richiesta con wheelchair=False per escludere blocchi da accessibilità…")
            vars_false = build_variables(False)
            data_false = call_trip(vars_false)
            print_results("wheelchair=False", data_false)
    else:
        vars_false = build_variables(False)
        data_false = call_trip(vars_false)
        print_results("wheelchair=False", data_false)

if __name__ == "__main__":
    main()
