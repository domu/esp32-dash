import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE FIREBASE ---
# URL del database Realtime di Firebase registrato per il progetto
FIREBASE_DB_URL = "https://esp32-dashboard-dpb-default-rtdb.europe-west1.firebasedatabase.app/"

# --- FUNZIONI DI LETTURA E SCRITTURA VIA HTTP ---
def get_sensor_data():
    """Legge lo storico dei dati dei sensori tramite richiesta REST GET"""
    try:
        url = f"{FIREBASE_DB_URL}sensor_logs.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data if data else {}
        return {}
    except Exception as e:
        st.error(f"Errore nel recupero dati storici: {e}")
        return {}

def get_sensor_names():
    """Legge i nomi personalizzati tramite richiesta REST GET"""
    try:
        url = f"{FIREBASE_DB_URL}sensor_names.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data if data else {}
        return {}
    except Exception:
        return {}

def update_sensor_name(sensor_id, new_name):
    """Aggiorna il nome di un sensore tramite richiesta REST PUT"""
    try:
        url = f"{FIREBASE_DB_URL}sensor_names/{sensor_id}.json"
        response = requests.put(url, json=new_name, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.sidebar.error(f"Errore nel salvataggio del nome: {e}")
        return False

# --- INTERFACCIA UTENTE STREAMLIT ---
st.set_page_config(page_title="IoT ESP32 Dashboard", layout="wide")
st.title("🌐 Dashboard Monitoraggio ESP32")
st.write("Monitoraggio in tempo reale e gestione avanzata dei sensori IoT.")

# Caricamento iniziale dei Dati da Firebase
logs = get_sensor_data()
names_mapping = get_sensor_names()

# Parsing dei dati strutturati in un DataFrame flessibile
rows = []
if logs:
    for sensor_id, readings in logs.items():
        if isinstance(readings, dict):
            for timestamp, metrics in readings.items():
                # Parsing robusto del timestamp per evitare conflitti con stringhe o millisecondi
                parsed_time = None
                try:
                    ts_clean = str(timestamp).strip()
                    if ts_clean.isdigit():
                        ts_val = int(ts_clean)
                        if ts_val > 5000000000:  # Formato in millisecondi (es. JS timestamp)
                            parsed_time = pd.to_datetime(ts_val, unit='ms')
                        else:  # Formato Unix epoch standard in secondi
                            parsed_time = pd.to_datetime(ts_val, unit='s')
                    else:
                        parsed_time = pd.to_datetime(ts_clean)
                except Exception:
                    parsed_time = pd.Timestamp.now()

                row = {
                    "sensor_id": sensor_id,
                    "display_name": names_mapping.get(sensor_id, sensor_id) if isinstance(names_mapping, dict) else sensor_id,
                    "timestamp": parsed_time
                }
                if isinstance(metrics, dict):
                    row.update(metrics)
                rows.append(row)

# Controllo se ci sono dati nel database
if not rows:
    st.warning("In attesa di dati dagli ESP32... Controlla che l'hardware stia inviando dati correttamente.")
    st.info(f"Verifica che il tuo database riceva i record all'indirizzo console o tramite i log dell'ESP32.")
    st.stop()

# 1. Creazione del DataFrame principale
df = pd.DataFrame(rows)

# 2. Definizione globale delle colonne metriche rilevate (es. temperatura, umidita, luminosita)
metrice_cols = [c for c in df.columns if c not in ['sensor_id', 'display_name', 'timestamp']]

# --- SIDEBAR: GESTIONE E RINOMINA SENSORI ---
st.sidebar.header("⚙️ Gestione Sensori")

unique_sensors = df['sensor_id'].unique()

st.sidebar.subheader("Rinomina Dispositivi")
selected_id = st.sidebar.selectbox("Seleziona ID ESP32 da rinominare", unique_sensors)
current_name = names_mapping.get(selected_id, selected_id) if isinstance(names_mapping, dict) else selected_id
new_name = st.sidebar.text_input(f"Nuovo nome per {selected_id}", value=current_name)

if st.sidebar.button("Salva Nome"):
    if new_name.strip():
        if update_sensor_name(selected_id, new_name.strip()):
            st.sidebar.success(f"Configurato correttamente: {selected_id} -> {new_name}")
            st.rerun()

# Filtro Selezione Visualizzazione nella Barra Laterale
st.sidebar.markdown("---")
st.sidebar.subheader("Filtri Visualizzazione")
selected_display_names = st.sidebar.multiselect(
    "Seleziona i sensori da mostrare",
    options=df['display_name'].unique(),
    default=df['display_name'].unique()
)

# Filtraggio e ordinamento temporale dei dati in base alla selezione dell'utente
df_filtered = df[df['display_name'].isin(selected_display_names)].sort_values(by='timestamp')