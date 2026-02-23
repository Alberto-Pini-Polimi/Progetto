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

cadorna m1 m2 (accessibile)
45.46765 9.175563

sant agostino m2 (accessibile)
45.45876 9.169992

cologno sud m2
45.51992 9.274548

tra moscova e lanza m2
45.47437 9.183323

caiazzo m2
45.48535 9.209441
'''
###CONCLUSIONI IMPORTANTI:
# aumentare e diminuire i costi blocca solo la fermata suggerita
# c è da controllare se non ne analizza altre per colpa di un max egress o simili
# altenrativamente si puo lavorare con calcoli di percorsi partendo da punti spostati

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
  $wheelchair: Boolean,
  $searchWindow: Int,
  $arriveBy: Boolean
) {
  trip(dateTime: $dateTime, from: $from, to: $to, modes: $modes, wheelchairAccessible: $wheelchair, searchWindow: $searchWindow, arriveBy: $arriveBy, debugItineraryFilter:true) {
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
        id
        generalizedCost
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
      "latitude": 45.46765,
      "longitude": 9.175563
    }
  },
  "to": {
    "coordinates": {
      "latitude": 45.45876,
      "longitude": 9.169992
    }
  },
  "dateTime": "2026-04-01T16:07:08.511Z",
  "modes": {
    "transportModes": [
      {"transportMode": "bus"},
      {"transportMode": "metro"},
      {"transportMode": "tram"}
    ],
    "accessMode": "foot",
    "egressMode": "foot",
    "directMode": "foot" #permette di avere anche i percorsi a piedi completi
  },
  "wheelchair": True, #permette di usare i params wheelchair
  "arriveBy": False,
  "searchWindow": 360  # minuti: 6 ore

}

payload = {
    "query": query,
    "variables": variables
}

response = requests.post(url, json=payload, headers=headers)
print("Status:", response.status_code)

try:
    data = response.json()
    #print(json.dumps(data, indent=2))  # per debug
except json.JSONDecodeError:
    print("❌ Risposta non in formato JSON:", response.text)

# STAMPA PATH
if "data" in data and data["data"].get("trip"):
    trip = data["data"]["trip"]
    if trip.get("tripPatterns"):
        pattern = trip["tripPatterns"][0] #DEBUG solo il primo percorso?
        durata_min = int(pattern.get('duration', 0) / 60)
        distanza_km = pattern.get('distance', 0) / 1000
        print(f"\n--- Primo percorso trovato ---")
        print(f"Durata prevista: {durata_min} min")
        print(f"Distanza totale: {distanza_km:.2f} km")
        print(f"Costo generalizzato: {pattern.get('generalizedCost')/60:.1f}m\n")
        notices = pattern.get("systemNotices") or []
        if notices:
            print("Notices (itinerary filter/debug):")
            for n in notices:
                print(f"  - [{n.get('tag')}] {n.get('text')}")
            print()

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
    print(json.dumps(data, indent=2))

