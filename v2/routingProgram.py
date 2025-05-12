import json
import requests
import polyline
import folium
import os
from shapely import geometry
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from pyproj import Transformer
from enum import Enum
import webbrowser
from datetime import datetime

# input principali da parte dell'utente
ORS_API_KEY = open("API_KEY.txt", 'r').read().strip()

COORDINATE_INIZIO = [9.17988, 45.47006]  # [lon, lat] castello sforzesco
#COORDINATE_FINE = [9.18956, 45.46424]    # [lon, lat] duomo
#COORDINATE_FINE = [9.203530, 45.485146] # centrale
COORDINATE_FINE = [9.226897, 45.478111] # piazza leo

# COORDINATE_INIZIO = [46.538795718940136, 12.124246397899869] 
# COORDINATE_FINE = [46.53569202884132, 12.1411393835463]

# COORDINATE_INIZIO = [round(COORDINATE_INIZIO[1], 6), round(COORDINATE_INIZIO[0], 6)]
# COORDINATE_FINE = [round(COORDINATE_FINE[1], 6), round(COORDINATE_FINE[0], 6)]

# L'istanza dell'utente è definita sotto nel main

# definisco un'area di distanza attorno ai percorsi
BUFFER_FACILITATORI_IN_METRI = 10
BUFFER_BARRIERE_IN_METRI = 3
BUFFER_INFRASTRUTTURE_IN_METRI = 50









# Definisci i sistemi di coordinate e le funzioni per la trasformazione tra i sistemi
wgs84 = 'EPSG:4326' # Sistema di coordinate geografiche (lat/lon)
utm_zone = 'EPSG:32632' # Proiezione UTM adatta (Milano nella zona UTM 32N)
project_to_utm = Transformer.from_crs(wgs84, utm_zone, always_xy=True).transform
project_to_wgs = Transformer.from_crs(utm_zone, wgs84, always_xy=True).transform

def inverti_coordinate(coord):
    return coord[1], coord[0]








class ProblemiMobilità(Enum):

    # Disabilità Fisica
    MOTORIA = "Motoria"

    # Disabilità Sensoriali
    VISIVA = "Visiva"
    UDITIVA = "Uditiva"

    # Altre disabilità
    MULTIPLE = "Multiple"
    ALTRE = "Altre"

    def __str__(self):
        return self.value
    
    def to_json(self):
        """Metodo per serializzare l'Enum in JSON."""
        return self.value

class TipoElemento(Enum):
    # Barriera
    BARRIERA = "Barriera"

    # Facilitatore
    FACILITATORE = "Facilitatore"

    # Infrastruttura
    INFRASTRUTTURA = "Infrastruttura"

    def __str__(self):
        return self.value
    
    def to_json(self):
        """Metodo per serializzare l'Enum in JSON."""
        return self.value


class Utente():

    def __init__(self, nickname, problema_di_mobilità):
        
        self.nickname = nickname # dev'essere univoco
        self.problema = problema_di_mobilità
        self.preferenze = None # qui si esprimono le preferenze dell'utente

    def interessa(self, elemento):
        """
            Metodo per capire se un elemento è utile per l'utente in questione
        """

        barreira_per = elemento.get("barreiraPer", [])
        facilitatore_per = elemento.get("facilitatorePer", [])
        infrastruttura_per = elemento.get("infrastrutturaPer", [])

        if str(self.problema) in barreira_per:
            return True
        if str(self.problema) in facilitatore_per:
            return True
        if str(self.problema) in infrastruttura_per:
            return True
        
        return False




class ElementoOSM:
    """Classe base per qualsiasi elemento proveniente da OpenStreetMap"""
    
    def __init__(self, elemento_del_DB):
        self.id = elemento_del_DB['id']
        self.coordinate_centroide = elemento_del_DB["coordinateCentroide"]
        self.autore = elemento_del_DB["autore"]
        self.ranking = elemento_del_DB["ranking"]
        self.nome = elemento_del_DB["nome"]
        self.descrizione = elemento_del_DB["descrizione"]
        self.barreira_per = elemento_del_DB["barreiraPer"] 
        self.facilitatore_per = elemento_del_DB["facilitatorePer"] 
        self.infrastruttura_per = elemento_del_DB["infrastrutturaPer"] 

    def cambiaRanking(self, quantità):

        self.ranking += quantità

        # saturo
        if self.ranking > 100:
            self.ranking = 100
        elif self.ranking < 0:
            self.ranking = 0

    def per(self, utente):

        if utente.problema.value in self.barreira_per:
            return TipoElemento.BARRIERA
        elif utente.problema.value in self.facilitatore_per:
            return TipoElemento.FACILITATORE
        elif utente.problema.value in self.infrastruttura_per:
            return TipoElemento.INFRASTRUTTURA
        else:
            return None















class Percorso():

    """
        input per l'inizializzazione:
        percorso: {
            "summary": {
                "distance": 100,
                "duration": 100
            },
            "segments" <-- ignoro totalmente
            "bbox": [coordinate],
            "geometry": encoded_data_per_la_rappresentazione_del_percorso_come_un_poligono,
            "waypoints" <-- ignoro totalmente
        }
    
    """
    
    def __init__(self, percorso):

        # prendo i dati del summary
        self.distanza = percorso["summary"]["distance"]
        self.durata = percorso["summary"]["duration"]
        # prendo il bbox (bounding box per acere un rang in cui cercare)
        self.bbox = percorso["bbox"] # lo userò per cercare barriere e facilitatori nel DB
        # faccio il decoding della polyline (encodata in geometry)
        self.coordinate_della_polyline = polyline.decode(percorso["geometry"])
        
        # Inverti le coordinate per shapely (lon, lat)
        coordinate_shapely = [inverti_coordinate(coord) for coord in self.coordinate_della_polyline]
        self.percorso_geo = LineString(coordinate_shapely)
        # Proietta la polyline in UTM
        percorso_utm_coords = [project_to_utm(lon, lat) for lat, lon in self.coordinate_della_polyline]
        self.percorso_utm = LineString(percorso_utm_coords)
        
        # Inizializza attributi
        self.barriere_trovate = []
        self.facilitatori_trovati = []
        self.infrastrutture_trovate = []
        self.barriere_da_evitare = []
        self.facilitatori_da_includere = []
        self.infrastrutture_da_includere = []
        
        # Crea il buffer di default
        self.creaBufferBarriere()
        self.creaBufferFacilitatori()
        self.creaBufferInfrastrutture()

    def creaBufferFacilitatori(self):
        """Crea un buffer attorno al percorso in UTM per i facilitatori"""
        self.bufferFacilitatori_utm = self.percorso_utm.buffer(BUFFER_FACILITATORI_IN_METRI)
        # Riproietta il buffer in WGS84 per la visualizzazione e il controllo dei facilitatori
        area_limitrofa_al_percorso_geo_coords = [project_to_wgs(x, y) for x, y in self.bufferFacilitatori_utm.exterior.coords]
        # Crea un poligono per i facilitatori
        self.bufferFacilitatori_geo = Polygon(area_limitrofa_al_percorso_geo_coords)

    def creaBufferBarriere(self):
        """Crea un buffer attorno al percorso in UTM per le barriere"""
        self.bufferBarriere_utm = self.percorso_utm.buffer(BUFFER_BARRIERE_IN_METRI)
        # Riproietta il buffer in WGS84 per la visualizzazione e il controllo delle barriere
        area_limitrofa_al_percorso_geo_coords = [project_to_wgs(x, y) for x, y in self.bufferBarriere_utm.exterior.coords]
        # Crea un poligono per le barriere
        self.bufferBarriere_geo = Polygon(area_limitrofa_al_percorso_geo_coords)

    def creaBufferInfrastrutture(self):
        """Crea un buffer attorno al percorso in UTM per le infrastrutture"""
        self.bufferInfrastrutture_utm = self.percorso_utm.buffer(BUFFER_INFRASTRUTTURE_IN_METRI)
        # Riproietta il buffer in WGS84 per la visualizzazione e il controllo delle infrastrutture
        area_limitrofa_al_percorso_geo_coords = [project_to_wgs(x, y) for x, y in self.bufferInfrastrutture_utm.exterior.coords]
        # Crea un poligono per le infrastrutture
        self.bufferInfrastrutture_geo = Polygon(area_limitrofa_al_percorso_geo_coords)

    def isNelBuffer(self, elemento_osm, tipo_buffer):
        """Verifica se un punto è all'interno del buffer"""

        punto_geo = Point([elemento_osm.coordinate_centroide.get("longitudine"), elemento_osm.coordinate_centroide.get("latitudine")])
            
        # Proietta il punto barriera in UTM
        punto_utm = project_to_utm(punto_geo.x, punto_geo.y)
        punto_utm_shapely = Point(punto_utm)
        # Verifica il contenimento nel buffer UTM e ritorna vero o falso
        if tipo_buffer == "barriere":
            return self.bufferBarriere_utm.contains(punto_utm_shapely)
        elif tipo_buffer == "facilitatori":
            return self.bufferFacilitatori_utm.contains(punto_utm_shapely)
        elif tipo_buffer == "infrastrutture":
            return self.bufferInfrastrutture_utm.contains(punto_utm_shapely)
        else:
            raise ValueError("Tipo di buffer non valido. Deve essere 'barriere' o 'facilitatori'.")

    def trovaElementiSulPercorso(self, elementi_caricati, utente):
        """
        Trova barriere e facilitatori sul percorso in base agli elementi caricati e all'utente
        """
        self.barriere_trovate = []
        self.facilitatori_trovati = []
        self.infrastrutture_trovate = []

        for elemento in elementi_caricati:
            
            # Verifica cosa l'elemento è per l'utente e se è nel rispettivo buffer

            if elemento.per(utente) == TipoElemento.FACILITATORE and self.isNelBuffer(elemento, "facilitatori"):
                self.facilitatori_trovati.append(elemento)
            
            elif elemento.per(utente) == TipoElemento.BARRIERA and self.isNelBuffer(elemento, "barriere"):
                self.barriere_trovate.append(elemento)
            
            elif elemento.per(utente) == TipoElemento.INFRASTRUTTURA and self.isNelBuffer(elemento, "infrastrutture"):
                self.infrastrutture_trovate.append(elemento)
            
            else:
                continue
        
        return self.barriere_trovate, self.facilitatori_trovati, self.infrastrutture_trovate



# parte grafica

class MappaFolium:
    """Classe per la gestione della visualizzazione su mappa Folium"""
    
    def __init__(self, centro=None, zoom_start=15):
        """
        Inizializza una nuova mappa Folium
        
        Args:
            centro: tuple (lat, lon) del centro della mappa
            zoom_start: livello di zoom iniziale
        """
        if centro:
            self.mappa = folium.Map(location=centro, zoom_start=zoom_start)
        else:
            self.mappa = folium.Map(location=[45.4642, 9.1900], zoom_start=12)  # Default: Milano
    
    def aggiungiPolyline(self, coordinate, colore="blue", peso=5, opacità=0.7, tooltip="Percorso"):
        """Aggiunge una polyline alla mappa"""
        folium.PolyLine(
            locations=coordinate,
            color=colore,
            weight=peso,
            opacity=opacità,
            tooltip=tooltip
        ).add_to(self.mappa)
    
    def aggiungiPoligono(self, coordinate, colore="yellow", fill=True, fill_opacity=0.2, tooltip=None):
        """Aggiunge un poligono alla mappa"""
        folium.Polygon(
            locations=coordinate,
            color=colore,
            fill=fill,
            fill_opacity=fill_opacity,
            tooltip=tooltip
        ).add_to(self.mappa)
    
    def aggiungiMarker(self, punto, colore="blue", icona=None, tooltip=None, popup=None):
        """Aggiunge un marker alla mappa"""
        icona_folium = folium.Icon(color=colore, icon=icona if icona else 'info-sign', prefix='glyphicon')
        folium.Marker(
            location=punto,
            icon=icona_folium,
            tooltip=tooltip,
            popup=popup
        ).add_to(self.mappa)
    
    def aggiungiDettagli(self, durata, distanza, numero_barriere_trovate):
        """Aggiunge un pannello con i dettagli del percorso alla mappa"""
        html_content = f"""
            <div id="info-panel" style="position: fixed;
                        top: 10px;
                        right: 10px;
                        z-index:9999;
                        background-color:white;
                        opacity:0.9;
                        border:2px solid grey;
                        padding:10px;">
                <h3>Info sul Percorso</h3>
                distanza: {distanza:.2f} m<br>
                durata: {self.formatta_durata(durata)}<br>
                # barriere trovate: {numero_barriere_trovate}
            </div>
        """
        self.mappa.get_root().html.add_child(folium.Element(html_content))

    def formatta_durata(self, secondi):
        """Formatta la durata in ore, minuti e secondi"""
        ore = int(secondi // 3600)
        minuti = int((secondi % 3600) // 60)
        secondi_rimanenti = int(secondi % 60)
        return f"{ore} h : {minuti} min : {secondi_rimanenti} sec"
    
    def aggiungiElemento(self, elemento, colore="red", icona="warning-sign"):
        """Aggiunge un ElementoOSM (Barriera o Facilitatore) alla mappa"""
        
        punto = (elemento.coordinate_centroide.get("latitudine"), elemento.coordinate_centroide.get("longitudine"))
        
        popup = folium.Popup(
            f"""
                <h3>{elemento.nome}</h3>
                <p>{elemento.descrizione}<\p>
                <br>
                ID: {elemento.id}
            """,
            max_width=300
        )
        
        self.aggiungiMarker(
            punto=punto,
            colore=colore,
            icona=icona,
            tooltip=elemento.nome,
            popup=popup
        )
    
    def salvaMappa(self, nome_file):
        """Salva la mappa in un file HTML"""
        try:
            self.mappa.save(nome_file)
            return True
        except Exception as e:
            print(f"Errore nel salvataggio della mappa: {e}")
            return False

def creaEDisegnaMappa(percorso, barriere, facilitatori, infrastrutture, mappa_file):
     # Crea la mappa
    centro_percorso = percorso.percorso_geo.centroid
    mappa = MappaFolium(centro=(centro_percorso.y, centro_percorso.x))
    
    # Aggiungi il percorso
    mappa.aggiungiPolyline(percorso.coordinate_della_polyline)
    
    # Aggiungi il buffer barriere
    # mappa.aggiungiPoligono(
    #     [(y, x) for x, y in percorso.bufferBarriere_geo.exterior.coords],
    #     tooltip='Area di ricerca barriere',
    #     colore='orange'
    # )
    # Aggiungi il buffer facilitatori
    mappa.aggiungiPoligono(
        [(y, x) for x, y in percorso.bufferFacilitatori_geo.exterior.coords],
        tooltip='Area di ricerca facilitatori',
        colore='lightgreen'
    )
    # Aggiungi il buffer infrastrutture
    mappa.aggiungiPoligono(
        [(y, x) for x, y in percorso.bufferInfrastrutture_geo.exterior.coords],
        tooltip='Area di ricerca infrastrutture',
        colore='lightblue'
    )

    # Aggiungi i infrastrutture
    for infrastruttura in infrastrutture:
        mappa.aggiungiElemento(infrastruttura, colore="blue", icona="plus-sign")
    # Aggiungi i facilitatori
    for facilitatore in facilitatori:
        mappa.aggiungiElemento(facilitatore, colore="green", icona="ok-sign")
    # Aggiungi le barriere
    for barriera in barriere:
        mappa.aggiungiElemento(barriera, colore="red", icona="warning-sign")
    
    # aggiungi durata e distanza
    mappa.aggiungiDettagli(percorso.durata, percorso.distanza, len(barriere))
    

    # Salva la mappa sovrascrivendo quella precedente
    mappa.salvaMappa(mappa_file)
    #print(f"Mappa del percorso salvata in: {mappa_file}")
    webbrowser.open('file://' + os.path.realpath(mappa_file))

    return









# caricare elementi da file JSON

def caricaElementiDaJSON(directory_risultati, bbox, utente):
    """
    Carica tutti gli elementi dai file JSON nella directory specificata
    """

    if isinstance(utente, ProblemiMobilità):
        exit(-1)

    elementi = []
    
    for file_name in os.listdir(directory_risultati):

        print(f"Trovato file: {file_name}")

        if file_name.endswith('.json'):
            file_path = os.path.join(directory_risultati, file_name)
            
            with open(file_path, 'r', encoding='utf-8') as file:

                contenuto = file.read()
                if not contenuto.strip():  # Verifica se il contenuto (dopo aver rimosso spazi bianchi) è vuoto
                    print("Vuoto, skipppo")
                    continue  # Passa al file successivo

                try:
                    data = json.loads(contenuto)
                    # Processa i dati JSON
                    for elemento in data: # Prende tutti gli elementi

                        # controllo se l'elemento può essere utile per l'utente
                        if utente.interessa(elemento):
                            # controllo se rientra nella bounding box
                            if bbox[0] <= elemento["coordinateCentroide"]["longitudine"] <= bbox[2] and bbox[1] <= elemento["coordinateCentroide"]["latitudine"] <= bbox[3]:
                                elemento_osm = ElementoOSM(elemento)  # Crea l'elemento OSM
                                if elemento_osm:
                                    elementi.append(elemento_osm)  # E lo aggiunge agli altri

                except json.JSONDecodeError:
                    print(f"Errore nel parsing del file JSON: {file_path}")
                except Exception as e:
                    print(f"Errore durante l'elaborazione del file {file_path}: {e}")
                    print(f"Errore: bbox: {bbox}")
                    print(f"Errore: elemento: {elemento["coordinateCentroide"]}")
                    print(f"Id elemento: {elemento["id"]}")
    
    print(f"{len(elementi)} trovati!")

    return elementi # Ritorna quindi tutti gli elementi parsati












# chiamata all'API di OpenRouteService per calcolare i percorsi

def chiamataAPIdiORS(inizio, fine, aree_da_evitare=None, waypoints=None):
    """
    Calcola uno o più percorsi pedonale usando OpenRouteService
    
    Args:
        inizio: lista [lon, lat]
        fine: lista [lon, lat]
        headers: headers per l'API ORS
        aree_da_evitare: lista di poligoni da evitare (opzionale)
        waypoints: lista di waypoints [lat, lon] da includere nel percorso successivamente selezionato (opzionale)
    
    Returns:
        routes found
    """
    # Controllo validità coordinate
    if len(inizio) != 2 or len(fine) != 2:
        print("Coordinate di inizio o fine non valide")
        return None
        
    # Costruisco il body & headers
    coordinates = [inizio]
    
    # Aggiungi waypoints se presenti
    if waypoints and len(waypoints) > 0:
        for wp in waypoints:
            # waypoints sono [lat, lon], converto in [lon, lat] per ORS
            coordinates.append([wp[1], wp[0]])
    
    # Aggiungi la destinazione
    coordinates.append(fine)
    
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8"
    }

    body = {
        "coordinates": coordinates,
        "instructions": False,
        "profile": "foot-walking",
        "format": "geojson"
    }
    
    # Aggiungi le aree da evitare se presenti
    if aree_da_evitare and len(aree_da_evitare) > 0:
        try:
            body["options"] = {
                "avoid_polygons": geometry.mapping(MultiPolygon(aree_da_evitare))
            }
        except Exception as e:
            print(f"Errore nella creazione dei poligoni da evitare: {e}")
            # Continua senza aree da evitare
    
    # Faccio la call a ORS
    try:    
        call = requests.post('https://api.openrouteservice.org/v2/directions/foot-walking/json', json=body, headers=headers)
        call.raise_for_status()
        #print(call)
        route_data = json.loads(call.text)
        
        if "routes" in route_data and len(route_data["routes"]) > 0:
            return route_data["routes"]
        else:
            print("Nessun percorso trovato")
            return None
    except requests.exceptions.HTTPError as e:
        print(f"Errore HTTP nel calcolo del percorso: {e}")
        if call.status_code == 401:
            print("Chiave API non valida o mancante")
        elif call.status_code == 403:
            print("Accesso negato")
        return None
    except Exception as e:
        print(f"Errore nel calcolo del percorso: {e}")
        return None


def mostraBarriereEFacilitatori(barriere, facilitatori):
    """
    Mostra le barriere e i facilitatori trovati e consente all'utente di selezionare quali evitare/includere
    
    Args:
        barriere: lista di oggetti Barriera
        facilitatori: lista di oggetti Facilitatore
    
    Returns:
        tuple (barriere_da_evitare, facilitatori_da_includere)
    """
    if not barriere:
        print("\nNessuna barriera trovata sul percorso.")
    else:
        print(f"\n========== BARRIERE TROVATE ({len(barriere)}) ==========")
        for i, barriera in enumerate(barriere):
            descrizione = f"Tipo: {barriera.tipo}"
            for key, value in barriera.tags.items():
                if key in ['description', 'note', 'name', 'wheelchair', 'tactile_paving', 'kerb', 'surface']:
                    descrizione += f", {key}: {value}"
            print(f"{i+1}. {barriera} - {descrizione}")
    
    if not facilitatori:
        print("\nNessun facilitatore trovato sul percorso.")
    else:
        print(f"\n========== FACILITATORI TROVATI ({len(facilitatori)}) ==========")
        for i, facilitatore in enumerate(facilitatori):
            descrizione = f"Tipo: {facilitatore.tipo}"
            for key, value in facilitatore.tags.items():
                if key in ['description', 'note', 'name', 'wheelchair', 'tactile_paving']:
                    descrizione += f", {key}: {value}"
            print(f"{i+1}. {facilitatore} - {descrizione}")
    
    # In un'applicazione reale, qui mostreremmo le immagini e consentiremmo la selezione
    barriere_da_evitare = []
    if barriere:
        print("\nSeleziona i numeri delle barriere che vuoi evitare (separati da virgola) (Enter per nessuna):")
        input_barriere = input("> ")
        
        if input_barriere.strip():
            try:
                indici = [int(idx.strip()) - 1 for idx in input_barriere.split(",")]
                barriere_da_evitare = [barriere[idx] for idx in indici if 0 <= idx < len(barriere)]
                if len(barriere_da_evitare) != len(indici):
                    print("Alcuni indici non validi sono stati ignorati.")
            except ValueError:
                print("Input non valido. Nessuna barriera evitata.")
    
    facilitatori_da_includere = []
    if facilitatori:
        print("\nSeleziona i numeri dei facilitatori che vuoi includere (separati da virgola) (Enter per nessuno):")
        input_facilitatori = input("> ")
        
        if input_facilitatori.strip():
            try:
                indici = [int(idx.strip()) - 1 for idx in input_facilitatori.split(",")]
                facilitatori_da_includere = [facilitatori[idx] for idx in indici if 0 <= idx < len(facilitatori)]
                if len(facilitatori_da_includere) != len(indici):
                    print("Alcuni indici non validi sono stati ignorati.")
            except ValueError:
                print("Input non valido. Nessun facilitatore selezionato.")
    
    return barriere_da_evitare, facilitatori_da_includere





































def main():

    # ------------ Impostazioni ------------
    headers = {
        'Authorization': ORS_API_KEY
    }
    directory_risultati = "data"  # Directory dove sono salvati i risultati delle query Overpass
    file_della_mappa = "mappa_percorso.html"  # Nome fisso per il file della mappa

    # ------------ dati di input ------------
    utente = Utente("firstUserEver", ProblemiMobilità.VISIVA)
    # per inserire coordinate di inizio e fine
    inizio = COORDINATE_INIZIO
    fine = COORDINATE_FINE

    
    
    # ------------ calcolo iniziale del percorso ------------
    print(f"Calcolo percorso pedonale da {inizio} a {fine}...")
    results = chiamataAPIdiORS(inizio, fine)
    # errori eventuali
    if not results:
        print("Impossibile calcolare il percorso. Verifica coordinate o connessione internet.")
        return

    # Crea l'oggetto percorso
    percorso = Percorso(results[0])
    

    # ------------ caricamento dati ------------
    print("\nCaricamento dati da file JSON...")
    elementi_osm_personalizzati = caricaElementiDaJSON(directory_risultati, percorso.bbox, utente) # qua carico tutti gli elementi 
    print(f"\nCaricati {len(elementi_osm_personalizzati)} elementi all'interno della bbox del percoso calcolato")   # a prescindere dalla vicinanza al percorso
    # questi elementi_osm sono già stati estratti considerando l'utente che li ha richiesti e la bbox del percorso





    # parto col primo percorso e lo visualizzo:

    print(f"\nCercando barriere e facilitatori per utente {utente.nickname} con disabilità: {utente.problema} lungo il percorso di default")
    barriere, facilitatori, infrastrutture = percorso.trovaElementiSulPercorso(elementi_osm_personalizzati, utente)
    print(f"Risultato:\n - {len(barriere)} barriere\n - {len(facilitatori)} facilitatori\n - {len(infrastrutture)} infrastrutture\ntrovati sul percorso")


    creaEDisegnaMappa(percorso, barriere, facilitatori, infrastrutture, file_della_mappa)






























    # # Tracciamento di tutte le scelte dell'utente nelle varie iterazioni
    # tutte_barriere_da_evitare = []  # Lista di tutte le barriere selezionate finora
    # tutti_facilitatori_da_includere = []  # Lista di tutti i facilitatori selezionati finora
    
    # # Memorizza gli ID per evitare duplicati
    # id_barriere_selezionate = set()
    # id_facilitatori_selezionati = set()




    # # Ciclo di ottimizzazione del percorso
    # utente_soddisfatto = False
    # iterazione = 1
    # while not utente_soddisfatto: # finche l'utente non è soddisfatto
        
    #     print(f"\n===== ITERAZIONE {iterazione} =====")
        
    #     # Trova barriere e facilitatori sul percorso attuale
    #     print(f"Cercando barriere e facilitatori per utente con disabilità: {utente.name}...")
    #     barriere, facilitatori = percorso.trovaElementiSulPercorso(utente, elementi_osm)
    #     print(f"Trovate {len(barriere)} barriere e {len(facilitatori)} facilitatori sul percorso.")
        
        # # Crea la mappa
        # centro_percorso = percorso.percorso_geo.centroid
        # mappa = MappaFolium(centro=(centro_percorso.y, centro_percorso.x))
        
        # # Aggiungi il percorso
        # mappa.aggiungiPolyline(percorso.coordinate_della_polyline)
        
        # # Aggiungi il buffer barriere
        # mappa.aggiungiPoligono(
        #     [(y, x) for x, y in percorso.bufferBarriere_geo.exterior.coords],
        #     tooltip='Area di ricerca barriere',
        #     colore='orange'
        # )
        # # Aggiungi il buffer facilitatori
        # mappa.aggiungiPoligono(
        #     [(y, x) for x, y in percorso.bufferFacilitatori_geo.exterior.coords],
        #     tooltip='Area di ricerca facilitatori',
        #     colore='lightgreen'
        # )

        # # Aggiungi le barriere
        # for barriera in barriere:
        #     evidenziato = barriera.id in id_barriere_selezionate
        #     mappa.aggiungiElemento(barriera, evidenzia=evidenziato)
        
        # # Aggiungi i facilitatori
        # for facilitatore in facilitatori:
        #     evidenziato = facilitatore.id in id_facilitatori_selezionati
        #     mappa.aggiungiElemento(facilitatore, evidenzia=evidenziato)
        
        # # Salva la mappa sovrascrivendo quella precedente
        # mappa.salvaMappa(mappa_file)
        # print(f"Mappa del percorso salvata in: {mappa_file}")
        # webbrowser.open('file://' + os.path.realpath(mappa_file))
        
    #     # Mostra le scelte precedenti all'utente
    #     if tutte_barriere_da_evitare:
    #         print("\n--- Barriere precedentemente selezionate da evitare ---")
    #         for i, barriera in enumerate(tutte_barriere_da_evitare):
    #             print(f"{i+1}. {barriera} - Tipo: {barriera.tipo}")
        
    #     if tutti_facilitatori_da_includere:
    #         print("\n--- Facilitatori precedentemente selezionati da includere ---")
    #         for i, facilitatore in enumerate(tutti_facilitatori_da_includere):
    #             print(f"{i+1}. {facilitatore} - Tipo: {facilitatore.tipo}")
        
    #     # Mostra le nuove barriere e facilitatori all'utente e chiedi quali evitare/includere
    #     nuove_barriere_da_evitare, nuovi_facilitatori_da_includere = mostraBarriereEFacilitatori(barriere, facilitatori)
        
    #     # Se l'utente non ha selezionato né barriere da evitare né facilitatori da includere, 
    #     # termina il ciclo di ottimizzazione
    #     if not nuove_barriere_da_evitare and not nuovi_facilitatori_da_includere:
    #         print("\nNessuna nuova barriera da evitare o facilitatore da includere.")
    #         print("Percorso definitivo confermato!")
    #         utente_soddisfatto = True
    #         continue
        
    #     # Aggiungi le nuove scelte alle liste complessive, evitando duplicati
    #     for barriera in nuove_barriere_da_evitare:
    #         if barriera.id not in id_barriere_selezionate:
    #             tutte_barriere_da_evitare.append(barriera)
    #             id_barriere_selezionate.add(barriera.id)
        
    #     for facilitatore in nuovi_facilitatori_da_includere:
    #         if facilitatore.id not in id_facilitatori_selezionati:
    #             tutti_facilitatori_da_includere.append(facilitatore)
    #             id_facilitatori_selezionati.add(facilitatore.id)
        
    #     # Ricalcola il percorso con TUTTE le preferenze dell'utente fino ad ora
    #     print("\nRicalcolo del percorso in base a tutte le scelte accumulate...")
        
    #     # Prepara poligoni da evitare per tutte le barriere selezionate
    #     aree_da_evitare = []
    #     for barriera in tutte_barriere_da_evitare:
    #         centroide = barriera.trovaCoordinateCentroide()
    #         # Proietta il punto in UTM
    #         punto_utm = project_to_utm(centroide[0], centroide[1])
    #         # Crea un buffer in metri intorno alla barriera (es. 20 metri) e riproiettalo in WGS84
    #         cerchio_utm = Point(punto_utm).buffer(BUFFER_FACILITATORI_IN_METRI)
    #         cerchio_coords = [project_to_wgs(x, y) for x, y in cerchio_utm.exterior.coords]
    #         aree_da_evitare.append(Polygon(cerchio_coords))
        
    #     # Prepara waypoints da includere per tutti i facilitatori selezionati
    #     waypoints = []
    #     for facilitatore in tutti_facilitatori_da_includere:
    #         centroide = facilitatore.trovaCoordinateCentroide()
    #         waypoints.append((centroide[1], centroide[0]))  # Inverte in [lat, lon] per ORS
        
    #     # Ricalcola il percorso
    #     nuovo_encoded_polyline = calcolaPercorsoConORS(
    #         inizio, 
    #         fine,
    #         aree_da_evitare if aree_da_evitare else None, 
    #         waypoints if waypoints else None
    #     )
        
    #     if nuovo_encoded_polyline:
    #         percorso = Percorso(nuovo_encoded_polyline)
    #         print("Percorso ricalcolato con successo!")
    #     else:
    #         print("Errore nel ricalcolo del percorso. Utilizzo percorso precedente.")
    #         print("Prova a fare scelte diverse nella prossima iterazione.")
        
    #     iterazione += 1
    
    # # Visualizza il percorso finale
    # barriere_finali, facilitatori_finali = percorso.trovaElementiSulPercorso(utente, elementi_osm)
    
    # # Crea la mappa finale
    # centro_percorso = percorso.percorso_geo.centroid
    # mappa_finale = MappaFolium(centro=(centro_percorso.y, centro_percorso.x))
    
    # # Aggiungi il percorso
    # mappa_finale.aggiungiPolyline(percorso.coordinate_della_polyline)
    
    # # Aggiungi il buffer barriere
    # mappa.aggiungiPoligono(
    #     [(y, x) for x, y in percorso.bufferBarriere_geo.exterior.coords],
    #     tooltip='Area di ricerca barriere',
    #     colore='orange'
    # )
    # # Aggiungi il buffer facilitatori
    # mappa.aggiungiPoligono(
    #     [(y, x) for x, y in percorso.bufferFacilitatori_geo.exterior.coords],
    #     tooltip='Area di ricerca facilitatori',
    #     colore='lightgreen'
    # )
    
    # # Aggiungi le barriere
    # for barriera in barriere_finali:
    #     evidenziata = barriera.id in id_barriere_selezionate
    #     mappa_finale.aggiungiElemento(barriera, evidenzia=evidenziata)
    
    # # Aggiungi i facilitatori
    # for facilitatore in facilitatori_finali:
    #     evidenziato = facilitatore.id in id_facilitatori_selezionati
    #     mappa_finale.aggiungiElemento(facilitatore, evidenzia=evidenziato)
    
    # # Salva la mappa finale
    # mappa_finale.salvaMappa(mappa_file)
    # print(f"\nPercorso finale salvato in: {mappa_file}")
    # webbrowser.open('file://' + os.path.realpath(mappa_file))
    
    # # Riepilogo di tutte le scelte dell'utente
    # print("\n===== RIEPILOGO DELLE SCELTE =====")
    # print(f"Barriere da evitare ({len(tutte_barriere_da_evitare)}):")
    # for i, barriera in enumerate(tutte_barriere_da_evitare):
    #     print(f"{i+1}. {barriera} - Tipo: {barriera.tipo}")
    
    # print(f"\nFacilitatori da includere ({len(tutti_facilitatori_da_includere)}):")
    # for i, facilitatore in enumerate(tutti_facilitatori_da_includere):
    #     print(f"{i+1}. {facilitatore} - Tipo: {facilitatore.tipo}")
    
    # print("\nAnalisi del percorso completata!")

if __name__ == "__main__":
    main()