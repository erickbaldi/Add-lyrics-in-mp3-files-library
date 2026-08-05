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
from mutagen.id3 import ID3, USLT  # <-- Sotto la lente: ora è qui, visibile e corretta!

if len(sys.argv) < 2:
    print('Uso: python3 prendi_testo_genius.py "/percorso/cartella/musica"')
    sys.exit(1)

cartella_radice = sys.argv[1]

# 🔑 INSERISCI IL TUO CLIENT ACCESS TOKEN DI GENIUS QUI SOTTO:
GENIUS_TOKEN = "nXBtED6rcyjXdCrpuGwuEnR2PNPEc-Zdc0pyPuNMEqE1gW0dydi77ld-0GPLcPgo"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def pulisci_testo(testo):
    if not testo:
        return ""
    t = str(testo).strip()
    t = re.sub(r'^\d+[\s\.\-_]*', '', t)
    t = re.sub(r'\([^)]*\)', '', t)
    t = re.sub(r'\[[^\]]*\]', '', t)
    t = re.sub(r'(?i)\.mp3$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

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
            frammenti = re.findall(r'<div[^>]*class="[^"]*Lyrics__Container[^"]*"[^>]*>(.*?)</div>', codice_html, re.DOTALL)
            if not frammenti:
                frammenti = re.findall(r'<div[^>]*class="lyrics"[^>]*>(.*?)</div>', codice_html, re.DOTALL)
            if frammenti:
                testo_unito = "\n".join(frammenti)
                testo_pulito = re.sub(r'<br\s*/?>', '\n', testo_unito)
                testo_pulito = re.sub(r'<[^>]+>', '', testo_pulito)
                return html.unescape(testo_pulito).strip()
    except Exception as e:
        print(f"⚠️ Errore nel bypass HTML di Genius: {e}")
    return None

print(f"📁 Inizio scansione protetta con GENIUS in: {cartella_radice}\n")

successi = 0
falliti = 0
gia_presenti = 0

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
                print("ℹ️ Tag ID3 incompleti. Tento il recupero dal nome del file...")
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
                
            if tags and "USLT::eng" in tags:
                print(f"⏭️ Il testo è già presente in questo file. Salto.")
                gia_presenti += 1
                continue
            
            artista_pulito = pulisci_testo(artista_raw)
            titolo_pulito = pulisci_testo(titolo_raw)
            
            if not artista_pulito or not titolo_pulito:
                print(f"⚠️ Dati non validi dopo la pulizia. Salto.")
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
                        print("🔗 Canzone trovata! Scarico il testo in modalità stealth...")
                        testo = scarica_testo_da_html(url_pagina_lyrics)
                        if testo:
                            if tags is None:
                                tags = ID3()
                            tags["USLT::eng"] = USLT(encoding=3, lang='eng', desc='', text=testo)
                            tags.save(file_mp3)
                            print("✅ Testo iniettato con successo da Genius!")
                            successi += 1
                            continue
                    print("❌ Testo non trovato su Genius.")
                    falliti += 1
            except Exception as e:
                print(f"💥 Errore di rete con Genius: {e}")
                falliti += 1
            
            time.sleep(1.0)

print(f"\n=========================================")
print(f"🎉 SCANSIONE GENIUS COMPLETATA!")
print(f"🎵 Testi aggiunti: {successi}")
print(f"⏭️ Canzoni già aggiornate: {gia_presenti}")
print(f"❌ Canzoni saltate o non trovate: {falliti}")
print(f"=========================================")

try:
    frase = "Ho finito di eseguire il tuo comando, mio signore!"
    subprocess.run(['spd-say', '-l', 'it', '-t', 'male1', frase])
except Exception as e:
    pass
