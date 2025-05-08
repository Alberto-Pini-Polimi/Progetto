import json
import requests
import polyline
import folium
from shapely import geometry
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from pyproj import Transformer

# definisco un'area di distanza attorno ai percorsi
BUFFER_DISTANZA_METRI = 20

# Definisci i sistemi di coordinate e le funzioni per la trasformazione tra i sistemi
wgs84 = 'EPSG:4326' # Sistema di coordinate geografiche (lat/lon)
utm_zone = 'EPSG:32632' # Proiezione UTM adatta (Milano nella zona UTM 32N)
project_to_utm = Transformer.from_crs(wgs84, utm_zone, always_xy=True).transform
project_to_wgs = Transformer.from_crs(utm_zone, wgs84, always_xy=True).transform


class Percorso:
    
    def __init__(self, encoded_polyline):
        
        # decoding della polyline
        self.coordinate_della_polyline = polyline.decode(encoded_polyline)
        # Inverti le coordinate per shapely (lon, lat)
        coordinate_shapely = [inverti_coordinate(coord) for coord in self.coordinate_della_polyline]
        self.percorso_geo = LineString(coordinate_shapely)

        # Proietta la polyline in UTM
        percorso_utm_coords = [project_to_utm(lon, lat) for lat, lon in self.coordinate_della_polyline]
        self.percorso_utm = LineString(percorso_utm_coords)

    def creaBufferAttornoAlPercorso(self, grandezza_buffer):
        # Crea un buffer in metri (es. 10 metri)
        self.area_limitrofa_al_percorso_utm = self.percorso_utm.buffer(grandezza_buffer)
        # Riproietta il buffer in WGS84 per la visualizzazione e il controllo delle barriere
        area_limitrofa_al_percorso_geo_coords = [project_to_wgs(x, y) for x, y in self.area_limitrofa_al_percorso_utm.exterior.coords]
        self.area_limitrofa_al_percorso_geo = Polygon(area_limitrofa_al_percorso_geo_coords)

    def isNelBuffer(self, punto):
        punto_geo = Point(punto) # lon, lat
        # Proietta il punto barriera in UTM
        punto_utm = project_to_utm(punto_geo.x, punto_geo.y)
        punto_utm_shapely = Point(punto_utm)
        # Verifica il contenimento nel buffer UTM e ritorna vero o falso
        return self.area_limitrofa_al_percorso_utm.contains(punto_utm_shapely)

    # funzioni grafiche ...
    def creaMappaFolium(self):
        # creo la mappa folium
        self.mappa = folium.Map(location=[self.percorso_geo.centroid.y, self.percorso_geo.centroid.x], zoom_start=13) # che allineo al centro del percorso

    def disegnaIlPercorso(self, colore):
        # aggiungo la polyline
        folium.PolyLine(self.coordinate_della_polyline, color=colore, weight=3).add_to(self.mappa)
        
    def disegnaBuffer(self):
        # inserisco l'area limitrofa nella mappa
        folium.Polygon(
            locations=[(y, x) for x, y in self.area_limitrofa_al_percorso_geo.exterior.coords],
            color="yellow",
            fill=True,
            fill_opacity=0.3,
            weight=2
        ).add_to(self.mappa)
    
    def disegnaMarker(self, punto, colore):
        folium.Marker(location=punto, icon=folium.Icon(color=colore)).add_to(self.mappa)


    def salvaMappa(self, nome_mappa):

        if self.mappa == None:
            return
        
        self.mappa.save(nome_mappa)

def inverti_coordinate(coord):
	return coord[1], coord[0]


""" STEP 0
	definisco gli input
"""

# coordinate di inizio e fine
inizio = [9.17988, 45.47006]
fine = [9.18956, 45.46424]
# barriere e facilitatori sono suddivisi in funzione delle preferenze dell'utente
facilitatori = [
]
barriere = [
    [9.18255, 45.46763],
    [9.18493, 45.46618]  # all'interno dell'area limitrofa al percorso
]


""" STEP 1
	inizio trovando la strada più semplice senza curare delle barriere o dei facilitatori
"""

# costruisco il body & headers:
body = {
	"coordinates":[inizio, fine],
    "instructions": False,
    "profile": "wheelchair",
    "format": "geojson"
    #"profile":
	#"elevation":"true", # <-- la polyline cambia in questo caso!!
	#"extra_info":["steepness","suitability","surface"]
}
headers = {
    'Authorization': '5b3ce3597851110001cf62487c5742934c8b4389bdf3c74d2a29107c'
}
# faccio la call a ORS
call = requests.post('https://api.openrouteservice.org/v2/directions/foot-walking/json', json=body, headers=headers)
if not call.ok:
    print("ERROR!!")
    exit
# converto il testo in JSON
standard_route = json.loads(call.text)


""" STEP 2
	trovo tutte le barriere sul percorso
"""

percorso_standard = Percorso(standard_route["routes"][0]["geometry"]) # creo percorso dalla polyline
percorso_standard.creaBufferAttornoAlPercorso(BUFFER_DISTANZA_METRI)  # creo area di buffer attorno al percorso

# parte grafica
percorso_standard.creaMappaFolium() # creo la mappa
percorso_standard.disegnaIlPercorso("red") # disegno il percorso standard
percorso_standard.disegnaBuffer() # prima di disegnarlo bisogna creare il buffer!!
percorso_standard.disegnaMarker(inverti_coordinate(inizio), "green")
percorso_standard.disegnaMarker(inverti_coordinate(fine), "blue")
for barriera in barriere:
    percorso_standard.disegnaMarker(inverti_coordinate(barriera), "red")
percorso_standard.salvaMappa("mappaStandard.html") # infine salvo la mappa
mappa = percorso_standard.mappa # mi salvo la mappa per dopo

# trovo le barriere all'interno del buffer del percorso
barriere_vicine_al_percorso = []
for barriera in barriere:
    if percorso_standard.isNelBuffer(barriera):
        barriere_vicine_al_percorso.append(barriera)

print(str(len(barriere_vicine_al_percorso)) + " barriere trovate nel buffer")


""" STEP 3
	ricalcolo la il percorso evitando esplicitamente queste barriere
"""

avoid_polygons = []
for barriera in barriere_vicine_al_percorso:
    # Proietta il punto barriera in UTM
    punto_utm = project_to_utm(Point(barriera).x, Point(barriera).y)
    # Crea un buffer in metri intorno alla barriera (es. 20 metri) e riproiettalo in WGS84
    buffer_barriera_utm = Point(punto_utm).buffer(20)
    buffer_barriera_geo_coords = [project_to_wgs(x, y) for x, y in buffer_barriera_utm.exterior.coords]
    avoid_polygons.append(Polygon(buffer_barriera_geo_coords))

if avoid_polygons:
    # creo la nuova query evitando
    body["options"] = {
        "avoid_polygons": geometry.mapping(MultiPolygon(avoid_polygons))
    }
    # nuova call all'API di ORS
    #print(geometry.mapping(MultiPolygon(avoid_polygons)))
    call = requests.post('https://api.openrouteservice.org/v2/directions/foot-walking/json', json=body, headers=headers)
    # converto il testo in JSON e poi in un percorso
    percorso_senza_barriere = Percorso(json.loads(call.text)["routes"][0]["geometry"])

    # parte grafica in cui aggiungo alla mappa di prima il nuovo percroso
    percorso_senza_barriere.mappa = mappa # gli do la mappa di prima
    percorso_senza_barriere.disegnaIlPercorso("blue") # disegno il nuovo percorso
    percorso_senza_barriere.salvaMappa("mappaDelNuovoPercorsoRispettoAQuelloVecchio.html")

else:
    print("Nessuna barriera vicina al percorso trovata.")

