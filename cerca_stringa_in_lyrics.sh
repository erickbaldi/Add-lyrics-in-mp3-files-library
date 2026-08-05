#!/bin/bash

if [ -z "$1" ]; then
  echo "Uso: $0 \"stringa da cercare\""
  exit 1
fi

# Convertiamo la stringa da cercare in minuscolo per evitare problemi
STRINGA_CERCA=$(echo "$1" | tr '[:upper:]' '[:lower:]')

echo "Scansione in corso con Beets per: '$STRINGA_CERCA'..."
echo "--------------------------------------------------------"

find . -type f -iname "*.mp3" | while read -r file; do
  
  # 1. Prendiamo TUTTO l'output di beets per evitare che filtri male il tag
  # 2. Convertiamo tutto l'output in minuscolo
  output_completo=$(beet info "$file" 2>/dev/null | tr '[:upper:]' '[:lower:]')
  
  # Controlliamo se la stringa è presente nell'output di Beets
  if echo "$output_completo" | grep -q "$STRINGA_CERCA"; then
    echo "Trovato in: $file"
  fi
done

echo "--------------------------------------------------------"
echo "Ricerca completata."
