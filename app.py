import streamlit as st
import streamlit.components.v1 as components

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

TERMINAL_HTML = r"""
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Valens Wealth</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet"/>
<style>
:root{
 --navy:#050b14;--panel:#091525;--panel2:#0d1b2e;--gold:#d4af37;
 --text:#e7e1d2;--muted:#8090a6;--line:rgba(255,255,255,.075);
 --green:#00c896;--red:#ff506d;--blue:#52a9ff;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:var(--navy);color:var(--text);font-family:Inter,sans-serif;overflow:hidden}
#app{height:100vh;display:flex;flex-direction:column;background:var(--navy)}
nav{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 18px;background:linear-gradient(180deg,#0b1729,#060c16);border-bottom:1px solid rgba(212,175,55,.28)}
.brand{display:flex;align-items:center;gap:10px;min-width:270px}
.brand img{height:30px;max-width:40px;object-fit:contain;filter:drop-shadow(0 0 7px rgba(212,175,55,.5))}
.brand b{font:700 18px 'Playfair Display';letter-spacing:1.5px;color:var(--gold)}
.tabs{display:flex;gap:3px}.tab{border:0;background:transparent;color:var(--muted);padding:7px 13px;font-size:11px;letter-spacing:.8px;cursor:pointer}
.tab:hover,.tab.active{color:var(--gold);background:rgba(212,175,55,.09);border-radius:4px}
.live{display:flex;align-items:center;gap:7px;color:var(--muted);font:11px 'IBM Plex Mono'}
.dot{width:7px;height:7px;background:var(--green);border-radius:50%;box-shadow:0 0 9px var(--green)}
.ticker{height:26px;display:flex;overflow:hidden;border-bottom:1px solid var(--line);background:#060d18}
.ticklabel{display:flex;align-items:center;background:var(--gold);color:#07101b;padding:0 10px;font-size:10px;font-weight:800;letter-spacing:1px}
.tickscroll{white-space:nowrap;display:flex;align-items:center;animation:scroll 60s linear infinite}
.tickscroll span{font-size:10px;color:var(--muted);padding:0 26px}.tickscroll b{color:var(--gold)}
@keyframes scroll{to{transform:translateX(-50%)}}
.marketbar{height:48px;display:flex;overflow:auto;background:#07101c;border-bottom:1px solid var(--line)}
.market{min-width:172px;padding:6px 15px;border:0;border-right:1px solid var(--line);background:transparent;color:var(--text);text-align:left;cursor:pointer}
.market.active{background:rgba(212,175,55,.08);border-bottom:2px solid var(--gold)}
.market small{display:block;color:var(--muted);font-size:9px;letter-spacing:.8px}.market strong{font:600 13px 'IBM Plex Mono'}.down{color:var(--red)}.up{color:var(--green)}
.shell{min-height:0;flex:1;display:grid;grid-template-columns:245px minmax(520px,1fr) 285px;overflow:hidden}
aside{background:var(--panel);min-height:0;overflow:auto}.left{border-right:1px solid var(--line)}.right{border-left:1px solid var(--line)}
.ph{height:36px;display:flex;align-items:center;justify-content:space-between;padding:0 12px;border-bottom:1px solid var(--line)}
.ph b{font-size:10px;color:var(--gold);letter-spacing:1.2px}.badge{font:9px 'IBM Plex Mono';color:var(--gold);border:1px solid rgba(212,175,55,.3);padding:2px 6px;border-radius:9px}
.flow{margin:8px;padding:10px;border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:5px;background:var(--panel2)}
.flow.buy{border-left-color:var(--green)}.flow.sell{border-left-color:var(--red)}
.flow h4{font-size:11px;display:flex;justify-content:space-between}.flow time{font-size:9px;color:var(--muted);font-weight:400}.flow .act{margin:6px 0 4px;font:700 11px 'IBM Plex Mono'}.flow p{font-size:9px;color:var(--muted);line-height:1.55}
.center{min-width:0;display:flex;flex-direction:column;overflow:auto}
.decision-desk{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:8px;padding:9px;background:#07101d;border-bottom:1px solid var(--line);flex-shrink:0}
.signal-main,.tradecard{background:var(--panel2);border:1px solid var(--line);border-radius:6px;padding:9px}
.signal-main{border-color:rgba(212,175,55,.4);box-shadow:0 0 18px rgba(212,175,55,.08)}
.kicker{font-size:9px;color:var(--gold);letter-spacing:1px;font-weight:700}.signalrow{display:flex;align-items:end;justify-content:space-between;margin-top:3px}
.selltxt{font:700 24px 'IBM Plex Mono';color:var(--red)}.conf{font:10px 'IBM Plex Mono';color:var(--gold)}.why{font-size:9px;color:var(--muted);line-height:1.5;margin-top:6px}
.tradecard h4{font-size:10px;color:var(--text);margin-bottom:6px}.tradecard .tf{color:var(--gold);font:9px 'IBM Plex Mono'}
.levels{display:grid;grid-template-columns:repeat(3,1fr);gap:4px}.lev{background:#07101c;padding:5px;border-radius:3px}.lev small{display:block;font-size:8px;color:var(--muted)}.lev b{font:600 10px 'IBM Plex Mono'}.entry{color:var(--blue)}.stop{color:var(--red)}.target{color:var(--green)}
.charthead{height:33px;display:flex;align-items:center;gap:10px;padding:0 12px;background:#080f1a;border-bottom:1px solid var(--line);flex-shrink:0}
.charthead b{font:11px 'IBM Plex Mono';color:var(--gold)}.tfbtn{font:10px 'IBM Plex Mono';border:0;background:transparent;color:var(--muted);cursor:pointer;padding:5px}.tfbtn.on{color:var(--gold);border:1px solid rgba(212,175,55,.3);border-radius:3px}
.chartwrap{height:340px;position:relative;background:#060d18;overflow:hidden;flex-shrink:0}
iframe{height:100%;width:100%;border:0}
.zones{position:absolute;inset:0;pointer-events:none;z-index:4}
.zone{position:absolute;left:8px;border:1px solid;border-radius:2px;opacity:.92;display:flex;align-items:center;padding-left:7px;font:600 9px 'IBM Plex Mono'}
.zone.r{background:linear-gradient(90deg,rgba(255,80,109,.30),rgba(255,80,109,.04));border-color:rgba(255,80,109,.8);color:#ff8498}
.zone.s{background:linear-gradient(90deg,rgba(0,200,150,.30),rgba(0,200,150,.04));border-color:rgba(0,200,150,.8);color:#66e6c2}
.zone em{font-style:normal;opacity:.8;margin-left:5px;font-size:8px}
.analysis{padding:10px 12px;border-top:1px solid var(--line);background:#080f1a}
.analysis .atitle{font-size:10px;color:var(--gold);letter-spacing:1px;font-weight:700;margin-bottom:7px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:9px}
.stat{background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:6px 8px}
.stat small{display:block;font-size:8px;color:var(--muted);letter-spacing:.6px}.stat b{font:600 12px 'IBM Plex Mono'}
.analysis p{font-size:11px;color:var(--text);line-height:1.6;opacity:.9}
.upcoming{padding:10px 12px;border-top:1px solid var(--line);background:#07101c}
.upcoming .atitle{font-size:10px;color:var(--gold);letter-spacing:1px;font-weight:700;margin-bottom:8px}
.newsrow{display:flex;gap:9px;padding:8px;border:1px solid var(--line);border-radius:5px;background:var(--panel2);margin-bottom:7px}
.newsrow .tm{font:600 10px 'IBM Plex Mono';color:var(--gold);min-width:52px}
.newsrow .body{flex:1}.newsrow .body b{font-size:11px}.imp{color:#ff8498;font-size:9px;margin-left:5px}
.newsrow .body p{font-size:9px;color:var(--muted);line-height:1.5;margin-top:3px}
.newsrow .exp{font-size:9px;color:var(--text);opacity:.85;margin-top:3px}
.event{margin:9px;border:1px solid var(--line);border-radius:6px;background:var(--panel2);overflow:hidden}
.eventtop{padding:8px;display:flex;align-items:center;gap:6px;background:rgba(212,175,55,.06);border-bottom:1px solid var(--line)}.eventtop b{font-size:10px}.eventtop time{font-size:9px;color:var(--muted);margin-left:auto}
.eventbody{padding:8px}.eventbody p{font-size:9px;color:var(--muted);line-height:1.45;margin-bottom:6px}.scenario{font-size:9px;padding:6px;border-left:3px solid;margin-top:5px;line-height:1.45}.bull{border-color:var(--green);background:rgba(0,200,150,.06)}.bear{border-color:var(--red);background:rgba(255,80,109,.06)}
@media(max-width:1050px){.shell{grid-template-columns:220px minmax(480px,1fr)}.right{display:none}.brand{min-width:auto}.tabs{display:none}}
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
    <span>XAU/USD <b>4,053.98</b> ▼ -1.83%</span><span>ECB Faiz: <b>%2.40</b></span><span>US İşsizlik Başvuruları: <b>187K</b></span><span>TCMB Faiz: <b>%37.00</b></span><span>Veriler doğrulama gerektirir.</span>
    <span>XAU/USD <b>4,053.98</b> ▼ -1.83%</span><span>ECB Faiz: <b>%2.40</b></span><span>US İşsizlik Başvuruları: <b>187K</b></span><span>TCMB Faiz: <b>%37.00</b></span><span>Veriler doğrulama gerektirir.</span>
  </div></div>

  <div class="marketbar">
    <button class="market active"><small>XAU/USD · GOLD OZ</small><strong>4,053.98</strong> <small class="down">▼ -1.83%</small></button>
    <button class="market"><small>BTC/USD</small><strong>118,240</strong> <small class="up">▲ +2.14%</small></button>
    <button class="market"><small>EUR/USD</small><strong>1.0842</strong> <small class="down">▼ -0.31%</small></button>
    <button class="market"><small>SPX500</small><strong>5,892</strong> <small class="up">▲ +0.47%</small></button>
  </div>

  <main class="shell">
    <aside class="left">
      <div class="ph"><b>SMART MONEY FLOW</b><span class="badge">LIVE</span></div>
      <article class="flow buy"><h4>Citadel LLC <time>14:32 UTC</time></h4><div class="act up">▲ LONG — XAU/USD</div><p>4,200 lot · Giriş: 4,048 · Hedef: 4,120</p></article>
      <article class="flow sell"><h4>Goldman Sachs <time>12:44 UTC</time></h4><div class="act down">▼ HEDGE — XAU/USD</div><p>2,100 lot · Giriş: 4,065 · Hedef: 4,000</p></article>
      <article class="flow buy"><h4>BlackRock <time>13:15 UTC</time></h4><div class="act up">▲ LONG — BTC/USD</div><p>850 lot · Giriş: 116,400 · Hedef: 122,000</p></article>
    </aside>

    <section class="center">
      <!-- AI SİNYAL MASASI EN ÜSTTE -->
      <div class="decision-desk">
        <div class="signal-main">
          <div class="kicker">AI SIGNAL ENGINE · XAU/USD</div>
          <div class="signalrow"><div class="selltxt">▼ SELL</div><div class="conf">74% CONFIDENCE</div></div>
          <div class="why">1H momentum negatif. 4,085 altında kaldıkça ana senaryo 4,040 ve 4,000 desteklerine çekilme.</div>
        </div>
        <div class="tradecard">
          <h4>⚡ SCALP <span class="tf">15M / 30M</span></h4>
          <div class="levels"><div class="lev"><small>GİRİŞ</small><b class="entry">4,058–65</b></div><div class="lev"><small>STOP</small><b class="stop">4,078</b></div><div class="lev"><small>TP</small><b class="target">4,042</b></div></div>
        </div>
        <div class="tradecard">
          <h4>◆ SWING <span class="tf">1H / 4H</span></h4>
          <div class="levels"><div class="lev"><small>GİRİŞ</small><b class="entry">4,050</b></div><div class="lev"><small>STOP</small><b class="stop">4,090</b></div><div class="lev"><small>TP</small><b class="target">4,000</b></div></div>
        </div>
      </div>

      <div class="charthead">
        <b>XAU/USD · GOLD SPOT</b>
        <button class="tfbtn">15M</button><button class="tfbtn">30M</button><button class="tfbtn on">1H</button><button class="tfbtn">4H</button><button class="tfbtn">1D</button>
      </div>

      <div class="chartwrap">
        <iframe src="https://www.tradingview.com/widgetembed/?symbol=OANDA%3AXAUUSD&interval=60&hidesidetoolbar=0&hidetoptoolbar=0&symboledit=1&toolbarbg=060d18&studies=RSI%4014%7CMACD%4012%2C26%2C9&theme=dark&style=1&timezone=Europe%2FIstanbul&withdateranges=1&locale=en" allowfullscreen></iframe>
        <div class="zones">
          <div class="zone r" style="top:16%;width:44%;height:22px">R2 · 4,118 <em>SUPPLY</em></div>
          <div class="zone r" style="top:34%;width:86%;height:26px">R1 · 4,085 <em>MAJOR LIQUIDITY</em></div>
          <div class="zone s" style="top:62%;width:90%;height:26px">S1 · 4,040 <em>DEMAND ZONE</em></div>
          <div class="zone s" style="top:80%;width:60%;height:22px">S2 · 4,000 <em>PSYCHOLOGICAL</em></div>
        </div>
      </div>

      <!-- CANLI GRAFİK ANALİZİ -->
      <div class="analysis">
        <div class="atitle">📊 CANLI GRAFİK ANALİZİ · XAU/USD 1H</div>
        <div class="stats">
          <div class="stat"><small>TREND</small><b class="down">DÜŞÜŞ ▼</b></div>
          <div class="stat"><small>RSI (14)</small><b class="down">38.4</b></div>
          <div class="stat"><small>MACD</small><b class="down">NEGATİF</b></div>
          <div class="stat"><small>EMA 50/200</small><b class="down">ÖLÜM KESİŞİMİ</b></div>
        </div>
        <p>Fiyat 4,085 arz bölgesinden reddedildi ve 1 saatlik grafikte alt EMA'ların altında işlem görüyor. RSI 40 eşiğinin altında; satıcılar kontrolde ancak aşırı satım değil. MACD histogramı negatif genişliyor — momentum satış yönlü. <b>4,040 kritik destek:</b> altında günlük kapanış gelirse 4,000 psikolojik seviyesi hedeflenir. Tepki alımları için 4,040 üzerinde tutunma ve 15M mum teyidi beklenmeli.</p>
      </div>

      <!-- YAKLAŞAN ÖNEMLİ HABERLER -->
      <div class="upcoming">
        <div class="atitle">🗓️ YAKLAŞAN ÖNEMLİ HABERLER · NELER BEKLENMELİ</div>
        <div class="newsrow"><div class="tm">15:15<br>UTC</div><div class="body"><b>🇪🇺 ECB Faiz Kararı<span class="imp">★★★ YÜKSEK</span></b><p>Beklenti %2.40 · Önceki %2.40</p><div class="exp"><b>Beklenti:</b> Faiz sabit tahmin ediliyor. Lagarde'ın basın toplantısındaki ton belirleyici — güvercin sinyal EUR'yu güçlendirip USD baskısıyla altını yukarı taşıyabilir, şahin ton tersi.</div></div></div>
        <div class="newsrow"><div class="tm">15:30<br>UTC</div><div class="body"><b>🇺🇸 US İşsizlik Başvuruları<span class="imp">★★★ YÜKSEK</span></b><p>Beklenti 215K · Önceki 209K</p><div class="exp"><b>Beklenti:</b> Beklenti altı (güçlü istihdam) veri USD'yi destekler, altın için baskı; beklenti üstü zayıf veri altını destekler.</div></div></div>
        <div class="newsrow"><div class="tm">15:45<br>UTC</div><div class="body"><b>🇪🇺 ECB Basın Açıklaması<span class="imp">★★★ YÜKSEK</span></b><p>Lagarde konuşması</p><div class="exp"><b>Beklenti:</b> "Yakında faiz indirimi" ifadesi altını hızla yukarı çekebilir; enflasyon vurgusu ise satış tetikler. Volatilite yüksek olacak.</div></div></div>
        <div class="newsrow"><div class="tm">20:00<br>UTC</div><div class="body"><b>🇺🇸 10Y TIPS İhalesi<span class="imp">★★ ORTA</span></b><p>Önceki %2.169</p><div class="exp"><b>Beklenti:</b> Yüksek reel getiri altın için negatif; zayıf talep altını destekler.</div></div></div>
        <p style="font-size:8px;color:var(--muted);margin-top:4px">Kaynak mantığı: Investing.com ekonomik takvimi · veriler doğrulama gerektirir.</p>
      </div>
    </section>

    <aside class="right">
      <div class="ph"><b>MACRO EVENT ANALYSIS</b><span class="badge">23 TEMMUZ</span></div>
      <article class="event"><div class="eventtop">🇪🇺 <b>ECB Faiz Kararı</b><time>15:15 UTC</time></div><div class="eventbody"><p>Açıklanan: <strong>%2.40</strong> · Önceki: %2.40</p><div class="scenario bull"><b>▲ XAU ALIM:</b> Dovish ton + EUR güçlenmesi USD'yi baskılarsa 4,085 test edilir.</div><div class="scenario bear"><b>▼ XAU SATIM:</b> Şahin söylem USD'yi güçlendirirse 4,040 / 4,000 izlenir.</div></div></article>
      <article class="event"><div class="eventtop">🇺🇸 <b>İşsizlik Başvuruları</b><time>15:30 UTC</time></div><div class="eventbody"><p>Açıklanan: <strong>187K</strong> · Beklenti: 215K</p><div class="scenario bear"><b>▼ USD GÜÇLÜ:</b> Beklenti altı veri faiz indirimini geciktirebilir; altına baskı.</div></div></article>
      <article class="event"><div class="eventtop">🇹🇷 <b>TCMB Faiz Kararı</b><time>14:00 UTC</time></div><div class="eventbody"><p>Açıklanan: <strong>%37.00</strong></p><div class="scenario bull"><b>▲ XAU/TRY:</b> TL zayıflaması yerel altın talebini destekleyebilir.</div></div></article>
    </aside>
  </main>
</div>
<script>
function clock(){const n=new Date();document.getElementById('clock').textContent=n.toUTCString().slice(17,25);}
clock();setInterval(clock,1000);
document.querySelectorAll('.market').forEach(x=>x.onclick=()=>{document.querySelectorAll('.market').forEach(y=>y.classList.remove('active'));x.classList.add('active')});
document.querySelectorAll('.tfbtn').forEach(x=>x.onclick=()=>{document.querySelectorAll('.tfbtn').forEach(y=>y.classList.remove('on'));x.classList.add('on')});
</script>
</body>
</html>
"""

components.html(TERMINAL_HTML, height=1180, scrolling=True)
