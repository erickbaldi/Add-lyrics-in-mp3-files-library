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
from mutagen.id3 import ID3, USLT

if len(sys.argv) < 2:
    print('Uso corretto: python3 prendi_testo_plain_LRCLIB_PLAIN_e_manda_email.py "/percorso/cartella/musica"')
    sys.exit(1)

cartella_radice = sys.argv[1]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Funzione per ripulire i testi prima di inviarli all'API
def pulisci_testo(testo):
    if not testo:
        return ""
    t = str(testo).strip()
    # Rimuove numeri iniziali (es: "01. ", "12 - ")
    t = re.sub(r'^\d+[\s\.\-_]*', '', t)
    # Rimuove scritte tra parentesi tonde o quadre
    t = re.sub(r'\([^)]*\)', '', t)
    t = re.sub(r'\[[^\]]*\]', '', t)
    # Rimuove l'estensione .mp3 se presente nel testo
    t = re.sub(r'(?i)\.mp3$', '', t)
    # Pulisce spazi doppi e bordi
    t = re.sub(r'\s+', ' ', t).strip()
    return t

# Funzione per inviare l'email con il riepilogo
def invia_email(successi, gia_presenti, falliti):
    # --- CONFIGURAZIONE SMTP (Esempio con Gmail o servizi Free come Brevo/SendGrid) ---
    SMTP_SERVER = "smtp.gmail.com"  # Modifica con il tuo provider (es. smtp.sendgrid.net, smtp-relay.brevo.com)
    SMTP_PORT = 587                 # Di solito 587 per STARTTLS
    EMAIL_MITTENTE = "erick.baldi.eb@gmail.com"
    EMAIL_DESTINATARIO = "erickbaldi@yahoo.it"
    PASSWORD = "hoae qumd tipq txjg"  # Se usi Gmail, genera una "Password per le app" dalle impostazioni Google
    
    # Costruzione del messaggio
    messaggio = MIMEMultipart()
    messaggio['From'] = EMAIL_MITTENTE
    messaggio['To'] = EMAIL_DESTINATARIO
    messaggio['Subject'] = "Server Linux Peppermint Erick 🎵 Aggiornamento Testi MP3 PLAIN Completato!"
    
    corpo_testo = f"""
    Ciao,
    Il processo di scansione e iniezione dei testi MP3 in modalità PLAIN è terminato.
    
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
        # Connessione al server SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Attiva la crittografia
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
            print(f"---")
            print(f"🎧 Analizzo file: {file}")
            
            artista_raw = None
            titolo_raw = None
            tags = None
            
            # 1. TENTATIVO: Legge i tag ID3 interni
            try:
                tags = ID3(file_mp3)
                artista_raw = tags.get('TPE1').text[0] if tags.get('TPE1') else None
                titolo_raw = tags.get('TIT2').text[0] if tags.get('TIT2') else None
            except Exception:
                # Se il file non ha proprio una struttura ID3, la inizializziamo vuota per dopo
                tags = None

            # 2. TENTATIVO (Fallback): Se i tag sono vuoti, deduce dal nome del file o cartella
            if not artista_raw or not titolo_raw:
                print("ℹ️ Tag ID3 mancanti o incompleti. Tento di indovinare dal nome del file...")
                nome_file_senza_est = os.path.splitext(file)[0]
                
                if "-" in nome_file_senza_est:
                    # Se c'è un trattino, spezza in due (es: "Aerosmith - Sweet Emotion" o "06 - Aerosmith - Sweet Emotion")
                    parti = [p.strip() for p in nome_file_senza_est.split("-")]
                    if len(parti) >= 2:
                        # Se la prima parte è solo un numero di traccia, la scarta
                        if parti[0].isdigit() and len(parti) > 2:
                            artista_raw = parti[1]
                            titolo_raw = " ".join(parti[2:])
                        else:
                            artista_raw = parti[0]
                            titolo_raw = " ".join(parti[1:])
                
                # Se ancora non ha trovato l'artista, usa il nome della cartella in cui si trova il file
                if not artista_raw:
                    artista_raw = os.path.basename(radice)
                if not titolo_raw:
                    titolo_raw = nome_file_senza_est

            # Controlla se siamo riusciti a ottenere qualcosa
            if not artista_raw or not titolo_raw:
                print(f"❌ Impossibile determinare Artista/Titolo in nessun modo. Salto.")
                falliti += 1
                continue
                
            # Controllo se il testo è già presente (per non sprecare traffico internet)
            if tags and "USLT::eng" in tags:
                print(f"⏭️ Il testo è già presente in questo file. Salto.")
                gia_presenti += 1
                continue
            
            # Applica i filtri di pulizia
            artista_pulito = pulisci_testo(artista_raw)
            titolo_pulito = pulisci_testo(titolo_raw)
            
            if not artista_pulito or not titolo_pulito:
                print(f"⚠️ Dati estratti troppo corti o non validi dopo la pulizia. Salto.")
                falliti += 1
                continue

            print(f"🔍 Cerco online: \"{artista_pulito}\" - \"{titolo_pulito}\"")
            
            artista_encoded = urllib.parse.quote(artista_pulito)
            titolo_encoded = urllib.parse.quote(titolo_pulito)
            url = f"https://lrclib.net/api/search?artist_name={artista_encoded}&track_name={titolo_encoded}"
            
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                    dati = json.loads(response.read().decode('utf-8'))
                    
                    if dati and len(dati) > 0:
                        testo = dati[0].get('plainLyrics')
                        
                        if testo:
                            # Se l'MP3 non aveva una struttura ID3 valida, la creiamo da zero ora
                            if tags is None:
                                tags = ID3()
                            
                            # Inietta il testo
                            tags["USLT::eng"] = USLT(encoding=3, lang='eng', desc='', text=testo)
                            tags.save(file_mp3)
                            print("✅ Testo iniettato con successo!")
                            successi += 1
                        else:
                            print("⚠️ Canzone trovata, ma non ha un testo associato.")
                            falliti += 1
                    else:
                        print("❌ Testo non trovato su LRCLIB.")
                        falliti += 1
                        
            except Exception as e:
                print(f"💥 Errore di rete su questo file: {e}")
                falliti += 1
            
            time.sleep(0.5)

print(f"\n=========================================")
print(f"🎉 SCANSIONE COMPLETATA CON LOGICA INTELLIGENTE!")
print(f"🎵 Testi aggiunti: {successi}")
print(f"⏭️ Canzoni già aggiornate: {gia_presenti}")
print(f"❌ Canzoni saltate o non trovate: {falliti}")
print(f"=========================================")

# 🗣️ NUOVA VOCE FINALE CON SPD-SAY
try:
    frase = "Ho finito di eseguire il tuo comando, mio signore!"
    subprocess.run(['spd-say', '-l', 'it', '-t', 'male1', frase])
except Exception as e:
    print(f"⚠️ Impossibile riprodurre l'audio con spd-say: {e}")

# 📧 INVIO NOTIFICA EMAIL
invia_email(successi, gia_presenti, falliti)
