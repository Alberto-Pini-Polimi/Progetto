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
import random


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


# input principali da parte dell'utente
ORS_API_KEY = open("API_KEY.txt", 'r').read().strip()

PROBLEMATICA_UTENTE = ProblemiMobilità.MOTORIA

# percorso CORTO
#COORDINATE_INIZIO = [45.484916762291135, 9.19188606022059] # Gae Aulenti
#COORDINATE_FINE = [45.46952050871136, 9.180556820875562] # castello Sforzesco

# percorso LUNGO
#COORDINATE_INIZIO = [45.47686209277475, 9.122741092267772] # san Siro
#COORDINATE_FINE = [45.45447977998694, 9.21002802045689] # piazzale libia

# altro percorso
#COORDINATE_INIZIO = [45.4574769358078, 9.166137110591368] # parco Don Luigi Giussani
#COORDINATE_FINE = [45.47369617989732, 9.203759327498373] # planetario

#COORDINATE_INIZIO = [45.43316993192978, 9.158379520641018] # parco Don Luigi Giussani
#COORDINATE_FINE = [45.46069914927452, 9.215797267672631] # planetario

COORDINATE_INIZIO = [45.46797351580205, 9.182596260259444] # CAIROLI
COORDINATE_FINE = [45.46420895249842, 9.18958581318816] # PIAZZA DUOMO

COORDINATE_INIZIO = [round(COORDINATE_INIZIO[1], 6), round(COORDINATE_INIZIO[0], 6)]
COORDINATE_FINE = [round(COORDINATE_FINE[1], 6), round(COORDINATE_FINE[0], 6)]

# L'istanza dell'utente è definita sotto nel main

# definisco un'area di distanza attorno ai percorsi
BUFFER_FACILITATORI_IN_METRI = 10
BUFFER_BARRIERE_IN_METRI = 3
BUFFER_INFRASTRUTTURE_IN_METRI = 50
BUFFER_ATTORNO_AL_QUALE_SI_CREA_UNA_ZONA_PROIBITA_IN_METRI = 15



# Definisci i sistemi di coordinate e le funzioni per la trasformazione tra i sistemi
wgs84 = 'EPSG:4326' # Sistema di coordinate geografiche (lat/lon)
utm_zone = 'EPSG:32632' # Proiezione UTM adatta (Milano nella zona UTM 32N)
project_to_utm = Transformer.from_crs(wgs84, utm_zone, always_xy=True).transform
project_to_wgs = Transformer.from_crs(utm_zone, wgs84, always_xy=True).transform

def inverti_coordinate(coord):
    return coord[1], coord[0]



class Utente():

    def __init__(self, nickname, problema_di_mobilità, tipologia_di_elemento_da_includere_sempre=None, tipologia_di_elemento_da_evitare_sempre=None):
        
        self.nickname = nickname # dev'essere univoco
        self.problema = problema_di_mobilità
        self.tipologia_di_elemento_da_includere_sempre = tipologia_di_elemento_da_includere_sempre if tipologia_di_elemento_da_includere_sempre else []
        self.tipologia_di_elemento_da_evitare_sempre = tipologia_di_elemento_da_evitare_sempre if tipologia_di_elemento_da_evitare_sempre else []

    def interessa(self, elemento):
        """
            Metodo per capire se un elemento è utile per l'utente in questione
        """

        name_elemento = elemento.get("name")

        if name_elemento in self.tipologia_di_elemento_da_includere_sempre:
            return True
        if name_elemento in self.tipologia_di_elemento_da_evitare_sempre:
            return False

        barriera_per = elemento.get("barrieraPer", [])
        facilitatore_per = elemento.get("facilitatorePer", [])
        infrastruttura_per = elemento.get("infrastrutturaPer", [])

        # vedo se un elemento è pertinente e poi ritorno True solo in base al ranking (nient'altro che un valore di priorità)
        if str(self.problema) in barriera_per or  str(self.problema) in facilitatore_per or str(self.problema) in infrastruttura_per:
            if elemento.get("autore") == self.nickname: # se l'elemento è inerente ed è stato creato dall'utente
                return True # allora lo includo poiché sicuramente per lui è interessante (dato che è stato lui a crearlo)
            return elemento.get("ranking") >= random.randint(0, 100) # altrimenti ritorno True in funzione della probabilità 

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
        self.barriera_per = elemento_del_DB["barrieraPer"] 
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

        if utente.problema.value in self.barriera_per:
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
        
        # Costruisci l'URL di Street View utilizzando le coordinate
        sv_url = f"https://www.google.com/maps?layer=c&cbll={punto[0]},{punto[1]}"

        popup = folium.Popup(
            f"""
                <h3>{elemento.nome}</h3>
                Descrizione: {elemento.descrizione}<br>
                <a href="{sv_url}" target="_blank" rel="noopener">Immagine Street View</a><br>
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

    # itero tutti i file .json contenenti i potenziali elementi da caricare in memoria
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

                # Carico il contenuto del file
                try:
                    data = json.loads(contenuto)
                    # Processa i dati JSON
                    for elemento in data:
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

def chiamataAPIdiORS(inizio, fine, elementi_da_evitare=None, waypoints=None, preferenza="fastest"):
    """
    Calcola uno o più percorsi pedonale usando OpenRouteService
    
    Args:
        inizio: lista [lon, lat]
        fine: lista [lon, lat]
        headers: headers per l'API ORS
        aree_da_evitare: lista di elementiOSM da evitare (opzionale)
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
        "format": "geojson",
        "preference": preferenza
    }
    
    # converto ogni elemento da evitare in un array di poligoni da evitare
    if elementi_da_evitare:
        poligoni_da_evitare = []
        for elemento_da_evitare in elementi_da_evitare:
            # Ottieni il centroide dell'elemento
            lon = elemento_da_evitare.coordinate_centroide["longitudine"]
            lat = elemento_da_evitare.coordinate_centroide["latitudine"]
            # Proietta il punto in UTM
            punto_utm = project_to_utm(lon, lat)
            # Crea un buffer in metri attorno al punto (ad esempio 10m)
            buffer_utm = Point(punto_utm).buffer(BUFFER_ATTORNO_AL_QUALE_SI_CREA_UNA_ZONA_PROIBITA_IN_METRI)
            # Riproietta il buffer in WGS84
            buffer_wgs84_coords = [project_to_wgs(x, y) for x, y in buffer_utm.exterior.coords]
            poligono = Polygon(buffer_wgs84_coords)
            poligoni_da_evitare.append(poligono)


        if len(poligoni_da_evitare) > 0:
            try:
                body["options"] = {
                    "avoid_polygons": geometry.mapping(MultiPolygon(poligoni_da_evitare))
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
        exit(-1)
    except Exception as e:
        print(f"Errore nel calcolo del percorso: {e}")
        exit(-1)



def main():

    # ------------ Impostazioni ------------
    directory_risultati = "data"  # Directory dove sono salvati i risultati delle query Overpass
    #file_della_mappa = "mappa_percorso.html"  # Nome fisso per il file della mappa

    # ------------ dati di input ------------
    utente = Utente("firstUserEver", PROBLEMATICA_UTENTE)
    # per inserire coordinate di inizio e fine
    inizio = COORDINATE_INIZIO
    fine = COORDINATE_FINE

    # ------------ calcolo iniziale del percorso ------------
    print(f"Calcolo percorso da {inizio} a {fine}...")
    results = chiamataAPIdiORS(inizio, fine) # quello calcolato è il percorso di default ed anche il più veloce
    # e creazione l'oggetto percorso
    percorso = Percorso(results[0])
    
    # ------------ caricamento dati ------------
    print("\nCaricamento dati da file JSON...")
    elementi_osm_personalizzati = caricaElementiDaJSON(directory_risultati, percorso.bbox, utente) # qua carico tutti gli elementi 
    print(f"\nCaricati {len(elementi_osm_personalizzati)} elementi all'interno della bbox del percoso calcolato") # a prescindere dalla vicinanza al percorso
    # questi elementi_osm sono già stati estratti considerando l'utente che li ha richiesti e la bbox del percorso (carico in memoria solo gli elementi necessari)

    # ------------ selezione dati caricati ------------
    # dagli elementi estratti trovo quelli rientranti nei buffer del percorso separandoli fra barriere, facilitatori ed infrastrutture
    print(f"\nCercando barriere e facilitatori per utente {utente.nickname} con disabilità: {utente.problema} lungo il percorso di default")
    barriere, facilitatori, infrastrutture = percorso.trovaElementiSulPercorso(elementi_osm_personalizzati, utente)
    print(f"Risultato:\n - {len(barriere)} barriere\n - {len(facilitatori)} facilitatori\n - {len(infrastrutture)} infrastrutture\ntrovati sul percorso")

    # ------------ disegno percorso di default ------------
    # creo la mappa col percorso e tutto il resto
    creaEDisegnaMappa(percorso, barriere, facilitatori, infrastrutture, "mappa_più_veloce.html")

    tutte_barriere_da_evitare = barriere

    # ora calcola automaticamente la mappa senza le barriere che l'utente non vuole 
    #barriere_che_lo_user_sicuramente_vuole_rimuovere = utente.


    # provo a fare un percorso togliendo tutte le barriere che incontro sulla via
    percorsoSenzaBarriere = Percorso(chiamataAPIdiORS(inizio, fine, tutte_barriere_da_evitare)[0])
    barriere, facilitatori, infrastrutture = percorsoSenzaBarriere.trovaElementiSulPercorso(elementi_osm_personalizzati, utente)
    
    
    for barriera in barriere:
        tutte_barriere_da_evitare.append(barriera)

    percorsoSenzaBarriere = Percorso(chiamataAPIdiORS(inizio, fine, tutte_barriere_da_evitare)[0])
    barriere, facilitatori, infrastrutture = percorsoSenzaBarriere.trovaElementiSulPercorso(elementi_osm_personalizzati, utente)

    for barriera in barriere:
        tutte_barriere_da_evitare.append(barriera)

    percorsoSenzaBarriere = Percorso(chiamataAPIdiORS(inizio, fine, tutte_barriere_da_evitare)[0])
    barriere, facilitatori, infrastrutture = percorsoSenzaBarriere.trovaElementiSulPercorso(elementi_osm_personalizzati, utente)

    for barriera in barriere:
        tutte_barriere_da_evitare.append(barriera)

    percorsoSenzaBarriere = Percorso(chiamataAPIdiORS(inizio, fine, tutte_barriere_da_evitare)[0])
    barriere, facilitatori, infrastrutture = percorsoSenzaBarriere.trovaElementiSulPercorso(elementi_osm_personalizzati, utente)

    creaEDisegnaMappa(percorsoSenzaBarriere, barriere, facilitatori, infrastrutture, "mappa_senza_barriere.html")



    # prova a fare un altro percorso togliendo tutte le barriere della bbox

    tutte_barriere_da_evitare = []
    for elemento_osm in elementi_osm_personalizzati:
        if elemento_osm.per(utente) == TipoElemento.BARRIERA:
            tutte_barriere_da_evitare.append(elemento_osm) # prendo tutte le barriere per l'utente nella bbox

    percorsoSenzaBarriereDellaBbox = Percorso(chiamataAPIdiORS(inizio, fine, tutte_barriere_da_evitare)[0])
    barriere, facilitatori, infrastrutture = percorsoSenzaBarriereDellaBbox.trovaElementiSulPercorso(elementi_osm_personalizzati, utente)

    creaEDisegnaMappa(percorsoSenzaBarriereDellaBbox, barriere, facilitatori, infrastrutture, "mappa_senza_barriere_della_bbox.html")


if __name__ == "__main__":
    main()