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
ORS_API_KEY = open("API_KEY.txt", 'r').read().strip()  # Sostituisci con la tua chiave reale
COORDINATE_INIZIO = [9.17988, 45.47006]  # [lon, lat] castello sforzesco
#COORDINATE_FINE = [9.18956, 45.46424]    # [lon, lat] duomo
#COORDINATE_FINE = [9.203530, 45.485146] # centrale
COORDINATE_FINE = [9.226897, 45.478111] # piazza leo

# COORDINATE_INIZIO = [46.538795718940136, 12.124246397899869] 
# COORDINATE_FINE = [46.53569202884132, 12.1411393835463]

# COORDINATE_INIZIO = [round(COORDINATE_INIZIO[1], 6), round(COORDINATE_INIZIO[0], 6)]
# COORDINATE_FINE = [round(COORDINATE_FINE[1], 6), round(COORDINATE_FINE[0], 6)]

# definisco un'area di distanza attorno ai percorsi
BUFFER_FACILITATORI_IN_METRI = 30
BUFFER_BARRIERE_IN_METRI = 5

# Definisci i sistemi di coordinate e le funzioni per la trasformazione tra i sistemi
wgs84 = 'EPSG:4326' # Sistema di coordinate geografiche (lat/lon)
utm_zone = 'EPSG:32632' # Proiezione UTM adatta (Milano nella zona UTM 32N)
project_to_utm = Transformer.from_crs(wgs84, utm_zone, always_xy=True).transform
project_to_wgs = Transformer.from_crs(utm_zone, wgs84, always_xy=True).transform

def inverti_coordinate(coord):
    return coord[1], coord[0]

class disabilità(Enum):
    NON_VEDENTE = 0
    WHEELCHAIR = 1

class ElementoOSM:
    """Classe base per qualsiasi elemento proveniente da OpenStreetMap"""
    
    def __init__(self, id, tipo_elemento, tags=None):
        self.id = id
        self.tipo_elemento = tipo_elemento  # node, way, relation
        self.tags = tags if tags else {}
        self.geometry = None  # Verrà impostata nelle sottoclassi
        self.centroide = None  # Verrà calcolato nelle sottoclassi
        self.tipo = None  # Sarà specificato nelle sottoclassi (es. "attraversamento", "bagno", ecc.)
        self.immagine_url = None
    
    def trovaCoordinateCentroide(self):
        """Restituisce le coordinate del centroide (lon, lat)"""
        return self.centroide
    
    def è_rilevante_per(self, tipo_disabilità):
        """Determina se questo elemento è rilevante per il tipo di disabilità specificato"""
        # Implementazione base, da sovrascrivere nelle sottoclassi
        return False
    
    def trova_immagine(self):
        """Trova l'URL dell'immagine di questo elemento, se disponibile"""
        # if 'mapillary' in self.tags:
        #     return f"https://mapillary.com/app/?pKey={self.tags['mapillary']}"
        # else:
        #     return f"https://via.placeholder.com/400x300?text={self.tipo}+ID:{self.id}"
        return None

class Barriera(ElementoOSM):
    """Rappresenta un ostacolo per una persona con disabilità"""
    
    def __init__(self, id, tipo_elemento, punto=None, poligono=None, tags=None):
        super().__init__(id, tipo_elemento, tags)
        self.tipo = self._determina_tipo()
        
        # Imposta la geometria in base ai parametri forniti
        if poligono:
            self.geometry = poligono
            self.centroide = (poligono.centroid.x, poligono.centroid.y)
        elif punto:
            self.geometry = punto
            self.centroide = (punto.x, punto.y)
        else:
            raise ValueError("Deve essere fornito almeno punto o poligono")
        
        self.immagine_url = self.trova_immagine()
    
    def _determina_tipo(self): # TODO: fare l'enum delle barriere e dei facilitatori
        """Determina il tipo specifico di barriera in base ai tag"""
        # Highway
        if self.tags.get('highway') == 'crossing':
            return "attraversamento"
        elif self.tags.get('highway') == 'steps':
            return "scalino"
        # Kerb
        elif 'kerb' in self.tags:
            return "kerb"
        # Superficie
        elif self.tags.get('surface') in ['cobblestone', 'gravel', 'pebblestone', 'sand']:
            return "superficie_difficile"
        # Marciapiede problematico
        elif self.tags.get('highway') == 'footway' and self.tags.get('width') and float(self.tags.get('width')) < 0.9:
            return "marciapiede_stretto"
        # Default
        return "barriera_generica"
        # molti altri tipi possibili ...
    
    def è_rilevante_per(self, tipo_disabilità):
        """Determina se questa barriera è rilevante per il tipo di disabilità specificato"""
        if tipo_disabilità == disabilità.NON_VEDENTE:
            # Per non vedenti
            if self.tipo == "attraversamento":
                # Attraversamenti senza segnale acustico
                return not (self.tags.get('traffic_signals:sound') == 'yes')
            
            # Scale e gradini
            if self.tipo == "scalino":
                return False
            
            # Kerb
            if self.tipo == "kerb":
                return False
            
            # Ostacoli non percepibili col bastone
            if 'tactile_paving' in self.tags and self.tags['tactile_paving'] == 'no':
                return True
                
            # Superfici problematiche per non vedenti
            if self.tipo == "superficie_difficile":
                return True
                
            # Altrimenti
            #return self.tipo in [...]
            return False
        
        elif tipo_disabilità == disabilità.WHEELCHAIR:
            # Per utenti in sedia a rotelle
            if self.tipo == "attraversamento":
                # Se è specificato wheelchair=no o non è accessibile
                if self.tags.get('wheelchair') == 'no':
                    return True
                # Se ha un gradino (kerb) alto
                if 'kerb' in self.tags and self.tags['kerb'] not in ['lowered', 'flush']:
                    return True
            
            # Kerb alti
            if self.tipo == "kerb" and self.tags.get('kerb:height') and float(self.tags.get('kerb:height', '0')) > 0.03:
                return True
            
            # Gradini e scale
            if self.tipo == "scalino" or self.tags.get('highway') == 'steps':
                return True
            
            # Superficie problematica per sedie a rotelle
            if self.tipo == "superficie_difficile":
                return True
            
            # Marciapiedi stretti
            if self.tipo == "marciapiede_stretto":
                return True
            
            # Pendenze elevate
            if 'incline' in self.tags:
                try:
                    incline = self.tags['incline']
                    if incline.endswith('%'):
                        incline_value = float(incline[:-1])
                        if incline_value > 8:  # Pendenza > 8% è difficile per sedia a rotelle
                            return True
                except ValueError:
                    pass
            
            #return self.tipo in [...]
            return False
        
        return False
    
    def __str__(self):
        return f"Barriera {self.tipo} (ID: {self.id})"

class Facilitatore(ElementoOSM):
    """Rappresenta un elemento che facilita una persona con disabilità"""
    
    def __init__(self, id, tipo_elemento, punto=None, poligono=None, tags=None):
        super().__init__(id, tipo_elemento, tags)
        self.tipo = self._determina_tipo()
        
        # Imposta la geometria in base ai parametri forniti
        if poligono:
            self.geometry = poligono
            self.centroide = (poligono.centroid.x, poligono.centroid.y)
        elif punto:
            self.geometry = punto
            self.centroide = (punto.x, punto.y)
        else:
            raise ValueError("Deve essere fornito almeno punto o poligono")
        
        self.immagine_url = self.trova_immagine()
    
    def _determina_tipo(self): # TODO: fare enum
        """Determina il tipo specifico di facilitatore in base ai tag"""
        # Attraversamento accessibile
        if self.tags.get('highway') == 'crossing' and self.tags.get('traffic_signals:sound') == 'yes':
            return "attraversamento_sonoro"
        elif self.tags.get('highway') == 'crossing' and self.tags.get('wheelchair') == 'yes':
            return "attraversamento_accessibile"
        
        # Servizi
        elif self.tags.get('amenity') == 'toilets' and self.tags.get('wheelchair') == 'yes':
            return "bagno_accessibile"
        
        # Panchine
        elif self.tags.get('amenity') == 'bench':
            return "panchina"
        
        # Fontanelle
        elif self.tags.get('amenity') == 'drinking_water':
            return "fontanella"
        
        # Ascensori
        elif self.tags.get('highway') == 'elevator' or self.tags.get('amenity') == 'elevator':
            return "ascensore"
        
        # Percorsi tattili
        elif self.tags.get('tactile_paving') == 'yes':
            return "percorso_tattile"
        
        # Default
        return "facilitatore_generico"
    
    def è_rilevante_per(self, tipo_disabilità):
        """Determina se questo facilitatore è rilevante per il tipo di disabilità specificato"""
        if tipo_disabilità == disabilità.NON_VEDENTE:
            # Per non vedenti
            if self.tipo == "attraversamento_sonoro":
                return True
            
            # Percorsi tattili
            if self.tipo == "percorso_tattile" or self.tags.get('tactile_paving') == 'yes':
                return True
            
            # Altri elementi utili per non vedenti
            #return self.tipo in [...]
            return False
        
        elif tipo_disabilità == disabilità.WHEELCHAIR:
            # Per utenti in sedia a rotelle
            if self.tipo == "attraversamento_accessibile":
                return True
            
            # Bagni accessibili
            if self.tipo == "bagno_accessibile":
                return True
            
            # Ascensori
            if self.tipo == "ascensore":
                return True
            
            # Panchine (per riposarsi)
            if self.tipo == "panchina":
                return True
            
            # Fontanelle accessibili
            if self.tipo == "fontanella" and self.tags.get('wheelchair') == 'yes':
                return True
            
            # Altri elementi utili
            #return self.tipo in ["rampa", "corrimano", "parcheggio_disabili"]
            return False
        
        return False
    
    def __str__(self):
        return f"Facilitatore {self.tipo} (ID: {self.id})"



















class Percorso():
    
    def __init__(self, encoded_polyline):
        # decoding della polyline
        self.coordinate_della_polyline = polyline.decode(encoded_polyline)
        # Inverti le coordinate per shapely (lon, lat)
        coordinate_shapely = [inverti_coordinate(coord) for coord in self.coordinate_della_polyline]
        self.percorso_geo = LineString(coordinate_shapely)

        # Proietta la polyline in UTM
        percorso_utm_coords = [project_to_utm(lon, lat) for lat, lon in self.coordinate_della_polyline]
        self.percorso_utm = LineString(percorso_utm_coords)
        
        # Inizializza attributi
        self.barriereTrovate = []
        self.facilitatoriTrovati = []
        self.barriere_da_evitare = []
        self.facilitatori_da_includere = []
        
        # Crea il buffer di default
        self.creaBufferBarriere()
        self.creaBufferFacilitatori()

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

    def isNelBuffer(self, punto, tipo_buffer):
        """Verifica se un punto è all'interno del buffer"""
        if isinstance(punto, tuple) or isinstance(punto, list):
            punto_geo = Point(punto)  # lon, lat
        else:
            punto_geo = punto  # Assume che sia già un oggetto Point
            
        # Proietta il punto barriera in UTM
        punto_utm = project_to_utm(punto_geo.x, punto_geo.y)
        punto_utm_shapely = Point(punto_utm)
        # Verifica il contenimento nel buffer UTM e ritorna vero o falso
        if tipo_buffer == "barriere":
            return self.bufferBarriere_utm.contains(punto_utm_shapely)
        elif tipo_buffer == "facilitatori":
            return self.bufferFacilitatori_utm.contains(punto_utm_shapely)
        else:
            raise ValueError("Tipo di buffer non valido. Deve essere 'barriere' o 'facilitatori'.")
    
    def elementoIntersecaIlRispettivoBuffer(self, elemento):
        """Verifica se un elemento (Barriera o Facilitatore) è nel rispettivo buffer"""

        tipo_buffer = "facilitatori" if isinstance(elemento, Facilitatore) else "barriere"
        # Se l'elemento è un poligono, controlla se interseca il buffer
        if isinstance(elemento.geometry, Polygon):
            # Converti le coordinate in UTM
            coords_utm = [project_to_utm(x, y) for x, y in elemento.geometry.exterior.coords]
            poligono_utm = Polygon(coords_utm)
            # Verifica se interseca il buffer
            if tipo_buffer == "barriere":
                return self.bufferBarriere_utm.intersects(poligono_utm)
            elif tipo_buffer == "facilitatori":
                return self.bufferFacilitatori_utm.intersects(poligono_utm)
            else:
                raise ValueError("tipo buffer incorretto")
            
        # se invece è un multipoligono
        elif isinstance(elemento.geometry, MultiPolygon):
            # Per ogni poligono nel multipoligono, verifica intersezione
            for poligono in elemento.geometry.geoms:
                coords_utm = [project_to_utm(x, y) for x, y in poligono.exterior.coords]
                poligono_utm = Polygon(coords_utm)
                # Verifica se interseca il buffer
                if tipo_buffer == "barriere":
                    if self.bufferBarriere_utm.intersects(poligono_utm):
                        return True
                elif tipo_buffer == "facilitatori":
                    if self.bufferFacilitatori_utm.intersects(poligono_utm):
                        return True
                else:
                    raise ValueError("tipo buffer incorretto")
            
            return False
        else:
            # Altrimenti, l'elemento non è un poligono
            return self.isNelBuffer(elemento.trovaCoordinateCentroide(), tipo_buffer)
    
    def trovaElementiSulPercorso(self, disabilitàUtente, elementi_caricati):
        """
        Trova barriere e facilitatori sul percorso in base ai dati caricati dai file JSON
        """
        self.barriereTrovate = []
        self.facilitatoriTrovati = []
        
        for elemento in elementi_caricati:
            # Verifica se l'elemento è nel buffer
            if self.elementoIntersecaIlRispettivoBuffer(elemento):
                # Verifica se è rilevante per la disabilità dell'utente
                if elemento.è_rilevante_per(disabilitàUtente):
                    if isinstance(elemento, Barriera):
                        self.barriereTrovate.append(elemento)
                    elif isinstance(elemento, Facilitatore):
                        self.facilitatoriTrovati.append(elemento)
        
        return self.barriereTrovate, self.facilitatoriTrovati













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
    
    def aggiungiElemento(self, elemento, evidenzia=False):
        """Aggiunge un ElementoOSM (Barriera o Facilitatore) alla mappa"""
        centroide = elemento.trovaCoordinateCentroide()
        punto = (centroide[1], centroide[0])  # Inverte in [lat, lon] per folium
        
        colore = 'red' if isinstance(elemento, Barriera) else 'green'
        icona = 'warning-sign' if isinstance(elemento, Barriera) else 'ok-sign'
        
        # Se l'elemento è evidenziato, cambia lo stile
        if evidenzia:
            colore = 'purple' if isinstance(elemento, Barriera) else 'blue'
        
        popup = folium.Popup(
            f"""
            <b>{elemento.tipo.capitalize()}</b><br>
            ID: {elemento.id}<br>
            <a href="{elemento.immagine_url}" target="_blank">Visualizza immagine</a>
            """,
            max_width=300
        )
        
        self.aggiungiMarker(
            punto=punto,
            colore=colore,
            icona=icona,
            tooltip=str(elemento),
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

def visualizzaPercorsoSuMappa(percorso, barriere, facilitatori, selezionati_barriere=None, selezionati_facilitatori=None):
    """
    Visualizza un percorso con barriere e facilitatori su una mappa Folium
    
    Args:
        percorso: Oggetto Percorso
        barriere: Lista di oggetti Barriera
        facilitatori: Lista di oggetti Facilitatore
        selezionati_barriere: Lista di ID delle barriere selezionate (opzionale)
        selezionati_facilitatori: Lista di ID dei facilitatori selezionati (opzionale)
    
    Returns:
        str: percorso del file HTML della mappa
    """
    # Crea una nuova mappa centrata sul percorso
    centro_percorso = percorso.percorso_geo.centroid
    mappa = MappaFolium(centro=(centro_percorso.y, centro_percorso.x))
    
    # Aggiungi il percorso
    mappa.aggiungiPolyline(percorso.coordinate_della_polyline)
    
    # Aggiungi il buffer delle barriere
    mappa.aggiungiPoligono(
        [(y, x) for x, y in percorso.bufferBarriere_geo.exterior.coords],
        tooltip='Area di ricerca barriere'
    )

    # Aggiungi il buffer dei facilitatori
    mappa.aggiungiPoligono(
        [(y, x) for x, y in percorso.bufferFacilitatori_geo.exterior.coords],
        tooltip='Area di ricerca facilitatori'
    )
    
    # Aggiungi le barriere
    for barriera in barriere:
        evidenziata = selezionati_barriere and barriera.id in selezionati_barriere
        mappa.aggiungiElemento(barriera, evidenzia=evidenziata)
    
    # Aggiungi i facilitatori
    for facilitatore in facilitatori:
        evidenziato = selezionati_facilitatori and facilitatore.id in selezionati_facilitatori
        mappa.aggiungiElemento(facilitatore, evidenzia=evidenziato)
    
    # Salva la mappa
    nome_file = f"mappa_percorso_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    mappa.salvaMappa(nome_file)
    
    return nome_file

































def caricaElementiDaJSON(directory_risultati):
    """
    Carica tutti gli elementi dai file JSON nella directory specificata
    e li converte in oggetti Barriera o Facilitatore
    """
    elementi = []
    # per trovare i risultati devo andare nella directory dei data_extractors
    directory_risultati = './QL_data_extractors/' + directory_risultati
    
    for file_name in os.listdir(directory_risultati):
        if file_name.endswith('.json'):
            file_path = os.path.join(directory_risultati, file_name)
            
            with open(file_path, 'r', encoding='utf-8') as file:
                try:
                    data = json.load(file)
                    # Processa i dati JSON
                    if 'elements' in data:
                        for elemento in data['elements']: # Prende tutti gli elementi
                            elemento_osm = creaElementoDaJSON(elemento) # Crea l'elemento OSM
                            if elemento_osm:
                                elementi.append(elemento_osm) # E lo aggiunge agli altri
                except json.JSONDecodeError:
                    print(f"Errore nel parsing del file JSON: {file_path}")
                except Exception as e:
                    print(f"Errore durante l'elaborazione del file {file_path}: {e}")
    
    return elementi # Ritorna quindi tutti gli elementi parsati

def creaElementoDaJSON(elemento_json):
    """
    Crea un oggetto Barriera o Facilitatore a partire dai dati JSON di un elemento OSM
    """
    if 'type' not in elemento_json or 'id' not in elemento_json:
        return None
    
    tipo_elemento = elemento_json['type']  # node, way, relation
    id_elemento = elemento_json['id']
    tags = elemento_json.get('tags', {})
    
    # Crea geometria
    geometria = None
    if tipo_elemento == 'node' and 'lat' in elemento_json and 'lon' in elemento_json:
        # Per i nodi, crea un punto
        geometria = Point(elemento_json['lon'], elemento_json['lat'])
    
    elif tipo_elemento == 'way' or tipo_elemento == 'relation':
        # Per way e relation, usa il centroide se disponibile
        if 'center' in elemento_json:
            geometria = Point(elemento_json['center']['lon'], elemento_json['center']['lat'])
        elif 'geometry' in elemento_json and len(elemento_json['geometry']) > 0:
            # Se sono disponibili le coordinate complete, prendi il centroide
            coordinates = [(point['lon'], point['lat']) for point in elemento_json['geometry']]
            line = LineString(coordinates)
            geometria = Point(line.centroid.x, line.centroid.y)
        else: # Non abbiamo le coordinate complete, quindi saltiamo questo elemento
            return None
    
    if geometria is None:
        return None
    
    # Capisco se l'elemento_json è una barriera o un facilitatore in base ai suoi tags
    if _è_facilitatore_da_tags(tags):
        return Facilitatore(id_elemento, tipo_elemento, punto=geometria, tags=tags)
    else:
        return Barriera(id_elemento, tipo_elemento, punto=geometria, tags=tags)

def _è_facilitatore_da_tags(tags):
    """
    Determina se un elemento è un facilitatore in base ai suoi tag
    """
    # Attraversamenti accessibili
    if tags.get('highway') == 'crossing' and (
        tags.get('traffic_signals:sound') == 'yes' or 
        tags.get('wheelchair') == 'yes'
    ):
        return True
    
    # Bagni accessibili
    if tags.get('amenity') == 'toilets' and tags.get('wheelchair') == 'yes':
        return True
    
    # Ascensori
    if tags.get('highway') == 'elevator' or tags.get('amenity') == 'elevator':
        return True
    
    # Panchine
    if tags.get('amenity') == 'bench':
        return True
    
    # Fontanelle
    if tags.get('amenity') == 'drinking_water':
        return True
    
    # Percorsi tattili
    if tags.get('tactile_paving') == 'yes':
        return True
    
    # Rampe accessibili
    if (tags.get('highway') == 'footway' or tags.get('ramp') == 'yes') and tags.get('wheelchair') == 'yes':
        return True
    
    # Default: assumiamo che sia una barriera
    return False

def calcolaPercorsoConORS(inizio, fine, aree_da_evitare=None, waypoints=None):
    """
    Calcola un percorso pedonale usando OpenRouteService
    
    Args:
        inizio: lista [lon, lat]
        fine: lista [lon, lat]
        headers: headers per l'API ORS
        aree_da_evitare: lista di poligoni da evitare (opzionale)
        waypoints: lista di waypoints [lat, lon] da includere nel percorso (opzionale)
    
    Returns:
        polyline encoded del percorso
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
            return route_data["routes"][0]["geometry"]
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
    directory_risultati = "results"  # Directory dove sono salvati i risultati delle query Overpass
    mappa_file = "mappa_percorso.html"  # Nome fisso per il file della mappa

    # ------------ dati di input ------------
    print("Inserisci il tipo di disabilità (0 per non vedente, 1 per sedia a rotelle):")
    input_disabilita = int(input("> "))
    utente = disabilità.NON_VEDENTE if input_disabilita == 0 else disabilità.WHEELCHAIR

    # Usa le coordinate predefinite
    inizio = COORDINATE_INIZIO
    fine = COORDINATE_FINE

    # ------------ caricamento dati ------------
    print("Caricamento dati da file JSON...")
    elementi_osm = caricaElementiDaJSON(directory_risultati) # qua carico tutti gli elementi 
    print(f"Caricati {len(elementi_osm)} elementi da OSM")   # a prescindere dalla vicinanza al percorso
    
    # ------------ calcolo iniziale del percorso ------------
    print(f"Calcolo percorso pedonale da {inizio} a {fine}...")
    encoded_polyline = calcolaPercorsoConORS(inizio, fine)

    if not encoded_polyline:
        print("Impossibile calcolare il percorso. Verifica coordinate o connessione internet.")
        return

    # Crea l'oggetto percorso
    percorso = Percorso(encoded_polyline)
    
    # Tracciamento di tutte le scelte dell'utente nelle varie iterazioni
    tutte_barriere_da_evitare = []  # Lista di tutte le barriere selezionate finora
    tutti_facilitatori_da_includere = []  # Lista di tutti i facilitatori selezionati finora
    
    # Memorizza gli ID per evitare duplicati
    id_barriere_selezionate = set()
    id_facilitatori_selezionati = set()
    







    # Ciclo di ottimizzazione del percorso
    utente_soddisfatto = False
    iterazione = 1
    while not utente_soddisfatto: # finche l'utente non è soddisfatto
        
        print(f"\n===== ITERAZIONE {iterazione} =====")
        
        # Trova barriere e facilitatori sul percorso attuale
        print(f"Cercando barriere e facilitatori per utente con disabilità: {utente.name}...")
        barriere, facilitatori = percorso.trovaElementiSulPercorso(utente, elementi_osm)
        print(f"Trovate {len(barriere)} barriere e {len(facilitatori)} facilitatori sul percorso.")
        
        # Crea la mappa
        centro_percorso = percorso.percorso_geo.centroid
        mappa = MappaFolium(centro=(centro_percorso.y, centro_percorso.x))
        
        # Aggiungi il percorso
        mappa.aggiungiPolyline(percorso.coordinate_della_polyline)
        
        # Aggiungi il buffer barriere
        mappa.aggiungiPoligono(
            [(y, x) for x, y in percorso.bufferBarriere_geo.exterior.coords],
            tooltip='Area di ricerca barriere',
            colore='orange'
        )
        # Aggiungi il buffer facilitatori
        mappa.aggiungiPoligono(
            [(y, x) for x, y in percorso.bufferFacilitatori_geo.exterior.coords],
            tooltip='Area di ricerca facilitatori',
            colore='lightgreen'
        )

        # Aggiungi le barriere
        for barriera in barriere:
            evidenziato = barriera.id in id_barriere_selezionate
            mappa.aggiungiElemento(barriera, evidenzia=evidenziato)
        
        # Aggiungi i facilitatori
        for facilitatore in facilitatori:
            evidenziato = facilitatore.id in id_facilitatori_selezionati
            mappa.aggiungiElemento(facilitatore, evidenzia=evidenziato)
        
        # Salva la mappa sovrascrivendo quella precedente
        mappa.salvaMappa(mappa_file)
        print(f"Mappa del percorso salvata in: {mappa_file}")
        webbrowser.open('file://' + os.path.realpath(mappa_file))
        
        # Mostra le scelte precedenti all'utente
        if tutte_barriere_da_evitare:
            print("\n--- Barriere precedentemente selezionate da evitare ---")
            for i, barriera in enumerate(tutte_barriere_da_evitare):
                print(f"{i+1}. {barriera} - Tipo: {barriera.tipo}")
        
        if tutti_facilitatori_da_includere:
            print("\n--- Facilitatori precedentemente selezionati da includere ---")
            for i, facilitatore in enumerate(tutti_facilitatori_da_includere):
                print(f"{i+1}. {facilitatore} - Tipo: {facilitatore.tipo}")
        
        # Mostra le nuove barriere e facilitatori all'utente e chiedi quali evitare/includere
        nuove_barriere_da_evitare, nuovi_facilitatori_da_includere = mostraBarriereEFacilitatori(barriere, facilitatori)
        
        # Se l'utente non ha selezionato né barriere da evitare né facilitatori da includere, 
        # termina il ciclo di ottimizzazione
        if not nuove_barriere_da_evitare and not nuovi_facilitatori_da_includere:
            print("\nNessuna nuova barriera da evitare o facilitatore da includere.")
            print("Percorso definitivo confermato!")
            utente_soddisfatto = True
            continue
        
        # Aggiungi le nuove scelte alle liste complessive, evitando duplicati
        for barriera in nuove_barriere_da_evitare:
            if barriera.id not in id_barriere_selezionate:
                tutte_barriere_da_evitare.append(barriera)
                id_barriere_selezionate.add(barriera.id)
        
        for facilitatore in nuovi_facilitatori_da_includere:
            if facilitatore.id not in id_facilitatori_selezionati:
                tutti_facilitatori_da_includere.append(facilitatore)
                id_facilitatori_selezionati.add(facilitatore.id)
        
        # Ricalcola il percorso con TUTTE le preferenze dell'utente fino ad ora
        print("\nRicalcolo del percorso in base a tutte le scelte accumulate...")
        
        # Prepara poligoni da evitare per tutte le barriere selezionate
        aree_da_evitare = []
        for barriera in tutte_barriere_da_evitare:
            centroide = barriera.trovaCoordinateCentroide()
            # Proietta il punto in UTM
            punto_utm = project_to_utm(centroide[0], centroide[1])
            # Crea un buffer in metri intorno alla barriera (es. 20 metri) e riproiettalo in WGS84
            cerchio_utm = Point(punto_utm).buffer(BUFFER_FACILITATORI_IN_METRI)
            cerchio_coords = [project_to_wgs(x, y) for x, y in cerchio_utm.exterior.coords]
            aree_da_evitare.append(Polygon(cerchio_coords))
        
        # Prepara waypoints da includere per tutti i facilitatori selezionati
        waypoints = []
        for facilitatore in tutti_facilitatori_da_includere:
            centroide = facilitatore.trovaCoordinateCentroide()
            waypoints.append((centroide[1], centroide[0]))  # Inverte in [lat, lon] per ORS
        
        # Ricalcola il percorso
        nuovo_encoded_polyline = calcolaPercorsoConORS(
            inizio, 
            fine,
            aree_da_evitare if aree_da_evitare else None, 
            waypoints if waypoints else None
        )
        
        if nuovo_encoded_polyline:
            percorso = Percorso(nuovo_encoded_polyline)
            print("Percorso ricalcolato con successo!")
        else:
            print("Errore nel ricalcolo del percorso. Utilizzo percorso precedente.")
            print("Prova a fare scelte diverse nella prossima iterazione.")
        
        iterazione += 1
    
    # Visualizza il percorso finale
    barriere_finali, facilitatori_finali = percorso.trovaElementiSulPercorso(utente, elementi_osm)
    
    # Crea la mappa finale
    centro_percorso = percorso.percorso_geo.centroid
    mappa_finale = MappaFolium(centro=(centro_percorso.y, centro_percorso.x))
    
    # Aggiungi il percorso
    mappa_finale.aggiungiPolyline(percorso.coordinate_della_polyline)
    
    # Aggiungi il buffer barriere
    mappa.aggiungiPoligono(
        [(y, x) for x, y in percorso.bufferBarriere_geo.exterior.coords],
        tooltip='Area di ricerca barriere',
        colore='orange'
    )
    # Aggiungi il buffer facilitatori
    mappa.aggiungiPoligono(
        [(y, x) for x, y in percorso.bufferFacilitatori_geo.exterior.coords],
        tooltip='Area di ricerca facilitatori',
        colore='lightgreen'
    )
    
    # Aggiungi le barriere
    for barriera in barriere_finali:
        evidenziata = barriera.id in id_barriere_selezionate
        mappa_finale.aggiungiElemento(barriera, evidenzia=evidenziata)
    
    # Aggiungi i facilitatori
    for facilitatore in facilitatori_finali:
        evidenziato = facilitatore.id in id_facilitatori_selezionati
        mappa_finale.aggiungiElemento(facilitatore, evidenzia=evidenziato)
    
    # Salva la mappa finale
    mappa_finale.salvaMappa(mappa_file)
    print(f"\nPercorso finale salvato in: {mappa_file}")
    webbrowser.open('file://' + os.path.realpath(mappa_file))
    
    # Riepilogo di tutte le scelte dell'utente
    print("\n===== RIEPILOGO DELLE SCELTE =====")
    print(f"Barriere da evitare ({len(tutte_barriere_da_evitare)}):")
    for i, barriera in enumerate(tutte_barriere_da_evitare):
        print(f"{i+1}. {barriera} - Tipo: {barriera.tipo}")
    
    print(f"\nFacilitatori da includere ({len(tutti_facilitatori_da_includere)}):")
    for i, facilitatore in enumerate(tutti_facilitatori_da_includere):
        print(f"{i+1}. {facilitatore} - Tipo: {facilitatore.tipo}")
    
    print("\nAnalisi del percorso completata!")

if __name__ == "__main__":
    main()