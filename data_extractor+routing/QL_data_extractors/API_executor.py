import os
import glob
import requests
import json

'''

Trova tutti i file .txt nella cartella "queries"
esegue questi file come se fossero query-QL con l'API di Overpass-Turbo
Per ogni query eseguita con successo apparirà un file .json nella cartella "results"


'''

def carica_query_da_file(nome_file):
    with open(nome_file, 'r', encoding='utf-8') as file:
        return file.read()

def esegui_query_overpass(query):
    url = "https://overpass-api.de/api/interpreter"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data={'data': query}, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Errore {response.status_code}: {response.text}")

def salva_json(nome_file, dati):
    with open(nome_file, 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)

# === Main ===
def main():

    # trovo le varie cartelle
    cwd = os.getcwd()
    cartella_queries = os.path.join(cwd, "queries")
    cartella_risultati = os.path.join(cwd, "results")
    # creo results se non esiste
    os.makedirs(cartella_risultati, exist_ok=True)

    # trova tutti i file .txt nella cartella "queries"
    file_txt = glob.glob(os.path.join(cartella_queries, "*.txt"))
    print(f"Trovati {len(file_txt)} file .txt nella cartella 'queries'")

    # per ogni file trovato...
    for path_file in file_txt:
        
        nome_file = os.path.basename(path_file)
        nome_senza_estensione = os.path.splitext(nome_file)[0]
        output_path = os.path.join(cartella_risultati, f"{nome_senza_estensione}.json")

        try:
            print(f"Eseguo query da: {nome_file}")
            query = carica_query_da_file(path_file)  # carico query dai file
            risultato = esegui_query_overpass(query) # eseguo la query
            salva_json(output_path, risultato)       # salvo il risultato
            print(f"✅ Salvato: {output_path}")
        except Exception as e:
            print(f"❌ Errore con {nome_file}: {e}")

if __name__ == "__main__":
    main()
