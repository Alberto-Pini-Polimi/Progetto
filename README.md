# Progetto Ingegneria Informatica (5 cfu)

Questo repository contiene un progetto universitario per il corso di Ingegneria Informatica. Il progetto si concentra sulla creazione di un sistema di routing che considera l'accessibilità per utenti con diverse problematiche.

## Struttura del Progetto

Il progetto è organizzato in due versioni principali:

-   `v1/`: La prima versione del progetto. Si tratta di una versione preliminare e meno completa.
-   `v2/`: La versione più recente, completa e consigliata per l'utilizzo.

Le differenze sostanziali tra le due versioni sono documentate nel file `v2/descrizione.md`.

## Versione 2 (v2)

La versione 2 del progetto implementa un programma di routing avanzato, con un focus sull'accessibilità per utenti con disabilità. Utilizza dati geospaziali provenienti da OpenStreetMap (OSM) e dati personalizzati per calcolare percorsi ottimali.

### Dati

La cartella `v2/data/` contiene i dati utilizzati dal programma:

-   `fromOSM.json`: Un dataset di punti di interesse (POI) estratti da OpenStreetMap, pre-processati per includere informazioni sull'accessibilità. Contiene elementi come:
    -   **Ascensori** (`highway: "elevator"`): Facilitatori per superare dislivelli.
    -   **Attraversamenti Pedonali** (`highway: "crossing"`): Con dettagli su ausili per non vedenti (segnali acustici, pavimentazione tattile).
    -   **Bagni Accessibili** (`amenity: "toilets"`): Con indicazioni sull'accessibilità per sedie a rotelle.
    -   **Bordi di Marciapiede** (`barrier: "kerb"`): Classificati come barriere o facilitatori a seconda dell'altezza.
    - **Fontanelle/Panchine/bar** come infrastrutture

-   `DATA1.json` e `DATA2.json`: File di dati mock utilizzati per testare il sistema con dati generati da utenti fittizi (es. "Pippo", "Pluto"). Questi file definiscono barriere, facilitatori e infrastrutture con coordinate specifiche.

### Esecuzione

Prima dell'esecuzione, assicurarsi di aver installato tutte le dipendenze necessarie. È possibile installarle tramite `pip` con il seguente comando:

```bash
pip install requests polyline folium shapely pyproj
```

Le principali librerie utilizzate dal programma sono:

- `json`
- `requests`
- `polyline`
- `folium`
- `os`
- `shapely`
- `pyproj`
- `enum`
- `webbrowser`
- `datetime`
- `random`

Alcune di queste (come `json`, `os`, `enum`, `webbrowser`, `datetime`, `random`) dovrebbero già far parte della libreria standard di Python e non richiedono quindi un'installazione aggiuntiva.

Per eseguire il programma di routing, è necessario posizionarsi nella directory `v2/` e lanciare lo script Python.

```bash
cd v2
python routingProgram.py
```

#### Parametri di Esempio

All'interno dello script `routingProgram.py`, sono pre-impostati i seguenti parametri per una simulazione di percorso a Milano per un utente con disabilità motoria:

-   **Nome Utente:** `Utente`
-   **Tipologia di problematica:** `ProblemiMobilità.MOTORIA`
-   **Coordinate di Partenza:** `[45.47686209277475, 9.122741092267772]` (Stadio San Siro)
-   **Coordinate di Arrivo:** `[45.45447977998694, 9.21002802045689]` (Piazzale Libia)

Questi parametri possono essere modificati direttamente nel codice per testare scenari differenti.

### Output

L'esecuzione dello script produrrà causerà l'apertura automatica di 2 o 3 pagine html direttamente sul browser. Queste contengono la mappa di OSM, il percorso trovato e tutte le barriere, facilitatori ed infrastrutture nei rispettivi buffer.

Se lo script non apre automaticamente niente allora basterà, a meno di errori, andare nella cartella `v2/` e aprire manualmente i file `mappa_*.html`

*(Nota: Questa sezione può essere aggiornata con un esempio concreto dell'output generato dal programma.)*