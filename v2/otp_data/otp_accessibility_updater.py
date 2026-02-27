#script che updeita stops.txt di milano-gtfs ....
#inizio a fare una bozza:

from enum import Enum
import requests

# qui è dove lo scraper mette i dati ogni ora
DATA_URL = "https://raw.githubusercontent.com/Alberto-Pini-Polimi/ISB_ATM-scraper/main/data/stations.json"



# funzione per estrarre i dati ed averli come maneggevole oggetto python
def getData(URL):
    # provo a richiedere 
    try:
        response = requests.get(URL)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error: {e}")
        print(f"response: {response.text}")
        return None
    # ritorno quindi i dati come oggetto python
    return data



# creo un enum per definire tutti i possibili percorsi che un utente può fare in una stazione
class FromTo(Enum):
    CITY_TO_MEZZANINO = 1
    MEZZANINO_TO_PLATFORM = 2
    # non c'è bisogno di:
    #  - differenziare tra molteplici linee di una stazione (anche se una stazione ha 2 linee nei dati estratti dallo scraper ci sono 2 stazioni indipendenti con lo stesso nome)
    #  - creare dei valori dell'enum che definiscono la direzione opposta (CITY_TO_MEZZANINO da la stessa info di MEZZANINO_TO_CITY). Assumo tutti i servizi siano bidirezionali
    # poi ci sono quelle composte solo per la comodità dell'utente che utilizza la funzione isAccessible
    CITY_TO_PLATFORM = 3

    PLATFORM_TO_PLATFORM = 4 # questo è particolare perchè non tiene conto di:
    #  - fermate tipo piola che hanno un collegamento diretto tra i binari dato che la banchina è la stessa
    #  - ritorna True anche se le due specifiche piattaforme che interessano all'utente sono effettivamente collegate in modo accessibile (dato che c'è un altro binario che non è collegato in modo accessibile)
    # TODO: creare una funzione solo per questo platform to platform

# funzione che calcola l'accessibilità di una stazione per uno specifico percorso all'interno della stessa
def isAccessible(station, fromTo, platformDirection=None):
    
    # questi if mappano le richieste di accessibilità composte in richieste elementari
    if fromTo == FromTo.CITY_TO_PLATFORM:
        # platform dev'essere per forza definita:
        if platformDirection == None: 
            return None
        # city-->platform = city-->mezzanino * mezzanino-->platform
        return isAccessible(station, FromTo.CITY_TO_MEZZANINO) and isAccessible(station, FromTo.MEZZANINO_TO_PLATFORM, platformDirection)

    elif fromTo == FromTo.PLATFORM_TO_PLATFORM:
        # qui non c'è bisogno di specificare una piattaforma dato che servono entrambe e sono immagazzinate nell'oggetto di stazione
        # per ogni direzione che contine la stazione
        for direction in station["directions"]:
            if not isAccessible(station, FromTo.MEZZANINO_TO_PLATFORM, direction["direction_name"]):
                return False # se trovo anche solo un segmento mezzanino fino alla banchina che non è accessibile allora lo scalo non si può fare
        return True # altrimenti lo scalo si può fare senza problemi

    else: # d'ora in poi saranno solo richieste semplici...

        # quindi devo estrarre le direzioni a prescindere:
        directions = station["directions"]
        # ovviamente non dev'essere null
        if directions == None:
            return None

        if fromTo == FromTo.CITY_TO_MEZZANINO:
            # prendo una delle due direzioni a caso tanto è indifferente (prendo sempre la prima dato che ce ne sono sempre almeno 2 e quindi almeno 1)
            # e vedo se c'è un segmento che dalla strada esterna va al mezzanino
            segment = next((s for s in directions[0]["segments"] if s["from_to_type"] == FromTo.CITY_TO_MEZZANINO.value), None)
            # ora devo controllare che ci sia almeno una opzione funzionante
            for option in segment["options"]:
                if option["is_working"]: # se c'è almeno un'opzione funzionante
                    return True # allora ritorno true
            return False # altrimenti false

        elif fromTo == FromTo.MEZZANINO_TO_PLATFORM:
            # come prima la piattaforma dev'essere definita
            if platformDirection == None:
                return None
            # ora devo controllare che la direzione che mi viene data corrisponda ad una direzione esistente
            for direction in directions:
                if direction["direction_name"] == platformDirection:
                    # a questo punto prendo quella direzione in questione e faccio più o meno le stesse cose di CITY_TO_MEZZANINO
                    for segment in direction["segments"]:
                        if segment["from_to_type"] == FromTo.MEZZANINO_TO_PLATFORM.value:
                            # ora devo controllare che ci sia almeno una opzione funzionante
                            for option in segment["options"]:
                                if option["is_working"]: # se c'è almeno un'opzione funzionante
                                    return True # allora ritorno true
                            return False # altrimenti false
            return False
        
        # TODO: aggiungere anche gli altri casi!!




if __name__ == "__main__":

    # prendo i dati dallo scraper:
    data = getData(DATA_URL)

    # per ora mi limito a prendere una singola stazione e controllo l'accessibilità al mezzanino ed a tutte le direzioni
    stazione = next((s for s in data if s["station_name"] == "Piola"), None)

    print("arrivare al mezzanino: " + isAccessible(stazione, FromTo.CITY_TO_MEZZANINO))
    print("dal mezzanino in direzione A: " + isAccessible(stazione, FromTo.MEZZANINO_TO_PLATFORM, "Assago Milanofiori Forum/Abbiategrasso"))
    print("dal mezzanino in direzione A: " + isAccessible(stazione, FromTo.MEZZANINO_TO_PLATFORM, "Cologno Nord/Gessate"))
    print(isAccessible(stazione, FromTo.PLATFORM_TO_PLATFORM))













    
    # decido la stazione su cui analizzare l'accessibilità
    # print("stazioni:")
    # for station in data:
    #     print(f"{station.get('station_name')} - {station.get('line')}")


        # per ogni stazione devo vedere le direzioni per mapparle alla riga del file stops.txt



    # poi in realtà lo dovrò fare con tutte per riscrivere i dati estratti all'interno di stops.txt