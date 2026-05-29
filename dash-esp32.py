import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- CONFIGURAZIONE FIREBASE ---
FIREBASE_DB_URL = "https://esp32-dashboard-dpb-default-rtdb.europe-west1.firebasedatabase.app/"

# --- FUNZIONI DI LETTURA E SCRITTURA VIA HTTP ---
def get_sensor_data():
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
    try:
        url = f"{FIREBASE_DB_URL}sensor_names/{sensor_id}.json"
        response = requests.put(url, json=new_name, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.sidebar.error(f"Errore nel salvataggio del nome: {e}")
        return False

def trigger_cam_snapshot():
    try:
        url = f"{FIREBASE_DB_URL}comandi/forza_scatto.json"
        response = requests.put(url, json=True, timeout=5)
        return response.status_code == 200
    except Exception:
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
                parsed_time = None
                try:
                    ts_clean = str(timestamp).strip()
                    if ts_clean.isdigit():
                        ts_val = int(ts_clean)
                        if ts_val > 5000000000:  
                            parsed_time = pd.to_datetime(ts_val, unit='ms')
                        else:  
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

if not rows:
    st.warning("In attesa di dati dagli ESP32... Controlla che l'hardware stia inviando dati correttamente.")
    st.stop()

# Creazione DataFrame principale
df = pd.DataFrame(rows)
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Definizione globale delle colonne metriche
metrice_cols = [c for c in df.columns if c not in ['sensor_id', 'display_name', 'timestamp']]

# --- SIDEBAR: GESTIONE DISPOSITIVI ---
st.sidebar.header("⚙️ Gestione Sensori")
unique_sensors = df['sensor_id'].unique()

st.sidebar.subheader("Rinomina Dispositivi")
selected_id = st.sidebar.selectbox("Seleziona ID ESP32 da rinominare", unique_sensors)
current_name = names_mapping.get(selected_id, selected_id) if isinstance(names_mapping, dict) else selected_id
new_name = st.sidebar.text_input(f"Nuovo nome per {selected_id}", value=current_name)

if st.sidebar.button("Salva Nome"):
    if new_name.strip() and update_sensor_name(selected_id, new_name.strip()):
        st.sidebar.success("Nome aggiornato!")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Filtri Visualizzazione")
selected_display_names = st.sidebar.multiselect(
    "Seleziona i sensori da mostrare",
    options=df['display_name'].unique(),
    default=df['display_name'].unique()
)

# Filtro Selezione dell'intervallo temporale per ottimizzare la leggibilità dei grafici
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Finestra Temporale Grafici")
time_window = st.sidebar.selectbox(
    "Mostra dati degli ultimi:",
    options=["Tutto lo storico", "6 Ore", "12 Ore", "24 Ore", "7 Giorni"],
    index=3  # Default su 24 Ore per evitare il sovraccarico visivo iniziale
)

# Applicazione filtri anagrafici
df_filtered = df[df['display_name'].isin(selected_display_names)]

# Applicazione del filtro sul tempo in base alla scelta dell'utente
if not df_filtered.empty:
    max_time = df_filtered['timestamp'].max()
    if time_window == "6 Ore":
        df_filtered = df_filtered[df_filtered['timestamp'] >= (max_time - timedelta(hours=6))]
    elif time_window == "12 Ore":
        df_filtered = df_filtered[df_filtered['timestamp'] >= (max_time - timedelta(hours=12))]
    elif time_window == "24 Ore":
        df_filtered = df_filtered[df_filtered['timestamp'] >= (max_time - timedelta(hours=24))]
    elif time_window == "7 Giorni":
        df_filtered = df_filtered[df_filtered['timestamp'] >= (max_time - timedelta(days=7))]

df_filtered = df_filtered.sort_values(by='timestamp')

# --- LAYOUT PRINCIPALE: VALORI ATTUALI ---
st.subheader("📍 Ultimi Valori Rilevati")

if selected_display_names:
    sensors_per_row = 3
    for i in range(0, len(selected_display_names), sensors_per_row):
        chunk = selected_display_names[i:i + sensors_per_row]
        cols = st.columns(len(chunk))
        
        for j, name in enumerate(chunk):
            sensor_df = df_filtered[df_filtered['display_name'] == name]
            if not sensor_df.empty:
                last_read = sensor_df.iloc[-1]
                
                with cols[j]:
                    with st.container(border=True):
                        st.markdown(f"### 🎯 **{name}**")
                        st.caption(f"⏱️ Ultimo update: {last_read['timestamp'].strftime('%d/%m %H:%M:%S')}")
                        st.markdown("---")
                        
                        for metric in metrice_cols:
                            if pd.notna(last_read.get(metric)):
                                m_lower = metric.lower()
                                suffix = "°C" if "temp" in m_lower else "%" if "umid" in m_lower or "hum" in m_lower else " lux" if "lux" in m_lower or "lum" in m_lower else ""
                                
                                current_val = last_read[metric]
                                max_val = sensor_df[metric].max()
                                min_val = sensor_df[metric].min()
                                
                                st.markdown(f"**{metric.capitalize()}**")
                                sub_col1, sub_col2, sub_col3 = st.columns(3)
                                with sub_col1: st.metric(label="Attuale", value=f"{current_val}{suffix}")
                                with sub_col2: st.metric(label="Min", value=f"{min_val}{suffix}")
                                with sub_col3: st.metric(label="Max", value=f"{max_val}{suffix}")
else:
    st.info("Seleziona almeno un sensore dalla barra laterale.")

# --- SEZIONE ESP32-CAM IN TEMPO REALE VIA TELEGRAM ---
st.markdown("---")
st.subheader("📷 Controllo Remoto ESP32-CAM")

with st.container(border=True):
    col_info, col_btn = st.columns([2, 1])
    with col_info:
        st.markdown("### **Scatto Istantaneo su Canale Telegram**")
        st.write("Invia un segnale di scatto prioritario all'ESP32-CAM per ricevere l'immagine direttamente sul tuo smartphone.")
    with col_btn:
        if st.button("📸 FORZA SCATTO ORA", use_container_width=True, type="primary"):
            with st.spinner("Invio segnale..."):
                if trigger_cam_snapshot(): st.success("Richiesta inviata! Controlla Telegram.")
                else: st.error("Errore nell'invio del comando.")

# --- GRAFICI TEMPORALI OTTIMIZZATI ED INTELLIGENTI ---
st.markdown("---")
st.subheader("📈 Andamento Temporale dei Valori (Filtro Anti-Folla Attivo)")

if not df_filtered.empty:
    import plotly.graph_objects as go
    g_cols = st.columns(3)
    
    metrics_to_plot = {
        "temperatura": {"suffix": "°C", "col_idx": 0},
        "umidita": {"suffix": "%", "col_idx": 1},
        "luminosita": {"suffix": " lux", "col_idx": 2}
    }
    
    for metric_name, cfg in metrics_to_plot.items():
        actual_col = [c for c in df_filtered.columns if metric_name in c.lower()]
        
        if actual_col:
            m_col = actual_col[0]
            fig = go.Figure()
            
            for sensor_name in df_filtered['display_name'].unique():
                sensor_data = df_filtered[df_filtered['display_name'] == sensor_name].sort_values('timestamp')
                sensor_data_clean = sensor_data.dropna(subset=[m_col])
                
                if not sensor_data_clean.empty:
                    # Calcolo dei picchi reali sul set di dati originale prima di sfoltire la linea grafica
                    idx_max = sensor_data_clean[m_col].idxmax()
                    idx_min = sensor_data_clean[m_col].idxmin()
                    pt_max = sensor_data_clean.loc[idx_max]
                    pt_min = sensor_data_clean.loc[idx_min]

                    # DOWN-SAMPLING INTELLIGENTE: Se ci sono troppi record (es. > 150), calcola la media mobile a blocchi
                    if len(sensor_data_clean) > 150:
                        sensor_data_clean = sensor_data_clean.set_index('timestamp').resample('15Min').mean(numeric_only=True).reset_index()
                        # Ripristina il display_name perso con il resample
                        sensor_data_clean['display_name'] = sensor_name

                    # Disegna la linea dell'andamento pulita e priva di rumore visivo
                    fig.add_trace(go.Scatter(
                        x=sensor_data_clean['timestamp'],
                        y=sensor_data_clean[m_col],
                        mode='lines',
                        name=sensor_name,
                        line=dict(width=2.5)
                    ))
                    
                    # Posiziona i marker dei massimi e minimi reali assoluti
                    fig.add_trace(go.Scatter(
                        x=[pt_max['timestamp']], y=[pt_max[m_col]],
                        mode='markers', name=f"Max {sensor_name}",
                        marker=dict(color='green', size=12, symbol='triangle-up'),
                        hovertemplate=f"Max Reale: %{{y}}{cfg['suffix']}<extra></extra>",
                        showlegend=False
                    ))
                    fig.add_trace(go.Scatter(
                        x=[pt_min['timestamp']], y=[pt_min[m_col]],
                        mode='markers', name=f"Min {sensor_name}",
                        marker=dict(color='red', size=12, symbol='triangle-down'),
                        hovertemplate=f"Min Reale: %{{y}}{cfg['suffix']}<extra></extra>",
                        showlegend=False
                    ))
            
            fig.update_layout(
                title=f"<b>{m_col.capitalize()}</b>",
                xaxis_title="Orario",
                yaxis_title=cfg['suffix'],
                margin=dict(l=20, r=20, t=40, b=20),
                height=380,
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            with g_cols[cfg['col_idx']]:
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Seleziona i sensori per generare i grafici temporali.")