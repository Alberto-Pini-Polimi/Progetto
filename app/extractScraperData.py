from enum import Enum
import requests
from pathlib import Path

# qui è dove lo scraper mette i dati ogni ora
DATA_URL = "https://raw.githubusercontent.com/Alberto-Pini-Polimi/ISB_ATM-scraper/main/data/stations.json"


# path to the OTP data folder
OTP_DATA_FOLDER = Path(__file__).resolve().parent.parent / "data/OTP_data"
# path del file gtfs
GTFS_FILE_PATH = OTP_DATA_FOLDER / "Milano-gtfs.zip"


# reference al path dove si trova stops.txt (post estazione)
FILE_STOPS = OTP_DATA_FOLDER / "Milano-gtfs" / "stops.txt"


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
    CITY_TO_PLATFORM = 3 # this is the composit version (1+2 or occasionally 7+6+2). The direct one is 8

    PLATFORM_TO_PLATFORM = 4 # questo è particolare perchè non tiene conto di:
    #  - fermate tipo piola che hanno un collegamento diretto tra i binari dato che la banchina è la stessa
    #  - ritorna True anche se le due specifiche piattaforme che interessano all'utente sono effettivamente collegate in modo accessibile (dato che c'è un altro binario che non è collegato in modo accessibile)
    # TODO: creare una funzione solo per questo platform to platform

    # poi ce ne sono altri molto rari ma cmq presenti:
    OVERPASS = 5 # questo c'è solo in pochissime fermate lontane dal centro di milano
    INTERMEDIO_TO_MEZZANINO = 6
    CITY_TO_INTERMEDIO = 7
    CITY_TO_PLATFORM_DIRECT = 8

    # questo è esattamente uguale a PLATFORM_TO_PLATFORM ma è da intendere per capire se una stazione è completamente accessibile dal mezzanino
    MEZZANINO_TO_ALL_PLATFORMS = 9

class Station:
    """
    Rappresenta una stazione della metropolitana con i suoi dati di accessibilità.
    """
    def __init__(self, raw_data):
        self.raw_data = raw_data
        self.name = raw_data.get("station_name", None)
        self.line = raw_data.get("line", None)
        self.atm_id = raw_data.get("atm_id", None)
        self.directions = raw_data.get("directions", [])

    def printDetails(self):
        """Stampa a schermo i dettagli principali della stazione."""
        print(f"\nSTAZIONE: {self.name} ({self.line})")
        print(f"ID ATM: {self.atm_id}")
        direzioni_nomi = [d.get("direction_name") for d in self.directions]
        print(f"Direzioni disponibili: {', '.join(direzioni_nomi) if direzioni_nomi else 'Nessuna'}")

    def printAccessibility(self):
        """stampo cose principali da sapere per l'accessibilità a quella stazione"""

        # mezzanino accessibile?
        if self.isAccessible(FromTo.CITY_TO_MEZZANINO):
            print("✅ Arrivare/Uscire al/dal mezzanino")
        else:
            print("❌ Arrivare/Uscire al/dal mezzanino")
        
        # per ogni direzione
        for d in self.directions:
            # banchina accessibile dal mezzanino?
            if self.isAccessible(FromTo.MEZZANINO_TO_PLATFORM, d["direction_name"]):
                print(f"✅ Dal/al mezzanino alla/dalla banchina in direzione {d["direction_name"]}")
            else:
                print(f"❌ Dal/al mezzanino alla/dalla banchina in direzione {d["direction_name"]}")
        
        # si può passare da una banchina all'altra
        print(f"{'✅' if self.isAccessible(FromTo.PLATFORM_TO_PLATFORM) else '❌'} Da banchina a banchina")


    def isAccessible(self, fromTo, platformDirection=None):
        """funzione che calcola l'accessibilità di una stazione per uno specifico percorso all'interno della stessa"""
        
        # questi if mappano le richieste di accessibilità composte in richieste elementari
        if fromTo == FromTo.CITY_TO_PLATFORM:
            # platform dev'essere per forza definita:
            if platformDirection == None: 
                return None
            # city-->platform = city-->mezzanino * mezzanino-->platform
            return self.isAccessible(FromTo.CITY_TO_MEZZANINO) and self.isAccessible(FromTo.MEZZANINO_TO_PLATFORM, platformDirection)

        elif fromTo == FromTo.PLATFORM_TO_PLATFORM or fromTo == FromTo.MEZZANINO_TO_ALL_PLATFORMS:
            # questo lo uso anche per capire se una stazione è completamente accessibile (scrivendolo nel stops.txt)
            # qui non c'è bisogno di specificare una piattaforma dato che servono entrambe e sono immagazzinate nell'oggetto di stazione
            # per ogni direzione che contine la stazione
            for direction in self.directions:
                if not self.isAccessible(FromTo.MEZZANINO_TO_PLATFORM, direction["direction_name"]):
                    return False # se trovo anche solo un segmento mezzanino fino alla banchina che non è accessibile allora lo scalo non si può fare
            return True # altrimenti lo scalo si può fare senza problemi

        else: # d'ora in poi saranno solo richieste semplici...

            # quindi devo estrarre le direzioni a prescindere:
            directions = self.directions
            # ovviamente non dev'essere null
            if directions == []:
                return None

            if fromTo == FromTo.CITY_TO_MEZZANINO:
                # prendo una delle due direzioni a caso tanto è indifferente (prendo sempre la prima dato che ce ne sono sempre almeno 2 e quindi almeno 1)
                # e vedo se c'è un segmento che dalla strada esterna va al mezzanino
                segment = next((s for s in directions[0]["segments"] if s["from_to_type"] == FromTo.CITY_TO_MEZZANINO.value), None)
                if not segment:
                    return False
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
            
            elif fromTo == FromTo.OVERPASS:
                # comune a tutta la stazione
                segment = next((s for s in directions[0]["segments"] if s["from_to_type"] == FromTo.OVERPASS.value), None)
                return any(opt["is_working"] for opt in segment["options"]) if segment else False

            elif fromTo == FromTo.INTERMEDIO_TO_MEZZANINO:
                # per stazioni a più livelli (es. Sondrio)
                segment = next((s for s in directions[0]["segments"] if s["from_to_type"] == FromTo.INTERMEDIO_TO_MEZZANINO.value), None)
                return any(opt["is_working"] for opt in segment["options"]) if segment else False

            elif fromTo == FromTo.CITY_TO_INTERMEDIO:
                segment = next((s for s in directions[0]["segments"] if s["from_to_type"] == FromTo.CITY_TO_INTERMEDIO.value), None)
                return any(opt["is_working"] for opt in segment["options"]) if segment else False

            elif fromTo == FromTo.CITY_TO_PLATFORM_DIRECT:
                # diretto strada-banchina: richiede la direzione specifica!!
                if platformDirection == None: 
                    return None # quindi conrollo come al solito
                for direction in directions:
                    if direction["direction_name"] == platformDirection:
                        segment = next((s for s in direction["segments"] if s["from_to_type"] == FromTo.CITY_TO_PLATFORM_DIRECT.value), None)
                        return any(opt["is_working"] for opt in segment["options"]) if segment else False
                return False

        return False

    def definedAsAccessible(self):
        """metodo che stabilisce se sul file stops.txt una stazione è definita come accessibile o meno"""

        # questa è la condizione che può facilmente essere modificata
        # in questo caso faccio una valutazione conservativa controllando l'accessibilità da e per tutte le banchine
        if self.isAccessible(FromTo.CITY_TO_MEZZANINO) and self.isAccessible(FromTo.MEZZANINO_TO_ALL_PLATFORMS):
            return True
        # se anche solo una banchina non è accessibile allora la valutazione conservativa la da come stazione non accessibile
        return False

