import os
import sys
import urllib.request
import urllib.parse
import json
import ssl
import time
import re
import subprocess
from mutagen.id3 import ID3, USLT

if len(sys.argv) < 2:
    print('Uso: python3 prendi_testo_ovh.py "/percorso/cartella/musica"')
    sys.exit(1)

cartella_radice = sys.argv[1]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 🧹 Pulizia metadati mirata per ottimizzare la ricerca nel database
def pulisci_metadati(testo):
    if not testo:
        return ""
    t = str(testo).strip()
    t = re.sub(r'^\d+[\s\.\-_]*', '', t) # Rimuove i numeri di traccia (es: "01 - ")
    t = re.sub(r'\([^)]*\)', '', t)      # Rimuove le parentesi tonde
    t = re.sub(r'\[[^\]]*\]', '', t)     # Rimuove le parentesi quadre
    t = re.sub(r'(?i)\.mp3$', '', t)     # Rimuove .mp3
    t = re.sub(r'\s+', ' ', t).strip()   # Compatta gli spazi doppi
    return t

print(f"📁 Inizio scansione INTEGRALE con LYRICS.OVH in: {cartella_radice}\n")

if not os.path.exists(cartella_radice):
    print(f"❌ ERRORE: La cartella '{cartella_radice}' non esiste.")
    sys.exit(1)

successi = 0
falliti = 0

for radice, directory, files in os.walk(cartella_radice):
    for file in files:
        if file.lower().endswith('.mp3'):
            file_mp3 = os.path.join(radice, file)
            print(f"---")
            print(f"🎧 Analizzo file: {file}")
            
            artista_raw = None
            titolo_raw = None
            tags = None
            
            try:
                tags = ID3(file_mp3)
                artista_raw = tags.get('TPE1').text[0] if tags.get('TPE1') else None
                titolo_raw = tags.get('TIT2').text[0] if tags.get('TIT2') else None
            except Exception:
                tags = None

            if not artista_raw or not titolo_raw:
                nome_file_senza_est = os.path.splitext(file)[0]
                if "-" in nome_file_senza_est:
                    parti = [p.strip() for p in nome_file_senza_est.split("-")]
                    if len(parti) >= 2:
                        if parti[0].isdigit() and len(parti) > 2:
                            artista_raw = parti[1]
                            titolo_raw = " ".join(parti[2:])
                        else:
                            artista_raw = parti[0]
                            titolo_raw = " ".join(parti[1:])
                if not artista_raw:
                    artista_raw = os.path.basename(radice)
                if not titolo_raw:
                    titolo_raw = nome_file_senza_est

            if not artista_raw or not titolo_raw:
                print(f"❌ Impossibile determinare Artista/Titolo. Salto.")
                falliti += 1
                continue
            
            artista_pulito = pulisci_metadati(artista_raw)
            titolo_pulito = pulisci_metadati(titolo_raw)
            
            if not artista_pulito or not titolo_pulito:
                print(f"⚠️ Dati vuoti dopo la pulizia. Salto.")
                falliti += 1
                continue

            print(f"🔍 Cerco su Lyrics.ovh: \"{artista_pulito}\" - \"{titolo_pulito}\"")
            
            # Codifica i dati per l'URL dell'API ufficiale
            artista_encoded = urllib.parse.quote(artista_pulito)
            titolo_encoded = urllib.parse.quote(titolo_pulito)
            
            url = f"https://api.lyrics.ovh/v1/{artista_encoded}/{titolo_encoded}"
            
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
                    dati = json.loads(response.read().decode('utf-8'))
                    testo = dati.get('lyrics', '').strip()
                    
                    if testo and len(testo) > 50:
                        if tags is None:
                            tags = ID3()
                        
                        # Inietta il testo puro così come arriva dall'API (Strofe + Ritornelli garantiti)
                        tags["USLT::eng"] = USLT(encoding=3, lang='eng', desc='', text=testo)
                        tags.save(file_mp3)
                        print("✅ Testo INTEGRALE (tutte le strofe) iniettato con successo!")
                        successi += 1
                        continue
                    else:
                        print("❌ Risposta ricevuta ma il testo era vuoto.")
                        falliti += 1
                        
            except Exception as e:
                print(f"❌ Brano non trovato nel database o errore di rete: {e}")
                falliti += 1
            
            # Pausa breve ed ecologica per non sovraccaricare il server
            time.sleep(0.5)

print(f"\n=========================================")
print(f"🎉 AGGIORNAMENTO OVH COMPLETATO!")
print(f"🎵 Testi integrali iniettati: {successi}")
print(f"❌ Canzoni non trovate o saltate: {falliti}")
print(f"=========================================")

try:
    frase = "Ho finito di scaricare i testi integrali da o vu acca, mio signore!"
    subprocess.run(['spd-say', '-l', 'it', '-t', 'male1', frase])
except Exception as e:
    pass

