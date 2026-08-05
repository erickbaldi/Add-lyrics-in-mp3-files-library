import os
import sys
import urllib.request
import urllib.parse
import ssl
import time
import re
import subprocess
import xml.etree.ElementTree as ET
from mutagen.id3 import ID3, USLT

if len(sys.argv) < 2:
    print('Uso: python3 prendi_testo_chartlyrics.py "/percorso/cartella/musica"')
    sys.exit(1)

cartella_radice = sys.argv[1]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 🧹 Pulizia metadati leggera per non confondere il database di Chartlyrics
def pulisci_metadati(testo):
    if not testo:
        return ""
    t = str(testo).strip()
    t = re.sub(r'^\d+[\s\.\-_]*', '', t) # Rimuove i numeri di traccia
    t = re.sub(r'\([^)]*\)', '', t)      # Rimuove le parentesi tonde
    t = re.sub(r'\[[^\]]*\]', '', t)     # Rimuove le parentesi quadre
    t = re.sub(r'(?i)\.mp3$', '', t)     # Rimuove .mp3
    t = re.sub(r'\s+', ' ', t).strip()   # Compatta gli spazi doppi
    return t

print(f"📁 Inizio scansione con CHARTLYRICS in: {cartella_radice}\n")

if not os.path.exists(cartella_radice):
    print(f"❌ ERRORE: La cartella '{cartella_radice}' non esiste.")
    sys.exit(1)

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

            # Salta se il testo completo è già presente
            if tags and "USLT::eng" in tags:
                testo_esistente = tags["USLT::eng"].text
                if testo_esistente and len(testo_esistente) > 200:
                    print(f"⏭️ Il testo completo è già presente in questo file. Salto.")
                    gia_presenti += 1
                    continue

            # Fallback sul nome del file se mancano i tag ID3
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

            print(f"🔍 Cerco su Chartlyrics: \"{artista_pulito}\" - \"{titolo_pulito}\"")
            
            # Codifica i parametri per l'API in XML di Chartlyrics
            artista_encoded = urllib.parse.quote(artista_pulito)
            titolo_encoded = urllib.parse.quote(titolo_pulito)
            
            url = f"http://api.chartlyrics.com/apiv1.asmx/SearchLyricDirect?artist={artista_encoded}&song={titolo_encoded}"
            
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=12, context=ctx) as response:
                    xml_data = response.read()
                    
                    # Analizza l'XML ricevuto dal server
                    root = ET.fromstring(xml_data)
                    
                    # I tag nell'XML di Chartlyrics usano un namespace specifico
                    ns = {'ns': 'http://api.chartlyrics.com/apiv1.asmx/'}
                    lyric_element = root.find('ns:Lyric', ns)
                    
                    testo = lyric_element.text.strip() if lyric_element is not None and lyric_element.text else ""
                    
                    if testo and len(testo) > 40:
                        if tags is None:
                            tags = ID3()
                        
                        tags["USLT::eng"] = USLT(encoding=3, lang='eng', desc='', text=testo)
                        tags.save(file_mp3)
                        print("✅ Testo INTEGRALE iniettato con successo da Chartlyrics!")
                        successi += 1
                        continue
                    else:
                        print("❌ Brano non trovato o privo di testo su Chartlyrics.")
                        falliti += 1
                        
            except Exception as e:
                print(f"❌ Errore di rete o brano non trovato: {e}")
                falliti += 1
            
            # Pausa di cortesia tra una richiesta e l'altra
            time.sleep(0.4)

print(f"\n=========================================")
print(f"🎉 AGGIORNAMENTO CHARTLYRICS COMPLETATO!")
print(f"🎵 Testi integrali scritti: {successi}")
print(f"⏭️ Canzoni già complete saltate: {gia_presenti}")
print(f"❌ Canzoni non trovate o fallite: {falliti}")
print(f"=========================================")

try:
    frase = "Ho finito di scaricare i testi da ciart lirical, mio signore!"
    subprocess.run(['spd-say', '-l', 'it', '-t', 'male1', frase])
except Exception as e:
    pass
