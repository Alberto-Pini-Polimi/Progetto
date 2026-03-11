import os
import zipfile
import csv
from collections import defaultdict

"""
inserisci il nome della fermata da cercare nella
variabile 'target_name', e lancia lo script.
Lo script stamperà le informazioni sulla fermata
se vuoi indagare dei path generati da OTP

il valore tra parentesi indica il tipo di mezzo:
0 - Tram, Streetcar, Light rail
1 - Metropolitana / Metro
2 - Ferrovia / Heavy rail
3 - Autobus / Bus
"""

# Nome fermata da cercare
target_name = "caiazzo"
#target_name = "Lanza M2"

# Percorsi
base_path = os.path.abspath(os.path.join("v2", "otp_data"))
gtfs_file = os.path.join(base_path, "Milano-gtfs.zip")

# Dizionari
stops = {}
stop_name_to_ids = defaultdict(list)
trips = {}
stop_times = defaultdict(list)
routes = {}

# Apri GTFS
with zipfile.ZipFile(gtfs_file, 'r') as z:
    # stops.txt
    with z.open('stops.txt') as f:
        reader = csv.DictReader(f.read().decode('utf-8').splitlines())
        for row in reader:
            stops[row['stop_id']] = row
            stop_name_to_ids[row['stop_name'].upper()].append(row['stop_id'])

    # stop_times.txt
    with z.open('stop_times.txt') as f:
        reader = csv.DictReader(f.read().decode('utf-8').splitlines())
        for row in reader:
            stop_times[row['stop_id']].append(row['trip_id'])

    # trips.txt
    with z.open('trips.txt') as f:
        reader = csv.DictReader(f.read().decode('utf-8').splitlines())
        for row in reader:
            trips[row['trip_id']] = row['route_id']

    # routes.txt
    with z.open('routes.txt') as f:
        reader = csv.DictReader(f.read().decode('utf-8').splitlines())
        for row in reader:
            routes[row['route_id']] = row

# Trova gli stop_id per il nome target
ids = stop_name_to_ids[target_name.upper()]
if not ids:
    print(f"Nessuna fermata trovata con il nome '{target_name}'")
else:
    for stop_id in ids:
        stop = stops[stop_id]
        print(f"\nFermata: {stop['stop_name']} ({stop_id})")
        print(f"Lat/Lon: {stop['stop_lat']}, {stop['stop_lon']}")
        accessible = stop['wheelchair_boarding'] == '1'
        print(f"Accessibile: {'Sì' if accessible else 'No'}")

        # Trova tutti i trip_id che passano da questa fermata
        trip_ids = stop_times.get(stop_id, [])
        line_ids = set()
        for t in trip_ids:
            route_id = trips.get(t)
            if route_id:
                line_ids.add(route_id)

        # Stampa i mezzi/linee
        print("Linee/mezzi che passano da qui:")
        for rid in line_ids:
            route = routes.get(rid, {})
            print(f" - {route.get('route_short_name', rid)} ({route.get('route_type', 'sconosciuto')})")
