# routes_wheelchair_example.py
import requests
import polyline
from datetime import datetime
import time

# ================================
# 1. Imposta la tua API key
# ================================
API_KEY = "AIzaSyCAMjlsXww47Np8pS02pbJQ6_6YODg1WCY"

# ================================
# 2. Funzione per chiamare Routes API
# ================================
def get_wheelchair_transit_route(origin, destination, departure_time=None):
    """
    Richiede un percorso transit wheelchair-accessible usando la Routes API.
    
    origin/destination: tuple (lat, lng)
    departure_time: datetime, se None usa orario attuale
    
    Restituisce:
        Lista di steps con travel_mode, polyline decodificata e fermate
    """
    if departure_time is None:
        from datetime import datetime, timezone
        departure_time = datetime.now(timezone.utc)
    # ISO 8601 UTC timestamp richiesto dalla Routes API
    departure_time_str = departure_time.isoformat("T") + "Z"

    # ================================
    # 2a. Costruzione della richiesta JSON
    # ================================
    url = f"https://routes.googleapis.com/directions/v2:computeRoutes?key={API_KEY}"
    payload = {
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
        "travelMode": "TRANSIT",  # mezzi pubblici
        "departureTime": departure_time_str,
        "transitPreferences": {
            "wheelchairAccessible": True  # richiede percorsi accessibili
        },
        "computeAlternativeRoutes": False,  # prendiamo solo il migliore
        "routeModifiers": {}  # eventuali altri vincoli
    }

    # ================================
    # 2b. Chiamata HTTP POST
    # ================================
    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    # ================================
    # 3. Parsing dei legs e steps
    # ================================
    steps_list = []

    # la nuova Routes API restituisce "routes[] → legs[] → steps[]"
    routes = data.get("routes", [])
    if not routes:
        raise RuntimeError("Nessun percorso trovato")

    route = routes[0]  # prendiamo il primo percorso
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            step_info = {
                "travel_mode": step.get("travelMode"),
            }

            # ================================
            # 3a. Polyline decodificata
            # ================================
            poly = step.get("polyline", {}).get("encodedPolyline")
            if poly:
                step_info["polyline_points"] = poly
                step_info["coords"] = polyline.decode(poly)
                """TODO mi sembra: se c è una poly associo allo step la polyline e le coordinate decodificate 
                    a sto punto sotto fa lo stesso con vari dettagli se è un mezzo pubblico"""

            # ================================
            # 3b. Dettagli transit (se presenti)
            # ================================
            transit_details = step.get("transitDetails")
            if transit_details:
                dep_stop = transit_details.get("departureStop", {}).get("location", {})
                arr_stop = transit_details.get("arrivalStop", {}).get("location", {})
                step_info.update({
                    "transit_line": transit_details.get("line", {}).get("shortName"),
                    "departure_stop": dep_stop,
                    "arrival_stop": arr_stop,
                    "num_stops": transit_details.get("numStops"),
                    "departure_time": transit_details.get("departureTime", {}).get("value"),
                    "arrival_time": transit_details.get("arrivalTime", {}).get("value")
                })

            steps_list.append(step_info)

    return steps_list

# ================================
# 4. Esempio di uso
# ================================
if __name__ == "__main__":
    origin = (45.4642, 9.19)      # Milano Duomo
    destination = (45.4780, 9.2300)

    steps = get_wheelchair_transit_route(origin, destination)

    from pprint import pprint
    pprint(steps)
