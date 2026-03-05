diff --git a/app.py b/app.py
index 060e5b18bc6ba4ac839f513362ac69b6a93e64b9..5cce1fc08c5dbb83e66a24f7d1f57a3edd533d43 100644
--- a/app.py
+++ b/app.py
@@ -1,97 +1,152 @@
-import streamlit as st
-import pandas as pd
-import numpy as np
-import ccxt
-import io, base64
-from datetime import datetime
-from streamlit_autorefresh import st_autorefresh
+import streamlit as st
+import pandas as pd
+import numpy as np
+import ccxt
+import io, base64
+from streamlit_autorefresh import st_autorefresh
 
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
-def fetch_data(symbol, exchange_name='binance', timeframe='15m', limit=200):
-    exchange = getattr(ccxt, exchange_name)({'enableRateLimit': True})
-    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
+def fetch_data(symbol, exchange_name='binance', timeframe='15m', limit=200):
+    exchange = getattr(ccxt, exchange_name)({'enableRateLimit': True})
+    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
     df = pd.DataFrame(data, columns=['ts','open','high','low','close','volume'])
     df['ts'] = pd.to_datetime(df['ts'], unit='ms')
     df.set_index('ts', inplace=True)
     return df
 
 # Sons simples (curtos)
 sound_up_b64 = "UklGRigAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQgAAAAA"
 sound_down_b64 = "UklGRigAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQgAAAAA"
 
 def play_sound(sound_b64):
     audio_bytes = base64.b64decode(sound_b64)
     st.audio(io.BytesIO(audio_bytes), format="audio/wav", start_time=0)
 
-def show_signal_alert(signal: str, confidence: float, min_conf: float = 70):
+def show_signal_alert(signal: str, confidence: float, min_conf: float = 70):
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
-        elif "DESCIDA" in signal:
-            play_sound(sound_down_b64)
+        elif "DESCIDA" in signal:
+            play_sound(sound_down_b64)
+
+def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
+    data = df.copy()
+    data['ema_fast'] = data['close'].ewm(span=9, adjust=False).mean()
+    data['ema_slow'] = data['close'].ewm(span=21, adjust=False).mean()
+
+    delta = data['close'].diff()
+    gains = delta.clip(lower=0).rolling(window=14).mean()
+    losses = (-delta.clip(upper=0)).rolling(window=14).mean()
+    rs = gains / losses.replace(0, np.nan)
+    data['rsi'] = 100 - (100 / (1 + rs))
+    data['rsi'] = data['rsi'].fillna(50)
+
+    data['macd'] = data['close'].ewm(span=12, adjust=False).mean() - data['close'].ewm(span=26, adjust=False).mean()
+    data['macd_signal'] = data['macd'].ewm(span=9, adjust=False).mean()
+    data['vol_mean'] = data['volume'].rolling(window=20).mean().fillna(data['volume'].mean())
+    return data
+
+def analyze_market(df: pd.DataFrame):
+    data = calculate_indicators(df)
+    last = data.iloc[-1]
+
+    up_points = 0
+    down_points = 0
+
+    if last['ema_fast'] > last['ema_slow']:
+        up_points += 30
+    else:
+        down_points += 30
+
+    if last['macd'] > last['macd_signal']:
+        up_points += 25
+    else:
+        down_points += 25
+
+    if last['rsi'] < 35:
+        up_points += 20
+    elif last['rsi'] > 65:
+        down_points += 20
+
+    if last['volume'] > last['vol_mean']:
+        if up_points >= down_points:
+            up_points += 10
+        else:
+            down_points += 10
+
+    trend_strength = abs(last['ema_fast'] - last['ema_slow']) / last['close']
+    volatility = data['close'].pct_change().rolling(window=20).std().iloc[-1]
+    projected_move = np.clip((trend_strength * 2) - (volatility or 0), -0.02, 0.02)
+
+    if up_points - down_points >= 20:
+        signal = "SUBIDA 🔼"
+    elif down_points - up_points >= 20:
+        signal = "DESCIDA 🔽"
+    else:
+        signal = "NEUTRAL ⚪"
+
+    confidence = min(98, 50 + abs(up_points - down_points))
+    pred_price = last['close'] * (1 + projected_move if signal == "SUBIDA 🔼" else 1 - projected_move if signal == "DESCIDA 🔽" else 1)
+    return signal, confidence, pred_price, last['close'], last['rsi']
 
 # =================== INTERFACE ===================
 st.title("🚀 Bot Trading Pro — Alerta Visual & Sonoro")
 
 symbol = st.sidebar.text_input("Símbolo (ex: BTC/USDT)", "BTC/USDT")
 exchange_name = st.sidebar.selectbox("Exchange", ["binance", "coinbase", "kraken", "kucoin"])
 timeframe = st.sidebar.selectbox("Timeframe", ["5m","15m","1h","4h","1d"])
 confidence_threshold = st.sidebar.slider("🔉 Nível mínimo de confiança p/ alerta", 50, 100, 75, 1)
 auto_refresh = st.sidebar.checkbox("Atualizar automaticamente", value=False)
 interval = st.sidebar.number_input("Intervalo (s)", min_value=10, max_value=300, value=60)
 
 # Atualização segura (sem erro de DOM)
 if auto_refresh:
     st_autorefresh(interval=interval * 1000, key="data_refresh")
 
 # =================== EXECUÇÃO ===================
-if st.button("Analisar mercado") or auto_refresh:
-    with st.spinner("Analisando tendência..."):
-        df = fetch_data(symbol, exchange_name, timeframe)
-        last_price = df['close'].iloc[-1]
-        pred_price = last_price * (1 + np.random.uniform(-0.01, 0.01))
-        diff = (pred_price - last_price) / last_price
-        confidence = np.random.uniform(60, 98)
-
-        signal = (
-            "SUBIDA 🔼" if diff > 0.002
-            else "DESCIDA 🔽" if diff < -0.002
-            else "NEUTRAL ⚪"
-        )
-
-        st.subheader(f"💰 Preço Atual: ${last_price:.2f}")
-        st.subheader(f"📈 Preço Previsto: ${pred_price:.2f}")
-        st.metric("Variação (%)", f"{diff*100:.2f}%")
-        show_signal_alert(signal, confidence, confidence_threshold)
+if st.button("Analisar mercado") or auto_refresh:
+    with st.spinner("Analisando tendência..."):
+        try:
+            df = fetch_data(symbol, exchange_name, timeframe)
+            signal, confidence, pred_price, last_price, rsi = analyze_market(df)
+            diff = (pred_price - last_price) / last_price
+
+            st.subheader(f"💰 Preço Atual: ${last_price:.2f}")
+            st.subheader(f"📈 Preço Estimado: ${pred_price:.2f}")
+            st.metric("Variação estimada (%)", f"{diff*100:.2f}%")
+            st.metric("RSI (14)", f"{rsi:.1f}")
+            show_signal_alert(signal, confidence, confidence_threshold)
+        except Exception as exc:
+            st.error(f"Não foi possível analisar o mercado agora: {exc}")
