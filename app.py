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
                "$order": "report_date_as_yyyy_mm_dd DESC, open_interest_all DESC",
                "$limit": 25,
            }, timeout=8)
        rows = r.json()
        if not rows:
            return None
        # "GOLD" gibi geniş bir anahtar kelime CFTC'de birden fazla kontratı eşleştirebilir
        # (ör. gerçek COMEX GOLD kontratı VS küçük, tokenize "PAX GOLD" türev kontratı).
        # Önce en güncel rapor tarihine indirge, sonra o tarihteki en yüksek açık pozisyonlu
        # (open interest) kontratı seç — bu güvenilir şekilde asıl/likit kontrattır.
        latest_date = rows[0].get("report_date_as_yyyy_mm_dd")
        candidates = [row for row in rows if row.get("report_date_as_yyyy_mm_dd") == latest_date] or rows
        d = max(candidates, key=lambda row: int(float(row.get("open_interest_all", 0) or 0)))
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

# ============ GÜNÜN ÖNEMLİ EKONOMİK HABERLERİ ============
# Ücretsiz, anahtarsız/keyless ve Investing.com/ForexFactory gibi sitelerin kullanım şartlarını
# ihlal etmeyen bir takvim kaynağı yok. Bu yüzden Finnhub'ın ücretsiz katmanını (finnhub.io/register,
# ~1 dk, kredi kartı gerekmez) kullanıyoruz. Anahtar YOKSA panel bunu açıkça söyler, uydurma veri
# göstermez.
import datetime as _dt

@st.cache_data(ttl=900)
def get_econ_calendar():
    key = ""
    try:
        key = st.secrets.get("FINNHUB_API_KEY", "")
    except Exception:
        key = ""
    key = key or __import__("os").environ.get("FINNHUB_API_KEY", "")
    if not key:
        return {"available": False, "events": [], "reason": "no_key", "diag": "no_key"}
    try:
        today = _dt.date.today()
        r = requests.get(
            "https://finnhub.io/api/v1/calendar/economic",
            params={"from": today.isoformat(), "to": (today + _dt.timedelta(days=6)).isoformat(), "token": key},
            timeout=8,
        )
        status = r.status_code
        try:
            body = r.json()
        except Exception:
            body = {}
        # Finnhub bazen 200 döner ama gövdede hata/erişim mesajı olur (ör. plan bu endpoint'i kapsamıyorsa) —
        # bu durumda "economicCalendar" anahtarı hiç olmaz. Bunu sessizce "0 haber" ile karıştırmıyoruz.
        has_calendar_key = isinstance(body, dict) and "economicCalendar" in body
        raw = (body.get("economicCalendar") or []) if isinstance(body, dict) else []
        wanted = {"US", "EU", "DE", "GB", "JP", "CN", "TR"}
        out = []
        for ev in raw:
            if ev.get("impact") not in ("medium", "high"):
                continue
            if ev.get("country") not in wanted:
                continue
            out.append({
                "time": ev.get("time"),
                "country": ev.get("country"),
                "event": ev.get("event"),
                "impact": ev.get("impact"),
                "actual": ev.get("actual"),
                "estimate": ev.get("estimate"),
                "prev": ev.get("prev"),
                "unit": ev.get("unit"),
            })
        out.sort(key=lambda e: e.get("time") or "")
        diag = f"status={status} raw_events={len(raw)} has_calendar_key={has_calendar_key} filtered={len(out)}"
        if status == 401 or status == 403:
            return {"available": False, "events": [], "reason": "tier_gated", "diag": diag + " body=" + str(body)[:200]}
        if status != 200:
            return {"available": False, "events": [], "reason": "error", "diag": diag + " body=" + str(body)[:200]}
        if not has_calendar_key:
            return {"available": False, "events": [], "reason": "tier_gated", "diag": diag + " — endpoint erişim/plan sorunu olabilir, body=" + str(body)[:200]}
        return {"available": True, "events": out[:14], "diag": diag}
    except Exception as e:
        return {"available": False, "events": [], "reason": "error", "diag": "exception: " + str(e)[:200]}

ECON_JSON = _json.dumps(get_econ_calendar())

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
*{scrollbar-width:thin;scrollbar-color:rgba(212,175,55,.35) #07101c}
*::-webkit-scrollbar{width:8px;height:8px}
*::-webkit-scrollbar-track{background:#07101c}
*::-webkit-scrollbar-thumb{background:rgba(212,175,55,.35);border-radius:4px;border:1px solid #07101c}
*::-webkit-scrollbar-thumb:hover{background:rgba(212,175,55,.6)}
*::-webkit-scrollbar-corner{background:#07101c}
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
.shell{min-height:0;flex:1;display:grid;grid-template-columns:270px minmax(540px,1fr) 310px;overflow:hidden}
aside{background:var(--panel);min-height:0;overflow:auto}.left{border-right:1px solid var(--line)}.right{border-left:1px solid var(--line)}
.ph{height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 13px;border-bottom:1px solid var(--line)}
.panelcard{margin:9px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--panel2);box-shadow:0 2px 8px rgba(0,0,0,.2)}
.panelcard .ph{border-bottom:1px solid var(--line);background:rgba(212,175,55,.05)}
.ph.collapsible{cursor:pointer;list-style:none;user-select:none}
.ph.collapsible::-webkit-details-marker{display:none}
.ph.collapsible::after{content:'▾';color:var(--muted);font-size:10px;margin-left:6px;transition:transform .15s}
details[open]>.ph.collapsible::after{transform:rotate(180deg)}
details.panelgroup{border-bottom:none}
.statusdot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle;box-shadow:0 0 5px currentColor}
.statusdot.on{background:var(--green);color:var(--green)}
.statusdot.off{background:var(--red);color:var(--red)}
.statusdot.mid{background:var(--gold);color:var(--gold)}
.statusdot.na{background:var(--muted);color:var(--muted);box-shadow:none}
.gaugerow{display:flex;gap:13px;padding:9px 13px;background:#07101d;border-bottom:1px solid var(--line);flex-wrap:wrap;align-items:center;flex-shrink:0}
.gauge{display:flex;flex-direction:column;align-items:center;gap:4px;min-width:32px}
.statusdot.big{width:15px;height:15px;margin-right:0}
.gauge small{font:8px 'IBM Plex Mono';color:var(--muted);letter-spacing:.3px}
.ph b{font-size:10px;color:var(--gold);letter-spacing:1.2px}.badge{font:9px 'IBM Plex Mono';color:var(--gold);border:1px solid rgba(212,175,55,.3);padding:2px 6px;border-radius:9px}
.simwarn{font:8px 'IBM Plex Mono';color:#ffb27a;padding:4px 12px;background:rgba(255,120,60,.08);border-bottom:1px solid var(--line)}
.netdelta{margin:8px;padding:8px 10px;border-radius:7px;font:700 12px 'IBM Plex Mono';text-align:center;border:1px solid var(--line);background:var(--panel2);letter-spacing:.5px}
.netdelta.buy{color:var(--green);border-color:rgba(0,200,150,.4);box-shadow:0 0 12px rgba(0,200,150,.1)}
.netdelta.sell{color:var(--red);border-color:rgba(255,80,109,.4);box-shadow:0 0 12px rgba(255,80,109,.1)}
.flow{margin:8px;padding:10px;border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:7px;background:var(--panel2);animation:fadein .5s ease}
@keyframes fadein{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
.flow.buy{border-left-color:var(--green)}.flow.sell{border-left-color:var(--red)}
.flow h4{font-size:11px;display:flex;justify-content:space-between}.flow time{font-size:9px;color:var(--muted);font-weight:400}.flow .act{margin:6px 0 4px;font:700 11px 'IBM Plex Mono'}.flow p{font-size:9px;color:var(--muted);line-height:1.55}
.center{min-width:0;display:flex;flex-direction:column;overflow:auto}
.decision-desk{display:grid;grid-template-columns:1.22fr 1fr 1fr;gap:8px;padding:9px;background:#07101d;border-bottom:1px solid var(--line);flex-shrink:0}
.signal-main,.tradecard{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:11px;box-shadow:0 2px 10px rgba(0,0,0,.22)}
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
.levels{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:7px}.lev{background:#07101c;padding:6px;border-radius:3px}.lev small{display:block;font-size:8px;color:var(--muted)}.lev b{font:600 10.5px 'IBM Plex Mono'}
.entry{color:var(--blue)}.stop{color:var(--red)}.target{color:var(--green)}
.pnl{font:8px 'IBM Plex Mono';color:var(--green);margin-top:5px;text-align:center;background:rgba(0,200,150,.07);padding:3px;border-radius:3px}
.charthead{height:35px;display:flex;align-items:center;gap:10px;padding:0 12px;background:#080f1a;border-bottom:1px solid var(--line);flex-shrink:0}
.sessionbar{display:flex;align-items:center;gap:10px;padding:6px 12px;background:#07101c;border-bottom:1px solid var(--line);flex-shrink:0;flex-wrap:wrap;font:10px 'IBM Plex Mono'}
.sesspill{display:flex;align-items:center;gap:5px;padding:3px 8px;border-radius:10px;border:1px solid var(--line);color:var(--muted)}
.sesspill.on{border-color:rgba(0,200,150,.5);color:var(--green);background:rgba(0,200,150,.08)}
.sesspill .dot2{width:6px;height:6px;border-radius:50%;background:var(--muted)}
.sesspill.on .dot2{background:var(--green);box-shadow:0 0 6px var(--green)}
.sessCountdown{color:var(--gold);font-weight:700}
.sessNote{color:var(--muted);margin-left:auto;font-size:9px}
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
.stat{background:var(--panel2);border:1px solid var(--line);border-radius:7px;padding:8px 9px}
.stat small{display:block;font-size:8px;color:var(--muted);letter-spacing:.5px}.stat b{font:600 12px 'IBM Plex Mono'}
.analysis p{font-size:11px;color:var(--text);line-height:1.6;opacity:.9}
.upcoming{padding:10px 12px;border-top:1px solid var(--line);background:#07101c}
.upcoming .atitle{font-size:10px;color:var(--gold);letter-spacing:1px;font-weight:700;margin-bottom:8px}
.newsrow{display:flex;gap:9px;padding:8px;border:1px solid var(--line);border-radius:7px;background:var(--panel2);margin-bottom:7px}
.newsrow .tm{font:600 10px 'IBM Plex Mono';color:var(--gold);min-width:52px}
.newsrow .body{flex:1}.newsrow .body b{font-size:11px}.imp{color:#ff8498;font-size:9px;margin-left:5px}
.newsrow .body p{font-size:9px;color:var(--muted);line-height:1.5;margin-top:3px}
.newsrow .exp{font-size:9px;color:var(--text);opacity:.85;margin-top:3px}
.bottomnote{padding:7px 12px;background:#07101c;border-top:1px solid var(--line);font-size:9px;color:var(--muted)}
.event{margin:10px;border:1px solid var(--line);border-radius:8px;background:var(--panel2);overflow:hidden}
.eventtop{padding:9px 10px;display:flex;align-items:center;gap:6px;background:rgba(212,175,55,.06);border-bottom:1px solid var(--line)}.eventtop b{font-size:10.5px}.eventtop time{font-size:9px;color:var(--muted);margin-left:auto}
.eventbody{padding:10px}.eventbody p{font-size:9.5px;color:var(--muted);line-height:1.55;margin-bottom:7px}.scenario{font-size:9.5px;padding:7px;border-left:3px solid;margin-top:6px;line-height:1.55}.bull{border-color:var(--green);background:rgba(0,200,150,.06)}.bear{border-color:var(--red);background:rgba(255,80,109,.06)}
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
    <div class="tabs"><button class="tab active" data-i18n="tab_terminal">TERMINAL</button><button class="tab" data-i18n="tab_portfolio">PORTFOLIO</button><button class="tab" data-i18n="tab_research">RESEARCH</button><button class="tab" data-i18n="tab_settings">SETTINGS</button><button class="tab" data-i18n="tab_account">ACCOUNT</button></div>
    <div style="display:flex;align-items:center;gap:14px">
      <button id="langToggle" style="font:700 10px 'IBM Plex Mono';background:transparent;border:1px solid rgba(212,175,55,.35);color:var(--gold);padding:4px 9px;border-radius:4px;cursor:pointer;letter-spacing:.5px">EN</button>
      <div class="live"><i class="dot"></i> <span data-i18n="live">LIVE</span> · <span id="clock"></span> UTC</div>
    </div>
  </nav>

  <div class="ticker"><div class="ticklabel">LIVE</div><div class="tickscroll">
    <span>XAU/USD <b id="tkXau">—</b></span><span>BTC/USD <b id="tkBtc">—</b></span><span>EUR/USD <b id="tkEur">—</b></span><span id="tkEconNote" data-i18n="tickerEconFallback">Ekonomik takvim için sağ panele bakın.</span>
    <span>XAU/USD <b id="tkXau2">—</b></span><span>BTC/USD <b id="tkBtc2">—</b></span><span>EUR/USD <b id="tkEur2">—</b></span><span data-i18n="tickerDisclaimer">Kurumsal akış ve haber verileri doğrulama gerektirir.</span>
  </div></div>

  <div class="marketbar" id="marketbar">
    <button class="market active" data-sym="OANDA:XAUUSD" data-label="XAU/USD · GOLD OZ" data-price="4053.98"><small>XAU/USD · GOLD OZ</small><strong>4,053.98</strong> <small class="down">▼ -1.83%</small></button>
    <button class="market" data-sym="BINANCE:BTCUSDT" data-label="BTC/USD" data-price="118240"><small>BTC/USD</small><strong>118,240</strong> <small class="up">▲ +2.14%</small></button>
    <button class="market" data-sym="OANDA:EURUSD" data-label="EUR/USD" data-price="1.0842"><small>EUR/USD</small><strong>1.0842</strong> <small class="down">▼ -0.31%</small></button>
    <button class="market" data-sym="OANDA:SPX500USD" data-label="SPX500" data-price=""><small>SPX500</small><strong>—</strong> <small style="color:var(--muted)" data-i18n="noLiveShort">canlı veri yok</small></button>
  </div>

  <main class="shell">
    <aside class="left">
      <div class="ph"><b data-i18n="risk_governor_title">🛡 CHALLENGE RİSK YÖNETİCİSİ</b><span class="badge" id="riskBadge">—</span></div>
      <div style="padding:9px;border-bottom:1px solid var(--line)">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
          <label style="font:8px 'IBM Plex Mono';color:var(--muted)"><span data-i18n="risk_balance">Bakiye ($)</span><input id="riskBalance" type="number" step="1000" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:4px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
          <label style="font:8px 'IBM Plex Mono';color:var(--muted)"><span data-i18n="risk_daily">Günlük Kayıp Limiti (%)</span><input id="riskDailyPct" type="number" step="0.5" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:4px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
          <label style="font:8px 'IBM Plex Mono';color:var(--muted)"><span data-i18n="risk_max">Maks. Toplam Kayıp (%)</span><input id="riskMaxPct" type="number" step="0.5" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:4px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
          <label style="font:8px 'IBM Plex Mono';color:var(--muted)"><span data-i18n="risk_target">Kâr Hedefi (%)</span><input id="riskTargetPct" type="number" step="0.5" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:4px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
          <label style="font:8px 'IBM Plex Mono';color:var(--muted)"><span data-i18n="risk_lotmin">Lot (min)</span><input id="riskLotMin" type="number" step="0.1" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:4px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
          <label style="font:8px 'IBM Plex Mono';color:var(--muted)"><span data-i18n="risk_lotmax">Lot (max)</span><input id="riskLotMax" type="number" step="0.1" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:4px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
          <label style="font:8px 'IBM Plex Mono';color:var(--muted)"><span data-i18n="risk_days">Hedef Gün Sayısı</span><input id="riskDays" type="number" step="1" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:4px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
          <label style="font:8px 'IBM Plex Mono';color:var(--muted)"><span data-i18n="risk_start">Başlangıç Tarihi</span><input id="riskStart" type="date" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:4px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
        </div>
        <div id="riskSummary" style="font-size:9px;color:var(--muted);line-height:1.6;margin-bottom:6px">—</div>
        <div style="height:7px;border-radius:4px;background:#07101c;overflow:hidden;border:1px solid var(--line)"><div id="riskBar" style="height:100%;width:0%;background:var(--green);transition:width .3s"></div></div>
        <div id="riskDetail" style="font-size:9px;margin-top:5px;font-weight:700">—</div>
        <div style="border-top:1px dashed var(--line);margin-top:9px;padding-top:8px">
          <div style="font:9px 'IBM Plex Mono';color:var(--gold);margin-bottom:5px" data-i18n="goal_progress_title">🎯 HEDEFE İLERLEME (gerçek izlenen sonuçlardan)</div>
          <div style="height:7px;border-radius:4px;background:#07101c;overflow:hidden;border:1px solid var(--line)"><div id="goalBar" style="height:100%;width:0%;background:var(--gold);transition:width .3s"></div></div>
          <div id="goalDetail" style="font-size:9px;color:var(--muted);margin-top:5px;line-height:1.6">—</div>
        </div>
      </div>
      <div class="panelcard">
      <div class="ph"><b data-i18n="mt5_bridge_title">🔌 MT5 KÖPRÜSÜ (manuel onaylı)</b><span class="badge" id="mt5BridgeBadge">—</span></div>
      <div style="padding:9px">
        <div style="font-size:8px;color:var(--muted);margin-bottom:7px" data-i18n="mt5BridgeHint">Diğer bilgisayarınızda valens_mt5_executor.py çalışıyorsa buraya bağlanın. Otomatik gönderim YOK — her KESİN İŞLEM'de burada bir "Gönder" butonu belirir, siz onaylamadan hiçbir emir MT5'e gitmez. ⚠ Bu uygulama Streamlit Cloud gibi https bir adreste açıksa, sade http:// LAN adresine tarayıcı "mixed content" güvenliğiyle bağlanamayabilir — en güvenilir yöntem bu app.py'yi de o bilgisayarda/aynı ağda lokal çalıştırmaktır (streamlit run app.py).</div>
        <div style="display:flex;gap:6px;margin-bottom:7px">
          <input id="mt5BridgeUrl" type="text" placeholder="http://192.168.x.x:8899" style="flex:1;min-width:0;background:#07101c;border:1px solid var(--line);color:var(--text);padding:6px;border-radius:3px;font:9px 'IBM Plex Mono'">
          <button id="mt5BridgeToggle" style="padding:7px 10px;border-radius:4px;border:1px solid var(--line);background:#07101c;color:var(--text);font:9px 'IBM Plex Mono';cursor:pointer;white-space:nowrap" data-i18n="mt5BridgeToggleOff">🔌 Bağlan</button>
        </div>
        <div id="mt5BridgeStatus" style="font-size:8px;color:var(--muted);line-height:1.5;margin-bottom:7px">—</div>
        <div id="mt5SendArea" style="display:none">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
            <label style="font:8px 'IBM Plex Mono';color:var(--muted);flex:1"><span data-i18n="mt5LotLabel">Gönderilecek lot</span><input id="mt5SendLot" type="number" step="0.01" min="0.01" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
          </div>
          <button id="mt5SendBtn" style="width:100%;padding:8px;background:var(--gold);color:#07101b;border:0;border-radius:4px;font:700 9px 'IBM Plex Mono';cursor:pointer" data-i18n="mt5SendBtnLabel">⚡ Bu Sinyali MT5'e Gönder (Onayla)</button>
          <div style="border-top:1px dashed var(--line);margin-top:9px;padding-top:8px">
            <label style="display:flex;align-items:center;gap:6px;font:8px 'IBM Plex Mono';color:var(--muted);cursor:pointer;margin-bottom:6px">
              <input id="mt5AutoSend" type="checkbox" style="width:13px;height:13px;cursor:pointer">
              <span data-i18n="mt5AutoSendLabel">🤖 Otomatik Gönder — SADECE DEMO hesap için (onay beklemeden gönderir)</span>
            </label>
            <div style="display:flex;align-items:center;gap:6px">
              <label style="font:8px 'IBM Plex Mono';color:var(--muted);flex:1"><span data-i18n="mt5AutoMinConfLabel">Min. güven (%)</span><input id="mt5AutoMinConf" type="number" step="1" min="50" max="99" value="90" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:10px 'IBM Plex Mono';margin-top:2px"></label>
            </div>
            <div style="font-size:8px;color:#ffb27a;margin-top:6px" data-i18n="mt5AutoSendWarn">⚠ Bu kutu işaretliyken TÜM işlemler onay beklemeden gerçek MT5 hesabına gönderilir. Sadece demo/test hesabında kullanın — gerçek parada KAPALI tutun.</div>
          </div>
        </div>
      </div>
      </div>
      <div class="panelcard">
      <div class="ph"><b data-i18n="signal_api_title">☁️ MERKEZİ SİNYAL KAYDI (7/24 sunucu)</b><span class="badge" id="signalApiBadge">—</span></div>
      <div style="padding:9px">
        <div style="font-size:8px;color:var(--muted);margin-bottom:7px" data-i18n="signalApiHint">Terminal 7/24 sunucuda çalışıyorsa, her sinyal buraya da kaydedilir — hangi cihazdan/tarayıcıdan girerseniz girin AYNI geçmişi görürsünüz. Bağlı değilken hiçbir şey değişmez, kayıt sadece bu tarayıcıda (localStorage) tutulmaya devam eder.</div>
        <div style="display:flex;gap:6px;margin-bottom:6px">
          <input id="signalApiUrl" type="text" placeholder="https://terminal.valenswealth.com" style="flex:1;min-width:0;background:#07101c;border:1px solid var(--line);color:var(--text);padding:6px;border-radius:3px;font:9px 'IBM Plex Mono'">
        </div>
        <div style="display:flex;gap:6px;margin-bottom:7px">
          <input id="signalApiCode" type="text" placeholder="Erken erişim kodu" style="flex:1;min-width:0;background:#07101c;border:1px solid var(--line);color:var(--text);padding:6px;border-radius:3px;font:9px 'IBM Plex Mono'">
          <button id="signalApiToggle" style="padding:7px 10px;border-radius:4px;border:1px solid var(--line);background:#07101c;color:var(--text);font:9px 'IBM Plex Mono';cursor:pointer;white-space:nowrap" data-i18n="signalApiToggleOff">☁️ Bağlan</button>
        </div>
        <div id="signalApiStatus" style="font-size:8px;color:var(--muted);line-height:1.5;margin-bottom:7px">—</div>
        <div id="signalApiStatsArea" style="display:none">
          <div style="border-top:1px dashed var(--line);margin-top:2px;padding-top:8px;font:9px 'IBM Plex Mono';color:var(--gold);margin-bottom:6px" data-i18n="signalApiStatsTitle">📊 Merkezi Strateji Performansı (tüm cihazlar)</div>
          <div id="signalApiStatsBody" style="font-size:9px;color:var(--text);line-height:1.8">—</div>
        </div>
      </div>
      </div>
      <div class="panelcard">
      <div class="ph"><b data-i18n="scalpMode_title">⚡ 1M SCALP MODU</b><span class="badge" id="scalpModeBadge">KAPALI</span></div>
      <div style="padding:9px">
        <div style="font-size:8px;color:var(--muted);margin-bottom:7px" data-i18n="scalpModeHint">Açınca grafik 1 dakikaya geçer, tüm stratejiler normal şekilde aranmaya devam eder — ama üst zaman dilimi (4H/1H) yapısı da hesaba katılır: onunla uyumlu sinyallerin güveni artar ("How to Analysis": üst zaman dilimi yön verir, alt zaman dilimi onay). Kapatınca önceki zaman dilimine döner.</div>
        <button id="scalpModeToggle" style="width:100%;padding:10px;background:var(--gold);color:#07101b;border:0;border-radius:4px;font:700 10px 'IBM Plex Mono';cursor:pointer;margin-bottom:8px" data-i18n="scalpModeToggleOff">⚡ 1M Scalp Modunu Aç</button>
        <div id="scalpModeBias" style="display:none;font-size:9px;color:var(--text);line-height:1.8">—</div>
      </div>
      </div>
      <div class="panelcard">
      <div class="ph"><b data-i18n="backtest_title">🔬 GEÇMİŞ VERİ TESTİ (backtest)</b><span class="badge" id="backtestBadge">—</span></div>
      <div style="padding:8px 9px">
        <div style="font-size:8px;color:var(--muted);margin-bottom:6px" data-i18n="backtestHint">Şu anki grafikteki GERÇEKTEN YAŞANMIŞ son ~300 muma bakılarak, her strateji geçmişte ateşlendiği HER noktada TP'ye mi SL'ye mi önce ulaşmış hesaplanır. Rastgele/olası gelecek tahmini DEĞİLDİR — sadece "bu kalıp bu grafikte geçmişte işe yaramış mı" sorusuna cevap verir.</div>
        <div id="backtestBody"><p style="color:var(--muted);font-size:8px">—</p></div>
      </div>
      </div>
      <div class="panelcard">
      <div class="ph"><b data-i18n="stratLive_title">📊 GERÇEK STRATEJİ PERFORMANSI (canlı takip)</b><span class="badge" id="stratLiveBadge">—</span></div>
      <div style="padding:8px 9px">
        <div style="font-size:8px;color:var(--muted);margin-bottom:6px" data-i18n="stratLiveHint">Bu terminalin ürettiği ve TP/SL'ye ulaştığı GERÇEK sinyallerden — hangi strateji burada gerçekten kazandırdı/kaybettirdi, kalıcı olarak hatırlanır. En az 3 işlem birikmeden gösterilmez.</div>
        <div id="stratLiveBody"><p style="color:var(--muted);font-size:8px">—</p></div>
      </div>
      </div>
      <div class="ph"><b data-i18n="order_flow_title">ORDER FLOW · YÜKLÜ İŞLEMLER</b><span class="badge" data-i18n="live">CANLI</span></div>
      <div class="simwarn" data-i18n="simwarn">🐋 BTC/kripto için Binance canlı YÜKLÜ (whale) emirleri gösterilir. Forex/endeks için agrega simülasyondur.</div>
      <div class="netdelta" id="netDelta">NET DELTA: — </div>
      <div id="flowFeed"></div>
    </aside>

    <section class="center">
      <div class="megaalert" id="fullAlignmentBanner" style="border-color:var(--gold);background:linear-gradient(90deg,rgba(212,175,55,.22),rgba(0,200,150,.12))"><span style="font-size:18px">🎯</span><div><b id="faBannerTitle" data-i18n="fullAlignmentTitle">TAM UYUM — KESİN İŞLEM</b><br><span id="faBannerBody">—</span></div></div>
      <div class="megaalert" id="megaAlert"><span style="font-size:16px">🚨</span><div><b id="megaAlertTitle" data-i18n="mega_alert_title">YÜKSEK POTANSİYELLİ SCALP</b><br><span id="megaAlertBody">—</span></div></div>

      <div class="gaugerow" id="gaugeRow">
        <div class="gauge"><i class="statusdot big na" id="gd_rsi"></i><small>RSI</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_macd"></i><small>MACD</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_ema"></i><small>EMA</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_boll"></i><small>BOLL</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_stoch"></i><small>STOCH</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_adx"></i><small>ADX</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_wr"></i><small>W%R</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_cci"></i><small>CCI</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_psar"></i><small>SAR</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_vwap"></i><small>VWAP</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_trend"></i><small data-i18n="gaugeTrend">TREND</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_pattern"></i><small data-i18n="gaugeCandle">MUM</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_sr"></i><small>S/R</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_fib"></i><small>FIB</small></div>
        <div class="gauge"><i class="statusdot big na" id="gd_news"></i><small data-i18n="gaugeNews">HABER</small></div>
      </div>

      <div class="decision-desk">
        <div class="signal-main">
          <div class="kicker"><span><span data-i18n="signal_engine">AI SIGNAL ENGINE</span> · <span id="sigPair">XAU/USD</span></span><em id="botStatus" data-i18n="running">● ÇALIŞIYOR</em></div>
          <div class="signalrow"><div class="sigtxt" id="sigTxt">—</div><div class="conf" id="sigConf">—</div></div>
          <div class="why" id="sigWhy" data-i18n="why_placeholder">Bot indikatörleri okuyor…</div>
          <div class="trigger wait" id="trigger">◇ GÖZLEM — Emir eşiği %87</div>
          <div id="strategyTagLine" style="font-size:9px;color:var(--gold);margin-top:5px;display:none"></div>
          <div class="winrate" id="winRate" data-i18n="winrate_placeholder">Geçmiş sinyal takibi: veri birikiyor…</div>
          <div style="margin-top:5px;display:flex;gap:8px">
            <a href="#" id="exportTrades" style="font:9px 'IBM Plex Mono';color:var(--blue);text-decoration:none" data-i18n="export_btn">⬇ Geçmişi Dışa Aktar (.json)</a>
            <label style="font:9px 'IBM Plex Mono';color:var(--blue);cursor:pointer"><span data-i18n="import_btn">⬆ İçe Aktar</span><input type="file" id="importTrades" accept="application/json" style="display:none"></label>
          </div>
        </div>
        <div class="tradecard">
          <h4>⚡ <span data-i18n="scalp_plan">SCALP PLAN</span> <span class="tf">15M / 30M</span></h4>
          <div class="levels"><div class="lev"><small data-i18n="entry_lbl">GİRİŞ</small><b class="entry" id="scEntry">—</b></div><div class="lev"><small data-i18n="stop_lbl">STOP</small><b class="stop" id="scStop">—</b></div><div class="lev"><small>TP</small><b class="target" id="scTp">—</b></div></div>
          <div id="scStatus" class="trade-status wait">◇ GÖZLEM — Emir eşiği %87</div>
          <div class="pnl" id="scPnl">Hedef ≈ $250 @ 2.5 lot</div>
          <div id="scTightTpNote" style="display:none;font-size:8px;color:#ffb27a;margin-top:5px;line-height:1.5"></div>
          <div id="scLastSignal" style="font:9px 'IBM Plex Mono';color:var(--muted);margin-top:5px">—</div>
        </div>
        <div class="tradecard">
          <h4>◆ <span data-i18n="swing_plan">SWING PLAN</span> <span class="tf">1H / 4H</span></h4>
          <div class="levels"><div class="lev"><small data-i18n="entry_lbl">GİRİŞ</small><b class="entry" id="swEntry">—</b></div><div class="lev"><small data-i18n="stop_lbl">STOP</small><b class="stop" id="swStop">—</b></div><div class="lev"><small>TP</small><b class="target" id="swTp">—</b></div></div>
          <div class="pnl" id="swPnl">Hedef ≈ $750 @ 2.5 lot</div>
          <div id="swLastSignal" style="font:9px 'IBM Plex Mono';color:var(--muted);margin-top:5px">—</div>
        </div>
      </div>

      <div class="charthead">
        <b id="chartTitle">XAU/USD · GOLD SPOT</b>
        <button class="tfbtn" data-int="1">1M</button><button class="tfbtn on" data-int="15">15M</button><button class="tfbtn" data-int="30">30M</button><button class="tfbtn" data-int="60">1H</button><button class="tfbtn" data-int="240">4H</button><button class="tfbtn" data-int="D">1D</button>
        <span id="goldOffsetNote" style="margin-left:auto;font-size:9px;color:var(--muted);font-family:'IBM Plex Mono'"></span>
      </div>

      <div class="sessionbar" id="sessionBar">
        <span class="sesspill" id="pillSydney"><i class="dot2"></i> Sydney</span>
        <span class="sesspill" id="pillTokyo"><i class="dot2"></i> Tokyo</span>
        <span class="sesspill" id="pillLondon"><i class="dot2"></i> London</span>
        <span class="sesspill" id="pillNewyork"><i class="dot2"></i> New York</span>
        <span id="sessCountdown" class="sessCountdown">—</span>
        <span id="sessNote" class="sessNote">—</span>
      </div>

      <div class="chartzone">
        <div class="volprofile"><div class="vphead" data-i18n="vol_profile">📊 HACİM PROFİLİ</div><div id="vpBars"></div></div>
        <div class="chartwrap">
          <div id="valensChart"></div>
          <div id="chartClosed"><span data-i18n="market_closed">● PİYASA KAPALI</span><small id="chartClosedMsg" data-i18n="weekend_msg">Hafta sonu — canlı veri akışı yok</small></div>
          <div class="zones" id="zones"></div>
        </div>
      </div>

      <div class="analysis">
        <div class="atitle"><span data-i18n="analysis_title_pre">📊 CANLI GRAFİK ANALİZİ ·</span> <span id="anPair">XAU/USD</span> <span data-i18n="analysis_title_post">· 12 GERÇEK İNDİKATÖR + GRAFİK + HABER</span><em id="anStatus" data-i18n="updating">● GÜNCELLENİYOR</em></div>
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
        <p id="anText" data-i18n="analysis_starting">Analiz motoru başlatılıyor…</p>
      </div>

      <div class="upcoming">
        <div class="atitle"><span data-i18n="econ_calendar_title">🗓️ EKONOMİK TAKVİM · BUGÜN + YAKLAŞAN (CANLI)</span> <span id="calDate"></span></div>
        <div class="tradingview-widget-container" style="border-radius:6px;overflow:hidden;border:1px solid var(--line)">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
          {
          "colorTheme": "dark",
          "isTransparent": true,
          "width": "100%",
          "height": "360",
          "locale": "tr",
          "importanceFilter": "-1,0,1",
          "countryFilter": "us,eu,gb,tr,de,jp,cn"
          }
          </script>
        </div>
        <p style="font-size:8px;color:var(--muted);margin-top:4px" data-i18n="tv_source_note">Kaynak: TradingView resmi Economic Calendar widget'ı (ücretsiz, gömme amaçlı sağlanır) · canlı ve otomatik güncellenir.</p>
      </div>

      <div class="bottomnote" data-i18n="bottomnote">AL/SAT sinyali; 12 gerçek indikatör (RSI, MACD, EMA50/200, Bollinger, Stochastic, ADX, ATR, VWAP, Williams %R, CCI, Parabolic SAR, Pivot) + grafik çizimleri (trend/kanal/Fibonacci/S-R/mum formasyonu) + o günkü haber yönü (manuel/canlı) kombine edilerek üretilir. Stop/hedef mesafeleri gerçek ATR volatilitesine göre dinamik hesaplanır. Grafik verisi Binance canlı feed'inden gelir (XAU→PAXG proxy). COT verisi CFTC resmi kaynağından çekilir. "Geçmiş başarı oranı" gerçekten üretilen sinyallerin TP/SL'ye önce ulaşma sonucundan hesaplanır — sabit/iddia edilen bir doğruluk yüzdesi değildir.</div>
    </section>

    <aside class="right">
      <div class="ph"><b data-i18n="macro_event_analysis">MACRO EVENT ANALYSIS</b><span class="badge" id="macroDate"></span></div>
      <article class="event" id="cotPanel" style="border-color:rgba(212,175,55,.4)">
        <div class="eventtop">🏦 <b data-i18n="cot_report">COT RAPORU · Kurumsal Pozisyon</b><time id="cotDate">—</time></div>
        <div class="eventbody" id="cotBody"><p style="color:var(--muted)" data-i18n="cot_loading">COT verisi yükleniyor…</p></div>
      </article>
      <div class="ph" style="border-top:1px solid var(--line)"><b data-i18n="todays_news">GÜNÜN ÖNEMLİ HABERLERİ</b><span class="badge" id="newsBadge">—</span></div>
      <div style="padding:8px 9px;border-bottom:1px solid var(--line)">
        <div style="font-size:8px;color:var(--muted);margin-bottom:6px" data-i18n="manualNewsHint">TradingView takviminden 3 yıldızlı haberi buraya girin — senaryo yorumu otomatik üretilir.</div>
        <div style="display:grid;grid-template-columns:2fr 1fr;gap:5px;margin-bottom:5px">
          <input id="mnEvent" type="text" placeholder="Ör: Fed Interest Rate Decision" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
          <select id="mnCountry" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
            <option value="US">🇺🇸 US</option><option value="EU">🇪🇺 EU</option><option value="DE">🇩🇪 DE</option>
            <option value="GB">🇬🇧 GB</option><option value="JP">🇯🇵 JP</option><option value="CN">🇨🇳 CN</option><option value="TR">🇹🇷 TR</option>
          </select>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;margin-bottom:6px">
          <input id="mnEstimate" type="text" placeholder="Beklenti" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
          <input id="mnPrev" type="text" placeholder="Önceki" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
          <input id="mnActual" type="text" placeholder="Gerçekleşen (varsa)" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
        </div>
        <div style="display:flex;gap:6px">
          <button id="mnAdd" style="flex:1;background:var(--gold);color:#07101b;border:0;padding:6px;border-radius:4px;font:700 9px 'IBM Plex Mono';cursor:pointer" data-i18n="manualNewsAdd">+ EKLE</button>
          <button id="mnClear" style="background:transparent;color:var(--muted);border:1px solid var(--line);padding:6px 9px;border-radius:4px;font:9px 'IBM Plex Mono';cursor:pointer" data-i18n="manualNewsClear">Temizle</button>
        </div>
      </div>
      <div id="newsEvents"><p style="color:var(--muted);font-size:10px;padding:9px" data-i18n="loading">Yükleniyor…</p></div>
      <div class="ph" style="border-top:1px solid var(--line)"><b data-i18n="trade_log_title">📒 SİNYAL KAR/ZARAR TAKİBİ</b><span class="badge" id="tradeLogBadge">—</span></div>
      <div style="padding:8px 9px">
        <div id="tradeLogSummary" style="font-size:9px;color:var(--muted);line-height:1.6;margin-bottom:6px">—</div>
        <div id="tradeLogList" style="max-height:230px;overflow:auto"></div>
      </div>
    </aside>
  </main>
</div>

<script>
let LANG = localStorage.getItem('valens_lang')||'tr';
const MONTHS = {
 tr: ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'],
 en: ['January','February','March','April','May','June','July','August','September','October','November','December']
};
const I18N = {
 tr: {
  live:'CANLI', order_flow_title:'ORDER FLOW · YÜKLÜ İŞLEMLER',
  simwarn:"🐋 BTC/kripto için Binance canlı YÜKLÜ (whale) emirleri gösterilir. Forex/endeks için agrega simülasyondur.",
  mega_alert_title:'YÜKSEK POTANSİYELLİ SCALP', signal_engine:'AI SIGNAL ENGINE', running:'● ÇALIŞIYOR',
  why_placeholder:'Bot indikatörleri okuyor…', winrate_placeholder:'Geçmiş sinyal takibi: veri birikiyor…',
  export_btn:'⬇ Geçmişi Dışa Aktar (.json)', import_btn:'⬆ İçe Aktar',
  scalp_plan:'SCALP PLAN', swing_plan:'SWING PLAN', entry_lbl:'GİRİŞ', stop_lbl:'STOP',
  vol_profile:'📊 HACİM PROFİLİ', market_closed:'● PİYASA KAPALI', weekend_msg:'Hafta sonu — canlı veri akışı yok',
  analysis_title_pre:'📊 CANLI GRAFİK ANALİZİ ·', analysis_title_post:'· 12 İNDİKATÖR + 8 STRATEJİ + GRAFİK + HABER',
  updating:'● GÜNCELLENİYOR', analysis_starting:'Analiz motoru başlatılıyor…',
  econ_calendar_title:'🗓️ EKONOMİK TAKVİM · BUGÜN + YAKLAŞAN (CANLI)',
  tv_source_note:"Kaynak: TradingView resmi Economic Calendar widget'ı (ücretsiz, gömme amaçlı sağlanır) · canlı ve otomatik güncellenir.",
  bottomnote:'AL/SAT sinyali; 12 gerçek indikatör (RSI, MACD, EMA50/200, Bollinger, Stochastic, ADX, ATR, VWAP, Williams %R, CCI, Parabolic SAR, Pivot) + grafik çizimleri (trend/kanal/Fibonacci/S-R/mum formasyonu) + 8 adlandırılmış strateji kalıbı (EMA kesişimi, ORB, momentum, likidite süpürme, RSI uyumsuzluğu, Bollinger sıkışması, EMA pullback, iç mum) + o günkü haber yönü (manuel/canlı) — HEPSİ TEK bir ağırlıklı skora kombine edilerek üretilir. Stop/hedef mesafeleri gerçek ATR volatilitesine göre dinamik hesaplanır. Grafik verisi Binance canlı feed\'inden gelir (XAU→PAXG proxy). COT verisi CFTC resmi kaynağından çekilir. "Geçmiş başarı oranı" gerçekten üretilen sinyallerin TP/SL\'ye önce ulaşma sonucundan hesaplanır — sabit/iddia edilen bir doğruluk yüzdesi değildir.',
  macro_event_analysis:'MACRO EVENT ANALYSIS', cot_report:'COT RAPORU · Kurumsal Pozisyon', cot_loading:'COT verisi yükleniyor…',
  todays_news:'GÜNÜN ÖNEMLİ HABERLERİ', loading:'Yükleniyor…',
  tab_terminal:'TERMINAL', tab_portfolio:'PORTFOLIO', tab_research:'RESEARCH', tab_settings:'SETTINGS', tab_account:'ACCOUNT',
  noDataStatus:'● VERİ YOK', noDataDesc:l=>'<b>'+l+'</b> için canlı OHLC/fiyat feed bağlantısı yok (bu enstrüman için gerçek veri kaynağı entegre edilmedi). Gerçek veri olmadan sinyal ve gösterge <b>üretilmiyor</b> — uydurma sayı göstermek yerine devre dışı bırakıldı.',
  noDataTrigger:'● VERİ AKIŞI YOK — sinyal üretilmiyor', noDataStatusShort:'● VERİ YOK',
  loadingStatus:'◇ YÜKLENİYOR', loadingDesc:l=>'Gerçek zamanlı OHLC verisi yükleniyor ('+l+')… veri gelince göstergeler ve sinyal motoru canlanacak.',
  loadingTrigger:'◇ VERİ YÜKLENİYOR…',
  marketClosedDesc:l=>'<b>'+l+'</b> piyasası şu an <b style="color:var(--red)">KAPALI</b>. Piyasa açılana kadar sinyal üretilmez.',
  marketClosedTrigger:'● PİYASA KAPALI — sinyal yok',
  watching:'◇ GÖZLEM', armedText:(dir)=>'⚡ EMİR TETİKLENDİ · '+dir+' · %',
  netlik:' NETLİK', esik:' / %', mutabakat:' eşik · ', mutabakatSuffix:' mutabakat',
  confidenceSuffix:'% CONFIDENCE · ', indicatorAgree:' indikatör mutabık',
  confirmedTrade:'⚡ KESİN İŞLEM · ', watchingThreshold:'◇ GÖZLEM — Emir eşiği %',
  targetProjection:(amt)=>'Hedefe ulaşırsa ≈ $'+amt+' @ 2.5 lot (projeksiyon, garanti değil)',
  megaAlertBody:(dir,l,en,st,tp,amt)=>'Giriş '+en+' · Stop '+st+' · Hedef '+tp+' · Hedefe ulaşırsa ≈ $'+amt+' @ 2.5 lot (15-30M) — bu bir garanti değil, TP\'ye ulaşırsa oluşacak projeksiyondur.',
  winBuilding:(n)=>'Geçmiş sinyal takibi: veri birikiyor ('+n+' sonuçlanan işlem) — güvenilir olması için en az birkaç düzine gerekir.',
  winResult:(n,w,r)=>'Gerçek takip: son '+n+' sinyalden <b>'+w+'</b> kazandı → <b>%'+r+'</b> gerçekleşen başarı oranı (bu terminaldeki geçmiş sinyallerden hesaplanır, iddia edilen bir hedef değildir).',
  aggConfirmNone:'3 MUM ONAY: Yok', aggConfirmYes:(dir)=>'3 MUM ONAY: '+dir+' · Güçlü teyit',
  exportSuccess:null, importSuccess:'Sinyal geçmişi içe aktarıldı.', importFail:'Dosya okunamadı — geçerli bir Valens yedek dosyası olduğundan emin olun.',
  newsApiMissing:'Canlı haber akışı için ücretsiz bir Finnhub API anahtarı gerekiyor (finnhub.io/register, ~1 dk, kart istemez) — Streamlit secrets\'e <code>FINNHUB_API_KEY</code> olarak eklenince bu panel otomatik dolar. Anahtar yokken uydurma haber gösterilmiyor.',
  newsTierGated:'Anahtarınız geçerli (diğer uç noktalarda çalışıyor) ama bu ekonomik takvim özelliği Finnhub\'ın ÜCRETSİZ planında kapalı — ücretli bir özellik. Bu paneli otomatik doldurmak için ücretli bir Finnhub planı (ya da başka bir ücretli takvim API\'si) gerekir. Bu arada aşağıdaki "EKONOMİK TAKVİM" bölümündeki TradingView widget\'ı zaten gerçek ve ücretsiz — güncel haberler için oraya bakabilirsiniz.',
  manualNewsHint:'TradingView takviminden 3 yıldızlı haberi buraya girin — senaryo yorumu otomatik üretilir.',
  manualNewsAdd:'+ EKLE', manualNewsClear:'Temizle',
  manualNewsEmpty:'Henüz haber eklenmedi. TradingView takvimine bakıp yukarıdaki formdan 3 yıldızlı haberleri ekleyin — sistem otomatik senaryo üretecek.',
  manualNewsNeedName:'Lütfen önce haber adını girin.',
  manualNewsRemove:'Sil', manualClearConfirm:'Tüm manuel eklenen haberleri silmek istediğinize emin misiniz?',
  cotLong:'Long', cotShort:'Short', cotSourceNote:'Kaynak: CFTC Legacy COT · her Salı kesiti Cuma yayınlanır.',
  tightTpWarning:(pct)=>'⚠ Dar hedef / geniş stop yapısı (video kaynağında gözlemlenen orana göre): hedef stoptan küçük, bu yüzden başabaş noktası için en az %'+pct+' gerçek kazanma oranı gerekir. Kazanma oranı yüksek görünse bile, kayıplar kazançlardan büyük olur — dikkatli değerlendirin.',
  stratLive_title:'📊 GERÇEK STRATEJİ PERFORMANSI (canlı takip)', stratLiveBadge:(n)=>n+' işlem',
  stratLiveHint:'Bu terminalin ürettiği ve TP/SL\'ye ulaştığı GERÇEK sinyallerden — hangi strateji burada gerçekten kazandırdı/kaybettirdi, kalıcı olarak hatırlanır. En az 3 işlem birikmeden gösterilmez.',
  stratLiveEmpty:'Henüz sonuçlanan sinyal yok — TP veya SL\'ye ulaşan ilk sinyalden itibaren burada birikmeye başlayacak.',
  newsNoEvents:'Önümüzdeki günler için orta/yüksek etkili planlı haber bulunamadı.', newsNoTemplate:'Bu veri tipi için hazır senaryo şablonu yok — rakamları kendi analizinize göre değerlendirin.',
  newsSame:'Sonuç beklentiyle aynı geldi — belirgin bir yön sinyali yok.',
  newsBeat:'aştı', newsMiss:'ıskaladı', newsHigh:'YÜKSEK', newsMed:'ORTA',
  ccyStrengthens:'güçlendirir', ccyWeakens:'zayıflatır',
  xauPressureNote:' XAU/USD için genel eğilim: baskı (USD güçlü).', xauSupportNote:' XAU/USD için genel eğilim: destek (USD zayıf).',
  xauPressureScenario:' → XAU/USD üzerinde baskı yönünde etki beklenir.', xauSupportScenario:' → XAU/USD üzerinde destekleyici etki beklenir.',
  newsCountBadge:n=>n+' HABER', defaultEventName:'Ekonomik Veri',
  ruleNfp:'İstihdam verisi', ruleUnrate:'İşsizlik oranı', ruleClaims:'İşsizlik başvuruları', ruleCpi:'Enflasyon (CPI)',
  ruleJolts:'JOLTS Açık İş Sayısı', ruleAdp:'ADP İstihdam Değişimi', ruleChallenger:'Challenger İşten Çıkarma',
  employmentFamilyNote:'📌 Bu, geniş "istihdam ailesi" verilerinden biri — JOLTS (açık iş sayısı), ADP, NFP (tarım dışı istihdam), İşsizlik Başvuruları ve İşsizlik Oranı birbiriyle ilişkilidir ve genelde birkaç gün arayla art arda gelir (ör. JOLTS → birkaç gün sonra İşsizlik Başvuruları → ayın ilk Cuma\'sı NFP). Piyasa bunları TEK TEK değil, biriktirdiği genel "işgücü piyasası zayıflıyor mu güçleniyor mu" resmine göre yorumlar — art arda gelen birkaç zayıf/güçlü veri, tek bir veriden daha belirleyicidir.',
  ruleGdp:'GSYH (GDP)', ruleRetail:'Perakende satışlar', rulePmi:'PMI', ruleRate:'Faiz kararı', ruleTrade:'Dış ticaret dengesi',
  noLiveFeedTitle:'● CANLI VERİ YOK', noLiveFeedDesc:"Bu enstrüman için Binance feed'i yok — TwelveData/OANDA API gerekir", noLiveShort:'canlı veri yok',
  goldOffsetLine:(sign,val)=>'PAXG proxy vs gerçek spot altın farkı: '+sign+val+'$ (ticker fiyatı ve giriş/stop/hedef sayıları bu farka göre otomatik düzeltilir; sadece grafik üzerindeki mum/S-R çizgileri ham PAXG ekseninde kalır)',
  tickerEconFallback:'Ekonomik takvim için sağ panele bakın.', tickerDisclaimer:'Kurumsal akış ve haber verileri doğrulama gerektirir.',
  tickerNextEvent:(country,name,time)=>country+' '+name+' — '+time,
  zoneTop:'Bölge Üst', zoneBottom:'Bölge Alt', srNearZone:'konsolidasyon/hacim bölgesine yakın',
  fvgTop:'FVG Üst', fvgBottom:'FVG Alt', fvgCE:'FVG %50 (CE)', fvgEntry:'FVG Giriş',
  mainResistance:'Ana Direnç (1H)', mainSupport:'Ana Destek (1H)', srNearMainSupport:'ana desteğe (1H) yakın', srNearMainResistance:'ana dirence (1H) yakın',
  mainResistanceBroken:'Eski Direnç (kırıldı → olası destek)', mainSupportBroken:'Eski Destek (kırıldı → olası direnç)',
  tagEmaCross:'EMA Momentum Kesişimi (9/21 + MACD/RSI)', tagOrb:'Açılış Aralığı Kırılımı (ORB)', tagMomentum:'Ardışık Mum Momentum Kırılımı',
  tagLiquiditySweep:'Likidite Süpürme Dönüşü (200 EMA + VWAP Reddi)',
  tagRsiDivergence:'RSI Uyumsuzluğu (Divergence)', tagBollSqueeze:'Bollinger Sıkışması + Kırılımı',
  tagEmaPullback:"EMA21'e Geri Çekilme (Trend Devamı)", tagInsideBar:'İç Mum (Inside Bar) Kırılımı',
  tagFvgRetest:'Fair Value Gap Retest (ICT)', tagObFvgConfluence:'Order Block + FVG Confluence (SMC)', tagIfvg:'Inverse Fair Value Gap (ICT)', tagAmdCycle:'AMD Döngüsü (Accumulation-Manipulation-Distribution)',
  tagValuationZone:'Değerleme Ekstremi + Bölge Confluence', tagMacdZeroCross:'MACD Sıfır Çizgisi Kesişimi',
  tagScalpOrb:'ORB Scalp Varyantı (dar aralık)', tagNoWickRetest:'No Wick (Fitilsiz Mum) Geri Test',
  tagOrbSweepFade:'ORB Süpürme-Geri Dönüş', tagBosSignal:'Piyasa Yapısı: BOS (Yapı Devamı)',
  tagChochSignal:'Piyasa Yapısı: CHoCH (Karakter Değişimi)', tagEqualHighsLows:'Eşit Tepe/Dip (EQH/EQL) Likidite Avı',
  tagTradeDelta:'Trades Delta (Gerçek Alım/Satım Hacim Farkı)',
  tagSilverBullet:'Silver Bullet (Likidite Süpürmesi + FVG)', tagOrbVolume:'ORB + Hacim Onayı',
  tagVwapPullback:'VWAP Geri Çekilme + Dönüş Mumu', tagTtmSqueeze:'TTM Squeeze (Bollinger/Keltner)',
  tagDivergenceChoch:'RSI Uyumsuzluğu + CHoCH', tagPocBounce:'Hacim Profili POC Sekmesi',
  tagOrderBlockMit:'Order Block Mitigasyonu', tagFibOte:'Fibonacci OTE (Optimal Giriş Bölgesi)',
  tagAsianFakeout:'Asya Aralığı Killzone Sahte Kırılımı', tagExtremeMR:'Aşırı Ortalamaya Dönüş (3-Sigma)',
  tagLevelConfluence:'Önceki Gün Seviye Confluence (POC/VAH/VAL)', tagDeltaConfirmTrend:'Delta Doğrulaması (Fonlanmış Hareket)',
  tagDeltaAbsorption:'Delta Absorpsiyonu (Tükeniş/Olası Dönüş)',
  candidateConfluence:'Çoklu Gösterge Konfluensi (15 klasik gösterge)',
  winningCandidateLine:(label,conf)=>'En güçlü aday: <b>'+label+'</b> (%'+conf+' güven)',
  noCandidateLine:'Şu an hiçbir strateji ya da gösterge konfluensi net bir sinyal vermiyor.',
  catUp:'YÜKSELİŞ', catDown:'DÜŞÜŞ', catNeutral:'NÖTR', catNoData:'aktif sinyal yok',
  catFull:'TAM DESTEKLİYOR', catNone:'ZIT YÖNDE', catPartial:'KISMEN DESTEKLİYOR',
  catIndicators:'📊 İNDİKATÖRLER', catActiveOf:'aktif /', catStrategies:'📐 STRATEJİLER',
  catNoStrategies:'Şu an ateşlenen bir strateji kalıbı yok', catChart:'📈 GRAFİK YORUMLAMA (trend + S/R + Fib)',
  catCandle:'🕯️ MUM GRAFİĞİ (formasyon)', catNoPattern:'Belirgin bir mum formasyonu yok',
  catFullAlignment:'TAM UYUM — indikatörler, stratejiler, mum ve grafik yorumlaması AYNI YÖNDE. Bu, sistemin en yüksek güven durumudur.',
  fullAlignmentTitle:'🎯 TAM UYUM — KESİN İŞLEM',
  fullAlignmentBody:(dir,label,conf)=>'Tüm kategoriler (indikatörler + stratejiler + mum + grafik yorumlaması) '+dir+' yönünde birleşti · '+label+' · %'+conf+' güven — bu sistemin en net anlarından biri, yine de garanti değildir.',
  catVerdict:'NET KARAR', catConfidence:'güven', catNoVerdictYet:'henüz net bir karar yok',
  strategyTagPrefix:'📐 Bu karara katkıda bulunan strateji kalıpları: ',
  rateDecisionNote:"⚠ Faiz kararlarında \"beklenti üstü/altı\" mantığı yanıltıcı olabilir: piyasa kararı zaten büyük ölçüde önceden fiyatlar (ör. CME FedWatch olasılıkları). Asıl fiyatı oynatan genelde üç şey: (1) sonucun piyasanın fiyatladığı OLASILIKLA örtüşüp örtüşmediği — beklenen bir 'sabit tutma' bile önceden fiyatlanan bir 'artış riski' kalkınca rahatlama yükselişi yaratabilir, (2) komitedeki muhalif oy dağılımı (şahin/güvercin), (3) açıklama metni ve basın toplantısının TONU. Bunların hiçbirini actual/forecast rakamından otomatik okuyamayız — bu yüzden burada yön tahmini VERMİYORUZ, sadece bunu bilin diye not düşüyoruz.",
  newsExpectLbl:'Beklenti', newsPrevLbl:'Önceki', newsActualLbl:'Gerçekleşen',
  newsCcyResult:(dir,ccy,label,beatTxt,dirTxt,extra)=>'<b>'+dir+' '+ccy+' PARA BİRİMİ:</b> '+label+' beklentiyi '+beatTxt+' → genellikle '+ccy+' para birimini '+dirTxt+'.'+extra,
  newsScenarioBeat:(label,ccy,extra)=>'<b>▲ BEKLENTİ ÜSTÜ GELİRSE:</b> '+label+' güçlü gelirse, genellikle '+ccy+' para birimi güçlenir'+extra,
  newsScenarioMiss:(label,ccy,extra)=>'<b>▼ BEKLENTİ ALTI GELİRSE:</b> '+label+' zayıf gelirse, genellikle '+ccy+' para birimi zayıflar'+extra,
  newsBeatUp:'beklenti üstü', newsBeatDown:'beklenti altı', newsLive:'(bugünkü gerçek veriden — ', newsManual:' (manuel)',
  newsData:'Haber',
  cotNoData:'Bu enstrüman için COT verisi yok (CFTC yalnız vadeli piyasa raporlar).',
  cotHedgeFunds:'HEDGE FONLAR (Spekülatör)', cotBanks:'BANKALAR / TİCARİ', cotNetLong:'NET LONG', cotNetShort:'NET SHORT',
  cotLong:'Long', cotShort:'Short', cotSourceNote:'Kaynak: CFTC Legacy COT · her Salı kesiti Cuma yayınlanır.',
  cotWeeklyNote:'Haftada 1 güncellenir, bu normaldir.',
  cotStaleWarning:(days)=>'Bu veri '+days+' gündür aynı — beklenenden eski olabilir, CFTC kaynağını kontrol edin.',
  psarUpLbl:'▲ YÜKSELİŞ', psarDownLbl:'▼ DÜŞÜŞ', trendUp:'yükselen trend', trendDown:'düşen trend', trendFlat:'yatay',
  srNearSupport:l=>'desteğe yakın ('+l+')', srNearResistance:l=>'dirence yakın ('+l+')',
  srNearDynSupport:'dinamik desteğe (Dyn Support) yakın', srNearDynResistance:'dinamik dirence (Dyn Resistance) yakın',
  confluenceSuffix:' + Fib seviyesi confluence',
  conflictWarning:'⚠ KARIŞIK SİNYAL: başka bir strateji/analiz kazanan adayın TERS yönünde de güçlü bir sinyal veriyor. En iyi seçeneği yine de gösteriyoruz, ama bu bölgede görüşler bölünmüş — dikkatli olun.',
  conflictBadge:'⚠ KARIŞIK SİNYAL — dönüş bölgesi olabilir',
  noLastSignal:'Henüz bu seviyede sinyal verilmedi.',
  lastSignalLine:(dir,entry,tp,time)=>'Son sinyal: <b>'+dir+'</b> · Giriş '+entry+' → TP '+tp+' · '+time,
  risk_governor_title:'🛡 CHALLENGE RİSK YÖNETİCİSİ', risk_balance:'Bakiye ($)', risk_daily:'Günlük Kayıp Limiti (%)',
  gaugeTrend:'TREND', gaugeCandle:'MUM', gaugeNews:'HABER',
  signal_api_title:'☁️ MERKEZİ SİNYAL KAYDI (7/24 sunucu)',
  signalApiHint:'Terminal 7/24 sunucuda çalışıyorsa, her sinyal buraya da kaydedilir — hangi cihazdan/tarayıcıdan girerseniz girin AYNI geçmişi görürsünüz. Bağlı değilken hiçbir şey değişmez, kayıt sadece bu tarayıcıda (localStorage) tutulmaya devam eder.',
  signalApiToggleOff:'☁️ Bağlan', signalApiToggleOn:'⏸ Bağlantıyı Kes',
  signalApiConnecting:'Bağlanıyor…', signalApiConnected:'✓ Bağlı — sinyaller merkezi olarak kaydediliyor.',
  signalApiInvalidCode:'✗ Erken erişim kodu yanlış.', signalApiUnreachable:'✗ Sunucuya ulaşılamadı — adresi kontrol edin.',
  signalApiNoUrl:'Önce sunucu adresini girin.',
  signalApiStatsTitle:'📊 Merkezi Strateji Performansı (tüm cihazlar)',
  signalApiStatsLine:(label,trades,winRate)=>label+': '+trades+' işlem · %'+winRate+' kazanma',
  signalApiStatsEmpty:'Henüz sonuçlanan sinyal yok.',
  mt5_bridge_title:'🔌 MT5 KÖPRÜSÜ (manuel onaylı)',
  mt5BridgeHint:'Diğer bilgisayarınızda valens_mt5_executor.py çalışıyorsa buraya bağlanın. Otomatik gönderim YOK — her KESİN İŞLEM\'de burada bir "Gönder" butonu belirir, siz onaylamadan hiçbir emir MT5\'e gitmez.',
  mt5BridgeToggleOff:'🔌 Bağlan', mt5BridgeToggleOn:'⏸ Bağlantıyı Kes',
  mt5BridgeBadgeOn:'BAĞLI', mt5BridgeBadgeOff:'BAĞLI DEĞİL',
  mt5BridgeNoUrl:'⚠ Önce köprü adresini girin (ör. http://192.168.1.23:8899).',
  mt5BridgeConnectedNote:'Köprüye bağlanıldı — KESİN İŞLEM oluştuğunda gönder butonu aktif olacak.',
  mt5BridgeStoppedNote:'Bağlantı kesildi.',
  mt5BridgeUnreachable:'⚠ Köprüye ulaşılamıyor — adresi, ağı ve valens_mt5_executor.py\'nin çalıştığını kontrol edin (https sayfadan http köprüye bağlanmak tarayıcı tarafından engellenmiş olabilir).',
  mt5BridgeExecuted:'✓ Gönderildi, MT5\'te işlem açıldı.',
  mt5BridgeSkipped:(reason)=>'Köprüye ulaştı ama işlem AÇILMADI (sebep: '+reason+').',
  mt5LotLabel:'Gönderilecek lot', mt5SendBtnLabel:'⚡ Bu Sinyali MT5\'e Gönder (Onayla)', mt5SendBtnSending:'Gönderiliyor…', mt5SendBtnSent:'✓ Gönderildi (bu sinyal için)',
  mt5CandleLimitReached:'⏸ Bu mumda/yönde gönderim sınırına (2) ulaşıldı — yeni mum bekleniyor.', mt5CandleLimitBtn:'⏸ Mum Başına Sınır Doldu (2/2)',
  mt5AutoSendLabel:'🤖 Otomatik Gönder — SADECE DEMO hesap için (onay beklemeden gönderir)',
  mt5AutoMinConfLabel:'Min. güven (%)',
  mt5AutoSendWarn:'⚠ Bu kutu işaretliyken TÜM işlemler onay beklemeden gerçek MT5 hesabına gönderilir. Sadece demo/test hesabında kullanın — gerçek parada KAPALI tutun.',
  scalpMode_title:'⚡ 1M SCALP MODU',
  scalpModeHint:'Açınca grafik 1 dakikaya geçer, tüm stratejiler normal şekilde aranmaya devam eder — ama üst zaman dilimi (4H/1H) yapısı da hesaba katılır: onunla uyumlu sinyallerin güveni artar ("How to Analysis": üst zaman dilimi yön verir, alt zaman dilimi onay). Kapatınca önceki zaman dilimine döner.',
  scalpModeToggleOff:'⚡ 1M Scalp Modunu Aç', scalpModeToggleOn:'⏸ 1M Scalp Modunu Kapat',
  scalpModeBadgeOn:'AÇIK', scalpModeBadgeOff:'KAPALI',
  scalpBiasUp:'Yükseliş', scalpBiasDown:'Düşüş', scalpBiasFlat:'Belirsiz',
  scalpBiasLine:(h4,h1)=>'4H: <b>'+h4+'</b> · 1H: <b>'+h1+'</b>',
  scalpBiasOnlySide:(side)=>'— '+side+' sinyalleri güçlendiriliyor (%10)',
  scalpBiasNoConsensus:'— 4H/1H uyuşmuyor, normal arama devam ediyor (bonus/ceza yok)',
  confSourceBacktest:'Güven, geçmiş veri testi sonuçlarına göre ayarlandı',
  regimePrefix:'📍 Piyasa Rejimi:', regimeTrendUp:'Güçlü Yükseliş Trendi', regimeTrendDown:'Güçlü Düşüş Trendi',
  regimeTrendFlat:'Güçlü Trend (yönsüz)', regimeRanging:'Yatay/Range', regimeUnclear:'Belirsiz/Geçiş',
  regimeBonus:'Bu strateji şu anki piyasa rejimine UYGUN — güven artırıldı', regimePenalty:'Bu strateji şu anki piyasa rejimine UYMUYOR — güven düşürüldü',
  structurePrefix:'📐 Yapı:', structureUp:'Yükselen (HH/HL)', structureDown:'Düşen (LH/LL)',
  structureBrokenUp:'Yükselen — kırılım (BOS) ▲', structureBrokenDown:'Düşen — kırılım (BOS) ▼', structureUnclear:'Belirsiz',
  structureBonus:'Bu strateji gerçek swing yapısına (BOS) UYGUN — güven artırıldı', structurePenalty:'Bu strateji gerçek swing yapısına (BOS) TERS — güven düşürüldü',
  exhaustionPrefix:'🕯️ Tükeniş:', exhaustionTop:'Tepede ret mumu kümesi', exhaustionTopStrong:'Tepede GÜÇLÜ ret kümesi ▼',
  exhaustionBottom:'Dipte ret mumu kümesi', exhaustionBottomStrong:'Dipte GÜÇLÜ ret kümesi ▲', exhaustionNone:'Yok',
  exhaustionBonus:'Bu strateji tepe/dip ret mumu kümesiyle UYUMLU — güven artırıldı', exhaustionPenalty:'Bu strateji tükenmiş yönde devam bekliyor — güven düşürüldü',
  backtest_title:'🔬 GEÇMİŞ VERİ TESTİ (backtest)',
  backtestHint:'Şu anki grafikteki GERÇEKTEN YAŞANMIŞ son ~300 muma bakılarak, her strateji geçmişte ateşlendiği HER noktada TP\'ye mi SL\'ye mi önce ulaşmış hesaplanır. Rastgele/olası gelecek tahmini DEĞİLDİR.',
  backtestNotEnoughData:'Yeterli geçmiş veri birikmedi (en az ~350 mum gerekir).',
  backtestNoSignals:'Bu ~300 mumda, en az 3 kez ateşlenen bir strateji bulunamadı.',
  backtestCandleCount:(n)=>'son '+n+' mum',
  risk_max:'Maks. Toplam Kayıp (%)', risk_target:'Kâr Hedefi (%)',
  risk_lotmin:'Lot (min)', risk_lotmax:'Lot (max)', risk_days:'Hedef Gün Sayısı', risk_start:'Başlangıç Tarihi',
  goal_progress_title:'🎯 HEDEFE İLERLEME (gerçek izlenen sonuçlardan)',
  goalDetailLine:(net,target,pctDone,daysLeft,paceNeeded,paceActual)=>
    'İzlenen net: <b>'+net+'</b> / $'+target+' hedef (%'+pctDone+'). Kalan: <b>'+daysLeft+' gün</b>. '+
    'Hedefe ulaşmak için günde ortalama <b>'+paceNeeded+'</b> gerekir — şu ana kadarki gerçek tempo: <b>'+paceActual+'/gün</b>. '+
    'Bu bir tahmindir, gerçek lot her işlemde kaydedilmediği için ortalama lot ('+t('avgLotNote')+') ile hesaplanır; garanti değildir.',
  avgLotNote:'lot aralığınızın ortalaması',
  trade_log_title:'📒 SİNYAL KAR/ZARAR TAKİBİ', tradeLogConfirmCandles:'mum onayı',
  tradeLogBadge:(n)=>n+' İŞLEM',
  tradeLogSummaryLine:(total,wins,losses,net)=>total+' işlem izlendi · <span style="color:var(--green)">'+wins+' kâr</span> / <span style="color:var(--red)">'+losses+' zarar</span> · Net: <b>'+net+'</b> (ortalama lot varsayımıyla tahmini)',
  tradeLogEmpty:'Henüz sonuçlanan bir sinyal yok — bir sinyal TP veya SL\'ye ulaştığında burada listelenecek.',
  tradeLogWin:'✓', tradeLogLoss:'✗',
  sessClosesIn:(label,time)=>label+' seansı kapanışa: '+time,
  sessOpensIn:(label,time)=>label+' seansı açılışa: '+time,
  sessNoneActive:'Şu an aktif ana seans yok (düşük likidite) — spread\'ler genişleyebilir.',
  sessHighActivity:(list)=>'Bu seansta genellikle en likit: '+list,
  sessLowActivity:'Bu seansta takip ettiğimiz enstrümanlarda görece düşük aktivite beklenir.',
  proxyStillMoving:(label)=>'⚠ Gerçek '+label+' piyasası kapalı (hafta sonu/seans dışı) — bu grafik 7/24 açık bir kripto proxy\'sinden geliyor, o yüzden hareket etmeye devam ediyor. Sinyal ÜRETİLMİYOR.',
  riskSummaryLine:(daily,max,target)=>'Günlük limit: <b>$'+daily+'</b> · Maks. kayıp: <b>$'+max+'</b> · Hedef: <b>$'+target+'</b>',
  riskOkBadge:'GÜVENLİ', riskWarnBadge:'DİKKAT', riskBlockBadge:'DURDUR',
  riskOkDetail:(pnl)=>'Bugünkü izlenen net: '+(pnl>=0?'+':'')+'$'+pnl+' — sınırın içinde.',
  riskWarnDetail:(pnl,pct)=>'⚠ Bugünkü kayıp günlük limitin %'+pct+'\'ine ulaştı ('+pnl+'$) — dikkatli olun.',
  riskBlockDetail:(pnl)=>'🛑 Bugünkü kayıp güvenlik eşiğini aştı ($'+pnl+') — yeni işlem ARANMIYOR. Yarın sıfırlanır.',
  riskBlockedStatus:'🛑 GÜNLÜK RİSK SINIRI — yeni sinyal durduruldu',
  cooldownStatus:(min)=>'⏸ STOP SONRASI SOĞUMA — ters yön '+min+' dk daha bekletiliyor (whipsaw koruması)',
  cooldownWhyNote:(min)=>' <span style="color:#ffb27a">⏸ Az önce ters yönde STOP oldu — sahte dönüş riskine karşı '+min+' dk daha bu yönde KESİN İŞLEM açılmayacak (aynı yönde devam serbest).</span>',
  confirmStatus:(have,need,dir)=>'🕐 MUM KAPANIŞ ONAYI BEKLENİYOR — '+dir+' · '+have+'/'+need+' mum',
  confirmWhyNote:(have,need)=>' <span style="color:var(--blue)">🕐 Bu sinyal henüz sadece '+have+'/'+need+' mum tarafından doğrulandı — mum kapanıp bir SONRAKİ mum da aynı yönü desteklerse KESİN İŞLEM sayılacak (aynı mumun ilk okuması tek başına yeterli değil, sahte titreşim riskine karşı).</span>',
  anText: p => (p.totalVotes>0 ? ('Bot '+p.totalVotes+' gerçek girdiyi (indikatörler + grafik kalıpları + 8 adlandırılmış strateji + haber) '+p.label+' üzerinde <b>gerçek Binance OHLC verisinden</b> tek bir skora kombine ediyor.') : ('Bot şu an '+p.label+' üzerinde net bir yön bulamıyor — göstergeler/stratejiler birbiriyle çelişiyor ya da hiçbiri belirgin değil (aşağıdaki kategori dökümüne bakın).')) + ' RSI <b>'+p.rsi+'</b>, MACD '+(p.macdPos?'pozitif':'negatif')+
   ', EMA 50/'+(p.emaGolden?'200 üzeri':'200 altı')+', ATR <b>'+p.atr+'</b> (volatilite), fiyat VWAP\'ın '+(p.vwapAbove?'üzerinde':'altında')+
   ', Williams %R <b>'+p.williamsR+'</b>, CCI <b>'+p.cci+'</b>, Parabolic SAR '+(p.psarUp?'yükseliş':'düşüş')+' yönünde. '+
   'Grafik: '+(p.trend>0?'yükselen trend':p.trend<0?'düşen trend':'yatay')+
   (p.patternName?' · '+p.patternName:'')+ (p.srText?' · '+p.srText:'')+
   '. Haber yönü'+(p.newsLive?' (bugünkü gerçek veriden — '+p.newsDetail+')':' (manuel)')+': '+(p.newsBias>0?'▲ pozitif':p.newsBias<0?'▼ negatif':'nötr')+
   '. Bileşke: <b style="color:'+p.sigColor+'">'+p.sigText+'</b> — güven %'+p.conf+' · '+p.agreeCount+'/'+p.totalVotes+' indikatör aynı yönde.',
  confSuffixLine:(conf,agree,total)=>conf+'% CONFIDENCE · '+agree+'/'+total+' indikatör mutabık',
  armedTrigger:(dir,conf)=>'⚡ EMİR TETİKLENDİ · '+dir+' · %'+conf+' NETLİK',
  waitTrigger:(conf,thr,agree,total)=>'◇ GÖZLEM · %'+conf+' / %'+thr+' eşik · '+agree+'/'+total+' mutabakat',
  confirmedStatus:(dir,conf,time)=>'⚡ KESİN İŞLEM · '+dir+' · %'+conf+' · '+time,
  waitStatus:(thr,conf)=>'◇ GÖZLEM — Emir eşiği %'+thr+' · %'+conf,
  targetHit:(amt)=>'Hedefe ulaşırsa ≈ $'+amt+' @ 2.5 lot (projeksiyon, garanti değil)',
  targetHitRange:(min,max,lotMin,lotMax)=>'Hedefe ulaşırsa ≈ $'+min+'–$'+max+' @ '+lotMin+'-'+lotMax+' lot (projeksiyon, garanti değil)',
  megaAlertTitleDyn:(dir,label)=>'🚨 YÜKSEK POTANSİYEL SCALP · '+dir+' · '+label,
  megaAlertBodyDyn:(en,st,tp,amt)=>'Giriş '+en+' · Stop '+st+' · Hedef '+tp+' · Hedefe ulaşırsa ≈ $'+amt+' @ 2.5 lot (15-30M) — bu bir garanti değil, TP\'ye ulaşırsa oluşacak projeksiyondur.',
  megaAlertBodyRange:(en,st,tp,min,max,lotMin,lotMax)=>'Giriş '+en+' · Stop '+st+' · Hedef '+tp+' · Hedefe ulaşırsa ≈ $'+min+'–$'+max+' @ '+lotMin+'-'+lotMax+' lot (15-30M) — bu bir garanti değil, TP\'ye ulaşırsa oluşacak projeksiyondur.',
 },
 en: {
  live:'LIVE', order_flow_title:'ORDER FLOW · LARGE TRADES',
  simwarn:"🐋 Live whale orders shown for BTC/crypto (Binance). Forex/index flow is an aggregate simulation.",
  mega_alert_title:'HIGH-POTENTIAL SCALP', signal_engine:'AI SIGNAL ENGINE', running:'● RUNNING',
  why_placeholder:'Bot is reading indicators…', winrate_placeholder:'Historical signal tracking: gathering data…',
  export_btn:'⬇ Export History (.json)', import_btn:'⬆ Import',
  scalp_plan:'SCALP PLAN', swing_plan:'SWING PLAN', entry_lbl:'ENTRY', stop_lbl:'STOP',
  vol_profile:'📊 VOLUME PROFILE', market_closed:'● MARKET CLOSED', weekend_msg:'Weekend — no live data feed',
  analysis_title_pre:'📊 LIVE CHART ANALYSIS ·', analysis_title_post:'· 12 INDICATORS + 8 STRATEGIES + CHART + NEWS',
  updating:'● UPDATING', analysis_starting:'Starting analysis engine…',
  econ_calendar_title:'🗓️ ECONOMIC CALENDAR · TODAY + UPCOMING (LIVE)',
  tv_source_note:"Source: TradingView's official Economic Calendar widget (free, provided for embedding) · updates live and automatically.",
  bottomnote:'The BUY/SELL signal is produced by combining 12 real indicators (RSI, MACD, EMA50/200, Bollinger, Stochastic, ADX, ATR, VWAP, Williams %R, CCI, Parabolic SAR, Pivot) + chart drawings (trend/channel/Fibonacci/S-R/candle pattern) + 8 named strategy patterns (EMA cross, ORB, momentum, liquidity sweep, RSI divergence, Bollinger squeeze, EMA pullback, inside bar) + the day\'s news direction (manual/live) — ALL combined into ONE weighted score. Stop/target distances are dynamically sized from real ATR volatility. Chart data comes from Binance\'s live feed (XAU→PAXG proxy). COT data comes from the official CFTC source. The "historical win rate" is computed from whether real generated signals actually reached TP or SL first — it is not a fixed or claimed accuracy figure.',
  macro_event_analysis:'MACRO EVENT ANALYSIS', cot_report:'COT REPORT · Institutional Positioning', cot_loading:'Loading COT data…',
  todays_news:"TODAY'S KEY NEWS", loading:'Loading…',
  tab_terminal:'TERMINAL', tab_portfolio:'PORTFOLIO', tab_research:'RESEARCH', tab_settings:'SETTINGS', tab_account:'ACCOUNT',
  noDataStatus:'● NO DATA', noDataDesc:l=>'No live OHLC/price feed is connected for <b>'+l+'</b> (no real data source is integrated for this instrument). No signal or indicator is <b>produced</b> without real data — disabled instead of showing a made-up number.',
  noDataTrigger:'● NO DATA FEED — no signal produced', noDataStatusShort:'● NO DATA',
  loadingStatus:'◇ LOADING', loadingDesc:l=>'Loading real-time OHLC data ('+l+')… indicators and the signal engine will come alive once data arrives.',
  loadingTrigger:'◇ LOADING DATA…',
  marketClosedDesc:l=>'<b>'+l+'</b> market is currently <b style="color:var(--red)">CLOSED</b>. No signal is produced until the market opens.',
  marketClosedTrigger:'● MARKET CLOSED — no signal',
  watching:'◇ WATCHING', armedText:(dir)=>'⚡ ORDER TRIGGERED · '+dir+' · ',
  netlik:' CERTAINTY', esik:' / ', mutabakat:' threshold · ', mutabakatSuffix:' agreement',
  confidenceSuffix:'% CONFIDENCE · ', indicatorAgree:' indicators agree',
  confirmedTrade:'⚡ CONFIRMED TRADE · ', watchingThreshold:'◇ WATCHING — Order threshold %',
  targetProjection:(amt)=>'If target is reached ≈ $'+amt+' @ 2.5 lots (projection, not guaranteed)',
  megaAlertBody:(dir,l,en,st,tp,amt)=>'Entry '+en+' · Stop '+st+' · Target '+tp+' · If target is reached ≈ $'+amt+' @ 2.5 lots (15-30M) — this is not a guarantee, it is a projection if TP is reached.',
  winBuilding:(n)=>'Historical signal tracking: gathering data ('+n+' resolved trades) — a reliable figure needs at least a few dozen.',
  winResult:(n,w,r)=>'Real tracking: <b>'+w+'</b> of the last '+n+' signals won → <b>'+r+'%</b> realized win rate (computed from this terminal\'s own signal history, not a claimed target).',
  aggConfirmNone:'3-CANDLE CONFIRM: None', aggConfirmYes:(dir)=>'3-CANDLE CONFIRM: '+dir+' · Strong confirmation',
  exportSuccess:null, importSuccess:'Signal history imported.', importFail:'Could not read file — make sure it is a valid Valens backup file.',
  newsApiMissing:'Live news requires a free Finnhub API key (finnhub.io/register, ~1 min, no card needed) — add it as <code>FINNHUB_API_KEY</code> in Streamlit secrets and this panel fills automatically. No made-up news is shown without a key.',
  newsTierGated:'Your key is valid (it works on other endpoints) but this economic calendar feature is gated behind Finnhub\'s PAID plan — the free tier does not include it. Filling this panel automatically would need a paid Finnhub plan (or another paid calendar API). In the meantime, the "ECONOMIC CALENDAR" section below already shows a real, free, live TradingView widget — check there for current news.',
  manualNewsHint:'Enter the 3-star news from the TradingView calendar here — scenario commentary is generated automatically.',
  manualNewsAdd:'+ ADD', manualNewsClear:'Clear',
  manualNewsEmpty:'No news added yet. Check the TradingView calendar and add today\'s 3-star events using the form above — the system will generate scenarios automatically.',
  manualNewsNeedName:'Please enter the event name first.',
  manualNewsRemove:'Remove', manualClearConfirm:'Remove all manually added news?',
  cotLong:'Long', cotShort:'Short', cotSourceNote:'Source: CFTC Legacy COT · each Tuesday cut is published Friday.',
  tightTpWarning:(pct)=>'⚠ Tight-target / wide-stop shape (matching the ratio observed in the video source): target is smaller than stop, so breakeven requires at least '+pct+'% real win rate. Even with a high-looking win rate, losses are bigger than wins — weigh this carefully.',
  stratLive_title:'📊 REAL STRATEGY PERFORMANCE (live tracked)', stratLiveBadge:(n)=>n+' trades',
  stratLiveHint:'From this terminal\'s own REAL signals that reached TP or SL — which strategy actually won/lost here is remembered permanently. Not shown until at least 3 trades accumulate.',
  stratLiveEmpty:'No resolved signals yet — this fills in starting from the first signal that hits TP or SL.',
  newsNoEvents:'No medium/high-impact scheduled news found for the coming days.', newsNoTemplate:'No ready-made scenario template for this data type — evaluate the raw numbers yourself.',
  newsSame:'Result matched expectations — no clear directional signal.',
  newsBeat:'beat', newsMiss:'missed', newsHigh:'HIGH', newsMed:'MEDIUM',
  ccyStrengthens:'strengthens', ccyWeakens:'weakens',
  xauPressureNote:' General tendency for XAU/USD: pressure (USD strong).', xauSupportNote:' General tendency for XAU/USD: support (USD weak).',
  xauPressureScenario:' → typically pressures XAU/USD.', xauSupportScenario:' → typically supports XAU/USD.',
  newsCountBadge:n=>n+' NEWS', defaultEventName:'Economic Data',
  ruleNfp:'Employment data', ruleUnrate:'Unemployment rate', ruleClaims:'Jobless claims', ruleCpi:'Inflation (CPI)',
  ruleJolts:'JOLTS Job Openings', ruleAdp:'ADP Employment Change', ruleChallenger:'Challenger Job Cuts',
  employmentFamilyNote:'📌 This is one of the broader "employment family" releases — JOLTS (job openings), ADP, NFP (payrolls), Jobless Claims, and the Unemployment Rate are all related and typically release a few days apart (e.g. JOLTS → Jobless Claims a few days later → NFP on the first Friday of the month). Markets tend to read these as a CUMULATIVE picture of labor-market strength/weakness rather than judging any single release in isolation — several consecutive weak/strong prints carry more weight than one data point.',
  ruleGdp:'GDP', ruleRetail:'Retail sales', rulePmi:'PMI', ruleRate:'Rate decision', ruleTrade:'Trade balance',
  noLiveFeedTitle:'● NO LIVE DATA', noLiveFeedDesc:'No Binance feed for this instrument — a TwelveData/OANDA API is required', noLiveShort:'no live data',
  goldOffsetLine:(sign,val)=>'PAXG proxy vs real spot gold gap: '+sign+val+'$ (the ticker price and entry/stop/target numbers are auto-corrected for this gap; only the on-chart candles/S-R lines stay on the raw PAXG axis)',
  tickerEconFallback:'See the right panel for the economic calendar.', tickerDisclaimer:'Institutional flow and news data require verification.',
  tickerNextEvent:(country,name,time)=>country+' '+name+' — '+time,
  zoneTop:'Zone Top', zoneBottom:'Zone Bottom', srNearZone:'near consolidation/volume zone',
  fvgTop:'FVG Top', fvgBottom:'FVG Bottom', fvgCE:'FVG 50% (CE)', fvgEntry:'FVG Entry',
  mainResistance:'Main Resistance (1H)', mainSupport:'Main Support (1H)', srNearMainSupport:'near main support (1H)', srNearMainResistance:'near main resistance (1H)',
  mainResistanceBroken:'Old Resistance (broken → possible support)', mainSupportBroken:'Old Support (broken → possible resistance)',
  tagEmaCross:'EMA Momentum Cross (9/21 + MACD/RSI)', tagOrb:'Opening Range Breakout (ORB)', tagMomentum:'Consecutive-Candle Momentum Breakout',
  tagLiquiditySweep:'Liquidity Sweep Reversal (200 EMA + VWAP Rejection)',
  tagRsiDivergence:'RSI Divergence', tagBollSqueeze:'Bollinger Squeeze Breakout',
  tagEmaPullback:'EMA21 Pullback (Trend Continuation)', tagInsideBar:'Inside Bar Breakout',
  tagFvgRetest:'Fair Value Gap Retest (ICT)', tagObFvgConfluence:'Order Block + FVG Confluence (SMC)', tagIfvg:'Inverse Fair Value Gap (ICT)', tagAmdCycle:'AMD Cycle (Accumulation-Manipulation-Distribution)',
  tagValuationZone:'Valuation Extreme + Zone Confluence', tagMacdZeroCross:'MACD Zero-Line Cross',
  tagScalpOrb:'ORB Scalp Variant (tight range)', tagNoWickRetest:'No Wick (Marubozu) Retest',
  tagOrbSweepFade:'ORB Sweep-and-Reclaim Fade', tagBosSignal:'Market Structure: BOS (Continuation)',
  tagChochSignal:'Market Structure: CHoCH (Change of Character)', tagEqualHighsLows:'Equal Highs/Lows (EQH/EQL) Liquidity Grab',
  tagTradeDelta:'Trades Delta (Real Buy/Sell Volume Imbalance)',
  tagSilverBullet:'Silver Bullet (Liquidity Sweep + FVG)', tagOrbVolume:'ORB + Volume Confirmation',
  tagVwapPullback:'VWAP Pullback + Reversal Candle', tagTtmSqueeze:'TTM Squeeze (Bollinger/Keltner)',
  tagDivergenceChoch:'RSI Divergence + CHoCH', tagPocBounce:'Volume Profile POC Bounce',
  tagOrderBlockMit:'Order Block Mitigation', tagFibOte:'Fibonacci OTE (Optimal Trade Entry)',
  tagAsianFakeout:'Asian Range Killzone Fakeout', tagExtremeMR:'Extreme Mean Reversion (3-Sigma)',
  tagLevelConfluence:'Prior-Day Level Confluence (POC/VAH/VAL)', tagDeltaConfirmTrend:'Delta Confirmation (Funded Move)',
  tagDeltaAbsorption:'Delta Absorption (Exhaustion/Possible Reversal)',
  candidateConfluence:'Multi-Indicator Confluence (15 classic indicators)',
  winningCandidateLine:(label,conf)=>'Strongest candidate: <b>'+label+'</b> ('+conf+'% confidence)',
  noCandidateLine:'No strategy or indicator confluence is giving a clear signal right now.',
  catUp:'UP', catDown:'DOWN', catNeutral:'NEUTRAL', catNoData:'no active signal',
  catFull:'FULLY SUPPORTS', catNone:'OPPOSES', catPartial:'PARTIALLY SUPPORTS',
  catIndicators:'📊 INDICATORS', catActiveOf:'active of', catStrategies:'📐 STRATEGIES',
  catNoStrategies:'No strategy pattern is firing right now', catChart:'📈 CHART READING (trend + S/R + Fib)',
  catCandle:'🕯️ CANDLE CHART (pattern)', catNoPattern:'No clear candlestick pattern',
  catFullAlignment:'FULL ALIGNMENT — indicators, strategies, candle, and chart reading all point the SAME WAY. This is the system\'s highest-confidence state.',
  fullAlignmentTitle:'🎯 FULL ALIGNMENT — CERTAIN TRADE',
  fullAlignmentBody:(dir,label,conf)=>'All categories (indicators + strategies + candle + chart reading) aligned '+dir+' · '+label+' · '+conf+'% confidence — one of the system\'s clearest moments, still not a guarantee.',
  catVerdict:'FINAL VERDICT', catConfidence:'confidence', catNoVerdictYet:'no clear verdict yet',
  strategyTagPrefix:'📐 Strategy patterns that contributed to this call: ',
  rateDecisionNote:"⚠ For rate decisions, simple \"beat/miss forecast\" logic can be misleading: the market has usually already priced in the odds of the decision (e.g. CME FedWatch probabilities). What actually moves price is typically: (1) whether the outcome matches the priced-in PROBABILITY — even an expected 'hold' can trigger a relief rally if it removes a priced-in hike risk, (2) the committee's dissent/vote split (hawkish vs dovish), (3) the tone of the statement and press conference. None of this can be read automatically from the actual/forecast numbers alone — so we deliberately do NOT generate a directional call here, just this note.",
  newsExpectLbl:'Forecast', newsPrevLbl:'Previous', newsActualLbl:'Actual',
  newsCcyResult:(dir,ccy,label,beatTxt,dirTxt,extra)=>'<b>'+dir+' '+ccy+':</b> '+label+' '+beatTxt+' forecast → typically '+dirTxt+' '+ccy+'.'+extra,
  newsScenarioBeat:(label,ccy,extra)=>'<b>▲ IF ABOVE FORECAST:</b> if '+label+' comes in strong, '+ccy+' typically strengthens'+extra,
  newsScenarioMiss:(label,ccy,extra)=>'<b>▼ IF BELOW FORECAST:</b> if '+label+' comes in weak, '+ccy+' typically weakens'+extra,
  newsBeatUp:'beat forecast', newsBeatDown:'missed forecast', newsLive:'(from today\'s real data — ', newsManual:' (manual)',
  newsData:'News',
  cotNoData:'No COT data for this instrument (CFTC only reports futures markets).',
  cotHedgeFunds:'HEDGE FUNDS (Speculators)', cotBanks:'BANKS / COMMERCIALS', cotNetLong:'NET LONG', cotNetShort:'NET SHORT',
  cotLong:'Long', cotShort:'Short', cotSourceNote:'Source: CFTC Legacy COT · each Tuesday cut is published Friday.',
  cotWeeklyNote:'Updates weekly — this is normal.',
  cotStaleWarning:(days)=>'This data has been unchanged for '+days+' days — may be older than expected, check the CFTC source.',
  psarUpLbl:'▲ UP', psarDownLbl:'▼ DOWN', trendUp:'uptrend', trendDown:'downtrend', trendFlat:'sideways',
  srNearSupport:l=>'near support ('+l+')', srNearResistance:l=>'near resistance ('+l+')',
  srNearDynSupport:'near dynamic support (Dyn Support)', srNearDynResistance:'near dynamic resistance (Dyn Resistance)',
  confluenceSuffix:' + Fib level confluence',
  conflictWarning:'⚠ MIXED SIGNAL: another strategy/analysis is giving a strong signal in the OPPOSITE direction from the winning candidate. We still show the best option, but opinion is split here — be careful.',
  conflictBadge:'⚠ MIXED SIGNAL — possible reversal zone',
  noLastSignal:'No signal has been given at this level yet.',
  lastSignalLine:(dir,entry,tp,time)=>'Last signal: <b>'+dir+'</b> · Entry '+entry+' → TP '+tp+' · '+time,
  risk_governor_title:'🛡 CHALLENGE RISK GOVERNOR', risk_balance:'Balance ($)', risk_daily:'Daily Loss Limit (%)',
  gaugeTrend:'TREND', gaugeCandle:'CANDLE', gaugeNews:'NEWS',
  signal_api_title:'☁️ CENTRAL SIGNAL LOG (24/7 server)',
  signalApiHint:'If the terminal is running 24/7 on a server, every signal is also recorded here — you see the SAME history no matter which device/browser you log in from. Nothing changes while disconnected — signals keep being tracked in this browser (localStorage) only.',
  signalApiToggleOff:'☁️ Connect', signalApiToggleOn:'⏸ Disconnect',
  signalApiConnecting:'Connecting…', signalApiConnected:'✓ Connected — signals are being recorded centrally.',
  signalApiInvalidCode:'✗ Early access code is wrong.', signalApiUnreachable:'✗ Could not reach the server — check the address.',
  signalApiNoUrl:'Enter the server address first.',
  signalApiStatsTitle:'📊 Central Strategy Performance (all devices)',
  signalApiStatsLine:(label,trades,winRate)=>label+': '+trades+' trades · '+winRate+'% win rate',
  signalApiStatsEmpty:'No resolved signals yet.',
  mt5_bridge_title:'🔌 MT5 BRIDGE (manual confirm)',
  mt5BridgeHint:"If valens_mt5_executor.py is running on your other PC, connect here. No auto-send — every CONFIRMED TRADE shows a Send button here, nothing reaches MT5 until you approve it.",
  mt5BridgeToggleOff:'🔌 Connect', mt5BridgeToggleOn:'⏸ Disconnect',
  mt5BridgeBadgeOn:'CONNECTED', mt5BridgeBadgeOff:'NOT CONNECTED',
  mt5BridgeNoUrl:'⚠ Enter the bridge address first (e.g. http://192.168.1.23:8899).',
  mt5BridgeConnectedNote:'Connected to bridge — the send button will activate when a CONFIRMED TRADE fires.',
  mt5BridgeStoppedNote:'Disconnected.',
  mt5BridgeUnreachable:"⚠ Can't reach the bridge — check the address, network, and that valens_mt5_executor.py is running (an https page reaching a plain http bridge may be blocked by the browser).",
  mt5BridgeExecuted:'✓ Sent, trade opened in MT5.',
  mt5BridgeSkipped:(reason)=>'Reached the bridge but no trade was opened (reason: '+reason+').',
  mt5LotLabel:'Lot to send', mt5SendBtnLabel:'⚡ Send This Signal to MT5 (Confirm)', mt5SendBtnSending:'Sending…', mt5SendBtnSent:'✓ Sent (for this signal)',
  mt5CandleLimitReached:'⏸ Send limit reached for this candle/direction (2) — waiting for a new candle.', mt5CandleLimitBtn:'⏸ Per-Candle Limit Reached (2/2)',
  mt5AutoSendLabel:'🤖 Auto-Send — DEMO accounts ONLY (sends without waiting for approval)',
  mt5AutoMinConfLabel:'Min. confidence (%)',
  mt5AutoSendWarn:"⚠ While this is checked, EVERY trade is sent to the real MT5 account without waiting for approval. Only use this on a demo/test account — keep it OFF with real money.",
  scalpMode_title:'⚡ 1M SCALP MODE',
  scalpModeHint:'Switches the chart to 1-minute — all strategies keep scanning normally, but the higher-timeframe (4H/1H) structure is also factored in: signals aligned with it get a confidence boost ("How to Analysis": higher timeframe gives direction, lower gives confirmation). Turning it off restores the previous timeframe.',
  scalpModeToggleOff:'⚡ Turn On 1M Scalp Mode', scalpModeToggleOn:'⏸ Turn Off 1M Scalp Mode',
  scalpModeBadgeOn:'ON', scalpModeBadgeOff:'OFF',
  scalpBiasUp:'Bullish', scalpBiasDown:'Bearish', scalpBiasFlat:'Unclear',
  scalpBiasLine:(h4,h1)=>'4H: <b>'+h4+'</b> · 1H: <b>'+h1+'</b>',
  scalpBiasOnlySide:(side)=>'— '+side+' signals are boosted (+10%)',
  scalpBiasNoConsensus:'— 4H/1H disagree, scanning continues normally (no bonus/penalty)',
  confSourceBacktest:'Confidence adjusted using historical backtest results',
  regimePrefix:'📍 Market Regime:', regimeTrendUp:'Strong Uptrend', regimeTrendDown:'Strong Downtrend',
  regimeTrendFlat:'Strong Trend (directionless)', regimeRanging:'Ranging/Sideways', regimeUnclear:'Unclear/Transitional',
  regimeBonus:'This strategy FITS the current market regime — confidence increased', regimePenalty:'This strategy does NOT fit the current market regime — confidence decreased',
  structurePrefix:'📐 Structure:', structureUp:'Bullish (HH/HL)', structureDown:'Bearish (LH/LL)',
  structureBrokenUp:'Bullish — break (BOS) ▲', structureBrokenDown:'Bearish — break (BOS) ▼', structureUnclear:'Unclear',
  structureBonus:'This strategy FITS the real swing structure (BOS) — confidence increased', structurePenalty:'This strategy goes AGAINST the real swing structure (BOS) — confidence decreased',
  exhaustionPrefix:'🕯️ Exhaustion:', exhaustionTop:'Rejection cluster at top', exhaustionTopStrong:'STRONG rejection cluster at top ▼',
  exhaustionBottom:'Rejection cluster at bottom', exhaustionBottomStrong:'STRONG rejection cluster at bottom ▲', exhaustionNone:'None',
  exhaustionBonus:'This strategy MATCHES the top/bottom rejection cluster — confidence increased', exhaustionPenalty:'This strategy expects continuation in an exhausted direction — confidence decreased',
  backtest_title:'🔬 HISTORICAL BACKTEST',
  backtestHint:'Looks at the ~300 REAL past candles on this chart and checks, for every point in the past where each strategy actually fired, whether price reached TP or SL first. This is NOT a random/possible-future projection.',
  backtestNotEnoughData:'Not enough historical data yet (needs at least ~350 candles).',
  backtestNoSignals:'No strategy fired at least 3 times in these ~300 candles.',
  backtestCandleCount:(n)=>'last '+n+' candles',
  risk_max:'Max Total Loss (%)', risk_target:'Profit Target (%)',
  risk_lotmin:'Lot (min)', risk_lotmax:'Lot (max)', risk_days:'Target Days', risk_start:'Start Date',
  goal_progress_title:'🎯 PROGRESS TO TARGET (from real tracked results)',
  goalDetailLine:(net,target,pctDone,daysLeft,paceNeeded,paceActual)=>
    'Tracked net: <b>'+net+'</b> / $'+target+' target ('+pctDone+'%). Remaining: <b>'+daysLeft+' days</b>. '+
    'Reaching the target needs an average of <b>'+paceNeeded+'</b>/day — your actual tracked pace so far: <b>'+paceActual+'</b>/day. '+
    'This is an estimate — actual lot size isn\'t logged per trade, so it uses the average of your lot range ('+t('avgLotNote')+'); not a guarantee.',
  avgLotNote:'the average of your lot range',
  trade_log_title:'📒 SIGNAL P&L TRACKING', tradeLogConfirmCandles:'candle confirmation',
  tradeLogBadge:(n)=>n+' TRADES',
  tradeLogSummaryLine:(total,wins,losses,net)=>total+' trades tracked · <span style="color:var(--green)">'+wins+' won</span> / <span style="color:var(--red)">'+losses+' lost</span> · Net: <b>'+net+'</b> (estimated using average lot)',
  tradeLogEmpty:'No signal has resolved yet — trades will appear here once TP or SL is reached.',
  tradeLogWin:'✓', tradeLogLoss:'✗',
  sessClosesIn:(label,time)=>label+' session closes in: '+time,
  sessOpensIn:(label,time)=>label+' session opens in: '+time,
  sessNoneActive:'No major session is currently active (low liquidity) — spreads may widen.',
  sessHighActivity:(list)=>'Typically most liquid this session: '+list,
  sessLowActivity:'Relatively low activity expected in our tracked instruments this session.',
  proxyStillMoving:(label)=>'⚠ The real '+label+' market is closed (weekend/off-session) — this chart comes from a 24/7 crypto proxy, so it keeps moving. No signal is being produced.',
  riskSummaryLine:(daily,max,target)=>'Daily limit: <b>$'+daily+'</b> · Max loss: <b>$'+max+'</b> · Target: <b>$'+target+'</b>',
  riskOkBadge:'SAFE', riskWarnBadge:'CAUTION', riskBlockBadge:'STOP',
  riskOkDetail:(pnl)=>"Today's tracked net: "+(pnl>=0?'+':'')+'$'+pnl+' — within limit.',
  riskWarnDetail:(pnl,pct)=>"⚠ Today's loss has reached "+pct+'% of the daily limit ($'+pnl+') — be careful.',
  riskBlockDetail:(pnl)=>"🛑 Today's loss has crossed the safety threshold ($"+pnl+') — no new trades are being armed. Resets tomorrow.',
  riskBlockedStatus:'🛑 DAILY RISK LIMIT — new signals paused',
  cooldownStatus:(min)=>'⏸ POST-STOP COOLDOWN — opposite direction held for '+min+' more min (whipsaw guard)',
  cooldownWhyNote:(min)=>' <span style="color:#ffb27a">⏸ This direction just got STOPPED OUT — to avoid a false reversal, no new CONFIRMED TRADE this direction for '+min+' more min (continuing the same direction is still allowed).</span>',
  confirmStatus:(have,need,dir)=>'🕐 WAITING FOR CANDLE-CLOSE CONFIRMATION — '+dir+' · '+have+'/'+need+' candles',
  confirmWhyNote:(have,need)=>' <span style="color:var(--blue)">🕐 This signal is only confirmed by '+have+'/'+need+' candle(s) so far — once this candle closes and the NEXT one still agrees, it becomes a CONFIRMED TRADE (a single candle\'s first reading alone is not enough, to guard against noise).</span>',
  anText: p => (p.totalVotes>0 ? ('The bot combines '+p.totalVotes+' real inputs (indicators + chart patterns + 8 named strategies + news) for '+p.label+' live from <b>real Binance OHLC data</b> into a single score.') : ('The bot cannot find a clear direction for '+p.label+' right now — indicators/strategies conflict or none are decisive (see the category breakdown below).')) + ' RSI <b>'+p.rsi+'</b>, MACD '+(p.macdPos?'positive':'negative')+
   ', EMA 50/'+(p.emaGolden?'above 200':'below 200')+', ATR <b>'+p.atr+'</b> (volatility), price is '+(p.vwapAbove?'above':'below')+' VWAP'+
   ', Williams %R <b>'+p.williamsR+'</b>, CCI <b>'+p.cci+'</b>, Parabolic SAR pointing '+(p.psarUp?'up':'down')+'. '+
   'Chart: '+(p.trend>0?'uptrend':p.trend<0?'downtrend':'sideways')+
   (p.patternName?' · '+p.patternName:'')+ (p.srText?' · '+p.srText:'')+
   '. News direction'+(p.newsLive?' (from today\'s real data — '+p.newsDetail+')':' (manual)')+': '+(p.newsBias>0?'▲ positive':p.newsBias<0?'▼ negative':'neutral')+
   '. Combined: <b style="color:'+p.sigColor+'">'+p.sigText+'</b> — confidence %'+p.conf+' · '+p.agreeCount+'/'+p.totalVotes+' indicators aligned.',
  confSuffixLine:(conf,agree,total)=>conf+'% CONFIDENCE · '+agree+'/'+total+' indicators agree',
  armedTrigger:(dir,conf)=>'⚡ ORDER TRIGGERED · '+dir+' · %'+conf+' CERTAINTY',
  waitTrigger:(conf,thr,agree,total)=>'◇ WATCHING · %'+conf+' / %'+thr+' threshold · '+agree+'/'+total+' agreement',
  confirmedStatus:(dir,conf,time)=>'⚡ CONFIRMED TRADE · '+dir+' · %'+conf+' · '+time,
  waitStatus:(thr,conf)=>'◇ WATCHING — Order threshold %'+thr+' · %'+conf,
  targetHit:(amt)=>'If target is reached ≈ $'+amt+' @ 2.5 lots (projection, not guaranteed)',
  targetHitRange:(min,max,lotMin,lotMax)=>'If target is reached ≈ $'+min+'–$'+max+' @ '+lotMin+'-'+lotMax+' lots (projection, not guaranteed)',
  megaAlertTitleDyn:(dir,label)=>'🚨 HIGH-POTENTIAL SCALP · '+dir+' · '+label,
  megaAlertBodyDyn:(en,st,tp,amt)=>'Entry '+en+' · Stop '+st+' · Target '+tp+' · If target is reached ≈ $'+amt+' @ 2.5 lots (15-30M) — this is not a guarantee, it is a projection if TP is reached.',
  megaAlertBodyRange:(en,st,tp,min,max,lotMin,lotMax)=>'Entry '+en+' · Stop '+st+' · Target '+tp+' · If target is reached ≈ $'+min+'–$'+max+' @ '+lotMin+'-'+lotMax+' lots (15-30M) — this is not a guarantee, it is a projection if TP is reached.',
 }
};
function t(key){ const v=(I18N[LANG]&&I18N[LANG][key]); return v!==undefined? v : I18N.tr[key]; }
function applyStaticI18N(){
 document.querySelectorAll('[data-i18n]').forEach(el=>{ el.textContent=t(el.getAttribute('data-i18n')); });
 document.querySelectorAll('[data-i18n-opt]').forEach(el=>{ el.textContent=t(el.getAttribute('data-i18n-opt')); });
 document.documentElement.lang=LANG;
 const btn=document.getElementById('langToggle'); if(btn) btn.textContent = LANG==='tr'?'EN':'TR';
}
function setDates(){
 const n=new Date(), M=MONTHS[LANG]||MONTHS.tr;
 document.getElementById('calDate').textContent=n.getDate()+' '+M[n.getMonth()]+' '+n.getFullYear();
 document.getElementById('macroDate').textContent=n.getDate()+' '+M[n.getMonth()].toUpperCase();
}
function clock(){const n=new Date();document.getElementById('clock').textContent=n.toUTCString().slice(17,25);}
clock();setInterval(clock,1000);
applyStaticI18N(); setDates();

// ============ FOREX SEANS SAATİ + GERİ SAYIM ============
// Standart UTC seans saatleri (yıl boyunca sabit — DST karışıklığını önlemek için UTC kullanılır,
// bazı seanslar DST'de ~1 saat kayabilir, bu yaklaşık/endüstri-standart değerlerdir).
const SESSIONS=[
 {key:'sydney', label:'Sydney', start:22, end:7},
 {key:'tokyo', label:'Tokyo', start:0, end:9},
 {key:'london', label:'London', start:8, end:17},
 {key:'newyork', label:'New York', start:13, end:22},
];
// Hangi seansta hangi takip ettiğimiz enstrüman genellikle daha likit/aktif olur (genel piyasa bilgisi).
const SESSION_ACTIVITY={
 sydney:   {'OANDA:XAUUSD':0, 'BINANCE:BTCUSDT':1, 'OANDA:EURUSD':0, 'OANDA:SPX500USD':0},
 tokyo:    {'OANDA:XAUUSD':1, 'BINANCE:BTCUSDT':1, 'OANDA:EURUSD':0, 'OANDA:SPX500USD':0},
 london:   {'OANDA:XAUUSD':2, 'BINANCE:BTCUSDT':1, 'OANDA:EURUSD':2, 'OANDA:SPX500USD':0},
 newyork:  {'OANDA:XAUUSD':2, 'BINANCE:BTCUSDT':2, 'OANDA:EURUSD':2, 'OANDA:SPX500USD':2},
};
function inSession(h,start,end){ return start<end ? (h>=start&&h<end) : (h>=start||h<end); }
function hoursUntil(nowH,targetH){ let d=targetH-nowH; while(d<=0)d+=24; return d; }
function getSessionState(){
 const n=new Date(), h=n.getUTCHours()+n.getUTCMinutes()/60+n.getUTCSeconds()/3600;
 const active=SESSIONS.filter(s=>inSession(h,s.start,s.end));
 let events=[];
 SESSIONS.forEach(s=>{ events.push({h:s.start,type:'start',s}); events.push({h:s.end,type:'end',s}); });
 events.forEach(e=>e.until=hoursUntil(h,e.h));
 events.sort((a,b)=>a.until-b.until);
 return {active, next:events[0]};
}
function fmtHM(hoursFloat){ const totalMin=Math.round(hoursFloat*60); return Math.floor(totalMin/60)+'s '+(totalMin%60)+'dk'; }
function updateSessionBar(){
 const st=getSessionState();
 SESSIONS.forEach(s=>{
  const el=document.getElementById('pill'+s.key.charAt(0).toUpperCase()+s.key.slice(1));
  if(el) el.classList.toggle('on', st.active.some(a=>a.key===s.key));
 });
 const cdEl=document.getElementById('sessCountdown');
 if(cdEl){
  const label=st.next.s.label;
  cdEl.textContent = (st.next.type==='end'? t('sessClosesIn') : t('sessOpensIn'))(label, fmtHM(st.next.until));
 }
 const noteEl=document.getElementById('sessNote');
 if(noteEl){
  if(CUR!=='BINANCE:BTCUSDT' && typeof isMarketOpen==='function' && !isMarketOpen(CUR)){
   const label=(typeof SYMS!=='undefined' && SYMS[CUR])?SYMS[CUR].label:CUR;
   noteEl.innerHTML='<span style="color:var(--red)">'+t('proxyStillMoving')(label)+'</span>';
  } else if(!st.active.length){ noteEl.textContent=t('sessNoneActive'); }
  else{
   const scores={}; Object.keys(SYMS).forEach(sym=>{ scores[sym]=Math.max(...st.active.map(a=>(SESSION_ACTIVITY[a.key]||{})[sym]||0)); });
   const high=Object.keys(scores).filter(sym=>scores[sym]>=2).map(sym=>SYMS[sym].label);
   noteEl.textContent = high.length ? t('sessHighActivity')(high.join(', ')) : t('sessLowActivity');
  }
 }
}

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
updateSessionBar(); setInterval(updateSessionBar,1000); // CUR/SYMS tanımlandıktan SONRA çağrılmalı

// O günkü önemli haber yönü — SADECE gerçek canlı veri (Finnhub) ya da manuel panel girdisi yoksa
// devreye giren yedek değerdir. Nötr (0) bırakılır: rastgele tahmin edilmiş bir yön, en yüksek ağırlıklı
// (1.0) oy olarak sessizce her sinyale sızmasın diye kasıtlı olarak sabit bir yön VERİLMEZ.
const NEWS_BIAS={
 'OANDA:XAUUSD': 0,
 'BINANCE:BTCUSDT': 0,
 'OANDA:EURUSD': 0,
 'OANDA:SPX500USD': 0
};
// Grafik motorunun canlı okuması buraya yazılır (trend/pattern/S-R/fib + gerçek indikatörler)
window.valensChartRead={};
window.valensCandleLock=null; // mum kilidi/devamlılık mekanizması için başlangıç durumu

function isMarketOpen(sym, atUnixSeconds){
 if(sym==='BINANCE:BTCUSDT')return true;
 const d=atUnixSeconds!=null ? new Date(atUnixSeconds*1000) : new Date();
 const day=d.getUTCDay(),h=d.getUTCHours();
 if(sym==='OANDA:SPX500USD'){
   if(day===0||day===6)return false;
   const m=h*60+d.getUTCMinutes(); return m>=870 && m<=1260;
 }
 if(day===6)return false;
 if(day===0 && h<22)return false;
 if(day===5 && h>=22)return false;
 return true;
}
window.valensIsMarketOpen = isMarketOpen; // grafik motoru (ayrı script) geçmiş mumları kontrol edebilsin diye
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
  if(conf){detail.innerHTML=t('aggConfirmYes')(conf>0?'▲ BUY':'▼ SELL');detail.style.color=conf>0?'var(--green)':'var(--red)';}
  else{detail.innerHTML=t('aggConfirmNone');detail.style.color='var(--muted)';}
}

// ============ GERÇEK SİNYAL BAŞARI TAKİBİ ============
// Burada hiçbir "%80-90 doğruluk" gibi sabit/iddia edilen rakam YOKTUR.
// Her "armed" sinyal gerçek giriş/TP/SL fiyatlarıyla kaydedilir; sonraki tick'lerde
// gerçek fiyat TP'ye mi SL'ye mi önce ulaşmış buna bakılır ve kazanma oranı BUNDAN hesaplanır.
const TRADE_STORE_PREFIX='valens_trades_';
function getTradeKey(sym){return TRADE_STORE_PREFIX+sym.replace(/[:\/]/g,'_');}
function loadTradeStore(sym){try{const raw=localStorage.getItem(getTradeKey(sym));if(!raw)return{trades:[]};return JSON.parse(raw);}catch(e){return{trades:[]};}}
function saveTradeStore(sym,store){try{localStorage.setItem(getTradeKey(sym),JSON.stringify(store));}catch(e){}}
function logArmedTrade(sym,dir,entry,tp,sl,stratKey,stratLabel,context,candleTime){
  const store=loadTradeStore(sym);
  store.trades=store.trades||[];
  const openTrade=store.trades.find(t=>!t.resolved);
  if(openTrade)return; // aynı anda tek açık takip — üst üste her tick'te yeni kayıt açılmaz
  // candleTime: chart.timeScale().timeToCoordinate() SADECE grafikte GERÇEKTEN çizili bir mumun
  // TAM zaman değerini kabul ediyor (Date.now() gibi rastgele bir saniye DEĞİL — test edip
  // doğruladım, aradaki fark 1dk'dan bile az olsa null dönüyor) — 1M Scalp Modu kutu çizimi bu
  // yüzden ts (Date.now()) değil, cr.candleTime'dan gelen bu alanı kullanıyor.
  const trade={ts:Date.now(),dir,entry,tp,sl,resolved:false,outcome:null,stratKey:stratKey||null,stratLabel:stratLabel||null,context:context||null,candleTime:candleTime||null};
  store.trades.push(trade);
  if(store.trades.length>500)store.trades=store.trades.slice(-500);
  saveTradeStore(sym,store);
  // 7/24 sunucudaki merkezi sinyal API'sine bağlıysa buraya da kaydedilir (bkz. pushSignalToApi
  // aşağıda) — bağlı değilken bu no-op'tur, localStorage davranışı hiç değişmez.
  pushSignalToApi(sym, trade.ts, {sym, dir, entry, tp, sl, stratKey:stratKey||null, stratLabel:stratLabel||null, context:context||null, ts:trade.ts});
}
// ---- İşlem anındaki GERÇEK gerekçeyi (rejim, kaç indikatör destekledi, S/R/mum durumu, kaç mum
// onayladı) okunaklı bir cümleye çevirir — kullanıcı isteği: "hangi strateji, hangi şartlar altında
// çalıştı, ilerde bilelim" diye kalıcı olarak trade log'a yazılır (sadece o an ekranda görünüp
// kaybolmasın diye).
function describeTradeContext(ctx){
  if(!ctx) return '';
  const regimeLabel = ctx.regime==='trendUp'?t('regimeTrendUp'):ctx.regime==='trendDown'?t('regimeTrendDown'):ctx.regime==='ranging'?t('regimeRanging'):ctx.regime==='trendFlat'?t('regimeTrendFlat'):t('regimeUnclear');
  const parts=[t('regimePrefix')+' '+regimeLabel];
  parts.push(t('catIndicators')+' '+ctx.agreeCount+'/'+ctx.totalVotes);
  if(ctx.trend) parts.push(ctx.trend>0?t('trendUp'):t('trendDown'));
  if(ctx.srText) parts.push(ctx.srText);
  if(ctx.patternName) parts.push(ctx.patternName);
  parts.push(ctx.confirmedCandles+' '+t('tradeLogConfirmCandles'));
  return parts.join(' · ');
}
// ============ STOP SONRASI SOĞUMA (whipsaw koruması) ============
// Kullanıcı geri bildirimi (gerçek örnek): %97 güvenli BUY stop oldu, hemen ardından %74 güvenli
// SELL arm oldu — SL'e takılıp aynı anda TERS yöne dönmek klasik bir "whipsaw" (sahte kırılım/
// dönüş) tuzağıdır: SL'i tetikleyen ani hareket, henüz oturmamış bir tepkiyi gerçek trend dönüşü
// gibi gösterebilir. Mum kilidi SADECE aynı mum içindeki titreşimi önlüyordu — yeni mum başladığında
// hiçbir "az önce burada kaybettik" hafızası yoktu. Şimdi bir sembolde STOP olduğunda kaydediliyor;
// botTick bunu okuyup TERS yöndeki yeni KESİN İŞLEM'i bir süre bekletiyor (aynı yönde devam serbest).
function stopCooldownKey(sym){ return 'valens_lastloss_'+sym.replace(/[:\/]/g,'_'); }
function recordStopLoss(sym,dir){
  try{ localStorage.setItem(stopCooldownKey(sym), JSON.stringify({dir,ts:Date.now()})); }catch(e){}
}
function getStopCooldown(sym){
  try{ const raw=localStorage.getItem(stopCooldownKey(sym)); return raw?JSON.parse(raw):null; }catch(e){ return null; }
}
function updateTradeOutcomes(sym,lastPrice){
  const store=loadTradeStore(sym);
  let changed=false;
  (store.trades||[]).forEach(t=>{
    if(t.resolved)return;
    if(t.dir>0){
      if(lastPrice>=t.tp){t.resolved=true;t.outcome='win';changed=true;resolveSignalOnApi(t);}
      else if(lastPrice<=t.sl){t.resolved=true;t.outcome='loss';changed=true;recordStopLoss(sym,t.dir);resolveSignalOnApi(t);}
    }else if(t.dir<0){
      if(lastPrice<=t.tp){t.resolved=true;t.outcome='win';changed=true;resolveSignalOnApi(t);}
      else if(lastPrice>=t.sl){t.resolved=true;t.outcome='loss';changed=true;recordStopLoss(sym,t.dir);resolveSignalOnApi(t);}
    }
    // 1M Scalp Modu kutusu: işlem sonuçlandığında (TP/SL) çizim de silinir — sinyal API'sine
    // bağlı olsun olmasın (resolveSignalOnApi'den bağımsız, o sadece merkezi kayıt içindir).
    if(t.resolved && window.valensScalpModeActive && window.valensClearScalpBox){
      window.valensClearScalpBox(); window.valensScalpBoxEndTime=null;
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
  if(wr.total<5){ el.textContent=t('winBuilding')(wr.total); return; }
  el.innerHTML=t('winResult')(wr.total,wr.wins,wr.rate.toFixed(1));
}

// ============ SON VERİLEN SCALP/SWING SİNYALİ + TARİHİ ============
// "En son bu seviyede bu işlem verildi" bilgisini kalıcı tutar (localStorage), her sembol/plan için ayrı.
function lastSigKey(sym,plan){ return 'valens_lastsig_'+plan+'_'+sym.replace(/[:\/]/g,'_'); }
function recordLastSignal(sym,plan,dir,entry,tp,sl){
  try{ localStorage.setItem(lastSigKey(sym,plan), JSON.stringify({dir,entry,tp,sl,ts:Date.now()})); }catch(e){}
}
function getLastSignal(sym,plan){
  try{ const raw=localStorage.getItem(lastSigKey(sym,plan)); return raw?JSON.parse(raw):null; }catch(e){ return null; }
}
function fmtSigTime(ts){
  const d=new Date(ts), M=MONTHS[LANG]||MONTHS.tr;
  return String(d.getUTCDate()).padStart(2,'0')+' '+M[d.getUTCMonth()].slice(0,3)+' '+String(d.getUTCHours()).padStart(2,'0')+':'+String(d.getUTCMinutes()).padStart(2,'0')+' UTC';
}
function updateLastSignalUI(){
  const cfg=SYMS[CUR];
  const fmt=v=>v.toLocaleString('en-US',{minimumFractionDigits:cfg.dec,maximumFractionDigits:cfg.dec});
  ['scalp','swing'].forEach(plan=>{
    const el=document.getElementById(plan==='scalp'?'scLastSignal':'swLastSignal'); if(!el)return;
    const sig=getLastSignal(CUR,plan);
    if(!sig){ el.textContent=t('noLastSignal'); return; }
    el.innerHTML=t('lastSignalLine')(sig.dir>0?'BUY':'SELL', fmt(sig.entry), fmt(sig.tp), fmtSigTime(sig.ts));
  });
}

// ============ FTMO/PROP FIRM CHALLENGE RİSK YÖNETİCİSİ ============
// Bot'u daha "agresif" yapmak yerine, gerçek izlenen (win/loss) işlem geçmişinden bugünkü net durumu
// hesaplayıp günlük kayıp limitine yaklaşılınca YENİ SİNYAL VERMEYİ DURDURUR. Bu, bir prop firm
// challenge'ında hesabı gerçekten bitiren şeyin "az sinyal" değil "limit ihlali" olması yüzünden var.
const RISK_KEY='valens_risk_settings';
function loadRiskSettings(){
  try{ const raw=localStorage.getItem(RISK_KEY); if(raw) return Object.assign({balance:50000, dailyPct:5, maxPct:10, targetPct:10, lotMin:0.8, lotMax:1.2, challengeDays:10, startDate:new Date().toISOString().slice(0,10)}, JSON.parse(raw)); }catch(e){}
  return {balance:50000, dailyPct:5, maxPct:10, targetPct:10, lotMin:0.8, lotMax:1.2, challengeDays:10, startDate:new Date().toISOString().slice(0,10)};
}
function saveRiskSettings(s){ try{ localStorage.setItem(RISK_KEY, JSON.stringify(s)); }catch(e){} }
function avgLot(){ const s=loadRiskSettings(); return ((parseFloat(s.lotMin)||0.8)+(parseFloat(s.lotMax)||1.2))/2; }
function computeTodayPnL(){
  const todayStr=new Date().toISOString().slice(0,10);
  const lot=avgLot();
  let pnl=0;
  Object.keys(SYMS).forEach(sym=>{
    const store=loadTradeStore(sym), cs=SYMS[sym].contractSize;
    (store.trades||[]).forEach(tr=>{
      if(!tr.resolved) return;
      if(new Date(tr.ts).toISOString().slice(0,10)!==todayStr) return;
      const dist = tr.outcome==='win' ? Math.abs(tr.tp-tr.entry) : -Math.abs(tr.entry-tr.sl);
      pnl += dist*cs*lot;
    });
  });
  return pnl;
}
function computeTotalPnL(){
  const lot=avgLot();
  let pnl=0;
  Object.keys(SYMS).forEach(sym=>{
    const store=loadTradeStore(sym), cs=SYMS[sym].contractSize;
    (store.trades||[]).forEach(tr=>{
      if(!tr.resolved) return;
      const dist = tr.outcome==='win' ? Math.abs(tr.tp-tr.entry) : -Math.abs(tr.entry-tr.sl);
      pnl += dist*cs*lot;
    });
  });
  return pnl;
}
function riskState(){
  const s=loadRiskSettings();
  const dailyLimit=s.balance*(s.dailyPct/100), maxLimit=s.balance*(s.maxPct/100);
  const todayPnl=computeTodayPnL(), totalPnl=computeTotalPnL();
  const todayLossPct = dailyLimit>0 ? Math.max(0,-todayPnl)/dailyLimit*100 : 0;
  const totalLossPct = maxLimit>0 ? Math.max(0,-totalPnl)/maxLimit*100 : 0;
  let level='ok';
  if(todayLossPct>=70 || totalLossPct>=70) level='block';
  else if(todayLossPct>=40 || totalLossPct>=40) level='warn';
  return {s,dailyLimit,maxLimit,todayPnl,totalPnl,todayLossPct,totalLossPct,level};
}
function isRiskBlocked(){ return riskState().level==='block'; }
function updateRiskUI(){
  const r=riskState();
  const bal=r.s.balance;
  document.getElementById('riskSummary').innerHTML = t('riskSummaryLine')(
    Math.round(r.dailyLimit).toLocaleString('en-US'), Math.round(r.maxLimit).toLocaleString('en-US'),
    Math.round(bal*(r.s.targetPct/100)).toLocaleString('en-US'));
  const bar=document.getElementById('riskBar'), badge=document.getElementById('riskBadge'), detail=document.getElementById('riskDetail');
  const pct=Math.min(100,Math.max(r.todayLossPct,r.totalLossPct*0.5));
  bar.style.width=pct+'%';
  bar.style.background = r.level==='block'?'var(--red)':r.level==='warn'?'#ffb27a':'var(--green)';
  badge.textContent = r.level==='block'?t('riskBlockBadge'):r.level==='warn'?t('riskWarnBadge'):t('riskOkBadge');
  badge.style.color = r.level==='block'?'var(--red)':r.level==='warn'?'#ffb27a':'var(--green)';
  const pnlFmt=Math.round(r.todayPnl).toLocaleString('en-US');
  detail.innerHTML = r.level==='block'?t('riskBlockDetail')(pnlFmt):r.level==='warn'?t('riskWarnDetail')(pnlFmt,Math.round(r.todayLossPct)):t('riskOkDetail')(pnlFmt);
  detail.style.color = r.level==='block'?'var(--red)':r.level==='warn'?'#ffb27a':'var(--green)';

  // ---- Hedefe ilerleme (gerçek izlenen sonuçlardan; TAHMİN'dir, garanti değildir) ----
  const targetUsd = bal*(r.s.targetPct/100);
  const trackedNet = computeTotalPnL();
  const pctDone = targetUsd>0 ? Math.max(0,Math.min(100, trackedNet/targetUsd*100)) : 0;
  const start = new Date(r.s.startDate+'T00:00:00Z');
  const totalDays = parseFloat(r.s.challengeDays)||10;
  const elapsedDays = Math.max(0,(Date.now()-start.getTime())/86400000);
  const daysLeft = Math.max(0, Math.ceil(totalDays-elapsedDays));
  const remaining = Math.max(0, targetUsd-trackedNet);
  const paceNeeded = daysLeft>0 ? remaining/daysLeft : remaining;
  const paceActual = elapsedDays>=1 ? trackedNet/elapsedDays : trackedNet;
  document.getElementById('goalBar').style.width = pctDone+'%';
  document.getElementById('goalDetail').innerHTML = t('goalDetailLine')(
    (trackedNet>=0?'+':'')+'$'+Math.round(trackedNet).toLocaleString('en-US'),
    Math.round(targetUsd).toLocaleString('en-US'), pctDone.toFixed(0), daysLeft,
    '$'+Math.round(paceNeeded).toLocaleString('en-US'), (paceActual>=0?'+':'')+'$'+Math.round(paceActual).toLocaleString('en-US')
  );
}

// ============ 1M SCALP MODU ============
// Kullanıcı isteği ("How to Analysis" görseli + 8 SMC eğitim videosu): Challenge Modu'nun yerine
// — üst zaman dilimi (4H/1H) YÖN verir, alt zaman dilimi (1dk) ONAY/giriş verir mantığını
// uygulayan bir mod. Açılınca grafik 1 dakikaya geçer (mevcut .tfbtn/valensSetInterval mekanizması
// üzerinden — YENİDEN YAZILMADI), ama 4H/1H yapı yönüyle ÇELİŞEN sinyaller tamamen devre dışı
// bırakılır (window.valensScalpModeActive + window.valensScalpBias, botTick içinde okunur).
window.valensScalpModeActive=false;
window.valensScalpPrevInterval=null;
function renderScalpBiasLine(){
  const el=document.getElementById('scalpModeBias'); if(!el) return;
  const bias=window.valensScalpBias;
  if(!window.valensScalpModeActive || !bias){ el.style.display='none'; return; }
  el.style.display='block';
  const dirLabel=(d)=> d>0?t('scalpBiasUp'):d<0?t('scalpBiasDown'):t('scalpBiasFlat');
  const aligned = bias.h4Dir!==0 && bias.h4Dir===bias.h1Dir;
  el.innerHTML = t('scalpBiasLine')(dirLabel(bias.h4Dir), dirLabel(bias.h1Dir)) +
    (aligned ? ' <b style="color:var(--gold)">'+t('scalpBiasOnlySide')(bias.h4Dir>0?'BUY':'SELL')+'</b>'
              : ' <span style="color:var(--muted)">'+t('scalpBiasNoConsensus')+'</span>');
}
window.valensRenderScalpBiasLine = renderScalpBiasLine; // fetchScalpBias (chart motoru) tazelendiğinde çağırabilsin
(function wireScalpMode(){
  const toggleBtn=document.getElementById('scalpModeToggle');
  if(!toggleBtn) return;
  toggleBtn.addEventListener('click', ()=>{
    const badge=document.getElementById('scalpModeBadge');
    if(!window.valensScalpModeActive){
      // ---- AÇ: mevcut zaman dilimini sakla, 1M'e geç, bias motorunu başlat ----
      const activeBtn=document.querySelector('.tfbtn.on');
      window.valensScalpPrevInterval = activeBtn ? activeBtn.dataset.int : '15';
      window.valensScalpModeActive=true;
      const oneMinBtn=document.querySelector('.tfbtn[data-int="1"]');
      if(oneMinBtn) oneMinBtn.click(); // mevcut interval değişim mekanizmasını tetikler (loadChart+valensSetInterval)
      toggleBtn.textContent=t('scalpModeToggleOn'); toggleBtn.style.background='var(--red)'; toggleBtn.style.color='#fff';
      if(badge){ badge.textContent=t('scalpModeBadgeOn'); badge.style.color='var(--green)'; }
      if(window.valensFetchScalpBias) window.valensFetchScalpBias();
    } else {
      // ---- KAPAT: kutu çizimini temizle, önceki zaman dilimine dön ----
      window.valensScalpModeActive=false;
      if(window.valensClearScalpBox) window.valensClearScalpBox();
      const prevBtn=document.querySelector('.tfbtn[data-int="'+(window.valensScalpPrevInterval||'15')+'"]');
      if(prevBtn) prevBtn.click();
      toggleBtn.textContent=t('scalpModeToggleOff'); toggleBtn.style.background='var(--gold)'; toggleBtn.style.color='#07101b';
      if(badge){ badge.textContent=t('scalpModeBadgeOff'); badge.style.color='var(--muted)'; }
      renderScalpBiasLine();
    }
  });
})();

// ============ MT5 KÖPRÜSÜ — MANUEL ONAYLI ============
// Kullanıcı "MT5'i tamamen kaldır" demişti, şimdi "diğer bilgisayardaki köprüye bağlanabileceğim bir
// alan" istiyor — bilerek OTOMATİK DEĞİL: bağlantı sadece durum okur, GÖNDERME sadece kullanıcı
// "Gönder" butonuna bastığında olur. Adres artık sabit 127.0.0.1 değil, kullanıcı girer (başka bir
// PC'deki köprüye bağlanabilmek için).
window.valensMT5Connected=false;
function mt5Url(){ const el=document.getElementById('mt5BridgeUrl'); const v=(el&&el.value||'').trim().replace(/\/$/,''); return v; }
function updateMT5UIConnected(connected){
  window.valensMT5Connected=connected;
  const btn=document.getElementById('mt5BridgeToggle'), badge=document.getElementById('mt5BridgeBadge'), status=document.getElementById('mt5BridgeStatus'), sendArea=document.getElementById('mt5SendArea');
  if(btn) btn.textContent = connected ? t('mt5BridgeToggleOn') : t('mt5BridgeToggleOff');
  if(badge){ badge.textContent = connected ? t('mt5BridgeBadgeOn') : t('mt5BridgeBadgeOff'); badge.style.color = connected ? 'var(--green)' : 'var(--muted)'; }
  if(status) status.textContent = connected ? t('mt5BridgeConnectedNote') : t('mt5BridgeStoppedNote');
  if(sendArea) sendArea.style.display = connected ? 'block' : 'none';
}
(function wireMT5Bridge(){
  const toggleBtn=document.getElementById('mt5BridgeToggle'), sendBtn=document.getElementById('mt5SendBtn');
  if(!toggleBtn) return;
  try{ const savedUrl=localStorage.getItem('valens_mt5_url'); if(savedUrl) document.getElementById('mt5BridgeUrl').value=savedUrl; }catch(e){}
  toggleBtn.addEventListener('click', ()=>{
    if(window.valensMT5Connected){ updateMT5UIConnected(false); return; }
    const url=mt5Url();
    const status=document.getElementById('mt5BridgeStatus');
    if(!url){ if(status) status.textContent=t('mt5BridgeNoUrl'); return; }
    try{ localStorage.setItem('valens_mt5_url', url); }catch(e){}
    if(status) status.textContent='…';
    fetch(url+'/status', {method:'GET'}).then(r=>r.json()).then(()=>{
      updateMT5UIConnected(true);
    }).catch(()=>{
      updateMT5UIConnected(false);
      if(status) status.textContent=t('mt5BridgeUnreachable');
    });
  });
  if(sendBtn) sendBtn.addEventListener('click', ()=>{
    const lot=parseFloat(document.getElementById('mt5SendLot').value)||0;
    sendSignalToMT5(window.valensPendingSignal, lot);
  });
})();
// ============ MERKEZİ SİNYAL API — 7/24 SUNUCU ============
// Kullanıcı isteği: terminal sunucuda kesintisiz çalışsın, hangi cihazdan girilirse girilsin
// AYNI sinyal geçmişi görülsün, ilerde "hangi strateji gerçekten kârlı" analizi yapılabilsin.
// MT5 köprüsüyle AYNI desen (kullanıcı URL girer, "Bağlan"a basar) ama burada bağlantı bir
// erken-erişim koduyla doğrulanıp (valens_signal_api.py /verify-code) paylaşılan bir API token'ı
// alınıyor — sonraki tüm istekler bu token'ı taşıyor. Bağlı değilken (varsayılan) hiçbir şey
// değişmez, davranış öncekiyle birebir aynıdır (sadece localStorage).
window.valensSignalApiConnected=false;
window.valensSignalApiToken=null;
function signalApiUrl(){ const el=document.getElementById('signalApiUrl'); const v=(el&&el.value||'').trim().replace(/\/$/,''); return v; }
function signalApiHeaders(){ return {'Content-Type':'application/json', 'X-Valens-Token': window.valensSignalApiToken||''}; }
function updateSignalApiUIConnected(connected){
  window.valensSignalApiConnected=connected;
  if(!connected) window.valensSignalApiToken=null;
  const btn=document.getElementById('signalApiToggle'), badge=document.getElementById('signalApiBadge'), statsArea=document.getElementById('signalApiStatsArea');
  if(btn) btn.textContent = connected ? t('signalApiToggleOn') : t('signalApiToggleOff');
  if(badge){ badge.textContent = connected ? '●' : '—'; badge.style.color = connected ? 'var(--green)' : 'var(--muted)'; }
  if(statsArea) statsArea.style.display = connected ? 'block' : 'none';
}
(function wireSignalApi(){
  const toggleBtn=document.getElementById('signalApiToggle');
  if(!toggleBtn) return;
  try{
    const savedUrl=localStorage.getItem('valens_signal_api_url'); if(savedUrl) document.getElementById('signalApiUrl').value=savedUrl;
    const savedCode=localStorage.getItem('valens_signal_api_code'); if(savedCode) document.getElementById('signalApiCode').value=savedCode;
  }catch(e){}
  toggleBtn.addEventListener('click', ()=>{
    if(window.valensSignalApiConnected){ updateSignalApiUIConnected(false); return; }
    const url=signalApiUrl(), code=(document.getElementById('signalApiCode').value||'').trim();
    const status=document.getElementById('signalApiStatus');
    if(!url){ if(status) status.textContent=t('signalApiNoUrl'); return; }
    try{ localStorage.setItem('valens_signal_api_url', url); localStorage.setItem('valens_signal_api_code', code); }catch(e){}
    if(status) status.textContent=t('signalApiConnecting');
    fetch(url+'/verify-code', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({code})})
      .then(r=>r.json()).then(res=>{
        if(res.ok && res.token){
          window.valensSignalApiToken=res.token;
          updateSignalApiUIConnected(true);
          if(status) status.textContent=t('signalApiConnected');
          refreshSignalApiStats();
        } else {
          updateSignalApiUIConnected(false);
          if(status) status.textContent=t('signalApiInvalidCode');
        }
      }).catch(()=>{
        updateSignalApiUIConnected(false);
        if(status) status.textContent=t('signalApiUnreachable');
      });
  });
})();
// Yeni bir armed sinyal merkezi API'ye kaydedilir. Dönen id, TEKRAR AYRICA yüklenmiş (loadTradeStore
// ile taze) bir kopyada `ts` eşleşmesiyle bulunup yazılıyor — logArmedTrade'in kendi `store` referansını
// tekrar kaydetmiyoruz, çünkü bu fetch'in yanıtı gecikirse arada updateTradeOutcomes() aynı işlemi
// çoktan sonuçlandırmış olabilir; o durumda eski/bayat store'u geri yazmak sonucu SİLERDİ.
function pushSignalToApi(sym, ts, payload){
  if(!window.valensSignalApiConnected || !window.valensSignalApiToken) return;
  const url=signalApiUrl(); if(!url) return;
  fetch(url+'/signal', {method:'POST', headers:signalApiHeaders(), body:JSON.stringify(payload)})
    .then(r=>r.json()).then(res=>{
      if(res.ok && res.id){
        const store=loadTradeStore(sym);
        const trade=(store.trades||[]).find(tr=>tr.ts===ts);
        if(trade){ trade.remoteId=res.id; saveTradeStore(sym,store); }
      }
    }).catch(()=>{});
}
function resolveSignalOnApi(trade){
  if(!window.valensSignalApiConnected || !window.valensSignalApiToken || !trade.remoteId) return;
  const url=signalApiUrl(); if(!url) return;
  fetch(url+'/signal/'+trade.remoteId+'/resolve', {method:'POST', headers:signalApiHeaders(), body:JSON.stringify({outcome:trade.outcome})})
    .then(()=>refreshSignalApiStats()).catch(()=>{});
}
function refreshSignalApiStats(){
  if(!window.valensSignalApiConnected || !window.valensSignalApiToken) return;
  const url=signalApiUrl(); if(!url) return;
  fetch(url+'/stats', {headers:signalApiHeaders()}).then(r=>r.json()).then(res=>{
    const body=document.getElementById('signalApiStatsBody'); if(!body || !res.ok) return;
    const entries=Object.keys(res.stats||{});
    if(!entries.length){ body.textContent=t('signalApiStatsEmpty'); return; }
    entries.sort((a,b)=>(res.stats[b].winRate||0)-(res.stats[a].winRate||0));
    body.innerHTML = entries.map(k=>{
      const s=res.stats[k], label=(window.valensTagLabels && window.valensTagLabels[k])||k;
      return t('signalApiStatsLine')(label, s.trades, s.winRate!=null?s.winRate:0);
    }).join('<br>');
  }).catch(()=>{});
}
setInterval(()=>{ if(window.valensSignalApiConnected) refreshSignalApiStats(); }, 5*60*1000); // 5dk'da bir tazele
// ---- Ortak gönderme fonksiyonu — hem manuel "Gönder" butonu hem de otomatik (demo/veri toplama)
// modu AYNI yolu kullanır, davranış hiçbir zaman ikisi arasında farklılaşmaz. ----
// ---- MUM BAŞINA MAKS 2 GÖNDERİM — kullanıcı geri bildirimi (gerçek örnek): aynı mum içinde
// birkaç saniye arayla farklı fiyat noktalarından (4341, 4342, 4343...) tekrar tekrar SELL
// gönderiliyordu. sigId kazanan stratejiye göre de değiştiğinden (best.key), tek başına yeterli bir
// dedup değildi — strateji bir tick'te değişse bile "aynı mum, aynı yön" hâlâ pratikte aynı fikirdir.
// Burada MUM ZAMANI + YÖNE göre ayrı, daha sıkı bir sayaç tutuluyor: bir yönde bir mumda en fazla 2
// gönderim, 3.'sü o mum kapanıp yeni mum başlayana kadar engellenir.
function candleSendLimitReached(sig){
  const tr = window.valensCandleSendTracker;
  return !!(tr && sig && tr.candleTime===sig.candleTime && tr.dir===sig.dir && tr.count>=2);
}
function recordCandleSend(sig){
  const tr = window.valensCandleSendTracker;
  if(!tr || tr.candleTime!==sig.candleTime || tr.dir!==sig.dir){
   window.valensCandleSendTracker = {candleTime:sig.candleTime, dir:sig.dir, count:1};
  } else { tr.count++; }
}
function sendSignalToMT5(sig, lot){
  const url=mt5Url(); if(!url || !window.valensMT5Connected || !sig) return;
  const sendBtn=document.getElementById('mt5SendBtn'), status=document.getElementById('mt5BridgeStatus');
  if(candleSendLimitReached(sig)){
   if(status) status.textContent=t('mt5CandleLimitReached');
   if(sendBtn){ sendBtn.disabled=true; sendBtn.textContent=t('mt5SendBtnLabel'); }
   return;
  }
  recordCandleSend(sig);
  if(sendBtn){ sendBtn.disabled=true; sendBtn.textContent=t('mt5SendBtnSending'); }
  fetch(url+'/signal', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({dir:sig.dir, entry:sig.entry, stop:sig.stop, tp:sig.tp, confidence:sig.confidence, label:sig.label, lot, signal_id:sig.sigId})
  }).then(r=>r.json()).then(res=>{
    if(status) status.textContent = res.executed ? t('mt5BridgeExecuted') : t('mt5BridgeSkipped')(res.reason||'?');
    window.valensLastSentSigId=sig.sigId;
    if(sendBtn) sendBtn.textContent=t('mt5SendBtnSent');
  }).catch(()=>{
    if(status) status.textContent=t('mt5BridgeUnreachable');
    if(sendBtn){ sendBtn.disabled=false; sendBtn.textContent=t('mt5SendBtnLabel'); }
  });
}

// ============ SİNYAL KAR/ZARAR GÜNLÜĞÜ ============
// Bot her "armed" (net BUY/SELL) sinyal verdiğinde o anki grafikten aldığı gerçek giriş/TP/SL
// zaten logArmedTrade() ile kaydediliyor; updateTradeOutcomes() her tick'te fiyatın TP'ye mi SL'ye mi
// ÖNCE ulaştığını kontrol edip sonucu (win/loss) kalıcı olarak işaretliyor. Burada bunu görünür bir
// kâr/zarar listesine dönüştürüyoruz — tüm enstrümanlar birlikte, en yeni en üstte.
function getAllResolvedTrades(){
  const lot=avgLot(); let all=[];
  Object.keys(SYMS).forEach(sym=>{
    const store=loadTradeStore(sym), cs=SYMS[sym].contractSize;
    (store.trades||[]).filter(tr=>tr.resolved).forEach(tr=>{
      const dist = tr.outcome==='win' ? Math.abs(tr.tp-tr.entry) : -Math.abs(tr.entry-tr.sl);
      all.push(Object.assign({sym, usd:dist*cs*lot}, tr));
    });
  });
  all.sort((a,b)=>b.ts-a.ts);
  return all;
}
function updateTradeLogUI(){
  const list=document.getElementById('tradeLogList'), summary=document.getElementById('tradeLogSummary'), badge=document.getElementById('tradeLogBadge');
  if(!list||!summary||!badge) return;
  const trades=getAllResolvedTrades();
  const wins=trades.filter(tr=>tr.outcome==='win').length, losses=trades.length-wins;
  const netUsd=trades.reduce((a,tr)=>a+tr.usd,0);
  badge.textContent=t('tradeLogBadge')(trades.length);
  summary.innerHTML=t('tradeLogSummaryLine')(trades.length,wins,losses,(netUsd>=0?'+':'')+'$'+Math.round(netUsd).toLocaleString('en-US'));
  if(!trades.length){ list.innerHTML='<p style="color:var(--muted);font-size:9px;padding:6px 2px">'+t('tradeLogEmpty')+'</p>'; return; }
  list.innerHTML = trades.slice(0,40).map(tr=>{
    const cfg=SYMS[tr.sym]; if(!cfg) return '';
    const fmt=v=>v.toLocaleString('en-US',{minimumFractionDigits:cfg.dec,maximumFractionDigits:cfg.dec});
    const win = tr.outcome==='win', col=win?'var(--green)':'var(--red)';
    const hitPx = win?tr.tp:tr.sl;
    const ctxLine = tr.context ? describeTradeContext(tr.context) : '';
    return '<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 2px;border-bottom:1px solid var(--line);font-size:9px">'+
      '<div><b style="color:'+col+'">'+(win?t('tradeLogWin'):t('tradeLogLoss'))+' '+(tr.dir>0?'BUY':'SELL')+'</b> '+cfg.label+(tr.stratLabel?' <span style="color:var(--muted)">· '+tr.stratLabel+'</span>':'')+
      '<br><span style="color:var(--muted)">'+fmt(tr.entry)+' → '+fmt(hitPx)+' · '+fmtSigTime(tr.ts)+'</span>'+
      (ctxLine?'<br><span style="color:var(--muted);font-size:8px">'+ctxLine+'</span>':'')+'</div>'+
      '<div style="color:'+col+';font-weight:700;white-space:nowrap">'+(tr.usd>=0?'+$':'-$')+Math.round(Math.abs(tr.usd)).toLocaleString('en-US')+'</div>'+
      '</div>';
  }).join('') + (trades.length>40?'<p style="font-size:8px;color:var(--muted);padding:4px 2px">+'+(trades.length-40)+'…</p>':'');
  renderStrategyLivePanel(trades);
  if(typeof renderScalpBiasLine==='function') renderScalpBiasLine();
}
// ============ GERÇEK STRATEJİ PERFORMANSI — CANLI TAKİP (MT5'siz, sadece bu terminalin ürettiği
// ve TP/SL'ye ulaştığı GERÇEK sinyallerden) ============ Kullanıcı isteği: "hangi strateji nerede
// çalışmış unutmasın". logArmedTrade() artık kazanan stratejinin key/label'ını da kaydediyor;
// burada sembol bağımsız, strateji bazlı toplanıyor — localStorage'da kalıcı, tarayıcı/sekme
// kapansa da (aynı cihaz/tarayıcıda) kaybolmaz.
function getStrategyLiveStats(trades){
  const groups={};
  trades.forEach(tr=>{
    if(!tr.stratKey) return; // bu güncellemeden ÖNCE kaydedilmiş eski işlemler — strateji bilgisi yok, sayılmaz
    if(!groups[tr.stratKey]) groups[tr.stratKey]={label:tr.stratLabel||tr.stratKey, trades:0, wins:0, netUsd:0};
    const g=groups[tr.stratKey];
    g.trades++; if(tr.outcome==='win') g.wins++; g.netUsd+=tr.usd;
  });
  return groups;
}
function renderStrategyLivePanel(trades){
  const el=document.getElementById('stratLiveBody'), badge=document.getElementById('stratLiveBadge');
  if(!el) return;
  const withStrat=trades.filter(tr=>tr.stratKey);
  if(badge) badge.textContent=t('stratLiveBadge')(withStrat.length);
  const groups=getStrategyLiveStats(trades);
  const entries=Object.entries(groups).filter(([,g])=>g.trades>=3).sort((a,b)=>(b[1].wins/b[1].trades)-(a[1].wins/a[1].trades));
  if(!entries.length){ el.innerHTML='<p style="color:var(--muted);font-size:8px">'+t('stratLiveEmpty')+'</p>'; return; }
  el.innerHTML=entries.map(([,g])=>{
    const pct=Math.round((g.wins/g.trades)*100), col=pct>=50?'var(--green)':'var(--red)';
    const dotClass=pct>=55?'on':pct>=40?'mid':'off';
    const profitColor=g.netUsd>=0?'var(--green)':'var(--red)';
    return '<div style="padding:3px 0;border-bottom:1px solid var(--line)">'+
      '<div style="display:flex;justify-content:space-between;font-size:8px">'+
      '<span><span class="statusdot '+dotClass+'"></span>'+g.label+'</span>'+
      '<span>%'+pct+' ('+g.wins+'/'+g.trades+') <b style="color:'+profitColor+'">'+(g.netUsd>=0?'+$':'-$')+Math.round(Math.abs(g.netUsd)).toLocaleString('en-US')+'</b></span>'+
      '</div></div>';
  }).join('');
}

function marketClosedUI(){
 const cfg=SYMS[CUR];
 document.getElementById('sigTxt').textContent=t('market_closed');
 document.getElementById('sigTxt').style.color='var(--red)';
 document.getElementById('sigConf').textContent='—';
 document.getElementById('sigPair').textContent=cfg.label;
 document.getElementById('anPair').textContent=cfg.label;
 ['iRsi','iMacd','iEma','iBoll','iStoch','iAdx','iAtr','iVwap','iWr','iCci','iPsar','iPivot'].forEach(id=>{const e=document.getElementById(id);e.textContent='—';e.className='';});
 document.getElementById('anText').innerHTML=t('marketClosedDesc')(cfg.label);
 const tg=document.getElementById('trigger');tg.className='trigger wait';tg.textContent=t('marketClosedTrigger');
 ['scEntry','scStop','scTp','swEntry','swStop','swTp'].forEach(id=>document.getElementById(id).textContent='—');
 const sc=document.getElementById('scStatus');sc.className='trade-status wait';sc.textContent=t('market_closed');
 document.getElementById('megaAlert').classList.remove('show');
 document.getElementById('fullAlignmentBanner').classList.remove('show');
 const stEl=document.getElementById('strategyTagLine'); if(stEl){stEl.style.display='none';stEl.textContent='';}
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
 document.getElementById('fullAlignmentBanner').classList.remove('show');
 { const stEl=document.getElementById('strategyTagLine'); if(stEl){stEl.style.display='none';stEl.textContent='';} }
 if(reason==='feed-none'){
   document.getElementById('sigTxt').textContent=t('noDataStatus');
   document.getElementById('sigTxt').style.color='var(--muted)';
   document.getElementById('sigConf').textContent='—';
   document.getElementById('anText').innerHTML=t('noDataDesc')(cfg.label);
   tg.className='trigger wait'; tg.textContent=t('noDataTrigger');
   sc.className='trade-status wait'; sc.textContent=t('noDataStatusShort');
 } else {
   document.getElementById('sigTxt').textContent=t('loadingStatus');
   document.getElementById('sigTxt').style.color='var(--gold)';
   document.getElementById('sigConf').textContent='—';
   document.getElementById('anText').innerHTML=t('loadingDesc')(cfg.label);
   tg.className='trigger wait'; tg.textContent=t('loadingTrigger');
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
 // ---- GERÇEK SPOT DÜZELTMESİ: XAU/USD grafiği Binance'ın PAXG proxy'sinden geliyor, gerçek spot
 // altından birkaç dolar farklı olabilir (updateGoldOffset() periyodik ölçer). Giriş/stop/hedef
 // sayıları ve açık işlem takibi (updateTradeOutcomes) AYNI düzeltilmiş baza göre hesaplanmalı —
 // aksi halde kayıt anında kullanılan baz ile sonraki tick'lerdeki TP/SL kontrolü tutarsız olur.
 const goldAdj = (CUR==='OANDA:XAUUSD') ? (window.valensGoldOffset||0) : 0;
 const adjLast = last + goldAdj;

 // ---- ÖNCE açık işlemi çöz, SONRA yeni karar ver — SIRALAMA HATASI DÜZELTMESİ ----
 // Gerçek kullanıcı örneği: %92 SELL stop oldu ve AYNI tick'te %91 BUY arm oldu, çünkü
 // updateTradeOutcomes() (ve onun içindeki recordStopLoss()) eskiden bu fonksiyonun EN SONUNDA
 // çalışıyordu — yani "STOP SONRASI SOĞUMA" kontrolü bu tick'te henüz kaydedilmemiş eski (soğuk)
 // veriyle çalışıyordu, taze stop'u bir tick (3sn) GERİ kalarak görüyordu. Artık açık işlem varsa
 // önce O çözülüyor (kaydı da dahil), sonra yeni aday/güven/soğuma hesaplanıyor — taze bir STOP
 // aynı tick'te ters yöndeki yeni "KESİN İŞLEM"i gerçekten engelliyor.
 updateTradeOutcomes(CUR, adjLast);

 // Haber yönü: gerçek zamanlı takvimden (bugün açıklanan, beklenti-vs-gerçekleşen) hesaplanan
 // bias varsa ONU kullan; yoksa (API anahtarı yoksa ya da bugün ilgili haber yoksa) elle
 // girilen sabit NEWS_BIAS'a düş.
 const liveNewsBias = (window.valensNewsBias && typeof window.valensNewsBias[CUR]==='number') ? window.valensNewsBias[CUR] : null;
 const effectiveNewsBias = liveNewsBias!==null ? liveNewsBias : (NEWS_BIAS[CUR]||0);

 // her indikatör kendi yönünü "oy" olarak verir (-1/0/+1) — klasik "Çoklu Gösterge Konfluensi" adayı için kullanılır
 const votes={
  rsi: rsi>55?1:rsi<45?-1:0,
  macd: Math.abs(macd)<0.01*atr?0:(macd>0?1:-1),
  ema: Math.abs(ema50-ema200)<0.0005*ema200?0:(ema50>ema200?1:-1),
  boll: bollPct>75?-1:bollPct<25?1:0,
  stoch: stoch>80?-1:stoch<20?1:0,
  adx: adx>25?(macd>0?1:-1):0,
  wr: williamsR<-80?1:williamsR>-20?-1:0,
  // CCI: RSI/Stoch/Williams %R ile TUTARLI olacak şekilde mean-reversion (aşırı satım/alım dönüş) yorumu kullanılır.
  cci: cci>100?-1:cci<-100?1:0,
  psar: (psar&&psar.isUp)?1:-1,
  vwap: Math.abs(last-vwap)<0.0005*vwap?0:(last>vwap?1:-1),
  trend: cr.trend||0,
  pattern: cr.pattern||0,
  sr: typeof cr.srBias==='number'?Math.sign(cr.srBias):0,
  fib: typeof cr.fibBias==='number'?Math.sign(cr.fibBias):0,
  news: Math.sign(effectiveNewsBias)
 };
 // Destek/direnç sinyali, ADX GÜÇLÜ bir trend teyit ediyorsa ve o trendin TERSİNE bir "sekme" öneriyorsa
 // daha düşük ağırlıklı sayılır — güçlü bir trende karşı gelen destek/direnç sekmeleri, gerçek piyasada
 // trend yönündeki kadar güvenilir değildir ("trend is your friend"). ADX zayıfsa (net bir trend yoksa,
 // ki bu ekran görüntünüzdeki durumdu: ADX 10.8) bu indirim uygulanmaz, tam ağırlık kalır.
 const srTrendStrong = adx>25 && cr.trend && votes.sr!==0 && votes.sr!==cr.trend;
 const weights={rsi:.5,macd:.6,ema:.5,boll:.3,stoch:.3,adx:.2,wr:.35,cci:.35,psar:.4,vwap:.25,trend:.6,pattern:.5,sr:srTrendStrong?0.5:1,fib:.4,news:1};
 let confluenceScore=0;
 Object.keys(votes).forEach(k=>confluenceScore+=votes[k]*(weights[k]||0));
 const totalBaseVotes=Object.keys(votes).length; // 15
 const confluenceConf=Math.min(97,Math.max(50,Math.round(50+Math.abs(confluenceScore)*13)));
 const confluenceDir=confluenceScore>0.6?1:confluenceScore<-0.6?-1:0;
 const confluenceAgree=confluenceDir!==0?Object.values(votes).filter(v=>v===confluenceDir).length:0;

 const tagLabels={emaCross:t('tagEmaCross'), orb:t('tagOrb'), momentum:t('tagMomentum'), liquiditySweep:t('tagLiquiditySweep'),
  rsiDivergence:t('tagRsiDivergence'), bollSqueeze:t('tagBollSqueeze'), emaPullback:t('tagEmaPullback'), insideBar:t('tagInsideBar'),
  fvgRetest:t('tagFvgRetest'), obFvgConfluence:t('tagObFvgConfluence'), ifvg:t('tagIfvg'), amdCycle:t('tagAmdCycle'), valuationZone:t('tagValuationZone'), macdZeroCross:t('tagMacdZeroCross'),
  scalpOrb:t('tagScalpOrb'), noWickRetest:t('tagNoWickRetest'),
  orbSweepFade:t('tagOrbSweepFade'), bosSignal:t('tagBosSignal'), chochSignal:t('tagChochSignal'),
  equalHighsLows:t('tagEqualHighsLows'), tradeDelta:t('tagTradeDelta'),
  silverBullet:t('tagSilverBullet'), orbVolume:t('tagOrbVolume'), vwapPullback:t('tagVwapPullback'),
  ttmSqueeze:t('tagTtmSqueeze'), divergenceChoch:t('tagDivergenceChoch'), pocBounce:t('tagPocBounce'),
  orderBlockMit:t('tagOrderBlockMit'), fibOte:t('tagFibOte'), asianFakeout:t('tagAsianFakeout'), extremeMeanReversion:t('tagExtremeMR'),
  levelConfluence:t('tagLevelConfluence'), deltaConfirmTrend:t('tagDeltaConfirmTrend'), deltaAbsorption:t('tagDeltaAbsorption')};
 window.valensTagLabels = tagLabels; // refreshSignalApiStats() gibi bu fonksiyonun DIŞINDaki kod için (ayrı kapsam)

 // ---- HER STRATEJİYİ BAĞIMSIZ BİR ADAY OLARAK DEĞERLENDİR ("bütün ihtimalleri test et, en uygununu ver") ----
 // Önceki tasarım: 23 şeyin TEK harmanlanmış skoruna bakılıyordu — güçlü ama tek bir kalıp (ör. temiz bir
 // likidite süpürmesi), ilgisiz bir gösterge (CCI, ADX vb.) katılmadığı için boğulabiliyordu. Şimdi: HER
 // strateji kendi tam koşulunu (kendi iç mantığında zaten TÜM şartları AND ile) sağladığında bağımsız bir
 // "aday" olur, kendi temel güvenine sahiptir; diğer göstergeler de aynı yöndeyse ek güven puanı alır.
 // O an en güçlü/en tam aday NİHAİ karar olur — genel bir "23'ün X'i aynı yönde olsun" şartı YOK artık.
 const STRATEGY_BASE_CONF={emaCross:72, orb:70, momentum:70, liquiditySweep:82, rsiDivergence:78, bollSqueeze:75, emaPullback:74, insideBar:68,
  fvgRetest:76, obFvgConfluence:88, ifvg:77, amdCycle:85, valuationZone:73, macdZeroCross:66,
  scalpOrb:68, noWickRetest:75,
  orbSweepFade:79, bosSignal:71, chochSignal:80, equalHighsLows:77, tradeDelta:65,
  silverBullet:86, orbVolume:74, vwapPullback:75, ttmSqueeze:77, divergenceChoch:84,
  pocBounce:76, orderBlockMit:75, fibOte:73, asianFakeout:78, extremeMeanReversion:80,
  levelConfluence:84, deltaConfirmTrend:70, deltaAbsorption:77};
 // ---- STRATEJİ AİLESİ + PİYASA REJİMİ — kullanıcının en baştaki orijinal tasarımında olup şu ana
 // kadar hiç uygulanmamış "anlık duruma göre en uygun strateji" fikri. Her strateji, doğası gereği
 // TREND'i (kırılımı/devamı takip eden) mi yoksa REVERSAL'ı (dönüş/ortalamaya çekilme arayan) mı
 // aradığına göre sınıflandırılır. Piyasa GÜÇLÜ TRENDDEYSE (ADX yüksek), trend ailesine bonus, trende
 // KARŞI ateşlenen reversal stratejilerine ceza verilir (güçlü trende karşı gitmek istatistiksel
 // olarak daha zayıftır). Piyasa YATAYSA (ADX düşük), tam tersi — reversal ailesine bonus, trend
 // ailesine (yatayda kırılımlar genelde sahte çıkar) ceza verilir. Bu KATI bir kapı DEĞİL — sadece
 // güveni ayarlayan bir bonus/ceza, Gemini'nin önerdiği sert kapının sorunlarını (tek bir zayıf halka
 // güçlü bir kurulumu tamamen susturması) tekrar etmiyor.
 const STRATEGY_FAMILY={
  emaCross:'trend', orb:'trend', momentum:'trend', emaPullback:'trend', bosSignal:'trend',
  scalpOrb:'trend', noWickRetest:'trend', orbVolume:'trend', vwapPullback:'trend', fibOte:'trend',
  deltaConfirmTrend:'trend', fvgRetest:'trend', obFvgConfluence:'trend',
  liquiditySweep:'reversal', rsiDivergence:'reversal', ifvg:'reversal', amdCycle:'reversal',
  valuationZone:'reversal', orbSweepFade:'reversal', chochSignal:'reversal', equalHighsLows:'reversal',
  silverBullet:'reversal', divergenceChoch:'reversal', pocBounce:'reversal', orderBlockMit:'reversal',
  asianFakeout:'reversal', extremeMeanReversion:'reversal', levelConfluence:'reversal', deltaAbsorption:'reversal',
  insideBar:'neutral', bollSqueeze:'neutral', macdZeroCross:'neutral', ttmSqueeze:'neutral', tradeDelta:'neutral'
 };
 function detectMarketRegime(adxVal, trendDir){
  if(adxVal==null) return 'unknown';
  if(adxVal>25) return trendDir>0?'trendUp':trendDir<0?'trendDown':'trendFlat';
  if(adxVal<18) return 'ranging';
  return 'transitional';
 }
 // DÜZELTME (kullanıcı geri bildirimi: art arda 8 kayıp, "sistem basit bir kanal kırılımını bile
 // okuyamıyor"): eskiden bu ceza/bonus sadece ±6 puandı — 65-85 baz güvene sahip bir dönüş stratejisi
 // +25'e kadar confirmBoost alabildiğinden ±6 pratikte hiçbir şeyi engellemiyordu. Artık güçlü trende
 // karşı çalışan dönüş stratejileri GERÇEKTEN caydırıcı bir ceza alıyor (aşağıda ayrıca bkz.
 // structureAdjustment — ADX'ten bağımsız, gerçek swing yapısına dayalı İKİNCİ ve daha güçlü bir veto).
 function regimeAdjustment(family, candDir, regime){
  if(family==='neutral' || regime==='unknown' || regime==='transitional') return 0;
  const isTrending = regime==='trendUp' || regime==='trendDown';
  const trendDir = regime==='trendUp'?1:regime==='trendDown'?-1:0;
  if(isTrending){
   if(family==='trend' && candDir===trendDir) return 8;    // duruma UYGUN: güçlü trend + trend ailesi, trend yönünde
   if(family==='reversal' && candDir===-trendDir) return -14; // duruma UYGUN DEĞİL: güçlü trende karşı dönüş arayan strateji
   return 0;
  }
  if(regime==='ranging'){
   if(family==='reversal') return 6;  // duruma UYGUN: yatay piyasa + dönüş/ortalama arayan strateji
   if(family==='trend') return -6;    // duruma UYGUN DEĞİL: yatayda kırılım takibi genelde sahte çıkar
  }
  return 0;
 }
 // ---- YAPI TABANLI VETO (ADX'ten BAĞIMSIZ) — ADX 18-25 "geçiş" bandında regimeAdjustment hiçbir
 // ceza uygulamıyordu; oysa bir kanal TAM OLARAK bu bantta kırılıyor olabilir (ADX henüz güçlü trend
 // seviyesine ulaşmadan). window.valensChartRead.structureBias gerçek swing high/low dizisinden
 // (fraktal pivot) hesaplanır, ADX'e hiç bakmaz — bu yüzden bu boşluğu kapatır. |structureBias|===2
 // ise son swing noktası kapanışla da kırılmış demektir (gerçek BOS) — bu durumda dönüş stratejisine
 // çok daha sert bir ceza uygulanır.
 function structureAdjustment(family, candDir, structureBias){
  if(family==='neutral' || !structureBias) return 0;
  const structDir = structureBias>0?1:-1, broke = Math.abs(structureBias)>=2;
  if(family==='trend' && candDir===structDir) return broke?12:6;
  if(family==='reversal' && candDir===-structDir) return broke?-22:-10;
  return 0;
 }
 // ---- TÜKENİŞ KÜMESİ CEZASI/BONUSU — kullanıcı geri bildirimi: art arda "Shooting Star" oluşmuş bir
 // tepede terminal hâlâ BUY veriyordu. window.valensChartRead.exhaustionBias (detectReversalExhaustion)
 // yapı henüz KIRILMADAN (structureAdjustment'tan DAHA ERKEN) tepe/dip ret mumu kümesini yakalar.
 // negatif = tepede ret kümesi (beklenen tepki AŞAĞI), pozitif = dipte ret kümesi (beklenen tepki YUKARI).
 function exhaustionAdjustment(family, candDir, exhaustionBias){
  if(family==='neutral' || !exhaustionBias) return 0;
  const revDir = exhaustionBias>0?1:-1, strong = Math.abs(exhaustionBias)>=2;
  if(family==='reversal' && candDir===revDir) return strong?14:7;    // dönüşü yakalamaya çalışan strateji — bonus
  if(family==='trend' && candDir===-revDir) return strong?-16:-8;    // tükenmiş yönde devam bekleyen strateji — ceza
  return 0;
 }
 // ---- 1M SCALP MODU — YÖN BONUSU/CEZASI (kullanıcı geri bildirimi: "uyuşmuyor diye işlem
 // aranmasın olmaz, sadece uyuştuğunda yüzde artsın") — DÜZELTME: eskiden 4H/1H uyuşmuyorsa
 // adaylar TAMAMEN eleniyordu (katı kapı). Artık diğer tüm ayarlamalarla (structureAdjustment,
 // exhaustionAdjustment vb.) AYNI desende bir bonus/ceza — arama hiçbir zaman durmuyor, sadece
 // üst zaman dilimiyle uyumlu adayların güveni artıyor (uyumsuz olanlarınki hafif düşüyor, YOK
 // OLMUYOR).
 function scalpBiasAdjustment(candDir){
  if(!window.valensScalpModeActive) return 0;
  const bias=window.valensScalpBias; if(!bias) return 0;
  const aligned = bias.h4Dir!==0 && bias.h4Dir===bias.h1Dir;
  if(!aligned) return 0; // üst zaman dilimi net değil — ne bonus ne ceza, normal aramaya devam
  const biasDir=Math.sign(bias.h4Dir);
  return candDir===biasDir ? 10 : -10;
 }
 // ---- TP'Yİ GERÇEK YAPIYA GÖRE KES — kullanıcı örneği: SELL sinyalinin TP'si Ana Destek'in (1H)
 // ALTINA konmuştu. TP'ye ulaşmak için fiyatın gerçek desteği KIRMASI gerekiyordu — ki kırarsa zaten
 // muhtemelen devam eder, orada "temiz" durup TP'yi vermesi gerçekçi bir varsayım değil. Eskiden TP
 // SADECE ATR'nin sabit bir katıydı, hiçbir gerçek destek/direnç seviyesine bakmıyordu. Artık: entry
 // ile ham (ATR bazlı) hedef arasında GERÇEK bir S/R seviyesi varsa (Ana 1H S/R veya Dyn S/R), hedef
 // o seviyeyi kırmadan, biraz ÖNÜNDE kesiliyor. Yapı hedefe çok yakınsa (anlamsız küçük bir hedef
 // kalırsa) ATR bazlı hama geri dönülüyor — o durumda zaten işlemin kendisi sorgulanmalı, TP'yi
 // yapaylaştırmak çözüm değil.
 function clampTargetToStructure(entry, rawTp, slDist, dir, levels){
  if(!levels) return rawTp;
  const rawDist = Math.abs(rawTp-entry);
  const buffer = rawDist*0.06;
  const candidateLevels = dir>0 ? [levels.mainRes, levels.dynRes] : [levels.mainSup, levels.dynSup];
  let nearest=null;
  candidateLevels.forEach(lv=>{
   if(lv==null || !isFinite(lv)) return;
   const between = dir>0 ? (lv>entry && lv<rawTp) : (lv<entry && lv>rawTp);
   if(!between) return;
   if(nearest===null || Math.abs(lv-entry)<Math.abs(nearest-entry)) nearest=lv;
  });
  if(nearest===null) return rawTp;
  const clamped = dir>0 ? (nearest-buffer) : (nearest+buffer);
  if(Math.abs(clamped-entry) < slDist*0.4) return rawTp; // yapı çok yakın — anlamlı hedef kalmıyor, ATR bazlıya dön
  return clamped;
 }
 function confirmBoost(dir){
  const agreeing=Object.keys(votes).filter(k=>votes[k]===dir).length;
  return Math.round((agreeing/totalBaseVotes)*25); // diğer 15 gösterge de aynı yöndeyse +0..+25 ek güven
 }
 let candidates=[];
 // Test amaçlı: window.valensStrategyOnlyMode=true iken genel "15 gösterge harmanı" (confluence)
 // adayı havuza HİÇ girmez — sadece gerçek isimli strateji kalıpları (likidite süpürmesi, FVG,
 // piyasa yapısı, vb. — bunların hepsi zaten kendi içinde fiyat/yapı yorumlaması içerir) yarışabilir.
 if(confluenceDir!==0 && !window.valensStrategyOnlyMode){
  candidates.push({key:'confluence', dir:confluenceDir, confidence:confluenceConf, label:t('candidateConfluence')});
 }
 const marketRegime = detectMarketRegime(adx, (typeof cr.fastTrend==='number'?cr.fastTrend:cr.trend)||0);
 (cr.strategyTags||[]).forEach(tag=>{
  const base=STRATEGY_BASE_CONF[tag.key]||70;
  const label=tagLabels[tag.key];
  let confidence=Math.min(97, base+confirmBoost(tag.dir));
  // ---- BAĞLAMA (PİYASA REJİMİNE) GÖRE AYARLAMA — "anlık duruma göre en uygun strateji hangisi"
  // sorusunun cevabı. Katı bir kapı değil, güveni ayarlayan bir bonus/ceza.
  const family = STRATEGY_FAMILY[tag.key] || 'neutral';
  const regimeAdj = regimeAdjustment(family, tag.dir, marketRegime);
  if(regimeAdj!==0) confidence = Math.min(97, Math.max(50, Math.round(confidence+regimeAdj)));
  const structureAdj = structureAdjustment(family, tag.dir, cr.structureBias||0);
  if(structureAdj!==0) confidence = Math.min(97, Math.max(50, Math.round(confidence+structureAdj)));
  const exhaustionAdj = exhaustionAdjustment(family, tag.dir, cr.exhaustionBias||0);
  if(exhaustionAdj!==0) confidence = Math.min(97, Math.max(50, Math.round(confidence+exhaustionAdj)));
  const scalpBiasAdj = scalpBiasAdjustment(tag.dir);
  if(scalpBiasAdj!==0) confidence = Math.min(97, Math.max(50, Math.round(confidence+scalpBiasAdj)));
  // ---- GEÇMİŞ VERİ TESTİNE (BACKTEST) GÖRE DİNAMİK AYARLAMA ----
  // window.valensBacktestResults, bu grafikteki GERÇEKTEN YAŞANMIŞ son ~300 mumda her stratejinin
  // geçmişte ateşlendiği HER noktada TP'ye mi SL'ye mi önce ulaştığını hesaplar (runHistoricalBacktest).
  // DÜZELTME (gerçek canlı veriyle doğrulandı): eskiden "kazanma oranı" HER strateji için %50'ye göre
  // ölçekleniyordu. Ama SL:TP oranı stratejiye göre değişiyor — standart strateji 1:2 (kazanma %33.3
  // üzerinde ZATEN kârlı), scalpOrb ise 1.6:0.5 (kazanma %76.2 altında ZARARLI). Sonuç: gerçekte kârlı
  // (ör. %40-48 kazanan, 1:2'de kârlı) stratejiler yanlışlıkla cezalandırılıyor, gerçekte zararsız
  // görünen ama o R:R'de aslında zararda olan stratejiler yeterince cezalandırılmıyordu — güven skoru
  // GERÇEK kârlılıktan kopuktu. Şimdi her stratejinin KENDİ başabaş oranına göre "edge" (kazanma oranı
  // − başabaş) hesaplanıyor; en az 5 sinyal gerekir, örneklem arttıkça (kademeli, 20+'da tam ağırlık)
  // etki güçleniyor.
  let realWinRate = null, source = null;
  const bt = window.valensBacktestResults && window.valensBacktestResults[tag.key];
  if(bt && bt.trades>=5){
   const btWinRate = bt.wins/bt.trades;
   realWinRate = btWinRate;
   const breakeven = (tag.key==='scalpOrb') ? (1.6/(1.6+0.5)) : (1/3); // SL/(SL+TP), botTick'teki gerçek SL/TP oranlarıyla eşleşir
   const edge = btWinRate - breakeven;
   const sampleWeight = Math.min(1, bt.trades/20); // <20 sinyalde kademeli, 20+'da tam güven
   const adj = Math.max(-18, Math.min(12, edge*55*sampleWeight));
   confidence = Math.min(97, Math.max(50, Math.round(confidence+adj)));
   source = 'backtest';
  }
  candidates.push({key:tag.key, dir:tag.dir, confidence, label, realWinRate, realTrades:bt?bt.trades:0, confSource:source, regime:marketRegime, family, structureBias:cr.structureBias||0, exhaustionBias:cr.exhaustionBias||0, fvgZone:tag.fvgZone||null, boxZone:tag.zone||null});
 });

 let best=null;
 candidates.forEach(c=>{ if(!best || c.confidence>best.confidence) best=c; });

 let rawDir = best ? best.dir : 0;
 // Varsayılan %87 — ama test amaçlı window.valensThreshold ile dışarıdan (headless runner'ın
 // --threshold parametresiyle) geçici olarak değiştirilebilir. Kod düzenlemeye gerek kalmaz.
 const THRESHOLD = (typeof window.valensThreshold==='number' && window.valensThreshold>=50 && window.valensThreshold<=99) ? window.valensThreshold : 87;

 // Şeffaflık: kazanan adayın TERS yönünde, ona yakın güvende başka bir aday varsa "karışık" işaretle.
 // ÖNEMLİ: bu artık sadece bir uyarı METNİ değil — çakışma GERÇEKTEN güveni düşürür. Rakip ne kadar
 // yakınsa (gerçek anlaşmazlık o kadar büyükse) indirim o kadar büyük olur. Önceden bu bilgi sadece
 // görüntüleniyordu ama karar/güven sayısını hiç etkilemiyordu — "%90 KESİN İŞLEM" ile "görüşler
 // bölünmüş, dikkatli olun" aynı anda gösterilip birbirini yalanlıyordu.
 const opposing = best ? candidates.filter(c=>c.dir===-best.dir && c.confidence>=(best.confidence-15)) : [];
 const conflicted = best!==null && opposing.length>0;
 let conf = best ? best.confidence : 50;
 if(conflicted){
  const closestOpposing = Math.max(...opposing.map(c=>c.confidence));
  const gap = conf - closestOpposing; // tanım gereği 0-15 arası
  const discount = Math.max(5, Math.round(18 - gap)); // rakip ne kadar yakınsa indirim o kadar büyük
  conf = Math.max(50, Math.round(conf - discount));
 }

 const agreeCount = best ? candidates.filter(c=>c.dir===best.dir).length : 0;
 const totalVotes = candidates.length;
 let technicallyArmed = best!==null && conf>=THRESHOLD;
 const riskBlocked = isRiskBlocked();
 let armed = technicallyArmed && !riskBlocked;

 // ---- MUM KİLİDİ / DEVAMLILIK MEKANİZMASI ----
 // İstek: mum kapanmasını beklemeden (mum İÇİNDEYKEN) sinyal verilebilsin, AMA aynı mum içinde
 // yön/güven sürekli değişip durmasın (titreşim/flip-flop önlensin) — "sell verdi, anlık değişiklik
 // oldu, otomatik buy'a döndü" sorunu budur. Mum GERÇEKTEN kapanıp yeni mum başladığında, o yeni
 // mumun taze hesaplaması aynı yönü DESTEKLİYORSA "devam" sayılır (güncel fiyata göre giriş/hedef
 // yenilenir); desteklemiyorsa kilit serbest bırakılıp o mumun kendi sonucu kullanılır.
 const curCandleTime = cr.candleTime || 0;
 const lock = window.valensCandleLock;
 if(!lock){
  if(armed) window.valensCandleLock = {candleTime:curCandleTime, dir:rawDir, conf, bestKey:best.key, bestLabel:best.label, confirmedCandles:1};
 } else if(lock.candleTime === curCandleTime){
  // AYNI mum — kilitli yönü/güveni koru, bu tick'in taze (muhtemelen gürültülü) sonucunu YOK SAY
  rawDir = lock.dir; conf = lock.conf;
  const lockedCandidate = candidates.find(c=>c.key===lock.bestKey && c.dir===lock.dir);
  if(lockedCandidate) best = lockedCandidate;
  // kilit zaten armed olarak kurulmuştu — durumu yeniden, tutarlı şekilde hesapla
  technicallyArmed = conf>=THRESHOLD;
  armed = technicallyArmed && !riskBlocked;
 } else {
  // YENİ mum başlamış — taze hesaplama kilidi destekliyor mu?
  if(armed && rawDir===lock.dir){
   // AYNI yön yeni mumda da tekrar ateşlendi — bu bir "onay mumu" sayılır, sayaç artar.
   window.valensCandleLock = {candleTime:curCandleTime, dir:rawDir, conf, bestKey:best.key, bestLabel:best.label, confirmedCandles:(lock.confirmedCandles||1)+1};
  } else {
   window.valensCandleLock = armed ? {candleTime:curCandleTime, dir:rawDir, conf, bestKey:best.key, bestLabel:best.label, confirmedCandles:1} : null; // desteklemedi, kilit serbest
  }
 }

 // ---- MUM KAPANIŞ ONAYI — kullanıcı geri bildirimi: "aynı mumda %90 BUY, hemen %90 SELL'e
 // dönebiliyor". Yukarıdaki kilit AYNI mum içindeki titreşimi zaten engelliyordu, ama tek bir
 // mumun (özellikle kısa zaman aralıklarında saniyeler süren) ilk okumasını hemen "KESİN İŞLEM"
 // sayıp göndermek riskliydi. Artık bir sinyal ilk ateşlendiğinde HEMEN gönderilmiyor — mum
 // GERÇEKTEN kapanıp YENİ bir mum AYNI yönü doğrulamadan (2. mum) gerçek KESİN İŞLEM sayılmıyor.
 // Aynı yönde devam ederse sayaç büyümeye devam eder, TERS yön gelirse kilit sıfırlanıp yeniden
 // 1'den başlar (yukarıdaki blok zaten bunu yapıyor).
 const REQUIRED_CONFIRM_CANDLES = 2;
 const confirmedCandles = window.valensCandleLock ? (window.valensCandleLock.confirmedCandles||1) : 0;
 const awaitingConfirmation = armed && confirmedCandles < REQUIRED_CONFIRM_CANDLES;
 if(awaitingConfirmation) armed = false;

 const COOLDOWN_MIN = 20;
 const lastStop = getStopCooldown(CUR);
 let cooldownActive = false, cooldownRemainMin = 0;
 if(lastStop && armed && rawDir===-lastStop.dir){
  const elapsedMin = (Date.now()-lastStop.ts)/60000;
  if(elapsedMin < COOLDOWN_MIN){ cooldownActive=true; cooldownRemainMin=Math.ceil(COOLDOWN_MIN-elapsedMin); armed=false; }
 }

 let sigText='◇ GÖZLEM', sigColor='var(--gold)';
 if(rawDir>0)sigText='▲ BUY'; else if(rawDir<0)sigText='▼ SELL';
 if(armed){sigText=rawDir>0?'▲ BUY':'▼ SELL';sigColor=rawDir>0?'var(--green)':'var(--red)';}

 const sigWhyEl=document.getElementById('sigWhy');
 if(sigWhyEl){
  let whyHtml = best ? t('winningCandidateLine')(best.label, conf) : t('noCandidateLine');
  if(conflicted) whyHtml += ' <span style="color:#ffb27a">'+t('conflictWarning')+'</span>';
  if(awaitingConfirmation) whyHtml += t('confirmWhyNote')(confirmedCandles, REQUIRED_CONFIRM_CANDLES);
  if(cooldownActive) whyHtml += t('cooldownWhyNote')(cooldownRemainMin);
  sigWhyEl.innerHTML = whyHtml;
 }

 const tagEl=document.getElementById('strategyTagLine');
 if(tagEl){
  if(candidates.length){
   const srcMark=(c)=> c.confSource==='backtest' ? ' <span style="color:var(--blue)" title="'+t('confSourceBacktest')+'">◐</span>' : '';
   const regimeMark=(c)=>{
    if(!c.family || c.family==='neutral' || !c.regime) return '';
    const adj = regimeAdjustment(c.family, c.dir, c.regime);
    if(adj>0) return ' <span style="color:var(--green)" title="'+t('regimeBonus')+'">▲</span>';
    if(adj<0) return ' <span style="color:var(--red)" title="'+t('regimePenalty')+'">▼</span>';
    return '';
   };
   const structureMark=(c)=>{
    if(!c.family || c.family==='neutral' || !c.structureBias) return '';
    const adj = structureAdjustment(c.family, c.dir, c.structureBias);
    if(adj>0) return ' <span style="color:var(--green)" title="'+t('structureBonus')+'">◆</span>';
    if(adj<0) return ' <span style="color:var(--red)" title="'+t('structurePenalty')+'">◇</span>';
    return '';
   };
   const exhaustionMark=(c)=>{
    if(!c.family || c.family==='neutral' || !c.exhaustionBias) return '';
    const adj = exhaustionAdjustment(c.family, c.dir, c.exhaustionBias);
    if(adj>0) return ' <span style="color:var(--green)" title="'+t('exhaustionBonus')+'">✳</span>';
    if(adj<0) return ' <span style="color:var(--red)" title="'+t('exhaustionPenalty')+'">✕</span>';
    return '';
   };
   const parts=candidates.slice().sort((a,b)=>b.confidence-a.confidence).map(c=>
    (c===best?'<b style="color:'+(c.dir>0?'var(--green)':'var(--red)')+'">':'')+c.label+' ('+c.confidence+'%)'+srcMark(c)+regimeMark(c)+structureMark(c)+exhaustionMark(c)+(c===best?'</b>':'')
   );
   const regimeLabel = marketRegime==='trendUp'?t('regimeTrendUp'):marketRegime==='trendDown'?t('regimeTrendDown'):marketRegime==='ranging'?t('regimeRanging'):marketRegime==='trendFlat'?t('regimeTrendFlat'):t('regimeUnclear');
   const sBias = cr.structureBias||0;
   const structureLabel = sBias>=2?t('structureBrokenUp'):sBias===1?t('structureUp'):sBias<=-2?t('structureBrokenDown'):sBias===-1?t('structureDown'):t('structureUnclear');
   const eBias = cr.exhaustionBias||0;
   const exhaustionLabel = eBias<=-2?t('exhaustionTopStrong'):eBias===-1?t('exhaustionTop'):eBias>=2?t('exhaustionBottomStrong'):eBias===1?t('exhaustionBottom'):t('exhaustionNone');
   tagEl.style.display='block'; tagEl.innerHTML='<div style="color:var(--muted);margin-bottom:2px">'+t('regimePrefix')+' <b style="color:var(--gold)">'+regimeLabel+'</b> · '+t('structurePrefix')+' <b style="color:var(--gold)">'+structureLabel+'</b> · '+t('exhaustionPrefix')+' <b style="color:var(--gold)">'+exhaustionLabel+'</b></div>'+t('strategyTagPrefix')+parts.join(' · ');
  } else { tagEl.style.display='none'; tagEl.textContent=''; }
 }

 // FVG (Fair Value Gap) stratejisi grafikte AYRI bir script/canvas bağlamında (chart motoru)
 // çizildiği için buradan doğrudan cs.createPriceLine çağrılamıyor — window.valensDrawFVGZone /
 // valensClearFVGZone köprü fonksiyonları (aşağıda chart motorunda tanımlı) üzerinden haberleşiyor,
 // tıpkı window.valensRenderBacktestPanel gibi mevcut diğer köprülerle aynı desen.
 if(best && best.key==='fvgRetest' && best.fvgZone && window.valensDrawFVGZone){
  window.valensDrawFVGZone(best.fvgZone, best.dir);
 } else if(window.valensClearFVGZone){
  window.valensClearFVGZone();
 }

 const fmt=v=>v.toLocaleString('en-US',{minimumFractionDigits:cfg.dec,maximumFractionDigits:cfg.dec});
 document.getElementById('sigTxt').textContent=sigText;
 document.getElementById('sigTxt').style.color=sigColor;
 document.getElementById('sigConf').textContent=t('confSuffixLine')(conf,agreeCount,totalVotes);
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
 set('iPsar', (psar?(psar.isUp?t('psarUpLbl'):t('psarDownLbl')):'—'), psar?(psar.isUp?1:-1):0);
 set('iPivot', pivots?('P '+fmt(pivots.pp)+' / R1 '+fmt(pivots.r1)+' / S1 '+fmt(pivots.s1)):'—', 0);

 // ---- ÜST DURUM GÖSTERGE ŞERİDİ (renkli daireler) — aynı 15 klasik oy'un (votes) görsel özeti,
 // referans terminal görselindeki kırmızı/sarı/yeşil gösterge sırasına benzer. ----
 const gaugeMap={rsi:'gd_rsi',macd:'gd_macd',ema:'gd_ema',boll:'gd_boll',stoch:'gd_stoch',adx:'gd_adx',wr:'gd_wr',cci:'gd_cci',psar:'gd_psar',vwap:'gd_vwap',trend:'gd_trend',pattern:'gd_pattern',sr:'gd_sr',fib:'gd_fib',news:'gd_news'};
 Object.keys(gaugeMap).forEach(k=>{
  const el=document.getElementById(gaugeMap[k]); if(!el) return;
  const v=votes[k]||0;
  el.className='statusdot big '+(v>0?'on':v<0?'off':'na');
 });

 // ---- Kategori kategori özet: indikatörler / stratejiler / grafik yorumu, kazanan yönü destekliyor mu? ----
 function computeCategoryStats(){
  const winDir = rawDir;
  // Kategori 1: İndikatörler (10 klasik osilatör/MA)
  const indKeys=['rsi','macd','ema','boll','stoch','adx','wr','cci','psar','vwap'];
  const indActive=indKeys.filter(k=>votes[k]!==0);
  const indAgree=winDir!==0?indActive.filter(k=>votes[k]===winDir).length:0;
  // Kategori 2: Stratejiler (8 adlandırılmış kalıp, confluence hariç)
  const stratCands=candidates.filter(c=>c.key!=='confluence');
  const stratAgree=winDir!==0?stratCands.filter(c=>c.dir===winDir).length:0;
  // Kategori 3: Mum grafiği (candlestick formasyonu — Hammer/Engulf/vb.)
  const candleActive=votes.pattern!==0;
  const candleAgree=winDir!==0 && votes.pattern===winDir;
  // Kategori 4: Grafik yorumlama (trend + S/R + Fibonacci — mum formasyonu HARİÇ)
  const chartKeys=['trend','sr','fib'];
  const chartActive=chartKeys.filter(k=>votes[k]!==0);
  const chartAgree=winDir!==0?chartActive.filter(k=>votes[k]===winDir).length:0;

  // ---- TAM UYUM: dört kategori de BAĞIMSIZ OLARAK aynı yönü doğruluyor mu? ----
  // İndikatörlerde güçlü çoğunluk (en az %60, en az 4 aktif gösterge) + en az 1 strateji desteği +
  // mum formasyonu aynı yönde + grafik yorumlama (trend/S-R/Fib) da aynı yönde — HEPSİ birden.
  const indStrong = indActive.length>=4 && indAgree>=Math.ceil(indActive.length*0.6);
  const stratStrong = stratAgree>=1;
  const candleStrong = candleActive && candleAgree;
  const chartStrong = chartActive.length>0 && chartAgree===chartActive.length;
  const fullAlignment = winDir!==0 && indStrong && stratStrong && candleStrong && chartStrong;

  return {winDir, indActive, indAgree, indKeys, stratCands, stratAgree, candleActive, candleAgree, chartActive, chartAgree, chartKeys, fullAlignment};
 }
 function buildCategoryBreakdown(st){
  const winDir=st.winDir;
  function stateBadge(agree,total){
   if(winDir===0) return '<span class="statusdot na"></span><span style="color:var(--muted)">'+t('catNoVerdictYet')+'</span>';
   if(total===0) return '<span class="statusdot na"></span><span style="color:var(--muted)">'+t('catNoData')+'</span>';
   if(agree===total) return '<span class="statusdot on"></span><span style="color:var(--green)">'+t('catFull')+'</span>';
   if(agree===0) return '<span class="statusdot off"></span><span style="color:var(--red)">'+t('catNone')+'</span>';
   return '<span class="statusdot mid"></span><span style="color:var(--gold)">'+t('catPartial')+' ('+agree+'/'+total+')</span>';
  }
  const indLevels='RSI '+rsi.toFixed(1)+' · MACD '+(macd>=0?'+':'')+macd.toFixed(2)+' · EMA '+(ema50>ema200?'Golden ▲':'Death ▼')+' · Boll %'+bollPct.toFixed(0)+' · Stoch '+stoch.toFixed(1)+' · ADX '+adx.toFixed(1);
  const stratList=st.stratCands.length?st.stratCands.map(c=>c.label+' ('+(c.dir>0?'▲':'▼')+' %'+c.confidence+')').join(', '):t('catNoStrategies');
  const candleLevel=cr.patternName?cr.patternName:t('catNoPattern');
  const chartParts=[]; if(cr.trend) chartParts.push(cr.trend>0?t('trendUp'):t('trendDown')); if(cr.srText) chartParts.push(cr.srText);
  const chartLevels=chartParts.length?chartParts.join(' · '):t('catNeutral');

  let html='<div style="margin-top:9px;padding-top:9px;border-top:1px dashed var(--line);font-size:10px;line-height:1.75">';
  html+='<div><b style="color:var(--gold)">'+t('catIndicators')+'</b> — '+indLevels+'<br>'+st.indActive.length+' '+t('catActiveOf')+' '+st.indKeys.length+' · '+stateBadge(st.indAgree,st.indActive.length)+'</div>';
  html+='<div style="margin-top:7px"><b style="color:var(--gold)">'+t('catStrategies')+'</b> — '+stratList+(st.stratCands.length?('<br>'+stateBadge(st.stratAgree,st.stratCands.length)):'')+'</div>';
  html+='<div style="margin-top:7px"><b style="color:var(--gold)">'+t('catCandle')+'</b> — '+candleLevel+'<br>'+stateBadge(st.candleAgree?1:0,st.candleActive?1:0)+'</div>';
  html+='<div style="margin-top:7px"><b style="color:var(--gold)">'+t('catChart')+'</b> — '+chartLevels+'<br>'+stateBadge(st.chartAgree,st.chartActive.length)+'</div>';
  if(st.fullAlignment) html+='<div style="margin-top:8px;padding:6px 8px;border-radius:4px;background:rgba(212,175,55,.12);border:1px solid var(--gold);font-size:10px"><b style="color:var(--gold)">🎯 '+t('catFullAlignment')+'</b></div>';
  html+='<div style="margin-top:9px;padding-top:7px;border-top:1px solid var(--line);font-size:12px"><b>'+t('catVerdict')+': <span style="color:'+sigColor+'">'+sigText+'</span></b> — %'+conf+' '+t('catConfidence')+(best?(' · '+best.label):'')+'</div>';
  html+='</div>';
  return html;
 }
 const catStats = computeCategoryStats();
 document.getElementById('anText').innerHTML = t('anText')({
  label:cfg.label, rsi:rsi.toFixed(1), macdPos:macd>0, emaGolden:ema50>ema200, atr:fmt(atr), vwapAbove:last>vwap,
  williamsR:williamsR.toFixed(1), cci:cci.toFixed(1), psarUp:psar&&psar.isUp, trend:cr.trend||0,
  patternName:cr.patternName, srText:cr.srText,
  newsLive:liveNewsBias!==null, newsDetail:(window.valensNewsDetail&&window.valensNewsDetail[CUR]||[]).slice(0,2).join(', ')||t('newsData'),
  newsBias:effectiveNewsBias, sigColor, sigText, conf, agreeCount, totalVotes
 }) + buildCategoryBreakdown(catStats);

 const tg=document.getElementById('trigger');
 if(armed){tg.className='trigger armed';tg.textContent=t('armedTrigger')(rawDir>0?'BUY':'SELL',conf);}
 else if(technicallyArmed && riskBlocked){tg.className='trigger wait';tg.textContent=t('riskBlockedStatus');}
 else if(awaitingConfirmation){tg.className='trigger wait';tg.textContent=t('confirmStatus')(confirmedCandles,REQUIRED_CONFIRM_CANDLES,rawDir>0?'BUY':'SELL');}
 else if(cooldownActive){tg.className='trigger wait';tg.textContent=t('cooldownStatus')(cooldownRemainMin);}
 else if(conflicted){tg.className='trigger wait';tg.textContent=t('conflictBadge')+' · '+t('waitTrigger')(conf,THRESHOLD,agreeCount,totalVotes);}
 else{tg.className='trigger wait';tg.textContent=t('waitTrigger')(conf,THRESHOLD,agreeCount,totalVotes);}

 const scStatusEl=document.getElementById('scStatus');
 const alertBox=document.getElementById('megaAlert');
 const faBanner=document.getElementById('fullAlignmentBanner');
 if(armed && catStats.fullAlignment){
   faBanner.classList.add('show');
   document.getElementById('faBannerBody').innerHTML=t('fullAlignmentBody')(rawDir>0?'▲ BUY':'▼ SELL', best?best.label:'', conf);
 } else { faBanner.classList.remove('show'); }
 if(armed){
   const d=rawDir;
   // ---- ATR bazlı dinamik SL/TP: sabit pip değil, GERÇEK volatiliteye göre ölçeklenir (2:1 R:R) ----
   // İSTİSNA — ORB Scalp Varyantı kazanan aday olduğunda: bu kalıp video kaynağında GÖZLEMLENEN gerçek
   // bir örnekte SL:TP oranının ~3.2:1 (dar hedef, geniş stop) olduğunu gösterdi — bu, YÜKSEK kazanma
   // oranı ama HER kayıp, kazançlardan çok daha büyük demektir. Kör kör aynı MUTLAK puanları kopyalamak
   // yerine AYNI ORANI kendi gerçek ATR'ımıza uyguluyoruz, ve gereken başabaş kazanma oranını AÇIKÇA
   // gösteriyoruz — bu R:R şeklini "varsayılan" yapmıyoruz, sadece bu spesifik kalıp ateşlendiğinde.
   const isTightTpOrb = best && best.key==='scalpOrb';
   // Test amaçlı: window.valensTightScalpMult ile (varsayılan 1.0 = değişiklik yok) scalp SL/TP
   // mesafeleri küçültülebilir — oranlar (1:2, ya da scalpOrb'un 3.2:1'i) AYNI kalır, sadece MUTLAK
   // büyüklük küçülür. Böylece 1dk gibi hızlı test senaryolarında daha sık kapanan, daha küçük
   // hedefli işlemler alınabilir.
   const tightMult = (typeof window.valensTightScalpMult==='number' && window.valensTightScalpMult>0 && window.valensTightScalpMult<=1) ? window.valensTightScalpMult : 1.0;
   const scSL = atr ? (isTightTpOrb?atr*1.6:atr*1.0)*tightMult : cfg.scSL;
   let scTP = atr ? (isTightTpOrb?atr*0.5:atr*2.0)*tightMult : cfg.scTP;
   // ---- ULAŞILABİLİRLİK SINIRI: hedefin "3 günde" değil, gerçekçi bir scalp süresinde (varsayılan
   // ~2 saat, window.valensMaxHoursToTP ile ayarlanabilir) ulaşılabilir olmasını sağlıyoruz. SL'e
   // DOKUNMUYORUZ — işlem başına risk (SL mesafesi × sabit lot) değişmiyor, sadece hedef gerçekçi
   // hale geliyor. 1.5x tampon payı, fiyatın düz bir çizgi değil hız kazanıp kaybederek hareket
   // ettiğini hesaba katıyor (tamamen ortalama hıza göre kesip fırsatları kaçırmamak için).
   const maxHours = (typeof window.valensMaxHoursToTP==='number' && window.valensMaxHoursToTP>0) ? window.valensMaxHoursToTP : 2;
   const hourlyMove = cr.hourlyMove;
   if(hourlyMove && hourlyMove>0){
    const reachableDistance = hourlyMove * maxHours * 1.5;
    if(scTP > reachableDistance) scTP = Math.max(reachableDistance, scSL*0.5); // asgari anlamlı bir hedef kalsın
   }
   const swSL = atr ? atr*3.0 : cfg.swSL, swTP = atr ? atr*6.0 : cfg.swTP;
   const scEntryPx=adjLast, scStopPx=adjLast-d*scSL;
   const swStopPx=adjLast-d*swSL;
   // ---- KULLANICI GERİ BİLDİRİMİ: giriş fiyatı canlı (gerçek spot-eşdeğeri, goldAdj ile düzeltilmiş)
   // ama TP/SL kırpması için kullanılan S/R seviyeleri (cr.srLevels) HAM grafik/PAXG fiyatındandı —
   // ikisi farklı bir referans noktasındaydı (goldAdj kadar, XAU/USD'de birkaç dolar fark edebilir).
   // Burada srLevels de AYNI goldAdj ile düzeltilip entry ile aynı baza getiriliyor.
   const adjSrLevels = cr.srLevels ? {
    mainSup: cr.srLevels.mainSup!=null?cr.srLevels.mainSup+goldAdj:null,
    mainRes: cr.srLevels.mainRes!=null?cr.srLevels.mainRes+goldAdj:null,
    dynSup: cr.srLevels.dynSup!=null?cr.srLevels.dynSup+goldAdj:null,
    dynRes: cr.srLevels.dynRes!=null?cr.srLevels.dynRes+goldAdj:null
   } : null;
   const scTpPx=clampTargetToStructure(adjLast, adjLast+d*scTP, scSL, d, adjSrLevels);
   const swTpPx=clampTargetToStructure(adjLast, adjLast+d*swTP, swSL, d, adjSrLevels);

   document.getElementById('scEntry').textContent=fmt(scEntryPx);
   document.getElementById('scStop').textContent=fmt(scStopPx);
   document.getElementById('scTp').textContent=fmt(scTpPx);
   document.getElementById('swEntry').textContent=fmt(adjLast);
   document.getElementById('swStop').textContent=fmt(swStopPx);
   document.getElementById('swTp').textContent=fmt(swTpPx);
   scStatusEl.className='trade-status armed';
   scStatusEl.textContent=t('confirmedStatus')(rawDir>0?'BUY':'SELL',conf,utc());
   const tpNoteEl=document.getElementById('scTightTpNote');
   if(tpNoteEl){
    if(isTightTpOrb){
     const breakeven=Math.round((scSL/(scSL+scTP))*100);
     tpNoteEl.style.display='block';
     tpNoteEl.textContent=t('tightTpWarning')(breakeven);
    } else { tpNoteEl.style.display='none'; }
   }

   // ---- Gerçek $ hedef potansiyeli (SİZİN planladığınız 0.8-1.2 lot aralığıyla) — GARANTİ DEĞİL, sadece TP'ye ulaşırsa oluşacak projeksiyon ----
   const rs=loadRiskSettings(), lotMin=parseFloat(rs.lotMin)||0.8, lotMax=parseFloat(rs.lotMax)||1.2, lotAvg=(lotMin+lotMax)/2;
   const scDist=Math.abs(scTpPx-scEntryPx), swDist=Math.abs(swTpPx-adjLast);
   const scTpUsdMin=scDist*cfg.contractSize*lotMin, scTpUsdMax=scDist*cfg.contractSize*lotMax, scTpUsdAvg=scDist*cfg.contractSize*lotAvg;
   const swTpUsdMin=swDist*cfg.contractSize*lotMin, swTpUsdMax=swDist*cfg.contractSize*lotMax;
   document.getElementById('scPnl').textContent = t('targetHitRange')(Math.round(scTpUsdMin).toLocaleString('en-US'),Math.round(scTpUsdMax).toLocaleString('en-US'),lotMin,lotMax);
   document.getElementById('swPnl').textContent = t('targetHitRange')(Math.round(swTpUsdMin).toLocaleString('en-US'),Math.round(swTpUsdMax).toLocaleString('en-US'),lotMin,lotMax);

   // Eşik eskiden 2.5 lot'a göre sabit $1000'di; artık SİZİN gerçek ortalama lotunuza göre orantılı ölçekleniyor
   // (aynı fiyat-hareketi kalitesi bar'ı, sadece gerçek pozisyon büyüklüğünüzle ifade ediliyor).
   const alertThreshold = 1000 * (lotAvg/2.5);
   if(scTpUsdAvg>=alertThreshold){
     alertBox.classList.add('show');
     document.getElementById('megaAlertTitle').textContent=t('megaAlertTitleDyn')(rawDir>0?'BUY':'SELL',cfg.label);
     document.getElementById('megaAlertBody').textContent=t('megaAlertBodyRange')(fmt(scEntryPx),fmt(scStopPx),fmt(scTpPx),Math.round(scTpUsdMin).toLocaleString('en-US'),Math.round(scTpUsdMax).toLocaleString('en-US'),lotMin,lotMax);
   } else { alertBox.classList.remove('show'); }

   logArmedTrade(CUR, rawDir, scEntryPx, scTpPx, scStopPx, best?best.key:null, best?best.label:null, {
    regime: marketRegime, agreeCount, totalVotes, trend: cr.trend||0, srText: cr.srText||'', patternName: cr.patternName||'', confirmedCandles
   }, cr.candleTime||null);
   // ---- 1M SCALP MODU KUTU ÇİZİMİ — kullanıcının paylaştığı video örnekleri: SL/TP çizgi değil,
   // zaman+fiyat ekseninde sınırlı bir KUTU olarak çizilir. window.valensDrawScalpBox (chart
   // motorunda tanımlı, FVG köprüsüyle AYNI desen) SL-TP aralığını, işlemin beklenen süresi kadar
   // (maxHours) ileriye doğru bir dikdörtgen olarak çizer — süre dolunca/sonuçlanınca silinir.
   // DÜZELTME (kullanıcı örneği: kutu fiyattan tamamen kopuk, havada asılı kalıyordu): burada
   // HER tick'te TAZE (canlı fiyata göre kayan) scStopPx/scTpPx kullanılıyordu, ama logArmedTrade
   // tek bir açık işlemi tekilleştiriyor (aynı işlem sonuçlanana kadar yeni kayıt açmıyor) — yani
   // kutu, GERÇEKTE takip edilen işlemden FARKLI (daha yeni, kayan) bir SL/TP çiziyordu; üstelik
   // "armed" bir tur FALSE olup (fiyat eşiği artık karşılamayınca) TP/SL'ye hiç ulaşmadan kutu
   // hiç temizlenmeden EKRANDA DONUP kalıyordu. Artık kutu, localStorage'daki GERÇEK açık işlem
   // kaydından (varsa) çiziliyor — o yoksa (sonuçlandı ya da hiç açılmadıysa) kutu temizleniyor.
   if(window.valensScalpModeActive && window.valensDrawScalpBox && window.valensClearScalpBox){
    const openTrade=(loadTradeStore(CUR).trades||[]).find(tr=>!tr.resolved);
    if(openTrade && openTrade.candleTime){
     const boxEntryTime=openTrade.candleTime;
     const boxEndTime=boxEntryTime+Math.round(maxHours*3600);
     window.valensScalpBoxEndTime=boxEndTime;
     window.valensDrawScalpBox(boxEntryTime, boxEndTime, Math.max(openTrade.sl,openTrade.tp), Math.min(openTrade.sl,openTrade.tp), openTrade.dir);
    } else {
     window.valensClearScalpBox(); window.valensScalpBoxEndTime=null;
    }
   }
   recordLastSignal(CUR,'scalp',rawDir,scEntryPx,scTpPx,scStopPx);
   recordLastSignal(CUR,'swing',rawDir,adjLast,swTpPx,swStopPx);
   // ---- MT5 KÖPRÜSÜ (manuel onaylı): bekleyen sinyali güncelle, gönder butonunun durumunu ayarla.
   // sigId SABİT mum zaman damgasına + kazanan stratejiye bağlı (dalgalanan fiyata değil) — aynı
   // kurulum sürdüğü sürece aynı kalır, "aynı sinyali defalarca gönder" riskini önler.
   const candleTimeForSig = cr.candleTime || Math.floor(Date.now()/1000);
   const sigId = rawDir+'-'+(best?best.key:'none')+'-'+candleTimeForSig;
   window.valensPendingSignal = {dir:rawDir, entry:scEntryPx, stop:scStopPx, tp:scTpPx, confidence:conf, label:(best?best.label:'?'), sigId, candleTime:candleTimeForSig};
   const mt5SendBtn=document.getElementById('mt5SendBtn');
   const candleLimitHit = candleSendLimitReached(window.valensPendingSignal);
   if(mt5SendBtn){
    if(candleLimitHit){ mt5SendBtn.disabled=true; mt5SendBtn.textContent=t('mt5CandleLimitBtn'); }
    else if(window.valensLastSentSigId===sigId){ mt5SendBtn.disabled=true; mt5SendBtn.textContent=t('mt5SendBtnSent'); }
    else { mt5SendBtn.disabled=false; mt5SendBtn.textContent=t('mt5SendBtnLabel'); }
   }
   // ---- OTOMATİK GÖNDER (demo/veri toplama modu) — kullanıcı açıkça işaretlemişse, bağlıysa,
   // güven eşiğini karşılıyorsa, bu sinyal daha önce gönderilmemişse VE bu mumda/yönde gönderim
   // sınırına (2) ulaşılmamışsa, onay beklemeden gönderir. Kapalıyken (varsayılan) hiçbir şey
   // değişmez, davranış manuel-onaylı moddan farksızdır.
   const autoChk=document.getElementById('mt5AutoSend');
   if(autoChk && autoChk.checked && window.valensMT5Connected && window.valensLastSentSigId!==sigId && !candleLimitHit){
    const minConf=parseFloat(document.getElementById('mt5AutoMinConf').value)||90;
    if(conf>=minConf){
     const autoLot=parseFloat(document.getElementById('mt5SendLot').value)||0.1;
     sendSignalToMT5(window.valensPendingSignal, autoLot);
    }
   }
 }else{
   ['scEntry','scStop','scTp','swEntry','swStop','swTp'].forEach(id=>document.getElementById(id).textContent='—');
   scStatusEl.className='trade-status wait';
   scStatusEl.textContent = (technicallyArmed && riskBlocked) ? t('riskBlockedStatus') : awaitingConfirmation ? t('confirmStatus')(confirmedCandles,REQUIRED_CONFIRM_CANDLES,rawDir>0?'BUY':'SELL') : cooldownActive ? t('cooldownStatus')(cooldownRemainMin) : t('waitStatus')(THRESHOLD,conf);
   alertBox.classList.remove('show');
   window.valensPendingSignal = null;
   const mt5SendBtnIdle=document.getElementById('mt5SendBtn');
   if(mt5SendBtnIdle){ mt5SendBtnIdle.disabled=true; mt5SendBtnIdle.textContent=t('mt5SendBtnLabel'); }
 }
 // ---- Scalp kutusu için süre-dolumu güvenlik ağı — trade resolve olduğunda (updateTradeOutcomes
 // içindeki resolveSignalOnApi noktası) zaten temizleniyor, ama TP/SL'ye hiç ulaşılmadan süre
 // dolarsa (kullanıcı isteği: "işlem süresi bitince çizdiklerini silebilir") burada da kontrol edilir.
 if(window.valensScalpBoxEndTime && Date.now()/1000>window.valensScalpBoxEndTime){
  if(window.valensClearScalpBox) window.valensClearScalpBox();
  window.valensScalpBoxEndTime=null;
 }

 updateWinRateUI();
 updateLastSignalUI();
 updateRiskUI();
 updateTradeLogUI();
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
 document.getElementById('fullAlignmentBanner').classList.remove('show');
 for(let i=0;i<4;i++) addFlow(); botTick();
 updateAggUI(); updateWinRateUI(); updateLastSignalUI(); updateRiskUI(); updateTradeLogUI();
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

// ---- ÜST FİYAT ŞERİDİ CANLI GÜNCELLEME ---- Önceden bu şeritteki değerler HTML'e sabit yazılmış
// örnek verilerdi ve HİÇBİR ZAMAN güncellenmiyordu — bu yüzden sinyal motorunun gerçek, canlı giriş
// fiyatıyla karşılaştırıldığında "tutarsız/eski" görünüyordu. Artık gerçek Binance verisinden,
// şu an hangi enstrümanı izlediğinizden BAĞIMSIZ olarak periyodik çekiliyor.
const TICKER_MAP={'OANDA:XAUUSD':'PAXGUSDT','BINANCE:BTCUSDT':'BTCUSDT','OANDA:EURUSD':'EURUSDT'};
// XAU/USD grafiğimiz Binance'ın PAXG (tokenize altın) proxy'sinden geliyor — bu, gerçek spot
// altınından FARKLI bir piyasadır (kripto arz-talebine göre "prim/iskonto" ile işlem görür, belgelenmiş,
// beklenen bir davranıştır, hata değildir). Gerçek karşılaştırma yapabilmeniz için PAXG ile gerçek spot
// arasındaki CANLI farkı ayrıca çekip şeffafça gösteriyoruz; ticker'da GERÇEK spot-eşdeğeri fiyat gösterilir.
window.valensGoldOffset = 0;
async function updateGoldOffset(){
 try{
  const [paxgR, spotR] = await Promise.all([
   fetch('https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT'),
   fetch('https://xaus.com/api/v1/spot?compact=1')
  ]);
  const paxgD = await paxgR.json(), spotD = await spotR.json();
  const paxgPx = parseFloat(paxgD.price), spotPx = parseFloat(spotD.spot_usd_oz);
  if(!isNaN(paxgPx) && !isNaN(spotPx)){
   window.valensGoldOffset = spotPx - paxgPx;
   const offEl=document.getElementById('goldOffsetNote');
   if(offEl){
    const off=window.valensGoldOffset;
    offEl.textContent = t('goldOffsetLine')(off>=0?'+':'', off.toFixed(2));
    offEl.style.color = Math.abs(off)>15 ? 'var(--red)' : 'var(--muted)';
   }
  }
 }catch(e){ /* xaus.com geçici olarak erişilemezse sessizce eski değeri koru */ }
}
const TOP_TICKER_IDS={'OANDA:XAUUSD':['tkXau','tkXau2'],'BINANCE:BTCUSDT':['tkBtc','tkBtc2'],'OANDA:EURUSD':['tkEur','tkEur2']};
async function updateTickerBar(){
 for(const sym of Object.keys(TICKER_MAP)){
  const btn=document.querySelector('.market[data-sym="'+sym+'"]'); if(!btn) continue;
  try{
   const r=await fetch('https://api.binance.com/api/v3/ticker/24hr?symbol='+TICKER_MAP[sym]);
   const d=await r.json();
   let px=parseFloat(d.lastPrice); const pct=parseFloat(d.priceChangePercent);
   if(isNaN(px)||isNaN(pct)) continue;
   if(sym==='OANDA:XAUUSD') px += (window.valensGoldOffset||0); // gerçek spot-eşdeğeri fiyat göster
   const cfg=SYMS[sym]; const dec=cfg?cfg.dec:2;
   btn.dataset.price=px;
   const pxFmt=px.toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec});
   btn.querySelector('strong').textContent=pxFmt;
   const pctEl=btn.querySelector('small.up, small.down')||btn.querySelector('small:last-child');
   if(pctEl){
    pctEl.className=pct>=0?'up':'down';
    pctEl.textContent=(pct>=0?'▲ +':'▼ ')+pct.toFixed(2)+'%';
   }
   // Üstteki akan şerit — önceden burada HİÇ güncellenmeyen sahte "ECB %2.40" gibi örnek değerler
   // duruyordu; artık aynı gerçek, canlı fiyatlarla besleniyor.
   (TOP_TICKER_IDS[sym]||[]).forEach(id=>{ const el=document.getElementById(id); if(el) el.textContent=pxFmt; });
  }catch(e){ /* tek bir sembolün geçici hatası tüm şeridi bozmasın */ }
 }
}
updateGoldOffset().then(updateTickerBar);
setInterval(updateGoldOffset, 45000); // xaus.com adil kullanım kuralı: en az 30sn — 45sn kullanıyoruz
setInterval(updateTickerBar, 15000);


// ---- GEÇMİŞ VERİ TESTİ (backtest) paneli — window.valensRenderBacktestPanel, chart engine script'i
// runHistoricalBacktest() sonucunu hesapladığında çağırır. Kazanma oranına göre sıralar, en az 3
// geçmiş sinyali olmayan stratejileri (istatistiksel olarak anlamsız olur) göstermez.
function backtestLabelFor(key){
 const i18nKey='tag'+key.charAt(0).toUpperCase()+key.slice(1);
 const label=t(i18nKey);
 return (label && label!==i18nKey) ? label : key;
}
window.valensRenderBacktestPanel=function(results){
 const el=document.getElementById('backtestBody'), badge=document.getElementById('backtestBadge');
 if(!el) return;
 if(!results){ el.innerHTML='<p style="color:var(--muted);font-size:8px">'+t('backtestNotEnoughData')+'</p>'; if(badge) badge.textContent='—'; return; }
 const entries=Object.entries(results).filter(([,s])=>s.trades>=3)
   .sort((a,b)=>(b[1].wins/b[1].trades)-(a[1].wins/a[1].trades));
 if(badge) badge.textContent=t('backtestCandleCount')(300);
 if(!entries.length){ el.innerHTML='<p style="color:var(--muted);font-size:8px">'+t('backtestNoSignals')+'</p>'; return; }
 el.innerHTML=entries.map(([key,s])=>{
  const pct=Math.round((s.wins/s.trades)*100);
  const color=pct>=50?'var(--green)':'var(--red)';
  const dotClass = pct>=55?'on':pct>=40?'mid':'off';
  return '<div style="display:flex;justify-content:space-between;font-size:8px;padding:3px 0;border-bottom:1px solid var(--line)">'+
   '<span><span class="statusdot '+dotClass+'"></span>'+backtestLabelFor(key)+'</span>'+
   '<span><b style="color:'+color+'">%'+pct+'</b> ('+s.wins+'/'+s.trades+')</span>'+
   '</div>';
 }).join('');
};

document.querySelectorAll('.tfbtn').forEach(x=>x.onclick=()=>{
 document.querySelectorAll('.tfbtn').forEach(y=>y.classList.remove('on'));
 x.classList.add('on'); INT=x.dataset.int; loadChart(); updateAggUI();
 if(window.valensSetInterval) window.valensSetInterval();
});
document.querySelectorAll('.tab').forEach(x=>x.onclick=()=>{
 document.querySelectorAll('.tab').forEach(y=>y.classList.remove('active')); x.classList.add('active');
});

document.getElementById('langToggle').addEventListener('click', ()=>{
 LANG = LANG==='tr' ? 'en' : 'tr';
 try{ localStorage.setItem('valens_lang', LANG); }catch(e){}
 applyStaticI18N(); setDates();
 botTick(); updateAggUI(); updateWinRateUI(); updateRiskUI(); updateTradeLogUI(); updateSessionBar();
 if(window.valensRenderCOT) window.valensRenderCOT(CUR);
 if(window.valensRenderNews) window.valensRenderNews();
 if(!isMarketOpen(CUR)) marketClosedUI();
});

// ---- Risk yöneticisi giriş alanları: değerleri yükle, değişince kaydet + yeniden hesapla ----
(function initRiskInputs(){
 const s=loadRiskSettings();
 document.getElementById('riskBalance').value=s.balance;
 document.getElementById('riskDailyPct').value=s.dailyPct;
 document.getElementById('riskMaxPct').value=s.maxPct;
 document.getElementById('riskTargetPct').value=s.targetPct;
 document.getElementById('riskLotMin').value=s.lotMin;
 document.getElementById('riskLotMax').value=s.lotMax;
 document.getElementById('riskDays').value=s.challengeDays;
 document.getElementById('riskStart').value=s.startDate;
 const save=()=>{
  const ns={
   balance: parseFloat(document.getElementById('riskBalance').value)||50000,
   dailyPct: parseFloat(document.getElementById('riskDailyPct').value)||5,
   maxPct: parseFloat(document.getElementById('riskMaxPct').value)||10,
   targetPct: parseFloat(document.getElementById('riskTargetPct').value)||10,
   lotMin: parseFloat(document.getElementById('riskLotMin').value)||0.8,
   lotMax: parseFloat(document.getElementById('riskLotMax').value)||1.2,
   challengeDays: parseFloat(document.getElementById('riskDays').value)||10,
   startDate: document.getElementById('riskStart').value || new Date().toISOString().slice(0,10),
  };
  saveRiskSettings(ns); updateRiskUI();
 };
 ['riskBalance','riskDailyPct','riskMaxPct','riskTargetPct','riskLotMin','riskLotMax','riskDays','riskStart'].forEach(id=>{
  document.getElementById(id).addEventListener('change', save);
 });
 updateRiskUI(); updateTradeLogUI();
})();

// ---- Sinyal/işlem geçmişini yedekleme: veri sadece bu tarayıcıda saklanıyor (sunucuda değil).
// Cihaz değiştirirseniz ya da tarayıcı verisini temizlerseniz kaybolur — bu yüzden dışa/içe aktarma var.
document.getElementById('exportTrades').addEventListener('click', e=>{
 e.preventDefault();
 const dump={};
 Object.keys(SYMS).forEach(sym=>{ dump[sym]=loadTradeStore(sym); });
 const blob=new Blob([JSON.stringify(dump,null,2)], {type:'application/json'});
 const url=URL.createObjectURL(blob);
 const a=document.createElement('a'); a.href=url; a.download='valens_sinyal_gecmisi_'+new Date().toISOString().slice(0,10)+'.json';
 a.click(); URL.revokeObjectURL(url);
});
document.getElementById('importTrades').addEventListener('change', e=>{
 const file=e.target.files[0]; if(!file)return;
 const reader=new FileReader();
 reader.onload=()=>{
   try{
     const dump=JSON.parse(reader.result);
     Object.keys(dump).forEach(sym=>{ if(SYMS[sym]) saveTradeStore(sym, dump[sym]); });
     updateWinRateUI();
     alert(t('importSuccess'));
   }catch(err){ alert(t('importFail')); }
 };
 reader.readAsText(file);
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
   if(!c){ dEl.textContent='—'; body.innerHTML='<p style="color:var(--muted)">'+t('cotNoData')+'</p>'; return; }
   // COT raporu haftada BİR kez (Cuma) yayınlanır — bu yüzden birkaç gün "aynı" görünmesi normaldir.
   // Ama gerçekten beklenenden eski kalırsa (>14 gün, olağan haftalık+tatil payını aşan), görünür uyarı ver.
   const daysOld = Math.floor((Date.now() - new Date(c.date+'T00:00:00Z').getTime())/86400000);
   dEl.textContent = c.date + (daysOld<=13 ? '' : '  ⚠');
   dEl.style.color = daysOld<=13 ? '' : 'var(--red)';
   dEl.title = daysOld<=13 ? '' : t('cotStaleWarning')(daysOld);
   const fundNet=c.fund_long-c.fund_short, bankNet=c.bank_long-c.bank_short;
   body.innerHTML=
    '<p><b>'+c.market+'</b> · OI: '+fmt(c.oi)+'</p>'+
    '<div class="scenario '+(fundNet>=0?'bull':'bear')+'"><b>'+(fundNet>=0?'▲':'▼')+' '+t('cotHedgeFunds')+':</b> '+
      (fundNet>=0?t('cotNetLong'):t('cotNetShort'))+' '+fmt(Math.abs(fundNet))+
      '<br>'+t('cotLong')+' '+fmt(c.fund_long)+' ('+chg(c.fund_dlong)+') · '+t('cotShort')+' '+fmt(c.fund_short)+' ('+chg(c.fund_dshort)+')</div>'+
    '<div class="scenario '+(bankNet>=0?'bull':'bear')+'"><b>'+(bankNet>=0?'▲':'▼')+' '+t('cotBanks')+':</b> '+
      (bankNet>=0?t('cotNetLong'):t('cotNetShort'))+' '+fmt(Math.abs(bankNet))+
      '<br>'+t('cotLong')+' '+fmt(c.bank_long)+' · '+t('cotShort')+' '+fmt(c.bank_short)+'</div>'+
    '<p style="font-size:8px;color:var(--muted);margin-top:5px">'+t('cotSourceNote')+
      (daysOld<=13 ? ' · '+t('cotWeeklyNote') : '')+'</p>';
 };
 window.valensRenderCOT(CUR);
})();
</script>

<script>
/* ============ GÜNÜN ÖNEMLİ HABERLERİ + SENARYO ANALİZİ ============ */
(function(){
 const ECON = __ECON_DATA__; // {available, events:[{time,country,event,impact,actual,estimate,prev,unit}]}
 window.valensNewsBias = {};   // botTick bunu okur; bir sembol için değer yoksa manuel NEWS_BIAS'a düşer
 window.valensNewsDetail = {};

 // Standart makro ilişki şablonları — ders kitabı seviyesinde genel eğilimlerdir, kesin tahmin DEĞİLDİR.
 const RULES = [
  {re:/non-?farm|nfp|payroll/i, higherIsCurrencyPositive:true, labelKey:'ruleNfp', employmentFamily:true},
  {re:/unemployment rate/i, higherIsCurrencyPositive:false, labelKey:'ruleUnrate', employmentFamily:true},
  {re:/jobless claims|unemployment claims/i, higherIsCurrencyPositive:false, labelKey:'ruleClaims', employmentFamily:true},
  {re:/jolts|job openings/i, higherIsCurrencyPositive:true, labelKey:'ruleJolts', employmentFamily:true},
  {re:/adp employment|adp non-?farm/i, higherIsCurrencyPositive:true, labelKey:'ruleAdp', employmentFamily:true},
  {re:/challenger.*job cuts|job cuts/i, higherIsCurrencyPositive:false, labelKey:'ruleChallenger', employmentFamily:true},
  {re:/cpi|inflation/i, higherIsCurrencyPositive:true, labelKey:'ruleCpi'},
  {re:/gdp/i, higherIsCurrencyPositive:true, labelKey:'ruleGdp'},
  {re:/retail sales/i, higherIsCurrencyPositive:true, labelKey:'ruleRetail'},
  {re:/pmi/i, higherIsCurrencyPositive:true, labelKey:'rulePmi'},
  {re:/interest rate|rate decision/i, higherIsCurrencyPositive:true, labelKey:'ruleRate'},
  {re:/trade balance/i, higherIsCurrencyPositive:true, labelKey:'ruleTrade'},
 ];
 function classify(name){ for(const r of RULES){ if(r.re.test(name||'')) return r; } return null; }
 // Sembol fiyatı üzerindeki etki yönü para birimine göre TERS olabilir: USD hem XAUUSD hem EURUSD'de
 // karşı/quote para birimidir (USD güçlenirse ikisi de düşer), ama EUR, EURUSD'de TABAN (base) para
 // birimidir (EUR güçlenirse EURUSD YÜKSELİR) — bu yüzden tek bir yön formülü kullanmıyoruz.
 const CCY_EFFECT = { US: {'OANDA:XAUUSD': -1, 'OANDA:EURUSD': -1}, EU: {'OANDA:EURUSD': 1} };
 function countryFlag(c){return {US:'🇺🇸',EU:'🇪🇺',DE:'🇩🇪',GB:'🇬🇧',JP:'🇯🇵',CN:'🇨🇳',TR:'🇹🇷'}[c]||'🌐';}
 // Üstteki akan şeritteki ekonomik not — GERÇEK takvim verisi (Finnhub canlı ya da manuel giriş)
 // varsa en yakın olayı gösterir; yoksa sahte bir sayı UYDURMAK yerine dürüst bir yönlendirme kalır.
 function updateTickerEconNote(events){
  const el=document.getElementById('tkEconNote'); if(!el) return;
  const now=new Date();
  const upcoming=(events||[]).filter(ev=>ev.time && new Date(ev.time)>=now).sort((a,b)=>a.time.localeCompare(b.time))[0];
  if(upcoming){
   const timeStr=fmtTime(upcoming.time);
   el.textContent=t('tickerNextEvent')(countryFlag(upcoming.country), upcoming.event||t('defaultEventName'), timeStr);
  } else {
   el.textContent=t('tickerEconFallback');
  }
 }
 function impStars(imp){return imp==='high'?('★★★ '+t('newsHigh')):('★★ '+t('newsMed'));}
 function fmtTime(tm){ if(!tm) return '—'; try{ return new Date(tm).toISOString().slice(11,16)+' UTC'; }catch(e){ return tm; } }

 // ---- Manuel haber girişi: TradingView takviminden okuyup buraya girilen 3 yıldızlı haberler.
 // Aynı senaryo motoru (RULES/classify) bunları da otomatik işler — kaynak farklı, analiz aynı. ----
 const MANUAL_KEY='valens_manual_news';
 function loadManualNews(){
  try{
   const raw=localStorage.getItem(MANUAL_KEY); let arr=raw?JSON.parse(raw):[];
   const cutoff=Date.now()-2*86400000; // 2 günden eski girdiler otomatik temizlenir
   arr=arr.filter(e=>{ const t2=new Date(e.time).getTime(); return isNaN(t2)?true:t2>=cutoff; });
   return arr;
  }catch(e){ return []; }
 }
 function saveManualNews(arr){ try{ localStorage.setItem(MANUAL_KEY, JSON.stringify(arr)); }catch(e){} }
 function getAllNewsEvents(){
  const finnhub = ECON.available ? (ECON.events||[]) : [];
  const manual = loadManualNews();
  return finnhub.concat(manual).sort((a,b)=>(a.time||'').localeCompare(b.time||''));
 }

 function renderNews(){
  const box=document.getElementById('newsEvents'), badge=document.getElementById('newsBadge');
  const events=getAllNewsEvents();
  updateTickerEconNote(events);
  if(!events.length){
   badge.textContent=t('newsCountBadge')(0);
   let extra='';
   if(!ECON.available){
    extra='<p style="color:var(--muted);font-size:9px;padding:0 9px 6px;line-height:1.5">'+(ECON.reason==='tier_gated'?t('newsTierGated'):'')+'</p>';
   }
   box.innerHTML='<p style="color:var(--muted);font-size:10px;padding:9px">'+t('manualNewsEmpty')+'</p>'+extra;
   return;
  }
  badge.textContent=t('newsCountBadge')(events.length);
  let html='';
  events.forEach((ev,idx)=>{
   const rule=classify(ev.event);
   const label=rule?t(rule.labelKey):null;
   const isRate = rule && rule.labelKey==='ruleRate';
   const released = ev.actual!==null && ev.actual!==undefined && ev.actual!=='';
   const removeBtn = ev.manual ? '<a href="#" class="mnRemove" data-idx="'+idx+'" style="color:var(--red);font-size:8px;margin-left:6px;text-decoration:none">✕ '+t('manualNewsRemove')+'</a>' : '';
   html+='<article class="event"><div class="eventtop">'+countryFlag(ev.country)+' <b>'+(ev.event||t('defaultEventName'))+'<span class="imp">'+impStars(ev.impact)+'</span></b><time>'+fmtTime(ev.time)+removeBtn+'</time></div><div class="eventbody">';
   html+='<p>'+t('newsExpectLbl')+': <strong>'+(ev.estimate??'—')+'</strong> · '+t('newsPrevLbl')+': '+(ev.prev??'—')+(released?(' · '+t('newsActualLbl')+': <strong>'+ev.actual+'</strong>'):'')+'</p>';
   if(isRate){
    // Faiz kararları için basit "beklenti üstü/altı" mantığı YANILTICI olabilir: karar genelde piyasa
    // tarafından zaten büyük ölçüde fiyatlanmıştır (ör. CME FedWatch olasılıkları). Asıl fiyatı hareket
    // ettiren şey çoğu zaman rakamın kendisi değil; (1) piyasanın önceden fiyatladığı olasılıkla ne kadar
    // örtüştüğü, (2) komite oylamasındaki muhalefet/şahin-güvercin dağılımı, (3) açıklama metninin ve
    // basın toplantısının TONU'dur — bunların hiçbiri actual/forecast rakamından okunamaz.
    html+='<p style="font-size:9px;color:var(--muted)">'+t('rateDecisionNote')+'</p>';
   } else if(!rule){
    html+='<p style="font-size:9px;color:var(--muted)">'+t('newsNoTemplate')+'</p>';
   } else if(released){
    const est=parseFloat(ev.estimate), act=parseFloat(ev.actual);
    if(!isNaN(est)&&!isNaN(act)&&est!==act){
     const beat=act>est, ccyPos=rule.higherIsCurrencyPositive?beat:!beat;
     const extra = ev.country==='US' ? (ccyPos?t('xauPressureNote'):t('xauSupportNote')) : '';
     html+='<div class="scenario '+(ccyPos?'bull':'bear')+'">'+t('newsCcyResult')(ccyPos?'▲':'▼', ev.country, label, beat?t('newsBeat'):t('newsMiss'), ccyPos?t('ccyStrengthens'):t('ccyWeakens'), extra)+'</div>';
    } else { html+='<p style="font-size:9px;color:var(--muted)">'+t('newsSame')+'</p>'; }
   } else {
    const extraBull = ev.country==='US' ? t('xauPressureScenario') : '.';
    const extraBear = ev.country==='US' ? t('xauSupportScenario') : '.';
    html+='<div class="scenario bull">'+t('newsScenarioBeat')(label, ev.country, extraBull)+'</div>';
    html+='<div class="scenario bear">'+t('newsScenarioMiss')(label, ev.country, extraBear)+'</div>';
   }
   if(rule && rule.employmentFamily){ html+='<p style="font-size:8px;color:var(--muted);margin-top:5px;line-height:1.5">'+t('employmentFamilyNote')+'</p>'; }
   html+='</div></article>';
  });
  box.innerHTML=html;
  box.querySelectorAll('.mnRemove').forEach(a=>a.addEventListener('click', e=>{
   e.preventDefault();
   const idx=parseInt(a.dataset.idx,10);
   const all=getAllNewsEvents(); const target=all[idx];
   let manual=loadManualNews();
   manual=manual.filter(m=>!(m.time===target.time && m.event===target.event));
   saveManualNews(manual);
   renderNews(); computeNewsBias();
  }));
 }
 window.valensRenderNews = renderNews;

 function computeNewsBias(){
  const bias={}, detail={}, todayStr=new Date().toISOString().slice(0,10);
  getAllNewsEvents().forEach(ev=>{
   if(!ev.time || !ev.time.startsWith(todayStr)) return; // sadece BUGÜN gerçekleşen/gerçekleşecek haberler
   const released = ev.actual!==null && ev.actual!==undefined && ev.actual!=='';
   if(!released) return; // gerçekleşmemiş haberin yönünü önceden bilemeyiz — tahmin uydurmuyoruz
   const rule=classify(ev.event); if(!rule) return;
   const est=parseFloat(ev.estimate), act=parseFloat(ev.actual);
   if(isNaN(est)||isNaN(act)||est===act) return;
   const beat=act>est, ccyPos=rule.higherIsCurrencyPositive?beat:!beat, w=ev.impact==='high'?0.6:0.3;
   const effects=CCY_EFFECT[ev.country]||{};
   Object.keys(effects).forEach(sym=>{
    const dir = ccyPos? effects[sym] : -effects[sym];
    bias[sym]=(bias[sym]||0)+dir*w;
    detail[sym]=detail[sym]||[]; detail[sym].push((ev.event||t('newsData'))+' ('+(beat?t('newsBeatUp'):t('newsBeatDown'))+')');
   });
  });
  Object.keys(bias).forEach(sym=>{ bias[sym]=Math.max(-1,Math.min(1,bias[sym])); });
  window.valensNewsBias=bias; window.valensNewsDetail=detail;
 }
 window.valensComputeNewsBias = computeNewsBias;

 // ---- Formdan ekleme/temizleme ----
 (function wireManualNewsForm(){
  const addBtn=document.getElementById('mnAdd'), clearBtn=document.getElementById('mnClear');
  if(!addBtn) return;
  addBtn.addEventListener('click', ()=>{
   const nameEl=document.getElementById('mnEvent');
   const name=(nameEl.value||'').trim();
   if(!name){ alert(t('manualNewsNeedName')); return; }
   const ev={
    time: new Date().toISOString(),
    country: document.getElementById('mnCountry').value,
    event: name,
    impact: 'high',
    estimate: document.getElementById('mnEstimate').value || null,
    prev: document.getElementById('mnPrev').value || null,
    actual: document.getElementById('mnActual').value || null,
    manual: true
   };
   const arr=loadManualNews(); arr.push(ev); saveManualNews(arr);
   ['mnEvent','mnEstimate','mnPrev','mnActual'].forEach(id=>document.getElementById(id).value='');
   renderNews(); computeNewsBias();
  });
  clearBtn.addEventListener('click', ()=>{
   if(!confirm(t('manualClearConfirm'))) return;
   saveManualNews([]);
   renderNews(); computeNewsBias();
  });
 })();


 renderNews();
 computeNewsBias();
})();
</script>

<script>
/* ============ VALENS CANLI GRAFİK + OTOMATİK ÇİZİM MOTORU + GERÇEK İNDİKATÖR HESABI ============ */
(function(){
 const el=document.getElementById('valensChart');
 if(!el||!window.LightweightCharts)return;
 const MAP={'OANDA:XAUUSD':'PAXGUSDT','BINANCE:BTCUSDT':'BTCUSDT','OANDA:EURUSD':'EURUSDT','OANDA:SPX500USD':null};
 // Zaman dilimi butonu değeri -> gerçek Binance kline aralığı. Önceden bu eşleme YOKTU, interval her
 // zaman sabit "15m" kalıyordu — hangi butona basılırsa basılsın veri hiç değişmiyordu.
 const INTERVAL_MAP={'1':'1m','15':'15m','30':'30m','60':'1h','240':'4h','D':'1d'};
 function currentBinInterval(){ return INTERVAL_MAP[(typeof INT!=='undefined'?INT:'15')] || '15m'; }

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
 // ATR bazlı volatilite zarfı (Keltner-tarzı) — trend yönüne göre renk değiştirir (TradingView referansınızdaki gibi)
 const kelUp=chart.addLineSeries({color:'rgba(0,200,150,.55)',lineWidth:1,lastValueVisible:false,priceLineVisible:false});
 const kelLo=chart.addLineSeries({color:'rgba(0,200,150,.55)',lineWidth:1,lastValueVisible:false,priceLineVisible:false});
 const resize=()=>{ chart.applyOptions({width:el.clientWidth,height:el.clientHeight}); if(typeof positionMainSRZones==='function') positionMainSRZones(); };
 // Önceden fitContent() TÜM (1000'e kadar) mumu sığdırıyordu — bu da her mumu çok ince/görünmez
 // yapıyordu, kullanıcı her açılışta manuel yakınlaştırmak zorunda kalıyordu. Artık açılışta sadece
 // son ~120 mumu (okunaklı bir yakınlık) gösteriyoruz; kullanıcı isterse kendisi uzaklaştırabilir.
 function showRecentRange(){
  const n=ohlc.length; if(n<2) return;
  const visibleCount=Math.min(120, n);
  try{ chart.timeScale().setVisibleLogicalRange({from:n-visibleCount, to:n-1}); }
  catch(e){ chart.timeScale().fitContent(); } // beklenmedik bir durumda güvenli yedek
 }
 window.addEventListener('resize',resize); setTimeout(resize,150);

 let ohlc=[],ws=null,tradeWs=null,binSym=null,curSym=null,srLines=[],fibLines=[],dynSup,dynRes,patternMarkers=[],zoneLines=[],fvgZoneLines=[],fvgMarker=null;
 // patternMarkers (mum formasyonları) VE fvgMarker (FVG giriş noktası) aynı cs.setMarkers() çağrısını
 // paylaşıyor — lightweight-charts setMarkers() önceki listeyi tamamen DEĞİŞTİRİR, birleştirmez.
 // Bu yüzden ikisini de tutan tek bir yer olmalı, yoksa biri diğerini görünmez şekilde silerdi.
 function refreshAllMarkers(){
  const all = fvgMarker ? patternMarkers.concat([fvgMarker]).sort((a,b)=>a.time-b.time) : patternMarkers;
  cs.setMarkers(all);
 }
 // ---- HAFTA SONU/KAPALI PİYASA MUM RENKLENDİRMESİ — kullanıcı gerçek ekran görüntüsüyle gösterdi:
 // XAU/USD piyasası GERÇEKTE kapalıyken (hafta sonu), grafiğimiz PAXG'nin (7/24 açık kripto) hareketini
 // göstermeye devam ediyor ve bu, gerçek altınla hiç ilgisi olmayan sahte bir teknik görünüm (kırılan
 // destekler, oluşan trendler) yaratıp YANILTICI oluyordu. BTC hariç (o zaten gerçekten 7/24 açık),
 // gerçek piyasası kapalı sembollerde o saatlerdeki mumları SOLUK GRİ render ediyoruz — "bu gerçek
 // piyasa hareketi değil" görsel olarak apaçık olsun diye.
 function isClosedMarketTime(sym, t){
  if(sym==='BINANCE:BTCUSDT') return false;
  return window.valensIsMarketOpen ? !window.valensIsMarketOpen(sym, t) : false;
 }
 function styledCandle(c, sym){
  if(!isClosedMarketTime(sym, c.time)) return c;
  const muted='#4a5568';
  return Object.assign({}, c, {color:muted, borderColor:muted, wickColor:muted});
 }
 function styledCandles(arr, sym){ return arr.map(c=>styledCandle(c, sym)); }
 // "Ana destek/direnç" HER ZAMAN 1 saatlik mumlardan hesaplanır (kullanıcı hangi zaman dilimini
 // izlerse izlesin) — "scalp" destek/direnç ise o an izlenen aralığın kendi dinamik S/R'ıdır.
 let mainSRZones=[], mainSRZoneEls=[], mainSRHistory=[], mainSRHistoryLines=[];
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
 // ---- SAATLİK TİPİK HAREKET TAHMİNİ — scalp hedefinin "gerçekçi sürede ulaşılabilir" olup olmadığını
 // kontrol etmek için kullanılır. ATR tek başına BÜYÜKLÜĞÜ söyler ama NE KADAR SÜREDE kat edileceğini
 // söylemez — bu yüzden son birkaç saatin GERÇEK kapanış-kapanış hareketini saat başına ortalıyoruz.
 function estimateHourlyMovement(candles){
  if(candles.length<10) return null;
  const w=candles.slice(-40); // yeterli örneklem
  const totalSeconds=w[w.length-1].time-w[0].time;
  if(totalSeconds<=0) return null;
  const totalHours=totalSeconds/3600;
  let totalMovement=0;
  for(let i=1;i<w.length;i++) totalMovement+=Math.abs(w[i].close-w[i-1].close);
  return totalHours>0 ? totalMovement/totalHours : null;
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
 // ---- ÜÇ ADLANDIRILMIŞ, İYİ BELGELENMİŞ SCALPING KALIBI ----
 // "5dk/15dk scalping" türünde YouTube'da neredeyse evrensel öğretilen üç standart teknik:
 // (1) hızlı EMA kesişimi + MACD/RSI teyidi, (2) seans açılışı aralık kırılımı (ORB),
 // (3) ardışık aynı yönlü mum + kırılım momentumu. Skoru bunlar DEĞİL, mevcut 15-oy sistemi belirliyor —
 // bunlar sadece "bu sinyal hangi bilinen kalıba uyuyor" diye ETİKETLEME amaçlıdır.
 function detectORB(a){
  const opens=[8,13]; // London, New York açılışı (UTC)
  const lastTime=a[a.length-1].time;
  const now=new Date(lastTime*1000);
  for(const openHour of opens){
   const sessionOpen=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),openHour,0,0)/1000;
   if(lastTime<sessionOpen) continue;
   const sessionCandles=a.filter(c=>c.time>=sessionOpen);
   if(sessionCandles.length<4 || sessionCandles.length>20) continue;
   const rangeCandles=sessionCandles.slice(0,3);
   const hi=Math.max(...rangeCandles.map(c=>c.high)), lo=Math.min(...rangeCandles.map(c=>c.low));
   const lastC=sessionCandles[sessionCandles.length-1];
   if(lastC.close>hi) return {key:'orb', dir:1};
   if(lastC.close<lo) return {key:'orb', dir:-1};
  }
  return null;
 }
 // ---- ORB SCALP VARYANTI: tek mumluk (3 değil), daha dar bir açılış aralığı kullanır ve kapanış
 // onayı BEKLEMEDEN fitil (wick) aralığı aşar aşmaz tetiklenir — daha hızlı, daha sık, ama daha
 // gürültülü. Geniş/onaylı ORB ile birlikte "birbirini dengeleyen çeşitli ORB varyantları" fikrini
 // uygular; ikisi FARKLI koşullarda ateşlenip birbirini tamamlar, aynı sinyali tekrar etmez. ----
 function detectScalpORB(a){
  const opens=[8,13];
  const lastTime=a[a.length-1].time;
  const now=new Date(lastTime*1000);
  for(const openHour of opens){
   const sessionOpen=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),openHour,0,0)/1000;
   if(lastTime<sessionOpen) continue;
   const sessionCandles=a.filter(c=>c.time>=sessionOpen);
   if(sessionCandles.length<2 || sessionCandles.length>6) continue; // sadece açılıştan hemen sonraki birkaç mum
   const rangeCandle=sessionCandles[0]; // TEK mumluk dar aralık (geniş varyant 3 mum kullanıyor)
   const curr=sessionCandles[sessionCandles.length-1];
   if(curr===rangeCandle) continue;
   if(curr.high>rangeCandle.high) return {key:'scalpOrb', dir:1};
   if(curr.low<rangeCandle.low) return {key:'scalpOrb', dir:-1};
  }
  return null;
 }
 // ---- ORB SÜPÜRME-GERİ DÖNÜŞ (video kaynaklarından): açılış aralığının bir ucu SÜPÜRÜLÜP (sahte kırılım)
 // fiyat aralığın İÇİNE geri kapandığında, aralığın KARŞI ucuna doğru bir "fade" (geri dönüş) işlemi —
 // mevcut ORB (devam) varyantlarının TERSİ bir mantık: kırılımı takip etmek yerine, kırılımın sahte
 // olduğunu doğrulayıp tersine oynuyor. ----
 function detectORBSweepFade(a){
  const opens=[8,13];
  const lastTime=a[a.length-1].time;
  const now=new Date(lastTime*1000);
  for(const openHour of opens){
   const sessionOpen=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),openHour,0,0)/1000;
   if(lastTime<sessionOpen) continue;
   const sessionCandles=a.filter(c=>c.time>=sessionOpen);
   if(sessionCandles.length<3 || sessionCandles.length>12) continue;
   const rangeCandle=sessionCandles[0];
   const hi=rangeCandle.high, lo=rangeCandle.low;
   const curr=sessionCandles[sessionCandles.length-1];
   if(curr===rangeCandle) continue;
   if(curr.low<lo && curr.close>lo && curr.close>curr.open) return {key:'orbSweepFade', dir:1};
   if(curr.high>hi && curr.close<hi && curr.close<curr.open) return {key:'orbSweepFade', dir:-1};
  }
  return null;
 }
 // ---- PİYASA YAPISI: BOS (Break of Structure) / CHoCH (Change of Character) — SMC'nin temel kavramı.
 // Basit bir pivot (swing) tespitiyle son 2 swing high/low'un HH+HL mi (yükseliş yapısı) yoksa LH+LL mi
 // (düşüş yapısı) oluşturduğuna bakılır. Mevcut yapı yönünde bir swing noktası kırılırsa BOS (devam),
 // TERS yönde kırılırsa CHoCH (karakter değişimi / olası dönüş, daha güçlü sinyal) sayılır. ----
 function findSwingPoints(a){
  const N=2, points=[];
  for(let i=N;i<a.length-N;i++){
   const c=a[i]; let isHigh=true, isLow=true;
   for(let j=i-N;j<=i+N;j++){ if(j===i) continue; if(a[j].high>=c.high) isHigh=false; if(a[j].low<=c.low) isLow=false; }
   if(isHigh) points.push({type:'high', price:c.high});
   if(isLow) points.push({type:'low', price:c.low});
  }
  return points;
 }
 // DÜZELTME (kullanıcının paylaştığı "This isn't A BOS!" videosu): findSwingPoints burada SADECE
 // son 44 mumdaki son 2 swing'e bakıyor — bu "INTERNAL" (yerel/küçük) bir yapı okumasıdır. Video
 // tam olarak şunu anlatıyor: küçük/yerel bir swing'in kırılması gerçek bir BOS SAYILMAZ, EĞER
 // daha büyük resimdeki (EXTERNAL) yapı hâlâ ters yöndeyse — o zaman bu sadece iç dalgalanma,
 // trend devamı değil. `detectSwingStructure(a,60)` (daha geniş pencere, daha büyük swing'ler)
 // buradaki EXTERNAL referans olarak kullanılıyor: internal kırılım EXTERNAL yapıyla AÇIKÇA
 // çelişiyorsa (ör. internal "yukarı kırıldı" derken external hâlâ net düşüşte) bosSignal hiç
 // üretilmiyor — CHoCH'a dokunulmuyor, çünkü CHoCH zaten TANIM GEREĞİ henüz external'a yansımamış
 // erken bir dönüş sinyalidir.
 function detectMarketStructure(a){
  if(a.length<35) return null;
  const points=findSwingPoints(a.slice(-45,-1));
  const highs=points.filter(p=>p.type==='high').slice(-2);
  const lows=points.filter(p=>p.type==='low').slice(-2);
  if(highs.length<2||lows.length<2) return null;
  const curr=a[a.length-1];
  const structUp = highs[1].price>highs[0].price && lows[1].price>lows[0].price;
  const structDown = highs[1].price<highs[0].price && lows[1].price<lows[0].price;
  const lastHigh=highs[highs.length-1], lastLow=lows[lows.length-1];
  const externalBias = detectSwingStructure(a, 60);
  if(structUp && curr.close>lastHigh.price){
   if(externalBias<0) return null; // internal "yukarı kırılım" ama EXTERNAL yapı hâlâ düşüşte — gerçek BOS değil
   return {key:'bosSignal', dir:1};
  }
  if(structUp && curr.close<lastLow.price) return {key:'chochSignal', dir:-1};
  if(structDown && curr.close<lastLow.price){
   if(externalBias>0) return null;
   return {key:'bosSignal', dir:-1};
  }
  if(structDown && curr.close>lastHigh.price) return {key:'chochSignal', dir:1};
  return null;
 }
 // ---- EŞİT TEPE/DİP (EQH/EQL) LİKİDİTE HAVUZU — birbirine çok yakın iki (veya daha fazla) tepe/dip,
 // üzerinde/altında dinlenen stop-loss'ların biriktiği bir "likidite havuzu" sayılır. Fiyat bu havuzu
 // süpürüp reddederse (kapanış geri içeri), klasik bir likidite avı dönüşü sinyali. ----
 function detectEqualHighsLows(a){
  if(a.length<20) return null;
  const window=a.slice(-15,-1), curr=a[a.length-1], tol=0.0015;
  const highs=window.map(c=>c.high);
  for(let i=0;i<highs.length;i++) for(let j=i+1;j<highs.length;j++){
   if(Math.abs(highs[i]-highs[j])/highs[i]<tol){
    const level=(highs[i]+highs[j])/2;
    if(curr.high>level*(1+tol) && curr.close<level && curr.close<curr.open) return {key:'equalHighsLows', dir:-1};
   }
  }
  const lows=window.map(c=>c.low);
  for(let i=0;i<lows.length;i++) for(let j=i+1;j<lows.length;j++){
   if(Math.abs(lows[i]-lows[j])/lows[i]<tol){
    const level=(lows[i]+lows[j])/2;
    if(curr.low<level*(1-tol) && curr.close>level && curr.close>curr.open) return {key:'equalHighsLows', dir:1};
   }
  }
  return null;
 }
 // ---- TRADES DELTA — video kaynağında adı geçen bir kavram: agresif alım hacmi ile agresif satım
 // hacmi arasındaki fark. Gerçek Binance aggTrade akışından (zaten whale-emir paneli için kullanılan
 // veri kaynağı) hesaplanır — GEX/Footprint/Heat Map gibi erişimimiz olmayan veri kaynaklarını taklit
 // etmiyoruz, sadece gerçekten elimizde olan veriden gerçek bir delta üretiyoruz. ----
 function detectTradeDelta(deltaValue){
  if(deltaValue==null) return null;
  if(deltaValue>0.35) return {key:'tradeDelta', dir:1};
  if(deltaValue<-0.35) return {key:'tradeDelta', dir:-1};
  return null;
 }
 // ---- DELTA DOĞRULAMA MATRİSİ — gözden geçirilen bir içerikten esinlenildi: fiyat yönü ile agresif
 // alım/satım hacmi (delta) yönü karşılaştırılır. Düz bir eşik yerine (eski detectTradeDelta) dört
 // farklı durumu ayırt eder: fiyat YUKARI + delta YUKARI = gerçek alım baskısı ("fonlanmış" hareket);
 // fiyat AŞAĞI + delta AŞAĞI = gerçek satış (karşı gitme); fiyat AŞAĞI + delta YUKARI = absorpsiyon
 // (biri satışı emiyor — genelde tükeniş/olası dönüş işareti); fiyat YUKARI + delta DÜZ = "kırılgan"
 // hareket (kimse gerçekten almıyor) — bu durumda yön ÜRETMİYORUZ, çünkü akış fiyatla çelişiyor. ----
 function detectDeltaConfirmation(a, deltaValue){
  if(deltaValue==null || a.length<6) return null;
  const curr=a[a.length-1], prior=a[a.length-6];
  const priceChangePct=(curr.close-prior.close)/prior.close;
  const priceUp=priceChangePct>0.0008, priceDown=priceChangePct<-0.0008;
  const deltaUp=deltaValue>0.15, deltaDown=deltaValue<-0.15;
  if(priceUp && deltaUp) return {key:'deltaConfirmTrend', dir:1};
  if(priceDown && deltaDown) return {key:'deltaConfirmTrend', dir:-1};
  if(priceDown && deltaValue>0.2) return {key:'deltaAbsorption', dir:1};
  if(priceUp && deltaValue<-0.2) return {key:'deltaAbsorption', dir:-1};
  return null;
 }
 // ==================== YENİ 10 KALIP (kullanıcı tarafından tarif edilen kurumsal/ICT stratejiler) ====================
 // ---- 1) SILVER BULLET: likidite süpürmesi (FİTİLLE, kapanışla değil) + arkasında taze bir FVG bırakan
 // güçlü ters yönlü kapanış. Mevcut Likidite Süpürme + FVG tespitlerinin BİRLEŞİMİ, tek başlarına
 // yakalayamayacakları daha seçici/güçlü bir kurulum. ----
 function detectSilverBullet(a, ema200, vwap){
  const sweep=detectLiquiditySweep(a, ema200, vwap);
  if(!sweep) return null;
  const fvgs=findFVGs(a, 5);
  const freshFvg=fvgs.some(f=>f.dir===sweep.dir);
  return freshFvg ? {key:'silverBullet', dir:sweep.dir} : null;
 }
 // ---- 2) ORB + HACİM ONAYI: mevcut geniş ORB'un (kapanış onaylı) hacim filtresiyle güçlendirilmiş hali —
 // kırılım anındaki hacim, son 20 mumun ortalamasının 2 katından fazla olmalı. ----
 function detectORBVolume(a){
  const opens=[8,13];
  const lastTime=a[a.length-1].time;
  const now=new Date(lastTime*1000);
  for(const openHour of opens){
   const sessionOpen=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),openHour,0,0)/1000;
   if(lastTime<sessionOpen) continue;
   const sessionCandles=a.filter(c=>c.time>=sessionOpen);
   if(sessionCandles.length<4 || sessionCandles.length>20) continue;
   const rangeCandles=sessionCandles.slice(0,3);
   const hi=Math.max(...rangeCandles.map(c=>c.high)), lo=Math.min(...rangeCandles.map(c=>c.low));
   const curr=sessionCandles[sessionCandles.length-1];
   const recentVols=a.slice(-21,-1).map(c=>c.volume||0);
   const avgVol=recentVols.reduce((s,v)=>s+v,0)/(recentVols.length||1);
   if((curr.volume||0) <= avgVol*2) continue;
   if(curr.close>hi) return {key:'orbVolume', dir:1};
   if(curr.close<lo) return {key:'orbVolume', dir:-1};
  }
  return null;
 }
 // ---- 3) VWAP GERİ ÇEKİLME: trend (EMA50 vs EMA200) + fiyat VWAP'a değip oradan bir dönüş mumuyla
 // (Hammer/Shooting Star/Engulf) tepki verir. ----
 function detectVwapPullback(a, ema50, ema200, vwap){
  if(a.length<3 || ema50==null || ema200==null || vwap==null) return null;
  const curr=a[a.length-1];
  const pat=pattern(a);
  if(!pat || pat.d==='neutral') return null;
  const touchedVwap = curr.low<=vwap*1.0015 && curr.high>=vwap*0.9985;
  if(!touchedVwap) return null;
  if(ema50>ema200 && pat.d==='bull' && curr.close>vwap) return {key:'vwapPullback', dir:1};
  if(ema50<ema200 && pat.d==='bear' && curr.close<vwap) return {key:'vwapPullback', dir:-1};
  return null;
 }
 // ---- 4) TTM SQUEEZE: Bollinger Bantları Keltner Kanalı'nın TAMAMEN İÇİNE girdiğinde ("sıkışma"),
 // sonra dışarı taştığında ("patlama") — genel "en dar genişlik" tanımından daha kesin, klasik TTM
 // Squeeze tanımı (Bollinger içeri/dışarı Keltner'e göre). ----
 function detectTTMSqueeze(a, closes){
  const period=20;
  if(closes.length<period+16 || a.length<period+16) return null;
  function bollAt(idx){
   const w=closes.slice(idx-period+1,idx+1), sma=w.reduce((s,v)=>s+v,0)/period;
   const sd=Math.sqrt(w.reduce((s,v)=>s+(v-sma)**2,0)/period);
   return {upper:sma+sd*2, lower:sma-sd*2};
  }
  function keltnerAt(idx){
   const emaW=closes.slice(Math.max(0,idx-19),idx+1);
   let ema=emaW[0]; const kk=2/(20+1);
   emaW.forEach((c,i)=>{ ema = i? c*kk+ema*(1-kk) : c; });
   const trs=[];
   for(let j=Math.max(1,idx-13);j<=idx;j++){
    const cur=a[j], prev=a[j-1];
    trs.push(Math.max(cur.high-cur.low, Math.abs(cur.high-prev.close), Math.abs(cur.low-prev.close)));
   }
   const atrV=trs.reduce((s,v)=>s+v,0)/(trs.length||1);
   return {upper:ema+atrV*1.5, lower:ema-atrV*1.5};
  }
  const n=closes.length;
  const bollPrev=bollAt(n-2), kelPrev=keltnerAt(n-2);
  const bollNow=bollAt(n-1), kelNow=keltnerAt(n-1);
  const squeezedPrev = bollPrev.upper<kelPrev.upper && bollPrev.lower>kelPrev.lower;
  const firedNow = bollNow.upper>=kelNow.upper || bollNow.lower<=kelNow.lower;
  if(!squeezedPrev || !firedNow) return null;
  const curr=a[a.length-1];
  if(curr.close>curr.open) return {key:'ttmSqueeze', dir:1};
  if(curr.close<curr.open) return {key:'ttmSqueeze', dir:-1};
  return null;
 }
 // ---- 5) RSI UYUMSUZLUĞU + CHoCH: mevcut iki bağımsız tespitin (RSI Uyumsuzluğu + Piyasa Yapısı
 // CHoCH) AYNI YÖNDE aynı anda gerçekleşmesi — tek başlarına olduğundan daha seçici bir dönüş sinyali. ----
 function detectDivergenceChoch(a, rsiSeries){
  const div=detectRSIDivergence(a, rsiSeries);
  if(!div) return null;
  const struct=detectMarketStructure(a);
  if(struct && struct.key==='chochSignal' && struct.dir===div.dir) return {key:'divergenceChoch', dir:div.dir};
  return null;
 }
 // ---- 6) HACİM PROFİLİ (VPVR) — POC SEKMESİ: son ~24 saatte en çok hacmin işlem gördüğü fiyat
 // seviyesi (Point of Control) hesaplanır; fiyat buraya gelip reddederse (iğne atıp tepki verirse)
 // "hacim mıknatısı" sekmesi sayılır. ----
 function detectPOCBounce(a){
  const lookback=96;
  if(a.length<lookback+2) return null;
  const window=a.slice(-lookback-1,-1);
  const lo=Math.min(...window.map(c=>c.low)), hi=Math.max(...window.map(c=>c.high));
  const bins=24, binSize=(hi-lo)/bins;
  if(!(binSize>0)) return null;
  const volByBin=new Array(bins).fill(0);
  window.forEach(c=>{
   const mid=(c.high+c.low)/2;
   let idx=Math.floor((mid-lo)/binSize);
   idx=Math.max(0,Math.min(bins-1,idx));
   volByBin[idx]+=(c.volume||0);
  });
  let maxIdx=0; for(let i=1;i<bins;i++) if(volByBin[i]>volByBin[maxIdx]) maxIdx=i;
  const poc=lo+(maxIdx+0.5)*binSize;
  const curr=a[a.length-1];
  if(Math.abs(curr.close-poc)/poc>=0.004) return null;
  if(curr.low<=poc && curr.close>poc && curr.close>curr.open) return {key:'pocBounce', dir:1};
  if(curr.high>=poc && curr.close<poc && curr.close<curr.open) return {key:'pocBounce', dir:-1};
  return null;
 }
 // ---- ÖNCEKİ GÜN SEVİYELERİ (POC/VAH/VAL/Yüksek/Düşük) + SEVİYE CONFLUENCE ——
 // Gözden geçirilen bir içerikten esinlenildi: "gerçek" referans seviyeleri sadece ÖNCEKİ TAM günün
 // hacim profilinden (kayan bir pencere değil) hesaplanır — POC (en çok hacmin işlem gördüğü tek
 // fiyat), VAH/VAL (POC'tan başlayıp hacmin %70'ine ulaşana kadar iki yöne genişletilen "değer alanı"
 // sınırları, standart yöntem) + önceki günün yüksek/düşüğü. Bu 5 seviyeden İKİSİ birbirine yakınsa
 // ("confluence"), bu güçlü bir bölge sayılır — fiyat orayı süpürüp geri alırsa sıradan bir POC
 // sekmesinden daha seçici/güçlü bir sinyaldir.
 function computePriorDayLevels(a){
  if(a.length<60) return null;
  const lastTime=a[a.length-1].time;
  const now=new Date(lastTime*1000);
  const todayStart=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),0,0,0)/1000;
  const priorDayStart=todayStart-86400, priorDayEnd=todayStart;
  const priorCandles=a.filter(c=>c.time>=priorDayStart && c.time<priorDayEnd);
  if(priorCandles.length<10) return null;
  const hi=Math.max(...priorCandles.map(c=>c.high)), lo=Math.min(...priorCandles.map(c=>c.low));
  const bins=30, binSize=(hi-lo)/bins;
  if(!(binSize>0)) return null;
  const volByBin=new Array(bins).fill(0);
  priorCandles.forEach(c=>{
   const mid=(c.high+c.low)/2;
   let idx=Math.floor((mid-lo)/binSize);
   idx=Math.max(0,Math.min(bins-1,idx));
   volByBin[idx]+=(c.volume||0);
  });
  const totalVol=volByBin.reduce((s,v)=>s+v,0);
  if(totalVol<=0) return null;
  let maxIdx=0; for(let i=1;i<bins;i++) if(volByBin[i]>volByBin[maxIdx]) maxIdx=i;
  const poc=lo+(maxIdx+0.5)*binSize;
  // VAH/VAL: standart yöntem — POC'tan başlayıp toplam hacmin %70'ine ulaşana kadar HANGİ komşu bin
  // daha yüksek hacimliyse o yöne bir bin daha genişlet.
  let included=volByBin[maxIdx], lowIdx=maxIdx, highIdx=maxIdx;
  while(included<totalVol*0.7 && (lowIdx>0||highIdx<bins-1)){
   const nextLow=lowIdx>0?volByBin[lowIdx-1]:-1, nextHigh=highIdx<bins-1?volByBin[highIdx+1]:-1;
   if(nextHigh>=nextLow && highIdx<bins-1){ highIdx++; included+=volByBin[highIdx]; }
   else if(lowIdx>0){ lowIdx--; included+=volByBin[lowIdx]; }
   else break;
  }
  return {poc, vah:lo+(highIdx+1)*binSize, val:lo+lowIdx*binSize, high:hi, low:lo};
 }
 function detectLevelConfluenceReversal(a, priorDay){
  if(!priorDay || a.length<15) return null;
  const curr=a[a.length-1];
  // 'vah','val' etiketiyle tutuyoruz ki VAH-VAL çiftini (aynı değer alanının iki doğal kenarı —
  // her zaman birbirine yakındır, eşleştirmek anlamsız/gereksiz sinyal üretir) hariç tutabilelim.
  const levels=[['poc',priorDay.poc],['vah',priorDay.vah],['val',priorDay.val],['high',priorDay.high],['low',priorDay.low]];
  const tol=curr.close*0.0025;
  let bigLevels=[];
  for(let i=0;i<levels.length;i++) for(let j=i+1;j<levels.length;j++){
   const [nameI,valI]=levels[i], [nameJ,valJ]=levels[j];
   if(nameI==='vah' && nameJ==='val') continue; // aynı değer alanının doğal iki kenarı, anlamsız eşleşme
   if(Math.abs(valI-valJ)<tol) bigLevels.push((valI+valJ)/2);
  }
  if(!bigLevels.length) return null;
  for(const lvl of bigLevels){
   // Kır → geri dön → karar ver: fiyat seviyeyi fitille geçip KAPANIŞLA geri alırsa (red/reclaim)
   if(curr.low<lvl-tol*0.4 && curr.close>lvl && curr.close>curr.open) return {key:'levelConfluence', dir:1};
   if(curr.high>lvl+tol*0.4 && curr.close<lvl && curr.close<curr.open) return {key:'levelConfluence', dir:-1};
  }
  return null;
 }
 // ---- 7) ORDER BLOCK MİTİGASYONU — büyük bir hareketten (impulse) hemen önceki SON ters yönlü mum,
 // "kurumsal emir bloğu" sayılır. Fiyat ileride bu bloğa geri dönüp reddederse mitigasyon sinyali. ----
 function findOrderBlocks(a, lookback){
  const w=a.slice(-lookback-3,-1), obs=[];
  for(let i=1;i<w.length-1;i++){
   const c=w[i], next=w[i+1];
   const moveSize=Math.abs(next.close-next.open);
   const avgRange=(w[i-1]?Math.abs(w[i-1].high-w[i-1].low):moveSize)||1e-9;
   if(moveSize>avgRange*1.8){
    if(next.close>next.open && c.close<c.open) obs.push({dir:1, top:c.high, bottom:c.low});
    if(next.close<next.open && c.close>c.open) obs.push({dir:-1, top:c.high, bottom:c.low});
   }
  }
  return obs;
 }
 function detectOrderBlockMitigation(a){
  if(a.length<20) return null;
  const obs=findOrderBlocks(a, 20), curr=a[a.length-1];
  for(let i=obs.length-1;i>=0;i--){
   const ob=obs[i];
   if(ob.dir>0 && curr.low<=ob.top && curr.low>=ob.bottom*0.998 && curr.close>ob.top && curr.close>curr.open) return {key:'orderBlockMit', dir:1};
   if(ob.dir<0 && curr.high>=ob.bottom && curr.high<=ob.top*1.002 && curr.close<ob.bottom && curr.close<curr.open) return {key:'orderBlockMit', dir:-1};
  }
  return null;
 }
 // ---- OB+FVG CONFLUENCE (kullanıcının paylaştığı "Confused by SMC" eskizi) — bir Order Block
 // ile bir FVG'nin ÇAKIŞTIĞI (üst üste bindiği) bölge, ikisinden ayrı ayrı daha güçlü bir giriş
 // noktası sayılır — eskizde tam olarak bu: FVG kutusu, Bullish OB kutusunun hemen üzerinde/
 // çakışık çiziliyor, BOS sonrası oluşuyor. İki bağımsız kalıbın AYNI bölgede AYNI yönde
 // birleşmesi, tek başına ikisinden daha yüksek olasılıklı bir giriş sayılır.
 function detectObFvgConfluence(a){
  if(a.length<25) return null;
  const obs=findOrderBlocks(a,20), fvgs=findFVGs(a,20), curr=a[a.length-1];
  for(let i=obs.length-1;i>=0;i--){
   const ob=obs[i];
   for(let j=fvgs.length-1;j>=0;j--){
    const f=fvgs[j];
    if(f.dir!==ob.dir) continue;
    const overlapTop=Math.min(ob.top,f.top), overlapBottom=Math.max(ob.bottom,f.bottom);
    if(overlapTop<=overlapBottom) continue; // gerçek bir çakışma yok
    if(ob.dir>0 && curr.low<=overlapTop && curr.close>overlapBottom && curr.close>curr.open){
     return {key:'obFvgConfluence', dir:1, zone:{top:overlapTop, bottom:overlapBottom}};
    }
    if(ob.dir<0 && curr.high>=overlapBottom && curr.close<overlapTop && curr.close<curr.open){
     return {key:'obFvgConfluence', dir:-1, zone:{top:overlapTop, bottom:overlapBottom}};
    }
   }
  }
  return null;
 }
 // ---- 8) FİBONACCİ OTE (Optimal Trade Entry): mevcut fibZone hesaplamasından ("golden" 0.5-0.618 ya da
 // "deep" 0.786+ bölgeleri) yararlanır — trend yönünde bu bölgeye çekilme + dönüş mumu birlikte arar. ----
 function detectFibOTE(a, fibZoneVal, ema200){
  if(!fibZoneVal || (fibZoneVal!=='golden' && fibZoneVal!=='deep') || ema200==null) return null;
  const curr=a[a.length-1];
  const pat=pattern(a);
  if(!pat || pat.d==='neutral') return null;
  if(curr.close>ema200 && pat.d==='bull') return {key:'fibOte', dir:1};
  if(curr.close<ema200 && pat.d==='bear') return {key:'fibOte', dir:-1};
  return null;
 }
 // ---- 9) ASYA ARALIĞI KILLZONE SAHTE KIRILIMI — Asya seansının (22:00-07:00 UTC) TAM aralığı çizilir;
 // Londra/NY açılışında bu aralığın bir ucu sahte kırılıp geri içeri kapanırsa ters yönde sinyal. ----
 function detectAsianRangeFakeout(a){
  const lastTime=a[a.length-1].time;
  const now=new Date(lastTime*1000);
  let asianOpen=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),22,0,0)/1000;
  if(lastTime<asianOpen) asianOpen-=86400;
  const asianClose=asianOpen+9*3600;
  if(lastTime<asianClose) return null;
  const asianCandles=a.filter(c=>c.time>=asianOpen && c.time<asianClose);
  if(asianCandles.length<10) return null;
  const hi=Math.max(...asianCandles.map(c=>c.high)), lo=Math.min(...asianCandles.map(c=>c.low));
  const postCandles=a.filter(c=>c.time>=asianClose);
  if(postCandles.length<1 || postCandles.length>8) return null;
  const curr=postCandles[postCandles.length-1];
  if(curr.high>hi && curr.close<hi && curr.close<curr.open) return {key:'asianFakeout', dir:-1};
  if(curr.low<lo && curr.close>lo && curr.close>curr.open) return {key:'asianFakeout', dir:1};
  return null;
 }
 // ---- 10) AŞIRI ORTALAMAYA DÖNÜŞ — fiyat 3 standart sapma dışına taşar (çok nadir) + RSI 15 altı/85
 // üstü + ilk dönüş mumu kapanır: istatistiksel bir uç noktadan "V" tipi dönüş. ----
 function detectExtremeMeanReversion(a, closes, rsiVal){
  const period=20;
  if(closes.length<period+2 || rsiVal==null) return null;
  const w=closes.slice(-period), sma=w.reduce((s,v)=>s+v,0)/period;
  const sd=Math.sqrt(w.reduce((s,v)=>s+(v-sma)**2,0)/period);
  const upper3=sma+sd*3, lower3=sma-sd*3;
  const curr=a[a.length-1];
  if(curr.close<lower3 && rsiVal<15 && curr.close>curr.open) return {key:'extremeMeanReversion', dir:1};
  if(curr.close>upper3 && rsiVal>85 && curr.close<curr.open) return {key:'extremeMeanReversion', dir:-1};
  return null;
 }
 // ==================== 10 YENİ KALIP SONU ====================
 // ---- NO WICK (FİTİLSİZ MUM) GERİ TEST — klasik "Marubozu" kavramının bir uygulaması: gövdenin bir
 // ucunda neredeyse hiç fitil olmayan bir mum, o yönde güçlü/kararlı bir hareketi gösterir. Trend
 // yönünde bir "fitilsiz mum" oluşmuşsa ve fiyat sonradan o seviyeye geri dönüp reddedilirse (tekrar
 // trend yönünde kapanırsa) bu bir giriş noktası sayılır. ----
 function findNoWickCandles(a, lookback){
  const w=a.slice(-lookback-1,-1), out=[];
  w.forEach(c=>{
   const range=c.high-c.low||1e-9, bodyTop=Math.max(c.open,c.close), bodyBot=Math.min(c.open,c.close);
   const topWick=c.high-bodyTop, botWick=bodyBot-c.low, bull=c.close>c.open;
   if(bull && botWick/range<0.1) out.push({dir:1, level:c.low});
   if(!bull && topWick/range<0.1) out.push({dir:-1, level:c.high});
  });
  return out;
 }
 function detectNoWickRetest(a, ema200){
  if(a.length<20 || ema200==null) return null;
  const curr=a[a.length-1];
  const trend = curr.close>ema200?1:curr.close<ema200?-1:0;
  if(trend===0) return null;
  const noWicks=findNoWickCandles(a,15);
  for(let i=noWicks.length-1;i>=0;i--){
   const nw=noWicks[i];
   if(nw.dir!==trend) continue; // sadece trend yönündeki fitilsiz mumlar geçerli
   if(nw.dir>0 && curr.low<=nw.level*1.002 && curr.close>nw.level && curr.close>curr.open) return {key:'noWickRetest', dir:1};
   if(nw.dir<0 && curr.high>=nw.level*0.998 && curr.close<nw.level && curr.close<curr.open) return {key:'noWickRetest', dir:-1};
  }
  return null;
 }
 // ---- (5) RSI UYUMSUZLUĞU: fiyat yeni bir dip/tepe yaparken RSI onu teyit etmiyorsa momentum
 // zayıflıyor demektir — klasik dönüş sinyali. Gerçek RSI serisinden (tek değer değil) hesaplanır. ----
 function calcRSISeries(closes, period){
  const out=new Array(closes.length).fill(null);
  for(let i=period;i<closes.length;i++){
   let gains=0, losses=0;
   for(let j=i-period+1;j<=i;j++){ const d=closes[j]-closes[j-1]; if(d>=0)gains+=d; else losses-=d; }
   const avgGain=gains/period, avgLoss=losses/period;
   out[i]= avgLoss===0?100:100-100/(1+avgGain/avgLoss);
  }
  return out;
 }
 function detectRSIDivergence(a, rsiSeries){
  if(a.length<30) return null;
  const N=10;
  const recentWin=a.slice(-N), priorWin=a.slice(-2*N,-N);
  const rsiRecent=rsiSeries.slice(-N), rsiPrior=rsiSeries.slice(-2*N,-N);
  if(priorWin.length<N||recentWin.length<N) return null;
  const idxMax=(arr,key)=>arr.reduce((best,c,i)=>c[key]>arr[best][key]?i:best,0);
  const idxMin=(arr,key)=>arr.reduce((best,c,i)=>c[key]<arr[best][key]?i:best,0);
  const rHiIdx=idxMax(recentWin,'high'), pHiIdx=idxMax(priorWin,'high');
  const rsiAtRHi=rsiRecent[rHiIdx], rsiAtPHi=rsiPrior[pHiIdx];
  if(recentWin[rHiIdx].high>priorWin[pHiIdx].high && rsiAtRHi!=null && rsiAtPHi!=null && rsiAtRHi<rsiAtPHi && rsiAtRHi>55) return {key:'rsiDivergence', dir:-1};
  const rLoIdx=idxMin(recentWin,'low'), pLoIdx=idxMin(priorWin,'low');
  const rsiAtRLo=rsiRecent[rLoIdx], rsiAtPLo=rsiPrior[pLoIdx];
  if(recentWin[rLoIdx].low<priorWin[pLoIdx].low && rsiAtRLo!=null && rsiAtPLo!=null && rsiAtRLo>rsiAtPLo && rsiAtRLo<45) return {key:'rsiDivergence', dir:1};
  return null;
 }
 // ---- (6) BOLLINGER SIKIŞMASI + KIRILIMI: bant genişliği çok daralınca ("sıkışma") volatilite
 // birikir; ardından genişleme başlayan mumun yönü kırılım sinyali sayılır. ----
 function detectBollSqueeze(a, closes){
  const period=20, lookback=20;
  if(closes.length<period+lookback) return null;
  function widthAt(idx){
   if(idx<period-1) return null;
   const w=closes.slice(idx-period+1,idx+1), sma=w.reduce((a2,b)=>a2+b,0)/period;
   const sd=Math.sqrt(w.reduce((a2,b)=>a2+(b-sma)**2,0)/period);
   return sma?(4*sd)/sma:null;
  }
  const widths=[]; for(let i=closes.length-lookback-1;i<closes.length;i++) widths.push(widthAt(i));
  const valid=widths.filter(w=>w!=null);
  if(valid.length<lookback) return null;
  const currentW=valid[valid.length-1], prevW=valid[valid.length-2];
  const minW=Math.min(...valid.slice(0,-1));
  const wasSqueezed = prevW<=minW*1.05, nowExpanding = currentW>prevW*1.15;
  if(!wasSqueezed||!nowExpanding) return null;
  const curr=a[a.length-1];
  if(curr.close>curr.open) return {key:'bollSqueeze', dir:1};
  if(curr.close<curr.open) return {key:'bollSqueeze', dir:-1};
  return null;
 }
 // ---- (7) EMA'YA GERİ ÇEKİLME (trend devamı): EMA21 eğimi net bir yöndeyken fiyat kısa süreliğine
 // EMA'ya dokunup tekrar trend yönünde kapanırsa — "trendde ucuza alım/pahalıya satım" klasiği. ----
 function detectEmaPullback(a, ema21Series){
  if(a.length<15 || !ema21Series || ema21Series.length<10) return null;
  const n=ema21Series.length, slope=ema21Series[n-1]-ema21Series[n-10];
  const curr=a[a.length-1], prev=a[a.length-2], emaCurr=ema21Series[n-1];
  if(slope>0){
   const touched = prev.low<=emaCurr*1.0015 && prev.low>=emaCurr*0.993;
   if(touched && curr.close>curr.open && curr.close>emaCurr) return {key:'emaPullback', dir:1};
  } else if(slope<0){
   const touched = prev.high>=emaCurr*0.9985 && prev.high<=emaCurr*1.007;
   if(touched && curr.close<curr.open && curr.close<emaCurr) return {key:'emaPullback', dir:-1};
  }
  return null;
 }
 // ---- (8) İÇ MUM (INSIDE BAR) KIRILIMI: bir mumun tamamı bir öncekinin içinde kalırsa (sıkışma),
 // sonraki mum bu aralığın dışına kırılırsa yön sinyali sayılır. ----
 function detectInsideBarBreakout(a){
  if(a.length<3) return null;
  const curr=a[a.length-1], inside=a[a.length-2], mother=a[a.length-3];
  const isInside = inside.high<=mother.high && inside.low>=mother.low;
  if(!isInside) return null;
  if(curr.close>inside.high) return {key:'insideBar', dir:1};
  if(curr.close<inside.low) return {key:'insideBar', dir:-1};
  return null;
 }
 // ---- PİYASA YAPISI (Market Structure / BOS) — kullanıcı geri bildirimi: sistem ADX'e dayalı "rejim"
 // hesabıyla açık bir kanal kırılımını ("lower high + lower low" dizisi, sonra son swing low'un da
 // kırılması) yeterince güçlü şekilde YAKALAYAMIYORDU — ADX 18-25 "geçiş" aralığında rejim cezası hiç
 // uygulanmıyordu, bu da tam olarak "kanal yeni kırıldı ama ADX henüz güçlü trend seviyesine ulaşmadı"
 // anındaki dönüş/reversal stratejilerinin (likidite süpürme, iFVG, order block, POC bounce...) cezasız
 // ateşlenebilmesine yol açıyordu. Bu fonksiyon ADX'ten TAMAMEN bağımsız, gerçek swing high/low
 // dizisinden (fraktal pivot) yapıyı okur — dönüş: +-1 (henüz kırılmamış yapı), +-2 (son swing'i de
 // kapanışla kırmış, yani BOS gerçekleşmiş — daha güçlü sinyal).
 function detectSwingStructure(a, lookback){
  const w=a.slice(-lookback); const N=3;
  if(w.length<N*2+5) return 0;
  let swingHighs=[], swingLows=[];
  for(let i=N;i<w.length-N;i++){
   const c=w[i], left=w.slice(i-N,i), right=w.slice(i+1,i+1+N);
   if(left.every(x=>x.high<=c.high) && right.every(x=>x.high<=c.high)) swingHighs.push(c.high);
   if(left.every(x=>x.low>=c.low) && right.every(x=>x.low>=c.low)) swingLows.push(c.low);
  }
  if(swingHighs.length<2 || swingLows.length<2) return 0;
  const lastHH=swingHighs[swingHighs.length-1], prevHH=swingHighs[swingHighs.length-2];
  const lastLL=swingLows[swingLows.length-1], prevLL=swingLows[swingLows.length-2];
  const curr=w[w.length-1];
  if(lastHH>prevHH && lastLL>prevLL) return curr.close>lastHH ? 2 : 1;   // yükselen yapı (HH+HL); kapanış son zirveyi de kırdıysa BOS
  if(lastHH<prevHH && lastLL<prevLL) return curr.close<lastLL ? -2 : -1; // düşen yapı (LH+LL); kapanış son dibi de kırdıysa BOS
  return 0;
 }
 // ---- TÜKENİŞ MUM KÜMESİ (reversal candle cluster) — kullanıcı geri bildirimi: grafikte üst üste
 // birkaç "Shooting Star" oluşmuş bir tepede terminal HÂLÂ BUY veriyordu. Kök neden: `pattern(a)`
 // SADECE en son mumu kontrol ediyor — bir kaç mum önce oluşan 3-4 tane üst üste ret mumu (shooting
 // star/bear engulf) bir sonraki mumda tamamen UNUTULUYOR, hiçbir yerde biriktirilmiyordu. Oysa
 // birden fazla ret mumunun aynı tepede kümelenmesi, TEK bir mumdan çok daha güçlü bir dönüş
 // sinyalidir (deneyimli bir grafik okuyucunun tam olarak fark ettiği şey budur) — yine de bu henüz
 // yapının (swing low/high) KIRILMASI anlamına gelmez, bu yüzden detectSwingStructure'dan bağımsız,
 // daha ERKEN uyaran ayrı bir katman. Son `lookback` mumda, aralığın üst/alt %15'ine yakın oluşmuş
 // kaç tane ters yön mumu (shooting star/bear engulf = tepe reddi, hammer/bull engulf = dip reddi)
 // olduğunu sayar.
 function detectReversalExhaustion(a, lookback){
  const w=a.slice(-lookback);
  if(w.length<5) return 0;
  const hiRef=Math.max(...w.map(c=>c.high)), loRef=Math.min(...w.map(c=>c.low));
  const range=(hiRef-loRef)||1e-9;
  let bearScore=0, bullScore=0;
  for(let i=1;i<w.length;i++){
   const c=w[i], p=w[i-1];
   const body=Math.abs(c.close-c.open);
   const up=c.high-Math.max(c.close,c.open), lo=Math.min(c.close,c.open)-c.low;
   const bull=c.close>c.open, bear=c.close<c.open;
   const nearHigh=(hiRef-c.high)/range<0.15, nearLow=(c.low-loRef)/range<0.15;
   const isShootingStar = up>body*2 && lo<body;
   const isBearEngulf = bear && p.close>p.open && c.close<p.open && c.open>p.close;
   const isHammer = lo>body*2 && up<body;
   const isBullEngulf = bull && p.close<p.open && c.close>p.open && c.open<p.close;
   if((isShootingStar||isBearEngulf) && nearHigh) bearScore++;
   if((isHammer||isBullEngulf) && nearLow) bullScore++;
  }
  if(bearScore>=2 && bearScore>bullScore) return -Math.min(2, Math.ceil(bearScore/2)); // -1 tek küme, -2 güçlü küme (3+)
  if(bullScore>=2 && bullScore>bearScore) return Math.min(2, Math.ceil(bullScore/2));
  return 0;
 }
 // ---- FAIR VALUE GAP (FVG) — ICT tanımı: 3 mumluk yapı, 1. mumun high/low'u ile 3. mumun low/high'ı
 // arasında boşluk (2. mum "displacement/güçlü hareket" mumu). Fiyat bu boşluğa geri dönüp (retest)
 // tepki verirse (dolmadan reddedilirse) bu klasik bir giriş noktasıdır. ----
 function findFVGs(a, lookback){
  const w=a.slice(-lookback-2,-1); let fvgs=[];
  for(let i=1;i<w.length-1;i++){
   const c1=w[i-1], c3=w[i+1];
   if(c1.high<c3.low) fvgs.push({dir:1, top:c3.low, bottom:c1.high, ce:(c3.low+c1.high)/2});
   else if(c1.low>c3.high) fvgs.push({dir:-1, top:c1.low, bottom:c3.high, ce:(c1.low+c3.high)/2});
  }
  return fvgs;
 }
 // ICT "CE" (Consequent Encroachment) / %50 kuralı: istatistiksel olarak fiyatın FVG'nin sadece
 // dış kenarına değil, boşluğun TAM ORTA NOKTASINA (50%) geri dönmesi reddedilme/dönüş olasılığını
 // belirgin şekilde artırır — bu videoda anlatılan tam olarak bu kavram. Eskiden kod boşluğun
 // herhangi bir kenarına dokunmayı yeterli sayıyordu (çok daha erken/gevşek tetikleniyordu);
 // artık fiyatın CE seviyesine ulaşmasını şart koşuyor.
 function detectFVGRetest(a){
  if(a.length<25) return null;
  const fvgs=findFVGs(a,20), curr=a[a.length-1];
  for(let i=fvgs.length-1;i>=0;i--){
   const f=fvgs[i];
   if(f.dir>0 && curr.low<=f.ce && curr.close>f.bottom && curr.close>curr.open) return {key:'fvgRetest', dir:1, fvgZone:{top:f.top, bottom:f.bottom, ce:f.ce}};
   if(f.dir<0 && curr.high>=f.ce && curr.close<f.top && curr.close<curr.open) return {key:'fvgRetest', dir:-1, fvgZone:{top:f.top, bottom:f.bottom, ce:f.ce}};
  }
  return null;
 }
 // ---- INVERSE FVG (IFVG) — bir FVG, fiyatın onu TAM GÖVDE KAPANIŞIYLA (sadece fitil değil) geçmesiyle
 // "bozulur" ve kutup değiştirir: bullish FVG bozulursa bearish IFVG (SAT), tersi de BUY olur. ----
 function detectIFVG(a){
  if(a.length<25) return null;
  const fvgs=findFVGs(a,20), curr=a[a.length-1];
  for(let i=fvgs.length-1;i>=0;i--){
   const f=fvgs[i];
   if(f.dir>0 && curr.close<f.bottom) return {key:'ifvg', dir:-1};
   if(f.dir<0 && curr.close>f.top) return {key:'ifvg', dir:1};
  }
  return null;
 }
 // ---- AMD DÖNGÜSÜ (Accumulation-Manipulation-Distribution) — ICT'nin temel piyasa döngüsü kavramı.
 // Zaten var olan iki gerçek tespiti SIRALI olarak birleştirir: konsolidasyon bölgesi (accumulation) +
 // o bölgenin sınırının süpürülmesi (manipulation, likidite süpürmesi) + güçlü yönlü kopuş (distribution).
 // Üçü BİRDEN gerçekleştiğinde ateşlenir — bu yüzden en yüksek temel güvene sahip kalıptır. ----
 function detectAMDCycle(a, zones, ema200, vwap){
  const sweep=detectLiquiditySweep(a, ema200, vwap);
  if(!sweep || !zones || !zones.length) return null;
  const curr=a[a.length-1];
  const nearZone=zones.some(z => (curr.close<=z.hi*1.006 && curr.close>=z.lo*0.994));
  return nearZone ? {key:'amdCycle', dir:sweep.dir} : null;
 }
 // ---- DEĞERLEME EKSTREMİ + BÖLGE CONFLUENCE — "gold ucuz mu pahalı mı" + bir arz/talep bölgesinde
 // olması ikisi birden gerekir (Bollinger %B'yi değerleme ekstremi, S/R yakınlığını bölge olarak kullanır). ----
 function detectValuationZoneConfluence(bollPct, srBias){
  if(bollPct>80 && srBias<0) return {key:'valuationZone', dir:-1};
  if(bollPct<20 && srBias>0) return {key:'valuationZone', dir:1};
  return null;
 }
 // ---- MACD SIFIR ÇİZGİSİ KESİŞİMİ — MACD çizgisinin sıfırı yukarı/aşağı kesmesi, sinyal çizgisi
 // kesişiminden farklı, daha geniş bir momentum dönüşü sinyalidir. Gerçek MACD SERİSİNDEN hesaplanır. ----
 function calcMACDSeries(a){
  const ema12=emaLine(a,12).map(p=>p.value), ema26=emaLine(a,26).map(p=>p.value);
  return ema12.map((v,i)=>v-(ema26[i]!=null?ema26[i]:v));
 }
 function detectMacdZeroCross(macdSeries){
  if(!macdSeries||macdSeries.length<2) return null;
  const prev=macdSeries[macdSeries.length-2], curr=macdSeries[macdSeries.length-1];
  if(prev<=0 && curr>0) return {key:'macdZeroCross', dir:1};
  if(prev>=0 && curr<0) return {key:'macdZeroCross', dir:-1};
  return null;
 }
 function detectLiquiditySweep(a, ema200, vwap){
  // "Likidite Süpürme Dönüşü": 200 EMA yön filtresi + yakın bir swing high/low'un süpürülüp (sweep)
  // kapanışın geri içeri dönmesi ("trick move") + VWAP reddi — hepsi AYNI ANDA gerçekleşmeli.
  if(a.length<12 || ema200==null || vwap==null) return null;
  const curr=a[a.length-1];
  const bias = curr.close>ema200 ? 1 : curr.close<ema200 ? -1 : 0;
  if(bias===0) return null;
  const priorWindow=a.slice(-12,-1); // "eski high/low" referansı, şu anki mum hariç
  if(bias>0){
   // BUY: yakın bir swing LOW süpürülür, sonra VWAP üzerine geri döner
   const localLow=Math.min(...priorWindow.map(c=>c.low));
   if(curr.low<localLow && curr.close>localLow && curr.low<vwap && curr.close>vwap) return {key:'liquiditySweep', dir:1};
  } else {
   // SELL: yakın bir swing HIGH süpürülür, sonra VWAP altına geri döner
   const localHigh=Math.max(...priorWindow.map(c=>c.high));
   if(curr.high>localHigh && curr.close<localHigh && curr.high>vwap && curr.close<vwap) return {key:'liquiditySweep', dir:-1};
  }
  return null;
 }
 function detectStrategyTags(a, ind){
  const tags=[];
  if(a.length<10) return tags;
  // (1) EMA9/21 momentum kesişimi + MACD + RSI filtresi
  if(ind.ema9>ind.ema21 && ind.macd>0 && ind.rsi>45 && ind.rsi<70) tags.push({key:'emaCross', dir:1});
  else if(ind.ema9<ind.ema21 && ind.macd<0 && ind.rsi<55 && ind.rsi>30) tags.push({key:'emaCross', dir:-1});
  // (2) Açılış aralığı kırılımı (ORB)
  const orb=detectORB(a); if(orb) tags.push(orb);
  // (3) Ardışık N mum + kırılım momentumu
  const N=3;
  if(a.length>=N+1){
   const recent=a.slice(-N-1,-1), curr=a[a.length-1];
   if(recent.every(c=>c.close>c.open) && curr.high>Math.max(...recent.map(c=>c.high))) tags.push({key:'momentum', dir:1});
   else if(recent.every(c=>c.close<c.open) && curr.low<Math.min(...recent.map(c=>c.low))) tags.push({key:'momentum', dir:-1});
  }
  // (4) Likidite süpürme dönüşü (200 EMA + swing sweep + VWAP reddi)
  const sweep=detectLiquiditySweep(a, ind.ema200, ind.vwap); if(sweep) tags.push(sweep);
  // (5) RSI uyumsuzluğu
  const closes=a.map(c=>c.close);
  const rsiSeries=calcRSISeries(closes,14);
  const rsiDiv=detectRSIDivergence(a, rsiSeries); if(rsiDiv) tags.push(rsiDiv);
  // (6) Bollinger sıkışması + kırılımı
  const squeeze=detectBollSqueeze(a, closes); if(squeeze) tags.push(squeeze);
  // (7) EMA21'e geri çekilme (trend devamı)
  const ema21Series=emaLine(a,21).map(p=>p.value);
  const pullback=detectEmaPullback(a, ema21Series); if(pullback) tags.push(pullback);
  // (8) İç mum (inside bar) kırılımı
  const insideBar=detectInsideBarBreakout(a); if(insideBar) tags.push(insideBar);
  // (9) Fair Value Gap retest
  const fvgR=detectFVGRetest(a); if(fvgR) tags.push(fvgR);
  // (9b) Order Block + FVG Confluence (kullanıcının paylaştığı SMC eskizi)
  const obFvg=detectObFvgConfluence(a); if(obFvg) tags.push(obFvg);
  // (10) Inverse Fair Value Gap
  const ifvg=detectIFVG(a); if(ifvg) tags.push(ifvg);
  // (11) AMD Döngüsü (accumulation + manipulation + distribution)
  const amd=detectAMDCycle(a, ind.zones, ind.ema200, ind.vwap); if(amd) tags.push(amd);
  // (12) Değerleme ekstremi + bölge confluence
  const valZone=detectValuationZoneConfluence(ind.bollPct, ind.srBias); if(valZone) tags.push(valZone);
  // (13) MACD sıfır çizgisi kesişimi
  const macdSeries=calcMACDSeries(a);
  const macdCross=detectMacdZeroCross(macdSeries); if(macdCross) tags.push(macdCross);
  // (14) ORB Scalp varyantı (dar/tek mumluk aralık, fitil tetikli)
  const scalpOrb=detectScalpORB(a); if(scalpOrb) tags.push(scalpOrb);
  // (15) No Wick (fitilsiz mum) geri test
  const noWick=detectNoWickRetest(a, ind.ema200); if(noWick) tags.push(noWick);
  // (16) ORB Süpürme-Geri Dönüş
  const orbFade=detectORBSweepFade(a); if(orbFade) tags.push(orbFade);
  // (17) Piyasa Yapısı BOS/CHoCH
  const structure=detectMarketStructure(a); if(structure) tags.push(structure);
  // (18) Eşit Tepe/Dip (EQH/EQL) likidite havuzu
  const eqhl=detectEqualHighsLows(a); if(eqhl) tags.push(eqhl);
  // (19) Trades Delta (gerçek agresif alım/satım hacmi farkı)
  const tDelta=detectTradeDelta(ind.tradeDelta); if(tDelta) tags.push(tDelta);
  // (20) Silver Bullet (likidite süpürmesi + FVG kombinasyonu)
  const silverBullet=detectSilverBullet(a, ind.ema200, ind.vwap); if(silverBullet) tags.push(silverBullet);
  // (21) ORB + Hacim onayı
  const orbVol=detectORBVolume(a); if(orbVol) tags.push(orbVol);
  // (22) VWAP Geri Çekilme + dönüş mumu
  const vwapPb=detectVwapPullback(a, ind.ema50, ind.ema200, ind.vwap); if(vwapPb) tags.push(vwapPb);
  // (23) TTM Squeeze (Bollinger/Keltner kesin tanımı)
  const ttm=detectTTMSqueeze(a, closes); if(ttm) tags.push(ttm);
  // (24) RSI Uyumsuzluğu + CHoCH kombinasyonu
  const divChoch=detectDivergenceChoch(a, rsiSeries); if(divChoch) tags.push(divChoch);
  // (25) Hacim Profili POC sekmesi
  const poc=detectPOCBounce(a); if(poc) tags.push(poc);
  // (26) Order Block mitigasyonu
  const obMit=detectOrderBlockMitigation(a); if(obMit) tags.push(obMit);
  // (27) Fibonacci OTE bölgesi
  const fibOte=detectFibOTE(a, ind.fibZone, ind.ema200); if(fibOte) tags.push(fibOte);
  // (28) Asya Aralığı Killzone sahte kırılımı
  const asianFake=detectAsianRangeFakeout(a); if(asianFake) tags.push(asianFake);
  // (29) Aşırı ortalamaya dönüş (3-sigma)
  const extremeMR=detectExtremeMeanReversion(a, closes, ind.rsi); if(extremeMR) tags.push(extremeMR);
  // (30) Önceki gün seviye confluence (POC/VAH/VAL/Yüksek/Düşük üst üste binmesi + süpürme-geri alım)
  const priorDayLv=computePriorDayLevels(a);
  const levelConf=detectLevelConfluenceReversal(a, priorDayLv); if(levelConf) tags.push(levelConf);
  // (31) Delta doğrulama matrisi (fonlanmış hareket / absorpsiyon)
  const deltaConf=detectDeltaConfirmation(a, ind.tradeDelta); if(deltaConf) tags.push(deltaConf);
  return tags;
 }
 // ---- GEÇMİŞ VERİ TESTİ (BACKTEST) — Kullanıcı isteği: "sinyal vermeden önce stratejiyi test etsin."
 // ÖNEMLİ AYRIM: bu rastgele/olası GELECEK yolları üretip "en iyisini" seçen bir şey DEĞİLDİR — o
 // yaklaşım her zaman şans eseri yukarı giden bir yol bulur, sahte güven yaratır. Bunun yerine, terminalin
 // zaten elinde olan GERÇEKTEN YAŞANMIŞ geçmiş mumlar üzerinde, her stratejinin (hem AL hem SAT) geçmişte
 // ateşlendiği HER noktayı bulup, o andan sonra fiyatın GERÇEKTE TP'ye mi SL'ye mi önce ulaştığını
 // (canlıdaki AYNI ATR formülüyle) kontrol eder — net etiketli, ayrı bir panelde gösterilir.
 function runHistoricalBacktest(){
  if(ohlc.length<350) return null;
  const WARMUP=250; // uzun-lookback'li stratejiler (BOS/CHoCH, TTM Squeeze vb.) için yeterli geçmiş bırak
  const TEST_RANGE=Math.min(300, ohlc.length-WARMUP-1);
  const MAX_FORWARD=100; // TP/SL'ye ulaşması için en fazla 100 mum ileri bak; ulaşamazsa "çözülmemiş" say, sayma
  if(TEST_RANGE<20) return null;
  const results={};
  for(let i=WARMUP; i<WARMUP+TEST_RANGE; i++){
   const histOhlc=ohlc.slice(0,i+1);
   const closes=histOhlc.map(c=>c.close);
   const last=closes[closes.length-1];
   // O andaki göstergeleri, ZATEN TEST EDİLMİŞ aynı fonksiyonlarla, o ana kadarki veriyle hesapla —
   // canlı sinyal motorundan AYRI/paralel bir hesaplama mantığı yazmıyoruz, tutarlılık garantili.
   const rsiReal=calcRSIReal(closes,14);
   const atrReal=calcATR(histOhlc,14);
   if(rsiReal==null||atrReal==null) continue;
   const macdReal=(emaValue(closes.slice(-40),12)||last)-(emaValue(closes.slice(-60),26)||last);
   const ema9Real=emaValue(closes.slice(-30),9)||last;
   const ema21Real=emaValue(closes.slice(-50),21)||last;
   const ema50Real=emaValue(closes.slice(-90),50)||last;
   const ema200Real=emaValue(closes,200)||last;
   const bollPctReal=calcBollPct(closes,20);
   const vwapReal=calcVWAP(histOhlc,96);

   const tags=detectStrategyTags(histOhlc, {rsi:rsiReal, macd:macdReal, ema9:ema9Real, ema21:ema21Real, ema50:ema50Real,
     ema200:ema200Real, vwap:vwapReal, zones:[], bollPct:bollPctReal!==null?bollPctReal:50, srBias:0, fibZone:null, tradeDelta:null});

   tags.forEach(tag=>{
    const isTightTpOrb=tag.key==='scalpOrb';
    const slDist=isTightTpOrb?atrReal*1.6:atrReal*1.0, tpDist=isTightTpOrb?atrReal*0.5:atrReal*2.0;
    const stopPx=last-tag.dir*slDist, tpPx=last+tag.dir*tpDist;
    let outcome=null;
    for(let j=i+1; j<Math.min(i+1+MAX_FORWARD, ohlc.length); j++){
     const c=ohlc[j];
     if(tag.dir>0){ if(c.low<=stopPx){outcome='loss';break;} if(c.high>=tpPx){outcome='win';break;} }
     else { if(c.high>=stopPx){outcome='loss';break;} if(c.low<=tpPx){outcome='win';break;} }
    }
    if(outcome){
     if(!results[tag.key]) results[tag.key]={wins:0,losses:0,trades:0};
     results[tag.key].trades++;
     if(outcome==='win') results[tag.key].wins++; else results[tag.key].losses++;
    }
   });
  }
  return results;
 }
 function drawSRLines(){
  srLines.forEach(l=>cs.removePriceLine(l)); srLines=[];
  const cfg=SYMS[curSym]; if(!cfg) return;
  cfg.sr.forEach(s=>{
   const px=(s.lo+s.hi)/2, isRes=s.type==='r';
   srLines.push(cs.createPriceLine({price:px,color:isRes?'#ff506d':'#00c896',lineWidth:2,lineStyle:0,axisLabelVisible:true,title:s.label}));
  });
 }
 // ---- RSI AŞIRI ALIM/SATIMDAN DÖNÜŞ SEVİYELERİ (kullanıcı isteği: "RSI yoğun alımdan 70 üstü
 // birkaç kez dönmüş olsun gibi ya da yoğun satımdan") — RSI 70 üzerinden geri 70'in altına
 // düştüğü ya da 30 altından geri 30'un üzerine çıktığı ANDAKİ fiyat seviyesi, gerçek bir
 // destek/direnç adayıdır (piyasa o bölgede tekrar tekrar "yeter" demiş demektir).
 function detectRsiReversalLevels(a){
  if(a.length<40) return [];
  const closes=a.map(c=>c.close);
  const rsiSeries=calcRSISeries(closes,14);
  let levels=[];
  for(let i=1;i<a.length;i++){
   if(rsiSeries[i]==null||rsiSeries[i-1]==null) continue;
   if(rsiSeries[i-1]>=70 && rsiSeries[i]<70) levels.push({price:a[i-1].high, kind:'res'});
   if(rsiSeries[i-1]<=30 && rsiSeries[i]>30) levels.push({price:a[i-1].low, kind:'sup'});
  }
  return levels;
 }
 // ---- LİKİDİTE SÜPÜRME NOKTALARI — bir swing high/low'un fitille aşılıp kapanışla geri içeri
 // dönüldüğü (yani "süpürülüp" reddedildiği) seviyeler. Süpürülen seviyenin kendisi, piyasanın
 // orada durup tersine döndüğü GERÇEK bir destek/direnç referansıdır.
 function detectSweepLevels(a){
  if(a.length<20) return [];
  const N=2; let swings=[], levels=[];
  for(let i=N;i<a.length-N;i++){
   const c=a[i]; let isHigh=true, isLow=true;
   for(let j=i-N;j<=i+N;j++){ if(j===i) continue; if(a[j].high>=c.high) isHigh=false; if(a[j].low<=c.low) isLow=false; }
   if(isHigh) swings.push({idx:i, price:c.high, type:'high'});
   if(isLow) swings.push({idx:i, price:c.low, type:'low'});
  }
  swings.forEach(s=>{
   for(let k=s.idx+1;k<Math.min(a.length,s.idx+15);k++){ // süpürme makul bir süre içinde olmalı
    const c=a[k];
    if(s.type==='high' && c.high>s.price && c.close<s.price){ levels.push({price:s.price, kind:'res'}); break; }
    if(s.type==='low' && c.low<s.price && c.close>s.price){ levels.push({price:s.price, kind:'sup'}); break; }
   }
  });
  return levels;
 }
 // Yakın fiyattaki tekil seviyeleri (RSI dönüşü / süpürme noktaları) tek bir bölgede toplar —
 // AYNI bölgede birden fazla dönüş/süpürme varsa bu gerçek bir confluence'dır, tek seferlik bir
 // nokta değil ("birkaç kez dönmüş olsun" isteği tam olarak bu — count>=2 şartı).
 function clusterLevelsIntoZones(levels, tolerancePct){
  if(!levels.length) return [];
  const sorted=levels.slice().sort((a,b)=>a.price-b.price);
  let clusters=[];
  sorted.forEach(lv=>{
   const last=clusters[clusters.length-1];
   if(last && (lv.price-last.hi)/lv.price < tolerancePct){ last.hi=Math.max(last.hi,lv.price); last.lo=Math.min(last.lo,lv.price); last.count++; }
   else clusters.push({hi:lv.price, lo:lv.price, count:1});
  });
  return clusters.filter(c=>c.count>=2);
 }
 // ---- ANA DESTEK/DİRENÇ: her zaman 1 saatlik mumlardan, o an izlenen zaman diliminden BAĞIMSIZ ----
 // DÜZELTME (kullanıcı geri bildirimi): eskiden bu SADECE son ~100 saatlik mumun ham min/max'ıydı —
 // "en son mum nereye değdiyse" seviyeyi oraya çekiyordu, gerçek bir destek/direnç (fiyatın TEKRAR
 // TEKRAR reaksiyon verdiği, volatilitenin BİRİKTİĞİ bölge) değildi. Artık ÜÇ bağımsız kanıt
 // birleştiriliyor: (1) konsolidasyon/volatilite birikimi bölgeleri, (2) RSI aşırı alım/satımdan
 // dönüş seviyeleri, (3) likidite süpürme (swing sweep) noktaları — birbirine yakın/çakışan
 // adaylar tek bir bölgede birleşip fiyata en yakın olanlar tutuluyor.
 // DÜZELTME 2 (kullanıcı hâlâ tek dev bir blok gösterdi — referans görselindeki gibi SEYREK, DAR,
 // birbirinden AYRIK kutular istiyor): genişlik sınırı her bölgeyi tek tek sınırlasa bile, ÇOK
 // SAYIDA (özellikle yatay/dalgalı bir piyasada) birbirine bitişik dar bölge üretilince görsel
 // olarak yine TEK bir kesintisiz blok gibi görünüyordu. Artık üç ek önlem var: (1) bölge genişliği
 // sınırı daha SIKI (1.4×ATR, önceden 2.2×), (2) son listede birbirine ÇOK yakın kalan bölgeler
 // (aralarında en az yarım ATR boşluk yoksa) ayrı ayrı gösterilmiyor — en güçlü kanıtlı (weight)
 // olan tutulup diğeri elenir, (3) en fazla 4 bölge (6 değil) — az ama güvenilir.
 function buildMainSRZones(bars, lastPrice){
  const atrRef=calcATR(bars,14)||((bars[bars.length-1].high-bars[bars.length-1].low)||1);
  // DÜZELTME 3 (kullanıcının kesin isteği): ATR'ye dayalı hesap hâlâ çok geniş bantlar üretebiliyordu
  // (yüksek volatiliteli dönemlerde ATR'nin kendisi büyüyünce sınır da büyüyordu). Artık MUTLAK bir
  // dolar tavanı var — bir bölge, ATR ne olursa olsun 10 dolardan GENİŞ OLAMAZ.
  const HARD_MAX_ZONE_WIDTH=10;
  const maxZoneWidth=Math.min(atrRef*1.4, HARD_MAX_ZONE_WIDTH);
  const minGap=Math.min(atrRef*0.5, HARD_MAX_ZONE_WIDTH*0.6);
  // ÖNEMLİ: aşağıdaki merge döngüsü sadece İKİ bölge BİRLEŞTİĞİNDE sonucu sınırlıyordu — ama
  // detectConsolidationZones gibi bir kaynaktan gelen TEK bir ham bölge zaten kendi başına 10
  // dolardan geniş gelebiliyordu (hiç birleşmeden), bu durumda hiç kontrol edilmeden geçiyordu.
  // Her adayı kaynağından çıkar çıkmaz (merge'den ÖNCE) 10 dolara sabitliyoruz — hiçbir bölge,
  // hangi kaynaktan gelirse gelsin, asla bu sınırı aşamaz.
  const clampWidth=(z)=>{ const w=z.hi-z.lo; if(w<=HARD_MAX_ZONE_WIDTH) return z; const mid=(z.hi+z.lo)/2; return {hi:mid+HARD_MAX_ZONE_WIDTH/2, lo:mid-HARD_MAX_ZONE_WIDTH/2, weight:z.weight}; };
  const consolZones=detectConsolidationZones(bars).map(z=>clampWidth({hi:z.hi, lo:z.lo, weight:1}));
  const rsiZones=clusterLevelsIntoZones(detectRsiReversalLevels(bars), 0.0025).map(z=>clampWidth({hi:z.hi, lo:z.lo, weight:z.count}));
  const sweepZones=clusterLevelsIntoZones(detectSweepLevels(bars), 0.0025).map(z=>clampWidth({hi:z.hi, lo:z.lo, weight:z.count}));
  const all=[...consolZones, ...rsiZones, ...sweepZones];
  if(!all.length) return [];
  all.sort((a,b)=>a.lo-b.lo);
  let merged=[];
  all.forEach(c=>{
   const last=merged[merged.length-1];
   if(last && c.lo<=last.hi*1.0015){
    const newHi=Math.max(last.hi,c.hi), newLo=Math.min(last.lo,c.lo);
    if((newHi-newLo)<=maxZoneWidth){ last.hi=newHi; last.lo=newLo; last.weight+=c.weight; }
    else merged.push({hi:c.hi, lo:c.lo, weight:c.weight}); // birleşirse çok genişleyecekti — ayrı bölge
   }
   else merged.push({hi:c.hi, lo:c.lo, weight:c.weight});
  });
  // Bitişik/çok yakın kalan bölgeleri seyrekleştir — aralarında yeterli boşluk yoksa sadece en
  // güçlü kanıtlıyı (weight) tut, "duvar gibi" bitişik kutular yerine seyrek, net bölgeler kalsın.
  merged.sort((a,b)=>a.lo-b.lo);
  let spaced=[];
  merged.forEach(z=>{
   const prev=spaced[spaced.length-1];
   if(prev && (z.lo-prev.hi)<minGap){ if(z.weight>prev.weight) spaced[spaced.length-1]=z; }
   else spaced.push(z);
  });
  spaced.sort((a,b)=>Math.abs(lastPrice-(a.hi+a.lo)/2)-Math.abs(lastPrice-(b.hi+b.lo)/2));
  return spaced.slice(0,4);
 }
 async function fetchMainSR(sym){
  const bs=MAP[sym]; if(!bs){ mainSRZones=[]; mainSRHistory=[]; return; }
  try{
   const r=await fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=1h&limit=200`);
   const d=await r.json();
   if(!Array.isArray(d)||!d.length) return;
   const bars=d.map(k=>({time:k[0]/1000,open:+k[1],high:+k[2],low:+k[3],close:+k[4]}));
   const newZones=buildMainSRZones(bars, bars[bars.length-1].close);
   // Kırılan bölge takibi: eski bölgelerin dış sınırları (en yüksek tepe / en düşük dip) yeni
   // bölgelerin dışına taştıysa (gerçekten kırıldıysa), eski sınır mainSRHistory'ye taşınır.
   if(mainSRZones.length && newZones.length){
    const oldMaxHi=Math.max(...mainSRZones.map(z=>z.hi)), oldMinLo=Math.min(...mainSRZones.map(z=>z.lo));
    const newMaxHi=Math.max(...newZones.map(z=>z.hi)), newMinLo=Math.min(...newZones.map(z=>z.lo));
    if(newMaxHi>oldMaxHi+1e-6) addBrokenMainSR(oldMaxHi, 'res');
    if(newMinLo<oldMinLo-1e-6) addBrokenMainSR(oldMinLo, 'sup');
   }
   mainSRZones=newZones;
   if(sym===curSym) drawMainSRZones();
  }catch(e){ /* sessizce yoksay — bu ikincil bir veri kaynağı, ana grafiği bozmasın */ }
 }
 function addBrokenMainSR(price, kind){
  // aynı seviyeye çok yakın bir kayıt zaten varsa tekrar ekleme (küçük fiyat titremeleri
  // yeni bir "kırılım" olarak sayılmasın)
  if(mainSRHistory.some(h=>Math.abs(h.price-price)/price<0.001)) return;
  mainSRHistory.push({price, kind});
  if(mainSRHistory.length>4) mainSRHistory.shift(); // grafik kirlenmesin — en fazla son 4 kırılan seviye
 }
 // ---- Ana Destek/Direnç bölgelerini DOLU DİKDÖRTGEN BANT olarak çizer (tek çizgi değil) —
 // lightweight-charts'ta native dikdörtgen yok, 1M Scalp kutusuyla AYNI DOM overlay tekniği
 // kullanılıyor, ama zaman ekseninde SINIRSIZ (grafiğin tüm genişliğinde) — sadece fiyat ekseninde
 // sınırlı bir yatay bant.
 function ensureMainSRZoneEl(idx){
  if(mainSRZoneEls[idx]) return mainSRZoneEls[idx];
  const div=document.createElement('div');
  div.className='mainSRZoneBox';
  div.style.cssText='position:absolute;left:0;right:0;pointer-events:none;z-index:3;border-top:1px solid rgba(255,140,66,.55);border-bottom:1px solid rgba(255,140,66,.55);background:rgba(255,140,66,.10);display:none;';
  el.appendChild(div);
  mainSRZoneEls[idx]=div;
  return div;
 }
 function positionMainSRZones(){
  mainSRZones.forEach((z,i)=>{
   const div=ensureMainSRZoneEl(i);
   const yTop=cs.priceToCoordinate(z.hi), yBot=cs.priceToCoordinate(z.lo);
   if(yTop==null||yBot==null){ div.style.display='none'; return; }
   div.style.display='block';
   div.style.top=Math.min(yTop,yBot)+'px';
   div.style.height=Math.max(2,Math.abs(yBot-yTop))+'px';
  });
  for(let i=mainSRZones.length;i<mainSRZoneEls.length;i++){ if(mainSRZoneEls[i]) mainSRZoneEls[i].style.display='none'; }
 }
 function drawMainSRZones(){
  mainSRHistoryLines.forEach(l=>cs.removePriceLine(l)); mainSRHistoryLines=[];
  mainSRHistory.forEach(h=>{
   const title = h.kind==='res' ? t('mainResistanceBroken') : t('mainSupportBroken');
   mainSRHistoryLines.push(cs.createPriceLine({price:h.price,color:'rgba(255,140,66,.45)',lineWidth:1,lineStyle:2,axisLabelVisible:true,title}));
  });
  positionMainSRZones();
 }
 // Diğer kodun (yakınlık/srBias kontrolü, TP kırpma) tek bir "en yakın destek/en yakın direnç"
 // değerine ihtiyacı var — birden fazla bölgeden mevcut fiyata göre en yakın olanı seçer.
 function nearestMainSR(last){
  let sup=null, res=null;
  mainSRZones.forEach(z=>{
   const mid=(z.hi+z.lo)/2;
   if(mid<=last && (sup==null || z.hi>sup.hi)) sup=z;
   if(mid>=last && (res==null || z.lo<res.lo)) res=z;
  });
  return {sup, res};
 }
 // ---- 1M SCALP MODU — ÜST ZAMAN DİLİMİ BIAS ("How to Analysis" görseli + Türkçe BIAS/DOL
 // videosu): 4H ve 1H'ı mevcut ohlc/WS pipeline'ına HİÇ dokunmadan, fetchMainSR ile AYNI desende
 // (bağımsız REST kline çağrısı) çeker, detectSwingStructure ile yapı yönünü okur. 2dk'da bir
 // tazelenir, sadece window.valensScalpModeActive açıkken (gereksiz istek atılmasın).
 async function fetchScalpBias(sym){
  const bs=MAP[sym]; if(!bs){ window.valensScalpBias=null; if(window.valensRenderScalpBiasLine) window.valensRenderScalpBiasLine(); return; }
  try{
   const [r4,r1]=await Promise.all([
    fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=4h&limit=100`),
    fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=1h&limit=100`)
   ]);
   const [d4,d1]=await Promise.all([r4.json(), r1.json()]);
   if(!Array.isArray(d4)||!Array.isArray(d1)||!d4.length||!d1.length) return;
   const toBars=d=>d.map(k=>({time:k[0]/1000,open:+k[1],high:+k[2],low:+k[3],close:+k[4]}));
   window.valensScalpBias = {h4Dir: detectSwingStructure(toBars(d4),60), h1Dir: detectSwingStructure(toBars(d1),60)};
   if(window.valensRenderScalpBiasLine) window.valensRenderScalpBiasLine();
  }catch(e){ /* sessizce yoksay — ikincil bir veri kaynağı, ana grafiği bozmasın */ }
 }
 window.valensFetchScalpBias=function(){ if(curSym) fetchScalpBias(curSym); };
 setInterval(()=>{ if(window.valensScalpModeActive && curSym) fetchScalpBias(curSym); }, 2*60*1000);

 // ---- 1M SCALP MODU — KUTU/DİKDÖRTGEN ÇİZİM (kullanıcının paylaştığı video örnekleri) ----
 // lightweight-charts v4'te native "dikdörtgen" primitifi yok. Video'lardaki gibi GERÇEK bir kutu
 // (hem zaman HEM fiyat ekseninde sınırlı, tek bir çizgi değil) için DOM overlay tekniği: chart
 // container'ının üzerine mutlak-konumlu, yarı saydam bir <div>, pozisyonu timeToCoordinate/
 // priceToCoordinate ile hesaplanıp CSS left/top/width/height'a çevrilir.
 let scalpBoxEl=null, scalpBoxState=null;
 function ensureScalpBoxEl(){
  if(scalpBoxEl) return scalpBoxEl;
  scalpBoxEl=document.createElement('div');
  scalpBoxEl.id='scalpTradeBox';
  scalpBoxEl.style.cssText='position:absolute;pointer-events:none;z-index:5;display:none;border-radius:2px;transition:opacity .2s;';
  el.style.position = el.style.position || 'relative';
  el.appendChild(scalpBoxEl);
  return scalpBoxEl;
 }
 function positionScalpBox(){
  if(!scalpBoxState || !scalpBoxEl) return;
  const x1=chart.timeScale().timeToCoordinate(scalpBoxState.entryTime);
  const x2=chart.timeScale().timeToCoordinate(scalpBoxState.endTime);
  const yTop=cs.priceToCoordinate(scalpBoxState.top);
  const yBottom=cs.priceToCoordinate(scalpBoxState.bottom);
  if(x1==null||yTop==null||yBottom==null){ scalpBoxEl.style.display='none'; return; }
  const rightX = x2!=null ? x2 : x1+60;
  scalpBoxEl.style.display='block';
  scalpBoxEl.style.left=Math.min(x1,rightX)+'px';
  scalpBoxEl.style.top=Math.min(yTop,yBottom)+'px';
  scalpBoxEl.style.width=Math.max(2,Math.abs(rightX-x1))+'px';
  scalpBoxEl.style.height=Math.max(2,Math.abs(yBottom-yTop))+'px';
  scalpBoxEl.style.background = scalpBoxState.dir>0 ? 'rgba(0,200,150,.18)' : 'rgba(255,80,109,.18)';
  scalpBoxEl.style.border = '1px solid ' + (scalpBoxState.dir>0 ? 'rgba(0,200,150,.6)' : 'rgba(255,80,109,.6)');
 }
 // entryTime/endTime: saniye cinsinden UNIX zaman damgası (ohlc.time ile aynı birim). endTime,
 // "işlem süresi" penceresinin sonu — bu süre geçince ya da işlem sonuçlanınca kutu silinir.
 window.valensDrawScalpBox=function(entryTime, endTime, top, bottom, dir){
  ensureScalpBoxEl();
  scalpBoxState={entryTime, endTime, top, bottom, dir};
  positionScalpBox();
 };
 window.valensClearScalpBox=function(){
  scalpBoxState=null;
  if(scalpBoxEl) scalpBoxEl.style.display='none';
 };
 chart.timeScale().subscribeVisibleTimeRangeChange(positionScalpBox);
 // ---- Kullanıcı geri bildirimi: grafik kaydırılınca/yakınlaştırılınca fiyat ekseni yeniden
 // ölçekleniyor (autoscale) ama Ana Destek/Direnç bantları eski koordinatlarda kalıp fiyattan
 // KOPUYORDU — bu bantlar sadece veri tazelenince (5dk'da bir) yeniden konumlanıyordu. Artık
 // görünür zaman aralığı her değiştiğinde (kaydırma/yakınlaştırma dahil) de yeniden konumlanıyor.
 chart.timeScale().subscribeVisibleTimeRangeChange(positionMainSRZones);
 chart.priceScale('right').subscribePriceRangeChange && chart.priceScale('right').subscribePriceRangeChange(positionMainSRZones);

 function drawFibonacci(dataArr){
  const a=dataArr||ohlc;
  fibLines.forEach(l=>cs.removePriceLine(l)); fibLines=[];
  if(a.length<40)return;
  const w=a.slice(-80);
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
 function drawTrendChannel(dataArr){
  const a=dataArr||ohlc;
  if(a.length<30){trendSeries.setData([]);chanUp.setData([]);chanLo.setData([]);return;}
  const w=a.slice(-60), n=w.length;
  let sx=0,sy=0,sxy=0,sxx=0;
  w.forEach((c,i)=>{sx+=i;sy+=c.close;sxy+=i*c.close;sxx+=i*i;});
  const slope=(n*sxy-sx*sy)/(n*sxx-sx*sx), intercept=(sy-slope*sx)/n;
  let maxDev=0;
  w.forEach((c,i)=>{const line=slope*i+intercept;maxDev=Math.max(maxDev,Math.abs(c.high-line),Math.abs(c.low-line));});
  const mid=[],up=[],low=[];
  w.forEach((c,i)=>{const v=slope*i+intercept;mid.push({time:c.time,value:+v.toFixed(4)});up.push({time:c.time,value:+(v+maxDev).toFixed(4)});low.push({time:c.time,value:+(v-maxDev).toFixed(4)});});
  trendSeries.setData(mid); chanUp.setData(up); chanLo.setData(low);
 }
 // ---- ATR bazlı volatilite zarfı (EMA20 ± ATR14*2) — TradingView ekranınızdaki renkli "volatilite bulutu"
 // konseptinin genel/klasik karşılığı (Keltner Channel). Trend yönüne göre renk değiştirir. ----
 function drawVolatilityBand(dataArr){
  const a=dataArr||ohlc;
  if(a.length<25){ kelUp.setData([]); kelLo.setData([]); return; }
  const closes=a.map(c=>c.close), period=20, mult=2, k=2/(period+1);
  let ema=closes[0]; const emaSeries=[];
  closes.forEach((c,i)=>{ ema = i? c*k+ema*(1-k) : c; emaSeries.push(ema); });
  let trs=[0];
  for(let i=1;i<a.length;i++){
   const cur=a[i], prev=a[i-1];
   trs.push(Math.max(cur.high-cur.low,Math.abs(cur.high-prev.close),Math.abs(cur.low-prev.close)));
  }
  const up=[], lo=[];
  for(let i=0;i<a.length;i++){
   const start=Math.max(0,i-13), slice=trs.slice(start,i+1);
   const atr=slice.reduce((a2,b)=>a2+b,0)/slice.length;
   up.push({time:a[i].time,value:+(emaSeries[i]+atr*mult).toFixed(4)});
   lo.push({time:a[i].time,value:+(emaSeries[i]-atr*mult).toFixed(4)});
  }
  const bullish = closes[closes.length-1] >= emaSeries[emaSeries.length-1];
  const col = bullish ? 'rgba(0,200,150,.55)' : 'rgba(255,80,109,.55)';
  kelUp.applyOptions({color:col}); kelLo.applyOptions({color:col});
  kelUp.setData(up); kelLo.setData(lo);
 }
 // ---- Konsolidasyon / hacim birikim bölgesi tespiti — TradingView ekranınızdaki teal kutular gibi
 // dar-aralıklı, sıkışık fiyat pencerelerini gerçek OHLC'den bulur; bunlar geleceğe dönük S/R adayı olur. ----
 // DÜZELTME (kullanıcı geri bildirimi: "böyle noktalarda çok geniş bir aralık veriyor") — eskiden
 // birleştirme SINIRSIZ uzayabiliyordu: yavaş bir trend/dalgalanmada onlarca ardışık pencere tek
 // tek "dar" olsa bile, hepsi art arda birleşince toplam bant çok YÜKSEK bir aralığa çıkabiliyordu
 // (her pencere kendi içinde dar ama zincir uzadıkça kapsadığı toplam fiyat aralığı büyüyor).
 // Artık birleştirme sırasında SONUÇ bandının toplam genişliği bir üst sınırı (maxZoneWidth) aşarsa
 // birleştirilmiyor, yeni bir bölge olarak ayrılıyor — böylece tek bir bölge asla makul bir
 // (gerçek, dar) destek/direnç aralığından büyük olamıyor.
 function detectConsolidationZones(dataArr){
  const a=dataArr||ohlc;
  if(a.length<40) return [];
  const N=6, atrRef=calcATR(a,14)||( (a[a.length-1].high-a[a.length-1].low)||1 );
  const maxZoneWidth=atrRef*1.4; // DÜZELTME 2: kullanıcı hâlâ çok geniş bulduğu için daha da sıkılaştırıldı
  let raw=[];
  for(let i=N;i<a.length;i++){
   const w=a.slice(i-N,i);
   const hi=Math.max(...w.map(c=>c.high)), lo=Math.min(...w.map(c=>c.low));
   if((hi-lo) < atrRef*1.2) raw.push({startIdx:i-N, endIdx:i-1, hi, lo});
  }
  let merged=[];
  raw.forEach(z=>{
   const last=merged[merged.length-1];
   if(last && z.startIdx<=last.endIdx+1){
    const newHi=Math.max(last.hi,z.hi), newLo=Math.min(last.lo,z.lo);
    if((newHi-newLo)<=maxZoneWidth){ last.endIdx=Math.max(last.endIdx,z.endIdx); last.hi=newHi; last.lo=newLo; }
    else merged.push(Object.assign({},z)); // birleşirse çok genişleyecekti — ayrı yeni bölge başlat
   }
   else merged.push(Object.assign({},z));
  });
  return merged.filter(z=>(z.endIdx-z.startIdx)>=N-1).slice(-6);
 }
 function drawZoneLines(dataArr){
  const a=dataArr||ohlc;
  zoneLines.forEach(l=>cs.removePriceLine(l)); zoneLines=[];
  const zones=detectConsolidationZones(a);
  const last=a[a.length-1]?a[a.length-1].close:0;
  // sadece fiyata en yakın 2 bölgeyi çiz (grafik kirlenmesin)
  zones.map(z=>({z,dist:Math.min(Math.abs(last-z.hi),Math.abs(last-z.lo))})).sort((a2,b)=>a2.dist-b.dist).slice(0,2).forEach(({z})=>{
   zoneLines.push(cs.createPriceLine({price:z.hi,color:'rgba(20,184,166,.85)',lineWidth:1,lineStyle:3,axisLabelVisible:true,title:t('zoneTop')}));
   zoneLines.push(cs.createPriceLine({price:z.lo,color:'rgba(20,184,166,.85)',lineWidth:1,lineStyle:3,axisLabelVisible:true,title:t('zoneBottom')}));
  });
  return zones;
 }
 // ---- FVG (Fair Value Gap) %50/CE görselleştirmesi — botTick() FARKLI bir <script> bloğunda
 // çalışıyor (cs/chart nesnelerine doğrudan erişemiyor), bu yüzden window.valensDrawFVGZone /
 // valensClearFVGZone köprü fonksiyonları üzerinden çağrılıyor. fvgRetest stratejisi devredeyken
 // boşluğun üst/alt kenarları kesikli çizgiyle, %50 (CE) seviyesi ise kalın altın çizgiyle,
 // giriş mumu da bir ok işaretiyle grafikte gösterilir.
 window.valensDrawFVGZone=function(zone, dir){
  if(!zone) return;
  fvgZoneLines.forEach(l=>cs.removePriceLine(l)); fvgZoneLines=[];
  const edgeColor = dir>0 ? 'rgba(0,200,150,.75)' : 'rgba(255,80,109,.75)';
  fvgZoneLines.push(cs.createPriceLine({price:zone.top,color:edgeColor,lineWidth:1,lineStyle:2,axisLabelVisible:true,title:t('fvgTop')}));
  fvgZoneLines.push(cs.createPriceLine({price:zone.bottom,color:edgeColor,lineWidth:1,lineStyle:2,axisLabelVisible:true,title:t('fvgBottom')}));
  fvgZoneLines.push(cs.createPriceLine({price:zone.ce,color:'#d4af37',lineWidth:2,lineStyle:0,axisLabelVisible:true,title:t('fvgCE')}));
  const lastBar = ohlc[ohlc.length-1];
  if(lastBar){
   fvgMarker = {time:lastBar.time, position:dir>0?'belowBar':'aboveBar', color:'#d4af37', shape:dir>0?'arrowUp':'arrowDown', text:t('fvgEntry')};
  }
  refreshAllMarkers();
 };
 window.valensClearFVGZone=function(){
  if(fvgZoneLines.length){ fvgZoneLines.forEach(l=>cs.removePriceLine(l)); fvgZoneLines=[]; }
  if(fvgMarker){ fvgMarker=null; refreshAllMarkers(); }
 };
 function analyze(isCloseTick){
  if(ohlc.length<20)return;
  // ---- HAFTA SONU/KAPALI PİYASA DONDURMA — kullanıcı gerçek ekran görüntüsüyle gösterdi: XAU/USD
  // GERÇEKTE kapalıyken bile grafiğimiz PAXG'nin (7/24 kripto) hareketini gösterip, destek/direnç/trend
  // çizgilerini bu SAHTE hareketten yeniden çiziyordu — "destek kırılmış, aşağı gitmiş" gibi YANILTICI
  // bir teknik görünüm yaratıyordu. Artık: piyasa şu an kapalıysa (BTC hariç), tüm analiz SADECE son
  // GERÇEK açık-piyasa mumuna kadar olan veriyle yapılır — mumlar görsel olarak (soluk gri) akmaya
  // devam eder ama S/R, trend, Fib, bölge çizgileri ve gösterge sayıları son gerçek an'da DONAR.
  let a = ohlc;
  if(curSym!=='BINANCE:BTCUSDT' && isClosedMarketTime(curSym, ohlc[ohlc.length-1].time)){
   let lastOpenIdx = ohlc.length-1;
   while(lastOpenIdx>0 && isClosedMarketTime(curSym, ohlc[lastOpenIdx].time)) lastOpenIdx--;
   a = ohlc.slice(0, lastOpenIdx+1);
   if(a.length<20) return; // henüz hiç gerçek-piyasa verisi yoksa analiz üretme
  }
  e20.setData(emaLine(a,20)); e50.setData(emaLine(a,50));
  const{sup,res}=supRes(a);
  if(dynSup)cs.removePriceLine(dynSup); if(dynRes)cs.removePriceLine(dynRes);
  dynSup=cs.createPriceLine({price:sup,color:'#00c896',lineWidth:1,lineStyle:2,title:'Dyn Support'});
  dynRes=cs.createPriceLine({price:res,color:'#ff506d',lineWidth:1,lineStyle:2,title:'Dyn Resistance'});
  drawFibonacci(a);
  drawTrendChannel(a);
  drawVolatilityBand(a);
  const zones=drawZoneLines(a);
  const pat=pattern(a);
  const lastTime=a[a.length-1].time;
  // Formasyon işaretleri KALICI: tespit edilen her mum formasyonu grafikte kalır, sadece o an
  // oluşmakta olan SON mumun girdisi (henüz mum kapanmadığı için) canlı güncellenir/kaldırılır.
  patternMarkers = patternMarkers.filter(m=>m.time!==lastTime);
  if(pat&&pat.d!=='neutral'){
   patternMarkers.push({time:lastTime, position:pat.d==='bull'?'belowBar':'aboveBar',
    color:pat.d==='bull'?'#00c896':'#ff506d', shape:pat.d==='bull'?'arrowUp':'arrowDown', text:pat.n});
  }
  if(patternMarkers.length>300) patternMarkers=patternMarkers.slice(-300); // makul bir üst sınır
  patternMarkers.sort((a,b)=>a.time-b.time); // lightweight-charts zaman sırası ister
  refreshAllMarkers();

  const last=a[a.length-1].close;
  const closes=a.map(c=>c.close);
  const w=a.slice(-60); let sx=0,sy=0,sxy=0,sxx=0;
  w.forEach((c,i)=>{sx+=i;sy+=c.close;sxy+=i*c.close;sxx+=i*i;});
  const slope=(w.length*sxy-sx*sy)/(w.length*sxx-sx*sx);
  // ---- HIZLI TREND (piyasa rejimi tespiti için AYRI, daha kısa vadeli ölçüm) — kullanıcı gerçek
  // örnekle gösterdi: fiyat desteği kırıp aşağı giderken bile bot %80 BUY veriyordu. Kök neden: rejim
  // bonusu, 60 mumluk YAVAŞ eğime bakıyordu — bu, taze bir dönüşün etkisini geç yansıtıyor, önceki
  // yükselişin "hafızası" hâlâ pozitif slope üretip trend-takip (BUY) stratejilerine haksız bonus
  // veriyordu. Rejim tespiti artık çok daha kısa (15 mum) bir eğime bakıyor — gerçek bir dönüşe çok
  // daha hızlı tepki verir, genel "confluence" oyu (cr.trend, aşağıda) hâlâ yavaş/geniş resme bakmaya
  // devam ediyor (o amaç için değişmedi).
  let fastTrend=0;
  if(a.length>=16){
   const fw=a.slice(-15); let fsx=0,fsy=0,fsxy=0,fsxx=0;
   fw.forEach((c,i)=>{fsx+=i;fsy+=c.close;fsxy+=i*c.close;fsxx+=i*i;});
   const fslope=(fw.length*fsxy-fsx*fsy)/(fw.length*fsxx-fsx*fsx);
   fastTrend = fslope>0?1:fslope<0?-1:0;
  }
  const cfg=SYMS[curSym]; let srBias=0, srText='';
  if(cfg){cfg.sr.forEach(s=>{const mid=(s.lo+s.hi)/2,dist=Math.abs(last-mid)/last;
    if(dist<0.004){ if(s.type==='s'){srBias=0.5;srText=t('srNearSupport')(s.label);}
                    else{srBias=-0.5;srText=t('srNearResistance')(s.label);} }});}
  // ANA destek/direnç (1 saatlik, o an izlenen zaman diliminden BAĞIMSIZ) — en yüksek öncelikli S/R
  // kaynağıdır ("ana destek direnç noktaları 1 saatlikten alınıyor"). Şu an izlenen aralığın kendi
  // dinamik S/R'ı ("scalp" S/R) aşağıda ayrıca hesaba katılır, ama ana 1H seviyesi öncelik kazanır.
  const nearMainSR = nearestMainSR(last);
  if(nearMainSR.sup || nearMainSR.res){
    const distMainSup = nearMainSR.sup ? Math.abs(last-nearMainSR.sup.hi)/last : Infinity;
    const distMainRes = nearMainSR.res ? Math.abs(last-nearMainSR.res.lo)/last : Infinity;
    if(distMainSup<0.004 && distMainSup<=distMainRes && Math.abs(0.7)>Math.abs(srBias)){ srBias=0.7; srText=t('srNearMainSupport'); }
    else if(distMainRes<0.004 && distMainRes<distMainSup && Math.abs(-0.7)>Math.abs(srBias)){ srBias=-0.7; srText=t('srNearMainResistance'); }
  }
  // Dinamik Dyn Support/Resistance'a (grafikte çizilen, son 60 mumdan hesaplanan gerçek çizgi — "scalp" S/R,
  // şu an izlenen zaman dilimine özel) yakınlık da hesaba katılır.
  if(typeof sup==='number' && typeof res==='number' && isFinite(sup) && isFinite(res)){
    const distSup=Math.abs(last-sup)/last, distRes=Math.abs(last-res)/last;
    if(distSup<0.003 && distSup<=distRes && Math.abs(0.6)>Math.abs(srBias)){ srBias=0.6; srText=t('srNearDynSupport'); }
    else if(distRes<0.003 && distRes<distSup && Math.abs(-0.6)>Math.abs(srBias)){ srBias=-0.6; srText=t('srNearDynResistance'); }
  }
  // Konsolidasyon/hacim birikim bölgelerine (gerçek OHLC'den tespit edilen dar-aralık pencereler) yakınlık —
  // TradingView ekranınızdaki teal kutuların karşılığı, üçüncü bir gerçek S/R kaynağı olarak skora giriyor.
  (zones||[]).forEach(z=>{
   const distTop=Math.abs(last-z.hi)/last, distBot=Math.abs(last-z.lo)/last;
   if(distBot<0.003 && distBot<=distTop && Math.abs(0.55)>Math.abs(srBias)){ srBias=0.55; srText=t('srNearZone'); }
   else if(distTop<0.003 && distTop<distBot && Math.abs(-0.55)>Math.abs(srBias)){ srBias=-0.55; srText=t('srNearZone'); }
  });
  // Fibonacci artık BAĞIMSIZ bir yön oyu değil — fiyat aynı anda hem S/R hem bir Fib seviyesindeyse
  // bunu bir "confluence" (üst üste binen destek/direnç) olarak S/R sinyaline teyit ekler.
  let fibBias=0;
  if(fibLines.length && srBias!==0){
    const up=slope>0, diff=res-sup;
    const fibLevels=[0,0.236,0.382,0.5,0.618,0.786,1].map(r=>up?res-diff*r:sup+diff*r);
    const nearFib = fibLevels.some(px=>Math.abs(last-px)/last<0.003);
    if(nearFib){ fibBias = srBias>0?0.5:-0.5; srText += t('confluenceSuffix'); }
  }
  // Manuel örüntü öğretimi eşleştirmesi için: fiyatın hangi Fib BÖLGESİNE en yakın olduğu (S/R'dan
  // bağımsız olarak) — 'shallow' (0-38.2), 'golden' (50-61.8), 'deep' (78.6-100), yoksa null.
  let fibZone=null;
  if(fibLines.length){
    const up2=slope>0, diff2=res-sup;
    const zoneMap=[{r:0.191,z:'shallow'},{r:0.382,z:'shallow'},{r:0.5,z:'golden'},{r:0.618,z:'golden'},{r:0.786,z:'deep'},{r:1,z:'deep'}];
    let best=null, bestDist=Infinity;
    zoneMap.forEach(zm=>{ const px=up2?res-diff2*zm.r:sup+diff2*zm.r; const d=Math.abs(last-px)/last; if(d<bestDist){bestDist=d;best=zm.z;} });
    if(bestDist<0.006) fibZone=best;
  }

  // ---- GERÇEK İNDİKATÖRLER: gerçek OHLC'den hesaplanır (rastgele değil) ----
  const rsiReal=calcRSIReal(closes,14);
  const macdReal=(emaValue(closes.slice(-40),12)||last)-(emaValue(closes.slice(-60),26)||last);
  const ema9Real=emaValue(closes.slice(-30),9)||last;
  const ema21Real=emaValue(closes.slice(-50),21)||last;
  const ema50Real=emaValue(closes.slice(-90),50)||last;
  const ema200Real=emaValue(closes,200)||last;
  const bollPctReal=calcBollPct(closes,20);
  const stochReal=calcStoch(a,14);
  const adxReal=calcADXReal(a,14);
  const atrReal=calcATR(a,14);
  const vwapReal=calcVWAP(a,96);
  const wrReal=calcWilliamsR(a,14);
  const cciReal=calcCCI(a,20);
  const psarReal=calcPSAR(a);
  const pivotsReal=calcPivots(a);
  const strategyTags = detectStrategyTags(a, {rsi:rsiReal, macd:macdReal, ema9:ema9Real, ema21:ema21Real, ema50:ema50Real, ema200:ema200Real, vwap:vwapReal, zones:zones, bollPct:bollPctReal!==null?bollPctReal:50, srBias:srBias, fibZone:fibZone, tradeDelta:(typeof currentTradeDelta==='function'?currentTradeDelta():null)});

  window.valensChartRead={
    trend: slope>0?1:slope<0?-1:0,
    fastTrend,
    pattern: pat?(pat.d==='bull'?1:pat.d==='bear'?-1:0):0,
    patternName: pat?pat.n:'',
    srBias, srText, fibBias, fibZone, strategyTags,
    structureBias: detectSwingStructure(a, 60),
    exhaustionBias: detectReversalExhaustion(a, 8),
    // ---- Kullanıcı geri bildirimi: SELL sinyalinin TP'si Ana Destek'in (1H) ALTINA konmuştu — yani
    // hedefe ulaşmak için fiyatın gerçek desteği kırması gerekiyordu, ki kırarsa zaten daha aşağı gider,
    // orada durup TP'ye "temiz" ulaşması gerçekçi değil. TP/SL hesaplaması botTick'te (ayrı script)
    // yapılıyor, o yüzden gerçek S/R seviyeleri buradan köprüleniyor — botTick artık TP'yi bu
    // seviyelerin ÖNÜNDE (kırmadan) kesiyor.
    // mainSup/mainRes: en yakın bölgenin fiyata BAKAN kenarı (ör. destek bölgesinin ÜST sınırı) —
    // TP bu noktayı geçmeden kırpılır, yani bölgeye "ilk temas" noktası baz alınır.
    srLevels: {mainSup:nearestMainSR(last).sup?nearestMainSR(last).sup.hi:null, mainRes:nearestMainSR(last).res?nearestMainSR(last).res.lo:null,
               dynSup:(typeof sup==='number'&&isFinite(sup))?sup:null, dynRes:(typeof res==='number'&&isFinite(res))?res:null},
    hasLiveData:true,
    candleTime: a[a.length-1].time, // mevcut mumun SABİT zaman damgası — sinyal tekilleştirmede kullanılır
    hourlyMove: estimateHourlyMovement(a), // saatlik tipik hareket — TP ulaşılabilirlik sınırı için
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
 // ---- Grafik verisi önbelleği: terminali her açtığınızda WebSocket'in yeniden bağlanmasını beklemeden
 // ÖNCEKİ oturumdan kalma veriyi anında gösterir, sonra taze veriyle günceller. ----
 function ohlcCacheKey(sym,intv){ return 'valens_ohlc_'+sym.replace(/[:\/]/g,'_')+'_'+intv; }
 function saveOhlcCache(sym,intv,data){
  try{ localStorage.setItem(ohlcCacheKey(sym,intv), JSON.stringify({ts:Date.now(), data:data.slice(-1000)})); }catch(e){}
 }
 function loadOhlcCache(sym,intv){
  try{
   const raw=localStorage.getItem(ohlcCacheKey(sym,intv)); if(!raw) return null;
   const parsed=JSON.parse(raw);
   if(Date.now()-parsed.ts > 24*3600*1000) return null; // 24 saatten eski önbellek kullanılmaz
   return parsed.data;
  }catch(e){ return null; }
 }
 function filterClosedMarketCandles(arr, sym){
  if(sym==='BINANCE:BTCUSDT') return arr;
  return arr.filter(c=>!isClosedMarketTime(sym, c.time));
 }
 async function loadHistory(){
  const intv=currentBinInterval();
  // Önce önbellekten (varsa) anında göster — kullanıcı sayfayı her açtığında boş grafik görmesin
  const cached=loadOhlcCache(curSym,intv);
  if(cached && cached.length){ ohlc=filterClosedMarketCandles(cached,curSym); cs.setData(ohlc); showRecentRange(); analyze(true); }
  try{
   // Binance REST API'de tek istekte alınabilecek azami mum sayısı 1000'dir — önceki 200 limiti
   // gereksiz yere veriyi kısıtlıyordu (15dk'da sadece ~50 saat; 1000 ile ~10 gün).
   const r=await fetch(`https://api.binance.com/api/v3/klines?symbol=${binSym}&interval=${intv}&limit=1000`);
   const d=await r.json();
   if(!Array.isArray(d))throw new Error('no data');
   // ---- GERÇEK XAU/USD (ya da EUR/USD) PİYASASI KAPALIYKEN OLUŞAN MUMLAR TAMAMEN ATILIR ----
   // Kullanıcı gerçek ekran görüntüsüyle gösterdi: sadece analiz çizgilerini dondurmak yetmiyor —
   // mumların kendisi hâlâ görünüp hareket etmeye devam edince grafiği okurken kafa karıştırıcı
   // oluyordu. Artık hafta sonu/kapalı-piyasa PAXG hareketi grafiğe HİÇ girmiyor — sanki o saatler
   // hiç yaşanmamış gibi, gerçek bir forex/emtia platformunun hafta sonu davranışıyla aynı.
   ohlc=filterClosedMarketCandles(d.map(k=>({time:k[0]/1000,open:+k[1],high:+k[2],low:+k[3],close:+k[4],volume:+k[5]})), curSym);
   cs.setData(ohlc); showRecentRange(); analyze(true);
   saveOhlcCache(curSym,intv,ohlc);
   setTimeout(()=>{
    window.valensBacktestResults = runHistoricalBacktest();
    if(window.valensRenderBacktestPanel) window.valensRenderBacktestPanel(window.valensBacktestResults);
   }, 50); // taze veri sonrası, tarayıcının önce çizimi bitirmesine izin vermek için küçük bir gecikme
  }catch(e){console.error('history err',e);}
 }
 function connect(){
  if(ws){ws.close();ws=null;}
  const intv=currentBinInterval();
  ws=new WebSocket(`wss://stream.binance.com:9443/ws/${binSym.toLowerCase()}@kline_${intv}`);
  ws.onmessage=ev=>{
   const k=JSON.parse(ev.data).k;
   const bar={time:k.t/1000,open:+k.o,high:+k.h,low:+k.l,close:+k.c,volume:+k.v};
   if(isClosedMarketTime(curSym, bar.time)) return; // gerçek piyasa kapalıyken gelen mumu grafiğe hiç yansıtma
   const last=ohlc[ohlc.length-1];
   if(last&&last.time===bar.time)ohlc[ohlc.length-1]=bar; else{ohlc.push(bar);if(ohlc.length>1000)ohlc.shift();}
   cs.update(bar); analyze(k.x);
   if(k.x) saveOhlcCache(curSym,intv,ohlc); // sadece mum KAPANDIĞINDA önbelleği güncelle (her tick'te yazmaya gerek yok)
  };
 }
 // Tüm işlemlerin (sadece yüklü olanların değil) alım/satım hacmini kayan bir pencerede biriktirir —
 // "Trades Delta" (agresif alım hacmi - agresif satım hacmi) gerçek Binance verisinden hesaplanır.
 let deltaWindow=[];
 function currentTradeDelta(){
  const cutoff=Date.now()-5*60*1000; // son 5 dakika
  deltaWindow=deltaWindow.filter(d=>d.t>=cutoff);
  let buy=0, sell=0;
  deltaWindow.forEach(d=>{ if(d.buy) buy+=d.notional; else sell+=d.notional; });
  const total=buy+sell;
  return total>0 ? (buy-sell)/total : 0; // -1..+1 arası, +1 tamamen alım baskın
 }
 function connectTrades(){
  if(tradeWs){tradeWs.close();tradeWs=null;}
  deltaWindow=[];
  tradeWs=new WebSocket(`wss://stream.binance.com:9443/ws/${binSym.toLowerCase()}@aggTrade`);
  const TH = binSym==='BTCUSDT'?200000 : binSym==='PAXGUSDT'?150000 : 100000;
  tradeWs.onmessage=ev=>{
   const t=JSON.parse(ev.data);
   const qty=+t.q, px=+t.p, notional=qty*px;
   const buy = !t.m;
   deltaWindow.push({t:Date.now(), buy, notional});
   if(notional < TH) return;
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
  curSym=sym; window.valensCurSym=sym;
  if(ws){ws.close();ws=null;} if(tradeWs){tradeWs.close();tradeWs=null;}
  // ---- ESKİ PARİTENİN TÜM ÇİZGİLERİNİ TEMİZLE (eksen takılmasın) ----
  cs.setMarkers([]); trendSeries.setData([]); chanUp.setData([]); chanLo.setData([]);
  kelUp.setData([]); kelLo.setData([]);
  patternMarkers=[]; // farklı enstrümana geçince eski sembolün formasyon geçmişini taşıma
  fvgZoneLines.forEach(l=>cs.removePriceLine(l)); fvgZoneLines=[]; fvgMarker=null;
  e20.setData([]); e50.setData([]);
  srLines.forEach(l=>cs.removePriceLine(l)); srLines=[];
  fibLines.forEach(l=>cs.removePriceLine(l)); fibLines=[];
  zoneLines.forEach(l=>cs.removePriceLine(l)); zoneLines=[];
  mainSRZones=[]; mainSRZoneEls.forEach(d=>{ if(d) d.style.display='none'; });
  mainSRHistoryLines.forEach(l=>cs.removePriceLine(l)); mainSRHistoryLines=[]; mainSRHistory=[];
  if(dynSup){cs.removePriceLine(dynSup);dynSup=null;}
  if(dynRes){cs.removePriceLine(dynRes);dynRes=null;}
  ohlc=[]; cs.setData([]);
  binSym=MAP[sym];
  if(!binSym){
   window.valensChartRead={hasLiveData:false};
   closedEl.style.display='flex';
   closedEl.innerHTML='<span>'+t('noLiveFeedTitle')+'</span><small>'+t('noLiveFeedDesc')+'</small>';
   drawSRLines(); chart.priceScale('right').applyOptions({autoScale:true}); return;
  }
  window.valensChartRead={};
  closedEl.style.display='none';
  window.valensCandleLock=null;
  fetchMainSR(sym);
  loadHistory().then(()=>{
    drawSRLines(); connect(); connectTrades();
    // ---- EKSENİ YENİ FİYATA OTURT ----
    chart.priceScale('right').applyOptions({autoScale:true});
    showRecentRange();
  });
  setTimeout(resize,120);
 };
 setInterval(()=>{ if(curSym && binSym) fetchMainSR(curSym); }, 5*60*1000); // ana S/R'ı 5 dakikada bir tazele
 // ---- Zaman dilimi (15M/30M/1H/4H/1D) değiştiğinde GERÇEKTEN yeni aralıkta veri çeker ----
 // Önceden zaman dilimi butonları sadece başlık yazısını değiştiriyordu, veri her zaman 15m kalıyordu.
 window.valensSetInterval=function(){
  if(!binSym) return; // canlı veri akışı olmayan enstrüman (ör. SPX500) — yapacak bir şey yok
  if(ws){ws.close();ws=null;} if(tradeWs){tradeWs.close();tradeWs=null;}
  cs.setMarkers([]); trendSeries.setData([]); chanUp.setData([]); chanLo.setData([]);
  kelUp.setData([]); kelLo.setData([]);
  patternMarkers=[];
  fvgZoneLines.forEach(l=>cs.removePriceLine(l)); fvgZoneLines=[]; fvgMarker=null;
  e20.setData([]); e50.setData([]);
  srLines.forEach(l=>cs.removePriceLine(l)); srLines=[];
  fibLines.forEach(l=>cs.removePriceLine(l)); fibLines=[];
  zoneLines.forEach(l=>cs.removePriceLine(l)); zoneLines=[];
  if(dynSup){cs.removePriceLine(dynSup);dynSup=null;}
  if(dynRes){cs.removePriceLine(dynRes);dynRes=null;}
  ohlc=[]; cs.setData([]);
  window.valensChartRead={};
  window.valensCandleLock=null;
  loadHistory().then(()=>{
   drawSRLines(); connect(); connectTrades();
   chart.priceScale('right').applyOptions({autoScale:true});
   showRecentRange();
  });
 };
 window.valensSetSymbol(CUR);
})();
</script>
</body>
</html>
"""

TERMINAL_HTML = TERMINAL_HTML.replace("__COT_DATA__", COT_JSON).replace("__ECON_DATA__", ECON_JSON)
components.html(TERMINAL_HTML, height=1550, scrolling=True)
