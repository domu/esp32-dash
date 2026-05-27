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

# --- LAYOUT PRINCIPALE: VALORI ATTUALI (CON CONTENITORI COMPATTI MIN/MAX) ---
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
                    # Contenitore con bordo per delimitare l'area del singolo modulo ESP32
                    with st.container(border=True):
                        st.markdown(f"### 🎯 **{name}**")
                        st.caption(f"⏱️ Ultimo update: {last_read['timestamp'].strftime('%H:%M:%S')}")
                        st.markdown("---")
                        
                        # Mostra dinamicamente tutte le metriche associate (Attuale, Min, Max)
                        for metric in metrice_cols:
                            if pd.notna(last_read.get(metric)):
                                m_lower = metric.lower()
                                suffix = "°C" if "temp" in m_lower else "%" if "umid" in m_lower or "hum" in m_lower else " lux" if "lux" in m_lower or "lum" in m_lower else ""
                                
                                current_val = last_read[metric]
                                max_val = sensor_df[metric].max()
                                min_val = sensor_df[metric].min()
                                
                                st.markdown(f"**{metric.capitalize()}**")
                                sub_col1, sub_col2, sub_col3 = st.columns(3)
                                
                                with sub_col1:
                                    st.metric(label="Attuale", value=f"{current_val}{suffix}")
                                with sub_col2:
                                    st.metric(label="Min", value=f"{min_val}{suffix}")
                                with sub_col3:
                                    st.metric(label="Max", value=f"{max_val}{suffix}")
                                
                            # st.markdown("<div style='margin-bottom: -10px;'></div>", unsafe_html=True)
else:
    st.info("Seleziona almeno un sensore dalla barra laterale per visualizzare i blocchi dati.")

# --- GRAFICI TEMPORALI AVANZATI CON PLOTLY (MOSTRATI TUTTI E 3 CONTEMPORANEAMENTE) ---
st.markdown("---")
st.subheader("📈 Andamento Temporale dei Valori")

if not df_filtered.empty:
    import plotly.graph_objects as go
    
    # Visualizzazione su 3 colonne affiancate per mostrare contemporaneamente i 3 parametri rilevati
    g_cols = st.columns(3)
    
    metrics_to_plot = {
        "temperatura": {"color": "#FF4B4B", "suffix": "°C", "col_idx": 0},
        "umidita": {"color": "#0068C9", "suffix": "%", "col_idx": 1},
        "luminosita": {"color": "#FFABAB", "suffix": " lux", "col_idx": 2}
    }
    
    for metric_name, cfg in metrics_to_plot.items():
        # Cerca la corrispondenza parziale della colonna (case-insensitive)
        actual_col = [c for c in df_filtered.columns if metric_name in c.lower()]
        
        if actual_col:
            m_col = actual_col[0]
            fig = go.Figure()
            
            for sensor_name in df_filtered['display_name'].unique():
                sensor_data = df_filtered[df_filtered['display_name'] == sensor_name].sort_values('timestamp')
                
                # Rimuove righe senza misurazioni valide per la metrica specifica
                sensor_data_clean = sensor_data.dropna(subset=[m_col])
                
                if not sensor_data_clean.empty:
                    # Linea temporale principale
                    fig.add_trace(go.Scatter(
                        x=sensor_data_clean['timestamp'],
                        y=sensor_data_clean[m_col],
                        mode='lines',
                        name=sensor_name,
                        line=dict(width=2)
                    ))
                    
                    # Identificazione indici di picco Massimo e Minimo storici
                    idx_max = sensor_data_clean[m_col].idxmax()
                    idx_min = sensor_data_clean[m_col].idxmin()
                    
                    # Evidenziazione Punto Massimo (Triangolo Verde rivolto verso l'alto)
                    fig.add_trace(go.Scatter(
                        x=[sensor_data_clean.loc[idx_max, 'timestamp']],
                        y=[sensor_data_clean.loc[idx_max, m_col]],
                        mode='markers',
                        name=f"Max {sensor_name}",
                        marker=dict(color='green', size=11, symbol='triangle-up'),
                        hovertemplate=f"Max: %{{y}}{cfg['suffix']}<br>%{{x|%H:%M:%S}}<extra></extra>",
                        showlegend=False
                    ))
                    
                    # Evidenziazione Punto Minimo (Triangolo Rosso rivolto verso il basso)
                    fig.add_trace(go.Scatter(
                        x=[sensor_data_clean.loc[idx_min, 'timestamp']],
                        y=[sensor_data_clean.loc[idx_min, m_col]],
                        mode='markers',
                        name=f"Min {sensor_name}",
                        marker=dict(color='red', size=11, symbol='triangle-down'),
                        hovertemplate=f"Min: %{{y}}{cfg['suffix']}<br>%{{x|%H:%M:%S}}<extra></extra>",
                        showlegend=False
                    ))
            
            # Configurazione estetica dei grafici Plotly interattivi
            fig.update_layout(
                title=f"<b>{m_col.capitalize()}</b>",
                xaxis_title="Orario",
                yaxis_title=cfg['suffix'],
                margin=dict(l=20, r=20, t=40, b=20),
                height=350,
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            with g_cols[cfg['col_idx']]:
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Seleziona almeno un sensore per generare i grafici temporali.")