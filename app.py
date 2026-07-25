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
[data-testid="stToolbar"] {display:none;}
.block-container {padding:0!important;max-width:100%!important;}
.stApp {background:#050b14;}
iframe {display:block;}
</style>
""", unsafe_allow_html=True)

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
.brand b{font:700 18px 'Playfair Display';letter-spacing:1.5px;color:var(--gold)}
.tabs{display:flex;gap:3px}
.tab{border:0;background:transparent;color:var(--muted);padding:7px 13px;font-size:11px;letter-spacing:.8px;cursor:pointer;border-radius:4px}
.tab:hover,.tab.active{color:var(--gold);background:rgba(212,175,55,.09)}
.live{display:flex;align-items:center;gap:6px;font:600 11px 'IBM Plex Mono';color:var(--muted)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 1.4s infinite}
.dot.off{background:var(--red);box-shadow:0 0 8px var(--red);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
main{flex:1;display:flex;overflow:hidden}
#chartWrap{flex:1;position:relative}
#chart{position:absolute;inset:0}
#overlay{position:absolute;top:12px;left:12px;z-index:5;background:rgba(9,21,37,.72);backdrop-filter:blur(10px);border:1px solid rgba(212,175,55,.25);border-radius:10px;padding:12px 14px;min-width:210px;font:500 11px 'IBM Plex Mono'}
#overlay h4{font:700 12px 'Playfair Display';color:var(--gold);letter-spacing:1px;margin-bottom:8px}
.ov-row{display:flex;justify-content:space-between;gap:16px;padding:2px 0;color:var(--muted)}
.ov-row span:last-child{color:var(--text)}
.sig{margin-top:8px;padding:6px 10px;border-radius:6px;text-align:center;font-weight:700;letter-spacing:1px}
.sig.buy{background:rgba(0,200,150,.15);color:var(--green);border:1px solid var(--green)}
.sig.sell{background:rgba(255,80,109,.15);color:var(--red);border:1px solid var(--red)}
.sig.hold{background:rgba(128,144,166,.12);color:var(--muted);border:1px solid var(--muted)}
.sig.closed{background:rgba(255,80,109,.08);color:var(--red);border:1px dashed var(--red)}
aside{width:280px;background:var(--panel);border-left:1px solid var(--line);padding:14px;overflow-y:auto}
aside h3{font:700 12px 'Playfair Display';color:var(--gold);letter-spacing:1px;margin-bottom:10px}
.pcard{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:8px;font-size:11px}
.pcard .t{color:var(--gold);font-weight:600;margin-bottom:3px}
.pcard .d{color:var(--muted);font-size:10px}
.price{font:700 15px 'IBM Plex Mono';color:var(--gold)}
</style>
</head>
<body>
<div id="app">
 <nav>
  <div class="brand"><b>◆ VALENS WEALTH</b></div>
  <div class="tabs">
   <button class="tab active" data-sym="BTCUSDT" data-lbl="BTC/USD">BTC/USD</button>
   <button class="tab" data-sym="ETHUSDT" data-lbl="ETH/USD">ETH/USD</button>
   <button class="tab" data-sym="XAUUSD" data-lbl="XAU/USD">XAU/USD</button>
  </div>
  <div class="live"><span class="dot" id="dot"></span><span id="liveTxt">CONNECTING…</span>&nbsp;&nbsp;<span class="price" id="hdrPrice">—</span></div>
 </nav>
 <main>
  <div id="chartWrap">
   <div id="chart"></div>
   <div id="overlay">
    <h4>QUANT ANALYSIS</h4>
    <div class="ov-row"><span>Trend (EMA)</span><span id="ovTrend">—</span></div>
    <div class="ov-row"><span>RSI(14)</span><span id="ovRsi">—</span></div>
    <div class="ov-row"><span>Support</span><span id="ovSup">—</span></div>
    <div class="ov-row"><span>Resistance</span><span id="ovRes">—</span></div>
    <div class="ov-row"><span>Pattern</span><span id="ovPat">—</span></div>
    <div class="sig hold" id="ovSig">ANALYZING…</div>
   </div>
  </div>
  <aside>
   <h3>SIGNAL LOG</h3>
   <div id="log"></div>
  </aside>
 </main>
</div>

<script>
const $=id=>document.getElementById(id);
let chart,candleSeries,ema20Line,ema50Line,supLine,resLine;
let ws=null,ohlc=[],curSym="BTCUSDT",curLbl="BTC/USD";

// ---------- CHART ----------
chart=LightweightCharts.createChart($('chart'),{
 layout:{background:{color:'#050b14'},textColor:'#8090a6',fontFamily:'IBM Plex Mono'},
 grid:{vertLines:{color:'rgba(255,255,255,.04)'},horzLines:{color:'rgba(255,255,255,.04)'}},
 rightPriceScale:{borderColor:'rgba(212,175,55,.2)'},
 timeScale:{borderColor:'rgba(212,175,55,.2)',timeVisible:true,secondsVisible:false},
 crosshair:{mode:0}
});
candleSeries=chart.addCandlestickSeries({
 upColor:'#00c896',downColor:'#ff506d',borderVisible:false,
 wickUpColor:'#00c896',wickDownColor:'#ff506d'
});
ema20Line=chart.addLineSeries({color:'#52a9ff',lineWidth:1,priceLineVisible:false,lastValueVisible:false});
ema50Line=chart.addLineSeries({color:'#d4af37',lineWidth:1,priceLineVisible:false,lastValueVisible:false});
window.addEventListener('resize',()=>chart.applyOptions({width:$('chart').clientWidth,height:$('chart').clientHeight}));

// ---------- MARKET HOURS ----------
function marketOpen(sym){
 if(sym==='BTCUSDT'||sym==='ETHUSDT')return true; // crypto 24/7
 const d=new Date();const day=d.getUTCDay();const h=d.getUTCHours();
 // XAU/USD: kapalı Cumartesi; Pazar 23:00 UTC öncesi kapalı; Cuma 22:00 UTC sonrası kapalı
 if(day===6)return false;
 if(day===0&&h<23)return false;
 if(day===5&&h>=22)return false;
 return true;
}

// ---------- INDICATORS ----------
function ema(data,p){const k=2/(p+1);let e=data[0].close;return data.map((c,i)=>{e=i?c.close*k+e*(1-k):c.close;return{time:c.time,value:+e.toFixed(2)}});}
function rsi(data,p=14){if(data.length<p+1)return 50;let g=0,l=0;for(let i=data.length-p;i<data.length;i++){const ch=data[i].close-data[i-1].close;ch>=0?g+=ch:l-=ch;}const rs=l===0?100:g/l;return +(100-100/(1+rs)).toFixed(1);}
function supRes(data){const n=Math.min(data.length,60);const s=data.slice(-n);let hi=-1e9,lo=1e9;s.forEach(c=>{if(c.high>hi)hi=c.high;if(c.low<lo)lo=c.low;});return{sup:lo,res:hi};}

// ---------- CANDLE PATTERNS ----------
function detectPattern(data){
 if(data.length<3)return null;
 const c=data[data.length-1],p=data[data.length-2];
 const body=Math.abs(c.close-c.open),range=c.high-c.low||1e-9;
 const upper=c.high-Math.max(c.close,c.open),lower=Math.min(c.close,c.open)-c.low;
 const bull=c.close>c.open,bear=c.close<c.open;
 // Hammer
 if(lower>body*2&&upper<body&&range>0)return{name:'🔨 Hammer',dir:'bull'};
 // Shooting Star
 if(upper>body*2&&lower<body)return{name:'⭐ Shooting Star',dir:'bear'};
 // Doji
 if(body<range*0.1)return{name:'✚ Doji',dir:'neutral'};
 // Bullish Engulfing
 if(bull&&p.close<p.open&&c.close>p.open&&c.open<p.close)return{name:'🟢 Bullish Engulfing',dir:'bull'};
 // Bearish Engulfing
 if(bear&&p.close>p.open&&c.close<p.open&&c.open>p.close)return{name:'🔴 Bearish Engulfing',dir:'bear'};
 // Marubozu
 if(body>range*0.9)return{name:bull?'▮ Bullish Marubozu':'▮ Bearish Marubozu',dir:bull?'bull':'bear'};
 return null;
}

// ---------- ANALYSIS ----------
function analyze(){
 if(!marketOpen(curSym)){
  $('ovSig').className='sig closed';$('ovSig').textContent='● MARKET CLOSED';
  $('ovTrend').textContent='—';$('ovRsi').textContent='—';
  $('ovPat').textContent='—';return;
 }
 if(ohlc.length<20)return;
 const e20=ema(ohlc,20),e50=ema(ohlc,50);
 ema20Line.setData(e20);ema50Line.setData(e50);
 const last=ohlc[ohlc.length-1].close;
 const trendUp=e20[e20.length-1].value>e50[e50.length-1].value;
 const r=rsi(ohlc);
 const{sup,res}=supRes(ohlc);
 const pat=detectPattern(ohlc);

 $('ovTrend').textContent=trendUp?'▲ Bullish':'▼ Bearish';
 $('ovTrend').style.color=trendUp?'#00c896':'#ff506d';
 $('ovRsi').textContent=r;
 $('ovSup').textContent=sup.toFixed(2);
 $('ovRes').textContent=res.toFixed(2);
 $('ovPat').textContent=pat?pat.name:'—';

 // S/R çizgileri
 if(supLine)candleSeries.removePriceLine(supLine);
 if(resLine)candleSeries.removePriceLine(resLine);
 supLine=candleSeries.createPriceLine({price:sup,color:'#00c896',lineWidth:1,lineStyle:2,title:'Support'});
 resLine=candleSeries.createPriceLine({price:res,color:'#ff506d',lineWidth:1,lineStyle:2,title:'Resistance'});

 // Skor
 let score=0;
 score+=trendUp?1:-1;
 if(r<30)score+=1;if(r>70)score-=1;
 const nearSup=last<=sup*1.004,nearRes=last>=res*0.996;
 let strong=false;
 if(pat){
  if(pat.dir==='bull'){score+=1;if(nearSup){score+=2;strong=true;}}
  if(pat.dir==='bear'){score-=1;if(nearRes){score-=2;strong=true;}}
 }
 let sig='hold',txt='◆ HOLD';
 if(score>=2){sig='buy';txt=strong?'▲ STRONG BUY':'▲ BUY';}
 else if(score<=-2){sig='sell';txt=strong?'▼ STRONG SELL':'▼ SELL';}
 $('ovSig').className='sig '+sig;$('ovSig').textContent=txt;

 // Pattern marker + log
 if(pat&&pat.dir!=='neutral'){
  candleSeries.setMarkers([{
   time:ohlc[ohlc.length-1].time,
   position:pat.dir==='bull'?'belowBar':'aboveBar',
   color:pat.dir==='bull'?'#00c896':'#ff506d',
   shape:pat.dir==='bull'?'arrowUp':'arrowDown',
   text:pat.name.replace(/[^\w ]/g,'').trim()
  }]);
 }
 if(sig!=='hold'&&strong)pushLog(txt,pat?pat.name:'',last);
}

let lastLog=0;
function pushLog(sig,pat,price){
 const now=Date.now();if(now-lastLog<8000)return;lastLog=now;
 const t=new Date().toLocaleTimeString('tr-TR');
 const el=document.createElement('div');el.className='pcard';
 el.innerHTML=`<div class="t">${sig}</div><div class="d">${pat} @ ${price.toFixed(2)} · ${t}</div>`;
 $('log').prepend(el);
 while($('log').children.length>12)$('log').lastChild.remove();
}

// ---------- DATA FEED ----------
async function loadHistory(sym){
 // XAU için Binance'te doğrudan çift yok; PAXG (altın destekli) proxy kullanılır
 const bsym=sym==='XAUUSD'?'PAXGUSDT':sym;
 try{
  const res=await fetch(`https://api.binance.com/api/v3/klines?symbol=${bsym}&interval=1m&limit=200`);
  const d=await res.json();
  ohlc=d.map(k=>({time:k[0]/1000,open:+k[1],high:+k[2],low:+k[3],close:+k[4]}));
  candleSeries.setData(ohlc);chart.timeScale().fitContent();
  analyze();
 }catch(e){console.error(e);}
}
function connect(sym){
 if(ws){ws.close();ws=null;}
 const bsym=(sym==='XAUUSD'?'PAXGUSDT':sym).toLowerCase();
 if(!marketOpen(sym)){$('dot').className='dot off';$('liveTxt').textContent='MARKET CLOSED';analyze();return;}
 ws=new WebSocket(`wss://stream.binance.com:9443/ws/${bsym}@kline_1m`);
 ws.onopen=()=>{$('dot').className='dot';$('liveTxt').textContent='LIVE · '+curLbl;};
 ws.onclose=()=>{$('dot').className='dot off';$('liveTxt').textContent='DISCONNECTED';};
 ws.onmessage=ev=>{
  const k=JSON.parse(ev.data).k;
  const bar={time:k[String('t')]/1000||k.t/1000,open:+k.o,high:+k.h,low:+k.l,close:+k.c};
  const last=ohlc[ohlc.length-1];
  if(last&&last.time===bar.time){ohlc[ohlc.length-1]=bar;}
  else{ohlc.push(bar);if(ohlc.length>300)ohlc.shift();}
  candleSeries.update(bar);
  $('hdrPrice').textContent=bar.close.toFixed(2);
  analyze();
 };
}

function switchSym(sym,lbl){
 curSym=sym;curLbl=lbl;
 $('log').innerHTML='';
 candleSeries.setMarkers([]);
 loadHistory(sym).then(()=>connect(sym));
}

document.querySelectorAll('.tab').forEach(t=>{
 t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');
  switchSym(t.dataset.sym,t.dataset.lbl);
 };
});

// init
setTimeout(()=>{chart.applyOptions({width:$('chart').clientWidth,height:$('chart').clientHeight});},100);
switchSym('BTCUSDT','BTC/USD');
setInterval(()=>{ // piyasa saati değişimini yakala
 if(!marketOpen(curSym)&&ws){ws.close();ws=null;$('dot').className='dot off';$('liveTxt').textContent='MARKET CLOSED';analyze();}
 if(marketOpen(curSym)&&!ws){connect(curSym);}
},30000);
</script>
</body>
</html>
"""

components.html(TERMINAL_HTML, height=780, scrolling=False)
