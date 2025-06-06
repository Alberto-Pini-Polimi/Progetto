# Seconda Versione: Segnalazione di Elementi per l'Accessibilità

In generale si punta ad una approccio più semi-automatico, togliendo in parte il lungo processo di selezione del percorso via iterazioni. 
Opto più per una proposta di vari percorsi dai quali l'utente va a selezionare il migliore a seconda delle sue preferenze.

**Nuove Funzionalità:**

- **Autore e Ranking:** Ogni elemento (facilitatore o barriera) ora è associato a un autore e possiede un ranking.
- **Classificazione e Disabilità:** Gli elementi sono pre-classificati come facilitatori o barriere e sono collegati a specifiche disabilità.
- **Provenienza:** Un elemento può essere creato direttamente da un utente o estratto da OpenStreetMap (OSM).
- **Descrizione:** Ogni elemento include una descrizione fornita dall'utente creatore o estratta da OSM.
- **Multi-Percorso:** All'utente si presentano più percorsi, assieme alle relative info, da cui scegliere.

### Feedback Utente

Dopo aver pianificato ed eseguito un percorso suggerito, l'utente ha la possibilità di selezionare alcuni elementi incontrati lungo il tragitto per recensirli positivamente o negativamente. Questo feedback può portare a:

- **Modifica Diretta (automatica):** Piccole variazioni del ranking dell'elemento.
- **Modifica Indiretta (tramite moderatore):** Modifiche più sostanziali all'elemento, basate sul feedback ricevuto.

### Funzionamento del Ranking

Un elemento creato dall'utente X ha una priorità massima di visualizzazione per lo stesso utente X. Questo significa che, quando X percorrerà un itinerario che include tale elemento, quest'ultimo gli comparirà sempre come una barriera evitabile (con la potenziale opzione di evitarlo automaticamente, a meno che l'elemento creato non corrisponda alla sua specifica disabilità).

**Dettagli del Ranking:**

- Ogni elemento inizia con un ranking percentuale compreso tra 0% e 25%. Questo valore indica la probabilità che un utente con una disabilità corrispondente visualizzi l'elemento se il suo percorso lo include.
- Gli elementi creati dall'utente sono sempre visibili all'utente creatore, indipendentemente dal loro ranking.
- Il ranking di un elemento può essere modificato in base al feedback degli utenti:
  - Al termine di un percorso, un utente diverso dal creatore può confermare o smentire l'utilità di uno o più elementi tramite una notifica di validazione dell'applicazione.
  - Utenti dedicati alla verifica possono influenzare direttamente il ranking nel database.

### OSM vs User-Created

I dati estratti da OSM sono inizialmente considerati affidabili, con un ranking predefinito del 100% (e quindi visibili a tutti gli utenti). Questo ranking può essere abbassato rapidamente se gli utenti, tramite il feedback post-percorso, segnalano inesattezze.

Quando un utente crea un nuovo elemento, il campo del database `"elementoOSM"` viene impostato su `null`.

Gli altri campi, in particolare le coordinate geografiche, vengono calcolati automaticamente se l'elemento è importato da OSM. Se l'elemento è creato dall'utente, le coordinate vengono specificate tramite un'interfaccia grafica.

### Esempio di Entry del Database

nella v1 i dati erano direttamente i risultati delle query di OSM, quindi meno uniformi tra di loro e con ampia variabilità. Ora invece, grazie allo script `"data_extractor_from_OSM_script.py"` i dati sono prima parsati e poi "inseriti" nel "DB" (cioè i file contenenti tutte le barriere e i facilitatori)

esempio concreto di un elemento inserito dall'utente Pippo (in questo caso del file barriere.json):

```json
{
    "id": "mock-element-id",
    "barrieraPer": [
        "Motoria"
    ],
    "facilitatorePer": [],
    "infrastrutturaPer": [],
    "autore": "Pippo",
    "ranking": 50,
    "nome": "barriera-generica",
    "descrizione": "Questo è un dato di mock dell'utente Pippo",
    "immagine": null,
    "elementoOSM": null,
    "coordinateCentroide": {
        "longitudine": 9.184913,
        "latitudine": 45.466296
    }
}```

L'utente Pippo crea la barriera per le problematiche motorie di nome barriera-generica.
A questa barriera è inizialmente stato dato un ranking di 10, ma col tempo si è alzato a 50.
Adesso il 50% degli utenti che non sono Pippo e che non hanno come preferenze di barriere il nome "barriera-generica" vedono il 50% delle volte l'elemento creato da Pippo se i loro percorsi passano di li.
Invece l'utente Pippo e tutti gli utenti che hanno come preferenza di barriera il nome "barriera-generica" vedono sempre l'elemento indipendentemente dal ranking che questo ha.







