'''
moscova
"latitude": 45.481685414153816,
"longitude": 9.182068687522559

bovisa
"latitude": 45.50217816956206,
"longitude": 9.16154437030653

centrale circa
"latitude": 45.484130,
"longitude": 9.196586

'''

#i 4 innserimenti di wheel han creato bug prima andava

import requests
import json

url = "http://localhost:8080/otp/transmodel/v3"
headers = {"Content-Type": "application/json"}

# Query GraphQL per la versione 2.8.1
query = """
query trip(
  $dateTime: DateTime,
  $from: Location!,
  $to: Location!,
  $modes: Modes,
) {
  trip(dateTime: $dateTime, from: $from, to: $to, modes: $modes) {
    previousPageCursor
    nextPageCursor
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

# Variabili da passare alla query
variables = {
  "from": {
    "coordinates": {
      "latitude": 45.481685414153816,
      "longitude": 9.182068687522559
    }
  },
  "to": {
    "coordinates": {
      "latitude": 45.484130,
      "longitude": 9.196586
    }
  },
  "dateTime": "2025-10-24T18:07:08.511Z",
  "modes": {
    "transportModes": [
      {
        "transportMode": "bus"
      },
      {
        "transportMode": "metro"
      },
      {
        "transportMode": "tram"
      }
    ],
    "accessMode": "foot",
    "egressMode": "foot"
  },
}

payload = {"query": query, "variables": variables}

# Esecuzione della richiesta POST
response = requests.post(url, json=payload, headers=headers)

print("Status:", response.status_code)

try:
    data = response.json()
    print(json.dumps(data, indent=2))  #principalmente per debug
except json.JSONDecodeError:
    print("❌ Risposta non in formato JSON:", response.text)

# Estrazione dei legs del primo tripPattern con più informazioni
if "data" in data and data["data"].get("trip"):
    trip = data["data"]["trip"]
    if trip.get("tripPatterns"):
        pattern = trip["tripPatterns"][0]
        # Intestazione percorso
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
            
            # Se è camminata, scrivi “Cammina da X a Y”
            if mode.lower() == 'foot':
                print(f"{i}. 🚶 Cammina da {from_name} a {to_name}")
            else:
                line = leg.get('line')
                line_info = f"{line.get('publicCode')} - {line.get('name')}" if line else "Linea sconosciuta"
                print(f"{i}. {mode.upper()} da {from_name} a {to_name} con {line_info}")
            
            # Orari, se disponibili
            aimed_start = leg.get('aimedStartTime')
            aimed_end = leg.get('aimedEndTime')
            if aimed_start and aimed_end:
                print(f"   Orario previsto: {aimed_start} → {aimed_end}")
            
            print()  # Riga vuota tra i legs
    else:
        print("❌ Nessun tripPattern trovato.")
else:
    print("❌ Nessun percorso trovato.")
