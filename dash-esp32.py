import streamlit as st
import pandas as pd
import requests

# --- CONFIGURAZIONE FIREBASE ---
# Usa il tuo URL di Firebase. ASSICURATI che finisca con il carattere "/"
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
                # --- PARSING ROBUSTO DEL TIMESTAMP ---
                parsed_time = None
                try:
                    # Rimuove eventuali spazi se è una stringa
                    ts_clean = str(timestamp).strip()
                    
                    if ts_clean.isdigit():
                        ts_val = int(ts_clean)
                        # Se ha 13 o più cifre è in millisecondi (es. JavaScript/Firebase standard)
                        if ts_val > 5000000000:
                            parsed_time = pd.to_datetime(ts_val, unit='ms')
                        else:
                            parsed_time = pd.to_datetime(ts_val, unit='s')
                    else:
                        # Prova il parsing come stringa di data standard (es. "2026-05-27 15:00:00")
                        parsed_time = pd.to_datetime(ts_clean)
                except Exception:
                    # Se fallisce tutto, usa l'orario di sistema attuale per non far crashare l'app
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

# --- LAYOUT PRINCIPALE: VALORI ATTUALI (CON MIN/MAX) ---
st.subheader("📍 Ultimi Valori Rilevati")

# Crea una griglia di card ben delimitate per ogni sensore selezionato
if selected_display_names:
    # Mostriamo al massimo 3 sensori per riga per mantenere il layout compatto e leggibile
    sensors_per_row = 3
    for i in range(0, len(selected_display_names), sensors_per_row):
        chunk = selected_display_names[i:i + sensors_per_row]
        cols = st.columns(len(chunk))
        
        for j, name in enumerate(chunk):
            sensor_df = df_filtered[df_filtered['display_name'] == name]
            if not sensor_df.empty:
                last_read = sensor_df.iloc[-1]
                
                with cols[j]:
                    # Contenitore con bordo per delimitare chiaramente l'area del sensore
                    with st.container(border=True):
                        st.markdown(f"### 🎯 **{name}**")
                        st.caption(f"⏱️ Ultimo update: {last_read['timestamp'].strftime('%H:%M:%S')}")
                        st.markdown("---")
                        
                        # Ciclo dinamico sulle metriche presenti (Temperatura, Umidità, Luminosità...)
                        for metric in metrice_cols:
                            if pd.notna(last_read.get(metric)):
                                # Identifica il suffisso corretto per l'unità di misura
                                m_lower = metric.lower()
                                suffix = "°C" if "temp" in m_lower else "%" if "umid" in m_lower or "hum" in m_lower else " lux" if "lux" in m_lower or "lum" in m_lower else ""
                                
                                # Calcolo statistico sul momento per il sensore specifico
                                current_val = last_read[metric]
                                max_val = sensor_df[metric].max()
                                min_val = sensor_df[metric].min()
                                
                                # Layout compatto su 3 micro-colonne all'interno dell'area delimitata
                                st.markdown(f"**{metric.capitalize()}**")
                                sub_col1, sub_col2, sub_col3 = st.columns(3)
                                
                                with sub_col1:
                                    st.metric(label="Attuale", value=f"{current_val}{suffix}")
                                with sub_col2:
                                    st.metric(label="Min", value=f"{min_val}{suffix}")
                                with sub_col3:
                                    st.metric(label="Max", value=f"{max_val}{suffix}")
                                
                                st.markdown("<div style='margin-bottom: -10px;'></div>", unsafe_html=True)
else:
    st.info("Seleziona almeno un sensore dalla barra laterale per visualizzare i dati.")
# --- GRAFICI TEMPORALI AVANZATI (PLOTLY) ---
st.markdown("---")
st.subheader("📈 Andamento Temporale dei Valori")

if not df_filtered.empty:
    import plotly.graph_objects as go
    
    # Creiamo 3 colonne per mostrare i 3 grafici affiancati (se lo schermo è grande)
    # Se preferisci vederli uno sotto l'altro, basta togliere le colonne e usare st.plotly_chart di seguito
    g_cols = st.columns(3)
    
    # Definiamo le metriche da tracciare e i loro colori/simboli
    metrics_to_plot = {
        "temperatura": {"color": "#FF4B4B", "suffix": "°C", "col_idx": 0},
        "umidita": {"color": "#0068C9", "suffix": "%", "col_idx": 1},
        "luminosita": {"color": "#FFABAB", "suffix": " lux", "col_idx": 2}
    }
    
    for metric_name, cfg in metrics_to_plot.items():
        # Verifichiamo se la metrica esiste effettivamente nei dati inviati
        actual_col = [c for c in df_filtered.columns if metric_name in c.lower()]
        
        if actual_col:
            m_col = actual_col[0]
            
            # Creiamo il grafico Plotly
            fig = go.Figure()
            
            # Tracciamo le linee per ogni sensore selezionato
            for sensor_name in df_filtered['display_name'].unique():
                sensor_data = df_filtered[df_filtered['display_name'] == sensor_name].sort_values('timestamp')
                
                if not sensor_data[m_col].dropna().empty:
                    # Linea principale del grafico
                    fig.add_trace(go.Scatter(
                        x=sensor_data['timestamp'],
                        y=sensor_data[m_col],
                        mode='lines',
                        name=sensor_name,
                        line=dict(width=2)
                    ))
                    
                    # Identifichiamo l'indice del valore Massimo e Minimo
                    idx_max = sensor_data[m_col].idxmax()
                    idx_min = sensor_data[m_col].idxmin()
                    
                    # Punto di Massimo (Triangolo in su Verde)
                    fig.add_trace(go.Scatter(
                        x=[sensor_data.loc[idx_max, 'timestamp']],
                        y=[sensor_data.loc[idx_max, m_col]],
                        mode='markers',
                        name=f"Max {sensor_name}",
                        marker=dict(color='green', size=11, symbol='triangle-up'),
                        hovertemplate=f"Max: %{{y}}{cfg['suffix']}<br>%{{x|%H:%M:%S}}<extra></extra>",
                        showlegend=False
                    ))
                    
                    # Punto di Minimo (Triangolo in giù Rosso)
                    fig.add_trace(go.Scatter(
                        x=[sensor_data.loc[idx_min, 'timestamp']],
                        y=[sensor_data.loc[idx_min, m_col]],
                        mode='markers',
                        name=f"Min {sensor_name}",
                        marker=dict(color='red', size=11, symbol='triangle-down'),
                        hovertemplate=f"Min: %{{y}}{cfg['suffix']}<br>%{{x|%H:%M:%S}}<extra></extra>",
                        showlegend=False
                    ))
            
            # Configurazione del layout grafico (Margini, titoli e interattività)
            fig.update_layout(
                title=f"<b>{m_col.capitalize()}</b>",
                xaxis_title="Orario",
                yaxis_title=cfg['suffix'],
                margin=dict(l=20, r=20, t=40, b=20),
                height=350,
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            # Pubblichiamo il grafico nella rispettiva colonna della dashboard
            with g_cols[cfg['col_idx']]:
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Seleziona almeno un sensore per generare i grafici temporali.")