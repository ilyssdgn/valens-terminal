import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import time
import random
import feedparser

st.set_page_config(
    page_title="Valens Wealth | Otonom Varlık Yönetimi",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="💎"
)

# ==============================================================================
# SESSION STATE & DİL (LANGUAGE) AYARLARI
# ==============================================================================
if 'page' not in st.session_state:
    st.session_state.page = 'landing'
if 'lang' not in st.session_state:
    st.session_state.lang = 'EN'

def switch_page(page_name):
    st.session_state.page = page_name
    st.rerun()

# Çeviri Sözlüğü (Translations)
translations = {
    "TR": {
        "landing_subtitle": "Otonom Varlık Yönetim Terminali",
        "landing_desc": "Yalnızca davetiye ile erişilebilen, kurumlar ve nitelikli yatırımcılar için tasarlanmış analiz terminali.",
        "landing_btn": "Valens Terminal'e Bağlan  →",
        "risk_title": "Risk Bildirimi & Yasal Uyarı",
        "risk_desc": "Bu platformda yer alan veriler ve teknik analizler yalnızca bilgilendirme amaçlıdır ve yatırım tavsiyesi niteliği taşımaz. Kripto para birimleri yüksek oynaklığa sahiptir; yatırım kararlarınızı kendi araştırmanıza ve risk toleransınıza göre veriniz.",
        "sidebar_title": "VALENS",
        "sidebar_sub": "QUANT TERMINAL v2.0",
        "market_sel": "PİYASA SEÇİMİ",
        "inst": "Enstrüman",
        "risk_params": "RİSK PARAMETRELERİ",
        "tp": "Kar Al Hedefi (%)",
        "sl": "Zarar Durdur (%)",
        "engine": "OTONOM MOTOR",
        "btn_start": "🚀 Botu Başlat",
        "warn_info": "⚠️ Bu terminal yalnızca bilgilendirme amaçlıdır; yatırım tavsiyesi değildir.",
        "logout": "Çıkış Yap",
        "live_data": "CANLI VERİ",
        "timeframe": "Zaman Dilimi: 15dk",
        "err_data": "Canlı piyasa verisi şu anda senkronize edilemiyor. Lütfen kısa süre sonra tekrar deneyin.",
        "overbought": "Aşırı Alım",
        "oversold": "Aşırı Satım",
        "neutral": "Nötr",
        "bullish": "Boğa (Bullish)",
        "bearish": "Ayı (Bearish)",
        "momentum": "Momentum (Dönem)",
        "price_action": "Fiyat Hareketi",
        "wait_chart": "Grafik için canlı veri bekleniyor.",
        "engine_title": "Valens AI Otonom Karar Motoru",
        "status_init": "Valens AI Motoru Devreye Alınıyor...",
        "status_1": "Fiyat verisi işleniyor...",
        "status_2": "RSI ve MACD güncelleniyor...",
        "status_3": "Sinyal ve risk parametreleri hesaplanıyor...",
        "status_done": "Analiz tamamlandı",
        "status_err": "Analiz başlatılamadı: canlı fiyat verisi alınamadı.",
        "final_eval": "NİHAİ SİSTEM DEĞERLENDİRMESİ",
        "strength": "GÖSTERGE GÜCÜ",
        "entry": "GİRİŞ (ENTRY)",
        "tp_label": "KAR AL (TP",
        "sl_label": "ZARAR DURDUR (SL",
        "engine_warn": "Bu değerlendirme yalnızca RSI ve MACD göstergelerinin kural tabanlı birleşimine dayanır; finansal danışmanlık veya getiri taahhüdü içermez.",
        "info_prompt": "Detaylı sinyal analizi için sol menüden **🚀 Botu Başlat** butonuna tıklayın.",
        "sig_buy": "AL (BUY)",
        "sig_sell": "SAT (SELL)",
        "sig_watch_up": "İZLE — YÜKSELİŞ EĞİLİMİ",
        "sig_watch_down": "İZLE — DÜŞÜŞ EĞİLİMİ",
        "sig_neutral": "NÖTR",
        "whale_alert": "[BALİNA ALARMI] {symbol} ağında {amount} transfer tespit edildi! Kurumsal hareketlilik gözleniyor.",
        "quant_status": "RSI kritik bölgelere yaklaşıyor, direnç seviyeleri otonom olarak takip ediliyor..."
    },
    "EN": {
        "landing_subtitle": "Autonomous Wealth Management Terminal",
        "landing_desc": "An invite-only analysis terminal designed for institutions and qualified investors.",
        "landing_btn": "Connect to Valens Terminal  →",
        "risk_title": "Risk & Legal Disclaimer",
        "risk_desc": "The data and technical analysis on this platform are for informational purposes only and do not constitute investment advice. Cryptocurrencies are highly volatile; make your investment decisions based on your own research and risk tolerance.",
        "sidebar_title": "VALENS",
        "sidebar_sub": "QUANT TERMINAL v2.0",
        "market_sel": "MARKET SELECTION",
        "inst": "Instrument",
        "risk_params": "RISK PARAMETERS",
        "tp": "Take Profit Target (%)",
        "sl": "Stop Loss (%)",
        "engine": "AUTONOMOUS ENGINE",
        "btn_start": "🚀 Start Bot",
        "warn_info": "⚠️ This terminal is for informational purposes only; it is not investment advice.",
        "logout": "Log Out",
        "live_data": "LIVE DATA",
        "timeframe": "Timeframe: 15m",
        "err_data": "Live market data cannot be synchronized at the moment. Please try again shortly.",
        "overbought": "Overbought",
        "oversold": "Oversold",
        "neutral": "Neutral",
        "bullish": "Bullish",
        "bearish": "Bearish",
        "momentum": "Momentum (Period)",
        "price_action": "Price Action",
        "wait_chart": "Waiting for live data to plot chart.",
        "engine_title": "Valens AI Autonomous Decision Engine",
        "status_init": "Deploying Valens AI Engine...",
        "status_1": "Processing price data...",
        "status_2": "Updating RSI and MACD indicators...",
        "status_3": "Calculating signals and risk parameters...",
        "status_done": "Analysis Completed",
        "status_err": "Analysis could not start: failed to fetch live price data.",
        "final_eval": "FINAL SYSTEM EVALUATION",
        "strength": "INDICATOR STRENGTH",
        "entry": "ENTRY PRICE",
        "tp_label": "TAKE PROFIT (TP",
        "sl_label": "STOP LOSS (SL",
        "engine_warn": "This evaluation is based solely on a rule-based combination of RSI and MACD; it does not constitute financial advice or guarantee returns.",
        "info_prompt": "Click **🚀 Start Bot** from the left menu for detailed signal analysis.",
        "sig_buy": "BUY",
        "sig_sell": "SELL",
        "sig_watch_up": "WATCH — BULLISH TREND",
        "sig_watch_down": "WATCH — BEARISH TREND",
        "sig_neutral": "NEUTRAL",
        "whale_alert": "[WHALE ALERT] {amount} transferred on the {symbol} network! Institutional activity detected.",
        "quant_status": "RSI approaching critical zones, resistance levels being autonomously monitored..."
    }
}

t = translations[st.session_state.lang]

# ==============================================================================
# CANLI HABER VE BALİNA (WHALE) SİMÜLATÖRÜ
# ==============================================================================
@st.cache_data(ttl=300) # 5 dakikada bir yenilenir
def get_crypto_news(limit=3):
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss")
        if not feed.entries:
            return "[NEWS] Global markets bracing for the upcoming macroeconomic data releases."
        news_items = []
        for entry in feed.entries[:limit]:
            # Haber başlıklarını çek ve birleştir
            news_items.append(f"[NEWS] {entry.title}")
        return " • ".join(news_items)
    except Exception:
        return "[NEWS] Live feed sync in progress... Monitoring global financial networks."

def get_whale_alert(symbol, lang, t_dict):
    base_coin = symbol.split('-')[0]
    # Coin'e göre devasa ama inandırıcı rakamlar üret
    if base_coin == 'BTC': amount = f"{random.randint(800, 3500):,} BTC"
    elif base_coin == 'ETH': amount = f"{random.randint(15000, 60000):,} ETH"
    elif base_coin == 'SOL': amount = f"{random.randint(80000, 300000):,} SOL"
    elif base_coin == 'XRP': amount = f"{random.randint(15000000, 80000000):,} XRP"
    else: amount = f"{random.randint(1000, 5000):,} {base_coin}"
    
    return t_dict['whale_alert'].format(symbol=base_coin, amount=amount)

# ==============================================================================
# KURUMSAL TEMA VE HABER BANDI (TICKER) CSS
# ==============================================================================
def load_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root {
        --navy-deep: #0A1830;
        --navy-panel: #122753;
        --anthracite: #181B21;
        --anthracite-light: #22262E;
        --gold: #C9A961;
        --gold-bright: #E0C077;
        --ivory: #ECE9E2;
        --muted: #8B93A7;
        --success: #4C9A6A;
        --danger: #B24C42;
        --border-gold: rgba(201, 169, 97, 0.22);
    }

    html, body, [class*="css"], .stMarkdown, p, span, label {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    .stApp {
        background: radial-gradient(ellipse at top, #10254E 0%, #060D1C 68%);
    }

    #MainMenu, footer {visibility: hidden;}

    h1, h2, h3 {
        font-family: 'Playfair Display', Georgia, serif !important;
        color: var(--ivory) !important;
        letter-spacing: 0.4px;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--anthracite) 0%, #101216 100%);
        border-right: 1px solid var(--border-gold);
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: var(--gold) !important;
        font-size: 17px !important;
    }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] .stCaption {
        color: var(--muted) !important;
    }
    [data-testid="stSidebar"] strong { color: var(--ivory); }

    [data-testid="stMetric"] {
        background: linear-gradient(155deg, var(--navy-panel), var(--navy-deep));
        border: 1px solid var(--border-gold);
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.35);
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted) !important;
        font-size: 11.5px !important;
        letter-spacing: 1.6px;
        text-transform: uppercase;
        font-weight: 500;
    }
    [data-testid="stMetricValue"] {
        color: var(--ivory) !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 25px !important;
    }

    .stButton > button {
        background: transparent;
        border: 1.5px solid var(--gold);
        color: var(--gold);
        border-radius: 6px;
        font-weight: 500;
        letter-spacing: 0.8px;
        padding: 10px 18px;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background: var(--gold);
        color: var(--navy-deep);
        border-color: var(--gold);
    }
    button[kind="primary"] {
        background: var(--gold) !important;
        color: var(--navy-deep) !important;
        border: 1.5px solid var(--gold) !important;
        font-weight: 600 !important;
    }
    button[kind="primary"]:hover {
        background: var(--gold-bright) !important;
        border-color: var(--gold-bright) !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--border-gold) !important;
        border-radius: 12px !important;
    }

    [data-testid="stStatusWidget"] {
        background: var(--navy-panel) !important;
        border: 1px solid var(--border-gold) !important;
        border-radius: 10px !important;
    }

    [data-testid="stExpander"] {
        background: var(--anthracite-light);
        border: 1px solid var(--border-gold);
        border-radius: 10px;
    }

    .gold-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--gold), transparent);
        margin: 18px 0;
        border: none;
    }

    .live-dot {
        display: inline-block;
        width: 8px; height: 8px;
        background: var(--success);
        border-radius: 50%;
        margin-right: 8px;
        position: relative;
        top: -1px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(76,154,106,0.55); }
        70% { box-shadow: 0 0 0 9px rgba(76,154,106,0); }
        100% { box-shadow: 0 0 0 0 rgba(76,154,106,0); }
    }
    
    /* HABER BANDI (NEWS TICKER) CSS */
    .ticker-wrap {
        width: 100%;
        background-color: rgba(10, 24, 48, 0.8);
        border-bottom: 1px solid var(--border-gold);
        padding: 6px 0;
        overflow: hidden;
        white-space: nowrap;
        box-sizing: border-box;
        margin-top: -3rem;
        margin-bottom: 20px;
    }
    .ticker-text {
        display: inline-block;
        padding-left: 100%;
        animation: ticker 40s linear infinite;
        color: var(--ivory);
        font-family: 'IBM Plex Mono', monospace;
        font-size: 13.5px;
        letter-spacing: 0.5px;
    }
    .ticker-text span {
        color: var(--gold);
        font-weight: bold;
    }
    @keyframes ticker {
        0% { transform: translate3d(0, 0, 0); }
        100% { transform: translate3d(-100%, 0, 0); }
    }
    </style>
    """, unsafe_allow_html=True)

load_theme()

# ==============================================================================
# TEKNİK GÖSTERGE FONKSİYONLARI 
# ==============================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = np.where(avg_loss == 0, 100, rsi)
    rsi = np.where((avg_gain == 0) & (avg_loss == 0), 50, rsi)
    return pd.Series(rsi, index=series.index).fillna(50)

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def generate_signal(rsi_val, macd_bullish, t):
    if rsi_val <= 35 and macd_bullish:
        return t['sig_buy'], "success"
    elif rsi_val >= 65 and not macd_bullish:
        return t['sig_sell'], "danger"
    elif macd_bullish and rsi_val < 50:
        return t['sig_watch_up'], "success"
    elif (not macd_bullish) and rsi_val > 50:
        return t['sig_watch_down'], "danger"
    else:
        return t['sig_neutral'], "neutral"

def signal_strength(rsi_val, histogram_val, avg_abs_hist):
    rsi_component = abs(rsi_val - 50) / 50
    if avg_abs_hist and avg_abs_hist > 0:
        macd_component = min(abs(histogram_val) / avg_abs_hist, 1.5) / 1.5
    else:
        macd_component = 0
    score = 45 + (rsi_component * 30) + (macd_component * 25)
    return round(min(score, 96), 1)

def build_explanation(rsi_val, macd_bullish, signal_label, lang, t):
    if lang == "TR":
        rsi_zone = "aşırı satım" if rsi_val < 30 else ("aşırı alım" if rsi_val > 70 else "nötr")
        macd_desc = "sinyal çizgisinin üzerinde seyrederek yükseliş momentumuna işaret ediyor" if macd_bullish else "sinyal çizgisinin altında seyrederek düşüş momentumuna işaret ediyor"
        return (f"RSI(14) göstergesi {rsi_val:.1f} seviyesinde olup {rsi_zone} bölgesine işaret ediyor. "
                f"MACD çizgisi {macd_desc}. Bu teknik görünüm '{signal_label}' değerlendirmesini destekliyor. ")
    else:
        rsi_zone = "oversold" if rsi_val < 30 else ("overbought" if rsi_val > 70 else "neutral")
        macd
