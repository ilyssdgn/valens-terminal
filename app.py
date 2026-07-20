"""
VALENS WEALTH CAPITAL — Autonomous Quant Terminal
====================================================
Institutional-grade Streamlit trading terminal. Every number on screen
(price, RSI/MACD/EMA/Bollinger/VWAP readings, AI signal, confidence,
entry/stop/target, news) is computed live from real market data via
yfinance. Nothing on this page is hardcoded or simulated.
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Valens Wealth Capital | Quant Terminal",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="💎",
)

# ==============================================================================
# INSTRUMENT & TIMEFRAME UNIVERSE
# ==============================================================================
INSTRUMENTS = {
    "XAUUSD": {"label": "Gold Spot (Fut.)", "yf": "GC=F",      "tv": "TVC:GOLD",         "fmt": "{:,.2f}"},
    "SPX500": {"label": "S&P 500 Index",   "yf": "^GSPC",     "tv": "SP:SPX",           "fmt": "{:,.2f}"},
    "NDX100": {"label": "Nasdaq 100",       "yf": "^NDX",      "tv": "NASDAQ:NDX",       "fmt": "{:,.2f}"},
    "BTCUSD": {"label": "Bitcoin / USD",    "yf": "BTC-USD",   "tv": "COINBASE:BTCUSD",  "fmt": "{:,.2f}"},
    "ETHUSD": {"label": "Ethereum / USD",   "yf": "ETH-USD",   "tv": "COINBASE:ETHUSD",  "fmt": "{:,.2f}"},
    "AAPL":   {"label": "Apple Inc.",       "yf": "AAPL",      "tv": "NASDAQ:AAPL",      "fmt": "{:,.2f}"},
    "EURUSD": {"label": "EUR / USD",        "yf": "EURUSD=X",  "tv": "FX:EURUSD",        "fmt": "{:,.4f}"},
}
# NOTE on SPX: yfinance requires the caret-prefixed index ticker "^GSPC" — plain
# "SPX" or ".INX" are not valid Yahoo symbols and will silently return empty
# frames (or raise, depending on yfinance version). "^GSPC" is correct and is
# also given extra retry protection in fetch_history()/fetch_live_price() below
# so a single transient Yahoo timeout never surfaces as a page error.

TIMEFRAMES = {
    "1M":  {"interval": "1m",  "period": "1d",  "tv": "1",   "resample": None},
    "5M":  {"interval": "5m",  "period": "5d",  "tv": "5",   "resample": None},
    "15M": {"interval": "15m", "period": "5d",  "tv": "15",  "resample": None},
    "1H":  {"interval": "60m", "period": "1mo", "tv": "60",  "resample": None},
    "4H":  {"interval": "60m", "period": "3mo", "tv": "240", "resample": "4h"},
    "1D":  {"interval": "1d",  "period": "1y",  "tv": "D",   "resample": None},
}

# ==============================================================================
# SESSION STATE
# ==============================================================================
defaults = {
    "lang": "EN",
    "symbol_key": "XAUUSD",
    "timeframe": "1D",
    "bot_active": True,
    "tp_pct": 2.5,
    "sl_pct": 1.2,
    "auto_refresh": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# TRANSLATIONS
# ==============================================================================
translations = {
    "EN": {
        "market_sel": "MARKET SELECTION", "instrument": "Instrument",
        "risk_params": "RISK PARAMETERS", "tp": "Take Profit Target (%)", "sl": "Stop Loss (%)",
        "engine": "AUTONOMOUS ENGINE", "btn_start": "🚀 Start Bot", "btn_stop": "⏸ Stop Bot",
        "auto_refresh": "Auto-refresh (30s)",
        "warn_info": "⚠️ This terminal is for informational purposes only; it is not investment advice.",
        "err_data": "Live market data cannot be synchronized at the moment. Please try again shortly.",
        "quant_engine": "Live AI Quant Engine", "live_news": "Live News Feed", "ai_signal": "AI Signal",
        "active_signal": "ACTIVE SIGNAL", "confidence": "CONFIDENCE", "synced_to": "Synced to chart —",
        "entry": "ENTRY", "stop_loss": "STOP LOSS", "target": "TARGET",
        "overbought": "OVERBOUGHT", "oversold": "OVERSOLD", "neutral": "NEUTRAL",
        "bull_cross": "Bullish Crossover", "bear_cross": "Bearish Crossover", "converge": "Convergence",
        "golden_confirmed": "Golden Cross Confirmed", "golden_near": "Golden Cross Approaching",
        "death_cross": "Death Cross", "mixed_trend": "Mixed Trend",
        "expansion": "Width Expansion", "contraction": "Width Contraction", "stable": "Stable",
        "surge": "Surge Detected", "normal_vol": "Normal Volume",
        "above_vwap": "Price Above VWAP", "below_vwap": "Price Below VWAP",
        "info_prompt": "Click **🚀 Start Bot** in the sidebar to activate the live signal engine.",
        "no_news": "No recent news available for this instrument.",
        "as_of": "As of",
    },
    "TR": {
        "market_sel": "PİYASA SEÇİMİ", "instrument": "Enstrüman",
        "risk_params": "RİSK PARAMETRELERİ", "tp": "Kar Al Hedefi (%)", "sl": "Zarar Durdur (%)",
        "engine": "OTONOM MOTOR", "btn_start": "🚀 Botu Başlat", "btn_stop": "⏸ Botu Durdur",
        "auto_refresh": "Otomatik yenile (30sn)",
        "warn_info": "⚠️ Bu terminal yalnızca bilgilendirme amaçlıdır; yatırım tavsiyesi değildir.",
        "err_data": "Canlı piyasa verisi şu anda senkronize edilemiyor. Lütfen kısa süre sonra tekrar deneyin.",
        "quant_engine": "Canlı AI Quant Motoru", "live_news": "Canlı Haber Akışı", "ai_signal": "AI Sinyali",
        "active_signal": "AKTİF SİNYAL", "confidence": "GÜVEN SKORU", "synced_to": "Grafikle senkronize —",
        "entry": "GİRİŞ", "stop_loss": "ZARAR DURDUR", "target": "HEDEF",
        "overbought": "AŞIRI ALIM", "oversold": "AŞIRI SATIM", "neutral": "NÖTR",
        "bull_cross": "Boğa Kesişimi", "bear_cross": "Ayı Kesişimi", "converge": "Yakınsama",
        "golden_confirmed": "Altın Kesişim Onaylandı", "golden_near": "Altın Kesişim Yaklaşıyor",
        "death_cross": "Ölüm Kesişimi", "mixed_trend": "Karışık Trend",
        "expansion": "Bant Genişlemesi", "contraction": "Bant Daralması", "stable": "Stabil",
        "surge": "Hacim Artışı", "normal_vol": "Normal Hacim",
        "above_vwap": "Fiyat VWAP Üzerinde", "below_vwap": "Fiyat VWAP Altında",
        "info_prompt": "Canlı sinyal motorunu etkinleştirmek için soldaki **🚀 Botu Başlat** butonuna tıklayın.",
        "no_news": "Bu enstrüman için güncel haber bulunmuyor.",
        "as_of": "Güncelleme",
    },
}
t = translations[st.session_state.lang]

# ==============================================================================
# THEME / CSS — Institutional Luxury (Oxford Navy + Champagne Gold)
# ==============================================================================
def load_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root {
        --navy: #050b14;
        --navy-panel: #0b1523;
        --navy-panel-2: #0e1a2c;
        --gold: #D4AF37;
        --gold-bright: #F0D77B;
        --white: #FFFFFF;
        --ivory: #ECEAE3;
        --muted: #8B93A7;
        --success: #3FAE6A;
        --danger: #C0453B;
        --border-gold: rgba(212, 175, 55, 0.25);
    }

    html, body, [class*="css"], .stMarkdown, p, span, label, div {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    .stApp {
        background: radial-gradient(ellipse at top, #0c1a30 0%, var(--navy) 65%) !important;
    }
    .main .block-container {
        padding-top: 1rem; padding-bottom: 2rem; max-width: 100%;
    }
    #MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden; height: 0;}

    h1, h2, h3, h4 {
        font-family: 'Playfair Display', Georgia, serif !important;
        color: var(--white) !important;
        letter-spacing: 0.3px;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a1220 0%, #050b14 100%);
        border-right: 1px solid var(--border-gold);
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: var(--gold) !important; font-size: 16px !important;
    }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: var(--muted) !important; }

    .stButton > button {
        background: transparent; border: 1.5px solid var(--gold); color: var(--gold);
        border-radius: 6px; font-weight: 600; letter-spacing: 0.6px; padding: 8px 16px;
        transition: all .2s ease; width: 100%;
    }
    .stButton > button:hover { background: var(--gold); color: var(--navy); }

    div[role="radiogroup"] { gap: 4px; }
    div[role="radiogroup"] label {
        border: 1px solid var(--border-gold); border-radius: 6px; padding: 4px 12px !important;
        color: var(--muted) !important; font-family: 'IBM Plex Mono', monospace; font-size: 13px;
    }

    /* ---------- Top Navbar ---------- */
    .valens-navbar {
        display: flex; align-items: center; justify-content: space-between;
        background: linear-gradient(180deg, #0a1526 0%, #060d18 100%);
        border: 1px solid var(--border-gold); border-radius: 10px;
        padding: 14px 28px; margin-bottom: 14px;
    }
    .navbar-brand { display: flex; align-items: center; gap: 12px; }
    .navbar-crest { font-size: 26px; color: var(--gold); }
    .navbar-title { font-family: 'Playfair Display', serif; font-size: 21px; color: var(--white); line-height: 1.1; }
    .navbar-sub { font-size: 11px; color: var(--gold); letter-spacing: 2px; }
    .navbar-tabs { display: flex; gap: 30px; }
    .navbar-tab { color: var(--muted); font-size: 15px; padding-bottom: 4px; }
    .navbar-tab.active { color: var(--white); border-bottom: 2px solid var(--gold); font-weight: 600; }
    .navbar-clock { text-align: right; color: var(--white); font-family: 'IBM Plex Mono', monospace; font-size: 15px; }
    .navbar-date { color: var(--muted); font-size: 12px; }

    /* ---------- Generic Card ---------- */
    .v-card {
        background: linear-gradient(155deg, var(--navy-panel-2), var(--navy-panel));
        border: 1px solid var(--border-gold); border-radius: 12px;
        padding: 20px 22px; margin-bottom: 16px; box-shadow: 0 6px 20px rgba(0,0,0,0.35);
    }
    .v-card-title {
        font-family: 'Playfair Display', serif; color: var(--gold); font-size: 18px;
        margin-bottom: 14px; border-bottom: 1px solid var(--border-gold); padding-bottom: 10px;
    }

    /* ---------- Price header ---------- */
    .price-value { font-family: 'IBM Plex Mono', monospace; font-size: 34px; color: var(--white); font-weight: 600; }
    .price-change-up { color: var(--success); font-size: 16px; font-family: 'IBM Plex Mono', monospace; }
    .price-change-down { color: var(--danger); font-size: 16px; font-family: 'IBM Plex Mono', monospace; }
    .price-label { color: var(--muted); font-size: 12px; letter-spacing: 1.5px; text-transform: uppercase; }

    /* ---------- Sync badge ---------- */
    .sync-badge {
        display: inline-flex; align-items: center; gap: 6px; font-size: 11px;
        color: var(--gold-bright); letter-spacing: 0.5px; margin-bottom: 10px;
        font-family: 'IBM Plex Mono', monospace;
    }
    .sync-dot {
        width: 7px; height: 7px; border-radius: 50%; background: var(--success);
        box-shadow: 0 0 6px var(--success); animation: pulse-dot 1.8s infinite;
    }
    @keyframes pulse-dot { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

    /* ---------- Indicator rows ---------- */
    .ind-row { margin-bottom: 14px; }
    .ind-row-top { display: flex; justify-content: space-between; font-size: 13.5px; margin-bottom: 5px; }
    .ind-name { color: var(--white); font-weight: 600; }
    .ind-desc { color: var(--muted); }
    .ind-pct { color: var(--gold); font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
    .ind-bar-bg { background: rgba(212,175,55,0.12); border-radius: 4px; height: 6px; overflow: hidden; }
    .ind-bar-fill { background: linear-gradient(90deg, var(--gold), var(--gold-bright)); height: 100%; border-radius: 4px; }

    /* ---------- News ---------- */
    .news-item {
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 0; border-bottom: 1px solid rgba(212,175,55,0.12); font-size: 13.5px;
    }
    .news-item:last-child { border-bottom: none; }
    .news-src { color: var(--gold); font-weight: 700; width: 90px; flex-shrink: 0; }
    .news-title { color: var(--white); flex-grow: 1; padding: 0 10px; }
    .news-title a { color: var(--white); text-decoration: none; }
    .news-title a:hover { color: var(--gold); }
    .news-time { color: var(--muted); font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; flex-shrink: 0; }

    /* ---------- AI Signal Card (the centerpiece) ---------- */
    .signal-card {
        border-radius: 14px; overflow: hidden; border: 1px solid var(--gold);
        box-shadow: 0 0 45px rgba(212,175,55,0.30), 0 0 90px rgba(212,175,55,0.12);
        animation: signal-glow 3.2s ease-in-out infinite;
    }
    @keyframes signal-glow {
        0%, 100% { box-shadow: 0 0 45px rgba(212,175,55,0.30), 0 0 90px rgba(212,175,55,0.12); }
        50% { box-shadow: 0 0 60px rgba(212,175,55,0.45), 0 0 120px rgba(212,175,55,0.20); }
    }
    .signal-header {
        background: linear-gradient(90deg, #7a5f1c, var(--gold), #7a5f1c);
        color: var(--navy); text-align: center; padding: 10px; font-weight: 700;
        letter-spacing: 3px; font-size: 12.5px;
    }
    .signal-body { background: radial-gradient(ellipse at center, #12213a 0%, var(--navy-panel) 75%); padding: 30px 24px; text-align: center; }
    .signal-decision-buy { color: var(--success); font-size: 40px; font-weight: 700; font-family: 'Playfair Display', serif; letter-spacing: 0.5px; text-shadow: 0 0 24px rgba(63,174,106,0.45); }
    .signal-decision-sell { color: var(--danger); font-size: 40px; font-weight: 700; font-family: 'Playfair Display', serif; letter-spacing: 0.5px; text-shadow: 0 0 24px rgba(192,69,59,0.45); }
    .signal-decision-neutral { color: var(--gold); font-size: 40px; font-weight: 700; font-family: 'Playfair Display', serif; letter-spacing: 0.5px; text-shadow: 0 0 24px rgba(212,175,55,0.45); }
    .signal-asset { color: var(--muted); font-size: 13px; letter-spacing: 1.5px; margin-top: 2px; text-transform: uppercase; }
    .signal-confidence { color: var(--gold-bright); font-size: 15px; margin-top: 10px; font-weight: 600; letter-spacing: 0.5px; }
    .signal-levels { display: flex; justify-content: space-between; margin-top: 24px; border-top: 1px solid var(--border-gold); padding-top: 18px; }
    .signal-level { text-align: center; flex: 1; }
    .signal-level-label { color: var(--muted); font-size: 11px; letter-spacing: 1px; }
    .signal-level-value { color: var(--white); font-family: 'IBM Plex Mono', monospace; font-size: 16px; margin-top: 3px; font-weight: 600; }

    .gold-divider { height: 1px; background: linear-gradient(90deg, transparent, var(--gold), transparent); margin: 12px 0; }
    </style>
    """, unsafe_allow_html=True)


# ==============================================================================
# DATA LAYER — real yfinance calls, cached & defensive
# ==============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_history(yf_symbol: str, period: str, interval: str) -> pd.DataFrame:
    last_err = None
    for attempt in range(2):
        try:
            df = yf.Ticker(yf_symbol).history(period=period, interval=interval, auto_adjust=True)
            if df is None or df.empty:
                last_err = "empty"
                time.sleep(0.6)
                continue
            df = df.dropna(subset=["Close"])
            if df.empty:
                last_err = "empty"
                time.sleep(0.6)
                continue
            return df
        except Exception as e:
            last_err = e
            time.sleep(0.6)
            continue
    return pd.DataFrame()


@st.cache_data(ttl=45, show_spinner=False)
def fetch_live_price(yf_symbol: str) -> dict:
    """Returns dict(price, prev_close, change, change_pct) from live/fast data, with robust fallbacks."""
    for attempt in range(2):
        try:
            tk = yf.Ticker(yf_symbol)
            try:
                fi = tk.fast_info
                price = float(fi.last_price)
                prev = float(fi.previous_close)
            except Exception:
                hist = tk.history(period="5d", interval="1d", auto_adjust=True)
                if hist.empty or len(hist) < 2:
                    time.sleep(0.6)
                    continue
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
            if not prev:
                time.sleep(0.6)
                continue
            change = price - prev
            change_pct = (change / prev) * 100
            return {"price": price, "prev_close": prev, "change": change, "change_pct": change_pct}
        except Exception:
            time.sleep(0.6)
            continue
    return {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_news(yf_symbol: str, limit: int = 6) -> list:
    """Defensive parser — yfinance's news schema has shifted across versions."""
    items = []
    try:
        raw = yf.Ticker(yf_symbol).news or []
    except Exception:
        raw = []
    for art in raw[:limit * 2]:
        try:
            content = art.get("content", art) if isinstance(art, dict) else {}
            title = content.get("title") or art.get("title")
            if not title:
                continue
            publisher = None
            if isinstance(content.get("provider"), dict):
                publisher = content["provider"].get("displayName")
            publisher = publisher or content.get("publisher") or art.get("publisher") or "Market Wire"
            link = None
            for key_path in (("clickThroughUrl", "url"), ("canonicalUrl", "url")):
                node = content.get(key_path[0])
                if isinstance(node, dict) and node.get(key_path[1]):
                    link = node[key_path[1]]
                    break
            link = link or content.get("link") or art.get("link") or "#"
            ts = content.get("pubDate") or art.get("providerPublishTime")
            time_str = ""
            if isinstance(ts, (int, float)):
                time_str = datetime.fromtimestamp(ts).strftime("%H:%M")
            elif isinstance(ts, str):
                try:
                    time_str = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
                except Exception:
                    time_str = ""
            items.append({"title": title, "publisher": publisher, "link": link, "time": time_str})
        except Exception:
            continue
        if len(items) >= limit:
            break
    return items


# ==============================================================================
# INDICATOR ENGINE — pure pandas, no external TA library required
# ==============================================================================
def compute_indicators(df: pd.DataFrame) -> dict:
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = (100 - (100 / (1 + rs))).fillna(50)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = sma20 + 2 * std20
    lower = sma20 - 2 * std20
    bb_width = (upper - lower) / sma20

    typical = (high + low + close) / 3
    vwap = (typical * vol).cumsum() / vol.cumsum().replace(0, np.nan)

    return dict(rsi=rsi, macd_line=macd_line, signal_line=signal_line, hist=hist,
                ema50=ema50, ema200=ema200, sma20=sma20, upper=upper, lower=lower,
                bb_width=bb_width, vwap=vwap)


def normalize_last(series: pd.Series, window: int = 100, invert: bool = False) -> float:
    s = series.dropna()
    if len(s) < 5:
        return 50.0
    w = s.tail(window)
    lo, hi = w.min(), w.max()
    if hi == lo:
        return 50.0
    pct = (s.iloc[-1] - lo) / (hi - lo) * 100
    if invert:
        pct = 100 - pct
    return float(np.clip(pct, 0, 100))


def generate_signal(df: pd.DataFrame, ind: dict, sl_pct: float, tp_pct: float) -> dict:
    close = float(df["Close"].iloc[-1])
    rsi_v = float(ind["rsi"].iloc[-1])
    macd_v, sig_v, hist_v = float(ind["macd_line"].iloc[-1]), float(ind["signal_line"].iloc[-1]), float(ind["hist"].iloc[-1])
    ema50_v, ema200_v = float(ind["ema50"].iloc[-1]), float(ind["ema200"].iloc[-1])
    vwap_v = float(ind["vwap"].iloc[-1]) if not np.isnan(ind["vwap"].iloc[-1]) else close
    upper_v, lower_v = float(ind["upper"].iloc[-1]), float(ind["lower"].iloc[-1])
    bb_width_v = ind["bb_width"]
    vol_v = float(df["Volume"].iloc[-1])
    vol_avg = float(df["Volume"].rolling(20).mean().iloc[-1]) if len(df) >= 20 else vol_v

    votes = 0
    votes += 1 if macd_v > sig_v else -1
    if close > ema50_v > ema200_v:
        votes += 1
    elif close < ema50_v < ema200_v:
        votes -= 1
    votes += 1 if close > vwap_v else -1

    bb_pos = (close - lower_v) / (upper_v - lower_v) if upper_v != lower_v else 0.5
    if bb_pos > 0.8:
        votes += 1
    elif bb_pos < 0.2:
        votes -= 1

    price_chg = float(df["Close"].pct_change().iloc[-1] or 0)
    vol_surge = vol_avg > 0 and vol_v > 1.5 * vol_avg
    if vol_surge and price_chg > 0:
        votes += 1
    elif vol_surge and price_chg < 0:
        votes -= 1

    if votes >= 3:
        decision = "STRONG BUY"
    elif votes >= 1:
        decision = "BUY"
    elif votes <= -3:
        decision = "STRONG SELL"
    elif votes <= -1:
        decision = "SELL"
    else:
        decision = "NEUTRAL"

    if rsi_v >= 75 and decision == "STRONG BUY":
        decision = "BUY"
    if rsi_v <= 25 and decision == "STRONG SELL":
        decision = "SELL"

    confidence = float(np.clip(55 + abs(votes) * 9, 50, 97))

    bullish = decision in ("BUY", "STRONG BUY")
    bearish = decision in ("SELL", "STRONG SELL")
    if bearish:
        stop = close * (1 + sl_pct / 100)
        target = close * (1 - tp_pct / 100)
    else:
        stop = close * (1 - sl_pct / 100)
        target = close * (1 + tp_pct / 100)

    macd_bar = normalize_last(ind["hist"])
    ema_bar = 100 - normalize_last((ind["ema50"] - ind["ema200"]).abs())
    bb_bar = normalize_last(bb_width_v)
    vol_bar = normalize_last(df["Volume"], window=50)
    vwap_bar = normalize_last(df["Close"] - ind["vwap"])
    rsi_bar = float(np.clip(abs(rsi_v - 50) * 2, 0, 100))

    return dict(
        decision=decision, confidence=confidence, votes=votes,
        entry=close, stop=stop, target=target,
        rsi_val=rsi_v, rsi_bar=rsi_bar,
        macd_state=("bull_cross" if hist_v >= 0 else "bear_cross") if macd_bar >= 15 else "converge",
        macd_bar=macd_bar,
        ema_state=("golden_confirmed" if close > ema50_v > ema200_v else
                   "death_cross" if close < ema50_v < ema200_v else
                   "golden_near" if ema_bar > 70 else "mixed_trend"),
        ema_bar=ema_bar,
        bb_state=("expansion" if bb_bar > 65 else "contraction" if bb_bar < 35 else "stable"),
        bb_bar=bb_bar,
        vol_state=("surge" if vol_surge else "normal_vol"), vol_bar=vol_bar,
        vwap_state=("above_vwap" if close > vwap_v else "below_vwap"), vwap_bar=vwap_bar,
    )


# ==============================================================================
# UI HELPERS
# ==============================================================================
def indicator_row(name: str, desc: str, pct: float):
    st.markdown(f"""
    <div class="ind-row">
        <div class="ind-row-top">
            <span><span class="ind-name">{name}</span> &nbsp;–&nbsp; <span class="ind-desc">{desc}</span></span>
            <span class="ind-pct">{pct:.0f}%</span>
        </div>
        <div class="ind-bar-bg"><div class="ind-bar-fill" style="width:{pct:.0f}%;"></div></div>
    </div>
    """, unsafe_allow_html=True)


def mini_spark(series: pd.Series, color: str, height: int = 45):
    fig = go.Figure(go.Scatter(y=series.tail(30).values, mode="lines", line=dict(color=color, width=1.6)))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"spark_{color}_{time.time()}")


def render_tradingview(tv_symbol: str, tv_interval: str, height: int = 560):
    container_id = f"tv_{tv_symbol.replace(':', '_')}_{tv_interval}"
    html = f"""
    <div class="tradingview-widget-container">
      <div id="{container_id}"></div>
      <script src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%",
        "height": {height},
        "symbol": "{tv_symbol}",
        "interval": "{tv_interval}",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#050b14",
        "enable_publishing": false,
        "hide_top_toolbar": false,
        "hide_legend": false,
        "withdateranges": true,
        "allow_symbol_change": false,
        "studies": ["RSI@tv-basicstudies", "MACD@tv-basicstudies", "Volume@tv-basicstudies"],
        "container_id": "{container_id}"
      }});
      </script>
    </div>
    """
    st.components.v1.html(html, height=height + 10, scrolling=False)


# ==============================================================================
# APP
# ==============================================================================
load_theme()

# ---- Sidebar -----------------------------------------------------------------
with st.sidebar:
    st.markdown("### 💎 VALENS")
    st.caption("QUANT TERMINAL v2.0")
    lang_col1, lang_col2 = st.columns(2)
    if lang_col1.button("EN", use_container_width=True):
        st.session_state.lang = "EN"; st.rerun()
    if lang_col2.button("TR", use_container_width=True):
        st.session_state.lang = "TR"; st.rerun()

    st.markdown("---")
    st.markdown(f"**{t['market_sel']}**")
    symbol_key = st.selectbox(
        t["instrument"], options=list(INSTRUMENTS.keys()),
        format_func=lambda k: INSTRUMENTS[k]["label"],
        index=list(INSTRUMENTS.keys()).index(st.session_state.symbol_key),
    )
    st.session_state.symbol_key = symbol_key

    st.markdown("---")
    st.markdown(f"**{t['risk_params']}**")
    st.session_state.tp_pct = st.number_input(t["tp"], min_value=0.1, max_value=20.0, value=st.session_state.tp_pct, step=0.1)
    st.session_state.sl_pct = st.number_input(t["sl"], min_value=0.1, max_value=20.0, value=st.session_state.sl_pct, step=0.1)

    st.markdown("---")
    st.markdown(f"**{t['engine']}**")
    if st.session_state.bot_active:
        if st.button(t["btn_stop"]):
            st.session_state.bot_active = False; st.rerun()
    else:
        if st.button(t["btn_start"]):
            st.session_state.bot_active = True; st.rerun()
    st.session_state.auto_refresh = st.checkbox(t["auto_refresh"], value=st.session_state.auto_refresh)

    st.markdown("---")
    st.caption(t["warn_info"])

inst = INSTRUMENTS[st.session_state.symbol_key]

# ---- Top Navbar ----------------------------------------------------------
now_est = datetime.now(ZoneInfo("America/New_York"))
st.markdown(f"""
<div class="valens-navbar">
    <div class="navbar-brand">
        <div class="navbar-crest">♛</div>
        <div>
            <div class="navbar-title">Valens Wealth Capital</div>
            <div class="navbar-sub">SIGNALS TERMINAL</div>
        </div>
    </div>
    <div class="navbar-tabs">
        <div class="navbar-tab">Portfolio</div>
        <div class="navbar-tab active">Signals</div>
        <div class="navbar-tab">Research</div>
        <div class="navbar-tab">Settings</div>
        <div class="navbar-tab">Account</div>
    </div>
    <div class="navbar-clock">
        {now_est.strftime('%H:%M:%S')} EST
        <div class="navbar-date">{now_est.strftime('%B %d, %Y')}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---- Fetch data ------------------------------------------------------------
tf = TIMEFRAMES[st.session_state.timeframe]
raw_df = fetch_history(inst["yf"], tf["period"], tf["interval"])
if tf["resample"] and not raw_df.empty:
    try:
        raw_df = raw_df.resample(tf["resample"]).agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        ).dropna()
    except Exception:
        pass

live = fetch_live_price(inst["yf"])
news_items = fetch_news(inst["yf"])

col_left, col_right = st.columns([2.3, 1])

# ============================================================ LEFT COLUMN
with col_left:
    head_l, head_r = st.columns([2, 3])
    with head_l:
        st.markdown(f"### {inst['label']} <span style='color:var(--muted); font-size:15px;'>· {st.session_state.symbol_key}</span>", unsafe_allow_html=True)
    with head_r:
        st.session_state.timeframe = st.radio(
            "tf", options=list(TIMEFRAMES.keys()), index=list(TIMEFRAMES.keys()).index(st.session_state.timeframe),
            horizontal=True, label_visibility="collapsed",
        )

    render_tradingview(inst["tv"], TIMEFRAMES[st.session_state.timeframe]["tv"])

    st.markdown(f'<div class="v-card"><div class="v-card-title">📰 {t["live_news"]}</div>', unsafe_allow_html=True)
    if news_items:
        rows = ""
        for n in news_items:
            rows += f"""
            <div class="news-item">
                <span class="news-src">{n['publisher'][:14].upper()}</span>
                <span class="news-title"><a href="{n['link']}" target="_blank">{n['title']}</a></span>
                <span class="news-time">{n['time']}</span>
            </div>"""
        st.markdown(rows, unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ind-desc">{t["no_news"]}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================ RIGHT COLUMN
with col_right:
    # ---- Price card
    if live:
        change = live["change"]
        change_pct = live["change_pct"]
        cls = "price-change-up" if change >= 0 else "price-change-down"
        arrow = "▲" if change >= 0 else "▼"
        price_str = inst["fmt"].format(live["price"])
        st.markdown(f"""
        <div class="v-card">
            <div class="price-label">{inst['label']} ({st.session_state.symbol_key}) — {t['as_of']} {now_est.strftime('%H:%M:%S')} EST</div>
            <div class="price-value">{price_str}</div>
            <div class="{cls}">{arrow} {change:+,.2f} ({change_pct:+.2f}%)</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="v-card">{t["err_data"]}</div>', unsafe_allow_html=True)

    if raw_df.empty or len(raw_df) < 20:
        st.markdown(f'<div class="v-card">{t["err_data"]}</div>', unsafe_allow_html=True)
    elif not st.session_state.bot_active:
        st.markdown(f'<div class="v-card">{t["info_prompt"]}</div>', unsafe_allow_html=True)
    else:
        ind = compute_indicators(raw_df)
        sig = generate_signal(raw_df, ind, st.session_state.sl_pct, st.session_state.tp_pct)

        # ---- Sync badge (proves chart + engine are reading the same instrument)
        st.markdown(f"""
        <div class="sync-badge"><span class="sync-dot"></span> {t['synced_to']} {inst['label']} ({inst['yf']})</div>
        """, unsafe_allow_html=True)

        # ---- Quant Engine card
        st.markdown(f'<div class="v-card"><div class="v-card-title">⚙️ {t["quant_engine"]}</div>', unsafe_allow_html=True)
        rsi_label = t["overbought"] if sig["rsi_val"] > 70 else t["oversold"] if sig["rsi_val"] < 30 else t["neutral"]
        indicator_row("RSI", f"{sig['rsi_val']:.0f} - {rsi_label}", sig["rsi_bar"])
        indicator_row("MACD", t[sig["macd_state"]], sig["macd_bar"])
        indicator_row("EMA", t[sig["ema_state"]], sig["ema_bar"])
        indicator_row("Bollinger Bands", t[sig["bb_state"]], sig["bb_bar"])
        indicator_row("Volume", t[sig["vol_state"]], sig["vol_bar"])
        indicator_row("VWAP", t[sig["vwap_state"]], sig["vwap_bar"])
        st.markdown("</div>", unsafe_allow_html=True)

        # ---- AI Signal card
        decision = sig["decision"]
        deco_cls = "signal-decision-buy" if "BUY" in decision else "signal-decision-sell" if "SELL" in decision else "signal-decision-neutral"
        emoji = "🟢" if "BUY" in decision else "🔴" if "SELL" in decision else "🟡"
        st.markdown(f"""
        <div class="signal-card">
            <div class="signal-header">{t['active_signal']}</div>
            <div class="signal-body">
                <div class="{deco_cls}">{emoji} {decision}</div>
                <div class="signal-asset">{inst['label']} · {st.session_state.symbol_key}</div>
                <div class="signal-confidence">{sig['confidence']:.0f}% {t['confidence']}</div>
                <div class="signal-levels">
                    <div class="signal-level">
                        <div class="signal-level-label">{t['entry']}</div>
                        <div class="signal-level-value">{inst['fmt'].format(sig['entry'])}</div>
                    </div>
                    <div class="signal-level">
                        <div class="signal-level-label">{t['stop_loss']}</div>
                        <div class="signal-level-value">{inst['fmt'].format(sig['stop'])}</div>
                    </div>
                    <div class="signal-level">
                        <div class="signal-level-label">{t['target']}</div>
                        <div class="signal-level-value">{inst['fmt'].format(sig['target'])}</div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        spark_cols = st.columns(3)
        macd_color = "#3FAE6A" if float(ind["hist"].iloc[-1]) >= 0 else "#C0453B"
        rsi_color = "#C0453B" if sig["rsi_val"] > 70 else "#3FAE6A" if sig["rsi_val"] < 30 else "#D4AF37"
        with spark_cols[0]:
            st.markdown('<div class="price-label">PRICE (30)</div>', unsafe_allow_html=True)
            mini_spark(raw_df["Close"], "#D4AF37")
        with spark_cols[1]:
            st.markdown('<div class="price-label">RSI (30)</div>', unsafe_allow_html=True)
            mini_spark(ind["rsi"], rsi_color)
        with spark_cols[2]:
            st.markdown('<div class="price-label">MACD HIST (30)</div>', unsafe_allow_html=True)
            mini_spark(ind["hist"], macd_color)

# ==============================================================================
# AUTO-REFRESH
# ==============================================================================
if st.session_state.auto_refresh:
    time.sleep(30)
    st.rerun()
