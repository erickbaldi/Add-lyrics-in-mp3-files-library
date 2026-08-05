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
    print('Uso: python3 prendi_testo_free.py "/percorso/cartella/musica"')
    sys.exit(1)

cartella_radice = sys.argv[1]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 🧹 Nuova funzione di pulizia super tollerante
def pulisci_metadati(testo):
    if not testo:
        return ""
    t = str(testo).strip()
    
    # Rimuove solo l'estensione finale .mp3 (in modo insensibile a maiuscole/minuscole)
    t = re.sub(r'(?i)\.mp3$', '', t)
    
    # Rimuove solo i numeri iniziali di traccia (es: "01 ", "01. ", "01 - ")
    t = re.sub(r'^\d+[\s\.\-_]*', '', t)
    
    # Sostituisce spazi multipli o strani con un singolo spazio standard
    t = re.sub(r'\s+', ' ', t).strip()
    return t

print(f"📁 Inizio scansione con diagnostica in: {cartella_radice}\n")

successi = 0
falliti = 0

# Header simulato per ridurre il rischio di blocchi da parte del server
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

for radice, directory, files in os.walk(cartella_radice):
    for file in files:
        if file.lower().endswith('.mp3'):
            file_mp3 = os.path.join(radice, file)
            print(f"---")
            print(f"🎧 Nome file originale: {file}")
            
            artista_raw = None
            titolo_raw = None
            tags = None
            
            # 1. TENTATIVO: Lettura Tag ID3
            try:
                tags = ID3(file_mp3)
                artista_raw = tags.get('TPE1').text[0] if tags.get('TPE1') else None
                titolo_raw = tags.get('TIT2').text[0] if tags.get('TIT2') else None
                if artista_raw or titolo_raw:
                    print(f"   [Tag ID3 trovati] Artista: {artista_raw} | Titolo: {titolo_raw}")
            except Exception:
                tags = None

            # 2. TENTATIVO: Fallback su nome file o cartella
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
                
                print(f"   [Deducimento] Artista: {artista_raw} | Titolo: {titolo_raw}")

            # Applica la nuova pulizia leggera
            artista_pulito = pulisci_metadati(artista_raw)
            titolo_pulito = pulisci_metadati(titolo_raw)
            
            # STAMPA DI DIAGNOSTICA: Vediamo cosa esce dalla pulizia
            print(f"   [Dopo Pulizia] Artista: '{artista_pulito}' | Titolo: '{titolo_pulito}'")
            
            if not artista_pulito or not titolo_pulito:
                print(f"❌ Errore: Uno dei dati è rimasto vuoto dopo la pulizia. Salto.")
                falliti += 1
                continue

            print(f"🔍 Cerco online: \"{artista_pulito}\" - \"{titolo_pulito}\"")
            
            ricerca_query = f"{artista_pulito} {titolo_pulito}"
            query_encoded = urllib.parse.quote(ricerca_query)
            url = f"https://music.163.com/api/search/get/web?s={query_encoded}&type=1&limit=1"
            
            try:
                req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(req, timeout=20, context=ctx) as response:
                    risposta_web = response.read().decode('utf-8')
                    dati = json.loads(risposta_web)
                    
                    # 🛡️ Controllo di sicurezza: Se l'API restituisce una stringa annidata, decodificala di nuovo
                    if isinstance(dati, str):
                        try:
                            dati = json.loads(dati)
                        except Exception:
                            print(f"❌ Errore API (Risposta in formato stringa non valida): {dati}")
                            falliti += 1
                            continue
                    
                    # Estrazione provvisoria delle canzoni controllando che 'dati' sia un dizionario valido
                    songs = []
                    if isinstance(dati, dict) and dati.get('result'):
                        result_data = dati.get('result')
                        # A volte NetEase restituisce 'result' come stringa JSON
                        if isinstance(result_data, str):
                            try:
                                result_data = json.loads(result_data)
                            except Exception:
                                pass
                        if isinstance(result_data, dict):
                            songs = result_data.get('songs', [])
                    
                    if songs:
                        id_canzone = songs[0].get('id')
                        url_lyrics = f"https://music.163.com/api/song/media?id={id_canzone}"
                        req_lyrics = urllib.request.Request(url_lyrics, headers={'User-Agent': USER_AGENT})
                        
                        with urllib.request.urlopen(req_lyrics, timeout=20, context=ctx) as resp_lyrics:
                            risposta_testo = resp_lyrics.read().decode('utf-8')
                            dati_testo = json.loads(risposta_testo)
                            
                            # Altro controllo di sicurezza per la risposta del testo
                            if isinstance(dati_testo, str):
                                try:
                                    dati_testo = json.loads(dati_testo)
                                except Exception:
                                    pass
                                
                            testo_raw = dati_testo.get('lyric') if isinstance(dati_testo, dict) else None
                            
                            if testo_raw:
                                # Rimuove i timestamp (es. [00:12.34])
                                testo_pulito = re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]', '', testo_raw)
                                testo_pulito = testo_pulito.strip()
                                
                                if len(testo_pulito) > 100:
                                    if tags is None:
                                        try:
                                            tags = ID3(file_mp3)
                                        except Exception:
                                            tags = ID3()
                                        
                                    tags["USLT::eng"] = USLT(encoding=3, lang='eng', desc='', text=testo_pulito)
                                    tags.save(file_mp3)
                                    print("✅ Testo INTEGRALE iniettato!")
                                    successi += 1
                                    continue
                    
                    print("❌ Testo non trovato nel database.")
                    falliti += 1
                        
            except Exception as e:
                print(f"💥 Errore di connessione o elaborazione: {e}")
                falliti += 1
            
            # Un leggero delay per non essere flaggati immediatamente come bot
            time.sleep(1.0)

print(f"\n=========================================")
print(f"🎉 SCANSIONE COMPLETATA!")
print(f"🎵 Testi integrali aggiunti: {successi}")
print(f"❌ Canzoni saltate o fallite: {falliti}")
print(f"=========================================")

try:
    frase = "Ho finito l'analisi, mio signore!"
    subprocess.run(['spd-say', '-l', 'it', '-t', 'male1', frase])
except Exception as e:
    pass
