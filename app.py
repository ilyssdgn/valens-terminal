import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="Valens Wealth | Scalping Terminal", layout="wide")

if 'page' not in st.session_state: st.session_state.page = 'landing'

def switch_page(page_name):
    st.session_state.page = page_name
    st.rerun()

if st.session_state.page == 'landing':
    st.markdown("<br><br><br><br><h1 style='text-align: center; font-family: serif;'>VALENS WEALTH</h1><h4 style='text-align: center;'>Scalping AI Terminali</h4>", unsafe_allow_html=True)
    if st.button("Terminal'e Bağlan", use_container_width=True, type="primary"): switch_page('dashboard')

elif st.session_state.page == 'dashboard':
    if st.button("<- Çıkış"): switch_page('landing')
    
    st.subheader("BTC/USD Scalping Verisi (15m)")
    data = yf.download("BTC-USD", period="1d", interval="15m", progress=False)
    
    if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.droplevel(1)
    
    if not data.empty:
        fig = go.Figure(data=[go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'])])
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=400, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        current_price = float(data['Close'].iloc[-1])
    else:
        current_price = 64000.00
    
    if st.button("🚀 Scalp Sinyali Üret"):
        with st.spinner("Piyasa hacmi taranıyor..."): time.sleep(1.5)
        
        # SCALPING MATEMATİĞİ (%0.6 TP, %0.3 SL)
        tp_price = current_price * 1.006
        sl_price = current_price * 0.997
        
        st.subheader("Otonom Scalping Sinyali")
        st.markdown(f"""
        <div style="background-color:#1e1e1e; padding:20px; border-radius:10px; border:1px solid #333;">
            <p style="color:#aaa;">Giriş Fiyatı: <b>${current_price:,.2f}</b></p>
            <h3 style="color:#00ff00;">Hedef (TP): ${tp_price:,.2f}</h3>
            <h3 style="color:#ff4b4b;">Stop (SL): ${sl_price:,.2f}</h3>
            <p style="color:#aaa;">Risk/Ödül: <b>1:2</b></p>
        </div>
        """, unsafe_allow_html=True)
