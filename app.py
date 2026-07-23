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
.tradecard h4{font-size:10px;color:var(--text);margin-bottom:6px}.tradecard .tf{color:var(--gold);font:9px 'IBM Plex Mono'}
.levels{display:grid;grid-template-columns:repeat(3,1fr);gap:4px}.lev{background:#07101c;padding:5px;border-radius:3px}.lev small{display:block;font-size:8px;color:var(--muted)}.lev b{font:600 10px 'IBM Plex Mono'}.entry{color:var(--blue)}.stop{color:var(--red)}.target{color:var(--green)}
.charthead{height:35px;display:flex;align-items:center;gap:10px;padding:0 12px;background:#080f1a;border-bottom:1px solid var(--line);flex-shrink:0}
.charthead b{font:11px 'IBM Plex Mono';color:var(--gold)}.tfbtn{font:10px 'IBM Plex Mono';border:0;background:transparent;color:var(--muted);cursor:pointer;padding:5px}.tfbtn.on{color:var(--gold);border:1px solid rgba(212,175,55,.3);border-radius:3px}
.chartwrap{height:330px;position:relative;background:#060d18;overflow:hidden;flex-shrink:0}
iframe{height:100%;width:100%;border:0}
.zones{position:absolute;inset:0;pointer-events:none;z-index:4}
.zone{position:absolute;left:8px;right:auto;border-radius:2px;display:flex;align-items:center;padding-left:7px;font:600 9px 'IBM Plex Mono';border-style:solid}
.zone.r{background:linear-gradient(90deg,rgba(255,80,109,.32),rgba(255,80,109,.03));border-color:rgba(255,80,109,.85);color:#ff8498}
.zone.s{background:linear-gradient(90deg,rgba(0,200,150,.32),rgba(0,200,150,.03));border-color:rgba(0,200,150,.85);color:#66e6c2}
.zone em{font-style:normal;opacity:.8;margin-left:5px;font-size:8px}
.analysis{padding:10px 12px;border-top:1px solid var(--line);background:#080f1a}
.analysis .atitle{font-size:10px;color:var(--gold);letter-spacing:1px;font-weight:700;margin-bottom:7px;display:flex;justify-content:space-between}
.analysis .atitle em{font-style:normal;color:var(--green);font-size:8px}
.stats{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin-bottom:9px}
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
@media(max-width:1050px){.shell{grid-template-columns:225px minmax(500px,1fr)}.right{display:none}.brand{min-width:auto}.tabs{display:none}.stats{grid-template-columns:repeat(3,1fr)}}
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
    <span>XAU/USD <b>4,053.98</b> ▼ -1.83%</span><span>ECB Faiz Kararı: <b>%2.40</b></span><span>US İşsizlik Başvuruları: <b>187K</b></span><span>TCMB Faiz Kararı: <b>%37.00</b></span><span>Kurumsal akış ve haber verileri doğrulama gerektirir.</span>
    <span>XAU/USD <b>4,053.98</b> ▼ -1.83%</span><span>ECB Faiz Kararı: <b>%2.40</b></span><span>US İşsizlik Başvuruları: <b>187K</b></span><span>TCMB Faiz Kararı: <b>%37.00</b></span><span>Kurumsal akış ve haber verileri doğrulama gerektirir.</span>
  </div></div>

  <div class="marketbar">
    <button class="market active"><small>XAU/USD · GOLD OZ</small><strong id="mkPrice">4,053.98</strong> <small class="down" id="mkChg">▼ -1.83%</small></button>
    <button class="market"><small>BTC/USD</small><strong>118,240</strong> <small class="up">▲ +2.14%</small></button>
    <button class="market"><small>EUR/USD</small><strong>1.0842</strong> <small class="down">▼ -0.31%</small></button>
    <button class="market"><small>SPX500</small><strong>5,892</strong> <small class="up">▲ +0.47%</small></button>
  </div>

  <main class="shell">
    <aside class="left">
      <div class="ph"><b>SMART MONEY FLOW</b><span class="badge">● CANLI</span></div>
      <div id="flowFeed"></div>
    </aside>

    <section class="center">
      <!-- AI SİNYAL MASASI -->
      <div class="decision-desk">
        <div class="signal-main">
          <div class="kicker"><span>AI SIGNAL ENGINE · XAU/USD</span><em id="botStatus">● ÇALIŞIYOR</em></div>
          <div class="signalrow"><div class="sigtxt" id="sigTxt">—</div><div class="conf" id="sigConf">—</div></div>
          <div class="why" id="sigWhy">Bot indikatörleri okuyor…</div>
        </div>
        <div class="tradecard">
          <h4>⚡ SCALP PLAN <span class="tf">15M / 30M</span></h4>
          <div class="levels"><div class="lev"><small>GİRİŞ</small><b class="entry" id="scEntry">—</b></div><div class="lev"><small>STOP</small><b class="stop" id="scStop">—</b></div><div class="lev"><small>TP</small><b class="target" id="scTp">—</b></div></div>
          <div class="why">Anlık momentum bazlı gir-çık. 15m mum kapanışıyla teyit.</div>
        </div>
        <div class="tradecard">
          <h4>◆ SWING PLAN <span class="tf">1H / 4H</span></h4>
          <div class="levels"><div class="lev"><small>GİRİŞ</small><b class="entry" id="swEntry">—</b></div><div class="lev"><small>STOP</small><b class="stop" id="swStop">—</b></div><div class="lev"><small>TP</small><b class="target" id="swTp">—</b></div></div>
          <div class="why">Ana S/R bölgeleri arasında risk/ödül planı.</div>
        </div>
      </div>

      <div class="charthead">
        <b>XAU/USD · GOLD SPOT</b>
        <button class="tfbtn">15M</button><button class="tfbtn">30M</button><button class="tfbtn on">1H</button><button class="tfbtn">4H</button><button class="tfbtn">1D</button>
      </div>

      <div class="chartwrap">
        <iframe src="https://www.tradingview.com/widgetembed/?symbol=OANDA%3AXAUUSD&interval=60&hidesidetoolbar=0&hidetoptoolbar=0&symboledit=1&saveimage=1&toolbarbg=060d18&studies=RSI%4014%7CMACD%4012%2C26%2C9&theme=dark&style=1&timezone=Europe%2FIstanbul&withdateranges=1&locale=en" allowfullscreen></iframe>
        <!-- SABİT FİYAT ARALIKLI, HACME GÖRE KALINLIK: JS ile doldurulur -->
        <div class="zones" id="zones"></div>
      </div>

      <!-- CANLI GRAFİK ANALİZİ · 6 İNDİKATÖR -->
      <div class="analysis">
        <div class="atitle"><span>📊 CANLI GRAFİK ANALİZİ · XAU/USD 1H · 6 İNDİKATÖR</span><em id="anStatus">● GÜNCELLENİYOR</em></div>
        <div class="stats">
          <div class="stat"><small>RSI (14)</small><b id="iRsi">—</b></div>
          <div class="stat"><small>MACD</small><b id="iMacd">—</b></div>
          <div class="stat"><small>EMA 50/200</small><b id="iEma">—</b></div>
          <div class="stat"><small>BOLLINGER</small><b id="iBoll">—</b></div>
          <div class="stat"><small>STOCH</small><b id="iStoch">—</b></div>
          <div class="stat"><small>ADX</small><b id="iAdx">—</b></div>
        </div>
        <p id="anText">Analiz motoru başlatılıyor…</p>
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

      <div class="bottomnote">İndikatör değerleri ve akış simülasyondur; gerçek zamanlı emir defteri veya doğrulanmış kurumsal veri değildir.</div>
    </section>

    <aside class="right">
      <div class="ph"><b>MACRO EVENT ANALYSIS</b><span class="badge">23 TEMMUZ</span></div>
      <article class="event"><div class="eventtop">🇪🇺 <b>ECB Faiz Kararı</b><time>15:15 UTC</time></div><div class="eventbody"><p>Açıklanan: <strong>%2.40</strong> · Önceki: %2.40</p><div class="scenario bull"><b>▲ XAU ALIM:</b> Dovish ton ve EUR güçlenmesi USD'yi baskılarsa 4,085 test edilebilir.</div><div class="scenario bear"><b>▼ XAU SATIM:</b> Şahin söylem USD'yi güçlendirirse 4,040 / 4,000 izlenir.</div></div></article>
      <article class="event"><div class="eventtop">🇺🇸 <b>İşsizlik Başvuruları</b><time>15:30 UTC</time></div><div class="eventbody"><p>Açıklanan: <strong>187K</strong> · Beklenti: 215K</p><div class="scenario bear"><b>▼ USD GÜÇLÜ:</b> Beklenti altı veri, faiz indirimi beklentisini geciktirebilir; altın için kısa vadeli baskı.</div></div></article>
      <article class="event"><div class="eventtop">🇹🇷 <b>TCMB Faiz Kararı</b><time>14:00 UTC</time></div><div class="eventbody"><p>Açıklanan: <strong>%37.00</strong></p><div class="scenario bull"><b>▲ XAU/TRY:</b> TL zayıflama sinyali yerel altın talebini destekleyebilir.</div></div></article>
    </aside>
  </main>
</div>

<script>
/* ---------- SAAT ---------- */
function clock(){const n=new Date();document.getElementById('clock').textContent=n.toUTCString().slice(17,25);}
clock();setInterval(clock,1000);

/* ---------- SABİT S/R BÖLGELERİ (fiyat aralığına kilitli, hacme göre kalınlık) ---------- */
/* pxLow/pxHigh = grafik dikey aralığı referansı (yaklaşık 4,190 üst - 4,000 alt) */
const PX_TOP=4190, PX_BOT=3990;
function priceToTop(p){ return ((PX_TOP - p)/(PX_TOP-PX_BOT))*100; } // %
const SR=[
 {type:'r',lo:4113,hi:4123,label:'R2 · 4,118',vol:62,note:'ARZ'},
 {type:'r',lo:4079,hi:4091,label:'R1 · 4,085',vol:95,note:'ANA LİKİDİTE'},
 {type:'s',lo:4034,hi:4046,label:'S1 · 4,040',vol:88,note:'TALEP'},
 {type:'s',lo:3995,hi:4005,label:'S2 · 4,000',vol:70,note:'PSİKOLOJİK'},
];
(function drawZones(){
 const z=document.getElementById('zones');
 SR.forEach(s=>{
   const top=priceToTop(s.hi), bot=priceToTop(s.lo);
   const h=Math.max(6, bot-top); // yükseklik fiyat aralığına göre sabit
   const bw=1+Math.round(s.vol/28); // hacme göre çerçeve kalınlığı (ince->kalın)
   const width=45+ (s.vol*0.5); // hacim yüksekse daha geniş blok
   const d=document.createElement('div');
   d.className='zone '+s.type;
   d.style.top=top+'%'; d.style.height=h+'%';
   d.style.borderWidth=bw+'px'; d.style.width=Math.min(94,width)+'%';
   d.innerHTML=s.label+' <em>'+s.note+' · VOL '+s.vol+'</em>';
   z.appendChild(d);
 });
})();

/* ---------- CANLI SMART MONEY FLOW ---------- */
const firms=['Citadel LLC','Goldman Sachs','BlackRock','Bridgewater','JPMorgan','Millennium','Renaissance','Point72','Two Sigma','Morgan Stanley'];
const pairs=['XAU/USD','BTC/USD','EUR/USD','SPX500'];
const feed=document.getElementById('flowFeed');
function utc(){return new Date().toUTCString().slice(17,22)+' UTC';}
function rnd(a,b){return a+Math.random()*(b-a);}
function addFlow(){
 const buy=Math.random()>0.5;
 const firm=firms[Math.floor(Math.random()*firms.length)];
 const pair=pairs[Math.floor(Math.random()*pairs.length)];
 const lots=Math.round(rnd(400,5000)/50)*50;
 let entry=pair==='XAU/USD'?rnd(4040,4075):pair==='BTC/USD'?rnd(116000,120000):pair==='EUR/USD'?rnd(1.08,1.09):rnd(5850,5920);
 const fmt=pair==='EUR/USD'?entry.toFixed(4):Math.round(entry).toLocaleString('en-US');
 const el=document.createElement('article');
 el.className='flow '+(buy?'buy':'sell');
 el.innerHTML='<h4>'+firm+' <time>'+utc()+'</time></h4>'+
   '<div class="act '+(buy?'up':'down')+'">'+(buy?'▲ LONG':'▼ SHORT')+' — '+pair+'</div>'+
   '<p>'+lots.toLocaleString('en-US')+' lot · Giriş: '+fmt+'</p>';
 feed.prepend(el);
 while(feed.children.length>7) feed.removeChild(feed.lastChild);
}
for(let i=0;i<4;i++) addFlow();
setInterval(addFlow, 4500); // sürekli akış

/* ---------- AI BOT · 6 İNDİKATÖR · GERÇEKÇİ DEĞİŞKEN DEĞERLER ---------- */
/* Fiyatı rastgele yürüyüşle simüle et, indikatörleri gerçek formüllere yakın türet */
let price=4053.98;
let hist=[]; for(let i=0;i<220;i++){ price+=rnd(-2.2,2.0); hist.push(price); }
function ema(arr,p){let k=2/(p+1),e=arr[0];for(let i=1;i<arr.length;i++)e=arr[i]*k+e*(1-k);return e;}
function calcRSI(arr,p){let g=0,l=0;for(let i=arr.length-p;i<arr.length;i++){let d=arr[i]-arr[i-1];if(d>=0)g+=d;else l-=d;}if(l===0)return 100;let rs=(g/p)/(l/p);return 100-100/(1+rs);}
function botTick(){
 // yeni fiyat
 price+=rnd(-2.6,2.3); hist.push(price); if(hist.length>240)hist.shift();
 const last=hist[hist.length-1];
 // 6 indikatör
 const rsi=calcRSI(hist,14);
 const ema12=ema(hist.slice(-40),12), ema26=ema(hist.slice(-60),26);
 const macd=ema12-ema26;
 const ema50=ema(hist.slice(-90),50), ema200=ema(hist.slice(-200),200);
 const sma20=hist.slice(-20).reduce((a,b)=>a+b,0)/20;
 const sd=Math.sqrt(hist.slice(-20).reduce((a,b)=>a+(b-sma20)**2,0)/20);
 const bollUp=sma20+2*sd, bollLo=sma20-2*sd;
 const bollPct=((last-bollLo)/(bollUp-bollLo))*100;
 const win=hist.slice(-14), hi=Math.max(...win), lo=Math.min(...win);
 const stoch=((last-lo)/((hi-lo)||1))*100;
 const adx=Math.min(60,Math.abs(macd)*7+rnd(12,26));
 // skorlama (-1..+1)
 let score=0;
 score+= rsi>55?0.5: rsi<45?-0.5:0;
 score+= macd>0?0.6:-0.6;
 score+= ema50>ema200?0.5:-0.5;
 score+= bollPct>75?-0.3: bollPct<25?0.3:0;
 score+= stoch>80?-0.3: stoch<20?0.3:0;
 score+= adx>25?(macd>0?0.2:-0.2):0;
 const conf=Math.min(92,Math.max(52,Math.round(50+Math.abs(score)*22+rnd(-4,4))));
 let sig,col;
 if(score>0.6){sig='▲ BUY';col='var(--green)';}
 else if(score<-0.6){sig='▼ SELL';col='var(--red)';}
 else{sig='◆ NÖTR';col='var(--gold)';}
 // yaz
 const P=v=>v.toLocaleString('en-US',{maximumFractionDigits:2});
 document.getElementById('mkPrice').textContent=P(last);
 document.getElementById('sigTxt').textContent=sig;
 document.getElementById('sigTxt').style.color=col;
 document.getElementById('sigConf').textContent=conf+'% CONFIDENCE';
 // indikatör kutuları
 const set=(id,val,good)=>{const e=document.getElementById(id);e.textContent=val;e.className=good>0?'up':good<0?'down':'';};
 set('iRsi',rsi.toFixed(1), rsi>55?1:rsi<45?-1:0);
 set('iMacd',(macd>=0?'+':'')+macd.toFixed(2), macd>0?1:-1);
 set('iEma', ema50>ema200?'GOLDEN ▲':'DEATH ▼', ema50>ema200?1:-1);
 set('iBoll', bollPct.toFixed(0)+'%', bollPct>75?-1:bollPct<25?1:0);
 set('iStoch', stoch.toFixed(1), stoch>80?-1:stoch<20?1:0);
 set('iAdx', adx.toFixed(1), adx>25?1:0);
 // metin yorum
 document.getElementById('anText').innerHTML=
  'Bot 6 indikatörü canlı okuyor. RSI <b>'+rsi.toFixed(1)+'</b> ('+(rsi>55?'alıcı':rsi<45?'satıcı':'nötr')+'), MACD '+(macd>0?'pozitif':'negatif')+', EMA 50/'+(ema50>ema200?'200 üzeri (yükseliş yapısı)':'200 altı (düşüş yapısı)')+
  '. Bollinger bandında fiyat %<b>'+bollPct.toFixed(0)+'</b> konumda, Stochastic <b>'+stoch.toFixed(1)+'</b>, ADX <b>'+adx.toFixed(1)+'</b> ('+(adx>25?'trend güçlü':'trend zayıf')+
  '). Bileşke skor sinyali: <b style="color:'+col+'">'+sig+'</b> — güven %'+conf+'.';
 // trade seviyeleri (fiyata dinamik ama S/R'a saygılı)
 const r=x=>P(Math.round(x*100)/100);
 document.getElementById('scEntry').textContent=r(last);
 document.getElementById('scStop').textContent=r(sig.includes('SELL')?last+12:last-12);
 document.getElementById('scTp').textContent=r(sig.includes('SELL')?last-16:last+16);
 document.getElementById('swEntry').textContent=r(last);
 document.getElementById('swStop').textContent=r(sig.includes('SELL')?last+38:last-38);
 document.getElementById('swTp').textContent=r(sig.includes('SELL')?4000:4085);
 // durum yanıp sönmesi
 const bs=document.getElementById('botStatus'); bs.style.opacity=.35; setTimeout(()=>bs.style.opacity=1,250);
}
botTick();
setInterval(botTick, 3000); // bot sürekli çalışır

/* ---------- SEKME / BUTON ETKİLEŞİMLERİ ---------- */
document.querySelectorAll('.market').forEach(x=>x.onclick=()=>{document.querySelectorAll('.market').forEach(y=>y.classList.remove('active'));x.classList.add('active')});
document.querySelectorAll('.tfbtn').forEach(x=>x.onclick=()=>{document.querySelectorAll('.tfbtn').forEach(y=>y.classList.remove('on'));x.classList.add('on')});
</script>
</body>
</html>
"""

components.html(TERMINAL_HTML, height=1180, scrolling=True)
