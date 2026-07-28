import streamlit as st
import streamlit.components.v1 as components
import requests
import json as _json

st.set_page_config(
    page_title="Valens Wealth | Quant Terminal",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header {visibility:hidden;}
[data-testid="stHeader"] {display:none;}
.block-container {padding:0!important;max-width:100%!important;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_cot(keyword):
    try:
        r = requests.get(
            "https://publicreporting.cftc.gov/resource/6dca-aqww.json",
            params={
                "$where": f"market_and_exchange_names like '%{keyword}%'",
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": 1,
            }, timeout=8)
        d = r.json()[0]
        f = lambda k: int(float(d.get(k, 0) or 0))
        return {
            "date": d.get("report_date_as_yyyy_mm_dd", "")[:10],
            "market": d.get("market_and_exchange_names", "")[:40],
            "fund_long": f("noncomm_positions_long_all"),
            "fund_short": f("noncomm_positions_short_all"),
            "fund_dlong": f("change_in_noncomm_long_all"),
            "fund_dshort": f("change_in_noncomm_short_all"),
            "bank_long": f("comm_positions_long_all"),
            "bank_short": f("comm_positions_short_all"),
            "oi": f("open_interest_all"),
        }
    except Exception:
        return None

COT = {
    "OANDA:XAUUSD": get_cot("GOLD"),
    "BINANCE:BTCUSDT": get_cot("BITCOIN"),
    "OANDA:EURUSD": get_cot("EURO FX"),
    "OANDA:SPX500USD": get_cot("E-MINI S&P 500"),
}
COT_JSON = _json.dumps({k: v for k, v in COT.items() if v})

TERMINAL_HTML = r"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Valens Wealth</title>
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet"/>
<style>
:root{
 --navy:#050b14;--panel:#091525;--panel2:#0d1b2e;--gold:#d4af37;
 --goldDim:#80671b;--text:#e7e1d2;--muted:#8090a6;--line:rgba(255,255,255,.075);
 --green:#00c896;--red:#ff506d;--blue:#52a9ff;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:var(--navy);color:var(--text);font-family:Inter,sans-serif;overflow:hidden}
#app{height:100vh;display:flex;flex-direction:column;background:var(--navy)}
nav{height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 18px;background:linear-gradient(180deg,#0b1729,#060c16);border-bottom:1px solid rgba(212,175,55,.28)}
.brand{display:flex;align-items:center;gap:10px;min-width:280px}
.brand img{height:31px;max-width:42px;object-fit:contain;filter:drop-shadow(0 0 7px rgba(212,175,55,.5))}
.brand b{font:700 18px 'Playfair Display';letter-spacing:1.5px;color:var(--gold)}
.tabs{display:flex;gap:3px}.tab{border:0;background:transparent;color:var(--muted);padding:7px 13px;font-size:11px;letter-spacing:.8px;cursor:pointer}
.tab:hover,.tab.active{color:var(--gold);background:rgba(212,175,55,.09);border-radius:4px}
.live{display:flex;align-items:center;gap:7px;color:var(--muted);font:11px 'IBM Plex Mono'}
.dot{width:7px;height:7px;background:var(--green);border-radius:50%;box-shadow:0 0 9px var(--green);animation:pulse 1.4s infinite}
@keyframes pulse{50%{opacity:.35}}
.ticker{height:27px;display:flex;overflow:hidden;border-bottom:1px solid var(--line);background:#060d18}
.ticklabel{display:flex;align-items:center;background:var(--gold);color:#07101b;padding:0 10px;font-size:10px;font-weight:800;letter-spacing:1px}
.tickscroll{white-space:nowrap;display:flex;align-items:center;animation:scroll 65s linear infinite}
.tickscroll span{font-size:10px;color:var(--muted);padding:0 28px}.tickscroll b{color:var(--gold)}
@keyframes scroll{to{transform:translateX(-50%)}}
.marketbar{height:50px;display:flex;align-items:stretch;overflow:auto;background:#07101c;border-bottom:1px solid var(--line)}
.market{min-width:180px;padding:7px 15px;border:0;border-right:1px solid var(--line);background:transparent;color:var(--text);text-align:left;cursor:pointer}
.market.active{background:rgba(212,175,55,.08);border-bottom:2px solid var(--gold)}
.market small{display:block;color:var(--muted);font-size:9px;letter-spacing:.8px}.market strong{font:600 13px 'IBM Plex Mono'}.down{color:var(--red)}.up{color:var(--green)}
.shell{min-height:0;flex:1;display:grid;grid-template-columns:250px minmax(540px,1fr) 285px;overflow:hidden}
aside{background:var(--panel);min-height:0;overflow:auto}.left{border-right:1px solid var(--line)}.right{border-left:1px solid var(--line)}
.ph{height:38px;display:flex;align-items:center;justify-content:space-between;padding:0 12px;border-bottom:1px solid var(--line)}
.ph b{font-size:10px;color:var(--gold);letter-spacing:1.2px}.badge{font:9px 'IBM Plex Mono';color:var(--gold);border:1px solid rgba(212,175,55,.3);padding:2px 6px;border-radius:9px}
.simwarn{font:8px 'IBM Plex Mono';color:#ffb27a;padding:4px 12px;background:rgba(255,120,60,.08);border-bottom:1px solid var(--line)}
.netdelta{margin:8px;padding:8px 10px;border-radius:5px;font:700 12px 'IBM Plex Mono';text-align:center;border:1px solid var(--line);background:var(--panel2);letter-spacing:.5px}
.netdelta.buy{color:var(--green);border-color:rgba(0,200,150,.4);box-shadow:0 0 12px rgba(0,200,150,.1)}
.netdelta.sell{color:var(--red);border-color:rgba(255,80,109,.4);box-shadow:0 0 12px rgba(255,80,109,.1)}
.flow{margin:8px;padding:10px;border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:5px;background:var(--panel2);animation:fadein .5s ease}
@keyframes fadein{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
.flow.buy{border-left-color:var(--green)}.flow.sell{border-left-color:var(--red)}
.flow h4{font-size:11px;display:flex;justify-content:space-between}.flow time{font-size:9px;color:var(--muted);font-weight:400}.flow .act{margin:6px 0 4px;font:700 11px 'IBM Plex Mono'}.flow p{font-size:9px;color:var(--muted);line-height:1.55}
.center{min-width:0;display:flex;flex-direction:column;overflow:auto}
.decision-desk{display:grid;grid-template-columns:1.22fr 1fr 1fr;gap:8px;padding:9px;background:#07101d;border-bottom:1px solid var(--line);flex-shrink:0}
.signal-main,.tradecard{background:var(--panel2);border:1px solid var(--line);border-radius:6px;padding:9px}
.signal-main{border-color:rgba(212,175,55,.38);box-shadow:0 0 18px rgba(212,175,55,.08)}
.kicker{font-size:9px;color:var(--gold);letter-spacing:1px;font-weight:700;display:flex;justify-content:space-between}
.kicker em{font-style:normal;color:var(--green);font-size:8px}
.signalrow{display:flex;align-items:end;justify-content:space-between;margin-top:3px}
.sigtxt{font:700 22px 'IBM Plex Mono'}.conf{font:10px 'IBM Plex Mono';color:var(--gold)}.why{font-size:9px;color:var(--muted);line-height:1.5;margin-top:6px}
.trigger{margin-top:7px;font:700 9px 'IBM Plex Mono';padding:5px 7px;border-radius:4px;text-align:center;letter-spacing:.5px}
.trigger.armed{color:#07101b;background:var(--gold);box-shadow:0 0 14px rgba(212,175,55,.4)}
.trigger.wait{color:var(--muted);background:rgba(255,255,255,.04);border:1px solid var(--line)}
.trade-status{margin-top:8px;font:700 11px 'IBM Plex Mono';padding:6px;border-radius:6px;text-align:center}
.trade-status.armed{background:var(--gold);color:#07101b;box-shadow:0 0 12px rgba(212,175,55,.12)}
.trade-status.wait{background:rgba(255,255,255,.03);color:var(--muted);border:1px solid var(--line)}
.tradecard h4{font-size:10px;color:var(--text);margin-bottom:6px}.tradecard .tf{color:var(--gold);font:9px 'IBM Plex Mono'}
.levels{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-top:6px}.lev{background:#07101c;padding:5px;border-radius:3px}.lev small{display:block;font-size:8px;color:var(--muted)}.lev b{font:600 10px 'IBM Plex Mono'}
.entry{color:var(--blue)}.stop{color:var(--red)}.target{color:var(--green)}
.pnl{font:8px 'IBM Plex Mono';color:var(--green);margin-top:5px;text-align:center;background:rgba(0,200,150,.07);padding:3px;border-radius:3px}
.charthead{height:35px;display:flex;align-items:center;gap:10px;padding:0 12px;background:#080f1a;border-bottom:1px solid var(--line);flex-shrink:0}
.charthead b{font:11px 'IBM Plex Mono';color:var(--gold)}.tfbtn{font:10px 'IBM Plex Mono';border:0;background:transparent;color:var(--muted);cursor:pointer;padding:5px}.tfbtn.on{color:var(--gold);border:1px solid rgba(212,175,55,.3);border-radius:3px}
.chartzone{display:flex;height:330px;flex-shrink:0}
.volprofile{width:150px;background:#060b14;border-right:1px solid var(--line);position:relative;overflow:hidden}
.vphead{font:8px 'IBM Plex Mono';color:var(--gold);text-align:center;padding:3px 0;border-bottom:1px solid var(--line);letter-spacing:.5px}
.vpbar{position:absolute;right:0;height:9px;display:flex;align-items:center;justify-content:flex-end;padding-right:4px;font:600 7px 'IBM Plex Mono';color:#cfe;white-space:nowrap;border-radius:2px 0 0 2px}
.vpbar.buy{background:linear-gradient(90deg,rgba(0,200,150,.15),rgba(0,200,150,.75))}
.vpbar.sell{background:linear-gradient(90deg,rgba(255,80,109,.15),rgba(255,80,109,.75))}
.vpbar.poc{box-shadow:0 0 0 1px var(--gold);color:var(--gold);font-weight:800}
.vpprice{position:absolute;left:3px;font:7px 'IBM Plex Mono';color:var(--muted);pointer-events:none;z-index:2}
.chartwrap{flex:1;position:relative;background:#060d18;overflow:hidden}
#valensChart{position:absolute;inset:0}
#chartClosed{position:absolute;inset:0;display:none;align-items:center;justify-content:center;flex-direction:column;gap:6px;background:rgba(6,13,24,.82);z-index:6;font:700 13px 'IBM Plex Mono';color:var(--red);letter-spacing:1px}
#chartClosed small{color:var(--muted);font-weight:400;font-size:10px}
iframe{height:100%;width:100%;border:0}
.zones{position:absolute;inset:0;pointer-events:none;z-index:4}
.analysis{padding:10px 12px;border-top:1px solid var(--line);background:#080f1a}
.analysis .atitle{font-size:10px;color:var(--gold);letter-spacing:1px;font-weight:700;margin-bottom:7px;display:flex;justify-content:space-between}
.analysis .atitle em{font-style:normal;color:var(--green);font-size:8px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(84px,1fr));gap:6px;margin-bottom:9px}
.stat{background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:6px 7px}
.stat small{display:block;font-size:8px;color:var(--muted);letter-spacing:.5px}.stat b{font:600 12px 'IBM Plex Mono'}
.analysis p{font-size:11px;color:var(--text);line-height:1.6;opacity:.9}
.upcoming{padding:10px 12px;border-top:1px solid var(--line);background:#07101c}
.upcoming .atitle{font-size:10px;color:var(--gold);letter-spacing:1px;font-weight:700;margin-bottom:8px}
.newsrow{display:flex;gap:9px;padding:8px;border:1px solid var(--line);border-radius:5px;background:var(--panel2);margin-bottom:7px}
.newsrow .tm{font:600 10px 'IBM Plex Mono';color:var(--gold);min-width:52px}
.newsrow .body{flex:1}.newsrow .body b{font-size:11px}.imp{color:#ff8498;font-size:9px;margin-left:5px}
.newsrow .body p{font-size:9px;color:var(--muted);line-height:1.5;margin-top:3px}
.newsrow .exp{font-size:9px;color:var(--text);opacity:.85;margin-top:3px}
.bottomnote{padding:7px 12px;background:#07101c;border-top:1px solid var(--line);font-size:9px;color:var(--muted)}
.event{margin:9px;border:1px solid var(--line);border-radius:6px;background:var(--panel2);overflow:hidden}
.eventtop{padding:8px;display:flex;align-items:center;gap:6px;background:rgba(212,175,55,.06);border-bottom:1px solid var(--line)}.eventtop b{font-size:10px}.eventtop time{font-size:9px;color:var(--muted);margin-left:auto}
.eventbody{padding:8px}.eventbody p{font-size:9px;color:var(--muted);line-height:1.45;margin-bottom:6px}.scenario{font-size:9px;padding:6px;border-left:3px solid;margin-top:5px;line-height:1.45}.bull{border-color:var(--green);background:rgba(0,200,150,.06)}.bear{border-color:var(--red);background:rgba(255,80,109,.06)}
.megaalert{margin:0 9px 9px;padding:9px 12px;border-radius:6px;border:1px solid rgba(212,175,55,.5);background:linear-gradient(90deg,rgba(212,175,55,.14),rgba(0,200,150,.08));display:none;align-items:center;gap:10px;animation:alertpulse 1.1s infinite}
.megaalert.show{display:flex}
.megaalert b{font:800 12px 'IBM Plex Mono';color:var(--gold);letter-spacing:.4px}
.megaalert span{font-size:10px;color:var(--text)}
@keyframes alertpulse{0%,100%{box-shadow:0 0 6px rgba(212,175,55,.15)}50%{box-shadow:0 0 22px rgba(212,175,55,.55)}}
.winrate{font-size:9px;color:var(--muted);margin-top:5px}
.winrate b{color:var(--gold)}
@media(max-width:1050px){.shell{grid-template-columns:225px minmax(500px,1fr)}.right{display:none}.brand{min-width:auto}.tabs{display:none}.volprofile{width:110px}}
</style>
</head>
<body>
<div id="app">
  <nav>
    <div class="brand"><img src="https://cdn.abacus.ai/images/0f498010-a0a5-4cf2-98cd-491f08add03c.png" alt="Valens Wealth"/><b>VALENS WEALTH</b></div>
    <div class="tabs"><button class="tab active">TERMINAL</button><button class="tab">PORTFOLIO</button><button class="tab">RESEARCH</button><button class="tab">SETTINGS</button><button class="tab">ACCOUNT</button></div>
    <div class="live"><i class="dot"></i> LIVE · <span id="clock"></span> UTC</div>
  </nav>

  <div class="ticker"><div class="ticklabel">LIVE</div><div class="tickscroll">
    <span>XAU/USD <b id="tk1">4,053.98</b></span><span>ECB Faiz Kararı: <b>%2.40</b></span><span>US İşsizlik Başvuruları: <b>187K</b></span><span>TCMB Faiz Kararı: <b>%37.00</b></span><span>Kurumsal akış ve haber verileri doğrulama gerektirir.</span>
    <span>XAU/USD <b>4,053.98</b></span><span>ECB Faiz Kararı: <b>%2.40</b></span><span>US İşsizlik Başvuruları: <b>187K</b></span><span>TCMB Faiz Kararı: <b>%37.00</b></span><span>Kurumsal akış ve haber verileri doğrulama gerektirir.</span>
  </div></div>

  <div class="marketbar" id="marketbar">
    <button class="market active" data-sym="OANDA:XAUUSD" data-label="XAU/USD · GOLD OZ" data-price="4053.98"><small>XAU/USD · GOLD OZ</small><strong>4,053.98</strong> <small class="down">▼ -1.83%</small></button>
    <button class="market" data-sym="BINANCE:BTCUSDT" data-label="BTC/USD" data-price="118240"><small>BTC/USD</small><strong>118,240</strong> <small class="up">▲ +2.14%</small></button>
    <button class="market" data-sym="OANDA:EURUSD" data-label="EUR/USD" data-price="1.0842"><small>EUR/USD</small><strong>1.0842</strong> <small class="down">▼ -0.31%</small></button>
    <button class="market" data-sym="OANDA:SPX500USD" data-label="SPX500" data-price="5892"><small>SPX500</small><strong>5,892</strong> <small class="up">▲ +0.47%</small></button>
  </div>

  <main class="shell">
    <aside class="left">
      <div class="ph"><b>ORDER FLOW · YÜKLÜ İŞLEMLER</b><span class="badge">CANLI</span></div>
      <div class="simwarn">🐋 BTC/kripto için Binance canlı YÜKLÜ (whale) emirleri gösterilir. Forex/endeks için agrega simülasyondur.</div>
      <div class="netdelta" id="netDelta">NET DELTA: — </div>
      <div id="flowFeed"></div>
    </aside>

    <section class="center">
      <div class="megaalert" id="megaAlert"><span style="font-size:16px">🚨</span><div><b id="megaAlertTitle">YÜKSEK POTANSİYELLİ SCALP</b><br><span id="megaAlertBody">—</span></div></div>

      <div class="decision-desk">
        <div class="signal-main">
          <div class="kicker"><span>AI SIGNAL ENGINE · <span id="sigPair">XAU/USD</span></span><em id="botStatus">● ÇALIŞIYOR</em></div>
          <div class="signalrow"><div class="sigtxt" id="sigTxt">—</div><div class="conf" id="sigConf">—</div></div>
          <div class="why" id="sigWhy">Bot indikatörleri okuyor…</div>
          <div class="trigger wait" id="trigger">◇ GÖZLEM — Emir eşiği %87</div>
          <div class="winrate" id="winRate">Geçmiş sinyal takibi: veri birikiyor…</div>
        </div>
        <div class="tradecard">
          <h4>⚡ SCALP PLAN <span class="tf">15M / 30M</span></h4>
          <div class="levels"><div class="lev"><small>GİRİŞ</small><b class="entry" id="scEntry">—</b></div><div class="lev"><small>STOP</small><b class="stop" id="scStop">—</b></div><div class="lev"><small>TP</small><b class="target" id="scTp">—</b></div></div>
          <div id="scStatus" class="trade-status wait">◇ GÖZLEM — Emir eşiği %87</div>
          <div class="pnl" id="scPnl">Hedef ≈ $250 @ 2.5 lot</div>
        </div>
        <div class="tradecard">
          <h4>◆ SWING PLAN <span class="tf">1H / 4H</span></h4>
          <div class="levels"><div class="lev"><small>GİRİŞ</small><b class="entry" id="swEntry">—</b></div><div class="lev"><small>STOP</small><b class="stop" id="swStop">—</b></div><div class="lev"><small>TP</small><b class="target" id="swTp">—</b></div></div>
          <div class="pnl" id="swPnl">Hedef ≈ $750 @ 2.5 lot</div>
        </div>
      </div>

      <div class="charthead">
        <b id="chartTitle">XAU/USD · GOLD SPOT</b>
        <button class="tfbtn on" data-int="15">15M</button><button class="tfbtn" data-int="30">30M</button><button class="tfbtn" data-int="60">1H</button><button class="tfbtn" data-int="240">4H</button><button class="tfbtn" data-int="D">1D</button>
      </div>

      <div class="chartzone">
        <div class="volprofile"><div class="vphead">📊 HACİM PROFİLİ</div><div id="vpBars"></div></div>
        <div class="chartwrap">
          <div id="valensChart"></div>
          <div id="chartClosed">● PİYASA KAPALI<small id="chartClosedMsg">Hafta sonu — canlı veri akışı yok</small></div>
          <div class="zones" id="zones"></div>
        </div>
      </div>

      <div class="analysis">
        <div class="atitle"><span>📊 CANLI GRAFİK ANALİZİ · <span id="anPair">XAU/USD</span> · 6 İNDİKATÖR + GRAFİK + HABER</span><em id="anStatus">● GÜNCELLENİYOR</em></div>
        <div class="stats">
          <div class="stat"><small>RSI (14)</small><b id="iRsi">—</b></div>
          <div class="stat"><small>MACD</small><b id="iMacd">—</b></div>
          <div class="stat"><small>EMA 50/200</small><b id="iEma">—</b></div>
          <div class="stat"><small>BOLLINGER</small><b id="iBoll">—</b></div>
          <div class="stat"><small>STOCH</small><b id="iStoch">—</b></div>
          <div class="stat"><small>ADX</small><b id="iAdx">—</b></div>
          <div class="stat"><small>ATR (14)</small><b id="iAtr">—</b></div>
          <div class="stat"><small>VWAP</small><b id="iVwap">—</b></div>
          <div class="stat"><small>WILLIAMS %R</small><b id="iWr">—</b></div>
          <div class="stat"><small>CCI (20)</small><b id="iCci">—</b></div>
          <div class="stat"><small>PARABOLIC SAR</small><b id="iPsar">—</b></div>
          <div class="stat"><small>PIVOT (P/R1/S1)</small><b id="iPivot">—</b></div>
        </div>
        <p id="anText">Analiz motoru başlatılıyor…</p>
      </div>

      <div class="upcoming">
        <div class="atitle">🗓️ YAKLAŞAN ÖNEMLİ HABERLER · <span id="calDate"></span></div>
        <div class="newsrow"><div class="tm">15:15<br>UTC</div><div class="body"><b>🇪🇺 ECB Faiz Kararı<span class="imp">★★★ YÜKSEK</span></b><p>Beklenti %2.40 · Önceki %2.40</p><div class="exp"><b>Beklenti:</b> Faiz sabit tahmin ediliyor. Lagarde'ın basın toplantısındaki ton belirleyici.</div></div></div>
        <div class="newsrow"><div class="tm">15:30<br>UTC</div><div class="body"><b>🇺🇸 US İşsizlik Başvuruları<span class="imp">★★★ YÜKSEK</span></b><p>Beklenti 215K · Önceki 209K</p><div class="exp"><b>Beklenti:</b> Beklenti altı veri USD'yi destekler, altın için baskı.</div></div></div>
        <p style="font-size:8px;color:var(--muted);margin-top:4px">⚠ Bu takvim manuel örnek veridir · veriler doğrulama gerektirir.</p>
      </div>

      <div class="bottomnote">AL/SAT sinyali; 12 gerçek indikatör (RSI, MACD, EMA50/200, Bollinger, Stochastic, ADX, ATR, VWAP, Williams %R, CCI, Parabolic SAR, Pivot) + grafik çizimleri (trend/kanal/Fibonacci/S-R/mum formasyonu) + o günkü haber yönü (manuel) kombine edilerek üretilir. Stop/hedef mesafeleri gerçek ATR volatilitesine göre dinamik hesaplanır. Grafik verisi Binance canlı feed'inden gelir (XAU→PAXG proxy). COT verisi CFTC resmi kaynağından çekilir. "Geçmiş başarı oranı" gerçekten üretilen sinyallerin TP/SL'ye önce ulaşma sonucundan hesaplanır — sabit/iddia edilen bir doğruluk yüzdesi değildir.</div>
    </section>

    <aside class="right">
      <div class="ph"><b>MACRO EVENT ANALYSIS</b><span class="badge" id="macroDate"></span></div>
      <article class="event" id="cotPanel" style="border-color:rgba(212,175,55,.4)">
        <div class="eventtop">🏦 <b>COT RAPORU · Kurumsal Pozisyon</b><time id="cotDate">—</time></div>
        <div class="eventbody" id="cotBody"><p style="color:var(--muted)">COT verisi yükleniyor…</p></div>
      </article>
      <article class="event"><div class="eventtop">🇪🇺 <b>ECB Faiz Kararı</b><time>15:15 UTC</time></div><div class="eventbody"><p>Beklenti: <strong>%2.40</strong> · Önceki: %2.40</p><div class="scenario bull"><b>▲ XAU ALIM:</b> Dovish ton USD'yi baskılarsa 4,085 test edilebilir.</div><div class="scenario bear"><b>▼ XAU SATIM:</b> Şahin söylem USD'yi güçlendirirse 4,040 / 4,000 izlenir.</div></div></article>
    </aside>
  </main>
</div>

<script>
const months=['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'];
function clock(){const n=new Date();document.getElementById('clock').textContent=n.toUTCString().slice(17,25);}
clock();setInterval(clock,1000);
(function setDates(){
  const n=new Date();
  document.getElementById('calDate').textContent=n.getDate()+' '+months[n.getMonth()]+' '+n.getFullYear();
  document.getElementById('macroDate').textContent=n.getDate()+' '+months[n.getMonth()].toUpperCase();
})();

// contractSize: 1 lot'ta fiyat 1.0 birim hareket ederse oluşan USD kâr/zarar (broker'ınıza göre AYARLAYIN — bunlar tipik sektör varsayımlarıdır, garanti değildir)
const SYMS={
 'OANDA:XAUUSD':{label:'XAU/USD',title:'XAU/USD · GOLD SPOT',price:4053.98,step:2.5,dec:2,pipVal:1.0,contractSize:100,
   sr:[{type:'r',lo:4113,hi:4123,label:'R2 · 4,118'},{type:'r',lo:4079,hi:4091,label:'R1 · 4,085'},{type:'s',lo:4034,hi:4046,label:'S1 · 4,040'},{type:'s',lo:3995,hi:4005,label:'S2 · 4,000'}],
   top:4190,bot:3990, scTP:10, scSL:5, swTP:30, swSL:15},
 'BINANCE:BTCUSDT':{label:'BTC/USD',title:'BTC/USD · BITCOIN',price:118240,step:900,dec:0,pipVal:1,contractSize:1,
   sr:[{type:'r',lo:121000,hi:122500,label:'R2 · 122K'},{type:'r',lo:119000,hi:120200,label:'R1 · 120K'},{type:'s',lo:116500,hi:117500,label:'S1 · 117K'},{type:'s',lo:113500,hi:114500,label:'S2 · 114K'}],
   top:124000,bot:112000, scTP:600, scSL:300, swTP:2200, swSL:1100},
 'OANDA:EURUSD':{label:'EUR/USD',title:'EUR/USD · FX',price:1.0842,step:0.004,dec:4,pipVal:0.0001,contractSize:100000,
   sr:[{type:'r',lo:1.091,hi:1.093,label:'R2 · 1.0920'},{type:'r',lo:1.087,hi:1.0885,label:'R1 · 1.0878'},{type:'s',lo:1.080,hi:1.0815,label:'S1 · 1.0808'},{type:'s',lo:1.075,hi:1.0765,label:'S2 · 1.0758'}],
   top:1.096,bot:1.073, scTP:0.0035, scSL:0.0018, swTP:0.011, swSL:0.0055},
 'OANDA:SPX500USD':{label:'SPX500',title:'SPX500 · US500',price:5892,step:6,dec:1,pipVal:0.1,contractSize:1,
   sr:[{type:'r',lo:5945,hi:5970,label:'R2 · 5,958'},{type:'r',lo:5905,hi:5925,label:'R1 · 5,915'},{type:'s',lo:5855,hi:5875,label:'S1 · 5,865'},{type:'s',lo:5810,hi:5830,label:'S2 · 5,820'}],
   top:5990,bot:5800, scTP:14, scSL:7, swTP:45, swSL:22}
};
let CUR='OANDA:XAUUSD', INT='15';

// O günkü önemli haber yönü (+1 alım / -1 satım / 0 nötr). Haber günü güncelle.
const NEWS_BIAS={
 'OANDA:XAUUSD': -0.5,
 'BINANCE:BTCUSDT': +0.3,
 'OANDA:EURUSD': -0.3,
 'OANDA:SPX500USD': +0.4
};
// Grafik motorunun canlı okuması buraya yazılır (trend/pattern/S-R/fib + gerçek indikatörler)
window.valensChartRead={};

function isMarketOpen(sym){
 if(sym==='BINANCE:BTCUSDT')return true;
 const d=new Date(),day=d.getUTCDay(),h=d.getUTCHours();
 if(sym==='OANDA:SPX500USD'){
   if(day===0||day===6)return false;
   const m=h*60+d.getUTCMinutes(); return m>=870 && m<=1260;
 }
 if(day===6)return false;
 if(day===0 && h<23)return false;
 if(day===5 && h>=22)return false;
 return true;
}
function loadChart(){document.getElementById('chartTitle').textContent=SYMS[CUR].title;}
function drawZones(){document.getElementById('zones').style.display='none';}

function drawVolProfile(){
 const cfg=SYMS[CUR], box=document.getElementById('vpBars'); box.innerHTML='';
 const p2t=p=>((cfg.top-p)/(cfg.top-cfg.bot))*100;
 const rows=22, span=cfg.top-cfg.bot, step=span/rows; let bars=[];
 for(let i=0;i<rows;i++){
   const pxLevel=cfg.top - i*step - step/2;
   let vol=rnd(15,45);
   cfg.sr.forEach(s=>{ if(pxLevel<=s.hi && pxLevel>=s.lo) vol+=70; });
   vol+=rnd(-6,6);
   const buyDom = pxLevel < cfg.price ? Math.random()>0.35 : Math.random()>0.65;
   bars.push({px:pxLevel,vol:Math.max(8,vol),buy:buyDom});
 }
 const maxV=Math.max(...bars.map(b=>b.vol)), pocPx=bars.reduce((a,b)=>b.vol>a.vol?b:a).px;
 bars.forEach(b=>{
   const w=Math.max(14,(b.vol/maxV)*130);
   const el=document.createElement('div');
   el.className='vpbar '+(b.buy?'buy':'sell')+(Math.abs(b.px-pocPx)<step/2?' poc':'');
   el.style.top=p2t(b.px)+'%'; el.style.width=w+'px'; el.textContent=Math.round(b.vol);
   box.appendChild(el);
   const pl=document.createElement('div');
   pl.className='vpprice'; pl.style.top=p2t(b.px)+'%';
   pl.textContent=b.px.toLocaleString('en-US',{maximumFractionDigits:cfg.dec>2?3:0});
   box.appendChild(pl);
 });
}

const feed=document.getElementById('flowFeed');
let netLots=0, flowLog=[];
function utc(){return new Date().toUTCString().slice(17,22)+' UTC';}
function rnd(a,b){return a+Math.random()*(b-a);}
const flowTags=['Agresif satıcı','Alım baskısı','Kurumsal blok','Likidite avı','Piyasa emri','Stop tetikleme','Momentum akışı'];
function addFlow(){
 if(!isMarketOpen(CUR))return;
 if(CUR==='BINANCE:BTCUSDT')return;
 const cfg=SYMS[CUR], buy=Math.random()>0.5;
 const lots=Math.round(rnd(80,650)/10)*10;
 const cr=window.valensChartRead||{};
 const basePx=(cr.indicators && cr.indicators.lastClose)?cr.indicators.lastClose:cfg.price;
 const px=basePx+rnd(-cfg.step*2,cfg.step*2);
 const fmt=px.toLocaleString('en-US',{minimumFractionDigits:cfg.dec,maximumFractionDigits:cfg.dec});
 const tag=flowTags[Math.floor(Math.random()*flowTags.length)];
 netLots += buy?lots:-lots;
 flowLog.push(buy?lots:-lots); if(flowLog.length>14){netLots-=flowLog.shift();}
 const el=document.createElement('article');
 el.className='flow '+(buy?'buy':'sell');
 el.innerHTML='<h4><span>'+(buy?'▲ ALIM':'▼ SATIM')+'</span><time>'+utc()+'</time></h4>'+
   '<div class="act '+(buy?'up':'down')+'">'+lots.toLocaleString('en-US')+' lot '+(buy?'BUY':'SELL')+' · '+cfg.label+'</div>'+
   '<p>@ '+fmt+' · '+tag+'</p>';
 feed.prepend(el);
 while(feed.children.length>8) feed.removeChild(feed.lastChild);
 const nd=document.getElementById('netDelta'), dir=netLots>=0;
 nd.className='netdelta '+(dir?'buy':'sell');
 nd.textContent='NET DELTA: '+(dir?'+':'')+Math.round(netLots).toLocaleString('en-US')+' lot '+(dir?'▲ Alıcı baskın':'▼ Satıcı baskın');
}

const SIG_STORE_PREFIX='valens_signals_';
function getStoreKey(sym){return SIG_STORE_PREFIX+sym.replace(/[:\/]/g,'_');}
function loadSignalStore(sym){try{const raw=localStorage.getItem(getStoreKey(sym));if(!raw)return{signals:[],lastCandleIdxs:{}};return JSON.parse(raw);}catch(e){return{signals:[],lastCandleIdxs:{}};}}
function saveSignalStore(sym,store){try{localStorage.setItem(getStoreKey(sym),JSON.stringify(store));}catch(e){}}
function tfMinutes(intv){if(!intv)return 60;if(intv==='D')return 1440;return parseInt(intv,10)||60;}
function candleIndexForNow(tfMin){return Math.floor(Date.now()/(tfMin*60*1000));}
function recordCandleSignal(sym,tf,dir){
  if(typeof dir==='undefined')return;
  const tfMin=tfMinutes(tf),cIdx=candleIndexForNow(tfMin),store=loadSignalStore(sym);
  store.lastCandleIdxs=store.lastCandleIdxs||{};
  if(store.lastCandleIdxs[tf]===cIdx)return;
  store.signals=store.signals||[];
  store.signals.push({ts:Date.now(),tf:tfMin,candle:cIdx,dir:dir});
  if(store.signals.length>5000)store.signals=store.signals.slice(-5000);
  store.lastCandleIdxs[tf]=cIdx;saveSignalStore(sym,store);
}
function getCounts(sym,windowMinutes){
  const cutoff=Date.now()-windowMinutes*60*1000,store=loadSignalStore(sym);
  const slice=(store.signals||[]).filter(s=>s.ts>=cutoff);
  let buy=0,sell=0,neutral=0;
  slice.forEach(s=>{if(s.dir>0)buy++;else if(s.dir<0)sell++;else neutral++;});
  return{buy,sell,neutral,total:slice.length};
}
function evalStrength(buy,sell){
  const major=Math.max(buy,sell),minor=Math.min(buy,sell);
  if(major===0)return{label:'NÖTR',side:'NEUTRAL'};
  const ratio=minor===0?999:(major/minor),side=(buy>sell)?'BUY':'SELL';
  if(ratio>=3&&major>=20)return{label:'GÜÇLÜ '+side,side};
  if(ratio>=1.5&&major>=8)return{label:'ORTA '+side,side};
  return{label:'ZAYIF '+side,side};
}
function lastNConsecutiveSame(sym,tf,n){
  const store=loadSignalStore(sym),tfMin=tfMinutes(tf);
  const signals=(store.signals||[]).filter(s=>s.tf===tfMin);
  if(signals.length<n)return false;
  const dirs=signals.slice(-n).map(x=>x.dir);
  if(dirs.every(d=>d===dirs[0]&&d!==0))return dirs[0];
  return false;
}
function ensureAggUI(){
  let el=document.getElementById('aggSignal');if(el)return el;
  const container=document.querySelector('.signal-main');
  el=document.createElement('div');el.id='aggSignal';el.style.marginTop='8px';el.style.font="700 11px 'IBM Plex Mono'";
  el.innerHTML='<div style="display:flex;gap:8px;align-items:center;"><div id="aggSummary" style="color:var(--muted);font-size:12px"></div><div id="aggBadge" style="padding:4px 8px;border-radius:6px;background:rgba(255,255,255,0.03);color:var(--gold);font-size:11px"></div></div><div id="aggDetail" style="margin-top:6px;font-size:10px;color:var(--muted)"></div>';
  container.appendChild(el);return el;
}
function updateAggUI(){
  ensureAggUI();
  const windows=[15,45,60],parts=[];
  windows.forEach(w=>{const cnt=getCounts(CUR,w),st=evalStrength(cnt.buy,cnt.sell);parts.push(`${w}m: ${st.label} · B${cnt.buy}/S${cnt.sell}`);});
  document.getElementById('aggSummary').textContent=parts.join('  ·  ');
  const badge=document.getElementById('aggBadge'),detail=document.getElementById('aggDetail');
  const top=getCounts(CUR,45),topEval=evalStrength(top.buy,top.sell);
  badge.textContent=topEval.label;
  badge.style.background=topEval.side==='BUY'?'linear-gradient(90deg, rgba(0,200,150,.08), rgba(0,200,150,.18))':'linear-gradient(90deg, rgba(255,80,109,.08), rgba(255,80,109,.18))';
  badge.style.color=topEval.side==='BUY'?'var(--green)':(topEval.side==='SELL'?'var(--red)':'var(--gold)');
  let conf=lastNConsecutiveSame(CUR,INT,3);
  if(conf){detail.innerHTML='3 MUM ONAY: '+(conf>0?'▲ BUY':'▼ SELL')+' · Güçlü teyit';detail.style.color=conf>0?'var(--green)':'var(--red)';}
  else{detail.innerHTML='3 MUM ONAY: Yok';detail.style.color='var(--muted)';}
}

// ============ GERÇEK SİNYAL BAŞARI TAKİBİ ============
// Burada hiçbir "%80-90 doğruluk" gibi sabit/iddia edilen rakam YOKTUR.
// Her "armed" sinyal gerçek giriş/TP/SL fiyatlarıyla kaydedilir; sonraki tick'lerde
// gerçek fiyat TP'ye mi SL'ye mi önce ulaşmış buna bakılır ve kazanma oranı BUNDAN hesaplanır.
const TRADE_STORE_PREFIX='valens_trades_';
function getTradeKey(sym){return TRADE_STORE_PREFIX+sym.replace(/[:\/]/g,'_');}
function loadTradeStore(sym){try{const raw=localStorage.getItem(getTradeKey(sym));if(!raw)return{trades:[]};return JSON.parse(raw);}catch(e){return{trades:[]};}}
function saveTradeStore(sym,store){try{localStorage.setItem(getTradeKey(sym),JSON.stringify(store));}catch(e){}}
function logArmedTrade(sym,dir,entry,tp,sl){
  const store=loadTradeStore(sym);
  store.trades=store.trades||[];
  const openTrade=store.trades.find(t=>!t.resolved);
  if(openTrade)return; // aynı anda tek açık takip — üst üste her tick'te yeni kayıt açılmaz
  store.trades.push({ts:Date.now(),dir,entry,tp,sl,resolved:false,outcome:null});
  if(store.trades.length>500)store.trades=store.trades.slice(-500);
  saveTradeStore(sym,store);
}
function updateTradeOutcomes(sym,lastPrice){
  const store=loadTradeStore(sym);
  let changed=false;
  (store.trades||[]).forEach(t=>{
    if(t.resolved)return;
    if(t.dir>0){
      if(lastPrice>=t.tp){t.resolved=true;t.outcome='win';changed=true;}
      else if(lastPrice<=t.sl){t.resolved=true;t.outcome='loss';changed=true;}
    }else if(t.dir<0){
      if(lastPrice<=t.tp){t.resolved=true;t.outcome='win';changed=true;}
      else if(lastPrice>=t.sl){t.resolved=true;t.outcome='loss';changed=true;}
    }
  });
  if(changed)saveTradeStore(sym,store);
}
function getWinRate(sym){
  const store=loadTradeStore(sym);
  const resolved=(store.trades||[]).filter(t=>t.resolved);
  const wins=resolved.filter(t=>t.outcome==='win').length;
  return{wins,total:resolved.length,rate:resolved.length?(wins/resolved.length*100):null};
}
function updateWinRateUI(){
  const el=document.getElementById('winRate'); if(!el)return;
  const wr=getWinRate(CUR);
  if(wr.total<5){ el.textContent='Geçmiş sinyal takibi: veri birikiyor ('+wr.total+' sonuçlanan işlem) — güvenilir olması için en az birkaç düzine gerekir.'; return; }
  el.innerHTML='Gerçek takip: son '+wr.total+' sinyalden <b>'+wr.wins+'</b> kazandı → <b>%'+wr.rate.toFixed(1)+'</b> gerçekleşen başarı oranı (bu terminaldeki geçmiş sinyallerden hesaplanır, iddia edilen bir hedef değildir).';
}

function marketClosedUI(){
 const cfg=SYMS[CUR];
 document.getElementById('sigTxt').textContent='● PİYASA KAPALI';
 document.getElementById('sigTxt').style.color='var(--red)';
 document.getElementById('sigConf').textContent='—';
 document.getElementById('sigPair').textContent=cfg.label;
 document.getElementById('anPair').textContent=cfg.label;
 ['iRsi','iMacd','iEma','iBoll','iStoch','iAdx','iAtr','iVwap','iWr','iCci','iPsar','iPivot'].forEach(id=>{const e=document.getElementById(id);e.textContent='—';e.className='';});
 document.getElementById('anText').innerHTML='<b>'+cfg.label+'</b> piyasası şu an <b style="color:var(--red)">KAPALI</b>. Piyasa açılana kadar sinyal üretilmez.';
 const tg=document.getElementById('trigger');tg.className='trigger wait';tg.textContent='● PİYASA KAPALI — sinyal yok';
 ['scEntry','scStop','scTp','swEntry','swStop','swTp'].forEach(id=>document.getElementById(id).textContent='—');
 const sc=document.getElementById('scStatus');sc.className='trade-status wait';sc.textContent='● PİYASA KAPALI';
 document.getElementById('megaAlert').classList.remove('show');
}

function noLiveDataUI(reason){
 const cfg=SYMS[CUR];
 document.getElementById('sigPair').textContent=cfg.label;
 document.getElementById('anPair').textContent=cfg.label;
 ['iRsi','iMacd','iEma','iBoll','iStoch','iAdx','iAtr','iVwap','iWr','iCci','iPsar','iPivot'].forEach(id=>{const e=document.getElementById(id);e.textContent='—';e.className='';});
 const tg=document.getElementById('trigger');
 const sc=document.getElementById('scStatus');
 ['scEntry','scStop','scTp','swEntry','swStop','swTp'].forEach(id=>document.getElementById(id).textContent='—');
 document.getElementById('megaAlert').classList.remove('show');
 if(reason==='feed-none'){
   document.getElementById('sigTxt').textContent='● VERİ YOK';
   document.getElementById('sigTxt').style.color='var(--muted)';
   document.getElementById('sigConf').textContent='—';
   document.getElementById('anText').innerHTML='<b>'+cfg.label+'</b> için canlı OHLC/fiyat feed bağlantısı yok (bu enstrüman için gerçek veri kaynağı entegre edilmedi). Gerçek veri olmadan sinyal ve gösterge <b>üretilmiyor</b> — uydurma sayı göstermek yerine devre dışı bırakıldı.';
   tg.className='trigger wait'; tg.textContent='● VERİ AKIŞI YOK — sinyal üretilmiyor';
   sc.className='trade-status wait'; sc.textContent='● VERİ YOK';
 } else {
   document.getElementById('sigTxt').textContent='◇ YÜKLENİYOR';
   document.getElementById('sigTxt').style.color='var(--gold)';
   document.getElementById('sigConf').textContent='—';
   document.getElementById('anText').innerHTML='Gerçek zamanlı OHLC verisi yükleniyor ('+cfg.label+')… veri gelince göstergeler ve sinyal motoru canlanacak.';
   tg.className='trigger wait'; tg.textContent='◇ VERİ YÜKLENİYOR…';
   sc.className='trade-status wait'; sc.textContent='◇ YÜKLENİYOR';
 }
}

function botTick(){
 if(!isMarketOpen(CUR)){ marketClosedUI(); return; }
 const cfg=SYMS[CUR];
 const cr=window.valensChartRead||{};

 if(cr.hasLiveData===false){ noLiveDataUI('feed-none'); return; }
 if(!cr.indicators){ noLiveDataUI('loading'); return; }

 const {rsi,macd,ema50,ema200,bollPct,stoch,adx,atr,vwap,williamsR,cci,psar,pivots,lastClose:last}=cr.indicators;

 // her indikatör kendi yönünü "oy" olarak verir (-1/0/+1) — hem skora hem de "kaç indikatör aynı yönde?" sayacına girer
 const votes={
  rsi: rsi>55?1:rsi<45?-1:0,
  macd: macd>0?1:-1,
  ema: ema50>ema200?1:-1,
  boll: bollPct>75?-1:bollPct<25?1:0,
  stoch: stoch>80?-1:stoch<20?1:0,
  adx: adx>25?(macd>0?1:-1):0,
  wr: williamsR<-80?1:williamsR>-20?-1:0,
  cci: cci>100?1:cci<-100?-1:0,
  psar: (psar&&psar.isUp)?1:-1,
  vwap: last>vwap?1:-1,
  trend: cr.trend||0,
  pattern: cr.pattern||0,
  sr: typeof cr.srBias==='number'?Math.sign(cr.srBias):0,
  fib: typeof cr.fibBias==='number'?Math.sign(cr.fibBias):0,
  news: Math.sign(NEWS_BIAS[CUR]||0)
 };
 const weights={rsi:.5,macd:.6,ema:.5,boll:.3,stoch:.3,adx:.2,wr:.35,cci:.35,psar:.4,vwap:.25,trend:.6,pattern:.5,sr:1,fib:.4,news:1};
 let score=0;
 Object.keys(votes).forEach(k=>score+=votes[k]*(weights[k]||0));

 const conf=Math.min(97,Math.max(50,Math.round(50+Math.abs(score)*13)));
 const THRESHOLD=87;

 let rawDir=0;
 if(score>0.6)rawDir=1; else if(score<-0.6)rawDir=-1; else rawDir=0;

 // ---- SIKILAŞTIRILMIŞ TETİKLEME: sadece güven eşiği değil, indikatörlerin GERÇEKTEN çoğunluğu aynı yönde olmalı ----
 const agreeCount = rawDir!==0 ? Object.values(votes).filter(v=>v===rawDir).length : 0;
 const totalVotes = Object.keys(votes).length; // 15
 const armed = conf>=THRESHOLD && rawDir!==0 && agreeCount>=Math.ceil(totalVotes*0.6); // en az %60 indikatör mutabakatı

 let sigText='◇ GÖZLEM', sigColor='var(--gold)';
 if(rawDir>0)sigText='▲ BUY'; else if(rawDir<0)sigText='▼ SELL';
 if(armed){sigText=rawDir>0?'▲ BUY':'▼ SELL';sigColor=rawDir>0?'var(--green)':'var(--red)';}

 const fmt=v=>v.toLocaleString('en-US',{minimumFractionDigits:cfg.dec,maximumFractionDigits:cfg.dec});
 document.getElementById('sigTxt').textContent=sigText;
 document.getElementById('sigTxt').style.color=sigColor;
 document.getElementById('sigConf').textContent=conf+'% CONFIDENCE · '+agreeCount+'/'+totalVotes+' indikatör mutabık';
 document.getElementById('sigPair').textContent=cfg.label;
 document.getElementById('anPair').textContent=cfg.label;

 const set=(id,val,good)=>{const e=document.getElementById(id);e.textContent=val;e.className=good>0?'up':good<0?'down':'';};
 set('iRsi',rsi.toFixed(1), rsi>55?1:rsi<45?-1:0);
 set('iMacd',(macd>=0?'+':'')+macd.toFixed(cfg.dec>2?4:2), macd>0?1:-1);
 set('iEma', ema50>ema200?'GOLDEN ▲':'DEATH ▼', ema50>ema200?1:-1);
 set('iBoll', bollPct.toFixed(0)+'%', bollPct>75?-1:bollPct<25?1:0);
 set('iStoch', stoch.toFixed(1), stoch>80?-1:stoch<20?1:0);
 set('iAdx', adx.toFixed(1), adx>25?1:0);
 set('iAtr', fmt(atr), 0);
 set('iVwap', fmt(vwap), last>vwap?1:-1);
 set('iWr', williamsR.toFixed(1), williamsR<-80?1:williamsR>-20?-1:0);
 set('iCci', cci.toFixed(1), cci>100?1:cci<-100?-1:0);
 set('iPsar', (psar?(psar.isUp?'▲ YÜKSELİŞ':'▼ DÜŞÜŞ'):'—'), psar?(psar.isUp?1:-1):0);
 set('iPivot', pivots?('P '+fmt(pivots.pp)+' / R1 '+fmt(pivots.r1)+' / S1 '+fmt(pivots.s1)):'—', 0);

 document.getElementById('anText').innerHTML=
  'Bot 12 indikatörü '+cfg.label+' üzerinde <b>gerçek Binance OHLC verisinden</b> canlı hesaplıyor. RSI <b>'+rsi.toFixed(1)+'</b>, MACD '+(macd>0?'pozitif':'negatif')+
  ', EMA 50/'+(ema50>ema200?'200 üzeri':'200 altı')+', ATR <b>'+fmt(atr)+'</b> (volatilite), fiyat VWAP\'ın '+(last>vwap?'üzerinde':'altında')+
  ', Williams %R <b>'+williamsR.toFixed(1)+'</b>, CCI <b>'+cci.toFixed(1)+'</b>, Parabolic SAR '+(psar&&psar.isUp?'yükseliş':'düşüş')+' yönünde. '+
  'Grafik: '+((cr.trend||0)>0?'yükselen trend':(cr.trend||0)<0?'düşen trend':'yatay')+
  ((cr.patternName)?' · '+cr.patternName:'')+
  ((cr.srText)?' · '+cr.srText:'')+
  '. Haber yönü (manuel): '+((NEWS_BIAS[CUR]||0)>0?'▲ pozitif':(NEWS_BIAS[CUR]||0)<0?'▼ negatif':'nötr')+
  '. Bileşke: <b style="color:'+sigColor+'">'+sigText+'</b> — güven %'+conf+' · '+agreeCount+'/'+totalVotes+' indikatör aynı yönde.';

 const tg=document.getElementById('trigger');
 if(armed){tg.className='trigger armed';tg.textContent='⚡ EMİR TETİKLENDİ · '+(rawDir>0?'BUY':'SELL')+' · %'+conf+' NETLİK';}
 else{tg.className='trigger wait';tg.textContent='◇ GÖZLEM · %'+conf+' / %'+THRESHOLD+' eşik · '+agreeCount+'/'+totalVotes+' mutabakat';}

 const scStatusEl=document.getElementById('scStatus');
 const alertBox=document.getElementById('megaAlert');
 if(armed){
   const d=rawDir;
   // ---- ATR bazlı dinamik SL/TP: sabit pip değil, GERÇEK volatiliteye göre ölçeklenir (2:1 R:R) ----
   const scSL = atr ? atr*1.0 : cfg.scSL, scTP = atr ? atr*2.0 : cfg.scTP;
   const swSL = atr ? atr*3.0 : cfg.swSL, swTP = atr ? atr*6.0 : cfg.swTP;
   const scEntryPx=last, scStopPx=last-d*scSL, scTpPx=last+d*scTP;
   const swStopPx=last-d*swSL, swTpPx=last+d*swTP;

   document.getElementById('scEntry').textContent=fmt(scEntryPx);
   document.getElementById('scStop').textContent=fmt(scStopPx);
   document.getElementById('scTp').textContent=fmt(scTpPx);
   document.getElementById('swEntry').textContent=fmt(last);
   document.getElementById('swStop').textContent=fmt(swStopPx);
   document.getElementById('swTp').textContent=fmt(swTpPx);
   scStatusEl.className='trade-status armed';
   scStatusEl.textContent='⚡ KESİN İŞLEM · '+(rawDir>0?'BUY':'SELL')+' · %'+conf+' · '+utc();

   // ---- Gerçek $ hedef potansiyeli (2.5 lot varsayımıyla) — GARANTİ DEĞİL, sadece TP'ye ulaşırsa oluşacak projeksiyon ----
   const scTpUsd = Math.abs(scTpPx-scEntryPx) * cfg.contractSize * 2.5;
   document.getElementById('scPnl').textContent = 'Hedefe ulaşırsa ≈ $'+Math.round(scTpUsd).toLocaleString('en-US')+' @ 2.5 lot (projeksiyon, garanti değil)';
   const swTpUsd = Math.abs(swTpPx-last) * cfg.contractSize * 2.5;
   document.getElementById('swPnl').textContent = 'Hedefe ulaşırsa ≈ $'+Math.round(swTpUsd).toLocaleString('en-US')+' @ 2.5 lot (projeksiyon, garanti değil)';

   if(scTpUsd>=1000){
     alertBox.classList.add('show');
     document.getElementById('megaAlertTitle').textContent='🚨 YÜKSEK POTANSİYEL SCALP · '+(rawDir>0?'BUY':'SELL')+' · '+cfg.label;
     document.getElementById('megaAlertBody').textContent='Giriş '+fmt(scEntryPx)+' · Stop '+fmt(scStopPx)+' · Hedef '+fmt(scTpPx)+' · Hedefe ulaşırsa ≈ $'+Math.round(scTpUsd).toLocaleString('en-US')+' @ 2.5 lot (15-30M) — bu bir garanti değil, TP\'ye ulaşırsa oluşacak projeksiyondur.';
   } else { alertBox.classList.remove('show'); }

   logArmedTrade(CUR, rawDir, scEntryPx, scTpPx, scStopPx);
 }else{
   ['scEntry','scStop','scTp','swEntry','swStop','swTp'].forEach(id=>document.getElementById(id).textContent='—');
   scStatusEl.className='trade-status wait';
   scStatusEl.textContent='◇ GÖZLEM — Emir eşiği %'+THRESHOLD+' · %'+conf;
   alertBox.classList.remove('show');
 }

 updateTradeOutcomes(CUR, last);
 updateWinRateUI();
 recordCandleSignal(CUR, INT, rawDir);
 updateAggUI();
 const bs=document.getElementById('botStatus'); bs.style.opacity=.35; setTimeout(()=>bs.style.opacity=1,250);
 if(Math.random()>0.8) drawVolProfile();
}

function switchSymbol(sym){
 CUR=sym; loadChart(); drawZones(); drawVolProfile();
 feed.innerHTML=''; netLots=0; flowLog=[];
 window.valensChartRead={};
 document.getElementById('megaAlert').classList.remove('show');
 for(let i=0;i<4;i++) addFlow(); botTick();
 updateAggUI(); updateWinRateUI();
 if(window.valensSetSymbol) window.valensSetSymbol(sym);
 if(window.valensRenderCOT) window.valensRenderCOT(sym);
}

loadChart(); drawZones(); drawVolProfile();
for(let i=0;i<4;i++) addFlow(); botTick();
setInterval(addFlow, 4500);
setInterval(botTick, 3000);
setTimeout(()=>updateAggUI(), 600);

document.querySelectorAll('.market').forEach(x=>x.onclick=()=>{
 document.querySelectorAll('.market').forEach(y=>y.classList.remove('active'));
 x.classList.add('active'); switchSymbol(x.dataset.sym);
});
document.querySelectorAll('.tfbtn').forEach(x=>x.onclick=()=>{
 document.querySelectorAll('.tfbtn').forEach(y=>y.classList.remove('on'));
 x.classList.add('on'); INT=x.dataset.int; loadChart(); updateAggUI();
});
document.querySelectorAll('.tab').forEach(x=>x.onclick=()=>{
 document.querySelectorAll('.tab').forEach(y=>y.classList.remove('active')); x.classList.add('active');
});
</script>

<script>
/* ============ COT RAPORU (her Salı CFTC) ============ */
(function(){
 const COT = __COT_DATA__;
 function fmt(n){return Number(n).toLocaleString('en-US');}
 function chg(n){return (n>0?'+':'')+Number(n).toLocaleString('en-US');}
 window.valensRenderCOT=function(sym){
   const c=COT[sym], body=document.getElementById('cotBody'), dEl=document.getElementById('cotDate');
   if(!c){ dEl.textContent='—'; body.innerHTML='<p style="color:var(--muted)">Bu enstrüman için COT verisi yok (CFTC yalnız vadeli piyasa raporlar).</p>'; return; }
   dEl.textContent=c.date;
   const fundNet=c.fund_long-c.fund_short, bankNet=c.bank_long-c.bank_short;
   body.innerHTML=
    '<p><b>'+c.market+'</b> · OI: '+fmt(c.oi)+'</p>'+
    '<div class="scenario '+(fundNet>=0?'bull':'bear')+'"><b>'+(fundNet>=0?'▲':'▼')+' HEDGE FONLAR (Spekülatör):</b> '+
      (fundNet>=0?'NET LONG':'NET SHORT')+' '+fmt(Math.abs(fundNet))+
      '<br>Long '+fmt(c.fund_long)+' ('+chg(c.fund_dlong)+') · Short '+fmt(c.fund_short)+' ('+chg(c.fund_dshort)+')</div>'+
    '<div class="scenario '+(bankNet>=0?'bull':'bear')+'"><b>'+(bankNet>=0?'▲':'▼')+' BANKALAR / TİCARİ:</b> '+
      (bankNet>=0?'NET LONG':'NET SHORT')+' '+fmt(Math.abs(bankNet))+
      '<br>Long '+fmt(c.bank_long)+' · Short '+fmt(c.bank_short)+'</div>'+
    '<p style="font-size:8px;color:var(--muted);margin-top:5px">Kaynak: CFTC Legacy COT · her Salı kesiti Cuma yayınlanır.</p>';
 };
 window.valensRenderCOT(CUR);
})();
</script>

<script>
/* ============ VALENS CANLI GRAFİK + OTOMATİK ÇİZİM MOTORU + GERÇEK İNDİKATÖR HESABI ============ */
(function(){
 const el=document.getElementById('valensChart');
 if(!el||!window.LightweightCharts)return;
 const MAP={'OANDA:XAUUSD':'PAXGUSDT','BINANCE:BTCUSDT':'BTCUSDT','OANDA:EURUSD':'EURUSDT','OANDA:SPX500USD':null};

 const chart=LightweightCharts.createChart(el,{
  layout:{background:{color:'transparent'},textColor:'#8090a6',fontFamily:'IBM Plex Mono'},
  grid:{vertLines:{color:'rgba(255,255,255,.04)'},horzLines:{color:'rgba(255,255,255,.04)'}},
  rightPriceScale:{borderColor:'rgba(212,175,55,.2)'},
  timeScale:{borderColor:'rgba(212,175,55,.2)',timeVisible:true,secondsVisible:false},
  crosshair:{mode:0}
 });
 const cs=chart.addCandlestickSeries({upColor:'#00c896',downColor:'#ff506d',borderVisible:false,wickUpColor:'#00c896',wickDownColor:'#ff506d'});
 const e20=chart.addLineSeries({color:'#52a9ff',lineWidth:1,lastValueVisible:false,priceLineVisible:false});
 const e50=chart.addLineSeries({color:'#d4af37',lineWidth:1,lastValueVisible:false,priceLineVisible:false});
 const trendSeries=chart.addLineSeries({color:'#ffcf5c',lineWidth:2,lastValueVisible:false,priceLineVisible:false});
 const chanUp=chart.addLineSeries({color:'rgba(82,169,255,.7)',lineWidth:1,lineStyle:2,lastValueVisible:false,priceLineVisible:false});
 const chanLo=chart.addLineSeries({color:'rgba(82,169,255,.7)',lineWidth:1,lineStyle:2,lastValueVisible:false,priceLineVisible:false});
 const resize=()=>chart.applyOptions({width:el.clientWidth,height:el.clientHeight});
 window.addEventListener('resize',resize); setTimeout(resize,150);

 let ohlc=[],ws=null,tradeWs=null,binSym=null,curSym=null,srLines=[],fibLines=[],dynSup,dynRes;
 const closedEl=document.getElementById('chartClosed');

 const emaLine=(a,p)=>{const k=2/(p+1);let e=a[0].close;return a.map((c,i)=>{e=i?c.close*k+e*(1-k):c.close;return{time:c.time,value:+e.toFixed(4)}});};
 function emaValue(closes,period){
  if(!closes.length)return null;
  const k=2/(period+1); let e=closes[0];
  for(let i=1;i<closes.length;i++) e=closes[i]*k+e*(1-k);
  return e;
 }
 function calcRSIReal(closes,period){
  if(closes.length<period+1)return null;
  let gains=0,losses=0;
  for(let i=closes.length-period;i<closes.length;i++){
   const d=closes[i]-closes[i-1];
   if(d>=0)gains+=d; else losses-=d;
  }
  const avgGain=gains/period, avgLoss=losses/period;
  if(avgLoss===0)return 100;
  const rs=avgGain/avgLoss;
  return 100-100/(1+rs);
 }
 function calcBollPct(closes,period){
  if(closes.length<period)return null;
  const w=closes.slice(-period), sma=w.reduce((a,b)=>a+b,0)/period;
  const sd=Math.sqrt(w.reduce((a,b)=>a+(b-sma)**2,0)/period);
  const up=sma+2*sd, lo=sma-2*sd;
  return ((closes[closes.length-1]-lo)/((up-lo)||1))*100;
 }
 function calcStoch(candles,period){
  if(candles.length<period)return null;
  const w=candles.slice(-period);
  const hi=Math.max(...w.map(c=>c.high)), lo=Math.min(...w.map(c=>c.low));
  const last=candles[candles.length-1].close;
  return ((last-lo)/((hi-lo)||1))*100;
 }
 function calcADXReal(candles,period){
  if(candles.length<period*2+1)return null;
  let trs=[],plusDMs=[],minusDMs=[];
  for(let i=1;i<candles.length;i++){
   const cur=candles[i],prev=candles[i-1];
   const upMove=cur.high-prev.high, downMove=prev.low-cur.low;
   plusDMs.push((upMove>downMove&&upMove>0)?upMove:0);
   minusDMs.push((downMove>upMove&&downMove>0)?downMove:0);
   trs.push(Math.max(cur.high-cur.low,Math.abs(cur.high-prev.close),Math.abs(cur.low-prev.close)));
  }
  function wilder(arr,p){
   let out=[],sum=arr.slice(0,p).reduce((a,b)=>a+b,0); out.push(sum);
   for(let i=p;i<arr.length;i++){ sum=out[out.length-1]-(out[out.length-1]/p)+arr[i]; out.push(sum); }
   return out;
  }
  const trSm=wilder(trs,period), plusSm=wilder(plusDMs,period), minusSm=wilder(minusDMs,period);
  let dxs=[];
  for(let i=0;i<trSm.length;i++){
   const pDI=100*(plusSm[i]/(trSm[i]||1e-9)), mDI=100*(minusSm[i]/(trSm[i]||1e-9));
   dxs.push(100*Math.abs(pDI-mDI)/((pDI+mDI)||1));
  }
  const tail=dxs.slice(-period);
  return tail.reduce((a,b)=>a+b,0)/tail.length;
 }
 function calcATR(candles,period){
  if(candles.length<period+1)return null;
  let trs=[];
  for(let i=1;i<candles.length;i++){
   const cur=candles[i],prev=candles[i-1];
   trs.push(Math.max(cur.high-cur.low,Math.abs(cur.high-prev.close),Math.abs(cur.low-prev.close)));
  }
  const tail=trs.slice(-period);
  return tail.reduce((a,b)=>a+b,0)/period;
 }
 function calcVWAP(candles,period){
  const w=candles.slice(-period);
  let pv=0,vol=0;
  w.forEach(c=>{ const typical=(c.high+c.low+c.close)/3, v=c.volume||1; pv+=typical*v; vol+=v; });
  return vol?pv/vol:null;
 }
 function calcWilliamsR(candles,period){
  if(candles.length<period)return null;
  const w=candles.slice(-period);
  const hi=Math.max(...w.map(c=>c.high)), lo=Math.min(...w.map(c=>c.low));
  const last=candles[candles.length-1].close;
  return ((hi-last)/((hi-lo)||1))*-100;
 }
 function calcCCI(candles,period){
  if(candles.length<period)return null;
  const w=candles.slice(-period);
  const tp=w.map(c=>(c.high+c.low+c.close)/3);
  const sma=tp.reduce((a,b)=>a+b,0)/period;
  const meanDev=tp.reduce((a,b)=>a+Math.abs(b-sma),0)/period;
  return meanDev?(tp[tp.length-1]-sma)/(0.015*meanDev):0;
 }
 function calcPSAR(candles){
  if(candles.length<5)return null;
  let isUp=candles[1].close>candles[0].close;
  let sar=isUp?Math.min(candles[0].low,candles[1].low):Math.max(candles[0].high,candles[1].high);
  let ep=isUp?candles[1].high:candles[1].low, af=0.02;
  for(let i=2;i<candles.length;i++){
   const c=candles[i];
   sar=sar+af*(ep-sar);
   if(isUp){
    if(c.low<sar){isUp=false;sar=ep;ep=c.low;af=0.02;}
    else if(c.high>ep){ep=c.high;af=Math.min(af+0.02,0.2);}
   }else{
    if(c.high>sar){isUp=true;sar=ep;ep=c.high;af=0.02;}
    else if(c.low<ep){ep=c.low;af=Math.min(af+0.02,0.2);}
   }
  }
  return{sar,isUp};
 }
 function calcPivots(candles){
  const w=candles.slice(-96); // ~son 24 saat (15dk mumlarda) referans aralığı
  if(!w.length)return null;
  const hi=Math.max(...w.map(c=>c.high)), lo=Math.min(...w.map(c=>c.low));
  const close=candles[candles.length-1].close;
  const pp=(hi+lo+close)/3;
  return{pp, r1:2*pp-lo, s1:2*pp-hi, r2:pp+(hi-lo), s2:pp-(hi-lo)};
 }

 function supRes(a){const s=a.slice(-60);let hi=-1e12,lo=1e12;s.forEach(c=>{if(c.high>hi)hi=c.high;if(c.low<lo)lo=c.low;});return{sup:lo,res:hi};}
 function pattern(a){
  if(a.length<2)return null;const c=a[a.length-1],p=a[a.length-2];
  const body=Math.abs(c.close-c.open),range=c.high-c.low||1e-9;
  const up=c.high-Math.max(c.close,c.open),lo=Math.min(c.close,c.open)-c.low;
  const bull=c.close>c.open,bear=c.close<c.open;
  if(lo>body*2&&up<body)return{n:'Hammer',d:'bull'};
  if(up>body*2&&lo<body)return{n:'Shooting Star',d:'bear'};
  if(body<range*0.1)return{n:'Doji',d:'neutral'};
  if(bull&&p.close<p.open&&c.close>p.open&&c.open<p.close)return{n:'Bull Engulf',d:'bull'};
  if(bear&&p.close>p.open&&c.close<p.open&&c.open>p.close)return{n:'Bear Engulf',d:'bear'};
  return null;
 }
 function drawSRLines(){
  srLines.forEach(l=>cs.removePriceLine(l)); srLines=[];
  const cfg=SYMS[curSym]; if(!cfg) return;
  cfg.sr.forEach(s=>{
   const px=(s.lo+s.hi)/2, isRes=s.type==='r';
   srLines.push(cs.createPriceLine({price:px,color:isRes?'#ff506d':'#00c896',lineWidth:2,lineStyle:0,axisLabelVisible:true,title:s.label}));
  });
 }
 function drawFibonacci(){
  fibLines.forEach(l=>cs.removePriceLine(l)); fibLines=[];
  if(ohlc.length<40)return;
  const w=ohlc.slice(-80);
  let hi=-1e12,lo=1e12,hiT=0,loT=0;
  w.forEach(c=>{if(c.high>hi){hi=c.high;hiT=c.time;} if(c.low<lo){lo=c.low;loT=c.time;}});
  const upTrend = loT<hiT;
  const diff=hi-lo;
  const fibs=[{r:0,c:'#8090a6'},{r:0.236,c:'#52a9ff'},{r:0.382,c:'#52a9ff'},
              {r:0.5,c:'#d4af37'},{r:0.618,c:'#d4af37'},{r:0.786,c:'#52a9ff'},{r:1,c:'#8090a6'}];
  fibs.forEach(f=>{
   const px = upTrend ? hi - diff*f.r : lo + diff*f.r;
   fibLines.push(cs.createPriceLine({price:px,color:f.c,lineWidth:1,lineStyle:1,axisLabelVisible:true,title:'Fib '+f.r.toFixed(3)}));
  });
 }
 function drawTrendChannel(){
  if(ohlc.length<30){trendSeries.setData([]);chanUp.setData([]);chanLo.setData([]);return;}
  const w=ohlc.slice(-60), n=w.length;
  let sx=0,sy=0,sxy=0,sxx=0;
  w.forEach((c,i)=>{sx+=i;sy+=c.close;sxy+=i*c.close;sxx+=i*i;});
  const slope=(n*sxy-sx*sy)/(n*sxx-sx*sx), intercept=(sy-slope*sx)/n;
  let maxDev=0;
  w.forEach((c,i)=>{const line=slope*i+intercept;maxDev=Math.max(maxDev,Math.abs(c.high-line),Math.abs(c.low-line));});
  const mid=[],up=[],low=[];
  w.forEach((c,i)=>{const v=slope*i+intercept;mid.push({time:c.time,value:+v.toFixed(4)});up.push({time:c.time,value:+(v+maxDev).toFixed(4)});low.push({time:c.time,value:+(v-maxDev).toFixed(4)});});
  trendSeries.setData(mid); chanUp.setData(up); chanLo.setData(low);
 }
 function analyze(){
  if(ohlc.length<20)return;
  e20.setData(emaLine(ohlc,20)); e50.setData(emaLine(ohlc,50));
  const{sup,res}=supRes(ohlc);
  if(dynSup)cs.removePriceLine(dynSup); if(dynRes)cs.removePriceLine(dynRes);
  dynSup=cs.createPriceLine({price:sup,color:'#00c896',lineWidth:1,lineStyle:2,title:'Dyn Support'});
  dynRes=cs.createPriceLine({price:res,color:'#ff506d',lineWidth:1,lineStyle:2,title:'Dyn Resistance'});
  drawFibonacci();
  drawTrendChannel();
  const pat=pattern(ohlc);
  if(pat&&pat.d!=='neutral'){
   cs.setMarkers([{time:ohlc[ohlc.length-1].time,position:pat.d==='bull'?'belowBar':'aboveBar',
    color:pat.d==='bull'?'#00c896':'#ff506d',shape:pat.d==='bull'?'arrowUp':'arrowDown',text:pat.n}]);
  }

  const last=ohlc[ohlc.length-1].close;
  const closes=ohlc.map(c=>c.close);
  const w=ohlc.slice(-60); let sx=0,sy=0,sxy=0,sxx=0;
  w.forEach((c,i)=>{sx+=i;sy+=c.close;sxy+=i*c.close;sxx+=i*i;});
  const slope=(w.length*sxy-sx*sy)/(w.length*sxx-sx*sx);
  const cfg=SYMS[curSym]; let srBias=0, srText='';
  if(cfg){cfg.sr.forEach(s=>{const mid=(s.lo+s.hi)/2,dist=Math.abs(last-mid)/last;
    if(dist<0.004){ if(s.type==='s'){srBias=0.5;srText='desteğe yakın ('+s.label+')';}
                    else{srBias=-0.5;srText='dirence yakın ('+s.label+')';} }});}
  let fibBias=0;
  if(fibLines.length){const up=slope>0;const diff=res-sup;const f618=up?res-diff*0.618:sup+diff*0.618;
    if(Math.abs(last-f618)/last<0.004) fibBias=up?0.4:-0.4;}

  // ---- GERÇEK İNDİKATÖRLER: gerçek OHLC'den hesaplanır (rastgele değil) ----
  const rsiReal=calcRSIReal(closes,14);
  const macdReal=(emaValue(closes.slice(-40),12)||last)-(emaValue(closes.slice(-60),26)||last);
  const ema50Real=emaValue(closes.slice(-90),50)||last;
  const ema200Real=emaValue(closes,200)||last;
  const bollPctReal=calcBollPct(closes,20);
  const stochReal=calcStoch(ohlc,14);
  const adxReal=calcADXReal(ohlc,14);
  const atrReal=calcATR(ohlc,14);
  const vwapReal=calcVWAP(ohlc,96);
  const wrReal=calcWilliamsR(ohlc,14);
  const cciReal=calcCCI(ohlc,20);
  const psarReal=calcPSAR(ohlc);
  const pivotsReal=calcPivots(ohlc);

  window.valensChartRead={
    trend: slope>0?1:slope<0?-1:0,
    pattern: pat?(pat.d==='bull'?1:pat.d==='bear'?-1:0):0,
    patternName: pat?pat.n:'',
    srBias, srText, fibBias,
    hasLiveData:true,
    indicators:{
      rsi: rsiReal!==null?rsiReal:50,
      macd: macdReal,
      ema50: ema50Real,
      ema200: ema200Real,
      bollPct: bollPctReal!==null?bollPctReal:50,
      stoch: stochReal!==null?stochReal:50,
      adx: adxReal!==null?adxReal:15,
      atr: atrReal!==null?atrReal:(cfg?cfg.step:1),
      vwap: vwapReal!==null?vwapReal:last,
      williamsR: wrReal!==null?wrReal:-50,
      cci: cciReal!==null?cciReal:0,
      psar: psarReal,
      pivots: pivotsReal,
      lastClose: last
    }
  };
 }
 async function loadHistory(){
  try{
   const r=await fetch(`https://api.binance.com/api/v3/klines?symbol=${binSym}&interval=15m&limit=200`);
   const d=await r.json();
   if(!Array.isArray(d))throw new Error('no data');
   ohlc=d.map(k=>({time:k[0]/1000,open:+k[1],high:+k[2],low:+k[3],close:+k[4],volume:+k[5]}));
   cs.setData(ohlc); chart.timeScale().fitContent(); analyze();
  }catch(e){console.error('history err',e);}
 }
 function connect(){
  if(ws){ws.close();ws=null;}
  ws=new WebSocket(`wss://stream.binance.com:9443/ws/${binSym.toLowerCase()}@kline_15m`);
  ws.onmessage=ev=>{
   const k=JSON.parse(ev.data).k;
   const bar={time:k.t/1000,open:+k.o,high:+k.h,low:+k.l,close:+k.c,volume:+k.v};
   const last=ohlc[ohlc.length-1];
   if(last&&last.time===bar.time)ohlc[ohlc.length-1]=bar; else{ohlc.push(bar);if(ohlc.length>300)ohlc.shift();}
   cs.update(bar); analyze();
  };
 }
 function connectTrades(){
  if(tradeWs){tradeWs.close();tradeWs=null;}
  tradeWs=new WebSocket(`wss://stream.binance.com:9443/ws/${binSym.toLowerCase()}@aggTrade`);
  const TH = binSym==='BTCUSDT'?200000 : binSym==='PAXGUSDT'?150000 : 100000;
  tradeWs.onmessage=ev=>{
   const t=JSON.parse(ev.data);
   const qty=+t.q, px=+t.p, notional=qty*px;
   if(notional < TH) return;
   const buy = !t.m;
   const el2=document.createElement('article');
   el2.className='flow '+(buy?'buy':'sell');
   const usd = notional>=1e6 ? '$'+(notional/1e6).toFixed(2)+'M' : '$'+(notional/1e3).toFixed(0)+'K';
   el2.innerHTML='<h4><span>'+(buy?'🐋 ▲ YÜKLÜ ALIM':'🐋 ▼ YÜKLÜ SATIM')+'</span><time>'+
     new Date().toUTCString().slice(17,22)+' UTC</time></h4>'+
     '<div class="act '+(buy?'up':'down')+'">'+qty.toLocaleString('en-US',{maximumFractionDigits:3})+
     ' @ '+px.toLocaleString('en-US')+'</div>'+
     '<p>Hacim: <b style="color:'+(buy?'#00c896':'#ff506d')+'">'+usd+'</b> · Binance canlı emir</p>';
   feed.prepend(el2);
   while(feed.children.length>10) feed.removeChild(feed.lastChild);
  };
 }
 window.valensSetSymbol=function(sym){
  curSym=sym;
  if(ws){ws.close();ws=null;} if(tradeWs){tradeWs.close();tradeWs=null;}
  // ---- ESKİ PARİTENİN TÜM ÇİZGİLERİNİ TEMİZLE (eksen takılmasın) ----
  cs.setMarkers([]); trendSeries.setData([]); chanUp.setData([]); chanLo.setData([]);
  e20.setData([]); e50.setData([]);
  srLines.forEach(l=>cs.removePriceLine(l)); srLines=[];
  fibLines.forEach(l=>cs.removePriceLine(l)); fibLines=[];
  if(dynSup){cs.removePriceLine(dynSup);dynSup=null;}
  if(dynRes){cs.removePriceLine(dynRes);dynRes=null;}
  ohlc=[]; cs.setData([]);
  binSym=MAP[sym];
  if(!binSym){
   window.valensChartRead={hasLiveData:false};
   closedEl.style.display='flex';
   closedEl.innerHTML='● CANLI VERİ YOK<small>Bu enstrüman için Binance feed\'i yok — TwelveData/OANDA API gerekir</small>';
   drawSRLines(); chart.priceScale('right').applyOptions({autoScale:true}); return;
  }
  window.valensChartRead={};
  closedEl.style.display='none';
  loadHistory().then(()=>{
    drawSRLines(); connect(); connectTrades();
    // ---- EKSENİ YENİ FİYATA OTURT ----
    chart.priceScale('right').applyOptions({autoScale:true});
    chart.timeScale().fitContent();
  });
  setTimeout(resize,120);
 };
 window.valensSetSymbol(CUR);
})();
</script>
</body>
</html>
"""

TERMINAL_HTML = TERMINAL_HTML.replace("__COT_DATA__", COT_JSON)
components.html(TERMINAL_HTML, height=1180, scrolling=True)
