è arrivata mezzanotte:

il server OTP deve essere riavviato col `graph.obj` aggiornato:

### 1. spengo il servizio

``` bash
docker compose down
```

### 2. eseguo `dailyGTFSzipUpdater.py`

eseguo lo script che usa i dati dello scraper (dell'altra repo) per:
- modificare il file Milano-gtfs.zip per con i nuovi dati
- creare/modificare la baseline delle stazioni accessibili (dati inseriti nell'`graph.obj`)

``` bash
python3 app/dailyGTFSzipUpdater.py
```

### 3. elimino `graph.obj` vecchio

prima di ribuildare tutto devo eliminare `graph.obj` dato che altrimenti non usa i nuovi dati aggiornati in Milano-gtfs.zip

``` bash
rm data/OTP_data/graph.obj
```

### 4. ribuildo OTP

Faccio una build del server OTP che mi crea il file `graph.obj` partendo dai dati appena modificati (Milano-gtfs.zip) e la mappa OSM (MyMilan.osm.pbf)

``` bash
docker compose run --rm otp-builder
```

### 5. faccio partire il container (OTP ribuildato + Python)

Una volta creato con la build il container parte automaticamente e prende come input proprio il nuovo file `graph.obj`

``` bash
docker compose up
```

Attenzione! per questo comando nel `docker-compose.yalm` NON dev'essere commentata questa linea `command: ["--build", "--save"]`

### 5. Una volta ogni ora

A partire dall'ora successiva alla build bisogna lanciare hourlyMonitor.py

``` bash
python3 app/hourlyMonitor.py
```

Questo script usa le informazioni dello scraper estratte idealmente pochi minuti prima e le confronta con la baseline (`daily_accessibility_baseline.json`) per creare `inaccessible_stations_till_last_GTFSzip_file_update.txt`.

Questo file viene poi usato da `ORS_routing.py` per dare avvisi sul fatto che stazioni consigliate non siano più accessibili.