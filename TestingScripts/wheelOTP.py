import requests
import json

url = "http://localhost:8080/otp/transmodel/v3"
headers = {"Content-Type": "application/json"}

query = """
query trip($dateTime: DateTime, $from: Location!, $to: Location!) {
  trip(dateTime: $dateTime, from: $from, to: $to) {
    tripPatterns {
      aimedStartTime
      aimedEndTime
      expectedStartTime
      expectedEndTime
      duration
      distance
      generalizedCost
      legs {
        mode
        fromPlace { name }
        toPlace { name }
        line { publicCode name }
        pointsOnLink { points }
      }
    }
  }
}
"""

variables = {
    "from": {
        "coordinates": {
            "latitude": 45.481685414153816,
            "longitude": 9.182068687522559
        }
    },
    "to": {
        "coordinates": {
            "latitude": 45.50217816956206,
            "longitude": 9.16154437030653
        }
    },
    "dateTime": "2025-10-24T18:07:08.511Z"
}

# Parametri di accessibilità per wheelchair
wheelchair_payload = {
    "routingDefaults": {
        "wheelchairAccessibility": {
            "trip": {
                "onlyConsiderAccessible": False,
                "unknownCost": 600,
                "inaccessibleCost": 3600
            },
            "stop": {
                "onlyConsiderAccessible": False,
                "unknownCost": 600,
                "inaccessibleCost": 3600
            },
            "elevator": {
                "onlyConsiderAccessible": False
            },
            "inaccessibleStreetReluctance": 25,
            "maxSlope": 0.08333,
            "slopeExceededReluctance": 1,
            "stairsReluctance": 25
        }
    },
    "updaters": []
}

# Componi payload finale
payload = {
    "query": query,
    "variables": variables,
    "routingDefaults": wheelchair_payload["routingDefaults"]
}

response = requests.post(url, json=payload, headers=headers)

print("Status:", response.status_code)

try:
    data = response.json()
    #print(json.dumps(data, indent=2))  # per debug
except json.JSONDecodeError:
    print("❌ Risposta non in formato JSON:", response.text)

# Stampa percorso
trip = data.get("data", {}).get("trip")
if not trip:
    print("❌ Nessun trip trovato")
else:
    patterns = trip.get("tripPatterns")
    if not patterns:
        print("❌ Nessun percorso trovato (tripPatterns undefined)")
    else:
        pattern = patterns[0]
        durata_min = int(pattern.get('duration', 0) / 60)
        distanza_km = pattern.get('distance', 0) / 1000
        print(f"\n--- Primo percorso trovato ---")
        print(f"Durata prevista: {durata_min} min")
        print(f"Distanza totale: {distanza_km:.2f} km")
        print(f"Costo generalizzato: {pattern.get('generalizedCost')}\n")

        for i, leg in enumerate(pattern["legs"], 1):
            mode = leg['mode']
            from_name = leg['fromPlace'].get('name') or "?"
            to_name = leg['toPlace'].get('name') or "?"
            if mode.lower() == 'foot':
                print(f"{i}. 🚶 Cammina da {from_name} a {to_name}")
            else:
                line = leg.get('line')
                line_info = f"{line.get('publicCode')} - {line.get('name')}" if line else "Linea sconosciuta"
                print(f"{i}. {mode.upper()} da {from_name} a {to_name} con {line_info}")
            points = leg.get('pointsOnLink', {}).get('points', '')
            if points:
                print(f"   Polyline anteprima: {points[:80]}...")
            print()
