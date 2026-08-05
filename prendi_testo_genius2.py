import os
import sys
import urllib.request
import urllib.parse
import json
import ssl
import time
import re
import subprocess
import html

if len(sys.argv) < 2:
    print('Uso: python3 prendi_testo_genius.py "/percorso/cartella/musica"')
    sys.exit(1)

cartella_radice = sys.argv[1]

# 🔑 IL TUO CLIENT ACCESS TOKEN DI GENIUS INSERITO DIRETTAMENTE:
GENIUS_TOKEN = "nXBtED6rcyjXdCrpuGwuEnR2PNPEc-Zdc0pyPuNMEqE1gW0dydi77ld-0GPLcPgo"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 🧹 Questa pulisce SOLO l'artista e il titolo del file per fare la ricerca mirata
def pulisci_metadati(testo):
    if not testo:
        return ""
    t = str(testo).strip()
    t = re.sub(r'^\d+[\s\.\-_]*', '', t) # Toglie i numeri di traccia iniziali
    t = re.sub(r'\([^)]*\)', '', t)      # Toglie le parentesi tonde
    t = re.sub(r'\[[^\]]*\]', '', t)     # Toglie le parentesi quadre
    t = re.sub(r'(?i)\.mp3$', '', t)     # Toglie l'estensione .mp3
    t = re.sub(r'\s+', ' ', t).strip()   # Pulisce gli spazi doppi
    return t

# 🌀 FUNZIONE DI ESTRAZIONE CONTINUA ED EPURAZIONE PUBBLICITÀ
def scarica_testo_da_html(url_pagina):
    try:
        headers_browser = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3',
            'Connection': 'keep-alive'
        }
        req = urllib.request.Request(url_pagina, headers=headers_browser)
        with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
            codice_html = response.read().decode('utf-8')
            
            # Trova TUTTI i contenitori di testo sparsi nella pagina
            frammenti = re.findall(r'<div[^>]*class="[^"]*Lyrics__Container[^"]*"[^>]*>(.*?)</div>', codice_html, re.DOTALL)
            
            # Paracadute per le canzoni più vecchie su Genius
            if not frammenti:
                frammenti = re.findall(r'<div[^>]*class="lyrics"[^>]*>(.*?)</div>', codice_html, re.DOTALL)
            
            if frammenti:
                testo_completo = ""
                for pezzo in frammenti:
                    pezzo_pulito = re.sub(r'<br\s*/?>', '\n', pezzo)
                    pezzo_pulito = re.sub(r'<[^>]+>', '', pezzo_pulito)
                    testo_completo += pezzo_pulito + "\n"
                
                testo_finale = html.unescape(testo_completo).strip()
                
                # 🧼 Rimozione attiva dei residui fastidiosi di Genius (es: "You might also like", numeri di Embed finali)
                testo_finale = re.sub(r'(?i)you might also like', '', testo_finale)
                testo_finale = re.sub(r'\d+Embed$', '', testo_finale) # Elimina il counter dei click in fondo
                testo_finale = re.sub(r'Embed$', '', testo_finale)
                
                return testo_finale.strip()
                
    except Exception as e:
        print(f"⚠️ Errore durante l'estrazione dal sito Genius: {e}")
    return None

print(f"📁 Inizio scansione Genius (Modalità Tolleranza Massima) in: {cartella_radice}\n")

if not os.path.exists(cartella_radice):
    print(f"❌ ERRORE: La cartella '{cartella_radice}' NON esiste! Controlla il percorso.")
    sys.exit(1)

successi = 0
falliti = 0

from mutagen.id3 import ID3, USLT

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
                print(f"❌ Impossibile determinare le informazioni del brano. Salto.")
                falliti += 1
                continue
            
            artista_pulito = pulisci_metadati(artista_raw)
            titolo_pulito = pulisci_metadati(titolo_raw)
            
            if not artista_pulito or not titolo_pulito:
                print(f"⚠️ Dati vuoti dopo la pulizia dei metadati. Salto.")
                falliti += 1
                continue

            print(f"🔍 Cerco su Genius: \"{artista_pulito}\" - \"{titolo_pulito}\"")
            query = f"{artista_pulito} {titolo_pulito}"
            query_encoded = urllib.parse.quote(query)
            url_ricerca = f"https://api.genius.com/search?q={query_encoded}"
            
            try:
                req = urllib.request.Request(url_ricerca, headers={
                    'Authorization': f'Bearer {GENIUS_TOKEN.strip()}',
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0'
                })
                with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                    dati = json.loads(response.read().decode('utf-8'))
                    hits = dati.get('response', {}).get('hits', [])
                    
                    if hits:
                        url_pagina_lyrics = hits[0]['result']['url']
                        print("🔗 Canzone trovata! Estrazione testo...")
                        
                        testo = scarica_testo_da_html(url_pagina_lyrics)
                        
                        # 🔄 SOGLIA ABBASSATA A 20 CARATTERI: Passano anche i testi molto brevi
                        if testo and len(testo) > 20: 
                            if tags is None:
                                tags = ID3()
                            tags["USLT::eng"] = USLT(encoding=3, lang='eng', desc='', text=testo)
                            tags.save(file_mp3)
                            print("✅ Testo iniettato con successo!")
                            successi += 1
                            continue
                        else:
                            print("⚠️ Il testo estratto è risultato effettivamente vuoto sul sito.")
                            
                    print("❌ Testo non trovato su Genius.")
                    falliti += 1
            except Exception as e:
                print(f"💥 Errore di rete o API con Genius: {e}")
                falliti += 1
            
            time.sleep(1.0)

print(f"\n=========================================")
print(f"🎉 AGGIORNAMENTO COMPLETATO!")
print(f"🎵 Testi scritti correttamente: {successi}")
print(f"❌ Canzoni saltate: {falliti}")
print(f"=========================================")

try:
    frase = "Ho finito di aggiornare tutti i testi, mio signore!"
    subprocess.run(['spd-say', '-l', 'it', '-t', 'male1', frase])
except Exception as e:
    pass

