#!/bin/bash

if [ -z "$1" ]; then
    echo "Errore: Devi specificare il percorso di una cartella."
    echo "Uso: $0 /percorso/alla/cartella/musica"
    exit 1
fi

TARGET_DIR="${1%/}"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Errore: La cartella '$TARGET_DIR' non esiste."
    exit 1
fi

echo "Inizio elaborazione dei soli TAG ID3v2 (Nessuna modifica al filesystem)..."
echo "----------------------------------------------------------------------"

# Trova tutti i file .mp3 ricorsivamente
find "$TARGET_DIR" -type f -iname "*.mp3" -print0 | while IFS= read -r -d '' file; do

    # 1. Estrazione dei nomi grezzi dalle cartelle e dal file
    cartella_album=$(dirname "$file")
    cartella_artista=$(dirname "$cartella_album")

    album_grezzo=$(basename "$cartella_album")
    artista=$(basename "$cartella_artista")
    titolo_grezzo=$(basename "$file" .mp3)

    # 2. Pulizia delle sole variabili di testo tramite regex (l'hard disk non viene toccato)
    # Rimuove l'anno all'inizio dell'album (es: "2009 - Endgame" -> "Endgame")
    album_pulito=$(echo "$album_grezzo" | sed -E 's/^([0-9]{4})([- ._]*|\[.*\][ -_]*| )//' | xargs)
    
    # Rimuove il numero di traccia all'inizio del titolo (es: "11-megadeth-the right..." -> "megadeth-the right...")
    # Nota: pulisce qualsiasi sequenza numerica iniziale seguita da spazi, trattini o punti
    titolo_pulito=$(echo "$titolo_grezzo" | sed -E 's/^[0-9]+([- ._]*| )//' | xargs)

    echo "File: $file"
    echo " -> TAG TPE1/TPE2 (Artista): $artista"
    echo " -> TAG TALB (Album)      : $album_pulito (grezzo era: $album_grezzo)"
    echo " -> TAG TIT2 (Titolo)     : $titolo_pulito (grezzo era: $titolo_grezzo)"
    echo "----------------------------------------------------------------------"

    # 3. Sovrascrittura dei tag ID3v2 sul file originale
    mid3v2 --TPE1 "$artista" --TPE2 "$artista" --TALB "$album_pulito" --TIT2 "$titolo_pulito" "$file"

done

echo "Processo completato! I tag sono stati sovrascritti con successo."
