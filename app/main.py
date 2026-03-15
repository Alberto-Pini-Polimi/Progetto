import os
import time
import requests
import sys

def attendi_otp(url_otp, timeout_minuti=10):
    """
    Mette in pausa lo script finché OTP non risponde correttamente.
    Utile perché OTP deve 'masticare' il file .pbf prima di essere pronto.
    """
    print(f"⏳ Attendo che OpenTripPlanner sia pronto all'indirizzo: {url_otp}")
    
    # L'endpoint base di OTP per controllare lo stato
    # Se usi /otp/transmodel/v3 nel codice, facciamo un ping alla root o ai routers
    health_check_url = url_otp.replace("/transmodel/v3", "/routers/default")
    
    inizio = time.time()
    timeout_secondi = timeout_minuti * 60

    while True:
        try:
            # Chiediamo il punto base di OTP
            response = requests.get("http://otp:8080/otp/")
            if response.status_code < 500: # Se risponde in qualsiasi modo, il server è vivo
                break
        except:
            pass
        time.sleep(2) # riprovo ancora per vedere che si sia attivato
            
        tempo_trascorso = time.time() - inizio
        if tempo_trascorso > timeout_secondi:
            print("\n❌ Timeout: OTP non sembra essere partito o c'è un errore")
            sys.exit(1)
 
        time.sleep(10) # Riprova ogni 10 secondi

def main():
    print("\n======================================")
    print("||  Avvio del Container di Python   ||")
    print("======================================\n")

    # Recupera l'URL di OTP dalle variabili d'ambiente (settato in docker-compose.yml)
    # Se non lo trova, usa localhost come fallback di sicurezza
    otp_url = os.getenv("OTP_URL", "http://localhost:8080/otp/transmodel/v3")
    
    # aspettiamo che OTP sia pronto
    attendi_otp(otp_url)


    # IDEALMENTE:

    # faccio partire l'interfaccia web con cui l'utente può fare le sue richieste
    # questo diventerebbe un semplice server flask

    # all'arrivo di ogni richiesta si esegue OTP_routing (e quindi anche OSM_routing)
    # e si risponde con la mappa.html

    # questo script fa partire un azione periodica che esegue "dailyGTFSzipUpdater.py"
    # dopodiché blocco il container python e il server andrà in down
    # trovo un modo di lanciare il comando per ribuildare tutto col nuovo file Milano-gtfs.zip (updatato con la nuova accessibilità)
    
    # in tutto ciò c'è anche un'altra azione che esegue ogni ora per confrontare la
    # baseline che è stata scritta al tempo dell'update del GTFS con i nuovi dati sull'accessibilità
    # creando quindi un nuovo file "inaccessible_stations_till_last_GTFSzip_file_update.txt"
    # contenente i nomi delle stazioni che sono diventate inaccessibili




    # eseguo finalmente il programma
    try:
        import OTP_routing
        
        print("pronti, partenza, viaa 🚀 ...")
        OTP_routing.main()
        
    except ImportError as e:
        print(f"\n❌ Errore: Non trovo lo script OTP_routing.py. Errore: {e}")
    

if __name__ == "__main__":
    main()