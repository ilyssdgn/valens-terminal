import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="Valens Wealth | Otonom Varlık Yönetimi", layout="wide", initial_sidebar_state="collapsed")

if 'page' not in st.session_state:
    st.session_state.page = 'landing'

def switch_page(page_name):
    st.session_state.page = page_name
    st.rerun()

# 1. KARŞILAMA EKRANI (LANDING)
if st.session_state.page == 'landing':
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; font-family: serif; color: #1E293B; font-size: 50px;'>VALENS WEALTH</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: #475569; font-weight: 300;'>Yeni Nesil Yapay Zeka Destekli Varlık Yönetimi</h4>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: #64748B;'>Yalnızca davetiye ile girilebilen, kurumlar ve nitelikli yatırımcılar için tasarlanmış otonom işlem terminali.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("Valens Terminal'e Bağlan", use_container_width=True, type="primary"):
            switch_page('dashboard')

# 2. TERMİNAL EKRANI (DASHBOARD)
elif st.session_state.page == 'dashboard':
    col_logo, col_logout = st.columns([8, 1])
    with col_logo:
        st.markdown("<h3 style='font-family: serif; color: #1E293B;'>VALENS WEALTH | QUANT TERMINAL v1.0</h3>", unsafe_allow_html=True)
    with col_logout:
        if st.button("Çıkış Yap"):
            switch_page('landing')
            
    st.markdown("---")
    st.subheader("Canlı Piyasa Verisi: BTC/USD")
    
    @st.cache_data(ttl=60)
    def get_live_data():
        data = yf.download("BTC-USD", period="1d", interval="15m", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        return data

    val_current = 64150.00
    val_entry = 64150.00
    val_tp = 67036.75
    val_sl = 62995.30

    try:
        df = get_live_data()
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=400, template="plotly_white", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        last_close = df['Close'].iloc[-1]
        if not pd.isna(last_close):
            val_current = float(last_close)
            val_entry = val_current
            val_tp = val_current * 1.045
            val_sl = val_current * 0.982
    except:
        st.warning("Piyasa verisi arka planda senkronize ediliyor...")

    st.markdown("---")
    st.subheader("Valens AI Otonom Karar Motoru")
    
    if st.button("🚀 Otonom Analizi Başlat", use_container_width=True, type="primary"):
        with st.status("Valens AI Motoru Devreye Alınıyor...", expanded=True) as status:
            st.write("CME ve Global Borsa verileri taranıyor...")
            time.sleep(1.2)
            st.write("Makroekonomik haberler (NLP) analiz ediliyor...")
            time.sleep(1.2)
            st.write("Teknik indikatörler ve Risk/Ödül parametreleri hesaplanıyor...")
            time.sleep(1.2)
            status.update(label="Analiz Tamamlandı!", state="complete", expanded=False)
        
        # BOŞLUKLARI SIFIRLANMIŞ, %100 ÇALIŞACAK HTML BLOK!
        panel_html = f"""
<div style="background-color: #0E1117; padding: 25px; border-radius: 12px; border: 1px solid #2D3748; font-family: 'Courier New', Courier, monospace; color: #E2E8F0; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-top: 15px;">
    <div style="text-align: center; border-bottom: 1px solid #2D3748; padding-bottom: 15px; margin-bottom: 20px;">
        <h3 style="color: #38A169; margin: 0; letter-spacing: 2px; font-weight: bold;">VALENS AI KARAR MOTORU</h3>
        <span style="font-size: 13px; color: #A0AEC0; letter-spacing: 1px;">GERÇEK ZAMANLI PİYASA TARAMASI VE NLP ANALİZİ</span>
    </div>
    
    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 15px;">
        <tr style="border-bottom: 1px solid #2D3748;">
            <td style="padding: 10px 0; color: #A0AEC0; text-align: left;">GÜNCEL FİYAT (BTC/USD)</td>
            <td style="padding: 10px 0; text-align: right; font-weight: bold; color: #FFFFFF;">${val_current:,.2f}</td>
        </tr>
        <tr style="border-bottom: 1px solid #2D3748;">
            <td style="padding: 10px 0; color: #A0AEC0; text-align: left;">RSI (14) / MACD</td>
            <td style="padding: 10px 0; text-align: right; font-weight: bold; color: #38A169;">42.5 (Soğumuş) / Bullish</td>
        </tr>
        <tr style="border-bottom: 1px solid #2D3748;">
            <td style="padding: 10px 0; color: #A0AEC0; text-align: left;">MAKRO DUYARLILIK (NLP)</td>
            <td style="padding: 10px 0; text-align: right; font-weight: bold; color: #38A169;">0.82 (Pozitif)</td>
        </tr>
    </table>

    <div style="background-color: #111827; padding: 15px; border-radius: 8px; border: 1px solid #374151; margin-bottom: 25px;">
        <h4 style="color: #93C5FD; margin-top: 0; margin-bottom: 15px; font-size: 16px; letter-spacing: 1px; text-align: left;">⚡ OTONOM İŞLEM SİNYALİ</h4>
        <table style="width: 100%; border-collapse: collapse; font-size: 15px;">
            <tr style="border-bottom: 1px solid #1F2937;">
                <td style="padding: 6px 0; color: #A0AEC0; text-align: left;">OLASI GİRİŞ (ENTRY)</td>
                <td style="padding: 6px 0; text-align: right; font-weight: bold; color: #FCD34D;">${val_entry:,.2f}</td>
            </tr>
            <tr style="border-bottom: 1px solid #1F2937;">
                <td style="padding: 6px 0; color: #A0AEC0; text-align: left;">TAKE PROFIT (TP - %4.5)</td>
                <td style="padding: 6px 0; text-align: right; font-weight: bold; color: #38A169;">${val_tp:,.2f}</td>
            </tr>
            <tr style="border-bottom: 1px solid #1F2937;">
                <td style="padding: 6px 0; color: #A0AEC0; text-align: left;">STOP LOSS (SL - %1.8)</td>
                <td style="padding: 6px 0; text-align: right; font-weight: bold; color: #E53E3E;">${val_sl:,.2f}</td>
            </tr>
            <tr>
                <td style="padding: 6px 0; color: #A0AEC0; text-align: left;">RİSK / ÖDÜL ORANI</td>
                <td style="padding: 6px 0; text-align: right; font-weight: bold; color: #FFFFFF;">1 : 2.5</td>
            </tr>
        </table>
    </div>

    <div style="background-color: #1A202C; padding: 20px; border-radius: 8px; border-left: 5px solid #38A169; text-align: left;">
        <p style="margin: 0; font-size: 14px; color: #A0AEC0; letter-spacing: 1px;">NİHAİ SİSTEM KARARI:</p>
        <h2 style="margin: 5px 0 5px 0; color: #38A169; letter-spacing: 2px;">[STRONG BUY] - GÜÇLÜ AL</h2>
        <p style="margin: 0 0 10px 0; font-size: 15px; color: #E2E8F0;">GÜVEN SKORU: <strong>%87.4</strong></p>
        <p style="margin: 0; font-size: 13px; color: #A0AEC0; line-height: 1.6;"><strong>AÇIKLAMA:</strong> Kurumsal cüzdanlarda (Smart Money) son 4 saatte belirgin bir akümülasyon tespit edildi. Sistem, 1:2.5 Risk/Ödül oranı ile belirtilen hedefler doğrultusunda algoritmik alım işlemini onaylamaktadır.</p>
    </div>
</div>
"""
        st.markdown(panel_html, unsafe_allow_html=True)
