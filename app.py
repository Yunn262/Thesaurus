import streamlit as st
import pandas as pd
import numpy as np
import ccxt
import io, base64
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="🚀 Bot Trading Pro — Alertas Ativos", layout="wide")

# =================== CSS ===================
st.markdown("""
<style>
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.6); }
  70% { box-shadow: 0 0 20px 10px rgba(0, 255, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }
}
.pulse-green { animation: pulse 1.5s infinite; }
.pulse-red { animation: pulse 1.5s infinite; }
</style>
""", unsafe_allow_html=True)

# =================== FUNÇÕES ===================
@st.cache_data(ttl=300)
def fetch_data(symbol, exchange_name='binance', timeframe='15m', limit=200):
    exchange = getattr(ccxt, exchange_name)({'enableRateLimit': True})
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['ts','open','high','low','close','volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('ts', inplace=True)
    return df

# ================= INDICADORES =================

def indicators(df):

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0,0)).rolling(14).mean()
    loss = (-delta.where(delta < 0,0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100/(1+rs))

    # CCI
    tp = (df['high']+df['low']+df['close'])/3
    ma = tp.rolling(20).mean()
    md = tp.rolling(20).apply(lambda x: np.mean(np.abs(x-np.mean(x))))
    df['CCI'] = (tp-ma)/(0.015*md)

    # Bollinger
    ma = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['bb_upper'] = ma + (2*std)
    df['bb_lower'] = ma - (2*std)

    # Stochastic
    low14 = df['low'].rolling(14).min()
    high14 = df['high'].rolling(14).max()
    df['stoch'] = 100*((df['close']-low14)/(high14-low14))

    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['MACD'] = ema12 - ema26

    return df

# =================== ALERTA ===================
sound_up_b64 = "UklGRigAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQgAAAAA"
sound_down_b64 = "UklGRigAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQgAAAAA"

def play_sound(sound_b64):
    audio_bytes = base64.b64decode(sound_b64)
    st.audio(io.BytesIO(audio_bytes), format="audio/wav", start_time=0)

def show_signal_alert(signal: str, confidence: float, min_conf: float = 70):
    color_map = {"SUBIDA 🔼": "#1db954", "DESCIDA 🔽": "#e63946", "NEUTRAL ⚪": "#6c757d"}
    pulse_class = "pulse-green" if "SUBIDA" in signal else "pulse-red" if "DESCIDA" in signal else ""
    color = color_map.get(signal, "#6c757d")

    st.markdown(
        f"""
        <div class="{pulse_class}" style='background-color:{color};
        padding:1.3rem;border-radius:1rem;text-align:center;
        color:white;font-size:1.6rem;'>
        <b>{signal}</b><br>
        Confiança: {confidence:.2f}%
        </div>
        """,
        unsafe_allow_html=True,
    )

    if confidence >= min_conf:
        if "SUBIDA" in signal:
            play_sound(sound_up_b64)
        elif "DESCIDA" in signal:
            play_sound(sound_down_b64)

# =================== INTERFACE ===================
st.title("🚀 Bot Trading Pro — Alerta Visual & Sonoro")

symbol = st.sidebar.text_input("Símbolo (ex: BTC/USDT)", "BTC/USDT")
exchange_name = st.sidebar.selectbox("Exchange", ["binance", "coinbase", "kraken", "kucoin"])
timeframe = st.sidebar.selectbox("Timeframe", ["5m","15m","1h","4h","1d"])

confidence_threshold = st.sidebar.slider("🔉 Nível mínimo de confiança p/ alerta", 50, 100, 75, 1)

auto_refresh = st.sidebar.checkbox("Atualizar automaticamente", value=False)
interval = st.sidebar.number_input("Intervalo (s)", min_value=10, max_value=300, value=60)

# ===== MENU DE OPERAÇÃO =====
mode = st.sidebar.radio(
"Modo de Operação",
["Operação Normal", "Operar com Estratégias"]
)

# Atualização
if auto_refresh:
    st_autorefresh(interval=interval * 1000, key="data_refresh")

# =================== EXECUÇÃO ===================

if st.button("Analisar mercado") or auto_refresh:

    with st.spinner("Analisando mercado..."):

        df = fetch_data(symbol, exchange_name, timeframe)

        if mode == "Operar com Estratégias":
            df = indicators(df)

            last = df.iloc[-1]

            score_up = 0
            score_down = 0

            if last["RSI"] < 30:
                score_up += 1
            if last["RSI"] > 70:
                score_down += 1

            if last["CCI"] < -100:
                score_up += 1
            if last["CCI"] > 100:
                score_down += 1

            if last["close"] < last["bb_lower"]:
                score_up += 1
            if last["close"] > last["bb_upper"]:
                score_down += 1

            if last["stoch"] < 20:
                score_up += 1
            if last["stoch"] > 80:
                score_down += 1

            if last["MACD"] > 0:
                score_up += 1
            else:
                score_down += 1

            if score_up > score_down:
                signal = "SUBIDA 🔼"
            elif score_down > score_up:
                signal = "DESCIDA 🔽"
            else:
                signal = "NEUTRAL ⚪"

            confidence = (max(score_up, score_down)/5)*100

        else:

            last_price = df['close'].iloc[-1]
            pred_price = last_price * (1 + np.random.uniform(-0.01, 0.01))
            diff = (pred_price - last_price) / last_price
            confidence = np.random.uniform(60, 98)

            signal = (
                "SUBIDA 🔼" if diff > 0.002
                else "DESCIDA 🔽" if diff < -0.002
                else "NEUTRAL ⚪"
            )

        last_price = df['close'].iloc[-1]

        st.subheader(f"💰 Preço Atual: ${last_price:.2f}")

        show_signal_alert(signal, confidence, confidence_threshold)
