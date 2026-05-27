import streamlit as st
import pandas as pd
from firebase_admin import credentials, db, initialize_app, _apps
import google.auth.credentials

# --- CONFIGURAZIONE FIREBASE ---
# Assicurati che questo sia il tuo URL corretto
FIREBASE_DB_URL = "https://esp32-dashboard-dpb-default-rtdb.europe-west1.firebasedatabase.app/"

@st.cache_resource
def init_firebase():
    if not _apps:
        # Usiamo le credenziali anonime native di firebase_admin per la modalità di test
        cred = credentials.Anonymous()
        
        initialize_app(cred, {
            'databaseURL': FIREBASE_DB_URL,
            'httpTimeout': 10
        })

try:
    init_firebase()
except Exception as e:
    st.error(f"Errore di connessione a Firebase: {e}")

# --- FUNZIONI DI LETTURA E SCRITTURA ---
def get_sensor_data():
    """Legge lo storico dei dati dei sensori"""
    ref = db.reference('sensor_logs')
    data = ref.get()
    return data if data else {}

def get_sensor_names():
    """Legge i record dei nomi personalizzati associati agli ID"""
    ref = db.reference('sensor_names')
    names = ref.get()
    return names if names else {}

def update_sensor_name(sensor_id, new_name):
    """Aggiorna il nome di un sensore"""
    ref = db.reference(f'sensor_names/{sensor_id}')
    ref.set(new_name)

# --- INTERFACCIA UTENTE STREAMLIT ---
st.set_page_config(page_title="IoT ESP32 Dashboard", layout="wide")
st.title("🌐 Dashboard Monitoraggio ESP32")
st.write("Monitoraggio in tempo reale e gestione sensori.")

# Caricamento Dati
logs = get_sensor_data()
names_mapping = get_sensor_names()

# Parsing dei dati in un DataFrame flessibile
rows = []
for sensor_id, readings in logs.items():
    for timestamp, metrics in readings.items():
        row = {
            "sensor_id": sensor_id,
            "display_name": names_mapping.get(sensor_id, sensor_id),
            "timestamp": pd.to_datetime(timestamp, unit='s') if isinstance(timestamp, (int, float)) else pd.to_datetime(timestamp)
        }
        # Inserisce dinamicamente qualsiasi metrica inviata dall'ESP32 (temp, hum, lux, ecc.)
        if isinstance(metrics, dict):
            row.update(metrics)
        rows.append(row)

if not rows:
    st.warning("In attesa di dati dagli ESP32... Controlla la configurazione del database.")
    st.stop()

df = pd.DataFrame(rows)

# --- SIDEBAR: GESTIONE E RINOMINA SENSORI ---
st.sidebar.header("⚙️ Gestione Sensori")

# Lista dei sensori unici rilevati nel database
unique_sensors = df['sensor_id'].unique()

st.sidebar.subheader("Rinomina Dispositivi")
selected_id = st.sidebar.selectbox("Seleziona ID ESP32 da rinominare", unique_sensors)
current_name = names_mapping.get(selected_id, selected_id)
new_name = st.sidebar.text_input(f"Nuovo nome per {selected_id}", value=current_name)

if st.sidebar.button("Salva Nome"):
    if new_name.strip():
        update_sensor_name(selected_id, new_name.strip())
        st.sidebar.success(f"Configurato: {selected_id} -> {new_name}")
        st.rerun()

# Filtro Selezione Visualizzazione
st.sidebar.markdown("---")
st.sidebar.subheader("Filtri Visualizzazione")
selected_display_names = st.sidebar.multiselect(
    "Seleziona i sensori da mostrare",
    options=df['display_name'].unique(),
    default=df['display_name'].unique()
)

# Filtraggio del DataFrame
df_filtered = df[df['display_name'].isin(selected_display_names)].sort_values(by='timestamp')

# --- LAYOUT PRINCIPALE: VALORI ATTUALI ---
st.subheader("📍 Ultimi Valori Rilevati")
cols = st.columns(len(selected_display_names) if selected_display_names else 1)

# Identifica le metriche disponibili escludendo le colonne di servizio
metrice_cols = [c for c in df.columns if c not in ['sensor_id', 'display_name', 'timestamp']]

for i, name in enumerate(selected_display_names):
    sensor_df = df_filtered[df_filtered['display_name'] == name]
    if not sensor_df.empty:
        last_read = sensor_df.iloc[-1]
        with cols[i % len(cols)]:
            st.card = st.container(border=True)
            with st.card:
                st.markdown(f"### **{name}**")
                st.caption(f"Ultimo aggiornamento: {last_read['timestamp'].strftime('%H:%M:%S')}")
                
                # Mostra dinamicamente tutte le metriche presenti
                for metric in metrice_cols:
                    if pd.notna(last_read.get(metric)):
                        suffix = "°C" if "temp" in metric.lower() else "%" if "umid" in metric.lower() or "hum" in metric.lower() else " lux" if "lux" in metric.lower() or "lum" in metric.lower() else ""
                        st.metric(label=metric.capitalize(), value=f"{last_read[metric]}{suffix}")

# --- GRAFICI TEMPORALI ---
st.markdown("---")
st.subheader("📈 Andamento Temporale dei Valori")

if not df_filtered.empty and metrice_cols:
    selected_metric = st.selectbox("Seleziona la metrica da analizzare nel grafico", metrice_cols)
    
    # Pivot per il grafico: asse X = timestamp, colonne = i vari sensori, valori = la metrica scelta
    chart_data = df_filtered.pivot_table(index='timestamp', columns='display_name', values=selected_metric)
    
    st.line_chart(chart_data)
else:
    st.info("Seleziona almeno un sensore per vedere i grafici.")