import io
import base64
import ccxt
import numpy as np
import pandas as pd
import streamlit as st

from sklearn.ensemble import RandomForestClassifier
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="🚀 Institutional Trading Scanner", layout="wide")

# ==========================
# CONFIG
# ==========================

st.title("🚀 Institutional Multi Strategy Scanner")

symbol = st.sidebar.text_input("Symbol", "BTC/USDT")
exchange_name = st.sidebar.selectbox("Exchange", ["binance","kucoin","kraken","coinbase"])

timeframe = st.sidebar.selectbox(
    "Primary timeframe",
    ["5m","15m","1h","4h","1d"]
)

auto_refresh = st.sidebar.checkbox("Auto refresh")
interval = st.sidebar.number_input("Refresh seconds",10,300,60)

if auto_refresh:
    st_autorefresh(interval=interval*1000)

# ==========================
# FETCH DATA
# ==========================

@st.cache_data(ttl=120)
def fetch_data(symbol, exchange_name, timeframe, limit=200):

    exchange = getattr(ccxt, exchange_name)({
        "enableRateLimit": True
    })

    data = exchange.fetch_ohlcv(symbol,timeframe=timeframe,limit=limit)

    df = pd.DataFrame(
        data,
        columns=["ts","open","high","low","close","volume"]
    )

    df["ts"] = pd.to_datetime(df["ts"],unit="ms")
    df.set_index("ts",inplace=True)

    return df


# ==========================
# INDICATORS
# ==========================

def indicators(df):

    data = df.copy()

    data["ema9"] = data["close"].ewm(span=9).mean()
    data["ema21"] = data["close"].ewm(span=21).mean()

    delta = data["close"].diff()

    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()

    rs = gain / loss.replace(0,1e-10)

    data["rsi"] = 100 - (100/(1+rs))

    data["macd"] = data["close"].ewm(span=12).mean() - data["close"].ewm(span=26).mean()
    data["macd_signal"] = data["macd"].ewm(span=9).mean()

    low14 = data["low"].rolling(14).min()
    high14 = data["high"].rolling(14).max()

    data["stoch"] = 100*((data["close"]-low14)/(high14-low14))

    tp = (data["high"]+data["low"]+data["close"])/3
    sma = tp.rolling(20).mean()
    mad = (tp-sma).abs().rolling(20).mean()

    data["cci"] = (tp-sma)/(0.015*mad)

    data["bb_mid"] = data["close"].rolling(20).mean()
    std = data["close"].rolling(20).std()

    data["bb_upper"] = data["bb_mid"] + 2*std
    data["bb_lower"] = data["bb_mid"] - 2*std

    data["vol_mean"] = data["volume"].rolling(20).mean()

    return data


# ==========================
# LIQUIDITY SCANNER
# ==========================

def whale_detector(data):

    last = data.iloc[-1]

    if last["volume"] > last["vol_mean"]*3:
        return "🐋 Whale Volume Detected"

    if last["volume"] > last["vol_mean"]*2:
        return "⚠️ High Volume"

    return "Normal"


# ==========================
# MULTI TIMEFRAME
# ==========================

def multi_timeframe_trend(symbol):

    tf_list = ["15m","1h","4h"]

    signals = []

    for tf in tf_list:

        df = fetch_data(symbol,exchange_name,tf)

        data = indicators(df)

        last = data.iloc[-1]

        if last["ema9"] > last["ema21"]:
            signals.append(1)
        else:
            signals.append(-1)

    score = sum(signals)

    if score >= 2:
        return "Bullish"
    if score <= -2:
        return "Bearish"

    return "Neutral"


# ==========================
# AI PREDICTION
# ==========================

def ai_prediction(data):

    df = data.copy()

    df["future"] = df["close"].shift(-1)

    df["target"] = (df["future"] > df["close"]).astype(int)

    features = df[[
        "rsi",
        "macd",
        "stoch",
        "cci"
    ]]

    features = features.dropna()

    target = df.loc[features.index,"target"]

    if len(features) < 50:
        return "Not enough data"

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=6
    )

    model.fit(features,target)

    latest = features.iloc[-1].values.reshape(1,-1)

    pred = model.predict(latest)[0]

    prob = model.predict_proba(latest)[0].max()

    if pred == 1:
        direction = "UP"
    else:
        direction = "DOWN"

    return direction, round(prob*100,2)


# ==========================
# SIGNAL ENGINE
# ==========================

def signal_engine(data):

    last = data.iloc[-1]

    up = 0
    down = 0

    if last["ema9"] > last["ema21"]:
        up += 30
    else:
        down += 30

    if last["macd"] > last["macd_signal"]:
        up += 25
    else:
        down += 25

    if last["rsi"] < 35:
        up += 20

    if last["rsi"] > 65:
        down += 20

    if last["stoch"] < 20:
        up += 15

    if last["stoch"] > 80:
        down += 15

    if last["cci"] > 100:
        up += 10

    if last["cci"] < -100:
        down += 10

    if up > down:
        return "SUBIDA 🔼", up

    if down > up:
        return "DESCIDA 🔽", down

    return "NEUTRAL",50


# ==========================
# MAIN EXECUTION
# ==========================

if st.button("Run Institutional Scanner"):

    with st.spinner("Analyzing market..."):

        df = fetch_data(symbol,exchange_name,timeframe)

        data = indicators(df)

        signal,confidence = signal_engine(data)

        whale = whale_detector(data)

        trend = multi_timeframe_trend(symbol)

        ai = ai_prediction(data)

        last_price = data.iloc[-1]["close"]

        st.subheader(f"💰 Price: {last_price}")

        st.metric("Signal",signal)
        st.metric("Confidence",confidence)

        st.metric("Liquidity",whale)

        st.metric("Multi TF Trend",trend)

        if isinstance(ai,tuple):

            direction,prob = ai

            st.metric("AI Prediction",direction)
            st.metric("AI Confidence",f"{prob}%")

        else:

            st.warning(ai)
