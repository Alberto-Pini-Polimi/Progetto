#!/bin/bash

# Configurazione
ONE_HOUR=3600
UPDATE_CYCLES_BEFORE_TOTAL_UPDATE=4


echo "🤖 Orchestratore avviato. Ciclo: 1 Build + $UPDATE_CYCLES_BEFORE_TOTAL_UPDATE Monitoraggi."

while true; do
    # --- ORA X: BUILD TOTALE ---
    echo "--- [$(date +%T)] FASE 1: Esecuzione serverRoutine.sh (Build) ---"
    ./serverRoutine.sh
    
    # Ciclo per i 3 monitoraggi successivi (X+1, X+2, X+3)
    for i in {1..$UPDATE_CYCLES_BEFORE_TOTAL_UPDATE}; do
        echo "💤 In attesa per 1 ora..."
        sleep $ONE_HOUR
        
        echo "--- [$(date +%T)] FASE $((i+1)): Esecuzione hourlyMonitor.py (Check $i/3) ---"
        python3 app/hourlyMonitor.py
    done

    echo "💤 Ciclo completato. Aspetto un'ora prima della prossima build..."
    sleep $ONE_HOUR
    # Il ciclo ricomincia da capo con la build
done