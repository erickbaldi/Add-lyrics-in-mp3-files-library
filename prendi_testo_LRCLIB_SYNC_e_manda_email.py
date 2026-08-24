import os
import sys
import urllib.request
import urllib.parse
import json
import ssl
import time
import re
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mutagen.id3 import ID3, SYLT, ID3NoHeaderError

if len(sys.argv) < 2:
    print('Uso: python3 prendi_testo_tutti_new.py "/percorso/cartella/musica"')
    sys.exit(1)

cartella_radice = sys.argv[1]

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

def parse_lrc(lrc_string):
    """
    Converte una stringa LRC in una lista di tuple (testo, timestamp_ms)
    garantendo che ogni elemento sia esattamente una tupla di 2 elementi.
    """
    sylt_data = []
    linee = lrc_string.splitlines()
    for linea in linee:
        # Regex per catturare timestamp [mm:ss.xx] o [mm:ss.xxx]
        match = re.match(r'\[(\d+):(\d+)(?:\.(\d+))?\](.*)', linea)
        if match:
            minuti = int(match.group(1))
            secondi = int(match.group(2))
            
            # Gestione millesimi/centesimi
            ms_str = match.group(3) or "0"
            if len(ms_str) == 2:
                millesimi = int(ms_str) * 10
            elif len(ms_str) == 1:
                millesimi = int(ms_str) * 100
            else:
                millesimi = int(ms_str[:3])
                
            totale_ms = (minuti * 60 + secondi) * 1000 + millesimi
            testo_riga = match.group(4).strip()
            
            # Mutagen SYLT si aspetta (testo_stringa, ms_int)
            sylt_data.append((str(testo_riga), int(totale_ms)))
            
    return sylt_data

def invia_email(successi, gia_presenti, falliti):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    EMAIL_MITTENTE = "erick.baldi.eb@gmail.com"
    EMAIL_DESTINATARIO = "erickbaldi@yahoo.it"
    PASSWORD = "hoae qumd tipq txjg"
    
    messaggio = MIMEMultipart()
    messaggio['From'] = EMAIL_MITTENTE
    messaggio['To'] = EMAIL_DESTINATARIO
    messaggio['Subject'] = "Server Linux Peppermint Erick 🎵 Aggiornamento Testi MP3 Completato!"
    
    corpo_testo = f"""
    Ciao,
    Il processo di scansione e iniezione dei testi MP3 è terminato.
    
    Ecco il riepilogo finale:
    ---------------------------------------------------------
    🎵 Testi aggiunti: {successi}
    ⏭️ Canzoni già aggiornate: {gia_presenti}
    ❌ Canzoni saltate o non trovate: {falliti}
    ---------------------------------------------------------
    
    Buon ascolto!
    Erick
    """
    
    messaggio.attach(MIMEText(corpo_testo, 'plain', 'utf-8'))
    
    try:
        print("\n📧 Invio dell'email di notifica in corso...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_MITTENTE, PASSWORD)
        server.sendmail(EMAIL_MITTENTE, EMAIL_DESTINATARIO, messaggio.as_string())
        server.quit()
        print("✅ Email inviata con successo!")
    except Exception as e:
        print(f"❌ Impossibile inviare l'email: {e}")

print(f"📁 Inizio scansione avanzata (Tag ID3 + Fallback su Nome File) in: {cartella_radice}\n")

successi = 0
falliti = 0
gia_presenti = 0

for radice, directory, files in os.walk(cartella_radice):
    for file in files:
        if file.lower().endswith('.mp3'):
            file_mp3 = os.path.join(radice, file)
            print("---")
            print(f"🎧 Analizzo file: {file}")
            
            artista_raw = None
            titolo_raw = None
            tags = None
            
            try:
                tags = ID3(file_mp3)
                artista_raw = tags.get('TPE1').text[0] if tags.get('TPE1') else None
                titolo_raw = tags.get('TIT2').text[0] if tags.get('TIT2') else None
            except (ID3NoHeaderError, Exception):
                tags = None

            if not artista_raw or not titolo_raw:
                print("ℹ️ Tag ID3 mancanti o incompleti. Tento di indovinare dal nome del file...")
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
                print("❌ Impossibile determinare Artista/Titolo in nessun modo. Salto.")
                falliti += 1
                continue
                
            if tags and "SYLT::eng" in tags:
                print("⏭️ Il testo è già presente in questo file. Salto.")
                gia_presenti += 1
                continue
            
            artista_pulito = pulisci_testo(artista_raw)
            titolo_pulito = pulisci_testo(titolo_raw)
            
            if not artista_pulito or not titolo_pulito:
                print("⚠️ Dati estratti troppo corti o non validi dopo la pulizia. Salto.")
                falliti += 1
                continue

            print(f'🔍 Cerco online: "{artista_pulito}" - "{titolo_pulito}"')
            
            artista_encoded = urllib.parse.quote(artista_pulito)
            titolo_encoded = urllib.parse.quote(titolo_pulito)
            url = f"https://lrclib.net/api/search?artist_name={artista_encoded}&track_name={titolo_encoded}"
            
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                    dati = json.loads(response.read().decode('utf-8'))
                    
                    if dati and len(dati) > 0:
                        testo_lrc = dati[0].get('syncedLyrics')
                        
                        if testo_lrc:
                            if tags is None:
                                try:
                                    tags = ID3(file_mp3)
                                except ID3NoHeaderError:
                                    tags = ID3()
                            
                            sylt_tuples = parse_lrc(testo_lrc)
                            if sylt_tuples:
                                # Iniezione corretta con frame SYLT
                                tags.setall("SYLT", [
                                    SYLT(
                                        encoding=3,     # UTF-8
                                        lang='eng',     # Lingua
                                        format=2,       # Format 2 = timestamp espresso in millisecondi
                                        type=1,         # Type 1 = Testo/Lyrics
                                        desc='',
                                        text=sylt_tuples
                                    )
                                ])
                                tags.save(file_mp3)
                                print("✅ Testo iniettato con successo!")
                                successi += 1
                            else:
                                print("⚠️ Impossibile interpretare le righe del testo sincronizzato.")
                                falliti += 1
                        else:
                            print("⚠️ Canzone trovata, ma non ha un testo sincronizzato.")
                            falliti += 1
                    else:
                        print("❌ Testo non trovato su LRCLIB.")
                        falliti += 1
                        
            except Exception as e:
                print(f"💥 Errore durante l'elaborazione del file: {e}")
                falliti += 1
            
            time.sleep(0.5)

print("\n=========================================")
print("🎉 SCANSIONE COMPLETATA CON LOGICA INTELLIGENTE!")
print(f"🎵 Testi aggiunti: {successi}")
print(f"⏭️ Canzoni già aggiornate: {gia_presenti}")
print(f"❌ Canzoni saltate o non trovate: {falliti}")
print("=========================================")

try:
    frase = "Ho finito di eseguire il tuo comando, mio signore!"
    subprocess.run(['spd-say', '-l', 'it', '-t', 'male1', frase])
except Exception as e:
    print(f"⚠️ Impossibile riprodurre l'audio con spd-say: {e}")

invia_email(successi, gia_presenti, falliti)

