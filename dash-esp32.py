import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE FIREBASE ---
# Usa il tuo URL di Firebase. ASSICURATI che finisca con il carattere "/"
FIREBASE_DB_URL = "https://il-tuo-progetto-default-rtdb.europe-west1.firebasedatabase.app/"

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
        st.error(f"Errore nel recupero dati: {e}")
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
    except Exception as e:
        return {}

def update_sensor_name(sensor_id, new_name):
    """Aggiorna il nome di un sensore tramite richiesta REST PUT"""
    try:
        url = f"{FIREBASE_DB_URL}sensor_names/{sensor_id}.json"
        # Firebase accetta stringhe racchiuse tra virgolette nel formato REST
        response = requests.put(url, json=new_name, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.sidebar.error(f"Errore nel salvataggio: {e}")
        return False

# --- INTERFACCIA UTENTE STREAMLIT ---
st.set_page_config(page_title="IoT ESP32 Dashboard", layout="wide")
st.title("🌐 Dashboard Monitoraggio ESP32")
st.write("Monitoraggio in tempo reale e gestione sensori.")

# Caricamento Dati
logs = get_sensor_data()
names_mapping = get_sensor_names()

# Parsing dei dati in un DataFrame flessibile
rows = []
if logs:
    for sensor_id, readings in logs.items():
        if isinstance(readings, dict):
            for timestamp, metrics in readings.items():
                row = {
                    "sensor_id": sensor_id,
                    "display_name": names_mapping.get(sensor_id, sensor_id) if isinstance(names_mapping, dict) else sensor_id,
                    "timestamp": pd.to_datetime(timestamp, unit='s') if (isinstance(timestamp, (int, float)) or (isinstance(timestamp, str) and timestamp.isdigit())) else pd.to_datetime(timestamp)
                }
                if isinstance(metrics, dict):
                    row.update(metrics)
                rows.append(row)

if not rows:
    st.warning("In attesa di dati dagli ESP32... Controlla che l'ESP32 stia inviando dati correttamente.")
    st.info(f"Verifica che il tuo database riceva dati all'indirizzo: {FIREBASE_DB_URL}")
    st.stop()

df = pd.DataFrame(rows)

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
                
                for metric in metrice_cols:
                    if pd.notna(last_read.get(metric)):
                        suffix = "°C" if "temp" in metric.lower() else "%" if "umid" in metric.lower() or "hum" in metric.lower() else " lux" if "lux" in metric.lower() or "lum" in metric.lower() else ""
                        st.metric(label=metric.capitalize(), value=f"{last_read[metric]}{suffix}")

# --- GRAFICI TEMPORALI ---
st.markdown("---")
st.subheader("📈 Andamento Temporale dei Valori")

if not df_filtered.empty and metrice_cols:
    selected_metric = st.selectbox("Seleziona la metrica da analizzare nel grafico", metrice_cols)
    chart_data = df_filtered.pivot_table(index='timestamp', columns='display_name', values=selected_metric)
    st.line_chart(chart_data)
else:
    st.info("Seleziona almeno un sensore per vedere i grafici.")