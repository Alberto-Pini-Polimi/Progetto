'''
bovisa
"latitude": 45.5021781,
"longitude": 9.1615443

campus leonardo
"latitude": 45.479500,
"longitude": 9.222800

san siro stadio
"latitude": 45.478000,
"longitude": 9.124000

affori
"latitude": 45.5153,
"longitude": 9.17216

lorenteggio
"latitude": 45.44682,
"longitude": 9.124629

moscova
"latitude": 45.4816854,
"longitude": 9.1820686

dateo
"latitude": 45.487500,
"longitude": 9.203000

'''
'''
lampugnano m1
45.48898 9.125479

cadorna m1 m2
45.46765 9.175563

cologno sud m2
45.51992 9.274548

tra moscova e lanza m2
45.47437 9.183323

caiazzo m2
45.48535 9.209441
'''

import requests
import json

url = "http://localhost:8080/otp/transmodel/v3"
headers = {"Content-Type": "application/json"}

query = """
query trip(
  $dateTime: DateTime,
  $from: Location!,
  $to: Location!,
  $modes: Modes,
) {
  trip(dateTime: $dateTime, from: $from, to: $to, modes: $modes) {
    tripPatterns {
      aimedStartTime
      aimedEndTime
      expectedStartTime
      expectedEndTime
      duration
      distance
      generalizedCost
      legs {
        id
        mode
        fromPlace { name quay { id } }
        toPlace { name quay { id } }
        line { publicCode name id presentation { colour } }
        pointsOnLink { points }
      }
    }
  }
}
"""

variables = {
  "from": {
    "coordinates": {
      "latitude": 45.47437,
      "longitude": 9.183323
    }
  },
  "to": {
    "coordinates": {
      "latitude": 45.48535,
      "longitude": 9.209441
    }
  },
  "dateTime": "2025-10-24T18:07:08.511Z",
  "modes": {
    "transportModes": [
      {"transportMode": "bus"},
      {"transportMode": "metro"},
      {"transportMode": "tram"}
    ],
    "accessMode": "foot",
    "egressMode": "foot"
  },
}

# Config wheelchair senza cambiare log o mezzi
wheelchair_payload = {
    "routingDefaults": {
        "wheelchairAccessibility": {
            "trip": {
                "onlyConsiderAccessible": True,
                "unknownCost": 600,
                "inaccessibleCost": 3600
            },
            "stop": {
                "onlyConsiderAccessible": True,
                "unknownCost": 600,
                "inaccessibleCost": 3600
            },
            "elevator": {"onlyConsiderAccessible": True},
            "inaccessibleStreetReluctance": 25,
            "maxSlope": 0.08333,
            "slopeExceededReluctance": 1,
            "stairsReluctance": 25
        }
    },
    "updaters": []
}

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

# Stampa percorso con i tuoi log
if "data" in data and data["data"].get("trip"):
    trip = data["data"]["trip"]
    if trip.get("tripPatterns"):
        pattern = trip["tripPatterns"][0]
        durata_min = int(pattern.get('duration', 0) / 60)
        distanza_km = pattern.get('distance', 0) / 1000
        print(f"\n--- Primo percorso trovato ---")
        print(f"Durata prevista: {durata_min} min")
        print(f"Distanza totale: {distanza_km:.2f} km")
        print(f"Costo generalizzato: {pattern.get('generalizedCost')}\n")

        for i, leg in enumerate(pattern["legs"], 1):
            mode = leg['mode']
            from_name = leg['fromPlace']['name'] if leg['fromPlace']['name'] != "Origin" else "Partenza"
            to_name = leg['toPlace']['name'] if leg['toPlace']['name'] != "Destination" else "Arrivo"
            
            if mode.lower() == 'foot':
                print(f"{i}. 🚶 Cammina da {from_name} a {to_name}")
            else:
                line = leg.get('line')
                line_info = f"{line.get('publicCode')} - {line.get('name')}" if line else "Linea sconosciuta"
                print(f"{i}. {mode.upper()} da {from_name} a {to_name} con {line_info}")
            
            aimed_start = leg.get('aimedStartTime')
            aimed_end = leg.get('aimedEndTime')
            if aimed_start and aimed_end:
                print(f"   Orario previsto: {aimed_start} → {aimed_end}")
            
            print()
    else:
        print("❌ Nessun tripPattern trovato.")
else:
    print("❌ Nessun percorso trovato.")
