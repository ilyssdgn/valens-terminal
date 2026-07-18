import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import time

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
    st.session_state.lang = 'EN' # Varsayılan dili İngilizce yaptık (Global Vizyon)

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
        "sig_watch_up": "İZLE — YÜKSELİŞ EĞİLİMİ
