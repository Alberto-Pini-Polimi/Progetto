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
    PLATFORM_TO_PLATFORM = 4

# funzione che calcola l'accessibilità di una stazione per uno specifico percorso all'interno della stessa
def isAccessible(station, fromTo, platformDirection=None):
    
    # questi if mappano le richieste di accessibilità composte in richieste elementari
    if fromTo == FromTo.CITY_TO_PLATFORM:
        # platform dev'essere per forza definita:
        if platformDirection == None: 
            return None
        # city-->platform = city-->mezzanino * mezzanino-->platform
        return isAccessible(station, FromTo.CITY_TO_MEZZANINO) * isAccessible(station, FromTo.MEZZANINO_TO_PLATFORM, platformDirection)

    elif fromTo == FromTo.PLATFORM_TO_PLATFORM:
        # qui non c'è bisogno di specificare una piattaforma dato che servono entrambe e sono immagazzinate nell'oggetto di stazione
        # TODO: completare!!
        return isAccessible(station, FromTo.MEZZANINO_TO_PLATFORM, station.primaDirezione) * isAccessible(station, FromTo.MEZZANINO_TO_PLATFORM, station.secondaDirezione)

    # d'ora in poi saranno solo richieste semplici...
    elif fromTo == FromTo.CITY_TO_MEZZANINO:
        # semplicemente controllo l'oggetto station
        return #station. ....

    elif fromTo == FromTo.MEZZANINO_TO_PLATFORM:
        # come prima la piattaforma dev'essere definita
        if platformDirection == None:
            return None
        # ora devo controllare l'oggetto station
        return #station. ...




if __name__ == "__main__":

    # prendo i dati dallo scraper:
    data = getData(DATA_URL)
    
    # decido la stazione su cui analizzare l'accessibilità
    print("stazioni:")
    for station in data:
        print(f"{station.get('station_name')} - {station.get('line')}")

    # poi in realtà lo dovrò fare con tutte per riscrivere i dati estratti all'interno di stops.txt