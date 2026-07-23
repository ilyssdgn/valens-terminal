import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Valens Wealth | Quant Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.block-container {padding:0 !important; margin:0 !important; max-width:100% !important;}
[data-testid="stAppViewContainer"] {padding:0 !important;}
[data-testid="stHeader"] {display:none !important;}
</style>
""", unsafe_allow_html=True)

TERMINAL_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Valens Wealth | Quant Terminal</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{
  --navy:#050b14;--navy-panel:#0b1523;--navy-panel-2:#0e1a2c;
  --gold:#D4AF37;--gold-bright:#f0c93a;--gold-dim:#8a6f1e;
  --green:#00c896;--red:#ff4d6d;--blue:#4da6ff;
  --text-primary:#e8e0cc;--text-secondary:#8a9bb5;--text-muted:#4a5a72;
  --border-gold:rgba(212,175,55,0.25);--border-panel:rgba(255,255,255,0.06);
}
html,body{width:100%;height:100%;background:var(--navy);color:var(--text-primary);font-family:'Inter',sans-serif;overflow:hidden;}
.terminal-root{display:flex;flex-direction:column;height:100vh;width:100%;}

/* NAVBAR */
.navbar{display:flex;align-items:center;justify-content:space-between;background:linear-gradient(180deg,#0a1526 0%,#060d18 100%);border-bottom:1px solid var(--border-gold);padding:0 20px;height:54px;flex-shrink:0;}
.navbar-left{display:flex;align-items:center;gap:14px;}
.logo-img{height:32px;width:auto;filter:drop-shadow(0 0 8px rgba(212,175,55,0.6));}
.brand-name{font-family:'Playfair Display',serif;font-size:18px;font-weight:700;color:var(--gold);letter-spacing:1.5px;text-transform:uppercase;}
.navbar-center{display:flex;gap:4px;}
.nav-tab{padding:6px 16px;border:none;background:transparent;color:var(--text-secondary);font-size:12px;font-weight:500;letter-spacing:0.8px;text-transform:uppercase;cursor:pointer;border-radius:4px;transition:all 0.2s;}
.nav-tab:hover,.nav-tab.active{background:rgba(212,175,55,0.12);color:var(--gold);}
.navbar-right{display:flex;align-items:center;gap:12px;}
.status-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 2s infinite;}
.status-text{font-size:11px;color:var(--text-secondary);letter-spacing:0.5px;}
.time-display{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--gold);letter-spacing:1px;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.4;}}

/* NEWS TICKER */
.ticker-bar{background:#060d18;border-bottom:1px solid var(--border-panel);height:28px;overflow:hidden;display:flex;align-items:center;flex-shrink:0;}
.ticker-label{background:var(--gold);color:#000;font-size:10px;font-weight:700;padding:0 10px;height:100%;display:flex;align-items:center;letter-spacing:1px;flex-shrink:0;}
.ticker-track{display:flex;animation:ticker-scroll 90s linear infinite;white-space:nowrap;}
.ticker-track:hover{animation-play-state:paused;}
.ticker-item{font-size:11px;color:var(--text-secondary);padding:0 30px;letter-spacing:0.3px;}
.ticker-item span{color:var(--gold);font-weight:600;}
@keyframes ticker-scroll{0%{transform:translateX(0);}100%{transform:translateX(-50%);}}

/* PRICE STRIP */
.price-strip{display:flex;align-items:center;gap:0;background:#080f1e;border-bottom:1px solid var(--border-panel);height:42px;padding:0 16px;flex-shrink:0;overflow-x:auto;}
.price-strip::-webkit-scrollbar{display:none;}
.instrument-btn{display:flex;align-items:center;gap:10px;padding:0 16px;height:100%;border:none;background:transparent;cursor:pointer;border-right:1px solid var(--border-panel);transition:all 0.2s;min-width:160px;}
.instrument-btn:hover,.instrument-btn.active{background:rgba(212,175,55,0.08);}
.instrument-btn.active{border-bottom:2px solid var(--gold);}
.inst-name{font-size:11px;font-weight:600;color:var(--text-secondary);letter-spacing:0.5px;}
.instrument-btn.active .inst-name{color:var(--gold);}
.inst-price{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;color:var(--text-primary);}
.inst-change{font-size:10px;font-weight:500;}
.inst-change.up{color:var(--green);}
.inst-change.dn{color:var(--red);}
.sr-badges{display:flex;gap:4px;margin-left:auto;}
.sr-badge{font-size:9px;padding:2px 5px;border-radius:3px;font-family:'IBM Plex Mono',monospace;font-weight:600;}
.sr-badge.r{background:rgba(255,77,109,0.15);color:var(--red);border:1px solid rgba(255,77,109,0.3);}
.sr-badge.s{background:rgba(0,200,150,0.15);color:var(--green);border:1px solid rgba(0,200,150,0.3);}

/* MAIN LAYOUT */
.main-body{display:flex;flex:1;overflow:hidden;}
.left-panel{width:260px;flex-shrink:0;background:var(--navy-panel);border-right:1px solid var(--border-panel);display:flex;flex-direction:column;overflow-y:auto;}
.center-panel{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.right-panel{width:280px;flex-shrink:0;background:var(--navy-panel);border-left:1px solid var(--border-panel);display:flex;flex-direction:column;overflow-y:auto;}

/* PANEL HEADERS */
.panel-header{padding:10px 14px;border-bottom:1px solid var(--border-panel);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
.panel-title{font-size:10px;font-weight:600;color:var(--gold);letter-spacing:1.5px;text-transform:uppercase;}
.panel-badge{font-size:9px;padding:2px 7px;border-radius:10px;background:rgba(212,175,55,0.15);color:var(--gold);border:1px solid var(--border-gold);}

/* SMART MONEY FLOW */
.smf-feed{padding:8px;}
.smf-item{background:var(--navy-panel-2);border:1px solid var(--border-panel);border-radius:6px;padding:10px 12px;margin-bottom:8px;border-left:3px solid var(--gold);}
.smf-item.buy-flow{border-left-color:var(--green);}
.smf-item.sell-flow{border-left-color:var(--red);}
.smf-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;}
.smf-actor{font-size:11px;font-weight:600;color:var(--text-primary);}
.smf-time{font-size:9px;color:var(--text-muted);}
.smf-action{font-size:12px;font-weight:700;margin-bottom:4px;}
.smf-action.buy{color:var(--green);}
.smf-action.sell{color:var(--red);}
.smf-detail{font-size:10px;color:var(--text-secondary);line-height:1.5;}
.smf-analysis{font-size:10px;color:var(--text-muted);margin-top:6px;padding-top:6px;border-top:1px solid var(--border-panel);font-style:italic;}

/* AI SIGNAL */
.signal-box{margin:10px;background:var(--navy-panel-2);border:1px solid var(--border-gold);border-radius:8px;padding:14px;}
.signal-direction{font-size:28px;font-weight:700;text-align:center;letter-spacing:2px;margin-bottom:4px;}
.signal-direction.buy{color:var(--green);}
.signal-direction.sell{color:var(--red);}
.signal-direction.hold{color:var(--gold);}
.signal-pair{font-size:11px;color:var(--text-secondary);text-align:center;margin-bottom:10px;}
.signal-confidence{display:flex;align-items:center;gap:8px;margin-bottom:10px;}
.conf-bar{flex:1;height:6px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden;}
.conf-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--gold-dim),var(--gold));}
.conf-pct{font-size:11px;font-weight:600;color:var(--gold);font-family:'IBM Plex Mono',monospace;}
.signal-levels{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:10px;}
.level-box{background:rgba(0,0,0,0.3);border-radius:5px;padding:7px;text-align:center;}
.level-label{font-size:9px;color:var(--text-muted);letter-spacing:0.5px;margin-bottom:3px;}
.level-val{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;}
.level-val.entry{color:var(--blue);}
.level-val.sl{color:var(--red);}
.level-val.tp{color:var(--green);}
.signal-rationale{font-size:10px;color:var(--text-secondary);line-height:1.6;padding-top:8px;border-top:1px solid var(--border-panel);}

/* CHART AREA */
.chart-container{flex:1;position:relative;background:#060d18;overflow:hidden;}
.chart-frame{width:100%;height:100%;border:none;}
.sr-overlay{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:10;}
.sr-line{position:absolute;left:0;right:0;height:1px;display:flex;align-items:center;}
.sr-line.resistance{background:rgba(255,77,109,0.5);}
.sr-line.support{background:rgba(0,200,150,0.5);}
.sr-line-label{position:absolute;right:8px;font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;padding:1px 5px;border-radius:3px;}
.sr-line.resistance .sr-line-label{color:var(--red);background:rgba(255,77,109,0.15);}
.sr-line.support .sr-line-label{color:var(--green);background:rgba(0,200,150,0.15);}

/* EVENTS PANEL */
.event-card{margin:10px;background:var(--navy-panel-2);border:1px solid var(--border-panel);border-radius:8px;overflow:hidden;}
.event-header{padding:10px 12px;background:rgba(212,175,55,0.08);border-bottom:1px solid var(--border-panel);display:flex;align-items:center;gap:8px;}
.event-flag{font-size:16px;}
.event-name{font-size:11px;font-weight:600;color:var(--text-primary);}
.event-time{font-size:10px;color:var(--text-muted);margin-left:auto;}
.event-impact{font-size:9px;padding:2px 6px;border-radius:3px;background:rgba(255,77,109,0.2);color:var(--red);border:1px solid rgba(255,77,109,0.3);}
.event-body{padding:10px 12px;}
.event-current{font-size:10px;color:var(--text-secondary);margin-bottom:8px;}
.event-current strong{color:var(--gold);}
.scenario{padding:7px 10px;border-radius:5px;margin-bottom:6px;}
.scenario.bull{background:rgba(0,200,150,0.08);border-left:3px solid var(--green);}
.scenario.bear{background:rgba(255,77,109,0.08);border-left:3px solid var(--red);}
.scenario-title{font-size:10px;font-weight:700;margin-bottom:3px;}
.scenario.bull .scenario-title{color:var(--green);}
.scenario.bear .scenario-title{color:var(--red);}
.scenario-text{font-size:10px;color:var(--text-secondary);line-height:1.5;}

/* SCROLLBAR */
::-webkit-scrollbar{width:4px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--border-gold);border-radius:2px;}

/* TAB CONTENT */
.tab-content{display:none;flex:1;overflow-y:auto;padding:16px;}
.tab-content.active{display:block;}
.portfolio-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;}
.port-card{background:var(--navy-panel-2);border:1px solid var(--border-panel);border-radius:8px;padding:14px;}
.port-card-label{font-size:10px;color:var(--text-muted);letter-spacing:0.5px;margin-bottom:6px;}
.port-card-value{font-family:'IBM Plex Mono',monospace;font-size:20px;font-weight:600;color:var(--gold);}
.port-card-sub{font-size:11px;color:var(--green);margin-top:4px;}
.positions-table{width:100%;border-collapse:collapse;}
.positions-table th{font-size:10px;color:var(--text-muted);text-align:left;padding:6px 10px;border-bottom:1px solid var(--border-panel);letter-spacing:0.5px;}
.positions-table td{font-size:11px;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.03);font-family:'IBM Plex Mono',monospace;}
.positions-table tr:hover td{background:rgba(212,175,55,0.04);}
.research-card{background:var(--navy-panel-2);border:1px solid var(--border-panel);border-radius:8px;padding:14px;margin-bottom:12px;}
.research-card h4{font-size:12px;color:var(--gold);margin-bottom:8px;}
.research-card p{font-size:11px;color:var(--text-secondary);line-height:1.7;}
.settings-row{display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border-panel);}
.settings-label{font-size:12px;color:var(--text-primary);}
.settings-val{font-size:12px;color:var(--gold);font-family:'IBM Plex Mono',monospace;}
</style>
</head>
<body>
<div class="terminal-root">

  <!-- NAVBAR -->
  <nav class="navbar">
    <div class="navbar-left">
      <img src="https://cdn.abacus.ai/images/0f498010-a0a5-4cf2-98cd-491f08add03c.png" class="logo-img" alt="Valens Wealth"/>
      <span class="brand-name">Valens Wealth</span>
    </div>
    <div class="navbar-center">
      <button class="nav-tab active" onclick="switchTab('terminal',this)">Terminal</button>
      <button class="nav-tab" onclick="switchTab('portfolio',this)">Portfolio</button>
      <button class="nav-tab" onclick="switchTab('research',this)">Research</button>
      <button class="nav-tab" onclick="switchTab('settings',this)">Settings</button>
      <button class="nav-tab" onclick="switchTab('account',this)">Account</button>
    </div>
    <div class="navbar-right">
      <div class="status-dot"></div>
      <span class="status-text">LIVE</span>
      <span class="time-display" id="clock">--:--:--</span>
    </div>
  </nav>

  <!-- NEWS TICKER -->
  <div class="ticker-bar">
    <div class="ticker-label">LIVE</div>
    <div style="overflow:hidden;flex:1;">
      <div class="ticker-track" id="tickerTrack">
        <span class="ticker-item">XAU/USD <span>4,053.98</span> ▼ -1.83%</span>
        <span class="ticker-item">ECB Faiz Kararı: <span>%2.40 sabit</span> — Lagarde: "Enflasyon hedefte"</span>
        <span class="ticker-item">TCMB Faiz: <span>%37.00</span> — Beklenti dahilinde, TL stabil</span>
        <span class="ticker-item">US İşsizlik Başvuruları: <span>187K</span> — Beklentinin altında, USD güçlendi</span>
        <span class="ticker-item">BTC/USD <span>118,240</span> ▲ +2.14%</span>
        <span class="ticker-item">EUR/USD <span>1.0842</span> ▼ -0.31% — ECB sonrası baskı</span>
        <span class="ticker-item">Hedge Fund Akışı: <span>Citadel</span> XAU'da 4,200 lot LONG pozisyon açtı</span>
        <span class="ticker-item">SPX500 <span>5,892</span> ▲ +0.47% — Tech sektörü liderliğinde</span>
        <span class="ticker-item">Altın: Merkez bankaları Q2'de <span>290 ton</span> net alım yaptı</span>
        <span class="ticker-item">Fed: Temmuz toplantısında faiz <span>sabit</span> beklentisi %94</span>
        <span class="ticker-item">XAU/USD <span>4,053.98</span> ▼ -1.83%</span>
        <span class="ticker-item">ECB Faiz Kararı: <span>%2.40 sabit</span> — Lagarde: "Enflasyon hedefte"</span>
        <span class="ticker-item">TCMB Faiz: <span>%37.00</span> — Beklenti dahilinde, TL stabil</span>
        <span class="ticker-item">US İşsizlik Başvuruları: <span>187K</span> — Beklentinin altında, USD güçlendi</span>
        <span class="ticker-item">BTC/USD <span>118,240</span> ▲ +2.14%</span>
        <span class="ticker-item">EUR/USD <span>1.0842</span> ▼ -0.31% — ECB sonrası baskı</span>
        <span class="ticker-item">Hedge Fund Akışı: <span>Citadel</span> XAU'da 4,200 lot LONG pozisyon açtı</span>
        <span class="ticker-item">SPX500 <span>5,892</span> ▲ +0.47% — Tech sektörü liderliğinde</span>
        <span class="ticker-item">Altın: Merkez bankaları Q2'de <span>290 ton</span> net alım yaptı</span>
        <span class="ticker-item">Fed: Temmuz toplantısında faiz <span>sabit</span> beklentisi %94</span>
      </div>
    </div>
  </div>

  <!-- PRICE STRIP -->
  <div class="price-strip">
    <button class="instrument-btn active" id="btn-XAU" onclick="switchInstrument('XAU',this)">
      <div>
        <div class="inst-name">XAU/USD · OZ</div>
        <div class="inst-price" id="price-XAU">4,053.98</div>
        <div class="inst-change dn" id="chg-XAU">▼ -75.37 (-1.83%)</div>
      </div>
      <div class="sr-badges">
        <span class="sr-badge r">R 4,085</span>
        <span class="sr-badge s">S 4,040</span>
      </div>
    </button>
    <button class="instrument-btn" id="btn-BTC" onclick="switchInstrument('BTC',this)">
      <div>
        <div class="inst-name">BTC/USD</div>
        <div class="inst-price" id="price-BTC">118,240</div>
        <div class="inst-change up" id="chg-BTC">▲ +2,480 (+2.14%)</div>
      </div>
      <div class="sr-badges">
        <span class="sr-badge r">R 120K</span>
        <span class="sr-badge s">S 115K</span>
      </div>
    </button>
    <button class="instrument-btn" id="btn-EUR" onclick="switchInstrument('EUR',this)">
      <div>
        <div class="inst-name">EUR/USD</div>
        <div class="inst-price" id="price-EUR">1.0842</div>
        <div class="inst-change dn" id="chg-EUR">▼ -0.0034 (-0.31%)</div>
      </div>
      <div class="sr-badges">
        <span class="sr-badge r">R 1.092</span>
        <span class="sr-badge s">S 1.078</span>
      </div>
    </button>
    <button class="instrument-btn" id="btn-SPX" onclick="switchInstrument('SPX',this)">
      <div>
        <div class="inst-name">SPX500</div>
        <div class="inst-price" id="price-SPX">5,892</div>
        <div class="inst-change up" id="chg-SPX">▲ +27.4 (+0.47%)</div>
      </div>
      <div class="sr-badges">
        <span class="sr-badge r">R 5,950</span>
        <span class="sr-badge s">S 5,820</span>
      </div>
    </button>
  </div>

  <!-- MAIN BODY -->
  <div class="main-body">

    <!-- LEFT PANEL: Smart Money Flow -->
    <div class="left-panel">
      <div class="panel-header">
        <span class="panel-title">Smart Money Flow</span>
        <span class="panel-badge">LIVE</span>
      </div>
      <div class="smf-feed" id="smfFeed">
        <div class="smf-item buy-flow">
          <div class="smf-header"><span class="smf-actor">Citadel LLC</span><span class="smf-time">14:32 UTC</span></div>
          <div class="smf-action buy">▲ LONG — XAU/USD</div>
          <div class="smf-detail">4,200 lot · Giriş: 4,048 · Hedef: 4,120</div>
          <div class="smf-analysis">ECB faiz kararı sonrası USD zayıflaması beklentisiyle pozisyon açıldı. Teknik: 4,040 desteği üzerinde tutunma.</div>
        </div>
        <div class="smf-item sell-flow">
          <div class="smf-header"><span class="smf-actor">Bridgewater</span><span class="smf-time">13:58 UTC</span></div>
          <div class="smf-action sell">▼ SHORT — EUR/USD</div>
          <div class="smf-detail">1,800 lot · Giriş: 1.0875 · Hedef: 1.0780</div>
          <div class="smf-analysis">ECB'nin şahin duruşu beklentinin altında kaldı. EUR/USD 1.090 direncinden döndü, momentum satış yönünde.</div>
        </div>
        <div class="smf-item buy-flow">
          <div class="smf-header"><span class="smf-actor">BlackRock</span><span class="smf-time">13:15 UTC</span></div>
          <div class="smf-action buy">▲ LONG — BTC/USD</div>
          <div class="smf-detail">850 lot · Giriş: 116,400 · Hedef: 122,000</div>
          <div class="smf-analysis">Spot ETF akışları güçlü. 115K destek bölgesinden teknik alım. Risk iştahı artıyor.</div>
        </div>
        <div class="smf-item sell-flow">
          <div class="smf-header"><span class="smf-actor">Goldman Sachs</span><span class="smf-time">12:44 UTC</span></div>
          <div class="smf-action sell">▼ HEDGE — XAU/USD</div>
          <div class="smf-detail">2,100 lot · Giriş: 4,065 · Hedef: 4,000</div>
          <div class="smf-analysis">Portföy hedge'i. US İşsizlik verisi beklentinin altında geldi, USD güçlendi, altın baskı altında.</div>
        </div>
      </div>

      <!-- AI SIGNAL -->
      <div class="panel-header" style="margin-top:auto;">
        <span class="panel-title">AI Signal Engine</span>
        <span class="panel-badge" id="sigBadge">SELL</span>
      </div>
      <div class="signal-box">
        <div class="signal-direction sell" id="sigDir">▼ SELL</div>
        <div class="signal-pair" id="sigPair">XAU/USD · Confidence: 74%</div>
        <div class="signal-confidence">
          <div class="conf-bar"><div class="conf-fill" id="confFill" style="width:74%;"></div></div>
          <span class="conf-pct" id="confPct">74%</span>
        </div>
        <div class="signal-levels">
          <div class="level-box"><div class="level-label">ENTRY</div><div class="level-val entry" id="sigEntry">4,053.98</div></div>
          <div class="level-box"><div class="level-label">STOP</div><div class="level-val sl" id="sigSL">4,090.00</div></div>
          <div class="level-box"><div class="level-label">TARGET</div><div class="level-val tp" id="sigTP">4,000.00</div></div>
        </div>
        <div class="signal-rationale" id="sigRationale">
          RSI(14): 38.2 — aşırı satım bölgesine yaklaşıyor. MACD negatif momentum. EMA200 altında seyir. US İşsizlik verisi USD'yi güçlendirdi. ECB kararı EUR/USD'yi baskıladı, risk-off ortamı altın için çift yönlü baskı yaratıyor. Kısa vadeli SELL, 4,000 psikolojik destek hedef.
        </div>
      </div>
    </div>

    <!-- CENTER PANEL -->
    <div class="center-panel">

      <!-- TERMINAL TAB -->
      <div id="tab-terminal" class="tab-content active" style="padding:0;display:flex;flex-direction:column;flex:1;overflow:hidden;">
        <div class="chart-container" id="chartContainer">
          <iframe id="tvChart" class="chart-frame"
            src="https://www.tradingview.com/widgetembed/?frameElementId=tvChart&symbol=OANDA%3AXAUUSD&interval=60&hidesidetoolbar=0&hidetoptoolbar=0&symboledit=1&saveimage=1&toolbarbg=060d18&studies=RSI%4014%7CMACD%4012%2C26%2C9&theme=dark&style=1&timezone=Europe%2FIstanbul&withdateranges=1&showpopupbutton=1&locale=en"
            allowtransparency="true" allowfullscreen="true">
          </iframe>
          <!-- S/R OVERLAY -->
          <div class="sr-overlay" id="srOverlay"></div>
        </div>
      </div>

      <!-- PORTFOLIO TAB -->
      <div id="tab-portfolio" class="tab-content" style="display:none;">
        <div class="portfolio-grid">
          <div class="port-card"><div class="port-card-label">TOTAL AUM</div><div class="port-card-value">$4.82M</div><div class="port-card-sub">▲ +$142K today</div></div>
          <div class="port-card"><div class="port-card-label">DAILY P&L</div><div class="port-card-value" style="color:var(--green);">+$142,380</div><div class="port-card-sub">▲ +2.87% vs yesterday</div></div>
          <div class="port-card"><div class="port-card-label">OPEN POSITIONS</div><div class="port-card-value">7</div><div class="port-card-sub">3 Long · 4 Short</div></div>
          <div class="port-card"><div class="port-card-label">WIN RATE (30D)</div><div class="port-card-value" style="color:var(--gold);">68.4%</div><div class="port-card-sub">Sharpe: 2.14</div></div>
        </div>
        <table class="positions-table">
          <thead><tr><th>INSTRUMENT</th><th>DIRECTION</th><th>ENTRY</th><th>CURRENT</th><th>P&L</th><th>SIZE</th></tr></thead>
          <tbody>
            <tr><td>XAU/USD</td><td style="color:var(--red);">SHORT</td><td>4,065.00</td><td>4,053.98</td><td style="color:var(--green);">+$23,100</td><td>2,100 lot</td></tr>
            <tr><td>BTC/USD</td><td style="color:var(--green);">LONG</td><td>116,400</td><td>118,240</td><td style="color:var(--green);">+$15,640</td><td>850 lot</td></tr>
            <tr><td>EUR/USD</td><td style="color:var(--red);">SHORT</td><td>1.0875</td><td>1.0842</td><td style="color:var(--green);">+$5,940</td><td>1,800 lot</td></tr>
            <tr><td>SPX500</td><td style="color:var(--green);">LONG</td><td>5,840</td><td>5,892</td><td style="color:var(--green);">+$5,200</td><td>100 lot</td></tr>
          </tbody>
        </table>
      </div>

      <!-- RESEARCH TAB -->
      <div id="tab-research" class="tab-content" style="display:none;">
        <div class="research-card"><h4>XAU/USD — Makro Görünüm</h4><p>Merkez bankaları Q2 2026'da 290 ton net altın alımı gerçekleştirdi. Fed'in faiz indirimi beklentileri ve jeopolitik riskler altın talebini desteklemeye devam ediyor. Teknik olarak 4,000 USD kritik destek; bu seviyenin korunması durumunda 4,200 hedefi gündemde.</p></div>
        <div class="research-card"><h4>ECB Kararı Analizi — 23 Temmuz 2026</h4><p>ECB faiz oranını %2.40'ta sabit tuttu. Lagarde'ın açıklamaları beklentinin altında şahin kaldı. EUR/USD 1.090 direncinden döndü. Kısa vadede 1.078 desteği test edilebilir. Orta vadede EUR için nötr görünüm.</p></div>
        <div class="research-card"><h4>BTC/USD — Kurumsal Akış</h4><p>Spot Bitcoin ETF'lerine haftalık net giriş $2.1 milyar. BlackRock ve Fidelity fonları ağırlık artırıyor. 115K güçlü destek bölgesi. 120K psikolojik direnç aşılırsa 130K hedefi devreye girer.</p></div>
      </div>

      <!-- SETTINGS TAB -->
      <div id="tab-settings" class="tab-content" style="display:none;">
        <div class="settings-row"><span class="settings-label">Default Instrument</span><span class="settings-val">XAU/USD</span></div>
        <div class="settings-row"><span class="settings-label">Chart Interval</span><span class="settings-val">1H</span></div>
        <div class="settings-row"><span class="settings-label">Signal Confidence Threshold</span><span class="settings-val">65%</span></div>
        <div class="settings-row"><span class="settings-label">Risk Per Trade</span><span class="settings-val">1.5%</span></div>
        <div class="settings-row"><span class="settings-label">Timezone</span><span class="settings-val">Europe/Istanbul</span></div>
        <div class="settings-row"><span class="settings-label">Theme</span><span class="settings-val">Dark — Oxford Navy</span></div>
        <div class="settings-row"><span class="settings-label">News Feed</span><span class="settings-val">LIVE · Auto-refresh 60s</span></div>
        <div class="settings-row"><span class="settings-label">Terminal Version</span><span class="settings-val">v3.1.0</span></div>
      </div>

      <!-- ACCOUNT TAB -->
      <div id="tab-account" class="tab-content" style="display:none;">
        <div class="port-card" style="margin-bottom:12px;"><div class="port-card-label">ACCOUNT HOLDER</div><div class="port-card-value" style="font-size:16px;">Valens Wealth Capital</div><div class="port-card-sub">Institutional · Tier 1</div></div>
        <div class="settings-row"><span class="settings-label">Account ID</span><span class="settings-val">VWC-2026-001</span></div>
        <div class="settings-row"><span class="settings-label">Account Type</span><span class="settings-val">Prime Brokerage</span></div>
        <div class="settings-row"><span class="settings-label">Leverage</span><span class="settings-val">1:100</span></div>
        <div class="settings-row"><span class="settings-label">Margin Used</span><span class="settings-val">$482,000</span></div>
        <div class="settings-row"><span class="settings-label">Free Margin</span><span class="settings-val">$4,338,000</span></div>
        <div class="settings-row"><span class="settings-label">API Status</span><span class="settings-val" style="color:var(--green);">CONNECTED</span></div>
      </div>

    </div>

    <!-- RIGHT PANEL: Events -->
    <div class="right-panel">
      <div class="panel-header">
        <span class="panel-title">Key Events</span>
        <span class="panel-badge">23 TEMMUZ</span>
      </div>

      <!-- ECB -->
      <div class="event-card">
        <div class="event-header">
          <span class="event-flag">🇪🇺</span>
          <div><div class="event-name">ECB Faiz Kararı</div></div>
          <span class="event-time">15:15 UTC</span>
          <span class="event-impact">🔴 YÜK</span>
        </div>
        <div class="event-body">
          <div class="event-current">Açıklanan: <strong>%2.40 (Sabit)</strong> · Önceki: %2.40</div>
          <div class="scenario bull">
            <div class="scenario-title">▲ ALIM SENARYOSU</div>
            <div class="scenario-text">Lagarde "yakında faiz indirimi" sinyali verirse → EUR/USD 1.095'e yükselir → XAU/USD USD zayıflamasıyla 4,085 direncini test eder. <strong>XAU LONG, EUR LONG.</strong></div>
          </div>
          <div class="scenario bear">
            <div class="scenario-title">▼ SATIM SENARYOSU</div>
            <div class="scenario-text">ECB "faiz sabit kalacak" mesajı verirse → EUR/USD 1.078'e düşer → USD güçlenir, XAU 4,000 desteğini test eder. <strong>XAU SHORT, EUR SHORT.</strong></div>
          </div>
        </div>
      </div>

      <!-- TCMB -->
      <div class="event-card">
        <div class="event-header">
          <span class="event-flag">🇹🇷</span>
          <div><div class="event-name">TCMB Faiz Kararı</div></div>
          <span class="event-time">14:00 UTC</span>
          <span class="event-impact">🔴 YÜK</span>
        </div>
        <div class="event-body">
          <div class="event-current">Açıklanan: <strong>%37.00 (Sabit)</strong> · Önceki: %40.00</div>
          <div class="scenario bull">
            <div class="scenario-title">▲ TL GÜÇLENME</div>
            <div class="scenario-text">TCMB faiz indirimi hızını yavaşlatırsa → TL stabilize olur → USD/TRY baskı altında. Yerel yatırımcı altın talebinde azalma.</div>
          </div>
          <div class="scenario bear">
            <div class="scenario-title">▼ TL ZAYIFLAMA</div>
            <div class="scenario-text">Agresif faiz indirimi sinyali gelirse → TL değer kaybeder → Yerel altın talebi artar, XAU/TRY yükselir. <strong>XAU LONG (TRY bazlı).</strong></div>
          </div>
        </div>
      </div>

      <!-- US JOBLESS -->
      <div class="event-card">
        <div class="event-header">
          <span class="event-flag">🇺🇸</span>
          <div><div class="event-name">US İşsizlik Başvuruları</div></div>
          <span class="event-time">15:30 UTC</span>
          <span class="event-impact">🟡 ORT</span>
        </div>
        <div class="event-body">
          <div class="event-current">Açıklanan: <strong>187K</strong> · Beklenti: 215K · Önceki: 221K</div>
          <div class="scenario bull">
            <div class="scenario-title">▲ USD GÜÇLÜ (GERÇEKLEŞTI)</div>
            <div class="scenario-text">187K beklentinin çok altında → İşgücü piyasası güçlü → Fed faiz indirimi gecikir → USD güçlendi → XAU baskı altında. <strong>XAU SHORT aktif.</strong></div>
          </div>
          <div class="scenario bear">
            <div class="scenario-title">▼ SENARYO (GERÇEKLEŞMEDİ)</div>
            <div class="scenario-text">215K+ gelseydi → İşgücü zayıflıyor → Fed dovish → USD zayıflar → XAU yükselirdi.</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</div>

<script>
// CLOCK
function updateClock(){
  const now=new Date();
  document.getElementById('clock').textContent=
    now.toUTCString().slice(17,25)+' UTC';
}
setInterval(updateClock,1000);
updateClock();

// TAB SWITCHING
function switchTab(tab,btn){
  document.querySelectorAll('.tab-content').forEach(t=>{t.style.display='none';t.classList.remove('active');});
  document.querySelectorAll('.nav-tab').forEach(b=>b.classList.remove('active'));
  const el=document.getElementById('tab-'+tab);
  if(el){el.style.display='flex';el.classList.add('active');}
  if(btn)btn.classList.add('active');
  if(tab==='terminal'){
    const el2=document.getElementById('tab-terminal');
    if(el2){el2.style.display='flex';}
  }
}

// INSTRUMENT DATA
const instruments={
  XAU:{symbol:'OANDA:XAUUSD',price:'4,053.98',change:'▼ -75.37 (-1.83%)',dir:'sell',conf:74,entry:'4,053.98',sl:'4,090.00',tp:'4,000.00',rationale:'RSI(14): 38.2 — aşırı satım bölgesine yaklaşıyor. MACD negatif momentum. EMA200 altında seyir. US İşsizlik verisi USD\'yi güçlendirdi. Kısa vadeli SELL, 4,000 psikolojik destek hedef.',sr:{r3:4155,r2:4118,r1:4085,s1:4040,s2:4000,s3:3960},chartMin:3940,chartMax:4180},
  BTC:{symbol:'COINBASE:BTCUSD',price:'118,240',change:'▲ +2,480 (+2.14%)',dir:'buy',conf:68,entry:'116,400',sl:'113,000',tp:'122,000',rationale:'Spot ETF akışları güçlü. 115K destek bölgesinden teknik alım. RSI(14): 58 — momentum pozitif. MACD bullish crossover.',sr:{r3:125000,r2:122000,r1:120000,s1:115000,s2:112000,s3:108000},chartMin:107000,chartMax:127000},
  EUR:{symbol:'FX:EURUSD',price:'1.0842',change:'▼ -0.0034 (-0.31%)',dir:'sell',conf:61,entry:'1.0875',sl:'1.0920',tp:'1.0780',rationale:'ECB kararı beklentinin altında şahin kaldı. EUR/USD 1.090 direncinden döndü. MACD negatif. Kısa vadeli SELL.',sr:{r3:1.098,r2:1.092,r1:1.088,s1:1.078,s2:1.072,s3:1.065},chartMin:1.062,chartMax:1.100},
  SPX:{symbol:'SP:SPX',price:'5,892',change:'▲ +27.4 (+0.47%)',dir:'buy',conf:55,entry:'5,840',sl:'5,780',tp:'5,950',rationale:'Tech sektörü liderliğinde yükseliş. EMA50 üzerinde seyir. Momentum pozitif ancak 5,950 direncinde dikkatli olunmalı.',sr:{r3:6050,r2:5980,r1:5950,s1:5820,s2:5750,s3:5680},chartMin:5660,chartMax:6080}
};

let currentInst='XAU';

function switchInstrument(inst,btn){
  currentInst=inst;
  document.querySelectorAll('.instrument-btn').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
  const d=instruments[inst];
  // Update chart
  document.getElementById('tvChart').src=
    'https://www.tradingview.com/widgetembed/?frameElementId=tvChart&symbol='+encodeURIComponent(d.symbol)+'&interval=60&hidesidetoolbar=0&hidetoptoolbar=0&symboledit=1&saveimage=1&toolbarbg=060d18&studies=RSI%4014%7CMACD%4012%2C26%2C9&theme=dark&style=1&timezone=Europe%2FIstanbul&withdateranges=1&showpopupbutton=1&locale=en';
  // Update signal
  const dir=d.dir;
  const sigDir=document.getElementById('sigDir');
  sigDir.textContent=(dir==='buy'?'▲ BUY':'▼ SELL');
  sigDir.className='signal-direction '+(dir==='buy'?'buy':'sell');
  document.getElementById('sigBadge').textContent=(dir==='buy'?'BUY':'SELL');
  document.getElementById('sigPair').textContent=inst+'/USD · Confidence: '+d.conf+'%';
  document.getElementById('confFill').style.width=d.conf+'%';
  document.getElementById('confPct').textContent=d.conf+'%';
  document.getElementById('sigEntry').textContent=d.entry;
  document.getElementById('sigSL').textContent=d.sl;
  document.getElementById('sigTP').textContent=d.tp;
  document.getElementById('sigRationale').textContent=d.rationale;
  // Draw S/R
  drawSR(inst);
}

function drawSR(inst){
  const overlay=document.getElementById('srOverlay');
  overlay.innerHTML='';
  const d=instruments[inst];
  const sr=d.sr;
  const min=d.chartMin;
  const max=d.chartMax;
  const range=max-min;
  const levels=[
    {price:sr.r3,type:'resistance',label:'R3'},
    {price:sr.r2,type:'resistance',label:'R2'},
    {price:sr.r1,type:'resistance',label:'R1'},
    {price:sr.s1,type:'support',label:'S1'},
    {price:sr.s2,type:'support',label:'S2'},
    {price:sr.s3,type:'support',label:'S3'}
  ];
  levels.forEach(function(lv){
    const pct=((max-lv.price)/range)*100;
    if(pct<0||pct>100)return;
    const line=document.createElement('div');
    line.className='sr-line '+lv.type;
    line.style.top=pct+'%';
    const label=document.createElement('div');
    label.className='sr-line-label';
    label.textContent=lv.label+' '+lv.price.toLocaleString();
    line.appendChild(label);
    overlay.appendChild(line);
  });
}

// Initial S/R draw
drawSR('XAU');

// SMF auto-rotate (simulated live feed)
const smfData=[
  {actor:'Citadel LLC',time:'14:32 UTC',dir:'buy',inst:'XAU/USD',detail:'4,200 lot · Giriş: 4,048 · Hedef: 4,120',analysis:'ECB faiz kararı sonrası USD zayıflaması beklentisiyle pozisyon açıldı.'},
  {actor:'Bridgewater',time:'13:58 UTC',dir:'sell',inst:'EUR/USD',detail:'1,800 lot · Giriş: 1.0875 · Hedef: 1.0780',analysis:'ECB şahin duruşu beklentinin altında kaldı. EUR/USD 1.090 direncinden döndü.'},
  {actor:'BlackRock',time:'13:15 UTC',dir:'buy',inst:'BTC/USD',detail:'850 lot · Giriş: 116,400 · Hedef: 122,000',analysis:'Spot ETF akışları güçlü. 115K destek bölgesinden teknik alım.'},
  {actor:'Goldman Sachs',time:'12:44 UTC',dir:'sell',inst:'XAU/USD',detail:'2,100 lot · Giriş: 4,065 · Hedef: 4,000',analysis:'Portföy hedge\'i. US İşsizlik verisi USD\'yi güçlendirdi.'},
  {actor:'JPMorgan',time:'12:10 UTC',dir:'buy',inst:'SPX500',detail:'500 lot · Giriş: 5,840 · Hedef: 5,950',analysis:'Tech sektörü momentum pozitif. EMA50 üzerinde tutunma.'},
  {actor:'Two Sigma',time:'11:55 UTC',dir:'sell',inst:'XAU/USD',detail:'1,500 lot · Giriş: 4,072 · Hedef: 4,010',analysis:'Quant modeli SELL sinyali. RSI aşırı alım bölgesinden dönüş.'}
];

let smfIdx=0;
function rotateSMF(){
  const feed=document.getElementById('smfFeed');
  const d=smfData[smfIdx%smfData.length];
  const item=document.createElement('div');
  item.className='smf-item '+(d.dir==='buy'?'buy-flow':'sell-flow');
  item.innerHTML=
    '<div class="smf-header"><span class="smf-actor">'+d.actor+'</span><span class="smf-time">'+d.time+'</span></div>'+
    '<div class="smf-action '+(d.dir==='buy'?'buy':'sell')+'">'+(d.dir==='buy'?'▲ LONG':'▼ SHORT')+' — '+d.inst+'</div>'+
    '<div class="smf-detail">'+d.detail+'</div>'+
    '<div class="smf-analysis">'+d.analysis+'</div>';
  feed.insertBefore(item,feed.firstChild);
  if(feed.children.length>6)feed.removeChild(feed.lastChild);
  smfIdx++;
}
setInterval(rotateSMF,8000);
</script>
</body>
</html>
"""

components.html(TERMINAL_HTML, height=950, scrolling=False)
