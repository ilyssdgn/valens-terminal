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
.krtoast{position:fixed;top:16px;right:16px;z-index:9999;max-width:340px;padding:10px 14px;border-radius:6px;border:1px solid rgba(0,200,150,.55);background:linear-gradient(90deg,rgba(0,200,150,.16),rgba(0,0,0,.55));display:none;align-items:center;gap:10px;box-shadow:0 4px 18px rgba(0,0,0,.35);opacity:0;transform:translateY(-6px);transition:opacity .25s,transform .25s}
.krtoast.show{display:flex;opacity:1;transform:translateY(0)}
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
      <div class="ph"><b data-i18n="eliteScalp_title">⚡ VALENS ELİT SCALP — PERFORMANS</b><span class="badge" id="eliteScalpBadge">—</span></div>
      <div style="padding:9px">
        <div style="font-size:8px;color:var(--muted);margin-bottom:7px" data-i18n="eliteScalpHint">Üst zaman dilimi (4H/1H) yönü, GERÇEK backtest'te en güvenilir çıkan kalıp (Order Block Mitigasyonu) ve canlı alım/satım akışından (delta) HERHANGİ İKİSİ aynı yönde birleştiğinde ateşlenen, bu terminale özgü strateji — aynı indikatör/grafik verisini kullanır ama terminalin üstteki AI SIGNAL ENGINE'inden TAMAMEN BAĞIMSIZ karar verir ve kendi işlemini burada takip eder, üstteki motoru hiç etkilemez. Aşağıda sonuçlanan HER işlem, hem girişteki hem sonuçtaki gerçek gerekçesiyle listelenir.</div>
        <div id="eliteScalpLive" style="font-size:10px;font-weight:700;padding:7px 8px;border-radius:4px;background:rgba(255,255,255,0.03);margin-bottom:8px">—</div>
        <div id="eliteScalpSummary" style="font-size:9px;color:var(--muted);line-height:1.6;margin-bottom:6px">—</div>
        <div id="eliteScalpList" style="max-height:230px;overflow:auto"></div>
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
      <div class="krtoast" id="krToast"><span style="font-size:16px">🔒</span><div><b id="krToastTitle">—</b><br><span id="krToastBody">—</span></div></div>

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
  trailedSLTitle:'🔒 Kilitli Stop', eliteTrailedSLTitle:'🔒 Elit Kilitli Stop',
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
  tagValensEliteScalp:'⚡ Valens Elit Scalp (4H/1H Bias + Order Block Mit. + Delta üçlü onay)',
  tagSrTestReversal:'Ana/Ara Destek-Direnç Test + Tepki', tagSrBreakContinuation:'Ana/Ara Destek-Direnç Kırılım + Devam',
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
  mt5CandleWait4MinBtn:'⏸ 2. Gönderim İçin 4dk Bekleniyor',
  mt5AutoSendLabel:'🤖 Otomatik Gönder — SADECE DEMO hesap için (onay beklemeden gönderir)',
  mt5AutoMinConfLabel:'Min. güven (%)',
  mt5AutoSendWarn:'⚠ Bu kutu işaretliyken TÜM işlemler onay beklemeden gerçek MT5 hesabına gönderilir. Sadece demo/test hesabında kullanın — gerçek parada KAPALI tutun.',
  eliteScalp_title:'⚡ VALENS ELİT SCALP — PERFORMANS',
  eliteScalpHint:'Üst zaman dilimi (4H/1H) yönü, GERÇEK backtest\'te en güvenilir çıkan kalıp (Order Block Mitigasyonu) ve canlı alım/satım akışından (delta) HERHANGİ İKİSİ aynı yönde birleştiğinde ateşlenen, bu terminale özgü strateji — aynı indikatör/grafik verisini kullanır ama terminalin üstteki AI SIGNAL ENGINE\'inden TAMAMEN BAĞIMSIZ karar verir ve kendi işlemini burada takip eder, üstteki motoru hiç etkilemez. Aşağıda sonuçlanan HER işlem, hem girişteki hem sonuçtaki gerçek gerekçesiyle listelenir.',
  eliteScalpLiveIdle:'Beklemede — üç şarttan (4H/1H bias + Order Block Mitigasyonu + delta) en az ikisi henüz aynı yönde birleşmedi',
  eliteScalpLiveActive:(dir)=>'AKTİF — '+dir+' · şart karşılandı',
  eliteScalpBadge:(n)=>n+' İŞLEM',
  eliteScalpSummaryLine:(total,wins,losses,net)=>total+' işlem izlendi · <span style="color:var(--green)">'+wins+' kâr</span> / <span style="color:var(--red)">'+losses+' zarar</span> · Net: <b>'+net+'</b> (ortalama lot varsayımıyla tahmini)',
  eliteScalpEmpty:'Henüz sonuçlanan bir işlem yok — Destek/Direnç, EMA/MACD Kesişimi ve ORB stratejilerinden (17 yıllık gerçek veriyle doğrulanmış 3\'lü portföy) biri tetiklendiğinde burada birikmeye başlayacak.',
  pmWinLeftOnTable:(usd)=>'📈 Kâr alındı ama çıkıştan sonra fiyat aynı yönde $'+usd+' daha ilerledi — hedef biraz daha geniş tutulsaydı kâr artabilirdi.',
  pmWinGoodExit:'✅ Kâr alımından sonra fiyat durdu/geri döndü — hedef isabetli ayarlanmıştı.',
  pmLossHadProfit:(usd)=>'⚠️ Zarar öncesi pozisyon $'+usd+' kâra geçmişti — erken kâr koruma/trailing devreye girseydi bu zarar önlenebilirdi.',
  pmLossStopTooTight:(usd)=>'⚠️ Stop\'tan hemen sonra fiyat asıl yönümüze $'+usd+' geri döndü — stop biraz daha geniş olsaydı işlem kurtulabilirdi.',
  pmLossNoProfitEver:'❌ Fiyat kesintisiz aleyhimize gitti, hiç kâra geçmedi — sorun stop mesafesi değil, giriş sinyali/zamanlamasıydı.',
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
  outcomePrefix:'🎯 Sonuç anı:', outcomeTrendUp:'EMA yapısı yükseliş yönlü', outcomeTrendDown:'EMA yapısı düşüş yönlü', outcomeTrendFlat:'EMA yapısı yatay',
  outcomeRsi:(v)=>'RSI '+v, outcomeAdxStrong:(v)=>'ADX '+v+' (güçlü trend)', outcomeAdxWeak:(v)=>'ADX '+v+' (zayıf/yatay)',
  tradeLogBadge:(n)=>n+' İŞLEM',
  tradeLogSummaryLine:(total,wins,losses,net)=>total+' işlem izlendi · <span style="color:var(--green)">'+wins+' kâr</span> / <span style="color:var(--red)">'+losses+' zarar</span> · Net: <b>'+net+'</b> (ortalama lot varsayımıyla tahmini)',
  tradeLogEmpty:'Henüz sonuçlanan bir sinyal yok — bir sinyal TP veya SL\'ye ulaştığında burada listelenecek.',
  tradeLogWin:'✓', tradeLogLoss:'✗',
  trailLockNote:'🔒 Kâr koruma: TP\'nin %75\'i tamamlandığında stop, hedefin yarısına çekildi',
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
  positionOpenStatus:'⏸ POZİSYON SINIRI — bu paritede 3 açık pozisyon dolu ya da bu mumda zaten işlem açıldı',
  circuitPausedStatus:(min)=>'🛑 ARDIŞIK 3 KAYIP — tüm yeni sinyaller '+min+' dk duraklatıldı',
  circuitPausedWhyRegime:(min,dir)=>' <span style="color:#ff6b6b">🛑 Art arda 3 '+dir+' kaybı — piyasa rejimi/trend işlemler açıldıktan sonra değişmiş görünüyor. Sistem '+min+' dk tamamen duruyor, sonra yeniden teyit isteyecek.</span>',
  circuitPausedWhyGeneric:(min,dir)=>' <span style="color:#ff6b6b">🛑 Art arda 3 '+dir+' kaybı — hesabı korumak için sistem '+min+' dk tamamen duruyor. Devam ederken aynı yön için daha güçlü teyit isteyecek, ters yön normal çalışmaya devam edecek.</span>',
  circuitPenaltyWhyNote:(dir)=>' <span style="color:#ffb27a">⚠ Az önce art arda 3 '+dir+' kaybı oldu — bu yöndeki yeni adaylara ekstra güven cezası uygulanıyor (daha güçlü sinyal isteniyor), ters yön etkilenmiyor.</span>',
  profitLockToastTitle:'🔒 KÂR KORUMADAN KAPANDI',
  profitLockToastBody:(sym,dir,usd)=>sym+' '+dir+' işlemi kâr koruma seviyesinden kapatıldı (mum kapanış teyidiyle) · ≈ +$'+usd,
  riskReducedToastTitle:'⚠ RİSK AZALTILDI',
  riskReducedToastBody:(sym,dir)=>sym+' '+dir+' işleminde belirsiz bir dönüş sinyali görüldü — stop entry\'ye yaklaştırıldı, olası zarar küçültüldü.',
  profitLockArmedToastTitle:'🔒 KÂR KORUMA DEVREDE',
  profitLockArmedToastBody:(sym,dir)=>sym+' '+dir+' işleminde net yönlü bir dönüş sinyali görüldü — stop entry\'nin üzerine çekildi, küçük bir kâr kilitlendi.',
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
  trailedSLTitle:'🔒 Locked Stop', eliteTrailedSLTitle:'🔒 Elite Locked Stop',
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
  tagValensEliteScalp:'⚡ Valens Elite Scalp (4H/1H Bias + Order Block Mit. + Delta triple confirmation)',
  tagSrTestReversal:'Main/Intermediate S/R Test + Reaction', tagSrBreakContinuation:'Main/Intermediate S/R Break + Continuation',
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
  mt5CandleWait4MinBtn:'⏸ Waiting 4min For 2nd Send',
  mt5AutoSendLabel:'🤖 Auto-Send — DEMO accounts ONLY (sends without waiting for approval)',
  mt5AutoMinConfLabel:'Min. confidence (%)',
  mt5AutoSendWarn:"⚠ While this is checked, EVERY trade is sent to the real MT5 account without waiting for approval. Only use this on a demo/test account — keep it OFF with real money.",
  eliteScalp_title:'⚡ VALENS ELITE SCALP — PERFORMANCE',
  eliteScalpHint:'Fires when ANY TWO of the three — the higher timeframe (4H/1H) direction, the pattern that real backtesting shows is most reliable (Order Block Mitigation), and live buy/sell flow (delta) — agree on the same direction at once, a strategy unique to this terminal. Uses the same indicator/chart data but decides and tracks its own trade COMPLETELY INDEPENDENTLY of the AI Signal Engine above; it never affects that engine. Every resolved trade below is listed with its real reasoning, both at entry and at outcome.',
  eliteScalpLiveIdle:'Idle — fewer than two of the three conditions (4H/1H bias + Order Block Mitigation + delta) currently agree',
  eliteScalpLiveActive:(dir)=>'ACTIVE — '+dir+' · condition met',
  eliteScalpBadge:(n)=>n+' TRADES',
  eliteScalpSummaryLine:(total,wins,losses,net)=>total+' trades tracked · <span style="color:var(--green)">'+wins+' won</span> / <span style="color:var(--red)">'+losses+' lost</span> · Net: <b>'+net+'</b> (estimated using average lot)',
  eliteScalpEmpty:'No trade has resolved yet — once one of the Support/Resistance, EMA/MACD Cross, or ORB strategies (a 3-strategy portfolio validated on 17 years of real data) fires, results will accumulate here.',
  pmWinLeftOnTable:(usd)=>'📈 Profit taken, but price kept moving the same direction by $'+usd+' after exit — a wider target could have captured more.',
  pmWinGoodExit:'✅ Price stalled/reversed after the take-profit — the target was well placed.',
  pmLossHadProfit:(usd)=>'⚠️ This position was up $'+usd+' before the loss — an earlier profit-lock/trailing stop could have prevented this loss.',
  pmLossStopTooTight:(usd)=>'⚠️ Price reversed back $'+usd+' in our original direction right after the stop — a wider stop could have saved this trade.',
  pmLossNoProfitEver:'❌ Price moved against us the entire time, never turned profitable — the issue was entry timing/direction, not stop distance.',
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
  outcomePrefix:'🎯 At close:', outcomeTrendUp:'EMA structure bullish', outcomeTrendDown:'EMA structure bearish', outcomeTrendFlat:'EMA structure flat',
  outcomeRsi:(v)=>'RSI '+v, outcomeAdxStrong:(v)=>'ADX '+v+' (strong trend)', outcomeAdxWeak:(v)=>'ADX '+v+' (weak/ranging)',
  tradeLogBadge:(n)=>n+' TRADES',
  tradeLogSummaryLine:(total,wins,losses,net)=>total+' trades tracked · <span style="color:var(--green)">'+wins+' won</span> / <span style="color:var(--red)">'+losses+' lost</span> · Net: <b>'+net+'</b> (estimated using average lot)',
  tradeLogEmpty:'No signal has resolved yet — trades will appear here once TP or SL is reached.',
  tradeLogWin:'✓', tradeLogLoss:'✗',
  trailLockNote:'🔒 Profit lock: once TP was 75% complete, stop was moved to half the target',
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
  positionOpenStatus:'⏸ POSITION LIMIT — this pair already has 3 open positions or a trade already opened this candle',
  circuitPausedStatus:(min)=>'🛑 3 LOSSES IN A ROW — all new signals paused for '+min+' min',
  circuitPausedWhyRegime:(min,dir)=>' <span style="color:#ff6b6b">🛑 3 '+dir+' losses in a row — the market regime/trend looks like it changed after these trades opened. The system is fully pausing for '+min+' min, then will require fresh confirmation.</span>',
  circuitPausedWhyGeneric:(min,dir)=>' <span style="color:#ff6b6b">🛑 3 '+dir+' losses in a row — to protect the account the system is fully pausing for '+min+' min. When it resumes, the same direction will need stronger confirmation; the opposite direction is unaffected.</span>',
  circuitPenaltyWhyNote:(dir)=>' <span style="color:#ffb27a">⚠ 3 '+dir+' losses just happened in a row — new candidates in this direction get an extra confidence penalty (need a stronger signal); the opposite direction is unaffected.</span>',
  profitLockToastTitle:'🔒 CLOSED VIA PROFIT LOCK',
  profitLockToastBody:(sym,dir,usd)=>sym+' '+dir+' trade closed at the profit-lock level (confirmed by candle close) · ≈ +$'+usd,
  riskReducedToastTitle:'⚠ RISK REDUCED',
  riskReducedToastBody:(sym,dir)=>sym+' '+dir+' trade showed an ambiguous reversal signal — stop moved closer to entry, potential loss reduced.',
  profitLockArmedToastTitle:'🔒 PROFIT LOCK ARMED',
  profitLockArmedToastBody:(sym,dir)=>sym+' '+dir+' trade showed a clear directional reversal — stop moved above entry, a small profit is now locked in.',
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
  if(openPositionCountForSymbol(sym)>=3) return; // paritede max 3 eşzamanlı açık pozisyon
  if(candleAlreadyUsed(sym,candleTime)) return; // aynı mumda ikinci bir işlem açılmaz
  // candleTime: chart.timeScale().timeToCoordinate() SADECE grafikte GERÇEKTEN çizili bir mumun
  // TAM zaman değerini kabul ediyor (Date.now() gibi rastgele bir saniye DEĞİL — test edip
  // doğruladım, aradaki fark 1dk'dan bile az olsa null dönüyor) — 1M Scalp Modu kutu çizimi bu
  // yüzden ts (Date.now()) değil, cr.candleTime'dan gelen bu alanı kullanıyor.
  // lot: DÜZELTME (kullanıcı geri bildirimi: "eski dönemde lot 1-1.5 civarındaydı, bu terminali
  // yanıltıyor mu") — eskiden $ hesabı HER ZAMAN o anki (güncel) risk ayarındaki avgLot()'u
  // kullanıyordu, geçmiş işlemlere bile — yani lot ayarı değiştikçe ESKİ işlemlerin görünen $'ı da
  // geriye dönük değişiyordu (tarihsel olarak yanlış). Artık işlem AÇILDIĞI ANDAKİ lot burada
  // donduruluyor; getAllResolvedTrades/getEliteScalpResolvedTrades bunu kullanır (bu alan yoksa —
  // bu değişiklikten ÖNCEKİ eski kayıtlar — geriye dönük uyumluluk için güncel avgLot()'a düşer).
  const trade={ts:Date.now(),dir,entry,tp,sl,resolved:false,outcome:null,stratKey:stratKey||null,stratLabel:stratLabel||null,context:context||null,candleTime:candleTime||null,lot:avgLot(),mfe:0,mae:0};
  store.trades.push(trade);
  if(store.trades.length>500)store.trades=store.trades.slice(-500);
  saveTradeStore(sym,store);
  // 7/24 sunucudaki merkezi sinyal API'sine bağlıysa buraya da kaydedilir (bkz. pushSignalToApi
  // aşağıda) — bağlı değilken bu no-op'tur, localStorage davranışı hiç değişmez.
  pushSignalToApi(sym, trade.ts, {sym, dir, entry, tp, sl, stratKey:stratKey||null, stratLabel:stratLabel||null, context:context||null, ts:trade.ts, lot:trade.lot});
}
// ============ ⚡ VALENS ELİT SCALP — TAMAMEN BAĞIMSIZ TAKİP ============
// Kullanıcı düzeltmesi: "terminal gene çalışmaya devam etsin... bizim stratejimiz sadece ai signal
// engine yazan yerde değil soldaki kendi bölmesinde çalışacak" — bu strateji artık ana motorun
// candidates/best/logArmedTrade akışına HİÇ karışmıyor (bkz. botTick, eliteScalpTag ayrımı). Kendi
// AYRI localStorage kaydı (valens_elite_trades_*) ve kendi "tek açık işlem" kilidi var — ana motorun
// o an açık bir işlemi olsa bile bu strateji bağımsız kendi işlemini açıp takip edebilir.
const ELITE_TRADE_STORE_PREFIX='valens_elite_trades_';
function getEliteTradeKey(sym){return ELITE_TRADE_STORE_PREFIX+sym.replace(/[:\/]/g,'_');}
function loadEliteTradeStore(sym){try{const raw=localStorage.getItem(getEliteTradeKey(sym));if(!raw)return{trades:[]};return JSON.parse(raw);}catch(e){return{trades:[]};}}
function saveEliteTradeStore(sym,store){try{localStorage.setItem(getEliteTradeKey(sym),JSON.stringify(store));}catch(e){}}
// ---- PARİTE BAŞINA POZİSYON DİSİPLİNİ ----
// Kullanıcı geri bildirimi (başka bir deneysel bot ile karşılaştırma, sonra kullanıcının kendi
// düzeltmesi): önce "hesap-geneli tam olarak 1 açık pozisyon" kuralı denendi, ama kullanıcı bunun
// yerine daha esnek bir kural istedi — her paritede (sembolde) en fazla 3 eşzamanlı açık pozisyon
// (ana motor + Elite Scalp toplamı), VE aynı mum içinde en fazla 1 YENİ pozisyon açılabilir (aynı
// mumda ikinci/üçüncü pozisyonun açılması, gürültüyle/flip-flop'la üst üste girişi önler — 3'e kadar
// çıkmak için en az 3 FARKLI mum gerekir). Bu, "aynı anda 8'e kadar pozisyon" ve "aynı sembolde aynı
// anda hem AL hem SAT" riskini tamamen ortadan kaldırmasa da (kasıtlı olarak paritede sınırlı,
// hesap-geneli değil), art arda/aynı mumda patlayan pozisyon yığılmasını engelliyor.
function openPositionCountForSymbol(sym){
  const mainOpen=(loadTradeStore(sym).trades||[]).filter(t=>!t.resolved).length;
  const eliteOpen=(loadEliteTradeStore(sym).trades||[]).filter(t=>!t.resolved).length;
  const combo3Open=(loadCombo3Store(sym).trades||[]).filter(t=>!t.resolved).length;
  return mainOpen+eliteOpen+combo3Open;
}
function candleAlreadyUsed(sym, candleTime){
  if(candleTime==null) return false;
  const mainTrades=loadTradeStore(sym).trades||[];
  const eliteTrades=loadEliteTradeStore(sym).trades||[];
  return mainTrades.some(t=>t.candleTime===candleTime) || eliteTrades.some(t=>t.candleTime===candleTime);
}
function logEliteScalpTrade(sym,dir,entry,tp,sl,context,candleTime){
  const store=loadEliteTradeStore(sym);
  store.trades=store.trades||[];
  if(openPositionCountForSymbol(sym)>=3) return; // paritede max 3 eşzamanlı açık pozisyon
  if(candleAlreadyUsed(sym,candleTime)) return; // aynı mumda ikinci bir işlem açılmaz
  const trade={ts:Date.now(),dir,entry,tp,sl,resolved:false,outcome:null,stratKey:'valensEliteScalp',stratLabel:t('tagValensEliteScalp'),context:context||null,candleTime:candleTime||null,lot:avgLot()};
  store.trades.push(trade);
  if(store.trades.length>500)store.trades=store.trades.slice(-500);
  saveEliteTradeStore(sym,store);
  pushSignalToApi(sym, trade.ts, {sym, dir, entry, tp, sl, stratKey:'valensEliteScalp', stratLabel:trade.stratLabel, context:context||null, ts:trade.ts, lot:trade.lot}, true);
}
function updateEliteScalpTradeOutcomes(sym,lastPrice,cr,justClosedCandlePrice){
  const store=loadEliteTradeStore(sym);
  let changed=false;
  (store.trades||[]).forEach(t=>{
    if(t.resolved)return;
    if(applyTrailingStop(t, lastPrice, cr, window.valensDrawEliteTrailedSL)){
      changed=true;
      if(t.protectLevel===1 && window.valensShowRiskReducedToast) window.valensShowRiskReducedToast(sym, t.dir);
      else if(t.protectLevel===2 && window.valensShowProfitLockArmedToast) window.valensShowProfitLockArmedToast(sym, t.dir);
    }
    let exitPrice=null, closedViaProfitLock=false;
    if(t.dir>0){
      if(lastPrice>=t.tp) exitPrice=t.tp;
      else if(!t.slAdjusted && lastPrice<=t.sl) exitPrice=t.sl;
      else if(t.slAdjusted && justClosedCandlePrice!=null && justClosedCandlePrice<=t.sl){ exitPrice=t.sl; closedViaProfitLock=true; }
    }else if(t.dir<0){
      if(lastPrice<=t.tp) exitPrice=t.tp;
      else if(!t.slAdjusted && lastPrice>=t.sl) exitPrice=t.sl;
      else if(t.slAdjusted && justClosedCandlePrice!=null && justClosedCandlePrice>=t.sl){ exitPrice=t.sl; closedViaProfitLock=true; }
    }
    if(exitPrice!=null){
      t.resolved=true;
      t.exitPrice=exitPrice;
      t.outcome = (t.dir*(exitPrice-t.entry) >= 0) ? 'win' : 'loss';
      t.outcomeContext=buildOutcomeContext(cr,lastPrice);
      changed=true;
      resolveSignalOnApi(t);
      if(window.valensClearEliteTrailedSL) window.valensClearEliteTrailedSL();
      if(closedViaProfitLock && window.valensShowProfitLockToast){
        const cs=SYMS[sym].contractSize, lot=(t.lot!=null?t.lot:avgLot());
        window.valensShowProfitLockToast(sym, t.dir, Math.round(t.dir*(exitPrice-t.entry)*cs*lot));
      }
    }
  });
  if(changed)saveEliteTradeStore(sym,store);
}
// getAllResolvedTrades() ile AYNI desen (merkezi API bağlıysa oradan, değilse localStorage'dan) ama
// SADECE bu stratejinin AYRI mağazasından — genel işlem geçmişiyle hiç karışmaz.
function getEliteScalpResolvedTrades(){
  const fallbackLot=avgLot();
  if(window.valensSignalApiConnected && window.valensCentralSignals){
    return window.valensCentralSignals.filter(s=>s.resolved && s.stratKey==='valensEliteScalp').map(s=>{
      const cs2=(SYMS[s.sym]||{}).contractSize||100;
      const lot = s.lot!=null ? s.lot : fallbackLot;
      // exitPrice: DÜZELTME (kâr koruma/trailing stop) — GERÇEKTE dokunulan seviye (tp VEYA kâr
      // bölgesine çekilmiş sl); yoksa (bu değişiklikten önceki eski kayıtlar) eski win/loss varsayımına
      // düşer. dist artık işaretli (dir bazlı) — hem tam TP kazancını hem trailing'le kilitlenen KISMİ
      // kazancı (stop kâr bölgesindeyken dokunulduğunda) doğru işaretle hesaplar.
      const hitPx = s.exitPrice!=null ? s.exitPrice : (s.outcome==='win'?s.tp:s.sl);
      const dist = s.dir*(hitPx-s.entry);
      return {sym:s.sym, usd:dist*cs2*lot, ts:s.ts, dir:s.dir, entry:s.entry, tp:s.tp, sl:s.sl, exitPrice:hitPx,
              resolved:true, outcome:s.outcome, stratKey:s.stratKey, stratLabel:s.stratLabel, context:s.context, outcomeContext:s.outcomeContext, slAdjusted:s.slAdjusted||false};
    }).sort((a,b)=>b.ts-a.ts);
  }
  let all=[];
  Object.keys(SYMS).forEach(sym=>{
    const store=loadEliteTradeStore(sym), cs=SYMS[sym].contractSize;
    (store.trades||[]).filter(tr=>tr.resolved).forEach(tr=>{
      const lot = tr.lot!=null ? tr.lot : fallbackLot;
      const hitPx = tr.exitPrice!=null ? tr.exitPrice : (tr.outcome==='win'?tr.tp:tr.sl);
      const dist = tr.dir*(hitPx-tr.entry);
      all.push(Object.assign({sym, usd:dist*cs*lot}, tr));
    });
  });
  all.sort((a,b)=>b.ts-a.ts);
  return all;
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
// ---- SONUÇ ANI context'i — kullanıcı isteği: "kaybetti şu şunu takip etti neden kaybetti diye
// hafızasında tutsun". describeTradeContext GİRİŞTEKİ gerekçeyi anlatıyordu ama SL/TP'ye ulaştığı
// ANDAKİ piyasa durumunu (trend hâlâ aynı yönde mi, ADX güçlü mü) kaydetmiyordu — bu, ikisini
// karşılaştırıp "giriş anında X'ti, kapanışta Y oldu" görmeyi sağlar. updateTradeOutcomes çağrılırken
// o tick'in zaten okuduğu cr.indicators'tan (yeni bir hesaplama gerektirmeden) üretilir.
function buildOutcomeContext(cr,price){
  const ind=(cr&&cr.indicators)||null; if(!ind) return null;
  let trendState=null;
  if(ind.ema50!=null && ind.ema200!=null) trendState = ind.ema50>ind.ema200?'trendUp':(ind.ema50<ind.ema200?'trendDown':'trendFlat');
  return {
    rsi: ind.rsi!=null?Math.round(ind.rsi):null,
    adx: ind.adx!=null?Math.round(ind.adx):null,
    trendState, price
  };
}
function describeOutcomeContext(ctx){
  if(!ctx) return '';
  const details=[];
  if(ctx.trendState) details.push(ctx.trendState==='trendUp'?t('outcomeTrendUp'):ctx.trendState==='trendDown'?t('outcomeTrendDown'):t('outcomeTrendFlat'));
  if(ctx.rsi!=null) details.push(t('outcomeRsi')(ctx.rsi));
  if(ctx.adx!=null) details.push(ctx.adx>=25?t('outcomeAdxStrong')(ctx.adx):t('outcomeAdxWeak')(ctx.adx));
  return details.length ? t('outcomePrefix')+' '+details.join(' · ') : '';
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
// ============ ARDIŞIK KAYIP DEVRE KESİCİ (sadece ana motor) ============
// Kullanıcı geri bildirimi (gerçek örnek, funded/prop-firm hesap): "art arda kaybettiğimiz 3 işlem
// olunca hesap patlıyor" + "ısrarla aynı yöne (örn. sell) devam ediyor, piyasa tamamen farklı olsa
// bile". Yukarıdaki whipsaw-cooldown SADECE ters yönü 20dk bekletiyor, aynı yönde devam bilinçli
// olarak serbestti — yani aynı yönde art arda kaybeden bir seri hiç yavaşlamıyordu. Bu, hesap-geneli
// (tüm semboller, riskState() ile aynı mantık) bir sayaç: 3. ardışık kayıpta TÜM yeni ana-motor
// sinyalleri (her iki yön) 15dk tamamen durur; süre dolunca "en mantıklı pozisyon" mantığıyla geri
// döner — az önce kaybettiren yön 15 puan güven cezası alır (daha fazla kanıt ister), ters yön hiç
// cezalanmaz (piyasa gerçekten döndüyse yakalasın). Elite Scalp'e KASITLI olarak dokunulmuyor —
// tamamen bağımsız panel tasarımı korunuyor.
function mainLossStreakKey(){ return 'valens_main_loss_streak'; }
function getMainLossStreak(){
  try{ const raw=localStorage.getItem(mainLossStreakKey());
    return raw?JSON.parse(raw):{count:0,dir:0,pausedUntil:0,recentLossCtx:[]}; }catch(e){ return {count:0,dir:0,pausedUntil:0,recentLossCtx:[]}; }
}
function recordMainTradeOutcome(dir,outcome,ctx){
  try{
    let st=getMainLossStreak();
    if(outcome==='loss'){
      if(st.dir===dir){ st.count=(st.count||0)+1; st.recentLossCtx=(st.recentLossCtx||[]).concat([ctx||null]).slice(-3); }
      else { st.dir=dir; st.count=1; st.recentLossCtx=[ctx||null]; }
      if(st.count>=3 && !(st.pausedUntil>Date.now())){ st.pausedUntil=Date.now()+15*60000; }
    } else {
      st.count=0; st.dir=0; st.recentLossCtx=[];
      // Aktif bir duraklama varsa (paused'ken açılmış eski bir işlem şimdi kazandıysa) süresini
      // erken bitirmiyoruz — 15dk disiplini kazançla iptal edilmez, sadece seri sıfırlanır.
    }
    localStorage.setItem(mainLossStreakKey(), JSON.stringify(st));
  }catch(e){}
}
// ---- KÂR KORUMA (kademeli, dönüş-sinyaline dayalı) ----
// Kullanıcı geri bildirimi (çizimli örnek): eski sürüm SADECE "%75'e ulaştı mı" diye sabit bir fiyat
// yüzdesine bakıyordu — yapıyı bozmayan normal bir geri çekilmeyle (üstteki grafik: temiz, kademeli
// yükseliş) GERÇEK bir dönüşü (alttaki grafik: kararsız, yön belirtmeyen testere) ayırt edemiyordu.
// Kullanıcının kendi tarifi: "işlem güvenilir ve TP ihtimali hâlâ yüksekse dokunma; güvenilir değil
// ama TP ihtimali de düşük değilse SL'yi biraz entry'ye yaklaştır (riski azalt) + bildir; net yönlü
// bir dönüş varsa stopu entry'nin birkaç puan üzerine çek (küçük garanti kâr kilitle)". Artık tetik
// fiyat yüzdesi değil, zaten her tick hesaplanan GERÇEK dönüş sinyalleri: yapısal kırılma
// (structureBias), tükeniş kümesi (exhaustionBias), ters yönlü mum formasyonu (pattern) — kaç
// tanesi işlemin YÖNÜNE karşıysa (Elite Scalp'teki "kaç kanıt var" mantığıyla aynı desen):
//   0 sinyal -> dokunma (Kademe 0)
//   1 sinyal -> SL'yi orijinal SL ile entry'nin tam ortasına çek, hâlâ zarar ama küçültülmüş (Kademe 1)
//   2+ sinyal -> stopu entry + risk_mesafesinin %15'i seviyesine çek, küçük garanti kâr (Kademe 2)
// Her iki kademe de KALICIDIR (bir kere yükseldi mi geri gevşetilmez) — Kademe 1'den Kademe 2'ye
// yükselebilir ama asla geri inmez. Kademe 2'ye ulaşana kadar stop hâlâ GERÇEK risk sınırıdır ve
// anında (mum içi) tetiklenir; sadece Kademe 2 (garanti kâr) mum-kapanış teyidi bekler (bkz. aşağıdaki
// getJustClosedCandlePrice bloğu, t.slAdjusted üzerinden). drawFn verilirse (chart motoruna köprü)
// aktif stop seviyesinde kırmızı bir çizgi çizdirir.
function detectReversalSignalCount(dir, cr){
  if(!cr) return 0;
  let n=0;
  if(cr.structureBias!=null && cr.structureBias!==0){
    if(dir>0 ? cr.structureBias<0 : cr.structureBias>0) n++;
  }
  if(cr.exhaustionBias!=null && cr.exhaustionBias!==0){
    if(dir>0 ? cr.exhaustionBias<0 : cr.exhaustionBias>0) n++;
  }
  if(cr.pattern!=null && cr.pattern===-dir) n++;
  return n;
}
// Dönüş değeri: bu ÇAĞRIDA bir kademe YENİ tetiklendiyse/yükseldiyse true (çağıran, localStorage'a
// KAYDETMESİ gerektiğini bilsin diye — DÜZELTME: ilk sürümde çağıran sadece işlem SONUÇLANDIĞINDA
// kaydediyordu, mutasyon resolve olmayan bir tick'te belleğe yazılıp hiç localStorage'a düşmüyordu,
// bir sonraki tick'te store yeniden YÜKLENİNCE değişiklik SIFIRLANIYORDU — stop asla gerçekten
// çekilmiyordu).
function applyTrailingStop(t, lastPrice, cr, drawFn){
  let justTriggered=false;
  if(t.originalSl==null) t.originalSl = t.sl;
  if((t.protectLevel||0) < 2){
   const distToTp = Math.abs(t.tp-t.entry);
   const riskDist = Math.abs(t.entry-t.originalSl);
   // Fiyat henüz anlamlı ilerlemediyse hiç değerlendirmeye almıyoruz — erken bir dönüş sinyali
   // gürültüden ayırt edilemez. DÜZELTME (30 Eylül 2026, gerçek eylül verisiyle doğrulandı): eşik
   // eskiden %50'ydi — eylülde kâra geçip sonra zarara dönen 32 işlemden sadece 9'u bu eşiğe
   // ulaşabiliyordu (%30'da 15'i, %20'de 17'si ulaşırdı). %50 çok yüksekti, çoğu gerçek geri-dönüş
   // hiç değerlendirmeye girmeden tam zararla kapanıyordu. %35'e çekildi — Kademe 1 (tek sinyal)
   // pozisyonu KAPATMIYOR, sadece riski azaltıyor; asıl kapanışa yol açabilen Kademe 2 hâlâ 2+
   // bağımsız dönüş sinyali istiyor, o yüzden daha erken değerlendirmeye girmenin gürültü riski
   // sınırlı. Sonraki birkaç haftalık canlı sonuçla (post-mortem "erken_kar_korunmadi" etiketinin
   // azalıp azalmadığıyla) doğrulanmalı, tek seferde "kesin doğru" varsayılmamalı.
   const progressedEnough = t.dir>0 ? lastPrice >= t.entry+0.35*distToTp : lastPrice <= t.entry-0.35*distToTp;
   if(progressedEnough){
    const signalCount = detectReversalSignalCount(t.dir, cr);
    if(signalCount>=2 && (t.protectLevel||0)<2){
     t.sl = t.entry + t.dir*0.15*riskDist;
     t.protectLevel = 2;
     t.slAdjusted = true; // mum-kapanış-teyitli çıkış mantığı bunu okuyor (bkz. aşağı)
     justTriggered = true;
    } else if(signalCount===1 && (t.protectLevel||0)<1){
     t.sl = (t.originalSl + t.entry)/2;
     t.protectLevel = 1;
     t.riskReduced = true;
     justTriggered = true;
    }
   }
  }
  // protectLevel>0 olduğu sürece HER tick'te tekrar çizdirilir (sadece tetiklendiği anda değil) —
  // sembol/zaman dilimi değişince chart motoru TÜM çizgileri temizliyor (bkz. valensSetSymbol/
  // valensSetInterval), bu olmadan kilitlenmiş stop çizgisi bir daha asla geri gelmezdi.
  if((t.protectLevel||0)>0 && drawFn) drawFn(t.sl, t.dir);
  return justTriggered;
}
// ---- KÂR KORUMA SONRASI ÇIKIŞ İÇİN MUM KAPANIŞ TEYİDİ ----
// Kullanıcı geri bildirimi (gerçek örnek): BUY iki kez kâr korumaya (trailing stop) takılıp kapandı,
// ama fiyat hemen ardından asıl TP seviyesine kadar gitti — yani trailing stop, gerçek bir dönüş
// olmadan, anlık bir geri çekilmeyle (fitille) tetiklenip erken kapatıyordu. ÖNEMLİ AYRIM: bu SADECE
// kâr koruma devredeyken (t.slAdjusted) geçerli — orijinal SL hâlâ ANINDA (mum içi/fitil) tetiklenir,
// çünkü o asıl risk sınırıdır ve gevşetilmesi hesabı büyük kayba açık bırakır (bkz. ardışık kayıp
// devre kesici — aynı hataya düşmemek için). Kâr koruma seviyesi ise HER ZAMAN kârda (entry'nin lehte
// tarafında, applyTrailingStop ile sabitlenmiş) olduğu için gevşetmenin risk maliyeti yok — en kötü
// ihtimalle aynı kârı biraz gecikmeli alırız, daha büyük ihtimalle fitili atlatıp asıl TP'ye ulaşırız.
function getJustClosedCandlePrice(sym, cr){
  const tracker = window.valensCandleCloseTracker || (window.valensCandleCloseTracker={});
  const prev = tracker[sym];
  if(prev && cr && cr.candleTime!=null && prev.candleTime!=null && prev.candleTime!==cr.candleTime) return prev.close;
  return null;
}
function recordCandleCloseTick(sym, cr, price){
  const tracker = window.valensCandleCloseTracker || (window.valensCandleCloseTracker={});
  tracker[sym] = {candleTime: (cr && cr.candleTime!=null) ? cr.candleTime : (tracker[sym]?tracker[sym].candleTime:null), close: price};
}
function updateTradeOutcomes(sym,lastPrice,cr,justClosedCandlePrice){
  const store=loadTradeStore(sym);
  let changed=false;
  (store.trades||[]).forEach(t=>{
    if(t.resolved)return;
    // ---- MFE/MAE TAKIBI (2 haftalik test icin "islem sonrasi analiz" altyapisi) — kullanici
    // istegi: "kar eden islemlerde karı nasıl maksimize edebilirdik, zarar edende zararı nasıl
    // engelleyebilirdik". Islem boyunca gorulen EN IYI (lehte) ve EN KOTU (aleyhte) mesafeyi
    // (isaretli, giristen) her tick'te guncelliyoruz - cozum aninda "zarardan once kar gormus
    // muydu" (erken kar koruma faydali olurdu) sorusuna cevap verir.
    if(t.mfe==null) t.mfe=0; if(t.mae==null) t.mae=0;
    const curDist = t.dir*(lastPrice-t.entry);
    if(curDist>t.mfe){ t.mfe=curDist; changed=true; }
    if(curDist<t.mae){ t.mae=curDist; changed=true; }
    if(applyTrailingStop(t, lastPrice, cr, window.valensDrawTrailedSL)){
      changed=true;
      if(t.protectLevel===1 && window.valensShowRiskReducedToast) window.valensShowRiskReducedToast(sym, t.dir);
      else if(t.protectLevel===2 && window.valensShowProfitLockArmedToast) window.valensShowProfitLockArmedToast(sym, t.dir);
    }
    let exitPrice=null, closedViaProfitLock=false;
    if(t.dir>0){
      if(lastPrice>=t.tp) exitPrice=t.tp;
      else if(!t.slAdjusted && lastPrice<=t.sl) exitPrice=t.sl;
      else if(t.slAdjusted && justClosedCandlePrice!=null && justClosedCandlePrice<=t.sl){ exitPrice=t.sl; closedViaProfitLock=true; }
    }else if(t.dir<0){
      if(lastPrice<=t.tp) exitPrice=t.tp;
      else if(!t.slAdjusted && lastPrice>=t.sl) exitPrice=t.sl;
      else if(t.slAdjusted && justClosedCandlePrice!=null && justClosedCandlePrice>=t.sl){ exitPrice=t.sl; closedViaProfitLock=true; }
    }
    if(exitPrice!=null){
      // outcome artık HANGİ seviyeye (tp/sl) dokunulduğuna değil, o seviyenin girişe göre KÂR/ZARAR
      // olmasına göre belirleniyor — kâr koruma devredeyken stop artık kâr bölgesinde olabilir, o
      // durumda stop'a dokunmak GERÇEKTE bir kazançtır (t.sl>=entry için BUY, t.sl<=entry için SELL).
      t.resolved=true;
      t.exitPrice=exitPrice;
      t.outcome = (t.dir*(exitPrice-t.entry) >= 0) ? 'win' : 'loss';
      t.outcomeContext=buildOutcomeContext(cr,lastPrice);
      changed=true;
      if(t.outcome==='loss') recordStopLoss(sym,t.dir);
      recordMainTradeOutcome(t.dir,t.outcome,t.context||null);
      addPostMortemWatch({sym, ts:t.ts, stratKey:t.stratKey||null, dir:t.dir, entry:t.entry, exit:exitPrice,
        outcome:t.outcome, mfe:t.mfe||0, mae:t.mae||0, resolvedCandleTime:cr.candleTime||null,
        followCandleTime:null, followPrice:null, followDone:false, insight:null});
      resolveSignalOnApi(t);
      if(window.valensClearTrailedSL) window.valensClearTrailedSL();
      if(closedViaProfitLock && window.valensShowProfitLockToast){
        const cs=SYMS[sym].contractSize, lot=(t.lot!=null?t.lot:avgLot());
        window.valensShowProfitLockToast(sym, t.dir, Math.round(t.dir*(exitPrice-t.entry)*cs*lot));
      }
    }
  });
  if(changed)saveTradeStore(sym,store);
}
// ============ İŞLEM SONRASI ANALİZ ("POST-MORTEM") — 2 HAFTALIK TEST İZLEME ============
// Kullanıcı isteği: "kâr eden işlemlerde nerede nasıl kâr etti, kârı nasıl maksimize edebilirdik;
// zarar eden işlemlerde nerede nasıl zarar etti, zararı nasıl engelleyebilirdik, onu takip edelim."
// Her çözülen işlem için: (1) işlem SÜRESİNCE görülen en iyi/en kötü mesafe (MFE/MAE, bkz.
// updateTradeOutcomes) zaten kaydedildi; (2) çıkıştan sonra fiyatın ne yaptığını görmek için
// N mum daha "izliyoruz" (POST_MORTEM_FOLLOW_CANDLES) — bu, "TP'den sonra fiyat daha da gitti mi"
// (kâr elde kalmış mı) sorusuna cevap verir. İkisi birleşince otomatik, okunabilir bir içgörü üretilir.
const POST_MORTEM_FOLLOW_CANDLES = 8; // ~2 saat (15dk mumlarda) - kısa ama anlamlı bir "ne oldu sonra" penceresi
const POST_MORTEM_STORE_PREFIX = 'valens_postmortem_';
function getPostMortemKey(sym){ return POST_MORTEM_STORE_PREFIX+sym.replace(/[:\/]/g,'_'); }
function loadPostMortemStore(sym){ try{ const raw=localStorage.getItem(getPostMortemKey(sym)); return raw?JSON.parse(raw):{entries:[]}; }catch(e){ return {entries:[]}; } }
function savePostMortemStore(sym,store){ try{ localStorage.setItem(getPostMortemKey(sym), JSON.stringify(store)); }catch(e){} }
function addPostMortemWatch(entry){
  const store=loadPostMortemStore(entry.sym);
  store.entries=store.entries||[];
  store.entries.push(entry);
  if(store.entries.length>400) store.entries=store.entries.slice(-400);
  savePostMortemStore(entry.sym, store);
}
// Her tick'te botTick'ten çağrılır — bekleyen (henüz izlemesi bitmemiş) kayıtları o anki mumla
// karşılaştırır, yeterli mum geçtiyse takip fiyatını sabitler ve içgörüyü üretir.
function updatePostMortemWatch(sym, cr, lastPrice){
  if(!cr || cr.candleTime==null) return;
  const store=loadPostMortemStore(sym);
  let changed=false;
  (store.entries||[]).forEach(e=>{
    if(e.followDone) return;
    if(e.followCandleTime==null){
      // sembolün mum aralığını (saniye) INT'ten kabaca çıkar - sadece "N mum sonra" icin yaklaşık yeter
      const intvSec = (INT==='60'?3600:INT==='240'?14400:INT==='D'?86400:(parseInt(INT,10)||15)*60);
      e.followCandleTime = e.resolvedCandleTime + POST_MORTEM_FOLLOW_CANDLES*intvSec;
      changed=true;
    }
    if(cr.candleTime>=e.followCandleTime){
      e.followPrice=lastPrice; e.followDone=true;
      e.insight=describePostMortem(e);
      changed=true;
    }
  });
  if(changed) savePostMortemStore(sym, store);
}
// Otomatik, okunabilir "nasıl daha iyi olabilirdi" cümlesi — hem kâr maksimizasyonu (kazananlar)
// hem zarar önleme (kaybedenler) için, tamamen bu işlemin GERÇEK MFE/MAE ve çıkış-sonrası
// davranışına dayanır (varsayım/şablon değil).
function describePostMortem(e){
  const dir=e.dir;
  const slDist=Math.abs(e.entry-e.exit)||0.0001;
  const postMove = e.followPrice!=null ? dir*(e.followPrice-e.exit) : null;
  if(e.outcome==='win'){
    if(postMove!=null && postMove>slDist*0.3){
      return {tag:'hedef_dar', tr:t('pmWinLeftOnTable')(postMove.toFixed(2))};
    }
    return {tag:'hedef_iyi', tr:t('pmWinGoodExit')};
  } else {
    if(e.mfe>slDist*0.3){
      return {tag:'erken_kar_korunmadi', tr:t('pmLossHadProfit')(e.mfe.toFixed(2))};
    }
    if(postMove!=null && postMove>slDist*0.3){
      return {tag:'stop_dar', tr:t('pmLossStopTooTight')(postMove.toFixed(2))};
    }
    return {tag:'giris_hatali', tr:t('pmLossNoProfitEver')};
  }
}
// 2 haftalık (ya da istenen herhangi bir) dönem için toplu özet — hangi örüntü ne kadar sık
// görüldü ("kayıpların X%'i erken kâr korumasıyla önlenebilirdi" gibi). Konsoldan ya da ileride
// bir panelden çağrılabilir: window.valensPostMortemReport()
window.valensPostMortemReport=function(sym, sinceMs){
  sym = sym || CUR;
  const since = sinceMs!=null ? sinceMs : (Date.now()-14*24*3600*1000); // varsayılan: son 14 gün
  const store = loadPostMortemStore(sym);
  const entries = (store.entries||[]).filter(e=>e.ts>=since && e.followDone);
  const tagCounts={};
  entries.forEach(e=>{ const tg=e.insight?e.insight.tag:'bekliyor'; tagCounts[tg]=(tagCounts[tg]||0)+1; });
  const wins=entries.filter(e=>e.outcome==='win').length, losses=entries.length-wins;
  console.log(`=== Post-Mortem Özeti (${sym}, son ${Math.round((Date.now()-since)/86400000)} gün) ===`);
  console.log(`Toplam analiz edilmiş işlem: ${entries.length} (${wins} kâr, ${losses} zarar)`);
  Object.entries(tagCounts).forEach(([tag,n])=>console.log(`  ${tag}: ${n} işlem (%${(n/entries.length*100).toFixed(0)})`));
  return {sym, total:entries.length, wins, losses, tagCounts, entries};
};
// DÜZELTME (kullanıcı geri bildirimi): merkezi API'ye YAZMA (pushSignalToApi/resolveSignalOnApi)
// zaten vardı ama görüntüleme panelleri hâlâ SADECE bu tarayıcının localStorage'ını okuyordu —
// bağlıyken bile başka bir cihazdan girilen/sonuçlanan işlemler görünmüyordu. Artık bağlıyken
// (window.valensSignalApiConnected) merkezi kaynak (window.valensCentralSignals, periyodik
// tazelenir — bkz. refreshCentralSignals) önceliklidir; bağlı değilken eski yerel davranış
// birebir korunuyor.
function getWinRate(sym){
  if(window.valensSignalApiConnected && window.valensCentralSignals){
    const resolved=window.valensCentralSignals.filter(s=>s.resolved && s.sym===sym);
    const wins=resolved.filter(s=>s.outcome==='win').length;
    return{wins,total:resolved.length,rate:resolved.length?(wins/resolved.length*100):null};
  }
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
// DÜZELTME (kullanıcı geri bildirimi: "hesaplar patlıyor" — kâr koruma/trailing stop eklenirken
// BURASI güncellenmeyi kaçırmıştı): eskiden kazanan işlemler HER ZAMAN tam TP mesafesiyle
// hesaplanıyordu — ama kâr koruma tetiklenip stop girişin üzerine çekildiğinde gerçek çıkış artık
// tp'den KÜÇÜK. Bu, günlük/toplam kârı OLDUĞUNDAN BÜYÜK gösteriyordu — risk bloğu (aşağıda
// riskState) da bu şişirilmiş kâra bakıp GEREĞİNDEN GEÇ devreye giriyordu. Artık getAllResolvedTrades
// ile AYNI mantık: gerçek exitPrice (varsa) kullanılıyor.
function computeTodayPnL(){
  const todayStr=new Date().toISOString().slice(0,10);
  const lot=avgLot();
  let pnl=0;
  Object.keys(SYMS).forEach(sym=>{
    const store=loadTradeStore(sym), cs=SYMS[sym].contractSize;
    (store.trades||[]).forEach(tr=>{
      if(!tr.resolved) return;
      if(new Date(tr.ts).toISOString().slice(0,10)!==todayStr) return;
      const hitPx = tr.exitPrice!=null ? tr.exitPrice : (tr.outcome==='win'?tr.tp:tr.sl);
      const dist = tr.dir*(hitPx-tr.entry);
      pnl += dist*cs*(tr.lot!=null?tr.lot:lot);
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
      const hitPx = tr.exitPrice!=null ? tr.exitPrice : (tr.outcome==='win'?tr.tp:tr.sl);
      const dist = tr.dir*(hitPx-tr.entry);
      pnl += dist*cs*(tr.lot!=null?tr.lot:lot);
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

// ============ ⚡ VALENS ELİT SCALP — PERFORMANS PANELİ ============
// Kullanıcı düzeltmesi: "terminal gene çalışmaya devam etsin, biz stratejimizi ayrı bir şekilde
// soldaki bölgede test edicez... sadece ai signal engine yazan yerde değil soldaki kendi bölmesinde
// çalışacak" — bu strateji artık ana motorun candidates/best havuzuna karışmıyor (bkz. botTick,
// eliteScalpTag), TAMAMEN AYRI bir karar+takip süreci (bkz. logEliteScalpTrade/
// updateEliteScalpTradeOutcomes/getEliteScalpResolvedTrades). Aşağıdaki panel SADECE bu ayrı
// sürecin sonuçlarını gösterir — hem girişteki (describeTradeContext) hem sonuçtaki
// (describeOutcomeContext) gerçek gerekçesiyle. botTick her tick'te window.valensEliteScalpLive'ı
// (o an üç şart kesişiyor mu, hangi yönde) günceller, burada okunup "kaybolmadan" gösterilir.
function updateEliteScalpLiveStatus(live){
  const el=document.getElementById('eliteScalpLive'); if(!el) return;
  if(!live){ el.innerHTML='○ '+t('eliteScalpLiveIdle'); el.style.color='var(--muted)'; return; }
  const dirLabel = live.dir>0 ? 'BUY' : 'SELL';
  el.innerHTML = '● '+t('eliteScalpLiveActive')(dirLabel);
  el.style.color = live.dir>0 ? 'var(--green)' : 'var(--red)';
}
// Kullanıcı isteği: "solda elit strateji en son hangi noktada hangi tp/sl/entry değerleriyle
// ateşlenmiş, o çizgi olan yerde yazsın" — updateEliteScalpLiveStatus artık çağrılmıyordu (Elit
// Scalp'in eski karar mantığı devre dışı bırakılınca boşta kalmıştı), bu yüzden #eliteScalpLive
// hep boş "—" görünüyordu. Artık 3'lü kombinasyonun (SR/EMA-MACD/ORB, hangisi olursa) en son
// ateşlenen işlemini (açık ya da sonuçlanmış fark etmez) gerçek giriş/stop/tp değerleriyle gösterir.
function updateComboLastSignalUI(sym){
  const el=document.getElementById('eliteScalpLive'); if(!el) return;
  const store=loadCombo3Store(sym);
  const trades=(store.trades||[]).slice().sort((a,b)=>b.ts-a.ts);
  if(!trades.length){ el.innerHTML='○ '+t('eliteScalpLiveIdle'); el.style.color='var(--muted)'; return; }
  const tr=trades[0];
  const cfg=SYMS[sym]; if(!cfg) return;
  const fmt=v=>v.toLocaleString('en-US',{minimumFractionDigits:cfg.dec,maximumFractionDigits:cfg.dec});
  const dirLabel = tr.dir>0?'BUY':'SELL';
  const dot = !tr.resolved ? '●' : (tr.outcome==='win'?'✅':'❌');
  el.innerHTML = dot+' '+dirLabel+' · '+(tr.stratLabel||tr.stratKey||'')+' · '+t('entry_lbl')+' '+fmt(tr.entry)+' → SL '+fmt(tr.sl)+' / TP '+fmt(tr.tp)+' · '+fmtSigTime(tr.ts);
  el.style.color = !tr.resolved ? 'var(--gold)' : (tr.outcome==='win'?'var(--green)':'var(--red)');
}
// ============ ⚡ 3'LÜ ÇEŞİTLENDİRİLMİŞ PORTFÖY — ELİT SCALP YERİNE ============
// Kullanıcı isteği: "3 lü kombinasyonun aylık kar omiktarını ver ve appye elit strateji yerine onu
// ekle" — bu oturumda 17 yıllık GERÇEK XAUUSD verisiyle (HistData.com, 1dk→1H agregasyon) ayrı ayrı
// keşfedilip (2009-2018 discovery) SONRA hiç dokunulmamış 2019-2026 verisinde TEK SEFERLİK doğrulanan
// 3 bağımsız strateji: (1) Destek/Direnç Test-veya-Kırılım (güçlü seviyeler, ≥4 kez test edilmiş),
// (2) EMA9/21 + MACD kesişimi (kullanıcının kendi verdiği örnek), (3) ORB (açılış aralığı kırılımı,
// 4H trend filtresiyle). AYRI AYRI test edilip TEK TEK OOS'ta hayatta kaldılar, SONRA birlikte
// çalıştırılınca (çeşitlendirme) $100.000/%25 max drawdown sınırında %5.76/ay ortalama getiri verdiler
// — herhangi biri tek başına bunun çok altında. Devre kesici (mainLossStreak mantığı) SADECE
// SR bacağında yardımcı çıktı; EMA/MACD ve ORB TREND-DEVAM stratejileri olduğundan "aynı yönde ısrar"
// bloklaması onlarda asıl kazandıran devam hareketlerini kesiyordu (ORB'da kârı %66 düşürüyordu,
// ölçülerek bulundu) — bu yüzden ikisinde CB YOK, sadece SR'de VAR.
// ÖNEMLİ: canlı terminal 15dk mumla çalışıyor (INT='15') ama TÜM bu strateji 1 SAATLİK (H1) barlar
// üzerinde test edildi — bu yüzden kendi bağımsız H1/4H verisini (Binance REST, fetchScalpBias ile
// AYNI desende, window.valensCombo3H1/window.valensCombo3H4Trend üzerinden — bkz. fetchCombo3Data,
// farklı bir <script> bloğunda) kullanır, ana motorun 15dk mumlarına HİÇ karışmaz. Elit Scalp'in eski
// karar mantığı (eliteWinDir/detectStrategyTags içinde) koda DOKUNULMADI ama artık TETİKLENMİYOR —
// aşağıdaki botTick bloğunda logEliteScalpTrade çağrısı bu motorla DEĞİŞTİRİLDİ.
// Lot büyüklükleri kasıtlı olarak KÜÇÜK başlıyor (kalibre edilen $100k/%25DD oranı SR:EMA/MACD:ORB ≈
// 0.95:0.95:0.53 idi, burada ~19 kat küçültülmüş) — kullanıcının kendi kuralı: "test etmeden agresif
// değişiklik yapma" — gerçek $ sonuçları birikince (diğer stratejilerde yapıldığı gibi) büyütülebilir.
const COMBO3_LEGS = {
  sr:      {key:'valensComboSR',      label:'⚡ Kombine: Destek/Direnç Test-Kırılım', lot:0.05},
  emamacd: {key:'valensComboEmaMacd', label:'⚡ Kombine: EMA9/21+MACD Kesişimi',       lot:0.05},
  orb:     {key:'valensComboOrb',     label:'⚡ Kombine: Açılış Aralığı Kırılımı',     lot:0.03}
};
const COMBO3_STORE_PREFIX='valens_combo3_trades_';
function getCombo3Key(sym){return COMBO3_STORE_PREFIX+sym.replace(/[:\/]/g,'_');}
function loadCombo3Store(sym){try{const raw=localStorage.getItem(getCombo3Key(sym));if(!raw)return{trades:[]};return JSON.parse(raw);}catch(e){return{trades:[]};}}
function saveCombo3Store(sym,store){try{localStorage.setItem(getCombo3Key(sym),JSON.stringify(store));}catch(e){}}

function combo3CalcATR(bars,period){
  const n=bars.length; if(n<2) return null;
  const tr=[bars[0].high-bars[0].low];
  for(let i=1;i<n;i++){
    const c=bars[i], p=bars[i-1];
    tr.push(Math.max(c.high-c.low, Math.abs(c.high-p.close), Math.abs(c.low-p.close)));
  }
  const win=tr.slice(Math.max(0,n-period));
  return win.reduce((a,b)=>a+b,0)/win.length;
}
// Swing pivot + "güç" (kaç farklı pivot aynı bantta ~%0.15 yakınlıkta) — backtest'teki build_levels'in
// birebir JS karşılığı (PIVN=5, TOL=0.0015).
function combo3BuildLevels(bars){
  const PIVN=5, TOL=0.0015, n=bars.length;
  let pivHi=[], pivLo=[];
  for(let i=PIVN;i<n-PIVN;i++){
    let isHi=true, isLo=true;
    for(let j=i-PIVN;j<=i+PIVN;j++){
      if(j===i) continue;
      if(bars[j].high>bars[i].high) isHi=false;
      if(bars[j].low<bars[i].low) isLo=false;
    }
    if(isHi) pivHi.push({idx:i, price:bars[i].high});
    if(isLo) pivLo.push({idx:i, price:bars[i].low});
  }
  function withStrength(pivs){
    return pivs.map((p,k)=>{
      let s=1;
      for(let m=0;m<k;m++){ if(Math.abs(pivs[m].price-p.price)/p.price<TOL) s++; }
      return {idx:p.idx, price:p.price, strength:s};
    });
  }
  return {hi:withStrength(pivHi), lo:withStrength(pivLo), PIVN};
}
// Destek/Direnç Test-veya-Kırılım — sadece SON KAPANMIŞ H1 barında sinyal arar (backtest'in
// run_sr'sindeki tek-bar mantığının aynısı, min_strength=4, r=3.0, sl=1.5×ATR).
function combo3DetectSR(bars, levels, minStrength, rMult, slMult){
  const n=bars.length; if(n<70) return null;
  const i=n-1, prev=bars[i-1], curr=bars[i], TOL=0.0015;
  const atr=combo3CalcATR(bars,14); if(!atr) return null;
  const availHi=levels.hi.filter(l=>l.idx+levels.PIVN<=i-1 && l.strength>=minStrength && l.price>curr.close);
  const availLo=levels.lo.filter(l=>l.idx+levels.PIVN<=i-1 && l.strength>=minStrength && l.price<curr.close);
  if(!availHi.length || !availLo.length) return null;
  const resLevel=availHi.reduce((a,b)=>b.price<a.price?b:a).price;
  const supLevel=availLo.reduce((a,b)=>b.price>a.price?b:a).price;
  let sig=null;
  if(Math.abs(curr.high-resLevel)/resLevel<TOL || (curr.high>=resLevel && curr.close<resLevel)){
    if(curr.close<resLevel && curr.close<curr.open) sig=-1;
  }
  if(sig==null && prev.close<resLevel && curr.close>resLevel && curr.close>curr.open) sig=1;
  if(sig==null && (Math.abs(curr.low-supLevel)/supLevel<TOL || (curr.low<=supLevel && curr.close>supLevel))){
    if(curr.close>supLevel && curr.close>curr.open) sig=1;
  }
  if(sig==null && prev.close>supLevel && curr.close<supLevel && curr.close<curr.open) sig=-1;
  if(sig==null) return null;
  const slDist=atr*slMult;
  return {dir:sig, entry:curr.close, sl:curr.close-sig*slDist, tp:curr.close+sig*slDist*rMult, barTime:curr.time};
}
// EMA9/21 + MACD(12,26,9) kesişimi — kullanıcının kendi verdiği örnek strateji. confirm=2 mum,
// RSI filtresi yok, r=3.5, sl=2.0×ATR (mega taramada 2820 kombinasyonun OOS'ta en iyi hayatta kalanı).
function combo3DetectEmaMacd(bars, confirmBars, rMult, slMult){
  const n=bars.length; if(n<40) return null;
  const closes=bars.map(b=>b.close);
  function ema(period){
    const k=2/(period+1); let e=closes[0]; const out=[e];
    for(let i=1;i<closes.length;i++){ e=closes[i]*k+e*(1-k); out.push(e); }
    return out;
  }
  const ema9=ema(9), ema21=ema(21), ema12=ema(12), ema26=ema(26);
  const macdLine=ema12.map((v,i)=>v-ema26[i]);
  const k9=2/10; let s0=macdLine[0]; const macdSignal=[s0];
  for(let i=1;i<macdLine.length;i++){ s0=macdLine[i]*k9+s0*(1-k9); macdSignal.push(s0); }
  const macdHist=macdLine.map((v,i)=>v-macdSignal[i]);
  const atr=combo3CalcATR(bars,14); if(!atr) return null;
  const i=n-1;
  let lastCrossDir=0, crossBar=-1;
  for(let j=Math.max(1,i-confirmBars-1); j<=i; j++){
    if(ema9[j-1]<=ema21[j-1] && ema9[j]>ema21[j]){ lastCrossDir=1; crossBar=j; }
    if(ema9[j-1]>=ema21[j-1] && ema9[j]<ema21[j]){ lastCrossDir=-1; crossBar=j; }
  }
  if(crossBar<0 || (i-crossBar)>confirmBars) return null;
  let sig=null;
  if(lastCrossDir===1 && ema9[i]>ema21[i] && macdHist[i]>0) sig=1;
  else if(lastCrossDir===-1 && ema9[i]<ema21[i] && macdHist[i]<0) sig=-1;
  if(sig==null) return null;
  const curr=bars[i], slDist=atr*slMult;
  return {dir:sig, entry:curr.close, sl:curr.close-sig*slDist, tp:curr.close+sig*slDist*rMult, barTime:curr.time};
}
// ORB (açılış aralığı kırılımı) — 2 saatlik aralık (00:00-02:00 UTC), 4H EMA50 trend filtresi ile
// aynı yönde olmayan kırılımlar elenir (mega taramada mtf=true ile OOS'ta discovery'den bile iyi çıktı).
function combo3DetectOrb(bars, trend4h, rangeHours, sessionStart, rMult, slMult){
  const n=bars.length; if(n<30) return null;
  const i=n-1, curr=bars[i], prev=bars[i-1];
  const d=new Date(curr.time*1000), hr=d.getUTCHours();
  if(hr<sessionStart+rangeHours) return null;
  const dayStr=d.toISOString().slice(0,10);
  let rhi=-Infinity, rlo=Infinity;
  for(let j=i;j>=0;j--){
    const bd=new Date(bars[j].time*1000);
    if(bd.toISOString().slice(0,10)!==dayStr) break;
    const bh=bd.getUTCHours();
    if(bh>=sessionStart && bh<sessionStart+rangeHours){ rhi=Math.max(rhi,bars[j].high); rlo=Math.min(rlo,bars[j].low); }
  }
  if(!isFinite(rhi) || !isFinite(rlo)) return null;
  let sig=null;
  if(curr.close>rhi && curr.close>curr.open && prev.close<=rhi) sig=1;
  else if(curr.close<rlo && curr.close<curr.open && prev.close>=rlo) sig=-1;
  if(sig==null) return null;
  if(trend4h!=null && trend4h!==0 && sig!==trend4h) return null;
  const atr=combo3CalcATR(bars,14); if(!atr) return null;
  const slDist=atr*slMult;
  return {dir:sig, entry:curr.close, sl:curr.close-sig*slDist, tp:curr.close+sig*slDist*rMult, barTime:curr.time};
}
// Her tick'te çağrılır (botTick içinden) — window.valensCombo3H1/H4Trend farklı bir <script> blogunda
// (fetchCombo3Data) dolduruluyor, burada sadece OKUNUYOR (window.* her bloktan görünür, fonksiyon
// içine gömülü olmayan düz bir atama olduğu sürece köprüleme sorunu yok — bu oturumda defalarca
// doğrulandı, bkz. fetchScalpBias/window.valensScalpBias aynı deseni).
function updateCombo3(sym){
  const data=window.valensCombo3H1;
  if(!data || data.sym!==sym || !data.bars || data.bars.length<80) return;
  const bars=data.bars;
  const trend4h=(window.valensCombo3H4Trend && window.valensCombo3H4Trend.sym===sym) ? window.valensCombo3H4Trend.trend : null;
  const store=loadCombo3Store(sym); store.trades=store.trades||[];
  const lastBar=bars[bars.length-1];
  let changed=false;
  store.trades.forEach(tr=>{
    if(tr.resolved) return;
    let exitPrice=null;
    if(tr.dir>0){ if(lastBar.high>=tr.tp) exitPrice=tr.tp; else if(lastBar.low<=tr.sl) exitPrice=tr.sl; }
    else { if(lastBar.low<=tr.tp) exitPrice=tr.tp; else if(lastBar.high>=tr.sl) exitPrice=tr.sl; }
    if(exitPrice!=null){
      tr.resolved=true; tr.exitPrice=exitPrice;
      tr.outcome=(tr.dir*(exitPrice-tr.entry)>=0)?'win':'loss';
      changed=true;
      resolveSignalOnApi(tr);
    }
  });
  function hasOpen(stratKey){ return store.trades.some(t=>!t.resolved && t.stratKey===stratKey); }
  function barUsed(stratKey,barTime){ return store.trades.some(t=>t.stratKey===stratKey && t.barTime===barTime); }
  function tryOpen(legDef, sigResult){
    if(!sigResult) return;
    if(hasOpen(legDef.key) || barUsed(legDef.key, sigResult.barTime)) return;
    if(openPositionCountForSymbol(sym)>=3) return; // hesap-geneli pozisyon disiplini (bu oturumun kuralı) korunuyor
    const trade={ts:Date.now(), dir:sigResult.dir, entry:sigResult.entry, tp:sigResult.tp, sl:sigResult.sl,
      resolved:false, outcome:null, stratKey:legDef.key, stratLabel:legDef.label, barTime:sigResult.barTime, lot:legDef.lot};
    store.trades.push(trade); changed=true;
    pushSignalToApi(sym, trade.ts, {sym, dir:trade.dir, entry:trade.entry, tp:trade.tp, sl:trade.sl, stratKey:legDef.key, stratLabel:legDef.label, ts:trade.ts, lot:trade.lot}, true);
  }
  const levels=combo3BuildLevels(bars);
  tryOpen(COMBO3_LEGS.sr,      combo3DetectSR(bars, levels, 4, 3.0, 1.5));
  tryOpen(COMBO3_LEGS.emamacd, combo3DetectEmaMacd(bars, 2, 3.5, 2.0));
  tryOpen(COMBO3_LEGS.orb,     combo3DetectOrb(bars, trend4h, 2, 0, 4.0, 1.5));
  if(store.trades.length>500) store.trades=store.trades.slice(-500);
  if(changed) saveCombo3Store(sym, store);
}
// getEliteScalpResolvedTrades ile AYNI desen ama combo3 mağazasından — eski Elit Scalp panelinin
// AYNI DOM elemanlarını (eliteScalpList/Summary/Badge) artık bu üçlünün gerçek sonuçlarıyla dolduruyoruz.
function getCombo3ResolvedTrades(){
  const fallbackLot=avgLot();
  let all=[];
  Object.keys(SYMS).forEach(sym=>{
    const store=loadCombo3Store(sym), cs=SYMS[sym].contractSize;
    (store.trades||[]).filter(tr=>tr.resolved).forEach(tr=>{
      const lot=tr.lot!=null?tr.lot:fallbackLot;
      const hitPx=tr.exitPrice!=null?tr.exitPrice:(tr.outcome==='win'?tr.tp:tr.sl);
      const dist=tr.dir*(hitPx-tr.entry);
      all.push(Object.assign({sym, usd:dist*cs*lot}, tr));
    });
  });
  all.sort((a,b)=>b.ts-a.ts);
  return all;
}
function updateEliteScalpPanel(){
  const list=document.getElementById('eliteScalpList'), summary=document.getElementById('eliteScalpSummary'), badge=document.getElementById('eliteScalpBadge');
  if(!list||!summary||!badge) return;
  const es=getCombo3ResolvedTrades();
  const wins=es.filter(tr=>tr.outcome==='win').length, losses=es.length-wins;
  const netUsd=es.reduce((a,tr)=>a+tr.usd,0);
  badge.textContent=t('eliteScalpBadge')(es.length);
  summary.innerHTML=t('eliteScalpSummaryLine')(es.length,wins,losses,(netUsd>=0?'+':'')+'$'+Math.round(netUsd).toLocaleString('en-US'));
  if(!es.length){ list.innerHTML='<p style="color:var(--muted);font-size:9px;padding:6px 2px">'+t('eliteScalpEmpty')+'</p>'; return; }
  list.innerHTML = es.map(tr=>{
    const cfg=SYMS[tr.sym]; if(!cfg) return '';
    const fmt=v=>v.toLocaleString('en-US',{minimumFractionDigits:cfg.dec,maximumFractionDigits:cfg.dec});
    const win = tr.outcome==='win', col=win?'var(--green)':'var(--red)';
    const hitPx = tr.exitPrice!=null ? tr.exitPrice : (win?tr.tp:tr.sl);
    const ctxLine = tr.context ? describeTradeContext(tr.context) : '';
    const outcomeLine = tr.outcomeContext ? describeOutcomeContext(tr.outcomeContext) : '';
    const trailLine = tr.slAdjusted ? t('trailLockNote') : '';
    return '<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 2px;border-bottom:1px solid var(--line);font-size:9px">'+
      '<div><b style="color:'+col+'">'+(win?t('tradeLogWin'):t('tradeLogLoss'))+' '+(tr.dir>0?'BUY':'SELL')+'</b> '+cfg.label+
      '<br><span style="color:var(--muted)">'+fmt(tr.entry)+' → '+fmt(hitPx)+' · '+fmtSigTime(tr.ts)+'</span>'+
      (ctxLine?'<br><span style="color:var(--muted);font-size:8px">'+ctxLine+'</span>':'')+
      (outcomeLine?'<br><span style="color:var(--muted);font-size:8px">'+outcomeLine+'</span>':'')+
      (trailLine?'<br><span style="color:var(--gold);font-size:8px">'+trailLine+'</span>':'')+'</div>'+
      '<div style="color:'+col+';font-weight:700;white-space:nowrap">'+(tr.usd>=0?'+$':'-$')+Math.round(Math.abs(tr.usd)).toLocaleString('en-US')+'</div>'+
      '</div>';
  }).join('');
}

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
          refreshCentralSignals();
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
// useEliteStore: DÜZELTME — logEliteScalpTrade da bunu çağırıyor ama işlemi AYRI bir mağazada
// (loadEliteTradeStore) tutuyor; bu bayrak olmadan remoteId hep ANA mağazaya yazılmaya çalışılıyordu
// (işlem orada bulunamadığı için sessizce hiçbir şey olmuyordu) — Elit Scalp işlemleri hiçbir zaman
// remoteId almıyor, dolayısıyla resolveSignalOnApi (remoteId şartı yüzünden) hiç çalışmıyordu.
function pushSignalToApi(sym, ts, payload, useEliteStore){
  if(!window.valensSignalApiConnected || !window.valensSignalApiToken) return;
  const url=signalApiUrl(); if(!url) return;
  const load = useEliteStore ? loadEliteTradeStore : loadTradeStore;
  const save = useEliteStore ? saveEliteTradeStore : saveTradeStore;
  fetch(url+'/signal', {method:'POST', headers:signalApiHeaders(), body:JSON.stringify(payload)})
    .then(r=>r.json()).then(res=>{
      if(res.ok && res.id){
        const store=load(sym);
        const trade=(store.trades||[]).find(tr=>tr.ts===ts);
        if(trade){ trade.remoteId=res.id; save(sym,store); }
      }
    }).catch(()=>{});
}
function resolveSignalOnApi(trade){
  if(!window.valensSignalApiConnected || !window.valensSignalApiToken || !trade.remoteId) return;
  const url=signalApiUrl(); if(!url) return;
  fetch(url+'/signal/'+trade.remoteId+'/resolve', {method:'POST', headers:signalApiHeaders(), body:JSON.stringify({outcome:trade.outcome, outcomeContext:trade.outcomeContext||null, exitPrice:trade.exitPrice!=null?trade.exitPrice:null, sl:trade.sl, slAdjusted:!!trade.slAdjusted})})
    .then(()=>{ refreshSignalApiStats(); refreshCentralSignals(); }).catch(()=>{});
}
// Merkezi API'den TÜM cihazların işlem geçmişini çeker — bağlıyken getWinRate/getAllResolvedTrades
// bu listeyi kullanır (her kaydın context'i dahil, hangi cihazdan girilirse girilsin aynı geçmiş).
function refreshCentralSignals(){
  if(!window.valensSignalApiConnected || !window.valensSignalApiToken){ window.valensCentralSignals=null; return; }
  const url=signalApiUrl(); if(!url) return;
  fetch(url+'/signals?limit=2000', {headers:signalApiHeaders()}).then(r=>r.json()).then(res=>{
    if(res.ok && Array.isArray(res.signals)){
      window.valensCentralSignals=res.signals;
      updateTradeLogUI(); updateWinRateUI();
    }
  }).catch(()=>{});
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
setInterval(()=>{ if(window.valensSignalApiConnected){ refreshSignalApiStats(); refreshCentralSignals(); } }, 5*60*1000); // 5dk'da bir tazele
// ---- Ortak gönderme fonksiyonu — hem manuel "Gönder" butonu hem de otomatik (demo/veri toplama)
// modu AYNI yolu kullanır, davranış hiçbir zaman ikisi arasında farklılaşmaz. ----
// ---- MUM BAŞINA MAKS 2 GÖNDERİM — kullanıcı geri bildirimi (gerçek örnek): aynı mum içinde
// birkaç saniye arayla farklı fiyat noktalarından (4341, 4342, 4343...) tekrar tekrar SELL
// gönderiliyordu. sigId kazanan stratejiye göre de değiştiğinden (best.key), tek başına yeterli bir
// dedup değildi — strateji bir tick'te değişse bile "aynı mum, aynı yön" hâlâ pratikte aynı fikirdir.
// Burada MUM ZAMANI + YÖNE göre ayrı, daha sıkı bir sayaç tutuluyor: bir yönde bir mumda en fazla 2
// gönderim, 3.'sü o mum kapanıp yeni mum başlayana kadar engellenir.
// ---- 15 DAKİKALIK MUMDA ZAMANLI 2. SLOT (kullanıcı isteği) — "mum başına en fazla 2" kuralı
// zaten vardı ama ikisi de mumun HERHANGİ bir anında art arda ateşlenebiliyordu. 15dk'lık mum
// için artık NET bir zamanlama var: 1. gönderim mum AÇILIŞINDA (mumun ilk sinyali ne zaman
// gelirse), 2. gönderim ise mum başladıktan EN AZ 4 DAKİKA SONRA — aradaki 0-4dk'lık pencerede
// ikinci bir gönderime izin verilmiyor (diğer zaman dilimlerinde eski davranış — sadece "maks 2" — korunuyor).
function candleSendLimitReached(sig){
  const tr = window.valensCandleSendTracker;
  if(!tr || !sig || tr.candleTime!==sig.candleTime || tr.dir!==sig.dir) return false;
  if(tr.count>=2) return true;
  if(tr.count>=1 && typeof INT!=='undefined' && INT==='15'){
   const elapsedMin=(Date.now()/1000 - sig.candleTime)/60;
   if(elapsedMin<4) return true; // 2. slot için 4dk henüz dolmadı
  }
  return false;
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
  const fallbackLot=avgLot();
  // Bağlıyken merkezi kaynak kullanılır — bu, HANGİ CİHAZDAN girilirse girilsin aynı sonuçlanmış
  // işlem listesini (ve her birinin context'inde saklı "neden girildi" gerekçesini) verir.
  if(window.valensSignalApiConnected && window.valensCentralSignals){
    return window.valensCentralSignals.filter(s=>s.resolved).map(s=>{
      const cs2=(SYMS[s.sym]||{}).contractSize||100;
      // DÜZELTME (kullanıcı geri bildirimi: "eski dönemde lot büyüktü, bu terminali yanıltıyor mu")
      // — s.lot, işlem AÇILDIĞI ANDAKİ dondurulmuş lot (bkz. logArmedTrade); yoksa (bu değişiklikten
      // önceki eski kayıtlar) güncel avgLot()'a düşer.
      const lot = s.lot!=null ? s.lot : fallbackLot;
      // exitPrice: DÜZELTME (kâr koruma/trailing stop) — GERÇEKTE dokunulan seviye (tp VEYA kâr
      // bölgesine çekilmiş sl); yoksa (bu değişiklikten önceki eski kayıtlar) eski win/loss varsayımına
      // düşer. dist artık işaretli (dir bazlı) — hem tam TP kazancını hem trailing'le kilitlenen KISMİ
      // kazancı (stop kâr bölgesindeyken dokunulduğunda) doğru işaretle hesaplar.
      const hitPx = s.exitPrice!=null ? s.exitPrice : (s.outcome==='win'?s.tp:s.sl);
      const dist = s.dir*(hitPx-s.entry);
      return {sym:s.sym, usd:dist*cs2*lot, ts:s.ts, dir:s.dir, entry:s.entry, tp:s.tp, sl:s.sl, exitPrice:hitPx,
              resolved:true, outcome:s.outcome, stratKey:s.stratKey, stratLabel:s.stratLabel, context:s.context, outcomeContext:s.outcomeContext, slAdjusted:s.slAdjusted||false};
    }).sort((a,b)=>b.ts-a.ts);
  }
  let all=[];
  Object.keys(SYMS).forEach(sym=>{
    const store=loadTradeStore(sym), cs=SYMS[sym].contractSize;
    (store.trades||[]).filter(tr=>tr.resolved).forEach(tr=>{
      const lot = tr.lot!=null ? tr.lot : fallbackLot;
      const hitPx = tr.exitPrice!=null ? tr.exitPrice : (tr.outcome==='win'?tr.tp:tr.sl);
      const dist = tr.dir*(hitPx-tr.entry);
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
  // DÜZELTME (kullanıcı geri bildirimi: "171 işlemin tamamını göremiyorum") — eskiden sadece son 40
  // işlem gösterilip gerisi "+131…" notuna gizleniyordu. Kutu zaten kaydırılabilir (max-height+overflow),
  // artık TÜMÜ render ediliyor — hiçbir gerçek işlem gizli kalmıyor.
  // Post-mortem içgörüsü, işlem geçmişinden AYRI bir mağazada (loadPostMortemStore) tutuluyor —
  // eşleştirme sym+ts (her işlem için tekil) ile yapılır. Henüz izleme bitmemişse (POST_MORTEM_
  // FOLLOW_CANDLES kadar mum geçmemişse) satır gösterilmez, sessizce bekler.
  const pmBySymTs={};
  Object.keys(SYMS).forEach(s=>{ (loadPostMortemStore(s).entries||[]).forEach(e=>{ if(e.followDone) pmBySymTs[s+'|'+e.ts]=e; }); });
  list.innerHTML = trades.map(tr=>{
    const cfg=SYMS[tr.sym]; if(!cfg) return '';
    const fmt=v=>v.toLocaleString('en-US',{minimumFractionDigits:cfg.dec,maximumFractionDigits:cfg.dec});
    const win = tr.outcome==='win', col=win?'var(--green)':'var(--red)';
    const hitPx = tr.exitPrice!=null ? tr.exitPrice : (win?tr.tp:tr.sl);
    const ctxLine = tr.context ? describeTradeContext(tr.context) : '';
    const outcomeLine = tr.outcomeContext ? describeOutcomeContext(tr.outcomeContext) : '';
    const trailLine = tr.slAdjusted ? t('trailLockNote') : '';
    const pmEntry = pmBySymTs[tr.sym+'|'+tr.ts];
    const pmLine = pmEntry && pmEntry.insight ? pmEntry.insight.tr : '';
    return '<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 2px;border-bottom:1px solid var(--line);font-size:9px">'+
      '<div><b style="color:'+col+'">'+(win?t('tradeLogWin'):t('tradeLogLoss'))+' '+(tr.dir>0?'BUY':'SELL')+'</b> '+cfg.label+(tr.stratLabel?' <span style="color:var(--muted)">· '+tr.stratLabel+'</span>':'')+
      '<br><span style="color:var(--muted)">'+fmt(tr.entry)+' → '+fmt(hitPx)+' · '+fmtSigTime(tr.ts)+'</span>'+
      (ctxLine?'<br><span style="color:var(--muted);font-size:8px">'+ctxLine+'</span>':'')+
      (outcomeLine?'<br><span style="color:var(--muted);font-size:8px">'+outcomeLine+'</span>':'')+
      (trailLine?'<br><span style="color:var(--gold);font-size:8px">'+trailLine+'</span>':'')+
      (pmLine?'<br><span style="color:var(--blue);font-size:8px">'+pmLine+'</span>':'')+'</div>'+
      '<div style="color:'+col+';font-weight:700;white-space:nowrap">'+(tr.usd>=0?'+$':'-$')+Math.round(Math.abs(tr.usd)).toLocaleString('en-US')+'</div>'+
      '</div>';
  }).join('');
  renderStrategyLivePanel(trades);
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
 const justClosedCandlePrice = getJustClosedCandlePrice(CUR, cr);
 recordCandleCloseTick(CUR, cr, adjLast);
 updateTradeOutcomes(CUR, adjLast, cr, justClosedCandlePrice);
 updatePostMortemWatch(CUR, cr, adjLast);

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
  levelConfluence:t('tagLevelConfluence'), deltaConfirmTrend:t('tagDeltaConfirmTrend'), deltaAbsorption:t('tagDeltaAbsorption'),
  valensEliteScalp:t('tagValensEliteScalp'),
  srTestReversal:t('tagSrTestReversal'), srBreakContinuation:t('tagSrBreakContinuation')};
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
  levelConfluence:84, deltaConfirmTrend:70, deltaAbsorption:77,
  srTestReversal:78, srBreakContinuation:74};
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
  insideBar:'neutral', bollSqueeze:'neutral', macdZeroCross:'neutral', ttmSqueeze:'neutral', tradeDelta:'neutral',
  srTestReversal:'reversal', srBreakContinuation:'trend'
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
 // ---- MAKRO TREND YANLILIĞI AYARLAMASI — bkz. Block D'deki fetchMacroTrend, 26 Eylül 2026 17 yıllık
 // gerçek veri doğrulaması (200-günlük SMA + 30/200 kesişimi, sabit/literatür parametreleri, OOS'ta
 // discovery'den daha güçlü çıktı — overfit değil). Sadece 'trend' ailesini ayarlar, 'reversal'a dokunmaz.
 function macroTrendAdjustment(family, candDir, macroTrend){
  if(family!=='trend' || !macroTrend) return 0;
  const trendDir = macroTrend>0?1:-1, strong = Math.abs(macroTrend)>=2;
  if(candDir===trendDir) return strong?10:5;
  return strong?-14:-7;
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
 // ---- Kullanıcı düzeltmesi: ⚡ Valens Elit Scalp, AI SIGNAL ENGINE'in paylaştığı candidates/best
 // havuzuna KARIŞMAYACAK — terminal ("AI SIGNAL ENGINE" yazan yer) hiç etkilenmeden kendi işine
 // devam etsin, bu strateji SADECE kendi panelinde, TAMAMEN bağımsız bir karar/takip süreciyle
 // çalışsın. Aynı ham veriyi (indikatörler, yapı, delta) kullanır ama kendi ayrı mantığıyla karar
 // verir — bu yüzden 'valensEliteScalp' etiketini genel havuza HİÇ eklemiyoruz, ayrı yakalayıp
 // aşağıda (bkz. "⚡ VALENS ELİT SCALP — bağımsız karar/takip") kendi başına işliyoruz.
 const eliteScalpTag = (cr.strategyTags||[]).find(tg=>tg.key==='valensEliteScalp') || null;
 (cr.strategyTags||[]).forEach(tag=>{
  if(tag.key==='valensEliteScalp') return;
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
  const macroTrendAdj = macroTrendAdjustment(family, tag.dir, window.valensMacroTrend||0);
  if(macroTrendAdj!==0) confidence = Math.min(97, Math.max(50, Math.round(confidence+macroTrendAdj)));
  // ---- CANLI GUVEN MOTORU AYARLAMASI (bkz. Block D - window.valensChartRead.mlConfidence) ----
  // Kullanicinin istegi: "su an hangi kurulum en cok destekleniyor" sorusunu, sadece kac strateji
  // ayni yonde diye SAYMAK yerine (bu ayri test edildi, hicbir fark yaratmadi: %33.0 vs %32.8),
  // 17 yillik gercek veride ogrenilmis bir modelin verdigi olasilikla cevaplar. Diger ayarlamalarla
  // (rejim/yapi/tukenis) AYNI desende - sert bir kapi degil, orantili bir bonus/ceza.
  const mlProb = (cr.mlConfidence && cr.mlConfidence[tag.key]!=null) ? cr.mlConfidence[tag.key] : null;
  if(mlProb!=null){
   const mlAdj = Math.max(-15, Math.min(10, Math.round((mlProb-0.3336)*120)));
   if(mlAdj!==0) confidence = Math.min(97, Math.max(50, Math.round(confidence+mlAdj)));
  }
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
  candidates.push({key:tag.key, dir:tag.dir, confidence, label, realWinRate, realTrades:bt?bt.trades:0, confSource:source, regime:marketRegime, family, structureBias:cr.structureBias||0, exhaustionBias:cr.exhaustionBias||0, macroTrend:window.valensMacroTrend||0, fvgZone:tag.fvgZone||null, boxZone:tag.zone||null, mlConfidence:mlProb});
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
 const positionCapBlocked = openPositionCountForSymbol(CUR)>=3 || candleAlreadyUsed(CUR, cr.candleTime);
 let armed = technicallyArmed && !riskBlocked && !positionCapBlocked;

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
  armed = technicallyArmed && !riskBlocked && !positionCapBlocked;
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

 // ---- ARDIŞIK KAYIP DEVRE KESİCİ (sadece ana motor, hesap-geneli — bkz. mainLossStreakKey yorumu) ----
 const mainStreak = getMainLossStreak();
 const circuitPaused = !!(mainStreak.pausedUntil && Date.now() < mainStreak.pausedUntil);
 let circuitRemainMin = 0;
 if(circuitPaused){ circuitRemainMin = Math.ceil((mainStreak.pausedUntil-Date.now())/60000); armed=false; }
 // Duraklama süresi geçti ama seri (3+) henüz bir KAZANÇLA temizlenmediyse: az önce kaybettiren
 // yönü tekrarlamak isteyen adaya güven cezası — "en mantıklı pozisyon" mantığı, ters yön cezasız.
 const circuitPenaltyActive = !circuitPaused && mainStreak.count>=3 && rawDir===mainStreak.dir;
 if(circuitPenaltyActive){
  conf = Math.max(50, Math.round(conf-15));
  if(conf<THRESHOLD) armed=false;
 }
 // Duraklama tetiklendiğinde son kayıpların bağlamına (rejim/trend) bakıp kısa, dürüst bir sebep
 // özeti üret — "neden kaybetti bilsin" isteğiyle örtüşüyor, ekstra veri toplamaya gerek yok
 // (context zaten işlem açılırken kaydediliyordu).
 let circuitReasonIsRegimeShift = false;
 if(circuitPaused){
  const ctxs = mainStreak.recentLossCtx||[];
  circuitReasonIsRegimeShift = ctxs.length>0 && ctxs.every(c=>c && (c.regime!==marketRegime || (typeof c.trend==='number' && typeof cr.trend==='number' && Math.sign(c.trend||0)!==Math.sign(cr.trend||0))));
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
  if(circuitPaused){
   const dirLbl = mainStreak.dir>0?'BUY':'SELL';
   whyHtml += circuitReasonIsRegimeShift ? t('circuitPausedWhyRegime')(circuitRemainMin,dirLbl) : t('circuitPausedWhyGeneric')(circuitRemainMin,dirLbl);
  } else if(circuitPenaltyActive){
   whyHtml += t('circuitPenaltyWhyNote')(mainStreak.dir>0?'BUY':'SELL');
  }
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
 else if(circuitPaused){tg.className='trigger wait';tg.textContent=t('circuitPausedStatus')(circuitRemainMin);}
 else if(technicallyArmed && riskBlocked){tg.className='trigger wait';tg.textContent=t('riskBlockedStatus');}
 else if(technicallyArmed && positionCapBlocked){tg.className='trigger wait';tg.textContent=t('positionOpenStatus');}
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
    const tr15=window.valensCandleSendTracker;
    const awaiting4min = candleLimitHit && INT==='15' && tr15 && tr15.count===1 && tr15.candleTime===candleTimeForSig && tr15.dir===rawDir;
    if(awaiting4min){ mt5SendBtn.disabled=true; mt5SendBtn.textContent=t('mt5CandleWait4MinBtn'); }
    else if(candleLimitHit){ mt5SendBtn.disabled=true; mt5SendBtn.textContent=t('mt5CandleLimitBtn'); }
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
   // Kullanıcı isteği: "en son sinyal de scalp plan kısmında giriş/stop/tp kısımlarında yazsın" —
   // aktif bir kurulum yokken alanları boş "—" bırakmak yerine, EN SON verilen sinyalin gerçek
   // giriş/stop/tp değerlerini gösteriyoruz (recordLastSignal ile zaten kaydediliyordu, "Son sinyal"
   // metin satırında kullanılıyordu — şimdi asıl sayı kutularında da görünüyor).
   const lastSc=getLastSignal(CUR,'scalp'), lastSw=getLastSignal(CUR,'swing');
   if(lastSc){ document.getElementById('scEntry').textContent=fmt(lastSc.entry); document.getElementById('scStop').textContent=fmt(lastSc.sl); document.getElementById('scTp').textContent=fmt(lastSc.tp); }
   else { ['scEntry','scStop','scTp'].forEach(id=>document.getElementById(id).textContent='—'); }
   if(lastSw){ document.getElementById('swEntry').textContent=fmt(lastSw.entry); document.getElementById('swStop').textContent=fmt(lastSw.sl); document.getElementById('swTp').textContent=fmt(lastSw.tp); }
   else { ['swEntry','swStop','swTp'].forEach(id=>document.getElementById(id).textContent='—'); }
   scStatusEl.className='trade-status wait';
   scStatusEl.textContent = circuitPaused ? t('circuitPausedStatus')(circuitRemainMin) : (technicallyArmed && riskBlocked) ? t('riskBlockedStatus') : (technicallyArmed && positionCapBlocked) ? t('positionOpenStatus') : awaitingConfirmation ? t('confirmStatus')(confirmedCandles,REQUIRED_CONFIRM_CANDLES,rawDir>0?'BUY':'SELL') : cooldownActive ? t('cooldownStatus')(cooldownRemainMin) : t('waitStatus')(THRESHOLD,conf);
   alertBox.classList.remove('show');
   window.valensPendingSignal = null;
   const mt5SendBtnIdle=document.getElementById('mt5SendBtn');
   if(mt5SendBtnIdle){ mt5SendBtnIdle.disabled=true; mt5SendBtnIdle.textContent=t('mt5SendBtnLabel'); }
 }

 // ============ ⚡ VALENS ELİT SCALP — bağımsız karar/takip ============
 // Kullanıcı düzeltmesi: "terminal gene çalışmaya devam etsin, biz stratejimizi ayrı bir şekilde
 // soldaki bölgede test edicez... sadece ai signal engine yazan yerde değil soldaki kendi bölmesinde
 // çalışacak" — yukarıdaki armed/candidates akışına HİÇ karışmaz (o akış hâlâ tamamen kendi başına,
 // eskisi gibi çalışıyor). Aynı ham veriyi (atr, adjLast, S/R, rejim) okur ama TAMAMEN AYRI karar verir
 // ve AYRI bir localStorage kaydında (logEliteScalpTrade) kendi işlemini takip eder — ana motorun o an
 // açık bir işlemi olsa/olmasa bile bu stratejiyi etkilemez. Önce (varsa) açık kendi işlemini TP/SL'ye
 // göre çözer, SONRA yeni bir kurulum var mı bakar (updateTradeOutcomes'taki "önce çöz sonra karar ver"
 // ile aynı sıralama mantığı, aynı whipsaw nedeniyle).
 // ESKİ Elit Scalp (4H/1H Bias+OB Mit+Delta) ARTIK TETİKLENMİYOR — kullanıcı isteğiyle YERİNE
 // gerçek 17 yıllık veriyle doğrulanmış 3'lü çeşitlendirilmiş portföy (SR+EMA/MACD+ORB, bkz.
 // updateCombo3 tanımı yukarıda) geçti. Eski detectStrategyTags/eliteWinDir mantığı koda dokunulmadan
 // duruyor (geri dönüş gerekirse), sadece artık logEliteScalpTrade ÇAĞRILMIYOR.
 updateCombo3(CUR);
 updateComboLastSignalUI(CUR);
 if(typeof updateEliteScalpPanel==='function') updateEliteScalpPanel();

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
// ---- DÜZELTME (1 Ekim 2026, kullanıcı geri bildirimi: "ticker eskiye takılıp duruyor") ----
// Kök neden: xaus.com/Binance API'leri gayet sağlıklı, sorun tarayıcının kendisi — Chrome (ve diğer
// modern tarayıcılar) uzun süre ARKA PLANDA/odak dışı kalan sekmelerde setInterval'i agresifçe
// yavaşlatıyor (15sn'lik tazeleme dakikalarca gecikebiliyor). Terminal zaten saatlerce açık bir
// sekmede unutulmaya müsait olduğu için (bkz. sunucu taşıma planı — asıl kalıcı çözüm o), kullanıcı
// sekmeye geri döndüğünde ESKİ fiyatla karşılaşıyordu. Buradaki kısmi düzeltme: sekme tekrar
// görünür/aktif olduğu AN, throttled interval'i beklemeden anında tazele.
document.addEventListener('visibilitychange', ()=>{
 if(document.visibilityState==='visible'){ updateGoldOffset().then(updateTickerBar); }
});
window.addEventListener('focus', ()=>{ updateGoldOffset().then(updateTickerBar); });


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

 let ohlc=[],ws=null,tradeWs=null,binSym=null,curSym=null,srLines=[],fibLines=[],dynSup,dynRes,patternMarkers=[],zoneLines=[],fvgZoneLines=[],fvgMarker=null,trailedSLLine=null,eliteTrailedSLLine=null;
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
 // ---- 3 LINE STRIKE — kullanıcı isteği: TradingView'da gördüğü "The Arty" göstergesinden ilham,
 // bizim setimizde henüz olmayan tek gerçekten yeni/net-tanımlı parça buydu (MA bulutları ve risk
 // paneli zaten sahip olduğumuz EMA/ATR altyapısıyla örtüşüyordu, tekrar eklemedik). Klasik tanım:
 // 3 ardışık AYNI yönlü mum (her biri bir öncekinden daha ileri kapanıyor), ardından 4. mum TERS
 // yönde ve önceki 3 mumun TAMAMINI (ilk mumun açılışının ötesine kadar) siliyor. Literatürde bu
 // formasyonun "devam mı dönüş mü" sinyali olduğu tartışmalı (kaynaklar farklı etiketliyor) — bu
 // yüzden burada d:'bull'/'bear' SADECE YAPISAL yönü (4. mumun yönünü) belirtiyor, gerçek anlamı
 // (devam mı dönüş mü) gerçek backtest ile ayrıca doğrulanmadan hiçbir canlı karar mantığına
 // (armed/confidence) bağlanmadı — şimdilik sadece cr.pattern üzerinden kâr koruma dönüş-sinyali
 // sayımına (detectReversalSignalCount) ve işlem context'ine (ileride analiz için) giriyor.
 function detect3LineStrike(a){
  if(a.length<4) return null;
  const p3=a[a.length-4], p2=a[a.length-3], p1=a[a.length-2], c=a[a.length-1];
  const threeDown = p3.close<p3.open && p2.close<p2.open && p1.close<p1.open && p2.close<p3.close && p1.close<p2.close;
  const threeUp = p3.close>p3.open && p2.close>p2.open && p1.close>p1.open && p2.close>p3.close && p1.close>p2.close;
  if(threeDown && c.close>c.open && c.open<=p1.close && c.close>p3.open) return {n:'3 Line Strike', d:'bull'};
  if(threeUp && c.close<c.open && c.open>=p1.close && c.close<p3.open) return {n:'3 Line Strike', d:'bear'};
  return null;
 }
 function pattern(a){
  if(a.length<2)return null;const c=a[a.length-1],p=a[a.length-2];
  const strike=detect3LineStrike(a);
  if(strike) return strike;
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
 // ---- KLASİK GRAFİK FORMASYONLARI (omuz-baş-omuz, M/W çift tepe/dip) — kullanıcı isteği:
 // "bunları omuz baş omuz M W cup gibi grafik yorumlama ile de destekleseler". findSwingPoints
 // ham fraktal noktaları verir, art arda aynı tip gelebilir (iki 'high' arasında hiç 'low'
 // sinyallenmeyebilir) — burada daha GÜÇLÜ olan tutulup diğeri elenerek gerçek ALTERNE (yüksek-
 // düşük-yüksek-düşük...) bir dizi elde edilir; klasik formasyonlar bu dizi üzerinde tanınır.
 // Cup&Handle bilerek KAPSAM DIŞI bırakıldı — yuvarlak tabanlı, net bir "kaç swing" tanımı
 // olmayan bir formasyon, düşük kaliteli/güvenilmez bir versiyon eklemektense hiç eklenmedi.
 function alternatingSwings(a, lookback){
  const w=a.slice(-lookback);
  const raw=findSwingPoints(w);
  if(!raw.length) return [];
  let clean=[raw[0]];
  for(let i=1;i<raw.length;i++){
   const p=raw[i], last=clean[clean.length-1];
   if(p.type===last.type){
    if(p.type==='high' && p.price>last.price) clean[clean.length-1]=p;
    else if(p.type==='low' && p.price<last.price) clean[clean.length-1]=p;
   } else clean.push(p);
  }
  return clean;
 }
 // ---- M/W (Çift Tepe/Çift Dip) — iki benzer yükseklikteki tepe/dip arasındaki "boyun çizgisi"
 // (neckline) kırılınca onaylanır. dir:-1 = M (çift tepe, düşüş), dir:1 = W (çift dip, yükseliş).
 function detectDoubleTopBottom(a){
  if(a.length<30) return null;
  const sw=alternatingSwings(a,80);
  if(sw.length<3) return null;
  const [p1,neck,p2]=sw.slice(-3);
  const curr=a[a.length-1];
  const tol=0.0035; // iki tepe/dip birbirine bu kadar (·%0.35) yakınsa "eşit" sayılır
  if(p1.type==='high' && neck.type==='low' && p2.type==='high'){
   if(Math.abs(p1.price-p2.price)/p1.price<tol && curr.close<neck.price) return {key:'doubleTopBottom', dir:-1};
  }
  if(p1.type==='low' && neck.type==='high' && p2.type==='low'){
   if(Math.abs(p1.price-p2.price)/p1.price<tol && curr.close>neck.price) return {key:'doubleTopBottom', dir:1};
  }
  return null;
 }
 // ---- OMUZ-BAŞ-OMUZ (ve tersi) — orta tepe/dip (baş) iki yandakinden (omuzlar, birbirine yakın)
 // daha belirgin olmalı; iki omuz arasındaki dip/tepelerin (neckline) ortalaması kırılınca onaylanır.
 function detectHeadShoulders(a){
  if(a.length<40) return null;
  const sw=alternatingSwings(a,110);
  if(sw.length<5) return null;
  const [ls,neck1,head,neck2,rs]=sw.slice(-5);
  const curr=a[a.length-1];
  const shoulderTol=0.006; // omuzlar birbirine bu kadar (%0.6) yakın olmalı
  if(ls.type==='high'&&neck1.type==='low'&&head.type==='high'&&neck2.type==='low'&&rs.type==='high'){
   const neckline=(neck1.price+neck2.price)/2;
   if(head.price>ls.price && head.price>rs.price && Math.abs(ls.price-rs.price)/ls.price<shoulderTol && curr.close<neckline){
    return {key:'headShoulders', dir:-1};
   }
  }
  if(ls.type==='low'&&neck1.type==='high'&&head.type==='low'&&neck2.type==='high'&&rs.type==='low'){
   const neckline=(neck1.price+neck2.price)/2;
   if(head.price<ls.price && head.price<rs.price && Math.abs(ls.price-rs.price)/ls.price<shoulderTol && curr.close>neckline){
    return {key:'headShoulders', dir:1};
   }
  }
  return null;
 }
 // ---- ANA/ARA DESTEK-DİRENÇ TEST + TEPKİ — kullanıcı isteği: "1-4 saatlikte ana destek direnç
 // belirledik, 30 dklıkta ara hatları zaten belirliyoruz, bu seviyelerin kırılımı test edilip geri
 // dönüşü ya da devamını GÜÇLÜ test edebilecek bir strateji". Sert bir "hepsi birden" şartı DEĞİL —
 // seviyeye yakınlık ZORUNLU (asıl kanıt), sonra RSI aşırılığı / dönüş mumu / klasik formasyon
 // (M-W, omuz-baş-omuz) İKİNCİ kanıtlarından HERHANGİ BİRİ yeterli (Elit Scalp'teki "3'te 3" katı
 // şartının neredeyse hiç ateşlenmediğinden ders çıkarıldı — burada amaç daha SIK ama hâlâ gerçek
 // kanıta dayalı sinyal).
 function detectSRTestReversal(a, levels, rsi, structureBias){
  const curr=a[a.length-1], last=curr.close;
  if(last==null) return null;
  const pat=pattern(a);
  const dtb=detectDoubleTopBottom(a), hs=detectHeadShoulders(a);
  const nearTol=0.0025;
  const supLevel = levels.mainSup!=null ? levels.mainSup : levels.dynSup;
  const resLevel = levels.mainRes!=null ? levels.mainRes : levels.dynRes;
  if(supLevel!=null && Math.abs(last-supLevel)/last<nearTol && structureBias>=-1){
   const bullCandle = pat && pat.d==='bull';
   const rsiOversold = rsi!=null && rsi<35;
   const patternAgrees = (dtb&&dtb.dir>0) || (hs&&hs.dir>0);
   if(bullCandle || rsiOversold || patternAgrees) return {key:'srTestReversal', dir:1};
  }
  if(resLevel!=null && Math.abs(last-resLevel)/last<nearTol && structureBias<=1){
   const bearCandle = pat && pat.d==='bear';
   const rsiOverbought = rsi!=null && rsi>65;
   const patternAgrees = (dtb&&dtb.dir<0) || (hs&&hs.dir<0);
   if(bearCandle || rsiOverbought || patternAgrees) return {key:'srTestReversal', dir:-1};
  }
  return null;
 }
 // ---- ANA/ARA DESTEK-DİRENÇ KIRILIM + DEVAM — aynı seviyeler bu kez TERS yönde: taze bir kırılım
 // (bir önceki mum hâlâ seviyenin içindeydi, bu mum tam gövdeyle dışına çıktı) + yapı karşı değilse.
 function detectSRBreakContinuation(a, levels, structureBias){
  const curr=a[a.length-1], prev=a[a.length-2];
  if(!prev) return null;
  const resLevel = levels.mainRes!=null ? levels.mainRes : levels.dynRes;
  const supLevel = levels.mainSup!=null ? levels.mainSup : levels.dynSup;
  if(resLevel!=null && curr.close>resLevel && prev.close<=resLevel && curr.close>curr.open && structureBias>=0){
   return {key:'srBreakContinuation', dir:1};
  }
  if(supLevel!=null && curr.close<supLevel && prev.close>=supLevel && curr.close<curr.open && structureBias<=0){
   return {key:'srBreakContinuation', dir:-1};
  }
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
  // bosSignal DEVRE DIŞI (gerçek canlı kanıt): 167 işlemlik takipte net zararda (-$267, 5/11 ≈ %45).
  // chochSignal'e dokunulmadı, o ayrı bir istatistikte (küçük örnek, henüz kanıt yetersiz).
  if(structUp && curr.close>lastHigh.price){
   return null; // if(externalBias<0) return null; return {key:'bosSignal', dir:1};
  }
  if(structUp && curr.close<lastLow.price) return {key:'chochSignal', dir:-1};
  if(structDown && curr.close<lastLow.price){
   return null; // if(externalBias>0) return null; return {key:'bosSignal', dir:-1};
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
 // DÜZELTME (kullanıcı geri bildirimi: gerçek 171 işlemlik veride bu kalıp 35 işlemde sadece %40
 // kazanmış, net +$90 — hacmi büyük ama katkısı neredeyse sıfır): iki sıkılaştırma eklendi —
 // (1) kırılım ARTIK sadece o boşluğun kenarına marjinal olarak dokunmakla değil, boşluğun kendi
 // yüksekliğinin en az %15'i kadar ÖTESİNE kapanmalı (gürültülü/sınırda kırılımlar elenir);
 // (2) kırılım TAZE olmalı — bir önceki mum HÂLÂ boşluğun "içinde" kapanmış olmalı, yoksa fiyat
 // zaten günlerdir kırılmış bir seviyenin ötesinde oturuyor demektir, bu artık yeni bir sinyal değil
 // (aynı kırık seviye için tekrar tekrar ateşlenmeyi de önler).
 function detectIFVG(a){
  if(a.length<25) return null;
  const fvgs=findFVGs(a,20), curr=a[a.length-1], prev=a[a.length-2];
  for(let i=fvgs.length-1;i>=0;i--){
   const f=fvgs[i];
   const margin=(f.top-f.bottom)*0.15;
   if(f.dir>0 && curr.close<f.bottom-margin && prev.close>=f.bottom) return {key:'ifvg', dir:-1};
   if(f.dir<0 && curr.close>f.top+margin && prev.close<=f.top) return {key:'ifvg', dir:1};
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
  // DÜZELTME (kullanıcı geri bildirimi: gerçek 171 işlemlik veride bu kalıp 24 işlemde sadece %41.7
  // kazanmış): eskiden EMA9/21 "az önce bir kılcal kadar kesişti" bile yeterliydi (ayrım şartı yok)
  // ve RSI bandı 45-70/30-55 gibi genişti, 50'ye çok yakın KARARSIZ bölgeyi de kapsıyordu. Artık (1)
  // EMA9/21 arasında fiyatın en az %0.08'i kadar GERÇEK bir ayrım olmalı (kılcal/gürültü kesişimleri
  // elenir), (2) RSI bandı 50'nin daha net üstünde/altında olacak şekilde daraltıldı (net momentum,
  // kararsız bölge değil).
  // DEVRE DIŞI (kullanıcı isteği, gerçek CANLI kanıt): daha önce bir kez sıkılaştırılmıştı ama gerçek
  // 167 işlemlik canlı takipte hâlâ net zararda (-$309, 13/29 ≈ %43). Bu ham backtest değil, GERÇEK
  // paranla olan sonuç — bu yüzden tekrar sıkılaştırmak yerine tamamen çıkarıldı.
  // const emaSepPct = ind.ema21 ? Math.abs(ind.ema9-ind.ema21)/ind.ema21 : 0;
  // if(ind.ema9>ind.ema21 && emaSepPct>0.0008 && ind.macd>0 && ind.rsi>50 && ind.rsi<68) tags.push({key:'emaCross', dir:1});
  // else if(ind.ema9<ind.ema21 && emaSepPct>0.0008 && ind.macd<0 && ind.rsi<50 && ind.rsi>32) tags.push({key:'emaCross', dir:-1});
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
  // (7) EMA21'e geri çekilme (trend devamı) — DEVRE DIŞI (gerçek canlı kanıt): 167 işlemlik takipte
  // net zararda (-$41, 5/11 ≈ %45).
  const ema21Series=emaLine(a,21).map(p=>p.value);
  // const pullback=detectEmaPullback(a, ema21Series); if(pullback) tags.push(pullback);
  // (8) İç mum (inside bar) kırılımı
  const insideBar=detectInsideBarBreakout(a); if(insideBar) tags.push(insideBar);
  // (9) Fair Value Gap retest
  // DEVRE DIŞI (30 Eylül 2026, gerçek kanıt — üç ayrı kontrolde de dogrulandi): tüm zamanlar 11 işlem
  // 2 kazanç -$734.84, sadece eylülde 6 işlem 0 kazanç -$799 — hiçbir dönemde net pozitif olmadı,
  // geçici kötü seri değil kronik zayıf strateji.
  // const fvgR=detectFVGRetest(a); if(fvgR) tags.push(fvgR);
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
  // (14) ORB Scalp varyantı (dar/tek mumluk aralık, fitil tetikli) — DEVRE DIŞI. Önce sadece mevcut
  // R:R'de (SL 1.6x/TP 0.5x ATR) test edilip %73.5 kazanma ama başabaşın (%76.2) altında bulunmuştu;
  // "belki hedef yanlış ayarlanmıştır" itirazı üzerine 17 yıllık gerçek veride TP 0.5x'ten 1.6x'e
  // kadar TAM bir tarama yapıldı (aynı 43.695 sinyal, 10 farklı hedef). SONUÇ: hiçbir hedefte kârlı
  // değil — kazanma oranı her hedefte başabaşın hemen altında kalıyor (en iyisi TP=1.0x'te bile
  // -0.049R/işlem). Bu, yanlış R:R değil, girişin (seans açılışından hemen sonra tek mumluk dar
  // aralığın fitille kırılması) gerçek bir yön bilgisi taşımadığı anlamına geliyor. detectScalpORB()
  // ileride farklı bir GİRİŞ mantığıyla (R:R değil) denenebilir diye silinmedi.
  // const scalpOrb=detectScalpORB(a); if(scalpOrb) tags.push(scalpOrb);
  // (15) No Wick (fitilsiz mum) geri test — DEVRE DIŞI (gerçek canlı kanıt): 167 işlemlik takipte
  // net zararda (-$135, 0/2 — küçük örnek ama %0 kazanma).
  // const noWick=detectNoWickRetest(a, ind.ema200); if(noWick) tags.push(noWick);
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
  // (32) VALENS ELİT SCALP — kullanıcı isteği: "kendi unique scalp stratejini üret, elindeki kar/zarar
  // verisiyle". İLK TASARIM (BOS+OB/FVG+Delta) gerçek 151 işlemlik GENEL geçmişe dayanıyordu, ama o veri
  // çoğunlukla 15dk gibi daha yavaş bir zaman diliminden geliyordu. Bu terminalin KENDİ backtest sistemiyle
  // (runHistoricalBacktest) 1 DAKİKA'nın kendi gerçek geçmişini test edince ortaya çıktı: BOS 1dk'da son
  // derece zayıf (%5, 2/41 — çok gürültülü/whipsaw'a açık), Order Block Mitigasyonu ise en güçlü çıkan
  // kalıp (%63, 5/8). Bu yüzden BOS'u ATIP kanıtlanan kalıpla değiştirdik: ÜST ZAMAN DİLİMİ (4H/1H) yön
  // verir — bu zaten scalp modunun orijinal tasarım ilkesiydi ("How to Analysis": üst zaman dilimi yön,
  // alt zaman dilimi onay) — sonra 1dk'da GERÇEKTEN kanıtlanmış Order Block Mitigasyonu VE canlı delta
  // (agresif alım/satım akışı) o yönde onay verirse ateşlenir. NOT: window.valensScalpBias ve tradeDelta
  // canlı-only veridir, runHistoricalBacktest bunları geçmiş mumlara yansıtamaz (backtest paneli bu
  // stratejiyi göstermez) — bu, scalp modunun HTF-bias fikrinin baştan beri sahip olduğu bir kısıt,
  // yeni değil. Gerçek başarı oranı ancak CANLI takiple (Strateji Canlı Performans paneli, kendi stratKey'i
  // ile) kanıtlanır — kullanıcının "bir süre test edelim" isteği zaten bunu hedefliyor. %80 gibi bir oran
  // GARANTİ EDİLEMEZ; bu, gerçek 1dk verisinden damıtılmış bir HİPOTEZ.
  // DÜZELTME (kullanıcı geri bildirimi: gerçek veride 4H/1H bias sadece %12.4 saatte hizalı çıktı ve
  // eklendiğimizden beri 5 gün boyunca hiç hizalanmadı — üçü BİRDEN şartı pratikte neredeyse hiç
  // ateşlenmiyordu). Artık üçünden HERHANGİ İKİSİ aynı yönde yeterli (3'te 3 yerine 3'te 2) — üçü de
  // varsa ve 2'si aynı yönde 1'i ters yöndeyse çoğunluğun yönü kazanır. Daha sık ama muhtemelen daha
  // düşük kaliteli ateşlenecek — gerçek oranı yine ancak canlı takiple (kendi paneli) kanıtlanır.
  const scalpBias=window.valensScalpBias;
  const biasDir = (scalpBias && scalpBias.h4Dir!==0 && scalpBias.h4Dir===scalpBias.h1Dir) ? Math.sign(scalpBias.h4Dir) : null;
  const obMitDir = obMit ? obMit.dir : null;
  const deltaDir = (deltaConf && deltaConf.key==='deltaConfirmTrend') ? deltaConf.dir : null;
  const eliteVotes = [biasDir, obMitDir, deltaDir].filter(d=>d!=null);
  const eliteDirCounts = {};
  eliteVotes.forEach(d=>{ eliteDirCounts[d]=(eliteDirCounts[d]||0)+1; });
  let eliteWinDir=null, eliteWinCount=0;
  Object.keys(eliteDirCounts).forEach(d=>{ if(eliteDirCounts[d]>eliteWinCount){ eliteWinCount=eliteDirCounts[d]; eliteWinDir=+d; } });
  if(eliteWinCount>=2){
   tags.push({key:'valensEliteScalp', dir:eliteWinDir});
  }
  // (33) ANA/ARA DESTEK-DİRENÇ TEST+TEPKİ / KIRILIM+DEVAM — kullanıcı isteği: Elit Scalp çok
  // seyrek ateşleniyordu, "biraz daha sık ama güvenilir" bir strateji istendi. Zaten çizilen
  // ana (1H, mainSRZones) + ara (mevcut zaman dilimi, dinamik) S/R seviyelerini kullanır — bkz.
  // ind.mainSup/mainRes/dynSup/dynRes/structureBias (botTick DIŞINDAKİ chart-engine script'inden
  // köprülenir, aynı S/R rakamları grafikte zaten çizili olanlarla BİREBİR aynı).
  if(ind.srLevels){
   const srRev=detectSRTestReversal(a, ind.srLevels, ind.rsi, ind.structureBias||0); if(srRev) tags.push(srRev);
   const srBreak=detectSRBreakContinuation(a, ind.srLevels, ind.structureBias||0); if(srBreak) tags.push(srBreak);
  }
  // (34) Klasik grafik formasyonları — DÜZELTME (gerçek backtest'te canlı yakalandı): bağımsız aday
  // olarak eklenmişlerdi ama gerçek oranları çok düşük çıktı (Omuz-Baş-Omuz %33, Çift Tepe/Dip %29 —
  // ikisi de 1:2 R:R başabaşının ALTINDA) — buna rağmen taban güvenleri (80/82) yüksek olduğu için
  // CANLI olarak %90+ güvenle "en güçlü aday" oldular, gerçek performanslarıyla TAMAMEN çelişen bir
  // sinyal ürettiler (tam da terminalin bu oturum boyu düzelttiğimiz "yanlış güven" sorunu). Bağımsız
  // aday olmaktan ÇIKARILDILAR — detectDoubleTopBottom/detectHeadShoulders artık SADECE
  // detectSRTestReversal'ın İÇİNDE bir confluence kanıtı (o strateji gerçekten %50 ile iyi çalışıyor).
  return tags;
 }
 // ---- GEÇMİŞ VERİ TESTİ (BACKTEST) — Kullanıcı isteği: "sinyal vermeden önce stratejiyi test etsin."
 // ÖNEMLİ AYRIM: bu rastgele/olası GELECEK yolları üretip "en iyisini" seçen bir şey DEĞİLDİR — o
 // yaklaşım her zaman şans eseri yukarı giden bir yol bulur, sahte güven yaratır. Bunun yerine, terminalin
 // zaten elinde olan GERÇEKTEN YAŞANMIŞ geçmiş mumlar üzerinde, her stratejinin (hem AL hem SAT) geçmişte
 // ateşlendiği HER noktayı bulup, o andan sonra fiyatın GERÇEKTE TP'ye mi SL'ye mi önce ulaştığını
 // (canlıdaki AYNI ATR formülüyle) kontrol eder — net etiketli, ayrı bir panelde gösterilir.
 // rangeStart/rangeEnd verilirse (derin/17 yıllık gerçek veri testi için) varsayılan 300 mumluk
 // pencere yerine o aralık taranır — parametre verilmezse davranış BİREBİR AYNI kalır.
 function runHistoricalBacktest(rangeStart, rangeEnd){
  if(ohlc.length<350) return null;
  const WARMUP=250; // uzun-lookback'li stratejiler (BOS/CHoCH, TTM Squeeze vb.) için yeterli geçmiş bırak
  const TEST_RANGE=Math.min(300, ohlc.length-WARMUP-1);
  const MAX_FORWARD=100; // TP/SL'ye ulaşması için en fazla 100 mum ileri bak; ulaşamazsa "çözülmemiş" say, sayma
  if(TEST_RANGE<20 && rangeStart==null) return null;
  const start = rangeStart!=null ? rangeStart : WARMUP;
  const end = rangeEnd!=null ? rangeEnd : WARMUP+TEST_RANGE;
  const results={};
  // DÜZELTME (17 yıllık gerçek veri testi sırasında bulundu): histOhlc eskiden ohlc.slice(0,i+1) idi —
  // yani i büyüdükçe (binlerce/yüz binlerce mum) HER iterasyonda git gide büyüyen bir dizi kopyalanıyor
  // ve bazı göstergeler (ör. ema200Real) bu SINIRSIZ diziyi baştan sona tarıyordu — O(n²) karmaşıklık,
  // 400 binin üzerinde mumla pratik olarak asla bitmiyordu. Ayrıca bu GERÇEKÇİ de değildi: canlı sistem
  // zaten hiçbir zaman "2009'dan bugüne kadarki tüm mumları" görmüyor, loadHistory() sabit limit=1000
  // mumla çalışıyor. Son 1000 muma sınırlamak hem performansı O(1)'e indiriyor hem canlı davranışla
  // birebir tutarlı hale getiriyor.
  const HIST_WINDOW=1000;
  for(let i=start; i<end; i++){
   const histOhlc=ohlc.slice(Math.max(0,i+1-HIST_WINDOW), i+1);
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

   // srLevels: mainSup/mainRes (1H mainSRZones) geçmiş her nokta için yeniden inşa edilemiyor
   // (ayrı bir 1H veri çekimi gerektirir) — null bırakılıyor, detectSRTestReversal/Continuation
   // bu durumda otomatik dynSup/dynRes'e (o anki histOhlc'den GERÇEKTEN yeniden inşa edilebilen)
   // düşüyor — kısmi ama gerçek bir backtest kapsaması.
   const {sup:histSup,res:histRes}=supRes(histOhlc);
   const tags=detectStrategyTags(histOhlc, {rsi:rsiReal, macd:macdReal, ema9:ema9Real, ema21:ema21Real, ema50:ema50Real,
     ema200:ema200Real, vwap:vwapReal, zones:[], bollPct:bollPctReal!==null?bollPctReal:50, srBias:0, fibZone:null, tradeDelta:null,
     srLevels:{mainSup:null, mainRes:null, dynSup:histSup, dynRes:histRes}, structureBias:detectSwingStructure(histOhlc,60)});

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
  // dolar tavanı var — bir bölge, ATR ne olursa olsun HARD_MAX_ZONE_WIDTH'ten GENİŞ OLAMAZ.
  // DÜZELTME 4 (kullanıcı geri bildirimi): 10 dolarlık tavan hâlâ "alan çok büyük" hissi veriyordu —
  // en uygun/en dar noktaya indirmek için 5 dolara düşürüldü.
  const HARD_MAX_ZONE_WIDTH=5;
  const maxZoneWidth=Math.min(atrRef*1.4, HARD_MAX_ZONE_WIDTH);
  const minGap=Math.min(atrRef*0.5, HARD_MAX_ZONE_WIDTH*0.6);
  // ÖNEMLİ: aşağıdaki merge döngüsü sadece İKİ bölge BİRLEŞTİĞİNDE sonucu sınırlıyordu — ama
  // detectConsolidationZones gibi bir kaynaktan gelen TEK bir ham bölge zaten kendi başına
  // HARD_MAX_ZONE_WIDTH'ten geniş gelebiliyordu (hiç birleşmeden), bu durumda hiç kontrol edilmeden
  // geçiyordu. Her adayı kaynağından çıkar çıkmaz (merge'den ÖNCE) bu sınıra sabitliyoruz — hiçbir
  // bölge, hangi kaynaktan gelirse gelsin, asla bu sınırı aşamaz.
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
   const lastPrice=bars[bars.length-1].close;
   let newZones=buildMainSRZones(bars, lastPrice);
   // DÜZELTME (kullanıcı isteği): "destek kırıldı ya da direnç kırıldı, eğer all-time low ya da
   // all-time high'da DEĞİLSE önceden o bölgede oluşmuş destek/dirençlere baksın" — fiyat keskin
   // bir hareketle son 200 saatlik mumun hiç görmediği bir bölgeye geçtiğinde, orada GERÇEKTEN
   // hiç destek/direnç yokmuş gibi görünüyordu (yukarıdaki 200 saatlik pencerede kanıt yok) — ama
   // bu sadece SON birkaç günde oraya hiç gelinmediği anlamına gelir, aylar/yıllar önce orada
   // gerçekten oturulmuş/dönülmüş olabilir. Yakın bölge yoksa (>3×ATR), fiyat gerçek bir all-time
   // uç noktasında değilse günlük mumlarla (yıllara yayılan) geçmişe bakıp o bölgedeki GERÇEK eski
   // destek/dirençleri buluyoruz — hâlâ aynı HARD_MAX_ZONE_WIDTH sert tavan ve aynı kanıt şartları
   // (count≥2 vb.) geçerli, sadece bakılan pencere uzuyor.
   const atrRef=calcATR(bars,14)||1;
   const nearestGap=newZones.length ? Math.min(...newZones.map(z=>Math.abs(lastPrice-(z.hi+z.lo)/2))) : Infinity;
   if(nearestGap>atrRef*3){
    try{
     const rD=await fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=1d&limit=1000`);
     const dD=await rD.json();
     if(Array.isArray(dD)&&dD.length){
      const dailyBars=dD.map(k=>({time:k[0]/1000,open:+k[1],high:+k[2],low:+k[3],close:+k[4]}));
      const allTimeHigh=Math.max(...dailyBars.map(b=>b.high)), allTimeLow=Math.min(...dailyBars.map(b=>b.low));
      const nearAth=Math.abs(lastPrice-allTimeHigh)/allTimeHigh<0.01, nearAtl=Math.abs(lastPrice-allTimeLow)/allTimeLow<0.01;
      if(!nearAth && !nearAtl){
       const longZones=buildMainSRZones(dailyBars, lastPrice).filter(z=>Math.abs(lastPrice-(z.hi+z.lo)/2)<=atrRef*3);
       if(longZones.length){
        newZones=[...longZones, ...newZones].sort((a,b)=>Math.abs(lastPrice-(a.hi+a.lo)/2)-Math.abs(lastPrice-(b.hi+b.lo)/2)).slice(0,4);
       }
      }
     }
    }catch(e){ /* ikincil/geriye dönük kaynak, ana akışı bozmasın */ }
   }
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
 // ---- MAKRO TREND YANLILIĞI (kurumsal referans: 200-günlük SMA + 30/200 kesişimi) ----
 // 26 Eylül 2026'da 17 yıllık gerçek XAUUSD verisinde doğrulandı: bu iki kural (Moskowitz/Ooi/Pedersen
 // 2012 "Time Series Momentum" ve klasik golden/death cross tarzı, LİTERATÜRDEN sabit — bizim veriye
 // göre AYARLANMAMIŞ parametreler) OOS (2019-2026) döneminde discovery'den (2009-2018) DAHA GÜÇLÜ çıktı
 // (Sharpe 0.15→0.43 ve -0.05→0.69) — parametre veriye göre uydurulmadığı için bu güçlenme overfit
 // değil, gerçek/kalıcı bir edge işareti. window.valensMacroTrend -2 (güçlü düşüş, fiyat+30SMA ikisi de
 // 200SMA altında) ile +2 (güçlü yükseliş) arası; sadece 'trend' ailesindeki stratejileri ayarlar —
 // 'reversal' ailesi zaten kendi mantığıyla aşırı uçlarda dönüş arıyor, makro trend onunla çelişebilir,
 // o yüzden dokunulmuyor (bkz. structureAdjustment/exhaustionAdjustment'ın da aynı ayrımı yapması).
 async function fetchMacroTrend(sym){
  const bs=MAP[sym]; if(!bs){ window.valensMacroTrend=0; return; }
  try{
   const r=await fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=1d&limit=250`);
   const d=await r.json();
   if(!Array.isArray(d)||d.length<200){ window.valensMacroTrend=0; return; }
   const closes=d.map(k=>+k[4]);
   const last=closes[closes.length-1];
   const sma=(arr,p)=>{ const s=arr.slice(-p); return s.reduce((a,b)=>a+b,0)/s.length; };
   const sma200=sma(closes,200), sma30=sma(closes,30);
   let bias=0;
   bias += last>sma200 ? 1 : -1;
   bias += sma30>sma200 ? 1 : -1;
   window.valensMacroTrend=bias;
  }catch(e){ /* ikincil sinyal, ana akışı bozmasın */ }
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
 // ---- ⚡ VALENS ELİT SCALP — ÜST ZAMAN DİLİMİ BIAS ("How to Analysis" görseli + Türkçe BIAS/DOL
 // videosu): 4H ve 1H'ı mevcut ohlc/WS pipeline'ına HİÇ dokunmadan, fetchMainSR ile AYNI desende
 // (bağımsız REST kline çağrısı) çeker, detectSwingStructure ile yapı yönünü okur. valensEliteScalp
 // (detectStrategyTags) bunu window.valensScalpBias üzerinden okur — artık ayrı bir "mod"a bağlı
 // değil, sembol seçiliyken sürekli 2dk'da bir tazelenir.
 async function fetchScalpBias(sym){
  const bs=MAP[sym]; if(!bs){ window.valensScalpBias=null; return; }
  try{
   const [r4,r1]=await Promise.all([
    fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=4h&limit=100`),
    fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=1h&limit=100`)
   ]);
   const [d4,d1]=await Promise.all([r4.json(), r1.json()]);
   if(!Array.isArray(d4)||!Array.isArray(d1)||!d4.length||!d1.length) return;
   const toBars=d=>d.map(k=>({time:k[0]/1000,open:+k[1],high:+k[2],low:+k[3],close:+k[4]}));
   window.valensScalpBias = {h4Dir: detectSwingStructure(toBars(d4),60), h1Dir: detectSwingStructure(toBars(d1),60)};
  }catch(e){ /* sessizce yoksay — ikincil bir veri kaynağı, ana grafiği bozmasın */ }
 }
 window.valensFetchScalpBias=function(){ if(curSym) fetchScalpBias(curSym); };
 setInterval(()=>{ if(curSym) fetchScalpBias(curSym); }, 2*60*1000);

 // ---- 3'LÜ ÇEŞİTLENDİRİLMİŞ PORTFÖY (SR+EMA/MACD+ORB) İÇİN BAĞIMSIZ H1/4H VERİ ----
 // fetchScalpBias ile AYNI desen (bağımsız REST kline çağrısı, mevcut ohlc/WS pipeline'ına hiç
 // dokunmadan) — bu üçlü strateji 1 SAATLİK barlar üzerinde test edildi (canlı terminal 15dk'da
 // çalışıyor), bu yüzden kendi H1 verisini çeker. Tüketimi (updateCombo3) FARKLI bir <script>
 // blogunda (botTick'in bloğu) — window.valensCombo3H1/H4Trend üzerinden köprülenir.
 async function fetchCombo3Data(sym){
  const bs=MAP[sym]; if(!bs) return;
  try{
   const [r1,r4]=await Promise.all([
    fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=1h&limit=500`),
    fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=4h&limit=100`)
   ]);
   const [d1,d4]=await Promise.all([r1.json(), r4.json()]);
   if(!Array.isArray(d1)||!d1.length||!Array.isArray(d4)||!d4.length) return;
   const toBars=d=>d.map(k=>({time:Math.floor(k[0]/1000),open:+k[1],high:+k[2],low:+k[3],close:+k[4]}));
   // SON eleman Binance'te HENÜZ KAPANMAMIŞ (o an oluşan) mum olabilir — backtest sadece KAPANMIŞ
   // barlarla çalıştığı için (lookahead yok) burada da atılıyor.
   const h1closed=toBars(d1).slice(0,-1);
   const h4closed=toBars(d4).slice(0,-1);
   if(h1closed.length<80 || h4closed.length<10) return;
   let ema=h4closed[0].close; const k=2/51;
   h4closed.forEach((c,i)=>{ ema = i? c.close*k+ema*(1-k) : c.close; });
   const trend = h4closed[h4closed.length-1].close>ema ? 1 : -1;
   window.valensCombo3H1 = {sym, bars:h1closed};
   window.valensCombo3H4Trend = {sym, trend};
  }catch(e){ /* sessizce yoksay — ikincil bir veri kaynağı, ana grafiği bozmasın */ }
 }
 window.valensFetchCombo3=function(){ if(curSym) fetchCombo3Data(curSym); };
 setInterval(()=>{ if(curSym) fetchCombo3Data(curSym); }, 5*60*1000);

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
 // ---- KÂR KORUMA (trailing stop) ÇİZGİSİ — kullanıcı isteği: "stopun çekildiği yeri kırmızı küçük
 // bir çizgi ile göstersin... grafiği oynattıkça oynamasın, bulunduğu alanda sabit kalsın". DOM overlay
 // (scalp kutusunda kullanılan teknik) YERİNE lightweight-charts'ın NATİF cs.createPriceLine'ı
 // kullanılıyor — bu, tanımı gereği fiyat eksenine bağlıdır, kaydırma/yakınlaştırmada KENDİLİĞİNDEN
 // doğru fiyatta kalır, elle yeniden konumlandırma gerektirmez (mainSRZones/scalp kutusunun aksine).
 // Ana motorun işlemi ile Elit Scalp'in AYRI işlemi aynı anda açık olabileceği için iki AYRI çizgi.
 window.valensDrawTrailedSL=function(price, dir){
  if(trailedSLLine) cs.removePriceLine(trailedSLLine);
  trailedSLLine=cs.createPriceLine({price, color:'#ff3b5c', lineWidth:2, lineStyle:0, axisLabelVisible:true, title:t('trailedSLTitle')});
 };
 window.valensClearTrailedSL=function(){
  if(trailedSLLine){ cs.removePriceLine(trailedSLLine); trailedSLLine=null; }
 };
 window.valensDrawEliteTrailedSL=function(price, dir){
  if(eliteTrailedSLLine) cs.removePriceLine(eliteTrailedSLLine);
  eliteTrailedSLLine=cs.createPriceLine({price, color:'#ff3b5c', lineWidth:2, lineStyle:0, axisLabelVisible:true, title:t('eliteTrailedSLTitle')});
 };
 window.valensClearEliteTrailedSL=function(){
  if(eliteTrailedSLLine){ cs.removePriceLine(eliteTrailedSLLine); eliteTrailedSLLine=null; }
 };
 // ---- KÂR KORUMA BİLDİRİMİ — kullanıcı isteği: "kâr koruma devreye girdiği zaman işlemi kâr
 // korumadan kapatıyoruz diye bildirim atsın". Sadece TAM OLARAK bu sebeple (mum-kapanış teyitli
 // kâr koruma çıkışı, bkz. getJustClosedCandlePrice) kapanan işlemlerde tetiklenir — TP'ye ulaşan
 // ya da orijinal risk stopuna takılan işlemler bu bildirimi tetiklemez, zaten kendi UI'ları var.
 function showKrToast(title, body){
  const el=document.getElementById('krToast');
  if(!el) return;
  document.getElementById('krToastTitle').textContent=title;
  document.getElementById('krToastBody').textContent=body;
  el.classList.add('show');
  clearTimeout(window.valensKrToastTimer);
  window.valensKrToastTimer=setTimeout(()=>{ el.classList.remove('show'); }, 7000);
 }
 window.valensShowProfitLockToast=function(sym, dir, usd){
  showKrToast(t('profitLockToastTitle'), t('profitLockToastBody')(sym.split(':').pop(), dir>0?'BUY':'SELL', usd));
 };
 // ---- Kademe 1 (risk azaltma) ve Kademe 2 (kâr kilidi ARMED) bildirimleri — kullanıcı isteği:
 // her iki kademede de "bunun bildirimini versin". Bu, işlem KAPANDIĞINDA çalan valensShowProfitLockToast'tan
 // FARKLI — bunlar stop AYARLANDIĞI anda (işlem henüz açık, sadece koruması değişti) tetiklenir.
 window.valensShowRiskReducedToast=function(sym, dir){
  showKrToast(t('riskReducedToastTitle'), t('riskReducedToastBody')(sym.split(':').pop(), dir>0?'BUY':'SELL'));
 };
 window.valensShowProfitLockArmedToast=function(sym, dir){
  showKrToast(t('profitLockArmedToastTitle'), t('profitLockArmedToastBody')(sym.split(':').pop(), dir>0?'BUY':'SELL'));
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
  // ---- (33)/(34) YENİ STRATEJİLER İÇİN: zaten çizili S/R seviyeleri + yapı bias'ı — window.valensChartRead
  // için AŞAĞIDA da kullanılacak, iki kez hesaplamamak için burada tek seferlik alınıyor.
  const structureBiasNow = detectSwingStructure(a, 60);
  const srLevelsForTags = {mainSup: nearMainSR.sup?nearMainSR.sup.hi:null, mainRes: nearMainSR.res?nearMainSR.res.lo:null,
    dynSup: (typeof sup==='number'&&isFinite(sup))?sup:null, dynRes: (typeof res==='number'&&isFinite(res))?res:null};
  const strategyTags = detectStrategyTags(a, {rsi:rsiReal, macd:macdReal, ema9:ema9Real, ema21:ema21Real, ema50:ema50Real, ema200:ema200Real, vwap:vwapReal, zones:zones, bollPct:bollPctReal!==null?bollPctReal:50, srBias:srBias, fibZone:fibZone, tradeDelta:(typeof currentTradeDelta==='function'?currentTradeDelta():null), srLevels:srLevelsForTags, structureBias:structureBiasNow});

  // ---- (m2cgen ile Python'dan JS'e otomatik uretilmis model - elle duzenlenmez) ----
  function valensConfidenceScore(input) {
      var var0;
      if (input[2] > 0.512388466754457) {
          if (input[5] > 67.99727885723505) {
              if (input[9] > 19.500000000000004) {
                  if (input[6] > 3.698631433228608) {
                      var0 = -0.6938404122390165;
                  } else {
                      var0 = -0.7118984664489201;
                  }
              } else {
                  if (input[9] > 10.500000000000002) {
                      var0 = -0.7168035392997327;
                  } else {
                      var0 = -0.7063120066227582;
                  }
              }
          } else {
              if (input[9] > 3.5000000000000004) {
                  if (input[3] > 1.0278550228976773) {
                      var0 = -0.741867490314392;
                  } else {
                      var0 = -0.7171157524094774;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var0 = -0.7327528593533079;
                  } else {
                      var0 = -0.6992103768144347;
                  }
              }
          }
      } else {
          if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] <= -0.15050731119406482) {
                  var0 = -0.7222338114608241;
              } else {
                  if (input[6] > 1.7728395881409191) {
                      var0 = -0.7195160521853513;
                  } else {
                      var0 = -0.6825310408706123;
                  }
              }
          } else {
              if (input[2] <= -0.9171433916024895) {
                  if (input[5] > 54.80963993439257) {
                      var0 = -0.7329812130655518;
                  } else {
                      var0 = -0.7097478524744693;
                  }
              } else {
                  if (input[5] <= -29.59449508597042) {
                      var0 = -0.6859995998201223;
                  } else {
                      var0 = -0.7044570997189099;
                  }
              }
          }
      }
      var var1;
      if (input[2] > 0.512388466754457) {
          if (input[5] > 67.99727885723505) {
              if (input[9] > 19.500000000000004) {
                  if (input[6] > 3.698631433228608) {
                      var1 = 0.01291643188919809;
                  } else {
                      var1 = -0.004184029936232672;
                  }
              } else {
                  if (input[9] > 10.500000000000002) {
                      var1 = -0.008866298946607086;
                  } else {
                      var1 = 0.0011290692639186967;
                  }
              }
          } else {
              if (input[10] > 1.5000000000000002) {
                  if (input[3] > 1.0278550228976773) {
                      var1 = -0.0209785909309506;
                  } else {
                      var1 = -0.002914434506216505;
                  }
              } else {
                  if (input[4] > 6.425942734112858) {
                      var1 = 0.00982737955232033;
                  } else {
                      var1 = -0.02138762250057396;
                  }
              }
          }
      } else {
          if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[9] > 14.500000000000002) {
                  var1 = -0.01932535345342761;
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var1 = -0.015925183817838494;
                  } else {
                      var1 = -0.00044679336103227896;
                  }
              }
          } else {
              if (input[2] <= -0.9347891751879592) {
                  if (input[5] > 54.80963993439257) {
                      var1 = -0.02476221278441252;
                  } else {
                      var1 = -0.002294225330926912;
                  }
              } else {
                  if (input[9] > 20.500000000000004) {
                      var1 = 0.008907275397076057;
                  } else {
                      var1 = 0.0022425233294833813;
                  }
              }
          }
      }
      var var2;
      if (input[2] > 0.562630170505321) {
          if (input[5] > 36.01432832743052) {
              if (input[2] > 1.103118178873732) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var2 = -0.016204757930663654;
                  } else {
                      var2 = -0.002871576582407267;
                  }
              } else {
                  if (input[10] > 3.5000000000000004) {
                      var2 = 0.003668955263878298;
                  } else {
                      var2 = -0.003884278439474029;
                  }
              }
          } else {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                      var2 = -0.050132247811160206;
                  } else {
                      var2 = -0.019971339148735584;
                  }
              } else {
                  if (input[4] > 0.44770045251324836) {
                      var2 = -0.011069710731149797;
                  } else {
                      var2 = 0.02870719628727847;
                  }
              }
          }
      } else {
          if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[0] > 30.828549176161413) {
                  var2 = -0.0035855357021364154;
              } else {
                  if (input[9] > 14.500000000000002) {
                      var2 = -0.025776755470522314;
                  } else {
                      var2 = -0.009656048885758273;
                  }
              }
          } else {
              if (input[5] <= -34.779391478962644) {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var2 = 0.05156196373717751;
                  } else {
                      var2 = 0.01036445119970426;
                  }
              } else {
                  if (input[2] <= -0.9171433916024895) {
                      var2 = -0.0037268312632264943;
                  } else {
                      var2 = 0.002662756746436606;
                  }
              }
          }
      }
      var var3;
      if (input[2] > 0.512388466754457) {
          if (input[5] > 67.99727885723505) {
              if (input[9] > 19.500000000000004) {
                  if (input[6] > 3.698631433228608) {
                      var3 = 0.01245826101885355;
                  } else {
                      var3 = -0.0038480024434142863;
                  }
              } else {
                  if (input[9] > 10.500000000000002) {
                      var3 = -0.008316757161515668;
                  } else {
                      var3 = 0.0012118468574449622;
                  }
              }
          } else {
              if (input[9] > 3.5000000000000004) {
                  if (input[3] > 1.0278550228976773) {
                      var3 = -0.032009744274537615;
                  } else {
                      var3 = -0.008550280328508518;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var3 = -0.023425445890344457;
                  } else {
                      var3 = 0.00856913654878833;
                  }
              }
          }
      } else {
          if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] <= -0.15050731119406482) {
                  var3 = -0.012994703324138544;
              } else {
                  if (input[6] > 1.7728395881409191) {
                      var3 = -0.010709701654094577;
                  } else {
                      var3 = 0.024506092688137665;
                  }
              }
          } else {
              if (input[2] <= -0.9171433916024895) {
                  if (input[5] > 43.83642014465365) {
                      var3 = -0.01715426349661169;
                  } else {
                      var3 = -0.0011092250043487591;
                  }
              } else {
                  if (input[9] > 20.500000000000004) {
                      var3 = 0.008255031514951747;
                  } else {
                      var3 = 0.002008675088220409;
                  }
              }
          }
      }
      var var4;
      if (input[2] > 0.7364344871303423) {
          if (input[5] > 35.25256113656712) {
              if (input[9] > 3.5000000000000004) {
                  if (input[5] > 70.6027148026618) {
                      var4 = -0.0029800210220675893;
                  } else {
                      var4 = -0.011800945394136467;
                  }
              } else {
                  if (input[4] <= -1.2057540353889575) {
                      var4 = 0.019781998371902657;
                  } else {
                      var4 = -0.0016450011988579768;
                  }
              }
          } else {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var4 = -0.05647141371963961;
                  } else {
                      var4 = -0.02240385650163203;
                  }
              } else {
                  var4 = -0.0009166094288765898;
              }
          }
      } else {
          if (input[2] <= -0.9171433916024895) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -5.20604877356585) {
                      var4 = -0.0006994397023598771;
                  } else {
                      var4 = -0.01906989870688031;
                  }
              } else {
                  if (input[7] <= -1.4999999999999998) {
                      var4 = -0.013507103241450873;
                  } else {
                      var4 = 0.006314028194348637;
                  }
              }
          } else {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -0.1375084104867184) {
                      var4 = 0.0015036644631935272;
                  } else {
                      var4 = 0.009957024815785517;
                  }
              } else {
                  if (input[5] <= -29.59449508597042) {
                      var4 = 0.015550043142723402;
                  } else {
                      var4 = 0.0005260790653462395;
                  }
              }
          }
      }
      var var5;
      if (input[2] > 0.512388466754457) {
          if (input[5] > 41.948811368473365) {
              if (input[4] > 1.140378700310803) {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var5 = 0.011127565729253018;
                  } else {
                      var5 = -0.002255494587541875;
                  }
              } else {
                  if (input[9] > 10.500000000000002) {
                      var5 = -0.011868032999666081;
                  } else {
                      var5 = 0.0012780987618172012;
                  }
              }
          } else {
              if (input[4] > 0.44770045251324836) {
                  if (input[10] > 2.5000000000000004) {
                      var5 = -0.03192357339793838;
                  } else {
                      var5 = -0.006034776708292555;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var5 = 0.038154276001742246;
                  } else {
                      var5 = -0.003249582587214115;
                  }
              }
          }
      } else {
          if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[9] > 14.500000000000002) {
                  var5 = -0.017133319560920603;
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var5 = -0.014296358817737298;
                  } else {
                      var5 = 0.0005452728313648687;
                  }
              }
          } else {
              if (input[5] <= -34.779391478962644) {
                  if (input[4] > 0.5754747040913045) {
                      var5 = 0.0005085944202040337;
                  } else {
                      var5 = 0.03808097164169226;
                  }
              } else {
                  if (input[6] <= -2.398066420549097) {
                      var5 = -0.0011670662501331497;
                  } else {
                      var5 = 0.0030917784104824222;
                  }
              }
          }
      }
      var var6;
      if (input[2] > 0.7364344871303423) {
          if (input[5] > 35.25256113656712) {
              if (input[9] > 3.5000000000000004) {
                  if (input[5] > 70.6027148026618) {
                      var6 = -0.0027032346777625185;
                  } else {
                      var6 = -0.01111288179071463;
                  }
              } else {
                  if (input[4] <= -1.2057540353889575) {
                      var6 = 0.018570718279623297;
                  } else {
                      var6 = -0.0014623404231253602;
                  }
              }
          } else {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var6 = -0.054493199283316;
                  } else {
                      var6 = -0.020617525964542745;
                  }
              } else {
                  var6 = -0.00032267280733240734;
              }
          }
      } else {
          if (input[2] <= -0.9171433916024895) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -5.20604877356585) {
                      var6 = -0.0005350572442407184;
                  } else {
                      var6 = -0.018113922745904277;
                  }
              } else {
                  if (input[5] > 19.14508537197081) {
                      var6 = 0.011327292663714877;
                  } else {
                      var6 = -0.005258496365061597;
                  }
              }
          } else {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -0.1375084104867184) {
                      var6 = 0.0013682341342743153;
                  } else {
                      var6 = 0.009336095046116832;
                  }
              } else {
                  if (input[0] > 67.17230718398928) {
                      var6 = 0.006328430322295718;
                  } else {
                      var6 = 0.000039817381942898765;
                  }
              }
          }
      }
      var var7;
      if (input[2] > 0.512388466754457) {
          if (input[0] > 52.06853502461072) {
              if (input[9] > 10.500000000000002) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var7 = 0.0022721026010666056;
                  } else {
                      var7 = -0.01086830467699545;
                  }
              } else {
                  if (input[0] > 52.89417697841084) {
                      var7 = 0.0007122299260352604;
                  } else {
                      var7 = 0.030258625607334562;
                  }
              }
          } else {
              if (input[4] <= -0.4950921444997715) {
                  if (input[5] > 43.306883112568904) {
                      var7 = -0.0074047044099994205;
                  } else {
                      var7 = 0.021276617085795924;
                  }
              } else {
                  if (input[6] > 7.999681113877577) {
                      var7 = 0.014228299721938651;
                  } else {
                      var7 = -0.01602487971391048;
                  }
              }
          }
      } else {
          if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[0] > 30.828549176161413) {
                  var7 = -0.002447183140626201;
              } else {
                  if (input[9] > 14.500000000000002) {
                      var7 = -0.023046002699561155;
                  } else {
                      var7 = -0.008038372401710464;
                  }
              }
          } else {
              if (input[5] <= -34.779391478962644) {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var7 = 0.04558972137486339;
                  } else {
                      var7 = 0.007423295874621582;
                  }
              } else {
                  if (input[6] > 2.5493545797764527) {
                      var7 = 0.006844576391705663;
                  } else {
                      var7 = 0.0008228699112885232;
                  }
              }
          }
      }
      var var8;
      if (input[2] > 0.7364344871303423) {
          if (input[6] > 0.9224363701183542) {
              if (input[5] > 35.25256113656712) {
                  if (input[6] > 3.42896965457881) {
                      var8 = -0.002272459250617855;
                  } else {
                      var8 = -0.010859545192443086;
                  }
              } else {
                  if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                      var8 = -0.037377638688596164;
                  } else {
                      var8 = -0.004920665889210462;
                  }
              }
          } else {
              if (input[9] > 8.500000000000002) {
                  var8 = -0.014210477868852274;
              } else {
                  var8 = 0.0397978968444016;
              }
          }
      } else {
          if (input[2] <= -0.9171433916024895) {
              if (input[9] > 12.500000000000002) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var8 = -0.015760638371836208;
                  } else {
                      var8 = -0.00195844728714747;
                  }
              } else {
                  if (input[5] > 43.83642014465365) {
                      var8 = -0.015426590262287366;
                  } else {
                      var8 = 0.004056988424405321;
                  }
              }
          } else {
              if (input[9] > 18.500000000000004) {
                  if (input[4] > 2.224830200500726) {
                      var8 = -0.003571262186304035;
                  } else {
                      var8 = 0.007799870845988999;
                  }
              } else {
                  if (input[9] > 3.5000000000000004) {
                      var8 = -0.00010585484506661396;
                  } else {
                      var8 = 0.005639779472229076;
                  }
              }
          }
      }
      var var9;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -2.4043400015638174) {
              if (input[6] <= -2.0836067860364804) {
                  if (input[2] <= -1.0417062803742494) {
                      var9 = 0.0049368509937155036;
                  } else {
                      var9 = -0.01876569921349823;
                  }
              } else {
                  var9 = 0.025902708403431007;
              }
          } else {
              if (input[4] > 2.5971341022699526) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var9 = 0.013616580819103441;
                  } else {
                      var9 = -0.006314746224885648;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var9 = -0.02458581832248707;
                  } else {
                      var9 = -0.011047278809333703;
                  }
              }
          }
      } else {
          if (input[2] > 0.3060340617918521) {
              if (input[9] > 20.500000000000004) {
                  if (input[2] > 0.3659824905916446) {
                      var9 = 0.0018796847139059003;
                  } else {
                      var9 = 0.0305353908281169;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var9 = 0.004922360201511683;
                  } else {
                      var9 = -0.0044231143113266855;
                  }
              }
          } else {
              if (input[6] > 2.2593951888407307) {
                  if (input[5] > 124.44714520731416) {
                      var9 = 0.04926014430275922;
                  } else {
                      var9 = 0.007398439945160668;
                  }
              } else {
                  if (input[5] <= -34.779391478962644) {
                      var9 = 0.02003728441361824;
                  } else {
                      var9 = 0.0009136345328715769;
                  }
              }
          }
      }
      var var10;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -2.4043400015638174) {
              if (input[6] <= -2.0836067860364804) {
                  if (input[2] <= -1.0417062803742494) {
                      var10 = 0.004681150050952181;
                  } else {
                      var10 = -0.017956338424300847;
                  }
              } else {
                  var10 = 0.02438836616003528;
              }
          } else {
              if (input[4] > 2.5971341022699526) {
                  if (input[3] > 0.7991209866534285) {
                      var10 = -0.008485067838567726;
                  } else {
                      var10 = 0.007744535307497952;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var10 = -0.02357689898962964;
                  } else {
                      var10 = -0.01053817213517186;
                  }
              }
          }
      } else {
          if (input[2] > 1.2449878458998531) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 19.500000000000004) {
                      var10 = -0.037194996626498646;
                  } else {
                      var10 = -0.015572274095163053;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var10 = 0.007905152565912893;
                  } else {
                      var10 = -0.012812367915718853;
                  }
              }
          } else {
              if (input[9] > 20.500000000000004) {
                  if (input[5] > 84.62477280480881) {
                      var10 = 0.01827586856733817;
                  } else {
                      var10 = 0.0032179165401061867;
                  }
              } else {
                  if (input[9] > 3.5000000000000004) {
                      var10 = -0.0006943530780135882;
                  } else {
                      var10 = 0.005494477780254926;
                  }
              }
          }
      }
      var var11;
      if (input[2] > 0.3060340617918521) {
          if (input[6] <= -2.0836067860364804) {
              if (input[9] > 6.500000000000001) {
                  var11 = -0.03577642003309418;
              } else {
                  var11 = -0.008804846750181604;
              }
          } else {
              if (input[9] > 20.500000000000004) {
                  if (input[2] > 0.3659824905916446) {
                      var11 = 0.0016979065610898466;
                  } else {
                      var11 = 0.026878350877521412;
                  }
              } else {
                  if (input[9] > 10.500000000000002) {
                      var11 = -0.005697827777985604;
                  } else {
                      var11 = -0.0006578619352968528;
                  }
              }
          }
      } else {
          if (input[2] <= -0.17292263602242408) {
              if (input[0] > 64.75395318316197) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var11 = -0.03621876357066881;
                  } else {
                      var11 = -0.01235489626366121;
                  }
              } else {
                  if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                      var11 = -0.009230916151404511;
                  } else {
                      var11 = 0.00062751405332501;
                  }
              }
          } else {
              if (input[10] > 3.5000000000000004) {
                  if (input[2] > 0.032630134189059835) {
                      var11 = -0.00631885736526994;
                  } else {
                      var11 = 0.005920984442925244;
                  }
              } else {
                  if (input[6] > 2.96096381512298) {
                      var11 = 0.020884598177305817;
                  } else {
                      var11 = 0.005024048412967237;
                  }
              }
          }
      }
      var var12;
      if (input[2] > 0.7364344871303423) {
          if (input[6] > 0.9224363701183542) {
              if (input[5] > 35.25256113656712) {
                  if (input[6] > 3.4821968878924623) {
                      var12 = -0.0017047477769926035;
                  } else {
                      var12 = -0.009954071471128367;
                  }
              } else {
                  if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                      var12 = -0.03581064161417563;
                  } else {
                      var12 = -0.004393444233368973;
                  }
              }
          } else {
              if (input[9] > 8.500000000000002) {
                  var12 = -0.013421421336121661;
              } else {
                  var12 = 0.03742950359712028;
              }
          }
      } else {
          if (input[2] <= -0.9171433916024895) {
              if (input[5] > 54.80963993439257) {
                  if (input[13] > 8.500000000000002) {
                      var12 = 0.01339286256921646;
                  } else {
                      var12 = -0.03887711251904081;
                  }
              } else {
                  if (input[4] <= -4.21670651579148) {
                      var12 = 0.006944111300257249;
                  } else {
                      var12 = -0.005533290537585501;
                  }
              }
          } else {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -0.1375084104867184) {
                      var12 = 0.0011228870118451927;
                  } else {
                      var12 = 0.008321648005706202;
                  }
              } else {
                  if (input[0] > 67.17230718398928) {
                      var12 = 0.005803487737140185;
                  } else {
                      var12 = -0.0001636787279874135;
                  }
              }
          }
      }
      var var13;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 8.627739511800717) {
              var13 = 0.017468357073715322;
          } else {
              if (input[4] <= -2.4043400015638174) {
                  if (input[6] <= -2.0836067860364804) {
                      var13 = -0.006551362088068439;
                  } else {
                      var13 = 0.023811343575993876;
                  }
              } else {
                  if (input[2] <= -1.1384490160854523) {
                      var13 = -0.02464917201097513;
                  } else {
                      var13 = -0.007928080263279296;
                  }
              }
          }
      } else {
          if (input[2] > 1.103118178873732) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var13 = -0.03682888518634761;
                  } else {
                      var13 = -0.01234089340878427;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var13 = 0.007761838425248535;
                  } else {
                      var13 = -0.010451824686423875;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var13 = 0.03312480309885491;
              } else {
                  if (input[5] <= -34.779391478962644) {
                      var13 = 0.019149674527970215;
                  } else {
                      var13 = 0.000653733885165448;
                  }
              }
          }
      }
      var var14;
      if (input[2] > 0.3060340617918521) {
          if (input[6] <= -2.0836067860364804) {
              if (input[9] > 6.500000000000001) {
                  var14 = -0.03449574294293469;
              } else {
                  var14 = -0.008728083026333372;
              }
          } else {
              if (input[9] > 20.500000000000004) {
                  if (input[2] > 0.3659824905916446) {
                      var14 = 0.0017298860265253816;
                  } else {
                      var14 = 0.02514562255366175;
                  }
              } else {
                  if (input[9] > 10.500000000000002) {
                      var14 = -0.005351116072040844;
                  } else {
                      var14 = -0.0005411274414884194;
                  }
              }
          }
      } else {
          if (input[6] > 2.2593951888407307) {
              if (input[13] > 1.5000000000000002) {
                  if (input[4] > 2.0913098704508557) {
                      var14 = 0.006015913674189021;
                  } else {
                      var14 = 0.021424500956114433;
                  }
              } else {
                  if (input[3] > 0.06654748911058106) {
                      var14 = 0.001141994007514065;
                  } else {
                      var14 = -0.02915394563010487;
                  }
              }
          } else {
              if (input[4] > 5.857188587559812) {
                  if (input[9] > 4.500000000000001) {
                      var14 = 0.007389490976738685;
                  } else {
                      var14 = 0.03509485145946631;
                  }
              } else {
                  if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                      var14 = -0.008342161902166622;
                  } else {
                      var14 = 0.0007477278687689571;
                  }
              }
          }
      }
      var var15;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[2] <= -1.005074921462989) {
                  if (input[4] <= -4.21670651579148) {
                      var15 = 0.007448159978013038;
                  } else {
                      var15 = -0.01057045467845636;
                  }
              } else {
                  if (input[2] > 0.7872055857050603) {
                      var15 = -0.004520015414882005;
                  } else {
                      var15 = 0.001811395536994329;
                  }
              }
          } else {
              if (input[13] > 9.500000000000002) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var15 = -0.021675538091374427;
                  } else {
                      var15 = -0.005682597975690304;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var15 = -0.006894670906925443;
                  } else {
                      var15 = 0.000006416483144984331;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  var15 = -0.02483141568729031;
              } else {
                  if (input[4] > 2.2673368930640305) {
                      var15 = 0.007865458246077666;
                  } else {
                      var15 = -0.004947762964162458;
                  }
              }
          } else {
              if (input[4] <= -0.34936199502367266) {
                  if (input[2] > 1.066088040180986) {
                      var15 = 0.0636540299304172;
                  } else {
                      var15 = 0.016927859650533214;
                  }
              } else {
                  if (input[6] > 8.281812040067665) {
                      var15 = 0.02786145598560962;
                  } else {
                      var15 = 0.0009411433061254596;
                  }
              }
          }
      }
      var var16;
      if (input[2] > 0.3060340617918521) {
          if (input[0] > 55.71689369569628) {
              if (input[6] <= -2.282378601683849) {
                  var16 = -0.02622028044945652;
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var16 = -0.004304475139572252;
                  } else {
                      var16 = 0.001595588733965119;
                  }
              }
          } else {
              if (input[4] <= -0.19071640176439533) {
                  if (input[5] > 42.90242520060247) {
                      var16 = -0.006249383734729309;
                  } else {
                      var16 = 0.017668391321473905;
                  }
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var16 = -0.01403701214725074;
                  } else {
                      var16 = -0.0017430544560012142;
                  }
              }
          }
      } else {
          if (input[6] > 2.2593951888407307) {
              if (input[13] > 1.5000000000000002) {
                  if (input[4] > 2.0913098704508557) {
                      var16 = 0.005666927140686657;
                  } else {
                      var16 = 0.020213368822416214;
                  }
              } else {
                  if (input[3] > 0.06654748911058106) {
                      var16 = 0.0010291163184117317;
                  } else {
                      var16 = -0.02800600869125073;
                  }
              }
          } else {
              if (input[4] > 5.857188587559812) {
                  if (input[9] > 4.500000000000001) {
                      var16 = 0.0070378719488430235;
                  } else {
                      var16 = 0.03281443734675338;
                  }
              } else {
                  if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                      var16 = -0.007876031757982262;
                  } else {
                      var16 = 0.0006966338045244685;
                  }
              }
          }
      }
      var var17;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[2] <= -1.005074921462989) {
                  if (input[4] <= -4.21670651579148) {
                      var17 = 0.007067790181767725;
                  } else {
                      var17 = -0.010069584886881262;
                  }
              } else {
                  if (input[2] > 0.7872055857050603) {
                      var17 = -0.0042478195467004175;
                  } else {
                      var17 = 0.0017069736331381284;
                  }
              }
          } else {
              if (input[13] > 9.500000000000002) {
                  if (input[5] <= -4.036293855178701) {
                      var17 = -0.035292760812040934;
                  } else {
                      var17 = -0.008170121807428746;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var17 = -0.006555019742431569;
                  } else {
                      var17 = 0.000014524949291868832;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  var17 = -0.023803706981768584;
              } else {
                  if (input[4] > 2.2673368930640305) {
                      var17 = 0.007421952217843243;
                  } else {
                      var17 = -0.004700404435373963;
                  }
              }
          } else {
              if (input[4] <= -0.34936199502367266) {
                  if (input[2] > 1.066088040180986) {
                      var17 = 0.05928952145202951;
                  } else {
                      var17 = 0.015957678208915936;
                  }
              } else {
                  if (input[6] > 8.281812040067665) {
                      var17 = 0.026309617726802615;
                  } else {
                      var17 = 0.000898340115376184;
                  }
              }
          }
      }
      var var18;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -2.4043400015638174) {
              if (input[6] <= -2.0836067860364804) {
                  if (input[9] > 15.500000000000002) {
                      var18 = -0.02303585097569665;
                  } else {
                      var18 = 0.0018710140106013918;
                  }
              } else {
                  var18 = 0.020974007662981985;
              }
          } else {
              if (input[4] > 2.5971341022699526) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var18 = 0.01390229595477651;
                  } else {
                      var18 = -0.00532879514388971;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var18 = -0.021269493183144944;
                  } else {
                      var18 = -0.008861017628164698;
                  }
              }
          }
      } else {
          if (input[2] > 1.2449878458998531) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 19.500000000000004) {
                      var18 = -0.034611725001156064;
                  } else {
                      var18 = -0.013787871032650093;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var18 = 0.0077196812131102065;
                  } else {
                      var18 = -0.011501091703386167;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var18 = 0.02925389087022226;
              } else {
                  if (input[5] <= -34.779391478962644) {
                      var18 = 0.01783231850270623;
                  } else {
                      var18 = 0.0004984077901380341;
                  }
              }
          }
      }
      var var19;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 20.500000000000004) {
              if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                  var19 = 0.03206734959950084;
              } else {
                  if (input[5] > 84.62477280480881) {
                      var19 = 0.013121138270288058;
                  } else {
                      var19 = 0.0010687223982932504;
                  }
              }
          } else {
              if (input[2] > 0.7364344871303423) {
                  if (input[7] > 1.5000000000000002) {
                      var19 = 0.0031245029214299795;
                  } else {
                      var19 = -0.0072767559217390065;
                  }
              } else {
                  if (input[6] > 2.2593951888407307) {
                      var19 = 0.0036958906943500847;
                  } else {
                      var19 = -0.0014038073044209884;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var19 = -0.005009494118781797;
                  } else {
                      var19 = -0.03395016369290547;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var19 = 0.007285029114728745;
                  } else {
                      var19 = -0.004806177452107471;
                  }
              }
          } else {
              if (input[4] <= -0.34936199502367266) {
                  if (input[3] > 0.9234434448483347) {
                      var19 = 0.049335362410210706;
                  } else {
                      var19 = 0.014384339058567848;
                  }
              } else {
                  if (input[4] > 4.047127624433007) {
                      var19 = 0.010418362924416039;
                  } else {
                      var19 = -0.002613219232043904;
                  }
              }
          }
      }
      var var20;
      if (input[2] > 0.3060340617918521) {
          if (input[6] <= -2.0836067860364804) {
              if (input[9] > 6.500000000000001) {
                  var20 = -0.032821363046988745;
              } else {
                  var20 = -0.008193051821466303;
              }
          } else {
              if (input[0] > 55.71689369569628) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var20 = -0.003935651124429777;
                  } else {
                      var20 = 0.0015974439128122284;
                  }
              } else {
                  if (input[4] <= -0.6688301121124586) {
                      var20 = 0.005349314447911339;
                  } else {
                      var20 = -0.007743155106689748;
                  }
              }
          }
      } else {
          if (input[2] <= -0.17292263602242408) {
              if (input[0] > 64.75395318316197) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var20 = -0.034957039141077555;
                  } else {
                      var20 = -0.011870795483904215;
                  }
              } else {
                  if (input[4] <= -2.0004379047689356) {
                      var20 = 0.0027020261339901035;
                  } else {
                      var20 = -0.0019991344504059964;
                  }
              }
          } else {
              if (input[6] <= -4.096403012396194) {
                  if (input[3] > 0.07301218741877412) {
                      var20 = 0.007192745247861077;
                  } else {
                      var20 = 0.03834653103428183;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var20 = 0.007266592737068984;
                  } else {
                      var20 = 0.0004314769232151041;
                  }
              }
          }
      }
      var var21;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 8.627739511800717) {
              var21 = 0.016119596889616977;
          } else {
              if (input[4] <= -2.4043400015638174) {
                  if (input[3] > 0.7342584171049911) {
                      var21 = 0.027584682126073685;
                  } else {
                      var21 = -0.003102778143581463;
                  }
              } else {
                  if (input[4] > 3.157487598233804) {
                      var21 = -0.0014085728359193056;
                  } else {
                      var21 = -0.010691345120397901;
                  }
              }
          }
      } else {
          if (input[5] <= -34.779391478962644) {
              if (input[4] > 0.5754747040913045) {
                  var21 = -0.004033632303410457;
              } else {
                  if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                      var21 = 0.04063228405628658;
                  } else {
                      var21 = 0.023155895310959015;
                  }
              }
          } else {
              if (input[9] > 20.500000000000004) {
                  if (input[5] > 84.62477280480881) {
                      var21 = 0.015014895596074874;
                  } else {
                      var21 = 0.002167667943211963;
                  }
              } else {
                  if (input[9] > 3.5000000000000004) {
                      var21 = -0.0011382943929178781;
                  } else {
                      var21 = 0.003806896810965041;
                  }
              }
          }
      }
      var var22;
      if (input[2] > 0.3060340617918521) {
          if (input[6] <= -2.0836067860364804) {
              if (input[9] > 6.500000000000001) {
                  var22 = -0.0316136359304035;
              } else {
                  var22 = -0.007864013669358237;
              }
          } else {
              if (input[0] > 55.71689369569628) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var22 = -0.00375334130232781;
                  } else {
                      var22 = 0.0015132841743010677;
                  }
              } else {
                  if (input[4] <= -0.6688301121124586) {
                      var22 = 0.005060989837071986;
                  } else {
                      var22 = -0.007380320918518485;
                  }
              }
          }
      } else {
          if (input[2] > 0.2831395178635617) {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  var22 = 0.04587143332470714;
              } else {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var22 = 0.030557862420144438;
                  } else {
                      var22 = 0.0017931962948783402;
                  }
              }
          } else {
              if (input[4] > 5.535696777028553) {
                  if (input[0] > 52.55175265198409) {
                      var22 = 0.02885277321811529;
                  } else {
                      var22 = 0.005606097621251288;
                  }
              } else {
                  if (input[5] > 128.04227788475038) {
                      var22 = 0.019482728571777942;
                  } else {
                      var22 = 0.00027354336493400284;
                  }
              }
          }
      }
      var var23;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 8.627739511800717) {
              var23 = 0.015208574623607736;
          } else {
              if (input[4] <= -2.4043400015638174) {
                  if (input[6] <= -2.0836067860364804) {
                      var23 = -0.005029293785617649;
                  } else {
                      var23 = 0.019218262351343336;
                  }
              } else {
                  if (input[2] <= -1.1384490160854523) {
                      var23 = -0.021432329210361544;
                  } else {
                      var23 = -0.006461013466282907;
                  }
              }
          }
      } else {
          if (input[2] > 1.2449878458998531) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 19.500000000000004) {
                      var23 = -0.033191878388219964;
                  } else {
                      var23 = -0.012745039004440515;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var23 = 0.0073536610876317205;
                  } else {
                      var23 = -0.010987687347103495;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var23 = 0.027509033412138076;
              } else {
                  if (input[5] <= -34.779391478962644) {
                      var23 = 0.015867099923845756;
                  } else {
                      var23 = 0.00045609658964484144;
                  }
              }
          }
      }
      var var24;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[2] <= -1.1180532839378696) {
                  if (input[4] <= -4.21670651579148) {
                      var24 = 0.006049310241646068;
                  } else {
                      var24 = -0.011105497239160352;
                  }
              } else {
                  if (input[3] > 0.7461525345222845) {
                      var24 = -0.0036653525531555285;
                  } else {
                      var24 = 0.0014251162890655021;
                  }
              }
          } else {
              if (input[13] > 9.500000000000002) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var24 = -0.020294154273919004;
                  } else {
                      var24 = -0.004647970632772093;
                  }
              } else {
                  if (input[3] <= -0.9691031693117881) {
                      var24 = 0.007038731390132953;
                  } else {
                      var24 = -0.0034761306956729954;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  var24 = -0.022038473534299417;
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var24 = 0.006720382161170934;
                  } else {
                      var24 = -0.004700690594463036;
                  }
              }
          } else {
              if (input[4] <= -0.34936199502367266) {
                  if (input[2] > 1.066088040180986) {
                      var24 = 0.05236616728967497;
                  } else {
                      var24 = 0.013767311681807982;
                  }
              } else {
                  if (input[0] > 56.207921219246124) {
                      var24 = -0.005218368891186577;
                  } else {
                      var24 = 0.00772424133902796;
                  }
              }
          }
      }
      var var25;
      if (input[9] > 20.500000000000004) {
          if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
              var25 = 0.02983043607353025;
          } else {
              if (input[5] > 84.62477280480881) {
                  if (input[3] > 0.4535255126752083) {
                      var25 = 0.0024118492637250125;
                  } else {
                      var25 = 0.02673206768750519;
                  }
              } else {
                  if (input[5] <= -7.578872429369199) {
                      var25 = 0.023515850450276096;
                  } else {
                      var25 = 0.0003626349354418273;
                  }
              }
          }
      } else {
          if (input[9] > 3.5000000000000004) {
              if (input[2] > 0.7364344871303423) {
                  if (input[13] > 1.5000000000000002) {
                      var25 = -0.006254436791539539;
                  } else {
                      var25 = 0.006503369957014434;
                  }
              } else {
                  if (input[6] > 2.2593951888407307) {
                      var25 = 0.0036224993776899023;
                  } else {
                      var25 = -0.0013351439473372434;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                      var25 = -0.021111225548495583;
                  } else {
                      var25 = -0.0008080179969817655;
                  }
              } else {
                  if (input[4] <= -0.34936199502367266) {
                      var25 = 0.01567383291160708;
                  } else {
                      var25 = 0.002439550440935303;
                  }
              }
          }
      }
      var var26;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 8.627739511800717) {
              var26 = 0.01470840038682156;
          } else {
              if (input[4] <= -2.4043400015638174) {
                  if (input[3] > 0.7342584171049911) {
                      var26 = 0.0243158809624339;
                  } else {
                      var26 = -0.0029140279637575174;
                  }
              } else {
                  if (input[4] > 2.5971341022699526) {
                      var26 = -0.0018229537198147185;
                  } else {
                      var26 = -0.010249312820534349;
                  }
              }
          }
      } else {
          if (input[2] > 1.2449878458998531) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 19.500000000000004) {
                      var26 = -0.03182334122435857;
                  } else {
                      var26 = -0.012013506422755022;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var26 = 0.007376142864104406;
                  } else {
                      var26 = -0.010298701960676384;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var26 = 0.02586839313050049;
              } else {
                  if (input[5] <= -34.779391478962644) {
                      var26 = 0.014949001063938552;
                  } else {
                      var26 = 0.0004144026328388395;
                  }
              }
          }
      }
      var var27;
      if (input[9] > 20.500000000000004) {
          if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[2] <= -0.43692512381129284) {
                  if (input[5] > 39.68230743130311) {
                      var27 = -0.030499027170862388;
                  } else {
                      var27 = 0.00028984493825326624;
                  }
              } else {
                  if (input[4] <= -0.31292209129263854) {
                      var27 = 0.020640932495144856;
                  } else {
                      var27 = 0.0064117511099226025;
                  }
              }
          } else {
              if (input[4] > 3.4698611223847746) {
                  if (input[6] > 3.698631433228608) {
                      var27 = 0.005527751937046409;
                  } else {
                      var27 = -0.03546176373609007;
                  }
              } else {
                  var27 = 0.0018107928852528399;
              }
          }
      } else {
          if (input[9] > 3.5000000000000004) {
              if (input[2] > 0.7364344871303423) {
                  if (input[13] > 1.5000000000000002) {
                      var27 = -0.005898188518863364;
                  } else {
                      var27 = 0.006223040775511808;
                  }
              } else {
                  if (input[6] > 2.2593951888407307) {
                      var27 = 0.003419654773746306;
                  } else {
                      var27 = -0.0012844992844094996;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                      var27 = -0.020236833418656987;
                  } else {
                      var27 = -0.0007770307350406508;
                  }
              } else {
                  if (input[4] <= -0.34936199502367266) {
                      var27 = 0.01479684742781329;
                  } else {
                      var27 = 0.0023668203042213937;
                  }
              }
          }
      }
      var var28;
      if (input[2] > 0.3060340617918521) {
          if (input[0] > 55.71689369569628) {
              if (input[4] > 0.9187848953214247) {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var28 = 0.015005801276529824;
                  } else {
                      var28 = -0.0003016229743290297;
                  }
              } else {
                  if (input[13] > 3.5000000000000004) {
                      var28 = -0.006061624753183503;
                  } else {
                      var28 = 0.00639735308387485;
                  }
              }
          } else {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 9.500000000000002) {
                      var28 = -0.0224989393264424;
                  } else {
                      var28 = 0.021121728529684247;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var28 = 0.010583935462435122;
                  } else {
                      var28 = -0.008038633787548516;
                  }
              }
          }
      } else {
          if (input[2] > 0.2831395178635617) {
              if (input[10] > 3.5000000000000004) {
                  var28 = -0.005916894948065928;
              } else {
                  if (input[9] > 18.500000000000004) {
                      var28 = 0.006113545888630848;
                  } else {
                      var28 = 0.03245728195611349;
                  }
              }
          } else {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                      var28 = 0.024011233420495864;
                  } else {
                      var28 = 0.002430616872550293;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var28 = -0.002439112816594115;
                  } else {
                      var28 = 0.0016468176703810103;
                  }
              }
          }
      }
      var var29;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 8.627739511800717) {
              var29 = 0.014044870273030875;
          } else {
              if (input[4] <= -2.4043400015638174) {
                  if (input[0] > 27.469470602855804) {
                      var29 = 0.00986754854691779;
                  } else {
                      var29 = -0.010223634608815098;
                  }
              } else {
                  if (input[4] > 3.157487598233804) {
                      var29 = -0.0006994053566562877;
                  } else {
                      var29 = -0.009217059897314804;
                  }
              }
          }
      } else {
          if (input[5] > 139.46276228269554) {
              var29 = 0.021616780914729565;
          } else {
              if (input[2] > 1.2449878458998531) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var29 = -0.015703334486064587;
                  } else {
                      var29 = -0.0016616624745500897;
                  }
              } else {
                  if (input[4] > 9.401150856775486) {
                      var29 = 0.0243348749865107;
                  } else {
                      var29 = 0.0004223862979325771;
                  }
              }
          }
      }
      var var30;
      if (input[9] > 20.500000000000004) {
          if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
              var30 = 0.027952591337196603;
          } else {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -0.43692512381129284) {
                      var30 = -0.006963995513586525;
                  } else {
                      var30 = 0.010268074390177314;
                  }
              } else {
                  if (input[4] > 3.4698611223847746) {
                      var30 = -0.01292357402591058;
                  } else {
                      var30 = 0.001038325821093775;
                  }
              }
          }
      } else {
          if (input[9] > 3.5000000000000004) {
              if (input[2] > 0.7364344871303423) {
                  if (input[5] > 66.73316550839907) {
                      var30 = -0.0023227474772640846;
                  } else {
                      var30 = -0.010437858755225658;
                  }
              } else {
                  if (input[6] > 2.2593951888407307) {
                      var30 = 0.00323562890233923;
                  } else {
                      var30 = -0.0012434755682293889;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                      var30 = -0.01933664747285218;
                  } else {
                      var30 = -0.0006784852414465769;
                  }
              } else {
                  if (input[4] <= -0.34936199502367266) {
                      var30 = 0.013951972501562316;
                  } else {
                      var30 = 0.0022682892476757793;
                  }
              }
          }
      }
      var var31;
      if (input[2] > 0.3060340617918521) {
          if (input[6] <= -2.0836067860364804) {
              if (input[9] > 6.500000000000001) {
                  var31 = -0.03033864724491461;
              } else {
                  var31 = -0.008041024916051078;
              }
          } else {
              if (input[0] > 55.71689369569628) {
                  if (input[4] > 0.9187848953214247) {
                      var31 = 0.0020560887601468593;
                  } else {
                      var31 = -0.0027177546208724764;
                  }
              } else {
                  if (input[4] <= -0.19071640176439533) {
                      var31 = 0.004123955380137215;
                  } else {
                      var31 = -0.007031400511565297;
                  }
              }
          }
      } else {
          if (input[4] > 5.535696777028553) {
              if (input[5] > 70.22554774806824) {
                  var31 = 0.03388955774644969;
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var31 = -0.007125165363595507;
                  } else {
                      var31 = 0.01807494678879894;
                  }
              }
          } else {
              if (input[5] > 124.44714520731416) {
                  if (input[4] > 1.0583312261104756) {
                      var31 = 0.050069602398398944;
                  } else {
                      var31 = 0.00022588122447266676;
                  }
              } else {
                  if (input[7] > 1.5000000000000002) {
                      var31 = 0.017834295056243735;
                  } else {
                      var31 = 0.0002073106198959679;
                  }
              }
          }
      }
      var var32;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 8.627739511800717) {
              var32 = 0.01323661342805346;
          } else {
              if (input[4] <= -2.4043400015638174) {
                  if (input[3] > 0.7342584171049911) {
                      var32 = 0.022317357223447125;
                  } else {
                      var32 = -0.002656265638602183;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var32 = -0.014151474676878282;
                  } else {
                      var32 = -0.004610407411019413;
                  }
              }
          }
      } else {
          if (input[5] <= -34.779391478962644) {
              if (input[4] > 0.5754747040913045) {
                  var32 = -0.005641291411961794;
              } else {
                  if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                      var32 = 0.03562567111145542;
                  } else {
                      var32 = 0.020107011304083395;
                  }
              }
          } else {
              if (input[9] > 20.500000000000004) {
                  if (input[5] > 96.12555884548514) {
                      var32 = 0.01824022133676986;
                  } else {
                      var32 = 0.0022299072050100464;
                  }
              } else {
                  if (input[9] > 3.5000000000000004) {
                      var32 = -0.0009434908995730971;
                  } else {
                      var32 = 0.0030084371655356643;
                  }
              }
          }
      }
      var var33;
      if (input[2] > 0.3060340617918521) {
          if (input[6] <= -2.0836067860364804) {
              if (input[9] > 6.500000000000001) {
                  var33 = -0.029184300716973567;
              } else {
                  var33 = -0.007706562490938648;
              }
          } else {
              if (input[6] <= -0.7551169883193741) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var33 = -0.00700382325238244;
                  } else {
                      var33 = 0.019872765526048514;
                  }
              } else {
                  if (input[5] > 68.73201742693793) {
                      var33 = 0.0003405443523204889;
                  } else {
                      var33 = -0.0043609426982587456;
                  }
              }
          }
      } else {
          if (input[2] > 0.2831395178635617) {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  var33 = 0.04128995757110322;
              } else {
                  if (input[0] > 47.40082564351635) {
                      var33 = 0.013016716272672558;
                  } else {
                      var33 = -0.013749815600621213;
                  }
              }
          } else {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -0.7082825918688609) {
                      var33 = -0.005091572058247557;
                  } else {
                      var33 = 0.0048901026862056725;
                  }
              } else {
                  if (input[5] > 39.27720535678106) {
                      var33 = -0.0029567152239402712;
                  } else {
                      var33 = 0.001195513241467533;
                  }
              }
          }
      }
      var var34;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 5.595339644259805) {
              if (input[0] > 67.17230718398928) {
                  if (input[0] > 82.69759813776353) {
                      var34 = 0.01745691075928676;
                  } else {
                      var34 = -0.006908137326224343;
                  }
              } else {
                  var34 = 0.021254092651116174;
              }
          } else {
              if (input[6] > 4.075584176062313) {
                  if (input[4] > 2.420982285794383) {
                      var34 = -0.0035016238122649135;
                  } else {
                      var34 = -0.023552867467790103;
                  }
              } else {
                  if (input[2] > 1.049554179207316) {
                      var34 = 0.012427332493373333;
                  } else {
                      var34 = -0.004410912033720965;
                  }
              }
          }
      } else {
          if (input[5] > 139.46276228269554) {
              var34 = 0.019901042345456824;
          } else {
              if (input[5] <= -34.779391478962644) {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var34 = 0.03427524409225834;
                  } else {
                      var34 = 0.001495888804032121;
                  }
              } else {
                  if (input[9] > 20.500000000000004) {
                      var34 = 0.002957238389570544;
                  } else {
                      var34 = -0.0003960183955306676;
                  }
              }
          }
      }
      var var35;
      if (input[2] > 1.2449878458998531) {
          if (input[6] > 8.627739511800717) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  var35 = -0.011211316236322755;
              } else {
                  if (input[4] > 6.290654712658461) {
                      var35 = 0.027531641774870143;
                  } else {
                      var35 = 0.0038289544455607748;
                  }
              }
          } else {
              if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] > 1.499734792503489) {
                      var35 = 0.030217813340274263;
                  } else {
                      var35 = -0.025917416734863166;
                  }
              } else {
                  if (input[4] <= -1.9591388388858506) {
                      var35 = 0.02279532740778181;
                  } else {
                      var35 = -0.012549205011197162;
                  }
              }
          }
      } else {
          if (input[4] > 9.401150856775486) {
              var35 = 0.020740881980957245;
          } else {
              if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 5.434251947010837) {
                      var35 = 0.003933396160710638;
                  } else {
                      var35 = -0.005330633988849597;
                  }
              } else {
                  if (input[0] > 75.52030211082776) {
                      var35 = 0.006599184548295602;
                  } else {
                      var35 = 0.00019917683065009273;
                  }
              }
          }
      }
      var var36;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[2] <= -1.005074921462989) {
                  if (input[4] <= -4.21670651579148) {
                      var36 = 0.006551272396021703;
                  } else {
                      var36 = -0.00883143979837507;
                  }
              } else {
                  if (input[2] > 0.025809299484776383) {
                      var36 = -0.0009146705717858975;
                  } else {
                      var36 = 0.002615786253105353;
                  }
              }
          } else {
              if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[8] > 0.000000000000000000000000000000000010000000180025095) {
                      var36 = 0.019748726601401312;
                  } else {
                      var36 = -0.008257956929938573;
                  }
              } else {
                  if (input[9] > 5.500000000000001) {
                      var36 = -0.005693313822506639;
                  } else {
                      var36 = 0.003812004705034413;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] <= -6.382133466621322) {
                      var36 = -0.025655907258222657;
                  } else {
                      var36 = 0.00845785321175587;
                  }
              } else {
                  var36 = -0.005741150000787322;
              }
          } else {
              if (input[13] > 8.500000000000002) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var36 = 0.024581305582625355;
                  } else {
                      var36 = 0.008859203873263645;
                  }
              } else {
                  if (input[0] > 68.79176196941201) {
                      var36 = -0.011533278854273854;
                  } else {
                      var36 = 0.005610309161956678;
                  }
              }
          }
      }
      var var37;
      if (input[5] > 117.01558275614404) {
          if (input[4] <= -1.1719718718623295) {
              if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                  var37 = 0.018330327624225047;
              } else {
                  if (input[2] > 0.2831395178635617) {
                      var37 = -0.00526538502104283;
                  } else {
                      var37 = -0.02852700566723268;
                  }
              }
          } else {
              if (input[2] > 0.3575210933481173) {
                  if (input[2] > 0.493948739122735) {
                      var37 = 0.007249481646208188;
                  } else {
                      var37 = -0.013302771169153078;
                  }
              } else {
                  if (input[6] > 3.535515966166679) {
                      var37 = 0.04625034809198584;
                  } else {
                      var37 = 0.01443677673266288;
                  }
              }
          }
      } else {
          if (input[2] > 1.2449878458998531) {
              if (input[5] > 60.200564877650486) {
                  if (input[6] > 4.015152789582986) {
                      var37 = -0.0006075375208423404;
                  } else {
                      var37 = -0.023092796442108637;
                  }
              } else {
                  if (input[3] > 1.0278550228976773) {
                      var37 = -0.02664098798718985;
                  } else {
                      var37 = -0.0022335596374978644;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var37 = 0.01997247668667537;
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var37 = -0.0022807769561250884;
                  } else {
                      var37 = 0.0004904507445787908;
                  }
              }
          }
      }
      var var38;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[2] <= -1.1180532839378696) {
                  if (input[9] > 14.500000000000002) {
                      var38 = -0.011731738223543859;
                  } else {
                      var38 = 0.002627690603546026;
                  }
              } else {
                  if (input[3] > 0.14193601830092184) {
                      var38 = -0.0011655487498310015;
                  } else {
                      var38 = 0.002031054511600966;
                  }
              }
          } else {
              if (input[13] > 9.500000000000002) {
                  if (input[5] <= -4.036293855178701) {
                      var38 = -0.03323163212441207;
                  } else {
                      var38 = -0.00650534108038721;
                  }
              } else {
                  if (input[6] <= -1.2732214212272153) {
                      var38 = -0.005727161173161862;
                  } else {
                      var38 = 0.000853058703691983;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  var38 = -0.018514070876485402;
              } else {
                  if (input[4] > 2.2673368930640305) {
                      var38 = 0.007039772118743419;
                  } else {
                      var38 = -0.004316756338935318;
                  }
              }
          } else {
              if (input[4] <= -0.34936199502367266) {
                  if (input[3] > 0.9933024328533363) {
                      var38 = 0.044273791706579774;
                  } else {
                      var38 = 0.009714415602318817;
                  }
              } else {
                  if (input[6] > 8.281812040067665) {
                      var38 = 0.023758952593523328;
                  } else {
                      var38 = 0.00013947337111968168;
                  }
              }
          }
      }
      var var39;
      if (input[9] > 20.500000000000004) {
          if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
              var39 = 0.02581900958052767;
          } else {
              if (input[5] > 68.73201742693793) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var39 = -0.0035188047955060915;
                  } else {
                      var39 = 0.012174631953018947;
                  }
              } else {
                  if (input[4] <= -3.527656877820794) {
                      var39 = 0.010347549787570577;
                  } else {
                      var39 = -0.0026359169120691145;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[2] <= -1.3815464400185) {
                  if (input[13] > 5.500000000000001) {
                      var39 = -0.03523266454239187;
                  } else {
                      var39 = -0.012937808420995324;
                  }
              } else {
                  if (input[13] > 6.500000000000001) {
                      var39 = -0.004857637912189228;
                  } else {
                      var39 = 0.0013292925560594267;
                  }
              }
          } else {
              if (input[0] > 40.02258517728992) {
                  if (input[6] <= -2.620058240574581) {
                      var39 = -0.005829716215135727;
                  } else {
                      var39 = 0.0007038687308276124;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var39 = 0.007642371786653415;
                  } else {
                      var39 = 0.00022419172933571394;
                  }
              }
          }
      }
      var var40;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 9.003889728695166) {
              var40 = 0.023269815525681806;
          } else {
              if (input[3] > 0.22160115277279482) {
                  if (input[2] > 0.2831395178635617) {
                      var40 = 0.000648516939612879;
                  } else {
                      var40 = -0.020766340390036716;
                  }
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var40 = -0.0055319913298356;
                  } else {
                      var40 = 0.007576712437796888;
                  }
              }
          }
      } else {
          if (input[2] > 1.103118178873732) {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] > 1.6988462938644953) {
                      var40 = 0.015140238971518767;
                  } else {
                      var40 = -0.02156595452035691;
                  }
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var40 = 0.0028803727660105705;
                  } else {
                      var40 = -0.007522770204613007;
                  }
              }
          } else {
              if (input[2] <= -0.9347891751879592) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var40 = -0.01165037263201035;
                  } else {
                      var40 = 0.0017352919788240857;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var40 = 0.0026123427277204045;
                  } else {
                      var40 = -0.0005202395998692084;
                  }
              }
          }
      }
      var var41;
      if (input[5] > 117.01558275614404) {
          if (input[0] > 64.25004156967033) {
              if (input[6] <= -0.22802093153587424) {
                  var41 = -0.03509980263085569;
              } else {
                  if (input[9] > 11.500000000000002) {
                      var41 = 0.01844600733519142;
                  } else {
                      var41 = 0.0007240522021675635;
                  }
              }
          } else {
              if (input[6] > 2.7021091197227185) {
                  var41 = 0.011462759351953806;
              } else {
                  var41 = 0.035605168589647976;
              }
          }
      } else {
          if (input[2] > 1.2449878458998531) {
              if (input[5] > 60.200564877650486) {
                  if (input[6] > 4.015152789582986) {
                      var41 = -0.0006025956992500212;
                  } else {
                      var41 = -0.022086652477286386;
                  }
              } else {
                  if (input[3] > 1.0278550228976773) {
                      var41 = -0.0256071742750976;
                  } else {
                      var41 = -0.0017251940359813728;
                  }
              }
          } else {
              if (input[4] > 5.42653906653272) {
                  if (input[5] > 105.46306831248317) {
                      var41 = 0.02904812279609418;
                  } else {
                      var41 = 0.0035288568655839677;
                  }
              } else {
                  if (input[4] > 4.21339422970748) {
                      var41 = -0.00522370081433161;
                  } else {
                      var41 = 0.00016108579958091487;
                  }
              }
          }
      }
      var var42;
      if (input[9] > 18.500000000000004) {
          if (input[2] <= -1.0945618051755213) {
              if (input[10] > 1.5000000000000002) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var42 = -0.014118652839616564;
                  } else {
                      var42 = 0.005653059711836179;
                  }
              } else {
                  if (input[5] > 28.31217988396433) {
                      var42 = -0.04917098440251854;
                  } else {
                      var42 = -0.014524249987811367;
                  }
              }
          } else {
              if (input[5] > 84.62477280480881) {
                  if (input[4] <= -3.910803839423147) {
                      var42 = -0.008678640358684434;
                  } else {
                      var42 = 0.01311846118819935;
                  }
              } else {
                  if (input[4] > 2.224830200500726) {
                      var42 = -0.0035365575086361125;
                  } else {
                      var42 = 0.0034760852337430504;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[3] <= -1.4056918431732448) {
                  var42 = -0.026426433907461196;
              } else {
                  if (input[3] > 0.3261849805051614) {
                      var42 = -0.008449432528738239;
                  } else {
                      var42 = -0.001140357488929392;
                  }
              }
          } else {
              if (input[0] > 11.512657094240305) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var42 = -0.0024738448545886965;
                  } else {
                      var42 = 0.0009919379251418273;
                  }
              } else {
                  if (input[4] <= -1.608899516503428) {
                      var42 = 0.028961781046380808;
                  } else {
                      var42 = 0.0020963063559877684;
                  }
              }
          }
      }
      var var43;
      if (input[5] <= -29.59449508597042) {
          if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
              var43 = 0.03707173300005013;
          } else {
              if (input[3] <= -0.5448595876477775) {
                  if (input[2] <= -0.7082825918688609) {
                      var43 = 0.0032952146104852976;
                  } else {
                      var43 = 0.03272914562314819;
                  }
              } else {
                  if (input[3] <= -0.39477032531299977) {
                      var43 = -0.035244686554340585;
                  } else {
                      var43 = 0.001690076150271511;
                  }
              }
          }
      } else {
          if (input[5] <= -26.388170390808185) {
              if (input[6] <= -3.017878373503765) {
                  var43 = 0.0011156770057368268;
              } else {
                  var43 = -0.03454669627193601;
              }
          } else {
              if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 9.003889728695166) {
                      var43 = 0.02196626915746026;
                  } else {
                      var43 = 0.002156828905010591;
                  }
              } else {
                  if (input[9] > 20.500000000000004) {
                      var43 = 0.002348361824317776;
                  } else {
                      var43 = -0.0008922973250439538;
                  }
              }
          }
      }
      var var44;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[5] > 128.04227788475038) {
                  if (input[4] > 0.36564692169617413) {
                      var44 = 0.028128354337509372;
                  } else {
                      var44 = -0.0032073637841085988;
                  }
              } else {
                  if (input[2] <= -1.005074921462989) {
                      var44 = -0.00449733311884865;
                  } else {
                      var44 = 0.0004433890289447751;
                  }
              }
          } else {
              if (input[3] <= -0.6521306196725657) {
                  if (input[4] > 3.517091252060496) {
                      var44 = 0.024974642182147493;
                  } else {
                      var44 = 0.0004189790751976648;
                  }
              } else {
                  if (input[3] <= -0.10510055014682856) {
                      var44 = -0.011152934094136051;
                  } else {
                      var44 = -0.001858411610960582;
                  }
              }
          }
      } else {
          if (input[5] > 71.6659331446054) {
              if (input[6] <= -0.18669319955179953) {
                  var44 = -0.02247607673086236;
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var44 = 0.02648862811098209;
                  } else {
                      var44 = -0.00458590416189235;
                  }
              }
          } else {
              if (input[4] <= -2.358993777577276) {
                  if (input[3] <= -0.36821412168164397) {
                      var44 = 0.006661980659365636;
                  } else {
                      var44 = 0.019774258457403045;
                  }
              } else {
                  if (input[6] > 7.999681113877577) {
                      var44 = 0.02904622934577525;
                  } else {
                      var44 = 0.0005172788013797541;
                  }
              }
          }
      }
      var var45;
      if (input[2] > 0.3060340617918521) {
          if (input[6] <= -2.0836067860364804) {
              if (input[9] > 6.500000000000001) {
                  var45 = -0.028001380437668477;
              } else {
                  var45 = -0.00727459351255485;
              }
          } else {
              if (input[0] > 55.71689369569628) {
                  if (input[4] > 0.9187848953214247) {
                      var45 = 0.002034079559864717;
                  } else {
                      var45 = -0.002523167393110147;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var45 = 0.009466736264425147;
                  } else {
                      var45 = -0.005482422742244371;
                  }
              }
          }
      } else {
          if (input[2] > 0.2831395178635617) {
              if (input[10] > 3.5000000000000004) {
                  var45 = -0.0066104915402300365;
              } else {
                  if (input[9] > 18.500000000000004) {
                      var45 = 0.0045889930275190205;
                  } else {
                      var45 = 0.02958161582661638;
                  }
              }
          } else {
              if (input[4] > 5.535696777028553) {
                  if (input[0] > 52.55175265198409) {
                      var45 = 0.02507059811473395;
                  } else {
                      var45 = 0.003999058322664016;
                  }
              } else {
                  if (input[7] > 1.5000000000000002) {
                      var45 = 0.016112677914152107;
                  } else {
                      var45 = 0.00008497406086468935;
                  }
              }
          }
      }
      var var46;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] > 4.937278782346295) {
                  var46 = 0.023377547949939716;
              } else {
                  if (input[6] > 2.4034644482157037) {
                      var46 = -0.02508613091051054;
                  } else {
                      var46 = 0.0066744047519625305;
                  }
              }
          } else {
              if (input[13] > 4.500000000000001) {
                  if (input[9] > 12.500000000000002) {
                      var46 = -0.012070473204198816;
                  } else {
                      var46 = -0.003381748673121806;
                  }
              } else {
                  if (input[4] > 0.40537150626608415) {
                      var46 = -0.008628007471387785;
                  } else {
                      var46 = 0.014326451159934174;
                  }
              }
          }
      } else {
          if (input[0] > 11.512657094240305) {
              if (input[0] > 22.56849409934883) {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var46 = 0.002385516756789625;
                  } else {
                      var46 = -0.00036741536191954794;
                  }
              } else {
                  if (input[9] > 12.500000000000002) {
                      var46 = -0.01570748970597722;
                  } else {
                      var46 = 0.005947681623654872;
                  }
              }
          } else {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  var46 = -0.00008437745767247032;
              } else {
                  var46 = 0.03445080346243935;
              }
          }
      }
      var var47;
      if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 13.23529411764625) {
              if (input[6] <= -5.95588626791591) {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var47 = -0.04527547748023988;
                  } else {
                      var47 = -0.008126987067609004;
                  }
              } else {
                  if (input[4] > 2.224830200500726) {
                      var47 = -0.007636128514674531;
                  } else {
                      var47 = 0.0014418011948093955;
                  }
              }
          } else {
              var47 = 0.03178588083127208;
          }
      } else {
          if (input[0] > 23.082876100105) {
              if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] <= -16.185744168434606) {
                      var47 = 0.023845566285580037;
                  } else {
                      var47 = 0.005389964903965512;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var47 = 0.005380277282763278;
                  } else {
                      var47 = 0.00011645049525083624;
                  }
              }
          } else {
              if (input[9] > 12.500000000000002) {
                  if (input[6] <= -4.22423090678842) {
                      var47 = -0.018668124118285445;
                  } else {
                      var47 = -0.004788384308691525;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var47 = -0.004556603439776072;
                  } else {
                      var47 = 0.01188503645919793;
                  }
              }
          }
      }
      var var48;
      if (input[9] > 18.500000000000004) {
          if (input[5] > 84.62477280480881) {
              if (input[4] <= -3.910803839423147) {
                  if (input[6] <= -1.722908858603448) {
                      var48 = 0.00810189846150424;
                  } else {
                      var48 = -0.02381873416374065;
                  }
              } else {
                  if (input[2] > 0.26742813602864607) {
                      var48 = 0.00666259240147163;
                  } else {
                      var48 = 0.03136749378300166;
                  }
              }
          } else {
              if (input[13] > 2.5000000000000004) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var48 = -0.0047417266572024564;
                  } else {
                      var48 = 0.0030742714136871552;
                  }
              } else {
                  if (input[10] > 1.5000000000000002) {
                      var48 = 0.000008398998036621347;
                  } else {
                      var48 = 0.021625256507826845;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[3] <= -1.4056918431732448) {
                  var48 = -0.02440100344964577;
              } else {
                  if (input[3] > 0.3261849805051614) {
                      var48 = -0.008008215144052047;
                  } else {
                      var48 = -0.0010435072858426453;
                  }
              }
          } else {
              if (input[0] > 40.02258517728992) {
                  if (input[6] <= -2.620058240574581) {
                      var48 = -0.005536771361474521;
                  } else {
                      var48 = 0.0006455473863962301;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var48 = 0.006960459799923747;
                  } else {
                      var48 = 0.00015227067897704638;
                  }
              }
          }
      }
      var var49;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 9.003889728695166) {
              var49 = 0.02057618674510098;
          } else {
              if (input[2] > 1.3520871491794348) {
                  if (input[5] > 72.02917243495783) {
                      var49 = 0.00197516354025614;
                  } else {
                      var49 = -0.030724432269326737;
                  }
              } else {
                  if (input[4] > 0.9715869529760879) {
                      var49 = 0.006511869552956114;
                  } else {
                      var49 = -0.000028636355574438235;
                  }
              }
          }
      } else {
          if (input[3] > 0.7595953914765796) {
              if (input[0] > 50.970076479383174) {
                  if (input[5] > 93.15790468632058) {
                      var49 = -0.007680460177097295;
                  } else {
                      var49 = 0.00014881530316938058;
                  }
              } else {
                  if (input[0] > 43.39903825771221) {
                      var49 = -0.02802152955361167;
                  } else {
                      var49 = 0.006277045272092015;
                  }
              }
          } else {
              if (input[5] > 84.62477280480881) {
                  if (input[4] <= -1.3242311696170128) {
                      var49 = -0.0043060312221002775;
                  } else {
                      var49 = 0.008576755555271428;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var49 = -0.002688111631240799;
                  } else {
                      var49 = 0.0012248568323500785;
                  }
              }
          }
      }
      var var50;
      if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 13.23529411764625) {
              if (input[4] > 2.224830200500726) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var50 = 0.001877142530485505;
                  } else {
                      var50 = -0.012754072020542177;
                  }
              } else {
                  if (input[6] <= -5.95588626791591) {
                      var50 = -0.014515274264820511;
                  } else {
                      var50 = 0.0013545242690515087;
                  }
              }
          } else {
              var50 = 0.029928729958000895;
          }
      } else {
          if (input[0] > 23.082876100105) {
              if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 11.500000000000002) {
                      var50 = 0.03051481374194493;
                  } else {
                      var50 = 0.0059940858411971845;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var50 = 0.0051492981744306705;
                  } else {
                      var50 = 0.00011870118585691051;
                  }
              }
          } else {
              if (input[9] > 12.500000000000002) {
                  if (input[6] <= -2.7992662614894233) {
                      var50 = -0.015894386995249137;
                  } else {
                      var50 = -0.0008305890511264326;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var50 = -0.004339973830389099;
                  } else {
                      var50 = 0.011004322004820674;
                  }
              }
          }
      }
      var var51;
      if (input[7] > 1.5000000000000002) {
          if (input[0] > 61.12545479965525) {
              if (input[13] > 5.500000000000001) {
                  if (input[9] > 7.500000000000001) {
                      var51 = 0.0192280740867654;
                  } else {
                      var51 = -0.0016589205104511802;
                  }
              } else {
                  if (input[6] > 1.7728395881409191) {
                      var51 = -0.006999783616621388;
                  } else {
                      var51 = 0.015851346454262366;
                  }
              }
          } else {
              if (input[5] > 90.21846040958793) {
                  var51 = -0.003948649979977432;
              } else {
                  var51 = -0.03420933298559287;
              }
          }
      } else {
          if (input[2] > 1.179547940362516) {
              if (input[4] <= -2.2563190733059133) {
                  var51 = 0.028531162927542094;
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var51 = -0.020226840627937646;
                  } else {
                      var51 = -0.003103977303458593;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var51 = 0.019764878040644047;
              } else {
                  if (input[13] > 5.500000000000001) {
                      var51 = -0.0008144149237548095;
                  } else {
                      var51 = 0.0012603611157997038;
                  }
              }
          }
      }
      var var52;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[5] > 128.04227788475038) {
                  if (input[4] > 0.36564692169617413) {
                      var52 = 0.02600555370053703;
                  } else {
                      var52 = -0.003361697503804244;
                  }
              } else {
                  if (input[3] > 0.14193601830092184) {
                      var52 = -0.0014804100068707864;
                  } else {
                      var52 = 0.0011199125068216292;
                  }
              }
          } else {
              if (input[2] <= -1.4602761060823315) {
                  var52 = 0.01118408069450806;
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var52 = -0.007427149902660735;
                  } else {
                      var52 = -0.0010963910444614744;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var52 = -0.00029531011437625805;
                  } else {
                      var52 = -0.0286675425235291;
                  }
              } else {
                  if (input[4] > 2.2673368930640305) {
                      var52 = 0.006582072730093102;
                  } else {
                      var52 = -0.004142009980118936;
                  }
              }
          } else {
              if (input[13] > 8.500000000000002) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var52 = 0.022406680924828646;
                  } else {
                      var52 = 0.007888808737920831;
                  }
              } else {
                  if (input[0] > 68.79176196941201) {
                      var52 = -0.011361256494333921;
                  } else {
                      var52 = 0.004765280598217087;
                  }
              }
          }
      }
      var var53;
      if (input[4] > 5.42653906653272) {
          if (input[2] > 0.22406346109460493) {
              if (input[6] > 2.600604898520747) {
                  if (input[2] > 0.6769923502865521) {
                      var53 = 0.0042744403270185095;
                  } else {
                      var53 = -0.008564823531888087;
                  }
              } else {
                  var53 = 0.02518766813135643;
              }
          } else {
              if (input[2] <= -0.1375084104867184) {
                  if (input[6] <= -0.26664934304959803) {
                      var53 = 0.026293802959990988;
                  } else {
                      var53 = -0.00918952795784995;
                  }
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var53 = 0.032633322774153005;
                  } else {
                      var53 = 0.0037264889915160325;
                  }
              }
          }
      } else {
          if (input[4] > 3.9460979913492005) {
              if (input[0] > 27.469470602855804) {
                  if (input[2] <= -0.72087477928065) {
                      var53 = 0.026479513857136303;
                  } else {
                      var53 = -0.0032770899328500806;
                  }
              } else {
                  var53 = -0.04096509433903805;
              }
          } else {
              if (input[4] > 3.747559616936297) {
                  if (input[9] > 6.500000000000001) {
                      var53 = 0.01865561673630451;
                  } else {
                      var53 = -0.012273105256864859;
                  }
              } else {
                  if (input[3] > 0.5298948855459753) {
                      var53 = -0.0024778348785104813;
                  } else {
                      var53 = 0.0004945836159157974;
                  }
              }
          }
      }
      var var54;
      if (input[9] > 18.500000000000004) {
          if (input[0] > 41.4508936947301) {
              if (input[5] > 15.235072423311074) {
                  if (input[13] > 3.5000000000000004) {
                      var54 = 0.000982928856788051;
                  } else {
                      var54 = 0.008724062937556848;
                  }
              } else {
                  var54 = 0.03472103108226316;
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 36.3245553245549) {
                      var54 = -0.00020427737262864026;
                  } else {
                      var54 = -0.015485996265977228;
                  }
              } else {
                  if (input[4] > 0.8364726566893431) {
                      var54 = -0.009801115838938208;
                  } else {
                      var54 = 0.011651766510230588;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[3] <= -1.4056918431732448) {
                  if (input[4] <= -2.0776048705582624) {
                      var54 = -0.03265762668357123;
                  } else {
                      var54 = -0.012978676141955546;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var54 = -0.000009146102131948798;
                  } else {
                      var54 = -0.006463734800650666;
                  }
              }
          } else {
              if (input[5] > 72.02917243495783) {
                  if (input[6] <= -2.398066420549097) {
                      var54 = -0.01674571651289493;
                  } else {
                      var54 = -0.0001564227428809688;
                  }
              } else {
                  if (input[13] > 1.5000000000000002) {
                      var54 = 0.0017737605933329807;
                  } else {
                      var54 = -0.006712837122299805;
                  }
              }
          }
      }
      var var55;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[9] > 5.500000000000001) {
              if (input[4] <= -6.382133466621322) {
                  var55 = -0.02205449009638006;
              } else {
                  if (input[0] > 32.048749698331136) {
                      var55 = 0.002819880471113842;
                  } else {
                      var55 = -0.008420256697177029;
                  }
              }
          } else {
              if (input[4] <= -3.5876064888796386) {
                  if (input[0] > 44.50111137696333) {
                      var55 = 0.011738488935912509;
                  } else {
                      var55 = 0.029690182577111986;
                  }
              } else {
                  if (input[0] > 71.52325454578525) {
                      var55 = 0.027149594857180766;
                  } else {
                      var55 = 0.0008017203809392303;
                  }
              }
          }
      } else {
          if (input[9] > 20.500000000000004) {
              if (input[7] <= -1.4999999999999998) {
                  var55 = -0.018541851674648457;
              } else {
                  if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                      var55 = 0.02505232377924295;
                  } else {
                      var55 = 0.002199941818312161;
                  }
              }
          } else {
              if (input[3] > 0.8123153737545654) {
                  if (input[5] > 46.93129976544811) {
                      var55 = -0.0031855385211428835;
                  } else {
                      var55 = -0.030193300609364926;
                  }
              } else {
                  if (input[0] > 67.17230718398928) {
                      var55 = 0.005088044692789701;
                  } else {
                      var55 = -0.0008261248605230466;
                  }
              }
          }
      }
      var var56;
      if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 13.23529411764625) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] <= -3.389021381025161) {
                      var56 = 0.006854360937868082;
                  } else {
                      var56 = -0.009996025056747876;
                  }
              } else {
                  if (input[0] > 72.15007195058426) {
                      var56 = 0.018264017799630057;
                  } else {
                      var56 = -0.0011478822800865519;
                  }
              }
          } else {
              var56 = 0.02810531051576965;
          }
      } else {
          if (input[0] > 23.082876100105) {
              if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] <= -1.8015029132402238) {
                      var56 = 0.013025919333392717;
                  } else {
                      var56 = -0.0010391181205108683;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var56 = 0.0048935448407832725;
                  } else {
                      var56 = 0.00011160371396701983;
                  }
              }
          } else {
              if (input[9] > 12.500000000000002) {
                  if (input[13] > 5.500000000000001) {
                      var56 = -0.01603499682387902;
                  } else {
                      var56 = -0.0022553681623070304;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var56 = -0.004164305391889467;
                  } else {
                      var56 = 0.010293077727847946;
                  }
              }
          }
      }
      var var57;
      if (input[7] > 1.5000000000000002) {
          if (input[0] > 61.12545479965525) {
              if (input[13] > 5.500000000000001) {
                  if (input[9] > 7.500000000000001) {
                      var57 = 0.01818423237396849;
                  } else {
                      var57 = -0.001646668642143729;
                  }
              } else {
                  if (input[6] > 1.7728395881409191) {
                      var57 = -0.006635936134547541;
                  } else {
                      var57 = 0.015105720872011154;
                  }
              }
          } else {
              if (input[5] > 90.21846040958793) {
                  var57 = -0.003703855625698853;
              } else {
                  var57 = -0.03284797270559284;
              }
          }
      } else {
          if (input[2] > 1.179547940362516) {
              if (input[4] <= -2.2563190733059133) {
                  var57 = 0.02714527929255007;
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var57 = -0.019171523444975108;
                  } else {
                      var57 = -0.002799994523027009;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var57 = 0.018479396706221837;
              } else {
                  if (input[13] > 5.500000000000001) {
                      var57 = -0.0007839285530686646;
                  } else {
                      var57 = 0.001185365023520268;
                  }
              }
          }
      }
      var var58;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[7] <= -1.4999999999999998) {
                  if (input[5] > 1.7833279067643293) {
                      var58 = -0.01563302393507694;
                  } else {
                      var58 = 0.0021474471343551154;
                  }
              } else {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var58 = 0.002680103893879227;
                  } else {
                      var58 = -0.0004035769905649734;
                  }
              }
          } else {
              if (input[13] > 9.500000000000002) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var58 = -0.01810439283693266;
                  } else {
                      var58 = -0.0029402536456657516;
                  }
              } else {
                  if (input[6] <= -1.0135981929507285) {
                      var58 = -0.00514278368241169;
                  } else {
                      var58 = 0.0012927408494871754;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  var58 = -0.016915933542815644;
              } else {
                  if (input[4] > 2.2673368930640305) {
                      var58 = 0.0063114766245296805;
                  } else {
                      var58 = -0.0040085121316641575;
                  }
              }
          } else {
              if (input[5] > 78.10080459619273) {
                  if (input[3] > 1.0985917439686832) {
                      var58 = 0.00976161830843438;
                  } else {
                      var58 = -0.016335871896936926;
                  }
              } else {
                  if (input[4] > 1.21504549149153) {
                      var58 = 0.0009068433226548155;
                  } else {
                      var58 = 0.01280386264120996;
                  }
              }
          }
      }
      var var59;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] <= -5.20604877356585) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 8.500000000000002) {
                      var59 = 0.043032627322482954;
                  } else {
                      var59 = 0.0069250668183298975;
                  }
              } else {
                  if (input[13] > 9.500000000000002) {
                      var59 = -0.015948287383698485;
                  } else {
                      var59 = 0.006628900445919037;
                  }
              }
          } else {
              if (input[0] > 32.048749698331136) {
                  if (input[6] > 9.003889728695166) {
                      var59 = 0.0192113412290551;
                  } else {
                      var59 = 0.0017670427246077058;
                  }
              } else {
                  if (input[6] <= -1.3596197100501843) {
                      var59 = -0.020864769383700646;
                  } else {
                      var59 = 0.016296343378380516;
                  }
              }
          }
      } else {
          if (input[9] > 20.500000000000004) {
              if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                  var59 = 0.023622340253750616;
              } else {
                  if (input[7] <= -1.4999999999999998) {
                      var59 = -0.017225852376559;
                  } else {
                      var59 = 0.002090950843403472;
                  }
              }
          } else {
              if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 3.5000000000000004) {
                      var59 = 0.0010858859458986834;
                  } else {
                      var59 = 0.026183048601432127;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var59 = -0.0037698515118537914;
                  } else {
                      var59 = -0.00027527038586619765;
                  }
              }
          }
      }
      var var60;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[2] <= -0.18032876532877087) {
              if (input[5] > 93.15790468632058) {
                  if (input[6] <= -1.2732214212272153) {
                      var60 = -0.014433397985236688;
                  } else {
                      var60 = -0.04248170525568443;
                  }
              } else {
                  if (input[5] > 86.97895198216605) {
                      var60 = 0.03890298769908034;
                  } else {
                      var60 = -0.0005363713683932736;
                  }
              }
          } else {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 15.500000000000002) {
                      var60 = 0.01980560460551349;
                  } else {
                      var60 = 0.005374900953399323;
                  }
              } else {
                  if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                      var60 = -0.02382626606639942;
                  } else {
                      var60 = 0.0016284882022196134;
                  }
              }
          }
      } else {
          if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[5] <= -29.59449508597042) {
                  var60 = 0.0477286546148398;
              } else {
                  if (input[5] > 12.081266055558087) {
                      var60 = 0.0022718472228743327;
                  } else {
                      var60 = -0.018150152747103614;
                  }
              }
          } else {
              if (input[5] > 19.544289135213152) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var60 = -0.01004363364342397;
                  } else {
                      var60 = -0.001380287114976609;
                  }
              } else {
                  if (input[0] > 45.82856649399955) {
                      var60 = 0.027402194949437065;
                  } else {
                      var60 = 0.0013932344817472319;
                  }
              }
          }
      }
      var var61;
      if (input[4] > 5.42653906653272) {
          if (input[2] > 0.22406346109460493) {
              if (input[6] > 2.600604898520747) {
                  if (input[4] > 5.636429675392096) {
                      var61 = -0.002400952788961451;
                  } else {
                      var61 = 0.01714539555337253;
                  }
              } else {
                  var61 = 0.023833419177062474;
              }
          } else {
              if (input[2] <= -0.1375084104867184) {
                  if (input[6] <= -0.26664934304959803) {
                      var61 = 0.024945512490248668;
                  } else {
                      var61 = -0.008730032198741954;
                  }
              } else {
                  if (input[13] > 6.500000000000001) {
                      var61 = 0.00345136986621049;
                  } else {
                      var61 = 0.030808977943357786;
                  }
              }
          }
      } else {
          if (input[4] > 3.9460979913492005) {
              if (input[0] > 26.383030344586114) {
                  if (input[2] <= -0.72087477928065) {
                      var61 = 0.022547546548470604;
                  } else {
                      var61 = -0.0032664538407249618;
                  }
              } else {
                  var61 = -0.04357914298222746;
              }
          } else {
              if (input[4] > 3.84136763384246) {
                  if (input[0] > 46.694943750340066) {
                      var61 = 0.029669193654336817;
                  } else {
                      var61 = -0.006765606467427555;
                  }
              } else {
                  if (input[5] > 27.141286553166832) {
                      var61 = -0.0007498306766073515;
                  } else {
                      var61 = 0.0017329614913688621;
                  }
              }
          }
      }
      var var62;
      if (input[7] > 1.5000000000000002) {
          if (input[0] > 61.12545479965525) {
              if (input[13] > 7.500000000000001) {
                  if (input[13] > 8.500000000000002) {
                      var62 = 0.006435215360789278;
                  } else {
                      var62 = 0.03478524389219056;
                  }
              } else {
                  if (input[0] > 76.98568553550524) {
                      var62 = -0.013531214787249436;
                  } else {
                      var62 = 0.004736069771535692;
                  }
              }
          } else {
              if (input[5] > 90.21846040958793) {
                  var62 = -0.0034180047053664407;
              } else {
                  var62 = -0.03153900485541793;
              }
          }
      } else {
          if (input[6] > 10.31060103068119) {
              var62 = 0.01782633628719193;
          } else {
              if (input[2] > 1.179547940362516) {
                  if (input[4] <= -2.2563190733059133) {
                      var62 = 0.02556766442608446;
                  } else {
                      var62 = -0.007353644750470631;
                  }
              } else {
                  if (input[4] > 9.401150856775486) {
                      var62 = 0.01976064694455301;
                  } else {
                      var62 = 0.000005069408648163741;
                  }
              }
          }
      }
      var var63;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[5] > 128.04227788475038) {
                  if (input[4] > 0.36564692169617413) {
                      var63 = 0.02410935396328039;
                  } else {
                      var63 = -0.003509900884392761;
                  }
              } else {
                  if (input[3] > 0.14193601830092184) {
                      var63 = -0.0014148050678216384;
                  } else {
                      var63 = 0.0010435393018349514;
                  }
              }
          } else {
              if (input[2] <= -1.4602761060823315) {
                  var63 = 0.010489552682409488;
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var63 = -0.006872320752329711;
                  } else {
                      var63 = -0.0008493361617565687;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] > 3.114370403695782) {
                      var63 = 0.026944013768634423;
                  } else {
                      var63 = -0.0012533648108219713;
                  }
              } else {
                  if (input[0] > 68.79176196941201) {
                      var63 = 0.007709086248150452;
                  } else {
                      var63 = -0.006977020271287652;
                  }
              }
          } else {
              if (input[13] > 8.500000000000002) {
                  if (input[5] > 80.00550695293408) {
                      var63 = -0.004114014633788156;
                  } else {
                      var63 = 0.015252679020661944;
                  }
              } else {
                  if (input[10] > 4.500000000000001) {
                      var63 = -0.009548895679957547;
                  } else {
                      var63 = 0.004621115303055416;
                  }
              }
          }
      }
      var var64;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -7.123374703856836) {
              var64 = -0.015265706005557576;
          } else {
              if (input[4] <= -2.1729741642181852) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var64 = 0.015990983835967167;
                  } else {
                      var64 = 0.0021008758398528052;
                  }
              } else {
                  if (input[4] > 0.9715869529760879) {
                      var64 = 0.004683116782886462;
                  } else {
                      var64 = -0.0043343233911329075;
                  }
              }
          }
      } else {
          if (input[2] <= -0.9347891751879592) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -0.767716948598279) {
                      var64 = -0.00878496574106495;
                  } else {
                      var64 = -0.035396595603386975;
                  }
              } else {
                  if (input[5] > 54.80963993439257) {
                      var64 = -0.025741506451816533;
                  } else {
                      var64 = 0.003610661730539396;
                  }
              }
          } else {
              if (input[3] <= -0.5811484955150211) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var64 = -0.0028865250574350116;
                  } else {
                      var64 = 0.00804813086774869;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var64 = 0.002242284195377558;
                  } else {
                      var64 = -0.0010814096233488727;
                  }
              }
          }
      }
      var var65;
      if (input[7] > 1.5000000000000002) {
          if (input[0] > 61.12545479965525) {
              if (input[13] > 5.500000000000001) {
                  if (input[3] > 0.4735395160902805) {
                      var65 = 0.007799528481376536;
                  } else {
                      var65 = 0.03222933305470377;
                  }
              } else {
                  if (input[6] > 1.7728395881409191) {
                      var65 = -0.006222211899839972;
                  } else {
                      var65 = 0.014427824595296512;
                  }
              }
          } else {
              if (input[5] > 90.75609196671006) {
                  var65 = -0.002615467579318447;
              } else {
                  var65 = -0.029509013494317907;
              }
          }
      } else {
          if (input[6] > 10.31060103068119) {
              var65 = 0.016802885964872526;
          } else {
              if (input[2] > 1.179547940362516) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var65 = -0.01871197366889831;
                  } else {
                      var65 = -0.0020904603567965764;
                  }
              } else {
                  if (input[4] > 9.401150856775486) {
                      var65 = 0.01868229113184688;
                  } else {
                      var65 = 0.0000021065517976577467;
                  }
              }
          }
      }
      var var66;
      if (input[9] > 3.5000000000000004) {
          if (input[5] > 69.85608617600006) {
              if (input[4] <= -0.7078092796271618) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var66 = -0.006702528735039769;
                  } else {
                      var66 = 0.0053606785230171615;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var66 = 0.007926231090429083;
                  } else {
                      var66 = -0.0037742792610904368;
                  }
              }
          } else {
              if (input[2] > 0.11827058173472725) {
                  if (input[0] > 45.43848929792071) {
                      var66 = -0.0026119032442511467;
                  } else {
                      var66 = -0.008777804325216484;
                  }
              } else {
                  if (input[5] > 69.10005212074935) {
                      var66 = -0.024924380932345887;
                  } else {
                      var66 = 0.000435234031322524;
                  }
              }
          }
      } else {
          if (input[5] > 71.6659331446054) {
              if (input[6] <= -0.3473265683140172) {
                  var66 = -0.02102222576603136;
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var66 = 0.024549539654166626;
                  } else {
                      var66 = -0.004314288536451701;
                  }
              }
          } else {
              if (input[4] <= -2.358993777577276) {
                  if (input[10] > 2.5000000000000004) {
                      var66 = 0.005905108489798205;
                  } else {
                      var66 = 0.01864841906890062;
                  }
              } else {
                  if (input[6] > 7.999681113877577) {
                      var66 = 0.027548327673039337;
                  } else {
                      var66 = 0.000058831394026386205;
                  }
              }
          }
      }
      var var67;
      if (input[9] > 18.500000000000004) {
          if (input[5] > 69.85608617600006) {
              if (input[4] <= -3.0935790789862545) {
                  if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                      var67 = 0.016698059841699777;
                  } else {
                      var67 = -0.02100457956659872;
                  }
              } else {
                  if (input[3] > 0.12794365350766224) {
                      var67 = 0.006022401692629492;
                  } else {
                      var67 = 0.025315231611562683;
                  }
              }
          } else {
              if (input[4] > 2.224830200500726) {
                  if (input[6] <= -2.227482366506593) {
                      var67 = 0.02897280850220187;
                  } else {
                      var67 = -0.00822322240435139;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var67 = -0.003372181424016799;
                  } else {
                      var67 = 0.006534946578661206;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[6] <= -6.443218311398012) {
                  var67 = -0.02006061005842714;
              } else {
                  if (input[3] > 0.36378451209101553) {
                      var67 = -0.007491884686496872;
                  } else {
                      var67 = -0.0008395817330544424;
                  }
              }
          } else {
              if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] > 1.0611995407922705) {
                      var67 = -0.03209160280471717;
                  } else {
                      var67 = 0.005210783918090111;
                  }
              } else {
                  if (input[0] > 11.512657094240305) {
                      var67 = -0.0001993096232201517;
                  } else {
                      var67 = 0.012368106219351985;
                  }
              }
          }
      }
      var var68;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[9] > 5.500000000000001) {
              if (input[4] <= -6.382133466621322) {
                  var68 = -0.02094053625996962;
              } else {
                  if (input[0] > 32.048749698331136) {
                      var68 = 0.0025651358660168638;
                  } else {
                      var68 = -0.00785913548381628;
                  }
              }
          } else {
              if (input[13] > 6.500000000000001) {
                  if (input[13] > 10.500000000000002) {
                      var68 = 0.0002063400417442891;
                  } else {
                      var68 = 0.017813051668125603;
                  }
              } else {
                  if (input[10] > 1.5000000000000002) {
                      var68 = -0.004477817889045614;
                  } else {
                      var68 = 0.017956857037357304;
                  }
              }
          }
      } else {
          if (input[13] > 5.500000000000001) {
              if (input[7] > 1.5000000000000002) {
                  if (input[9] > 19.500000000000004) {
                      var68 = 0.030158583583875784;
                  } else {
                      var68 = 0.0033016317967318864;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var68 = 0.0074150611560452875;
                  } else {
                      var68 = -0.0018109230974040211;
                  }
              }
          } else {
              if (input[4] > 1.4603064204353786) {
                  if (input[5] > 69.85608617600006) {
                      var68 = 0.0035971834281141725;
                  } else {
                      var68 = -0.005652127767826672;
                  }
              } else {
                  if (input[4] <= -0.6271685031470128) {
                      var68 = 0.00023089472381640757;
                  } else {
                      var68 = 0.007810362128406458;
                  }
              }
          }
      }
      var var69;
      if (input[4] <= -2.1729741642181852) {
          if (input[5] > 43.306883112568904) {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] <= -5.327365940140429) {
                      var69 = -0.009303873111112719;
                  } else {
                      var69 = 0.009009120958173895;
                  }
              } else {
                  if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                      var69 = 0.0006728429836880424;
                  } else {
                      var69 = -0.008285950311300732;
                  }
              }
          } else {
              if (input[3] > 0.03781859696599881) {
                  if (input[0] > 49.304428434669454) {
                      var69 = 0.042972615214860996;
                  } else {
                      var69 = 0.01306362869665436;
                  }
              } else {
                  if (input[0] > 25.51590802753186) {
                      var69 = 0.005402092195033673;
                  } else {
                      var69 = -0.004038938001809408;
                  }
              }
          }
      } else {
          if (input[4] <= -0.7791403766304014) {
              if (input[0] > 75.52030211082776) {
                  var69 = 0.01262763794725145;
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var69 = -0.009927381452532684;
                  } else {
                      var69 = -0.0015682581415882562;
                  }
              }
          } else {
              if (input[4] <= -0.45083601189522843) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var69 = 0.023657096662518706;
                  } else {
                      var69 = 0.004008120682115066;
                  }
              } else {
                  if (input[5] > 69.85608617600006) {
                      var69 = 0.0026989294908121592;
                  } else {
                      var69 = -0.0014001303590266269;
                  }
              }
          }
      }
      var var70;
      if (input[4] > 5.42653906653272) {
          if (input[2] > 0.22406346109460493) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 4.1323870451544105) {
                      var70 = 0.0024588302935067826;
                  } else {
                      var70 = 0.036039350344081005;
                  }
              } else {
                  if (input[3] > 0.33217273721216956) {
                      var70 = 0.0016945815161459018;
                  } else {
                      var70 = -0.016956062718811272;
                  }
              }
          } else {
              if (input[2] <= -0.1375084104867184) {
                  if (input[6] <= -0.26664934304959803) {
                      var70 = 0.023561452057601937;
                  } else {
                      var70 = -0.008233626947562986;
                  }
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var70 = 0.029433992923915315;
                  } else {
                      var70 = 0.0024928832942961426;
                  }
              }
          }
      } else {
          if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[0] > 73.97049088155427) {
                  var70 = 0.03015611299083756;
              } else {
                  if (input[5] > 46.93129976544811) {
                      var70 = -0.0053790727200288095;
                  } else {
                      var70 = 0.009730868874099623;
                  }
              }
          } else {
              if (input[4] > 4.21339422970748) {
                  if (input[0] > 29.926259701776768) {
                      var70 = -0.002458154351667726;
                  } else {
                      var70 = -0.03595219910118677;
                  }
              } else {
                  if (input[2] > 1.200800479964507) {
                      var70 = -0.005228678693573445;
                  } else {
                      var70 = 0.0000737638600155185;
                  }
              }
          }
      }
      var var71;
      if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 13.23529411764625) {
              if (input[6] <= -5.95588626791591) {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var71 = -0.043013567536386715;
                  } else {
                      var71 = -0.00691809101600746;
                  }
              } else {
                  if (input[4] <= -2.0408506225936174) {
                      var71 = 0.005748735866555686;
                  } else {
                      var71 = -0.0033700308143143802;
                  }
              }
          } else {
              var71 = 0.02615033801038732;
          }
      } else {
          if (input[0] > 23.082876100105) {
              if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 14.500000000000002) {
                      var71 = -0.003795397754288623;
                  } else {
                      var71 = 0.010950590773844112;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var71 = 0.004727919430458058;
                  } else {
                      var71 = 0.00008712526270063507;
                  }
              }
          } else {
              if (input[9] > 12.500000000000002) {
                  if (input[6] <= -2.7992662614894233) {
                      var71 = -0.014331036345903693;
                  } else {
                      var71 = 0.0004672540602469271;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var71 = -0.0037384980840048155;
                  } else {
                      var71 = 0.009352078511213177;
                  }
              }
          }
      }
      var var72;
      if (input[9] > 18.500000000000004) {
          if (input[2] <= -1.0945618051755213) {
              if (input[10] > 1.5000000000000002) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var72 = -0.012131418469648839;
                  } else {
                      var72 = 0.006417279775872184;
                  }
              } else {
                  if (input[5] > 28.31217988396433) {
                      var72 = -0.04694363913010937;
                  } else {
                      var72 = -0.012708069279089969;
                  }
              }
          } else {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 96.12555884548514) {
                      var72 = 0.020785007236011455;
                  } else {
                      var72 = 0.0034969294808442834;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var72 = 0.0264469672833708;
                  } else {
                      var72 = -0.0010291445244356475;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[6] <= -6.443218311398012) {
                  var72 = -0.01890353470588165;
              } else {
                  if (input[3] > 0.36378451209101553) {
                      var72 = -0.007192864458518871;
                  } else {
                      var72 = -0.0007139854072237641;
                  }
              }
          } else {
              if (input[5] > 73.99244929814733) {
                  if (input[6] <= -2.282378601683849) {
                      var72 = -0.016267577143038895;
                  } else {
                      var72 = -0.0002620205480469268;
                  }
              } else {
                  if (input[6] > 7.999681113877577) {
                      var72 = 0.01907500381099286;
                  } else {
                      var72 = 0.0007763657044824162;
                  }
              }
          }
      }
      var var73;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] <= -5.20604877356585) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 8.500000000000002) {
                      var73 = 0.04008429581713075;
                  } else {
                      var73 = 0.005755202053942542;
                  }
              } else {
                  if (input[13] > 9.500000000000002) {
                      var73 = -0.015210503449959226;
                  } else {
                      var73 = 0.006411055024931531;
                  }
              }
          } else {
              if (input[0] > 32.048749698331136) {
                  if (input[3] > 0.09504352673695045) {
                      var73 = -0.00013129639728468682;
                  } else {
                      var73 = 0.005218816341403083;
                  }
              } else {
                  if (input[6] <= -1.3596197100501843) {
                      var73 = -0.019807721009287908;
                  } else {
                      var73 = 0.01581636895802304;
                  }
              }
          }
      } else {
          if (input[13] > 5.500000000000001) {
              if (input[7] > 1.5000000000000002) {
                  if (input[0] > 63.24679684411505) {
                      var73 = 0.013097077897725752;
                  } else {
                      var73 = -0.015543670751834056;
                  }
              } else {
                  if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                      var73 = 0.008269017855334867;
                  } else {
                      var73 = -0.00169547608069987;
                  }
              }
          } else {
              if (input[4] <= -8.18070102155914) {
                  var73 = 0.025364705854572546;
              } else {
                  if (input[4] > 1.4603064204353786) {
                      var73 = -0.0021947826805671267;
                  } else {
                      var73 = 0.0024601117153500796;
                  }
              }
          }
      }
      var var74;
      if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 2.224830200500726) {
              if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 10.500000000000002) {
                      var74 = -0.030357160842494835;
                  } else {
                      var74 = 0.006117708024728803;
                  }
              } else {
                  if (input[4] > 4.912099304131096) {
                      var74 = 0.004794467095597398;
                  } else {
                      var74 = -0.018339930801784445;
                  }
              }
          } else {
              if (input[4] > 1.7160674285510085) {
                  if (input[5] > 45.583015427105394) {
                      var74 = 0.03541053644943008;
                  } else {
                      var74 = -0.0008493148782782149;
                  }
              } else {
                  if (input[0] > 48.64391454929942) {
                      var74 = -0.00547131290494715;
                  } else {
                      var74 = 0.0035015251020890184;
                  }
              }
          }
      } else {
          if (input[4] <= -0.7791403766304014) {
              if (input[4] <= -2.1729741642181852) {
                  if (input[5] > 43.306883112568904) {
                      var74 = -0.002836414668142705;
                  } else {
                      var74 = 0.005319065963838848;
                  }
              } else {
                  var74 = -0.004596390258638989;
              }
          } else {
              if (input[5] > 69.85608617600006) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var74 = 0.00895200997947735;
                  } else {
                      var74 = -0.003326800978400349;
                  }
              } else {
                  if (input[4] <= -0.7078092796271618) {
                      var74 = 0.021540427560468155;
                  } else {
                      var74 = -0.000780240952413138;
                  }
              }
          }
      }
      var var75;
      if (input[38] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 78.73527750225064) {
              var75 = 0.021911181723159968;
          } else {
              if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
                  var75 = 0.013509295671375427;
              } else {
                  if (input[4] <= -0.5762604215079786) {
                      var75 = -0.005420158535196552;
                  } else {
                      var75 = -0.0003939441836558529;
                  }
              }
          }
      } else {
          if (input[2] > 0.512388466754457) {
              if (input[10] > 1.5000000000000002) {
                  if (input[0] > 37.2807635912475) {
                      var75 = -0.00017864956731373832;
                  } else {
                      var75 = 0.0239617214431264;
                  }
              } else {
                  if (input[5] > 68.36291572247318) {
                      var75 = -0.0007334189324882615;
                  } else {
                      var75 = -0.015459237254374286;
                  }
              }
          } else {
              if (input[2] <= -0.9171433916024895) {
                  if (input[5] > 33.60691761207234) {
                      var75 = -0.010427554181987528;
                  } else {
                      var75 = 0.00023510437058087662;
                  }
              } else {
                  if (input[6] <= -6.717684292131488) {
                      var75 = -0.008590094119686253;
                  } else {
                      var75 = 0.001647782036436049;
                  }
              }
          }
      }
      var var76;
      if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] <= -1.8783643679700581) {
              if (input[4] <= -2.301314617351657) {
                  if (input[5] > 43.83642014465365) {
                      var76 = -0.005721473154402698;
                  } else {
                      var76 = 0.008341005431604804;
                  }
              } else {
                  if (input[4] > 0.000000000000000000000000000000000010000000180025095) {
                      var76 = -0.000022112179608248756;
                  } else {
                      var76 = -0.015832801451961327;
                  }
              }
          } else {
              if (input[4] > 2.1419746152525203) {
                  if (input[13] > 6.500000000000001) {
                      var76 = 0.004764779548420311;
                  } else {
                      var76 = -0.006422541746913125;
                  }
              } else {
                  if (input[5] > 10.256312745234089) {
                      var76 = 0.00755983699647892;
                  } else {
                      var76 = -0.01702127394163501;
                  }
              }
          }
      } else {
          if (input[5] > 19.544289135213152) {
              if (input[5] > 69.85608617600006) {
                  if (input[4] <= -3.0935790789862545) {
                      var76 = -0.008013575219158338;
                  } else {
                      var76 = 0.002069832558366315;
                  }
              } else {
                  var76 = -0.003081870073642745;
              }
          } else {
              if (input[0] > 33.69891014281424) {
                  if (input[4] > 1.1731004098190219) {
                      var76 = -0.00006790459592876721;
                  } else {
                      var76 = 0.011107128497974045;
                  }
              } else {
                  if (input[2] <= -0.07927539197604427) {
                      var76 = 0.0009094060080323916;
                  } else {
                      var76 = -0.013984859947714246;
                  }
              }
          }
      }
      var var77;
      if (input[9] > 18.500000000000004) {
          if (input[7] <= -1.4999999999999998) {
              if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                  var77 = -0.028359262976031075;
              } else {
                  var77 = -0.0025757649313158104;
              }
          } else {
              if (input[0] > 86.25101283547333) {
                  var77 = 0.023676646143450945;
              } else {
                  if (input[2] > 1.103118178873732) {
                      var77 = -0.006326250942283631;
                  } else {
                      var77 = 0.0021460318808001447;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[5] > 70.6027148026618) {
                  if (input[4] <= -0.8609197916882126) {
                      var77 = -0.007796100637153418;
                  } else {
                      var77 = 0.004145435728845011;
                  }
              } else {
                  if (input[3] > 0.36378451209101553) {
                      var77 = -0.02597315444724582;
                  } else {
                      var77 = -0.0029770752673673757;
                  }
              }
          } else {
              if (input[5] > 73.99244929814733) {
                  if (input[6] <= -2.398066420549097) {
                      var77 = -0.015581692203592741;
                  } else {
                      var77 = -0.00042954433906521874;
                  }
              } else {
                  if (input[6] > 7.999681113877577) {
                      var77 = 0.01826965328561688;
                  } else {
                      var77 = 0.000761622918797201;
                  }
              }
          }
      }
      var var78;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[7] <= -1.4999999999999998) {
                  if (input[5] > 1.7833279067643293) {
                      var78 = -0.014585004011914888;
                  } else {
                      var78 = 0.0018730601836155312;
                  }
              } else {
                  if (input[3] > 0.14816154989694033) {
                      var78 = -0.0010664274685911938;
                  } else {
                      var78 = 0.0014980114581359155;
                  }
              }
          } else {
              if (input[9] > 5.500000000000001) {
                  var78 = -0.005250161109097027;
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var78 = -0.005328041649987636;
                  } else {
                      var78 = 0.004051775447784871;
                  }
              }
          }
      } else {
          if (input[5] > 71.6659331446054) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var78 = 0.026890741123155162;
                  } else {
                      var78 = -0.0006769555412026639;
                  }
              } else {
                  if (input[0] > 58.835776428762735) {
                      var78 = -0.005175010572905881;
                  } else {
                      var78 = -0.03234994107475724;
                  }
              }
          } else {
              if (input[4] <= -2.358993777577276) {
                  if (input[4] <= -2.6534313318860563) {
                      var78 = 0.008323378940637288;
                  } else {
                      var78 = 0.031926830770064286;
                  }
              } else {
                  if (input[4] > 4.269439697866238) {
                      var78 = 0.009540414753444637;
                  } else {
                      var78 = -0.0017084056427012764;
                  }
              }
          }
      }
      var var79;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[3] > 1.5495200352880245) {
              var79 = 0.017701463067226877;
          } else {
              if (input[0] > 58.835776428762735) {
                  if (input[5] > 71.29347043060852) {
                      var79 = 0.0002356098772133603;
                  } else {
                      var79 = -0.011332707552564473;
                  }
              } else {
                  if (input[6] > 0.7284727162066434) {
                      var79 = 0.008778134868760366;
                  } else {
                      var79 = 0.0009533903910785137;
                  }
              }
          }
      } else {
          if (input[3] > 0.7595953914765796) {
              if (input[5] > 93.15790468632058) {
                  if (input[4] <= -1.841986354723103) {
                      var79 = -0.020586086279565843;
                  } else {
                      var79 = -0.005357204486163616;
                  }
              } else {
                  if (input[0] > 50.970076479383174) {
                      var79 = 0.0007880623210580761;
                  } else {
                      var79 = -0.014177548703282198;
                  }
              }
          } else {
              if (input[5] > 84.62477280480881) {
                  if (input[4] <= -1.3242311696170128) {
                      var79 = -0.0031810897136722825;
                  } else {
                      var79 = 0.007256436272291749;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var79 = -0.002301385695043331;
                  } else {
                      var79 = 0.0009717357657728827;
                  }
              }
          }
      }
      var var80;
      if (input[4] <= -2.1729741642181852) {
          if (input[5] > 43.306883112568904) {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] <= -5.327365940140429) {
                      var80 = -0.008256423542889869;
                  } else {
                      var80 = 0.008871937410671998;
                  }
              } else {
                  if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                      var80 = 0.0010555521859767663;
                  } else {
                      var80 = -0.0074283516137007444;
                  }
              }
          } else {
              if (input[3] > 0.03781859696599881) {
                  if (input[0] > 49.304428434669454) {
                      var80 = 0.03962306662964768;
                  } else {
                      var80 = 0.011725081880653042;
                  }
              } else {
                  if (input[7] <= -1.4999999999999998) {
                      var80 = -0.007892311687412721;
                  } else {
                      var80 = 0.003976446417036059;
                  }
              }
          }
      } else {
          if (input[4] <= -0.7791403766304014) {
              if (input[2] <= -1.5107108589838323) {
                  var80 = 0.021853669488116078;
              } else {
                  if (input[6] <= -4.4242046780646325) {
                      var80 = -0.015613287701305571;
                  } else {
                      var80 = -0.0030296107823701767;
                  }
              }
          } else {
              if (input[4] <= -0.45083601189522843) {
                  if (input[3] <= -0.24344553277095524) {
                      var80 = -0.0024728813386305395;
                  } else {
                      var80 = 0.014948985400217033;
                  }
              } else {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var80 = 0.004986080115561369;
                  } else {
                      var80 = -0.0006974729911954266;
                  }
              }
          }
      }
      var var81;
      if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 13.23529411764625) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] > 0.9187848953214247) {
                      var81 = -0.015328570371848677;
                  } else {
                      var81 = -0.001189631944534151;
                  }
              } else {
                  if (input[5] > 41.466261218353374) {
                      var81 = 0.004996434865333989;
                  } else {
                      var81 = -0.0050234997636815;
                  }
              }
          } else {
              var81 = 0.024413294330200744;
          }
      } else {
          if (input[0] > 23.082876100105) {
              if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 11.500000000000002) {
                      var81 = 0.027145520398222905;
                  } else {
                      var81 = 0.004440318164353043;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var81 = 0.004490598619327049;
                  } else {
                      var81 = 0.0000883668227426264;
                  }
              }
          } else {
              if (input[9] > 12.500000000000002) {
                  if (input[13] > 5.500000000000001) {
                      var81 = -0.01433489120383668;
                  } else {
                      var81 = -0.0014896049892812262;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var81 = -0.0036364426497140553;
                  } else {
                      var81 = 0.008750060694360835;
                  }
              }
          }
      }
      var var82;
      if (input[9] > 20.500000000000004) {
          if (input[5] <= -7.578872429369199) {
              var82 = 0.021876627572926133;
          } else {
              if (input[13] > 10.500000000000002) {
                  if (input[2] <= -0.48159142127068255) {
                      var82 = -0.0227203442857331;
                  } else {
                      var82 = 0.0004393212136872839;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var82 = 0.02247986788589281;
                  } else {
                      var82 = 0.002061789582869155;
                  }
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] <= -0.7078092796271618) {
                      var82 = 0.0003103212696956906;
                  } else {
                      var82 = 0.026841640178722877;
                  }
              } else {
                  if (input[0] > 13.23529411764625) {
                      var82 = -0.0033178006973261912;
                  } else {
                      var82 = 0.024516092047276724;
                  }
              }
          } else {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -1.1437063176950601) {
                      var82 = -0.009530507989572579;
                  } else {
                      var82 = 0.0026225976065896617;
                  }
              } else {
                  if (input[21] > 0.000000000000000000000000000000000010000000180025095) {
                      var82 = 0.014197509230927781;
                  } else {
                      var82 = -0.001079862915398139;
                  }
              }
          }
      }
      var var83;
      if (input[9] > 3.5000000000000004) {
          if (input[9] > 7.500000000000001) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                      var83 = 0.03337092162862653;
                  } else {
                      var83 = 0.0012821940568769263;
                  }
              } else {
                  var83 = -0.0005336225500739859;
              }
          } else {
              if (input[13] > 9.500000000000002) {
                  if (input[5] <= -4.036293855178701) {
                      var83 = -0.03213267866195093;
                  } else {
                      var83 = -0.004816030291238473;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var83 = 0.013915540285973275;
                  } else {
                      var83 = -0.0016313423270711434;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var83 = 0.0013003146424570451;
                  } else {
                      var83 = -0.026586813830656676;
                  }
              } else {
                  if (input[4] > 2.2673368930640305) {
                      var83 = 0.0057727933019490335;
                  } else {
                      var83 = -0.0034510576721200636;
                  }
              }
          } else {
              if (input[13] > 8.500000000000002) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var83 = 0.019463422624578064;
                  } else {
                      var83 = 0.006169348802141659;
                  }
              } else {
                  if (input[10] > 4.500000000000001) {
                      var83 = -0.009128095709601635;
                  } else {
                      var83 = 0.004114842128418994;
                  }
              }
          }
      }
      var var84;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[2] <= -0.18032876532877087) {
              if (input[5] > 98.19400961422491) {
                  var84 = -0.033382943606625595;
              } else {
                  if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                      var84 = 0.019149950874341893;
                  } else {
                      var84 = -0.0005786118299775619;
                  }
              }
          } else {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 15.500000000000002) {
                      var84 = 0.01829350574681129;
                  } else {
                      var84 = 0.004533357287868355;
                  }
              } else {
                  if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                      var84 = -0.012201988662720452;
                  } else {
                      var84 = 0.0026798804785631747;
                  }
              }
          }
      } else {
          if (input[2] <= -0.2707003273254145) {
              if (input[6] <= -1.188675504753722) {
                  if (input[4] <= -2.0004379047689356) {
                      var84 = 0.0033563110956396185;
                  } else {
                      var84 = -0.004170129331382826;
                  }
              } else {
                  if (input[4] > 3.9460979913492005) {
                      var84 = -0.005557213963841057;
                  } else {
                      var84 = 0.013469488123651244;
                  }
              }
          } else {
              if (input[2] <= -0.18032876532877087) {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var84 = -0.017842227573589976;
                  } else {
                      var84 = -0.0055985263598755525;
                  }
              } else {
                  if (input[6] <= -4.032321514980188) {
                      var84 = 0.016730302460098927;
                  } else {
                      var84 = -0.0007653754464532761;
                  }
              }
          }
      }
      var var85;
      if (input[4] > 4.912099304131096) {
          if (input[2] > 0.21519627192871363) {
              if (input[5] > 40.15455777421886) {
                  if (input[5] > 44.287689435009696) {
                      var85 = 0.0015613247764782927;
                  } else {
                      var85 = 0.02851747853185578;
                  }
              } else {
                  if (input[4] > 6.290654712658461) {
                      var85 = 0.001567677399052989;
                  } else {
                      var85 = -0.028528411887755054;
                  }
              }
          } else {
              if (input[2] <= -0.1375084104867184) {
                  if (input[9] > 4.500000000000001) {
                      var85 = -0.008030598248304805;
                  } else {
                      var85 = 0.015163082058988251;
                  }
              } else {
                  if (input[13] > 6.500000000000001) {
                      var85 = 0.0016080075383191911;
                  } else {
                      var85 = 0.029619981840289036;
                  }
              }
          }
      } else {
          if (input[4] > 4.21339422970748) {
              if (input[9] > 3.5000000000000004) {
                  if (input[0] > 53.07348934080051) {
                      var85 = -0.0022087937554069;
                  } else {
                      var85 = -0.015593590850743895;
                  }
              } else {
                  var85 = 0.006671678326676735;
              }
          } else {
              if (input[2] > 1.200800479964507) {
                  if (input[5] > 67.99727885723505) {
                      var85 = -0.0008681496769363874;
                  } else {
                      var85 = -0.018222925909737647;
                  }
              } else {
                  if (input[4] > 3.2032943389782225) {
                      var85 = 0.004858720935167906;
                  } else {
                      var85 = -0.00015009889023213788;
                  }
              }
          }
      }
      var var86;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -7.123374703856836) {
              var86 = -0.014342975757757141;
          } else {
              if (input[13] > 3.5000000000000004) {
                  if (input[4] > 5.322105873571434) {
                      var86 = 0.016312437825015912;
                  } else {
                      var86 = 0.0025567102823547067;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var86 = -0.011741874996029342;
                  } else {
                      var86 = 0.0037053230352835846;
                  }
              }
          }
      } else {
          if (input[9] > 20.500000000000004) {
              if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 16.13730462928316) {
                      var86 = -0.001929945097323409;
                  } else {
                      var86 = -0.02725026352899095;
                  }
              } else {
                  if (input[5] <= -7.578872429369199) {
                      var86 = 0.032705867089475156;
                  } else {
                      var86 = 0.0025239483833111153;
                  }
              }
          } else {
              if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 2.5000000000000004) {
                      var86 = 0.0018704213200142939;
                  } else {
                      var86 = 0.03039102667800332;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var86 = -0.003317110441438356;
                  } else {
                      var86 = -0.000238932161424647;
                  }
              }
          }
      }
      var var87;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[5] > 91.29004180028802) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  var87 = -0.040236296782740884;
              } else {
                  var87 = -0.0018446826199432264;
              }
          } else {
              if (input[6] <= -2.398066420549097) {
                  if (input[4] <= -1.841986354723103) {
                      var87 = 0.0064752885384456145;
                  } else {
                      var87 = -0.03773772985976791;
                  }
              } else {
                  if (input[4] <= -0.5762604215079786) {
                      var87 = 0.030333192762539804;
                  } else {
                      var87 = 0.007384620700184476;
                  }
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] > 0.3147614493851478) {
                  if (input[0] > 62.753701799598225) {
                      var87 = 0.003164175503145617;
                  } else {
                      var87 = -0.012931042828619503;
                  }
              } else {
                  if (input[6] > 0.11443850873809754) {
                      var87 = 0.03032833876736298;
                  } else {
                      var87 = -0.000010020356340869713;
                  }
              }
          } else {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var87 = -0.001473767192103648;
                  } else {
                      var87 = 0.004316229775011728;
                  }
              } else {
                  if (input[0] > 44.50111137696333) {
                      var87 = 0.0007600820127710593;
                  } else {
                      var87 = -0.002682481469766771;
                  }
              }
          }
      }
      var var88;
      if (input[2] > 0.22406346109460493) {
          if (input[0] > 52.06853502461072) {
              if (input[5] > 38.40608426400883) {
                  if (input[13] > 1.5000000000000002) {
                      var88 = -0.0007554707886717709;
                  } else {
                      var88 = 0.0077122528060945585;
                  }
              } else {
                  var88 = 0.02572531043041473;
              }
          } else {
              if (input[4] <= -1.608899516503428) {
                  if (input[5] > 62.70267242553313) {
                      var88 = -0.0257245306851561;
                  } else {
                      var88 = 0.012398713772931483;
                  }
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var88 = -0.012180437233371345;
                  } else {
                      var88 = -0.001017802212064581;
                  }
              }
          }
      } else {
          if (input[6] > 2.5493545797764527) {
              if (input[13] > 1.5000000000000002) {
                  if (input[13] > 7.500000000000001) {
                      var88 = 0.00202408134054495;
                  } else {
                      var88 = 0.02094216288087622;
                  }
              } else {
                  var88 = -0.023754697409630345;
              }
          } else {
              if (input[0] > 65.44503760026167) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var88 = -0.02732452161885532;
                  } else {
                      var88 = -0.00556024522120491;
                  }
              } else {
                  if (input[4] > 5.857188587559812) {
                      var88 = 0.01468236394554435;
                  } else {
                      var88 = 0.0004552674135973673;
                  }
              }
          }
      }
      var var89;
      if (input[4] <= -8.76737386423564) {
          if (input[13] > 4.500000000000001) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var89 = -0.04481999875765963;
              } else {
                  var89 = 0.0037367323332080926;
              }
          } else {
              var89 = 0.02510798073726917;
          }
      } else {
          if (input[6] <= -10.140707619951096) {
              var89 = 0.019761879584571082;
          } else {
              if (input[2] <= -1.9123784633518905) {
                  var89 = -0.015428116513382231;
              } else {
                  if (input[3] <= -1.5218789267492705) {
                      var89 = 0.00983653288386577;
                  } else {
                      var89 = -0.00003570155088591945;
                  }
              }
          }
      }
      var var90;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[3] <= -0.456609706027228) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 45.23679132112875) {
                      var90 = -0.03424693731309857;
                  } else {
                      var90 = -0.005471085162401311;
                  }
              } else {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var90 = 0.006140463223839564;
                  } else {
                      var90 = -0.002918753057312519;
                  }
              }
          } else {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 17.500000000000004) {
                      var90 = 0.019278611615905786;
                  } else {
                      var90 = 0.00588153695920566;
                  }
              } else {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var90 = 0.008438699237742226;
                  } else {
                      var90 = -0.0013747178054927976;
                  }
              }
          }
      } else {
          if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[5] <= -29.59449508597042) {
                  var90 = 0.04297191942046841;
              } else {
                  if (input[5] > 12.081266055558087) {
                      var90 = 0.0021278084202818164;
                  } else {
                      var90 = -0.016916775825741408;
                  }
              }
          } else {
              if (input[5] > 19.544289135213152) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var90 = -0.008957792326924596;
                  } else {
                      var90 = -0.0011526384984414557;
                  }
              } else {
                  if (input[0] > 45.82856649399955) {
                      var90 = 0.025256557953516;
                  } else {
                      var90 = 0.0009787739235180817;
                  }
              }
          }
      }
      var var91;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[5] > 91.29004180028802) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  var91 = -0.03858534983091423;
              } else {
                  var91 = -0.0017437232394961425;
              }
          } else {
              if (input[6] <= -2.398066420549097) {
                  if (input[10] > 1.5000000000000002) {
                      var91 = -0.01905271966828287;
                  } else {
                      var91 = 0.028663922079403943;
                  }
              } else {
                  if (input[4] <= -0.5762604215079786) {
                      var91 = 0.028459294489214124;
                  } else {
                      var91 = 0.0071375720411214335;
                  }
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[4] > 2.344350703463393) {
                  if (input[4] > 4.912099304131096) {
                      var91 = 0.0015787296090369206;
                  } else {
                      var91 = -0.013884085809322107;
                  }
              } else {
                  if (input[9] > 19.500000000000004) {
                      var91 = 0.012076715978038773;
                  } else {
                      var91 = -0.0018418461397523766;
                  }
              }
          } else {
              if (input[6] > 7.999681113877577) {
                  if (input[2] > 1.8029973656259821) {
                      var91 = 0.020390448169088273;
                  } else {
                      var91 = 0.0009533737070486462;
                  }
              } else {
                  if (input[6] > 5.776823337771391) {
                      var91 = -0.005382952193920446;
                  } else {
                      var91 = 0.0004965800716739504;
                  }
              }
          }
      }
      var var92;
      if (input[38] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 78.73527750225064) {
              var92 = 0.020727458097707784;
          } else {
              if (input[13] > 5.500000000000001) {
                  if (input[6] > 7.1728245343270265) {
                      var92 = 0.013070554312057718;
                  } else {
                      var92 = -0.004677838339286006;
                  }
              } else {
                  if (input[5] > 90.21846040958793) {
                      var92 = 0.019891509422770442;
                  } else {
                      var92 = 0.00012744544817343915;
                  }
              }
          }
      } else {
          if (input[2] > 0.512388466754457) {
              if (input[10] > 1.5000000000000002) {
                  if (input[0] > 37.2807635912475) {
                      var92 = -0.00011515966607323507;
                  } else {
                      var92 = 0.022624306329752073;
                  }
              } else {
                  if (input[5] > 68.36291572247318) {
                      var92 = -0.0007511728359273842;
                  } else {
                      var92 = -0.0145375078783344;
                  }
              }
          } else {
              if (input[6] > 2.5493545797764527) {
                  if (input[4] > 2.344350703463393) {
                      var92 = -0.0007020036660756168;
                  } else {
                      var92 = 0.013925485014555233;
                  }
              } else {
                  if (input[4] > 5.857188587559812) {
                      var92 = 0.019764889101014843;
                  } else {
                      var92 = 0.0001717536175387142;
                  }
              }
          }
      }
      var var93;
      if (input[9] > 3.5000000000000004) {
          if (input[5] > 69.85608617600006) {
              if (input[0] > 47.40082564351635) {
                  if (input[4] > 0.7977856053883731) {
                      var93 = 0.0036798618371920383;
                  } else {
                      var93 = -0.0021888516863590494;
                  }
              } else {
                  var93 = 0.033264344393161505;
              }
          } else {
              if (input[5] > 69.47565045796492) {
                  var93 = -0.02544846035653156;
              } else {
                  if (input[2] > 0.11827058173472725) {
                      var93 = -0.0035313379597726;
                  } else {
                      var93 = 0.000353816901695433;
                  }
              }
          }
      } else {
          if (input[5] > 71.6659331446054) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var93 = 0.025170435938921983;
                  } else {
                      var93 = -0.000653649777572696;
                  }
              } else {
                  if (input[0] > 58.835776428762735) {
                      var93 = -0.004905422971117707;
                  } else {
                      var93 = -0.030818292345998217;
                  }
              }
          } else {
              if (input[4] <= -2.358993777577276) {
                  if (input[3] <= -0.36821412168164397) {
                      var93 = 0.004068115930360004;
                  } else {
                      var93 = 0.01604268426302757;
                  }
              } else {
                  if (input[6] > 7.999681113877577) {
                      var93 = 0.023539378363535937;
                  } else {
                      var93 = 0.00013032086037656046;
                  }
              }
          }
      }
      var var94;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 5.595339644259805) {
              if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                  var94 = 0.02508517215327712;
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var94 = 0.011088334520444047;
                  } else {
                      var94 = -0.003607916263291087;
                  }
              }
          } else {
              if (input[6] > 4.075584176062313) {
                  if (input[4] > 2.420982285794383) {
                      var94 = -0.0021735449081792305;
                  } else {
                      var94 = -0.021323085913533456;
                  }
              } else {
                  if (input[2] > 1.049554179207316) {
                      var94 = 0.013953896960657847;
                  } else {
                      var94 = -0.0030218872948123126;
                  }
              }
          }
      } else {
          if (input[2] > 1.455433865589791) {
              if (input[13] > 10.500000000000002) {
                  var94 = -0.025443267310159053;
              } else {
                  if (input[3] > 1.4918805968895918) {
                      var94 = 0.00678564850206186;
                  } else {
                      var94 = -0.011065230730598532;
                  }
              }
          } else {
              if (input[0] > 75.12713279102289) {
                  if (input[5] > 100.90857751286742) {
                      var94 = -0.005480439022440232;
                  } else {
                      var94 = 0.00941221362271769;
                  }
              } else {
                  if (input[4] > 9.401150856775486) {
                      var94 = 0.017665041460094125;
                  } else {
                      var94 = 0.00005355950058313703;
                  }
              }
          }
      }
      var var95;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[13] > 7.500000000000001) {
                  var95 = 0.029329520158370342;
              } else {
                  var95 = -0.0016380441642325366;
              }
          } else {
              if (input[6] <= -5.20604877356585) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var95 = 0.02215475769532505;
                  } else {
                      var95 = -0.0006895310369630131;
                  }
              } else {
                  if (input[3] <= -0.3045593201210037) {
                      var95 = -0.00524347829334094;
                  } else {
                      var95 = 0.002500694046794133;
                  }
              }
          }
      } else {
          if (input[3] > 0.7595953914765796) {
              if (input[9] > 1.5000000000000002) {
                  if (input[0] > 54.6459680035938) {
                      var95 = -0.002288932093080599;
                  } else {
                      var95 = -0.01255448234565;
                  }
              } else {
                  if (input[6] > 3.535515966166679) {
                      var95 = 0.0028105889990275405;
                  } else {
                      var95 = 0.022533952213708533;
                  }
              }
          } else {
              if (input[5] > 84.62477280480881) {
                  if (input[4] <= -1.3242311696170128) {
                      var95 = -0.0027064104920977205;
                  } else {
                      var95 = 0.006881839985725559;
                  }
              } else {
                  if (input[3] > 0.6747792718973525) {
                      var95 = 0.009995998853780018;
                  } else {
                      var95 = -0.000683649281142876;
                  }
              }
          }
      }
      var var96;
      if (input[4] <= -8.76737386423564) {
          if (input[13] > 4.500000000000001) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var96 = -0.04321905483916711;
              } else {
                  var96 = 0.0035325412257933564;
              }
          } else {
              var96 = 0.02357217557523832;
          }
      } else {
          if (input[6] <= -10.140707619951096) {
              var96 = 0.018564463132099678;
          } else {
              if (input[2] <= -1.9123784633518905) {
                  var96 = -0.014792141673035395;
              } else {
                  if (input[3] <= -1.5218789267492705) {
                      var96 = 0.0093334936487345;
                  } else {
                      var96 = -0.00003381227689014046;
                  }
              }
          }
      }
      var var97;
      if (input[4] <= -2.1729741642181852) {
          if (input[0] > 64.75395318316197) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] > 0.9394337683771994) {
                      var97 = -0.03376661466622185;
                  } else {
                      var97 = -0.007274818442081077;
                  }
              } else {
                  if (input[3] > 0.9933024328533363) {
                      var97 = 0.03026520029820406;
                  } else {
                      var97 = -0.0022355664021078926;
                  }
              }
          } else {
              if (input[2] > 0.9689046583490236) {
                  var97 = 0.035820364062301845;
              } else {
                  if (input[3] > 0.3968921775675264) {
                      var97 = -0.011059600861120695;
                  } else {
                      var97 = 0.002706945738331668;
                  }
              }
          }
      } else {
          if (input[4] <= -0.7791403766304014) {
              if (input[0] > 75.52030211082776) {
                  if (input[3] > 1.184076124812792) {
                      var97 = -0.007911986026943433;
                  } else {
                      var97 = 0.021138557967078843;
                  }
              } else {
                  if (input[2] <= -1.5107108589838323) {
                      var97 = 0.02126204732522693;
                  } else {
                      var97 = -0.005536106778757306;
                  }
              }
          } else {
              if (input[4] <= -0.45083601189522843) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var97 = 0.01600878560629593;
                  } else {
                      var97 = -0.0006633749034708011;
                  }
              } else {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var97 = 0.004741077530770356;
                  } else {
                      var97 = -0.0006331515508972162;
                  }
              }
          }
      }
      var var98;
      if (input[6] <= -2.8521579336286886) {
          if (input[5] > 26.75053527219527) {
              if (input[4] <= -2.0408506225936174) {
                  if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
                      var98 = 0.022966115833129585;
                  } else {
                      var98 = -0.0020093882006104497;
                  }
              } else {
                  if (input[4] > 0.24645920775219482) {
                      var98 = 0.002410815115564816;
                  } else {
                      var98 = -0.015316875172458711;
                  }
              }
          } else {
              if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -0.39477032531299977) {
                      var98 = 0.00712306439015047;
                  } else {
                      var98 = 0.034894423685549514;
                  }
              } else {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var98 = -0.008252788723129172;
                  } else {
                      var98 = 0.0020183223643355243;
                  }
              }
          }
      } else {
          if (input[0] > 17.04845007165648) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 24.0530548127776) {
                      var98 = 0.003468257886058829;
                  } else {
                      var98 = -0.005753604599142586;
                  }
              } else {
                  if (input[5] > 69.85608617600006) {
                      var98 = 0.0011069294737529004;
                  } else {
                      var98 = -0.0018734469988837732;
                  }
              }
          } else {
              var98 = 0.020439049696913014;
          }
      }
      var var99;
      if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 5.595339644259805) {
              if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                  var99 = 0.023564385417903806;
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var99 = 0.010475168222769542;
                  } else {
                      var99 = -0.0034305939069031763;
                  }
              }
          } else {
              if (input[6] > 4.075584176062313) {
                  if (input[4] > 2.420982285794383) {
                      var99 = -0.0021338481305500103;
                  } else {
                      var99 = -0.020526918815941344;
                  }
              } else {
                  if (input[2] > 1.049554179207316) {
                      var99 = 0.01280166708016254;
                  } else {
                      var99 = -0.002969106287690794;
                  }
              }
          }
      } else {
          if (input[2] > 1.455433865589791) {
              if (input[13] > 10.500000000000002) {
                  var99 = -0.02446694933330601;
              } else {
                  if (input[3] > 1.442442771255717) {
                      var99 = 0.0049531392462145015;
                  } else {
                      var99 = -0.012351159006231153;
                  }
              }
          } else {
              if (input[9] > 20.500000000000004) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var99 = -0.0032919488591239584;
                  } else {
                      var99 = 0.004062855266856405;
                  }
              } else {
                  if (input[0] > 86.25101283547333) {
                      var99 = -0.01449194656443565;
                  } else {
                      var99 = 0.00005845980740102465;
                  }
              }
          }
      }
      var var100;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[5] > 91.29004180028802) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  var100 = -0.037387662571072816;
              } else {
                  var100 = -0.0018481940047519831;
              }
          } else {
              if (input[10] > 3.5000000000000004) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var100 = 0.018138319715774325;
                  } else {
                      var100 = -0.019394470944944023;
                  }
              } else {
                  if (input[6] > 2.4034644482157037) {
                      var100 = 0.04284624851722091;
                  } else {
                      var100 = 0.005249174631022011;
                  }
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] > 1.0518052223976289) {
                  if (input[0] > 63.47585974173415) {
                      var100 = 0.0012115083135251818;
                  } else {
                      var100 = -0.0126182582089766;
                  }
              } else {
                  if (input[9] > 21.500000000000004) {
                      var100 = 0.020911835288898263;
                  } else {
                      var100 = -0.0007148124639868828;
                  }
              }
          } else {
              if (input[0] > 22.56849409934883) {
                  if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                      var100 = 0.006027242088280332;
                  } else {
                      var100 = 0.0002602393836766635;
                  }
              } else {
                  if (input[9] > 12.500000000000002) {
                      var100 = -0.010208739393149816;
                  } else {
                      var100 = 0.0038945730409122633;
                  }
              }
          }
      }
      var var101;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[3] <= -0.456609706027228) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 2.5000000000000004) {
                      var101 = -0.00045010589119006815;
                  } else {
                      var101 = -0.014636845417141484;
                  }
              } else {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var101 = 0.005746412738718462;
                  } else {
                      var101 = -0.0027601204910064764;
                  }
              }
          } else {
              if (input[9] > 17.500000000000004) {
                  if (input[3] > 0.5003486707332836) {
                      var101 = -0.01182302435751486;
                  } else {
                      var101 = 0.011563336688778283;
                  }
              } else {
                  if (input[0] > 39.82089512340189) {
                      var101 = -0.0009911664685086383;
                  } else {
                      var101 = 0.01268306624950236;
                  }
              }
          }
      } else {
          if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[5] <= -29.59449508597042) {
                  var101 = 0.04046763808665768;
              } else {
                  if (input[5] > 12.081266055558087) {
                      var101 = 0.001983444160158407;
                  } else {
                      var101 = -0.01576951883246899;
                  }
              }
          } else {
              if (input[5] > 19.544289135213152) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var101 = -0.008479680899417643;
                  } else {
                      var101 = -0.0010750004930558362;
                  }
              } else {
                  if (input[0] > 45.82856649399955) {
                      var101 = 0.023787112895494775;
                  } else {
                      var101 = 0.0008814853293153875;
                  }
              }
          }
      }
      var var102;
      if (input[4] > 4.912099304131096) {
          if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[2] > 0.5035640840959066) {
                  var102 = -0.02705673403321564;
              } else {
                  var102 = 0.0025691184048060303;
              }
          } else {
              if (input[14] > 0.000000000000000000000000000000000010000000180025095) {
                  var102 = 0.02497159447019908;
              } else {
                  if (input[6] > 3.1102826167205437) {
                      var102 = 0.0003217394503170952;
                  } else {
                      var102 = 0.008053905723926086;
                  }
              }
          }
      } else {
          if (input[4] > 4.21339422970748) {
              if (input[9] > 3.5000000000000004) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var102 = -0.002318114459838299;
                  } else {
                      var102 = -0.015480743867676736;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var102 = 0.018807090114029718;
                  } else {
                      var102 = -0.003202387182301761;
                  }
              }
          } else {
              if (input[4] > 3.2032943389782225) {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var102 = 0.017415661718852476;
                  } else {
                      var102 = 0.00094496916898305;
                  }
              } else {
                  if (input[4] > 2.1419746152525203) {
                      var102 = -0.004223972186601261;
                  } else {
                      var102 = 0.0003171325405237406;
                  }
              }
          }
      }
      var var103;
      if (input[5] > 117.01558275614404) {
          if (input[0] > 64.25004156967033) {
              if (input[6] <= -0.22802093153587424) {
                  var103 = -0.03170222086714028;
              } else {
                  if (input[9] > 11.500000000000002) {
                      var103 = 0.014249324795193731;
                  } else {
                      var103 = -0.0008855494780611447;
                  }
              }
          } else {
              if (input[6] > 2.7021091197227185) {
                  var103 = 0.008898739689245578;
              } else {
                  var103 = 0.033761077001929644;
              }
          }
      } else {
          if (input[5] > 100.90857751286742) {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  var103 = -0.03602368512431527;
              } else {
                  if (input[4] > 0.3243098842649636) {
                      var103 = 0.0013405712798134168;
                  } else {
                      var103 = -0.00938832926965966;
                  }
              }
          } else {
              if (input[0] > 75.9664238348739) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var103 = 0.01256229304286592;
                  } else {
                      var103 = -0.004807188609436296;
                  }
              } else {
                  if (input[6] > 10.31060103068119) {
                      var103 = 0.019033570272039835;
                  } else {
                      var103 = -0.00014976884385922628;
                  }
              }
          }
      }
      var var104;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 0.9715869529760879) {
              if (input[4] > 1.7160674285510085) {
                  var104 = 0.0021573544837184613;
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var104 = -0.008475526664844135;
                  } else {
                      var104 = 0.023057201229309904;
                  }
              }
          } else {
              if (input[4] <= -0.4950921444997715) {
                  if (input[4] <= -1.0376436871914176) {
                      var104 = 0.0009165250512932814;
                  } else {
                      var104 = 0.01877110009202128;
                  }
              } else {
                  if (input[2] > 1.0016590802373793) {
                      var104 = 0.01236331440456303;
                  } else {
                      var104 = -0.012655525799475667;
                  }
              }
          }
      } else {
          if (input[6] <= -4.495641208044259) {
              if (input[2] <= -0.18032876532877087) {
                  if (input[5] > 74.32437252525206) {
                      var104 = -0.02508567116276733;
                  } else {
                      var104 = -0.0023822711592743576;
                  }
              } else {
                  if (input[5] > 42.90242520060247) {
                      var104 = 0.0007045866451459765;
                  } else {
                      var104 = 0.035803541780267636;
                  }
              }
          } else {
              if (input[2] <= -0.2707003273254145) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var104 = -0.0012219938749763815;
                  } else {
                      var104 = 0.006641858264507149;
                  }
              } else {
                  if (input[2] <= -0.17292263602242408) {
                      var104 = -0.008702555064659586;
                  } else {
                      var104 = -0.00015765305599802556;
                  }
              }
          }
      }
      var var105;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[5] > 91.29004180028802) {
              if (input[0] > 68.17050522965086) {
                  var105 = 0.004927683126145455;
              } else {
                  var105 = -0.032017902994858675;
              }
          } else {
              if (input[13] > 6.500000000000001) {
                  if (input[10] > 2.5000000000000004) {
                      var105 = 0.0034009325751271254;
                  } else {
                      var105 = 0.029845360658049554;
                  }
              } else {
                  if (input[6] <= -1.776493203275405) {
                      var105 = -0.020866764129243907;
                  } else {
                      var105 = 0.009356755066810987;
                  }
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[4] > 2.224830200500726) {
                  if (input[4] > 4.912099304131096) {
                      var105 = 0.0016742068747891718;
                  } else {
                      var105 = -0.01246762218767181;
                  }
              } else {
                  if (input[20] > 0.000000000000000000000000000000000010000000180025095) {
                      var105 = 0.010662899173926575;
                  } else {
                      var105 = -0.0015700723483122086;
                  }
              }
          } else {
              if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 3.5000000000000004) {
                      var105 = -0.00016084174501002985;
                  } else {
                      var105 = 0.017289872142222558;
                  }
              } else {
                  if (input[2] <= -1.5649334836593047) {
                      var105 = -0.006811282491696572;
                  } else {
                      var105 = 0.00011748034424865474;
                  }
              }
          }
      }
      var var106;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[2] <= -0.1375084104867184) {
              if (input[0] > 65.68848758464974) {
                  if (input[4] <= -2.4525000035043685) {
                      var106 = -0.009331698817268;
                  } else {
                      var106 = -0.03694864938263292;
                  }
              } else {
                  if (input[0] > 63.24679684411505) {
                      var106 = 0.02762818316527993;
                  } else {
                      var106 = -0.00042101817326391515;
                  }
              }
          } else {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 31.984859074255873) {
                      var106 = -0.00565341587893375;
                  } else {
                      var106 = 0.012495878501411737;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var106 = 0.013556182182017436;
                  } else {
                      var106 = 0.00003071124017429089;
                  }
              }
          }
      } else {
          if (input[2] <= -0.2707003273254145) {
              if (input[5] > 83.75558925058311) {
                  if (input[6] <= -3.7039309301055208) {
                      var106 = -0.0009682456996872301;
                  } else {
                      var106 = 0.03682653070171265;
                  }
              } else {
                  if (input[0] > 56.207921219246124) {
                      var106 = -0.012300856771312992;
                  } else {
                      var106 = 0.0017140721238466787;
                  }
              }
          } else {
              if (input[2] <= -0.18032876532877087) {
                  var106 = -0.010385175096635913;
              } else {
                  if (input[6] <= -4.032321514980188) {
                      var106 = 0.015218956348299199;
                  } else {
                      var106 = -0.0007016952870217436;
                  }
              }
          }
      }
      var var107;
      if (input[4] <= -8.76737386423564) {
          if (input[13] > 4.500000000000001) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var107 = -0.041738344255270704;
              } else {
                  var107 = 0.00319511739387604;
              }
          } else {
              var107 = 0.02217960446881972;
          }
      } else {
          if (input[6] <= -10.140707619951096) {
              var107 = 0.0174642058442012;
          } else {
              if (input[2] <= -1.9123784633518905) {
                  var107 = -0.013842913912175748;
              } else {
                  if (input[3] <= -1.5218789267492705) {
                      var107 = 0.009041557681334933;
                  } else {
                      var107 = -0.00003409441749062494;
                  }
              }
          }
      }
      var var108;
      if (input[6] <= -2.8521579336286886) {
          if (input[4] <= -2.0004379047689356) {
              if (input[5] > 42.4312767999516) {
                  if (input[10] > 1.5000000000000002) {
                      var108 = -0.007666107453512439;
                  } else {
                      var108 = 0.006413044857615072;
                  }
              } else {
                  if (input[6] <= -3.122412304470862) {
                      var108 = 0.004205578676136975;
                  } else {
                      var108 = -0.020823658125953895;
                  }
              }
          } else {
              if (input[4] <= -0.03399001277826245) {
                  if (input[2] <= -1.5649334836593047) {
                      var108 = 0.017476573117742825;
                  } else {
                      var108 = -0.010145621816793857;
                  }
              } else {
                  if (input[6] <= -5.117681189325094) {
                      var108 = -0.013037904165965326;
                  } else {
                      var108 = 0.005889580319273907;
                  }
              }
          }
      } else {
          if (input[0] > 17.04845007165648) {
              if (input[2] <= -1.1180532839378696) {
                  var108 = -0.023476335522158404;
              } else {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var108 = 0.002238197152021287;
                  } else {
                      var108 = -0.00042654673901491164;
                  }
              }
          } else {
              var108 = 0.01924523961603863;
          }
      }
      var var109;
      if (input[2] > 0.22406346109460493) {
          if (input[0] > 52.06853502461072) {
              if (input[5] > 38.40608426400883) {
                  if (input[13] > 1.5000000000000002) {
                      var109 = -0.0006848924727198973;
                  } else {
                      var109 = 0.007326277511909921;
                  }
              } else {
                  var109 = 0.02425355489090668;
              }
          } else {
              if (input[4] <= -1.608899516503428) {
                  if (input[4] <= -1.8768784815380142) {
                      var109 = 0.0014998707409873023;
                  } else {
                      var109 = 0.0381722953233538;
                  }
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var109 = -0.011508015715096978;
                  } else {
                      var109 = -0.0008018813301003502;
                  }
              }
          }
      } else {
          if (input[6] > 2.5493545797764527) {
              if (input[13] > 1.5000000000000002) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var109 = 0.027166984416158314;
                  } else {
                      var109 = 0.006173925921577215;
                  }
              } else {
                  var109 = -0.02303736653074118;
              }
          } else {
              if (input[0] > 65.44503760026167) {
                  if (input[5] > 67.1617636323384) {
                      var109 = -0.004812560648925624;
                  } else {
                      var109 = -0.026759864821110976;
                  }
              } else {
                  if (input[5] > 117.01558275614404) {
                      var109 = 0.02790725220080147;
                  } else {
                      var109 = 0.0004505276719086391;
                  }
              }
          }
      }
      var var110;
      if (input[9] > 3.5000000000000004) {
          if (input[5] > 69.85608617600006) {
              if (input[0] > 47.40082564351635) {
                  if (input[4] > 0.7977856053883731) {
                      var110 = 0.0033763490278527473;
                  } else {
                      var110 = -0.0019530190720618967;
                  }
              } else {
                  var110 = 0.03110054499696578;
              }
          } else {
              if (input[5] > 69.47565045796492) {
                  var110 = -0.024341365390015236;
              } else {
                  if (input[2] > 0.025809299484776383) {
                      var110 = -0.0030400747123482483;
                  } else {
                      var110 = 0.00044046470521359;
                  }
              }
          }
      } else {
          if (input[5] > 71.6659331446054) {
              if (input[4] <= -2.301314617351657) {
                  if (input[0] > 60.256910276410956) {
                      var110 = -0.005649667271082495;
                  } else {
                      var110 = -0.03934930868523753;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var110 = 0.027321157833600743;
                  } else {
                      var110 = -0.0040824573804315745;
                  }
              }
          } else {
              if (input[5] > 69.10005212074935) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var110 = 0.006180289258882667;
                  } else {
                      var110 = 0.031847105762724474;
                  }
              } else {
                  if (input[0] > 66.95627012882493) {
                      var110 = -0.02056050349987476;
                  } else {
                      var110 = 0.0035746360731154997;
                  }
              }
          }
      }
      var var111;
      if (input[2] > 1.2449878458998531) {
          if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[9] > 18.500000000000004) {
                  var111 = -0.025333020214929405;
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var111 = -0.017895125084148523;
                  } else {
                      var111 = 0.0036458432679287653;
                  }
              }
          } else {
              if (input[43] > 0.000000000000000000000000000000000010000000180025095) {
                  var111 = -0.02137391691971804;
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var111 = 0.013163755830182125;
                  } else {
                      var111 = -0.004180179532721011;
                  }
              }
          }
      } else {
          if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[10] > 3.5000000000000004) {
                  if (input[13] > 5.500000000000001) {
                      var111 = -0.005181473435791041;
                  } else {
                      var111 = 0.01060115837926784;
                  }
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var111 = -0.010341669153753494;
                  } else {
                      var111 = 0.00011870802682736092;
                  }
              }
          } else {
              if (input[0] > 75.52030211082776) {
                  if (input[5] > 100.90857751286742) {
                      var111 = -0.005539321312467669;
                  } else {
                      var111 = 0.011971252479876567;
                  }
              } else {
                  if (input[4] > 9.401150856775486) {
                      var111 = 0.015224751330679284;
                  } else {
                      var111 = 0.00008255088849482429;
                  }
              }
          }
      }
      var var112;
      if (input[38] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 78.73527750225064) {
              var112 = 0.018649262705478432;
          } else {
              if (input[13] > 5.500000000000001) {
                  if (input[6] > 7.1728245343270265) {
                      var112 = 0.012465284795282847;
                  } else {
                      var112 = -0.00434331817054532;
                  }
              } else {
                  if (input[5] > 90.21846040958793) {
                      var112 = 0.01825387436762716;
                  } else {
                      var112 = 0.00016762483484620172;
                  }
              }
          }
      } else {
          if (input[2] > 0.512388466754457) {
              if (input[10] > 1.5000000000000002) {
                  if (input[0] > 37.2807635912475) {
                      var112 = -0.00008881887396551136;
                  } else {
                      var112 = 0.021638018342587075;
                  }
              } else {
                  if (input[5] > 68.36291572247318) {
                      var112 = -0.0007712290223637952;
                  } else {
                      var112 = -0.013642029466604665;
                  }
              }
          } else {
              if (input[0] > 31.776869407021277) {
                  if (input[13] > 9.500000000000002) {
                      var112 = 0.0036438631879595774;
                  } else {
                      var112 = 0.0006023017593461354;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var112 = -0.006724214528116919;
                  } else {
                      var112 = 0.0016544741432171321;
                  }
              }
          }
      }
      var var113;
      if (input[9] > 18.500000000000004) {
          if (input[0] > 41.4508936947301) {
              if (input[5] > 28.31217988396433) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var113 = -0.002631269308092826;
                  } else {
                      var113 = 0.004224589098597403;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var113 = 0.034573084474418335;
                  } else {
                      var113 = 0.005387411364010808;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 19.14508537197081) {
                      var113 = -0.012956678395305277;
                  } else {
                      var113 = 0.0033495986906587048;
                  }
              } else {
                  if (input[4] > 0.8364726566893431) {
                      var113 = -0.00948553206291578;
                  } else {
                      var113 = 0.010367493622709946;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[10] > 2.5000000000000004) {
                  if (input[5] > 70.6027148026618) {
                      var113 = 0.005323603419486948;
                  } else {
                      var113 = -0.003397217677263486;
                  }
              } else {
                  if (input[6] <= -2.398066420549097) {
                      var113 = -0.014664236222379163;
                  } else {
                      var113 = -0.0030101472680622806;
                  }
              }
          } else {
              if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] > 1.0611995407922705) {
                      var113 = -0.030936503396173543;
                  } else {
                      var113 = 0.0047632772339942855;
                  }
              } else {
                  var113 = -0.00007923814069060633;
              }
          }
      }
      var var114;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -7.123374703856836) {
              var114 = -0.013632883858387285;
          } else {
              if (input[13] > 3.5000000000000004) {
                  if (input[4] > 5.322105873571434) {
                      var114 = 0.015341217871694433;
                  } else {
                      var114 = 0.0022986674261055128;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var114 = -0.011342664949914098;
                  } else {
                      var114 = 0.0033001923158892488;
                  }
              }
          }
      } else {
          if (input[3] > 0.7595953914765796) {
              if (input[9] > 1.5000000000000002) {
                  if (input[6] > 3.4821968878924623) {
                      var114 = -0.0013868512400954415;
                  } else {
                      var114 = -0.007666294850824965;
                  }
              } else {
                  if (input[6] > 3.535515966166679) {
                      var114 = 0.0029046830104155394;
                  } else {
                      var114 = 0.02140427495406882;
                  }
              }
          } else {
              if (input[0] > 67.17230718398928) {
                  if (input[5] > 61.34338824862519) {
                      var114 = 0.006221246773876067;
                  } else {
                      var114 = -0.03585854288170254;
                  }
              } else {
                  if (input[0] > 65.68848758464974) {
                      var114 = -0.010345876767976952;
                  } else {
                      var114 = -0.0001273598444257685;
                  }
              }
          }
      }
      var var115;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[5] > 91.29004180028802) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  var115 = -0.03515930011620432;
              } else {
                  var115 = -0.0006715835650497803;
              }
          } else {
              if (input[0] > 27.469470602855804) {
                  if (input[13] > 4.500000000000001) {
                      var115 = 0.015102385724494592;
                  } else {
                      var115 = -0.0074406164052546785;
                  }
              } else {
                  var115 = -0.02675952212320193;
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] > 1.0518052223976289) {
                  if (input[0] > 42.99808218486713) {
                      var115 = -0.004335518028227661;
                  } else {
                      var115 = -0.023192557981694756;
                  }
              } else {
                  if (input[9] > 21.500000000000004) {
                      var115 = 0.019751750423206517;
                  } else {
                      var115 = -0.0005998409451400356;
                  }
              }
          } else {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -1.1940748965409262) {
                      var115 = -0.010175793998782639;
                  } else {
                      var115 = 0.001973686618689438;
                  }
              } else {
                  if (input[6] <= -5.649766231839755) {
                      var115 = 0.005412920641309368;
                  } else {
                      var115 = -0.0008902239433669246;
                  }
              }
          }
      }
      var var116;
      if (input[53] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[13] > 8.500000000000002) {
              var116 = 0.022612335193959235;
          } else {
              if (input[0] > 54.6459680035938) {
                  var116 = 0.016501340327926974;
              } else {
                  var116 = -0.012433977037824133;
              }
          }
      } else {
          if (input[9] > 3.5000000000000004) {
              if (input[9] > 8.500000000000002) {
                  if (input[5] > 139.46276228269554) {
                      var116 = 0.02211084461499703;
                  } else {
                      var116 = 0.00008214177079513671;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var116 = -0.004682137609098836;
                  } else {
                      var116 = 0.00017530057947975658;
                  }
              }
          } else {
              if (input[5] > 71.6659331446054) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var116 = 0.003615824505171203;
                  } else {
                      var116 = -0.010583978276959291;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var116 = 0.008116430226514655;
                  } else {
                      var116 = 0.0008598560308622485;
                  }
              }
          }
      }
      var var117;
      if (input[6] <= -2.8521579336286886) {
          if (input[4] > 3.517091252060496) {
              var117 = 0.0264102247973693;
          } else {
              if (input[4] <= -2.0004379047689356) {
                  if (input[5] > 42.4312767999516) {
                      var117 = -0.004144188514644905;
                  } else {
                      var117 = 0.0031638965069582317;
                  }
              } else {
                  if (input[4] <= -0.9355679102052262) {
                      var117 = -0.010504917693195025;
                  } else {
                      var117 = -0.0015746032273373592;
                  }
              }
          }
      } else {
          if (input[0] > 16.043665124941132) {
              if (input[2] <= -1.1180532839378696) {
                  var117 = -0.02234121594606374;
              } else {
                  if (input[2] <= -0.3112421825088057) {
                      var117 = 0.0031146516403588813;
                  } else {
                      var117 = -0.00019700788607896632;
                  }
              }
          } else {
              var117 = 0.02034455217309575;
          }
      }
      var var118;
      if (input[4] <= -8.76737386423564) {
          if (input[13] > 4.500000000000001) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var118 = -0.04015922322015568;
              } else {
                  var118 = 0.0028241516627786956;
              }
          } else {
              var118 = 0.02138177074692492;
          }
      } else {
          if (input[6] <= -10.140707619951096) {
              var118 = 0.01623137019213375;
          } else {
              if (input[2] <= -1.9123784633518905) {
                  var118 = -0.013318799878147795;
              } else {
                  if (input[3] <= -1.5218789267492705) {
                      var118 = 0.008666181370514123;
                  } else {
                      var118 = -0.00003306496640943793;
                  }
              }
          }
      }
      var var119;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[13] > 7.500000000000001) {
                  var119 = 0.027221256077770196;
              } else {
                  var119 = -0.0016453172468476583;
              }
          } else {
              if (input[6] > 8.281812040067665) {
                  var119 = 0.012661663789887916;
              } else {
                  if (input[0] > 56.39396172574019) {
                      var119 = -0.002466768035735342;
                  } else {
                      var119 = 0.0026756048245844023;
                  }
              }
          }
      } else {
          if (input[6] <= -4.495641208044259) {
              if (input[2] <= -0.18032876532877087) {
                  if (input[5] > 74.32437252525206) {
                      var119 = -0.023415817821463264;
                  } else {
                      var119 = -0.002274625806036262;
                  }
              } else {
                  if (input[4] <= -6.711865554587188) {
                      var119 = 0.037375912520386655;
                  } else {
                      var119 = 0.004147334021030048;
                  }
              }
          } else {
              if (input[2] <= -0.2707003273254145) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var119 = -0.0011262177625076474;
                  } else {
                      var119 = 0.00609895095511085;
                  }
              } else {
                  if (input[3] <= -0.2072500793613881) {
                      var119 = -0.00826679844111998;
                  } else {
                      var119 = -0.00012828315154737532;
                  }
              }
          }
      }
      var var120;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[5] > 91.29004180028802) {
              if (input[0] > 68.17050522965086) {
                  var120 = 0.00517686573482057;
              } else {
                  var120 = -0.030467689665908;
              }
          } else {
              if (input[0] > 27.469470602855804) {
                  if (input[13] > 6.500000000000001) {
                      var120 = 0.01718786781260294;
                  } else {
                      var120 = -0.0020713572252300046;
                  }
              } else {
                  var120 = -0.025729674821625217;
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[0] > 13.23529411764625) {
                  if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
                      var120 = 0.014224551915991812;
                  } else {
                      var120 = -0.003404509933038294;
                  }
              } else {
                  var120 = 0.025102787926929285;
              }
          } else {
              if (input[0] > 22.56849409934883) {
                  if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                      var120 = 0.005594591122418249;
                  } else {
                      var120 = 0.00022076428064955265;
                  }
              } else {
                  if (input[9] > 12.500000000000002) {
                      var120 = -0.009695079943739797;
                  } else {
                      var120 = 0.0035817422520835127;
                  }
              }
          }
      }
      var var121;
      if (input[5] > 117.01558275614404) {
          if (input[0] > 64.25004156967033) {
              if (input[6] <= -0.22802093153587424) {
                  var121 = -0.030419516835606578;
              } else {
                  if (input[9] > 11.500000000000002) {
                      var121 = 0.013280889697373958;
                  } else {
                      var121 = -0.000973970163636749;
                  }
              }
          } else {
              if (input[6] > 2.7021091197227185) {
                  var121 = 0.008609248541658898;
              } else {
                  var121 = 0.030917101737058097;
              }
          }
      } else {
          if (input[5] > 100.90857751286742) {
              if (input[0] > 72.4839286421002) {
                  if (input[3] > 0.49090892248369816) {
                      var121 = -0.007416696028777365;
                  } else {
                      var121 = -0.03382710567621457;
                  }
              } else {
                  if (input[4] <= -0.23350208572016248) {
                      var121 = -0.007859352158877723;
                  } else {
                      var121 = 0.004681391237950696;
                  }
              }
          } else {
              if (input[0] > 75.9664238348739) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var121 = 0.011472142421895898;
                  } else {
                      var121 = -0.004483012208955553;
                  }
              } else {
                  if (input[6] > 10.31060103068119) {
                      var121 = 0.017823478836491886;
                  } else {
                      var121 = -0.00013917303319723462;
                  }
              }
          }
      }
      var var122;
      if (input[2] > 1.2449878458998531) {
          if (input[13] > 7.500000000000001) {
              if (input[4] > 1.499734792503489) {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var122 = 0.02738338847222603;
                  } else {
                      var122 = 0.003591039500608725;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var122 = -0.035273672308780875;
                  } else {
                      var122 = 0.007098419319888061;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 85.12950162034976) {
                      var122 = -0.011107152007575435;
                  } else {
                      var122 = 0.013204611123011974;
                  }
              } else {
                  if (input[6] > 8.281812040067665) {
                      var122 = 0.009912077531527303;
                  } else {
                      var122 = -0.018874078354324777;
                  }
              }
          }
      } else {
          if (input[6] > 2.5493545797764527) {
              if (input[0] > 45.43848929792071) {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var122 = 0.01892230924397487;
                  } else {
                      var122 = 0.0019725123037161586;
                  }
              } else {
                  if (input[4] <= -0.4950921444997715) {
                      var122 = 0.023801900955854466;
                  } else {
                      var122 = -0.007810949484571811;
                  }
              }
          } else {
              if (input[4] > 5.857188587559812) {
                  if (input[2] <= -0.0181999008563946) {
                      var122 = 0.00734558163857095;
                  } else {
                      var122 = 0.03736126738646154;
                  }
              } else {
                  var122 = -0.0004466526599650258;
              }
          }
      }
      var var123;
      if (input[2] > 0.22406346109460493) {
          if (input[0] > 52.06853502461072) {
              if (input[5] > 40.99339472366089) {
                  if (input[13] > 1.5000000000000002) {
                      var123 = -0.0007642674447047885;
                  } else {
                      var123 = 0.007148767154375727;
                  }
              } else {
                  if (input[0] > 54.086174802343216) {
                      var123 = -0.003374387060309722;
                  } else {
                      var123 = 0.036003299550073;
                  }
              }
          } else {
              if (input[10] > 2.5000000000000004) {
                  if (input[4] > 2.508196128766592) {
                      var123 = -0.016238979296476743;
                  } else {
                      var123 = -0.0009670070406361573;
                  }
              } else {
                  if (input[4] > 6.425942734112858) {
                      var123 = 0.017853882221842737;
                  } else {
                      var123 = -0.0013097130200276311;
                  }
              }
          }
      } else {
          if (input[6] > 2.5493545797764527) {
              if (input[13] > 1.5000000000000002) {
                  if (input[13] > 7.500000000000001) {
                      var123 = 0.001110302404844081;
                  } else {
                      var123 = 0.018882024740465516;
                  }
              } else {
                  var123 = -0.02196682414750653;
              }
          } else {
              if (input[0] > 65.44503760026167) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var123 = -0.02440670080252258;
                  } else {
                      var123 = -0.004297542060460107;
                  }
              } else {
                  if (input[5] > 117.01558275614404) {
                      var123 = 0.025690192891678527;
                  } else {
                      var123 = 0.0004132057973237223;
                  }
              }
          }
      }
      var var124;
      if (input[4] <= -2.1729741642181852) {
          if (input[4] <= -2.548569004413761) {
              if (input[3] > 0.4044684408354277) {
                  if (input[2] > 0.8418977577725816) {
                      var124 = 0.006123910750804333;
                  } else {
                      var124 = -0.010599680329659487;
                  }
              } else {
                  if (input[0] > 25.51590802753186) {
                      var124 = 0.0019881070984286587;
                  } else {
                      var124 = -0.006151734514219281;
                  }
              }
          } else {
              if (input[6] > 2.1601279316659814) {
                  var124 = 0.031786461094751674;
              } else {
                  if (input[2] > 0.1103185485014367) {
                      var124 = -0.009547536860299324;
                  } else {
                      var124 = 0.009093879761412158;
                  }
              }
          }
      } else {
          if (input[4] <= -0.7791403766304014) {
              if (input[2] <= -1.5107108589838323) {
                  var124 = 0.020246794457067646;
              } else {
                  if (input[6] <= -4.4242046780646325) {
                      var124 = -0.013598140721048375;
                  } else {
                      var124 = -0.002599679345581712;
                  }
              }
          } else {
              if (input[4] <= -0.45083601189522843) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var124 = 0.015145686479912702;
                  } else {
                      var124 = -0.000625058149965108;
                  }
              } else {
                  if (input[6] <= -5.117681189325094) {
                      var124 = -0.011658751352773541;
                  } else {
                      var124 = 0.0002475646281881554;
                  }
              }
          }
      }
      var var125;
      if (input[3] > 0.5298948855459753) {
          if (input[5] > 35.25256113656712) {
              if (input[6] > 3.42896965457881) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var125 = -0.0035069270918421363;
                  } else {
                      var125 = 0.0029268753640234696;
                  }
              } else {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var125 = -0.012993713838222273;
                  } else {
                      var125 = -0.0018585185940104536;
                  }
              }
          } else {
              if (input[10] > 2.5000000000000004) {
                  var125 = -0.03958617584171127;
              } else {
                  var125 = 0.01183317432736776;
              }
          }
      } else {
          if (input[5] > 85.56957722496706) {
              if (input[3] <= -0.3772860596208332) {
                  var125 = 0.03305384227878529;
              } else {
                  if (input[4] <= -4.71024479799365) {
                      var125 = -0.012346778489019898;
                  } else {
                      var125 = 0.0046611539700190455;
                  }
              }
          } else {
              if (input[4] > 2.0913098704508557) {
                  if (input[10] > 2.5000000000000004) {
                      var125 = -0.005492258281235772;
                  } else {
                      var125 = 0.002082170418314005;
                  }
              } else {
                  if (input[6] > 2.5493545797764527) {
                      var125 = 0.01009211704782;
                  } else {
                      var125 = 0.00019813730238561766;
                  }
              }
          }
      }
      var var126;
      if (input[9] > 4.500000000000001) {
          if (input[4] > 6.995147082128496) {
              if (input[9] > 17.500000000000004) {
                  if (input[0] > 52.89417697841084) {
                      var126 = -0.005579216466396352;
                  } else {
                      var126 = 0.03157734894753574;
                  }
              } else {
                  if (input[6] > 8.281812040067665) {
                      var126 = -0.00025806729625840605;
                  } else {
                      var126 = -0.02460850008796927;
                  }
              }
          } else {
              if (input[4] > 6.789481691669448) {
                  var126 = 0.0176389069428983;
              } else {
                  if (input[2] > 1.3853947133785054) {
                      var126 = -0.007170551176455176;
                  } else {
                      var126 = -0.0000036795921044536103;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var126 = -0.03237427536656814;
                  } else {
                      var126 = -0.004190734777478155;
                  }
              } else {
                  if (input[0] > 74.32747876777766) {
                      var126 = 0.012320971900163472;
                  } else {
                      var126 = -0.002132967129859039;
                  }
              }
          } else {
              if (input[6] > 0.9224363701183542) {
                  if (input[4] <= -1.7220934315061662) {
                      var126 = 0.0165679385736993;
                  } else {
                      var126 = -0.0020716632440283735;
                  }
              } else {
                  if (input[2] <= -0.08564682271653988) {
                      var126 = 0.002693545038883251;
                  } else {
                      var126 = 0.01936746477106697;
                  }
              }
          }
      }
      var var127;
      if (input[38] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 78.73527750225064) {
              var127 = 0.01716220150365196;
          } else {
              if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
                  var127 = 0.012675849522597763;
              } else {
                  if (input[4] <= -0.5762604215079786) {
                      var127 = -0.004800621870203689;
                  } else {
                      var127 = -0.000045954350922073925;
                  }
              }
          }
      } else {
          if (input[3] > 0.4535255126752083) {
              if (input[5] > 46.93129976544811) {
                  if (input[9] > 10.500000000000002) {
                      var127 = -0.0023487128850490017;
                  } else {
                      var127 = 0.002392839900867371;
                  }
              } else {
                  if (input[4] > 4.452431186048718) {
                      var127 = 0.004699900654007942;
                  } else {
                      var127 = -0.016205728493372623;
                  }
              }
          } else {
              if (input[5] > 83.75558925058311) {
                  if (input[9] > 16.500000000000004) {
                      var127 = 0.015106441127188595;
                  } else {
                      var127 = 0.001219857262449566;
                  }
              } else {
                  if (input[5] > 78.83530520526448) {
                      var127 = -0.00792283948813409;
                  } else {
                      var127 = 0.0005283311777642366;
                  }
              }
          }
      }
      var var128;
      if (input[13] > 10.500000000000002) {
          if (input[5] > 91.91928172844878) {
              if (input[0] > 60.05785347067239) {
                  if (input[6] > 2.2593951888407307) {
                      var128 = -0.012221151694797264;
                  } else {
                      var128 = 0.003099867558227619;
                  }
              } else {
                  var128 = -0.03350547639859191;
              }
          } else {
              if (input[5] > 86.97895198216605) {
                  if (input[2] > 0.3659824905916446) {
                      var128 = 0.006936295916212355;
                  } else {
                      var128 = 0.0481382034956549;
                  }
              } else {
                  if (input[14] > 0.000000000000000000000000000000000010000000180025095) {
                      var128 = 0.02034075541199983;
                  } else {
                      var128 = -0.0015260163563914097;
                  }
              }
          }
      } else {
          if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[4] > 6.995147082128496) {
                  var128 = -0.017441887992537736;
              } else {
                  if (input[4] > 5.244537663167775) {
                      var128 = 0.019377434127669;
                  } else {
                      var128 = 0.0014644959599497886;
                  }
              }
          } else {
              if (input[3] > 1.4918805968895918) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var128 = -0.0072334888178404045;
                  } else {
                      var128 = 0.014176795895729014;
                  }
              } else {
                  if (input[9] > 21.500000000000004) {
                      var128 = 0.0034293987973301196;
                  } else {
                      var128 = -0.000937591053263592;
                  }
              }
          }
      }
      var var129;
      if (input[53] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[13] > 8.500000000000002) {
              var129 = 0.021300790070729422;
          } else {
              if (input[0] > 54.6459680035938) {
                  var129 = 0.015613662582557856;
              } else {
                  var129 = -0.011893770239690338;
              }
          }
      } else {
          if (input[13] > 10.500000000000002) {
              if (input[5] > 91.91928172844878) {
                  if (input[0] > 60.05785347067239) {
                      var129 = -0.006405877575395364;
                  } else {
                      var129 = -0.03279188881853025;
                  }
              } else {
                  if (input[5] > 86.97895198216605) {
                      var129 = 0.023043179372228884;
                  } else {
                      var129 = -0.0012259739172425883;
                  }
              }
          } else {
              if (input[10] > 3.5000000000000004) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var129 = 0.0046797345308962155;
                  } else {
                      var129 = -0.0015915622006185326;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var129 = 0.008687787308310732;
                  } else {
                      var129 = -0.000870774755743292;
                  }
              }
          }
      }
      var var130;
      if (input[6] <= -6.069857858271648) {
          if (input[4] <= -4.21670651579148) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var130 = -0.016703993319632234;
                  } else {
                      var130 = 0.009501525395831212;
                  }
              } else {
                  if (input[13] > 10.500000000000002) {
                      var130 = 0.037201488701419254;
                  } else {
                      var130 = 0.0029260129941835727;
                  }
              }
          } else {
              if (input[4] <= -3.038533070624908) {
                  if (input[9] > 3.5000000000000004) {
                      var130 = -0.021691529623436834;
                  } else {
                      var130 = 0.0034396369910577626;
                  }
              } else {
                  if (input[0] > 47.22048117114918) {
                      var130 = -0.020045861216152188;
                  } else {
                      var130 = -0.000598369869082657;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[0] > 47.87234042553219) {
                  var130 = -0.01077862383421298;
              } else {
                  if (input[0] > 32.903904947513766) {
                      var130 = 0.028292951224248887;
                  } else {
                      var130 = 0.004586330828340522;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var130 = -0.016574299197426794;
                  } else {
                      var130 = 0.002007850659709227;
                  }
              } else {
                  if (input[3] <= -0.5448595876477775) {
                      var130 = 0.0022836605195240534;
                  } else {
                      var130 = -0.00018747621899232677;
                  }
              }
          }
      }
      var var131;
      if (input[6] <= -2.8521579336286886) {
          if (input[4] > 3.517091252060496) {
              var131 = 0.024920535583018013;
          } else {
              if (input[4] <= -2.0004379047689356) {
                  if (input[5] > 42.4312767999516) {
                      var131 = -0.0039144872749574695;
                  } else {
                      var131 = 0.00290856209580578;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var131 = -0.029350154208120555;
                  } else {
                      var131 = -0.0038933246675031613;
                  }
              }
          }
      } else {
          if (input[0] > 17.04845007165648) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 24.0530548127776) {
                      var131 = 0.0031227094344620163;
                  } else {
                      var131 = -0.005382262556562918;
                  }
              } else {
                  if (input[5] > 69.85608617600006) {
                      var131 = 0.001066281509378472;
                  } else {
                      var131 = -0.0017525879708822694;
                  }
              }
          } else {
              var131 = 0.017327076557667766;
          }
      }
      var var132;
      if (input[5] > 19.544289135213152) {
          if (input[6] <= -2.398066420549097) {
              if (input[4] <= -2.0004379047689356) {
                  if (input[13] > 10.500000000000002) {
                      var132 = -0.00757092969698779;
                  } else {
                      var132 = 0.002274872933712013;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var132 = -0.02900354655671485;
                  } else {
                      var132 = -0.005697869014392952;
                  }
              }
          } else {
              if (input[5] > 24.0530548127776) {
                  if (input[5] > 25.781461905908227) {
                      var132 = 0.0004429561790232175;
                  } else {
                      var132 = 0.01556066540331867;
                  }
              } else {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var132 = -0.03084991436276262;
                  } else {
                      var132 = -0.005729033810551892;
                  }
              }
          }
      } else {
          if (input[9] > 2.5000000000000004) {
              if (input[3] > 0.12125265216769704) {
                  if (input[10] > 2.5000000000000004) {
                      var132 = -0.020971355256961827;
                  } else {
                      var132 = 0.008884611523304857;
                  }
              } else {
                  if (input[0] > 43.39903825771221) {
                      var132 = 0.01255429773927089;
                  } else {
                      var132 = 0.0003417579326139689;
                  }
              }
          } else {
              if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                  var132 = 0.031863191499763875;
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var132 = -0.005041921140914961;
                  } else {
                      var132 = 0.01147240963211907;
                  }
              }
          }
      }
      var var133;
      if (input[2] > 1.2449878458998531) {
          if (input[13] > 7.500000000000001) {
              if (input[4] > 1.499734792503489) {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var133 = 0.025903619343297386;
                  } else {
                      var133 = 0.0034082664611313606;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var133 = -0.03395697786506685;
                  } else {
                      var133 = 0.00670620916237295;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 85.12950162034976) {
                      var133 = -0.010857714223787932;
                  } else {
                      var133 = 0.012448603967293399;
                  }
              } else {
                  if (input[6] > 8.281812040067665) {
                      var133 = 0.009290151269792313;
                  } else {
                      var133 = -0.018016479958570614;
                  }
              }
          }
      } else {
          if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[9] > 21.500000000000004) {
                  var133 = -0.011404897298092083;
              } else {
                  if (input[3] > 0.8251442856487058) {
                      var133 = -0.006542634593372541;
                  } else {
                      var133 = 0.00021604438905774298;
                  }
              }
          } else {
              if (input[0] > 67.17230718398928) {
                  if (input[5] > 62.70267242553313) {
                      var133 = 0.00388380765570642;
                  } else {
                      var133 = -0.031610750785258435;
                  }
              } else {
                  if (input[2] > 0.025809299484776383) {
                      var133 = -0.0014100962901926256;
                  } else {
                      var133 = 0.00090011787944298;
                  }
              }
          }
      }
      var var134;
      if (input[9] > 18.500000000000004) {
          if (input[7] <= -1.4999999999999998) {
              if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                  var134 = -0.02651482619189255;
              } else {
                  var134 = -0.0022877719752429477;
              }
          } else {
              if (input[0] > 86.25101283547333) {
                  var134 = 0.021229635136603843;
              } else {
                  if (input[4] > 2.224830200500726) {
                      var134 = -0.002281942476902628;
                  } else {
                      var134 = 0.0025091770342315755;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[6] <= -6.443218311398012) {
                  if (input[4] <= -4.871147702697914) {
                      var134 = -0.00563744754842273;
                  } else {
                      var134 = -0.028898213624841865;
                  }
              } else {
                  if (input[3] > 0.3261849805051614) {
                      var134 = -0.006306734943634843;
                  } else {
                      var134 = -0.00021918880489742908;
                  }
              }
          } else {
              if (input[5] > 72.02917243495783) {
                  if (input[4] > 0.8364726566893431) {
                      var134 = 0.0017200009856645278;
                  } else {
                      var134 = -0.004603985482993359;
                  }
              } else {
                  if (input[13] > 1.5000000000000002) {
                      var134 = 0.0015382582964077783;
                  } else {
                      var134 = -0.006124638266813694;
                  }
              }
          }
      }
      var var135;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -7.123374703856836) {
              var135 = -0.013110495481480917;
          } else {
              if (input[13] > 3.5000000000000004) {
                  if (input[4] > 5.322105873571434) {
                      var135 = 0.01411262986175793;
                  } else {
                      var135 = 0.0020974572369158303;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var135 = -0.010731014151521721;
                  } else {
                      var135 = 0.00322047738711067;
                  }
              }
          }
      } else {
          if (input[13] > 5.500000000000001) {
              if (input[7] > 1.5000000000000002) {
                  if (input[4] <= -3.2619166395046837) {
                      var135 = 0.037870687093611646;
                  } else {
                      var135 = 0.003296741075835111;
                  }
              } else {
                  if (input[2] <= -1.5649334836593047) {
                      var135 = -0.015279719306131848;
                  } else {
                      var135 = -0.0010023146003162104;
                  }
              }
          } else {
              if (input[4] > 1.4603064204353786) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var135 = -0.0073905831822501464;
                  } else {
                      var135 = 0.00023871549828912475;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var135 = 0.007661012433736196;
                  } else {
                      var135 = 0.0004974883508689289;
                  }
              }
          }
      }
      var var136;
      if (input[4] <= -8.76737386423564) {
          if (input[13] > 4.500000000000001) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var136 = -0.03855911468361714;
              } else {
                  var136 = 0.0022225035486597;
              }
          } else {
              var136 = 0.020160794229994547;
          }
      } else {
          if (input[6] <= -10.140707619951096) {
              var136 = 0.01521232011620395;
          } else {
              if (input[4] <= -7.712317663256087) {
                  if (input[6] <= -5.379413601618121) {
                      var136 = 0.022088661419868955;
                  } else {
                      var136 = -0.005124507776507065;
                  }
              } else {
                  if (input[2] <= -1.9123784633518905) {
                      var136 = -0.015168370227266812;
                  } else {
                      var136 = -0.000018759351805920046;
                  }
              }
          }
      }
      var var137;
      if (input[4] <= -0.7791403766304014) {
          if (input[4] <= -2.1729741642181852) {
              if (input[4] <= -2.548569004413761) {
                  var137 = -0.00004386415046410139;
              } else {
                  if (input[6] > 2.1601279316659814) {
                      var137 = 0.02986003262638945;
                  } else {
                      var137 = 0.0042772462527272525;
                  }
              }
          } else {
              if (input[0] > 74.32747876777766) {
                  if (input[10] > 3.5000000000000004) {
                      var137 = -0.006446246720746278;
                  } else {
                      var137 = 0.019709927013338485;
                  }
              } else {
                  if (input[2] <= -1.5107108589838323) {
                      var137 = 0.020564379079674493;
                  } else {
                      var137 = -0.0049110919345481665;
                  }
              }
          }
      } else {
          if (input[4] <= -0.5385430840001747) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -2.7331600372354274) {
                      var137 = -0.006327240929950993;
                  } else {
                      var137 = 0.02212655789866806;
                  }
              } else {
                  if (input[6] <= -1.6725312394562015) {
                      var137 = 0.016811692205106768;
                  } else {
                      var137 = -0.010514316828011606;
                  }
              }
          } else {
              if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 7.339776188730569) {
                      var137 = -0.018108389461677876;
                  } else {
                      var137 = 0.005323240185503643;
                  }
              } else {
                  if (input[2] <= -1.1384490160854523) {
                      var137 = -0.011376563568797383;
                  } else {
                      var137 = -0.0002195721048705735;
                  }
              }
          }
      }
      var var138;
      if (input[2] > 1.2449878458998531) {
          if (input[43] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[0] > 76.98568553550524) {
                  var138 = -0.028764382697318347;
              } else {
                  var138 = -0.0028926811742173777;
              }
          } else {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 18.500000000000004) {
                      var138 = -0.024703238404893295;
                  } else {
                      var138 = -0.004362399531434243;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var138 = 0.011740911974314346;
                  } else {
                      var138 = -0.003787768540651934;
                  }
              }
          }
      } else {
          if (input[6] > 2.5493545797764527) {
              if (input[0] > 45.43848929792071) {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var138 = 0.017399729362359215;
                  } else {
                      var138 = 0.0018203328710523561;
                  }
              } else {
                  if (input[4] <= -0.4950921444997715) {
                      var138 = 0.02205937873253293;
                  } else {
                      var138 = -0.007141969562611746;
                  }
              }
          } else {
              if (input[4] > 5.857188587559812) {
                  if (input[2] <= -0.0181999008563946) {
                      var138 = 0.006779166482269368;
                  } else {
                      var138 = 0.03525120067922196;
                  }
              } else {
                  if (input[4] > 4.452431186048718) {
                      var138 = -0.007251845487759598;
                  } else {
                      var138 = -0.00022889433216696862;
                  }
              }
          }
      }
      var var139;
      if (input[5] > 92.60076342411848) {
          if (input[4] > 0.7977856053883731) {
              if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                  var139 = 0.02546387915361842;
              } else {
                  if (input[4] > 1.5491241530613575) {
                      var139 = -0.0013426471999169818;
                  } else {
                      var139 = 0.012803117607282956;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  var139 = -0.031273678359485746;
              } else {
                  if (input[2] > 0.5825270184100372) {
                      var139 = -0.010723926847995412;
                  } else {
                      var139 = -0.0014600430112317883;
                  }
              }
          }
      } else {
          if (input[5] > 88.03613376248084) {
              if (input[3] > 0.4044684408354277) {
                  if (input[3] > 0.5474301788428937) {
                      var139 = 0.003680726087684134;
                  } else {
                      var139 = -0.017826320396574568;
                  }
              } else {
                  if (input[9] > 15.500000000000002) {
                      var139 = 0.04113816110644491;
                  } else {
                      var139 = 0.008190766752637208;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -1.1411506569620806) {
                      var139 = -0.005431861013794408;
                  } else {
                      var139 = 0.011134063127087803;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var139 = -0.0033607761864805612;
                  } else {
                      var139 = 0.0001844263208461129;
                  }
              }
          }
      }
      var var140;
      if (input[5] > 19.544289135213152) {
          if (input[6] <= -2.398066420549097) {
              if (input[4] <= -2.0004379047689356) {
                  if (input[3] > 0.22160115277279482) {
                      var140 = -0.014259011785570706;
                  } else {
                      var140 = 0.001114278667641686;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var140 = -0.027650204375364258;
                  } else {
                      var140 = -0.005404459376707654;
                  }
              }
          } else {
              if (input[2] <= -1.005074921462989) {
                  var140 = -0.030226298485219495;
              } else {
                  if (input[5] > 24.0530548127776) {
                      var140 = 0.0007085817153155247;
                  } else {
                      var140 = -0.008300389358247184;
                  }
              }
          }
      } else {
          if (input[6] > 3.957449210482031) {
              if (input[13] > 6.500000000000001) {
                  var140 = -0.006700770562721808;
              } else {
                  var140 = 0.03668486808071605;
              }
          } else {
              if (input[3] > 0.14816154989694033) {
                  if (input[4] > 4.047127624433007) {
                      var140 = -0.04645470797381586;
                  } else {
                      var140 = -0.005800377521469642;
                  }
              } else {
                  if (input[0] > 44.50111137696333) {
                      var140 = 0.013834122905043695;
                  } else {
                      var140 = 0.0007007120506978279;
                  }
              }
          }
      }
      var var141;
      if (input[2] > 0.025809299484776383) {
          if (input[0] > 25.51590802753186) {
              if (input[6] <= -4.22423090678842) {
                  var141 = 0.024507198701851956;
              } else {
                  if (input[6] <= -2.282378601683849) {
                      var141 = -0.012853363274858535;
                  } else {
                      var141 = -0.0002458107090466464;
                  }
              }
          } else {
              var141 = -0.031432017253448345;
          }
      } else {
          if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  var141 = 0.03931254469574917;
              } else {
                  if (input[5] > 43.306883112568904) {
                      var141 = 0.020830298537138345;
                  } else {
                      var141 = -0.0053859173185186425;
                  }
              }
          } else {
              if (input[2] <= -0.0719761568464675) {
                  if (input[10] > 3.5000000000000004) {
                      var141 = 0.0020160235303826267;
                  } else {
                      var141 = -0.00183548033113591;
                  }
              } else {
                  if (input[0] > 32.048749698331136) {
                      var141 = 0.00727143820136579;
                  } else {
                      var141 = -0.01867927915064568;
                  }
              }
          }
      }
      var var142;
      if (input[9] > 5.500000000000001) {
          if (input[9] > 7.500000000000001) {
              if (input[7] <= -1.4999999999999998) {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var142 = 0.007814776526444954;
                  } else {
                      var142 = -0.009817933128996544;
                  }
              } else {
                  if (input[2] > 0.025809299484776383) {
                      var142 = -0.0008256876903809913;
                  } else {
                      var142 = 0.0015349833250683856;
                  }
              }
          } else {
              if (input[5] <= -18.17767320837807) {
                  var142 = -0.02644507486077783;
              } else {
                  if (input[3] <= -0.4204963420069765) {
                      var142 = 0.0028202343857557793;
                  } else {
                      var142 = -0.006380204749271797;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[7] <= -1.4999999999999998) {
                  var142 = 0.024779074869262677;
              } else {
                  if (input[5] > 0.000000000000000000000000000000000010000000180025095) {
                      var142 = -0.0016515838451646387;
                  } else {
                      var142 = -0.023137230324229336;
                  }
              }
          } else {
              if (input[4] > 1.017111697377455) {
                  if (input[13] > 2.5000000000000004) {
                      var142 = 0.002582996186340297;
                  } else {
                      var142 = -0.013326973486691415;
                  }
              } else {
                  if (input[2] > 0.9689046583490236) {
                      var142 = 0.02671531504878405;
                  } else {
                      var142 = 0.004597295018909838;
                  }
              }
          }
      }
      var var143;
      if (input[5] > 27.141286553166832) {
          if (input[0] > 26.383030344586114) {
              if (input[6] <= -2.5554043664065276) {
                  if (input[4] <= -2.0408506225936174) {
                      var143 = -0.0004111992584690787;
                  } else {
                      var143 = -0.00922161933268571;
                  }
              } else {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var143 = 0.002942814381733327;
                  } else {
                      var143 = -0.0006536337476118582;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 30.755186602054312) {
                      var143 = -0.04210698006463651;
                  } else {
                      var143 = -0.02220262025263447;
                  }
              } else {
                  var143 = 0.003744489093101046;
              }
          }
      } else {
          if (input[4] > 0.9187848953214247) {
              if (input[10] > 1.5000000000000002) {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var143 = -0.029981088695743365;
                  } else {
                      var143 = -0.005365081534493466;
                  }
              } else {
                  if (input[4] > 2.8049613573678696) {
                      var143 = 0.02411557044628646;
                  } else {
                      var143 = -0.0017763888837198942;
                  }
              }
          } else {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -2.7992662614894233) {
                      var143 = -0.0030411359153380336;
                  } else {
                      var143 = 0.03750973598012047;
                  }
              } else {
                  if (input[2] > 0.25887622514763803) {
                      var143 = 0.01642699031613877;
                  } else {
                      var143 = 0.0012121328962387788;
                  }
              }
          }
      }
      var var144;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 0.9715869529760879) {
              if (input[4] > 1.7160674285510085) {
                  var144 = 0.0017812045965420456;
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var144 = -0.00840355837089361;
                  } else {
                      var144 = 0.021553098661865975;
                  }
              }
          } else {
              if (input[4] <= -0.4950921444997715) {
                  if (input[4] <= -1.0376436871914176) {
                      var144 = 0.0007803138227281622;
                  } else {
                      var144 = 0.017736116538506787;
                  }
              } else {
                  if (input[2] > 1.0016590802373793) {
                      var144 = 0.012070090227489304;
                  } else {
                      var144 = -0.012089570119236004;
                  }
              }
          }
      } else {
          if (input[7] <= -1.4999999999999998) {
              if (input[5] <= -11.42528703884175) {
                  if (input[4] > 2.0411690032974543) {
                      var144 = 0.02852241189738841;
                  } else {
                      var144 = 0.0016031018600624056;
                  }
              } else {
                  if (input[4] <= -3.3236286389454217) {
                      var144 = -0.024560813021141964;
                  } else {
                      var144 = -0.004060964079321442;
                  }
              }
          } else {
              if (input[6] > 0.3551665137137319) {
                  if (input[0] > 26.75666323459365) {
                      var144 = -0.0007014202239109742;
                  } else {
                      var144 = -0.021500578000787016;
                  }
              } else {
                  if (input[6] <= -0.07527005098723467) {
                      var144 = 0.0001849078737715164;
                  } else {
                      var144 = 0.006811451907584022;
                  }
              }
          }
      }
      var var145;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[13] > 10.500000000000002) {
              if (input[10] > 3.5000000000000004) {
                  if (input[9] > 3.5000000000000004) {
                      var145 = -0.016808103424617634;
                  } else {
                      var145 = 0.012676260545953708;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var145 = -0.007296701792773794;
                  } else {
                      var145 = 0.010438010675383351;
                  }
              }
          } else {
              if (input[4] > 6.995147082128496) {
                  var145 = -0.016688988357081488;
              } else {
                  if (input[4] > 5.244537663167775) {
                      var145 = 0.018099242943891907;
                  } else {
                      var145 = 0.0014432054963622867;
                  }
              }
          }
      } else {
          if (input[2] <= -0.2707003273254145) {
              if (input[5] > 83.75558925058311) {
                  if (input[0] > 60.46307640313091) {
                      var145 = 0.008413350667998589;
                  } else {
                      var145 = 0.04313344537688005;
                  }
              } else {
                  if (input[6] <= -0.831454568954585) {
                      var145 = -0.0007602535493972163;
                  } else {
                      var145 = 0.008700691679074403;
                  }
              }
          } else {
              if (input[2] <= -0.18032876532877087) {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var145 = -0.01618857989203176;
                  } else {
                      var145 = -0.004146549344150728;
                  }
              } else {
                  if (input[6] <= -4.032321514980188) {
                      var145 = 0.013700020251633025;
                  } else {
                      var145 = -0.0006346019830399362;
                  }
              }
          }
      }
      var var146;
      if (input[5] <= -29.59449508597042) {
          if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
              var146 = 0.025642216985287538;
          } else {
              if (input[3] <= -0.5448595876477775) {
                  if (input[3] <= -0.7536198886030606) {
                      var146 = 0.001473406508795353;
                  } else {
                      var146 = 0.029946350214699286;
                  }
              } else {
                  if (input[3] <= -0.39477032531299977) {
                      var146 = -0.03460299672407282;
                  } else {
                      var146 = 0.000525011422500313;
                  }
              }
          }
      } else {
          if (input[5] <= -23.24721240218805) {
              if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                  var146 = -0.03236900931739877;
              } else {
                  if (input[5] <= -26.388170390808185) {
                      var146 = -0.00907757195938145;
                  } else {
                      var146 = 0.011329758071293914;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 52.55175265198409) {
                      var146 = -0.006635645517241196;
                  } else {
                      var146 = 0.0107523625393213;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var146 = 0.003177213726326189;
                  } else {
                      var146 = -0.00030531454825734696;
                  }
              }
          }
      }
      var var147;
      if (input[2] > 1.103118178873732) {
          if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[4] <= -1.608899516503428) {
                  var147 = 0.029663841908852785;
              } else {
                  if (input[5] > 52.60526124172524) {
                      var147 = 0.002628010005068418;
                  } else {
                      var147 = -0.02562920880560912;
                  }
              }
          } else {
              if (input[6] > 3.3803371165670133) {
                  if (input[13] > 2.5000000000000004) {
                      var147 = -0.001845911199233061;
                  } else {
                      var147 = -0.01483433345347206;
                  }
              } else {
                  var147 = -0.02462141491517919;
              }
          }
      } else {
          if (input[6] > 8.627739511800717) {
              var147 = -0.012943160283166243;
          } else {
              if (input[6] > 7.999681113877577) {
                  var147 = 0.02302661120852131;
              } else {
                  if (input[2] > 1.049554179207316) {
                      var147 = 0.007779483396680125;
                  } else {
                      var147 = 0.00006195272499160235;
                  }
              }
          }
      }
      var var148;
      if (input[4] <= -0.7791403766304014) {
          if (input[4] <= -2.1729741642181852) {
              if (input[0] > 64.75395318316197) {
                  var148 = -0.004552651110961486;
              } else {
                  if (input[2] > 0.9689046583490236) {
                      var148 = 0.03295995122068129;
                  } else {
                      var148 = 0.0012456539829813536;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 5.500000000000001) {
                      var148 = -0.012463649404502149;
                  } else {
                      var148 = 0.0017126920161746788;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var148 = -0.007889247764783794;
                  } else {
                      var148 = 0.005175293505497143;
                  }
              }
          }
      } else {
          if (input[4] <= -0.45083601189522843) {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -0.21368772293480612) {
                      var148 = -0.012498545087888894;
                  } else {
                      var148 = 0.03348080818195041;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var148 = 0.010661832674849117;
                  } else {
                      var148 = -0.0068935248149925125;
                  }
              }
          } else {
              if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 7.339776188730569) {
                      var148 = -0.01727625966639638;
                  } else {
                      var148 = 0.005038641263080615;
                  }
              } else {
                  if (input[4] <= -0.03399001277826245) {
                      var148 = -0.00621913223865338;
                  } else {
                      var148 = -0.00003540874706026627;
                  }
              }
          }
      }
      var var149;
      if (input[4] <= -8.76737386423564) {
          if (input[13] > 4.500000000000001) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var149 = -0.03730437366872501;
              } else {
                  var149 = 0.001992040942994618;
              }
          } else {
              var149 = 0.018980433487525608;
          }
      } else {
          if (input[6] <= -10.140707619951096) {
              var149 = 0.014302295562930388;
          } else {
              if (input[4] <= -7.712317663256087) {
                  if (input[6] <= -5.379413601618121) {
                      var149 = 0.020793876541356913;
                  } else {
                      var149 = -0.004879838993142913;
                  }
              } else {
                  if (input[2] <= -1.9123784633518905) {
                      var149 = -0.014451396761662625;
                  } else {
                      var149 = -0.000017168617245690245;
                  }
              }
          }
      }
      var var150;
      if (input[9] > 5.500000000000001) {
          if (input[9] > 7.500000000000001) {
              if (input[7] <= -1.4999999999999998) {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var150 = 0.007492549985100543;
                  } else {
                      var150 = -0.009291800986126723;
                  }
              } else {
                  if (input[2] > 0.025809299484776383) {
                      var150 = -0.0007982500590892497;
                  } else {
                      var150 = 0.001459598899910453;
                  }
              }
          } else {
              if (input[0] > 57.62589042924083) {
                  if (input[0] > 62.753701799598225) {
                      var150 = -0.004440511244328237;
                  } else {
                      var150 = 0.01383788378132493;
                  }
              } else {
                  if (input[5] > 68.73201742693793) {
                      var150 = -0.0262162346848991;
                  } else {
                      var150 = -0.004909669085907507;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] <= -8.30864402369986) {
                  var150 = 0.017993272607142997;
              } else {
                  if (input[6] <= -6.717684292131488) {
                      var150 = -0.01815284804528581;
                  } else {
                      var150 = -0.0014350231163023776;
                  }
              }
          } else {
              if (input[4] > 1.017111697377455) {
                  if (input[13] > 2.5000000000000004) {
                      var150 = 0.0024893797197015773;
                  } else {
                      var150 = -0.012594515358383046;
                  }
              } else {
                  if (input[0] > 64.51311365713559) {
                      var150 = -0.00776318407624015;
                  } else {
                      var150 = 0.009541388254394012;
                  }
              }
          }
      }
      var var151;
      if (input[4] > 4.912099304131096) {
          if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[2] > 0.5035640840959066) {
                  var151 = -0.02596870836086992;
              } else {
                  var151 = 0.002159443879966218;
              }
          } else {
              if (input[14] > 0.000000000000000000000000000000000010000000180025095) {
                  var151 = 0.02373775914261457;
              } else {
                  if (input[10] > 2.5000000000000004) {
                      var151 = 0.004875751410320782;
                  } else {
                      var151 = -0.0013196450343578175;
                  }
              }
          }
      } else {
          if (input[4] > 4.21339422970748) {
              if (input[9] > 13.500000000000002) {
                  if (input[0] > 52.89417697841084) {
                      var151 = -0.0015799827102942249;
                  } else {
                      var151 = -0.026406144525768935;
                  }
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var151 = 0.024894348254149892;
                  } else {
                      var151 = -0.004087485687402941;
                  }
              }
          } else {
              if (input[4] > 3.2032943389782225) {
                  if (input[2] > 1.1219032542947727) {
                      var151 = -0.010003638373768962;
                  } else {
                      var151 = 0.0049860742738694706;
                  }
              } else {
                  if (input[4] > 2.1419746152525203) {
                      var151 = -0.003910922997613416;
                  } else {
                      var151 = 0.0002764059832714883;
                  }
              }
          }
      }
      var var152;
      if (input[4] <= -0.7791403766304014) {
          if (input[4] <= -2.1729741642181852) {
              if (input[4] <= -2.548569004413761) {
                  var152 = -0.00016195874190468048;
              } else {
                  if (input[6] > 2.1601279316659814) {
                      var152 = 0.027628686265566887;
                  } else {
                      var152 = 0.003934260799723365;
                  }
              }
          } else {
              if (input[0] > 74.32747876777766) {
                  if (input[10] > 3.5000000000000004) {
                      var152 = -0.005748443651946333;
                  } else {
                      var152 = 0.018890403820162854;
                  }
              } else {
                  if (input[10] > 4.500000000000001) {
                      var152 = 0.00554306941607318;
                  } else {
                      var152 = -0.005503502324122247;
                  }
              }
          }
      } else {
          if (input[4] <= -0.45083601189522843) {
              if (input[3] <= -0.24344553277095524) {
                  if (input[5] > 41.948811368473365) {
                      var152 = -0.023632973060039315;
                  } else {
                      var152 = 0.0016706114231383514;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var152 = 0.030909646261349684;
                  } else {
                      var152 = 0.0037637544652586266;
                  }
              }
          } else {
              if (input[6] <= -5.117681189325094) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var152 = 0.001293970866002721;
                  } else {
                      var152 = -0.01976859860698224;
                  }
              } else {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var152 = 0.003995328261292889;
                  } else {
                      var152 = -0.0002500043127114581;
                  }
              }
          }
      }
      var var153;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[3] <= -0.456609706027228) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 45.23679132112875) {
                      var153 = -0.03275738294492169;
                  } else {
                      var153 = -0.0046996000947863645;
                  }
              } else {
                  if (input[2] <= -0.45302790421983913) {
                      var153 = 0.0020881939114901146;
                  } else {
                      var153 = -0.02191559499857183;
                  }
              }
          } else {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 3.5000000000000004) {
                      var153 = 0.005804076826582489;
                  } else {
                      var153 = 0.021992714478987013;
                  }
              } else {
                  if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                      var153 = -0.008780718352387085;
                  } else {
                      var153 = 0.0020365804844497764;
                  }
              }
          }
      } else {
          if (input[3] <= -0.5340223873031661) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 3.5000000000000004) {
                      var153 = 0.006957664888308445;
                  } else {
                      var153 = -0.008710165163850408;
                  }
              } else {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var153 = -0.006245702971886117;
                  } else {
                      var153 = 0.010605082208176218;
                  }
              }
          } else {
              if (input[0] > 44.50111137696333) {
                  var153 = 0.0000916987435358324;
              } else {
                  if (input[4] > 0.9187848953214247) {
                      var153 = -0.008246328645345932;
                  } else {
                      var153 = 0.00034711206470518534;
                  }
              }
          }
      }
      var var154;
      if (input[4] <= -0.03399001277826245) {
          if (input[3] > 1.2382710939230106) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var154 = -0.03396879403823898;
              } else {
                  if (input[4] <= -1.528269700471031) {
                      var154 = 0.035883480926640066;
                  } else {
                      var154 = -0.018028552825812384;
                  }
              }
          } else {
              if (input[6] > 2.600604898520747) {
                  if (input[5] > 91.29004180028802) {
                      var154 = -0.004776491726485151;
                  } else {
                      var154 = 0.012981671380537305;
                  }
              } else {
                  if (input[7] > 1.5000000000000002) {
                      var154 = 0.010433057609820525;
                  } else {
                      var154 = -0.0012018559625350206;
                  }
              }
          }
      } else {
          if (input[6] > 0.7642576721972248) {
              if (input[21] > 0.000000000000000000000000000000000010000000180025095) {
                  var154 = 0.031713000624412874;
              } else {
                  if (input[6] > 0.8055075614638355) {
                      var154 = -0.0005136901994244141;
                  } else {
                      var154 = -0.025529494597129693;
                  }
              }
          } else {
              if (input[10] > 1.5000000000000002) {
                  if (input[4] > 2.1419746152525203) {
                      var154 = -0.004442789398763222;
                  } else {
                      var154 = 0.004212967827825874;
                  }
              } else {
                  if (input[3] > 0.3039608682600068) {
                      var154 = 0.043041706225786985;
                  } else {
                      var154 = 0.006449871727742235;
                  }
              }
          }
      }
      var var155;
      if (input[5] > 19.544289135213152) {
          if (input[0] > 25.51590802753186) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var155 = 0.01621505289587939;
                  } else {
                      var155 = 0.0012011893227462397;
                  }
              } else {
                  if (input[5] > 69.85608617600006) {
                      var155 = 0.0006011212922916894;
                  } else {
                      var155 = -0.002337992942787702;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -1.3815464400185) {
                      var155 = -0.04530962420771249;
                  } else {
                      var155 = -0.010363111094019188;
                  }
              } else {
                  if (input[2] <= -0.7331540867338935) {
                      var155 = 0.01644659745732883;
                  } else {
                      var155 = -0.018997973987884748;
                  }
              }
          }
      } else {
          if (input[6] > 3.957449210482031) {
              if (input[13] > 6.500000000000001) {
                  var155 = -0.005844911977206394;
              } else {
                  var155 = 0.034756741270349216;
              }
          } else {
              if (input[3] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 2.5000000000000004) {
                      var155 = -0.019396827133472218;
                  } else {
                      var155 = 0.007235906017830008;
                  }
              } else {
                  if (input[3] <= -0.09198715495658778) {
                      var155 = 0.0008155629748339389;
                  } else {
                      var155 = 0.01843118156249624;
                  }
              }
          }
      }
      var var156;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] <= -5.20604877356585) {
              if (input[10] > 1.5000000000000002) {
                  if (input[5] > 1.7833279067643293) {
                      var156 = -0.0020670501865390906;
                  } else {
                      var156 = 0.01568263069152707;
                  }
              } else {
                  var156 = 0.02287226630472674;
              }
          } else {
              if (input[6] > 0.5201967351303219) {
                  if (input[2] > 0.512388466754457) {
                      var156 = -0.000030028626086554157;
                  } else {
                      var156 = 0.009633102954359438;
                  }
              } else {
                  if (input[13] > 6.500000000000001) {
                      var156 = 0.0022865262751227402;
                  } else {
                      var156 = -0.008349442981310358;
                  }
              }
          }
      } else {
          if (input[6] <= -4.495641208044259) {
              if (input[2] <= -0.07927539197604427) {
                  if (input[5] > 74.32437252525206) {
                      var156 = -0.02163418603502719;
                  } else {
                      var156 = -0.0017978524733056921;
                  }
              } else {
                  var156 = 0.01964372309529179;
              }
          } else {
              if (input[2] <= -0.2707003273254145) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var156 = -0.0009335861963681901;
                  } else {
                      var156 = 0.005630020202050124;
                  }
              } else {
                  if (input[2] <= -0.17292263602242408) {
                      var156 = -0.007612976582280131;
                  } else {
                      var156 = -0.00014073263191168942;
                  }
              }
          }
      }
      var var157;
      if (input[9] > 18.500000000000004) {
          if (input[0] > 41.4508936947301) {
              if (input[5] > 15.235072423311074) {
                  if (input[13] > 3.5000000000000004) {
                      var157 = 0.0002417815864262751;
                  } else {
                      var157 = 0.007140501649398239;
                  }
              } else {
                  var157 = 0.02828918257176243;
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 19.14508537197081) {
                      var157 = -0.011776573557414925;
                  } else {
                      var157 = 0.0036364996984583073;
                  }
              } else {
                  if (input[4] > 0.8364726566893431) {
                      var157 = -0.009276761660099494;
                  } else {
                      var157 = 0.00942720296711321;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[10] > 2.5000000000000004) {
                  if (input[5] > 70.6027148026618) {
                      var157 = 0.005248808621359329;
                  } else {
                      var157 = -0.002996074012062552;
                  }
              } else {
                  if (input[6] <= -2.398066420549097) {
                      var157 = -0.013415989894107406;
                  } else {
                      var157 = -0.0028522169128705785;
                  }
              }
          } else {
              if (input[2] <= -1.3815464400185) {
                  if (input[4] <= -3.9776333795063805) {
                      var157 = 0.014917466701281313;
                  } else {
                      var157 = -0.00040032915163249545;
                  }
              } else {
                  if (input[4] <= -0.03399001277826245) {
                      var157 = -0.0011354742650201202;
                  } else {
                      var157 = 0.0011077876177579859;
                  }
              }
          }
      }
      var var158;
      if (input[2] > 0.025809299484776383) {
          if (input[0] > 25.51590802753186) {
              if (input[6] <= -4.22423090678842) {
                  var158 = 0.021523209105402716;
              } else {
                  if (input[6] <= -2.282378601683849) {
                      var158 = -0.012250467295194616;
                  } else {
                      var158 = -0.00023970885844086835;
                  }
              }
          } else {
              var158 = -0.02950082206389794;
          }
      } else {
          if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  var158 = 0.03627987374860585;
              } else {
                  if (input[4] > 3.655683130085723) {
                      var158 = 0.031145073377381028;
                  } else {
                      var158 = -0.001486846734860903;
                  }
              }
          } else {
              if (input[0] > 64.75395318316197) {
                  if (input[10] > 4.500000000000001) {
                      var158 = 0.010458898346667323;
                  } else {
                      var158 = -0.012980666647534065;
                  }
              } else {
                  if (input[3] <= -0.20134330740589654) {
                      var158 = -0.0005237538468314621;
                  } else {
                      var158 = 0.0038159449609318366;
                  }
              }
          }
      }
      var var159;
      if (input[5] > 92.60076342411848) {
          if (input[4] > 0.7977856053883731) {
              if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                  var159 = 0.023487124716527894;
              } else {
                  if (input[4] > 1.5491241530613575) {
                      var159 = -0.001323158270087741;
                  } else {
                      var159 = 0.011982747096411457;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  var159 = -0.029666297070173587;
              } else {
                  if (input[2] > 0.5825270184100372) {
                      var159 = -0.010133851777860574;
                  } else {
                      var159 = -0.0013675640843713816;
                  }
              }
          }
      } else {
          if (input[5] > 88.64965447194571) {
              if (input[3] > 0.4044684408354277) {
                  if (input[5] > 91.91928172844878) {
                      var159 = 0.018998289528388987;
                  } else {
                      var159 = -0.0020736258147819766;
                  }
              } else {
                  if (input[9] > 15.500000000000002) {
                      var159 = 0.040415393132957854;
                  } else {
                      var159 = 0.007042083442056023;
                  }
              }
          } else {
              if (input[6] > 10.31060103068119) {
                  var159 = 0.016921398491865646;
              } else {
                  if (input[2] > 1.4199031747969257) {
                      var159 = -0.0068551539828136795;
                  } else {
                      var159 = 0.00008060411093315767;
                  }
              }
          }
      }
      var var160;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -7.123374703856836) {
              var160 = -0.01248763776551645;
          } else {
              if (input[0] > 21.921978436600792) {
                  if (input[6] <= -5.033129184600345) {
                      var160 = 0.009753714900332403;
                  } else {
                      var160 = 0.0009388628550029434;
                  }
              } else {
                  var160 = -0.013915696794041272;
              }
          }
      } else {
          if (input[3] > 0.7595953914765796) {
              if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                  var160 = -0.020583073988684128;
              } else {
                  if (input[9] > 1.5000000000000002) {
                      var160 = -0.002384856211770133;
                  } else {
                      var160 = 0.00903137704633059;
                  }
              }
          } else {
              if (input[0] > 67.17230718398928) {
                  if (input[5] > 61.34338824862519) {
                      var160 = 0.005880101062124595;
                  } else {
                      var160 = -0.03285298707932094;
                  }
              } else {
                  if (input[0] > 65.68848758464974) {
                      var160 = -0.009588939680808768;
                  } else {
                      var160 = -0.00013195992425810109;
                  }
              }
          }
      }
      var var161;
      if (input[6] <= -6.069857858271648) {
          if (input[4] <= -4.21670651579148) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var161 = -0.016045880219767033;
                  } else {
                      var161 = 0.00828326627392229;
                  }
              } else {
                  if (input[13] > 10.500000000000002) {
                      var161 = 0.035159865776005064;
                  } else {
                      var161 = 0.002348898273402689;
                  }
              }
          } else {
              if (input[4] <= -3.038533070624908) {
                  if (input[9] > 3.5000000000000004) {
                      var161 = -0.02056746100033933;
                  } else {
                      var161 = 0.002730965980794777;
                  }
              } else {
                  if (input[0] > 47.22048117114918) {
                      var161 = -0.017926504425136956;
                  } else {
                      var161 = -0.0001253369828253805;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[0] > 47.87234042553219) {
                  var161 = -0.010095648459456758;
              } else {
                  if (input[0] > 32.903904947513766) {
                      var161 = 0.02625833486208939;
                  } else {
                      var161 = 0.004653390443737586;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var161 = -0.01449124384926222;
                  } else {
                      var161 = 0.001939565924661212;
                  }
              } else {
                  if (input[3] <= -0.5448595876477775) {
                      var161 = 0.0022554534322953446;
                  } else {
                      var161 = -0.00021580368596904132;
                  }
              }
          }
      }
      var var162;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[13] > 10.500000000000002) {
              if (input[10] > 3.5000000000000004) {
                  if (input[9] > 3.5000000000000004) {
                      var162 = -0.016036406006716016;
                  } else {
                      var162 = 0.011638832765405033;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var162 = -0.006909992524545019;
                  } else {
                      var162 = 0.009620961965206162;
                  }
              }
          } else {
              if (input[2] <= -1.9123784633518905) {
                  var162 = -0.02286566881789018;
              } else {
                  if (input[0] > 13.23529411764625) {
                      var162 = 0.0016399391916836247;
                  } else {
                      var162 = 0.026895940164942702;
                  }
              }
          }
      } else {
          if (input[2] <= -0.3112421825088057) {
              if (input[6] <= -2.8521579336286886) {
                  if (input[3] <= -0.39477032531299977) {
                      var162 = 0.00008033729602953885;
                  } else {
                      var162 = -0.009554856754113175;
                  }
              } else {
                  if (input[10] > 3.5000000000000004) {
                      var162 = 0.014623961671414382;
                  } else {
                      var162 = 0.0013786591227430735;
                  }
              }
          } else {
              if (input[3] <= -0.20134330740589654) {
                  if (input[4] <= -5.041750399183811) {
                      var162 = 0.024037295588764343;
                  } else {
                      var162 = -0.008553555769825555;
                  }
              } else {
                  if (input[0] > 26.383030344586114) {
                      var162 = -0.0001473763073867075;
                  } else {
                      var162 = -0.029799080813409946;
                  }
              }
          }
      }
      var var163;
      if (input[4] > 4.912099304131096) {
          if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[2] > 0.5035640840959066) {
                  var163 = -0.024921017034543053;
              } else {
                  var163 = 0.0022393242796906318;
              }
          } else {
              if (input[5] <= -10.071781663624618) {
                  var163 = 0.02322938463665133;
              } else {
                  if (input[5] > 40.99339472366089) {
                      var163 = 0.0036450661012872327;
                  } else {
                      var163 = -0.0032237766031362955;
                  }
              }
          }
      } else {
          if (input[4] > 4.21339422970748) {
              if (input[9] > 3.5000000000000004) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var163 = -0.0015675544993572516;
                  } else {
                      var163 = -0.014109996443922072;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var163 = 0.017775791576551705;
                  } else {
                      var163 = -0.002663263171142961;
                  }
              }
          } else {
              if (input[4] > 3.2032943389782225) {
                  if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                      var163 = 0.015330943328153712;
                  } else {
                      var163 = 0.0010005881042867558;
                  }
              } else {
                  if (input[4] > 2.1419746152525203) {
                      var163 = -0.003704917448801029;
                  } else {
                      var163 = 0.00025898682841767366;
                  }
              }
          }
      }
      var var164;
      if (input[5] > 92.60076342411848) {
          if (input[4] > 0.7977856053883731) {
              if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                  var164 = 0.022178377931273845;
              } else {
                  if (input[2] > 0.12684171930706203) {
                      var164 = 0.0025995730261689806;
                  } else {
                      var164 = -0.010368789272480167;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  var164 = -0.028574144832622286;
              } else {
                  if (input[4] <= -6.711865554587188) {
                      var164 = -0.02346444861770329;
                  } else {
                      var164 = -0.0032985826080028056;
                  }
              }
          }
      } else {
          if (input[5] > 88.03613376248084) {
              if (input[3] > 0.4044684408354277) {
                  if (input[3] > 0.5474301788428937) {
                      var164 = 0.003462865669365562;
                  } else {
                      var164 = -0.01701126300128537;
                  }
              } else {
                  if (input[9] > 15.500000000000002) {
                      var164 = 0.03632176804567327;
                  } else {
                      var164 = 0.007211120090754539;
                  }
              }
          } else {
              if (input[6] > 10.31060103068119) {
                  var164 = 0.015996667477351092;
              } else {
                  if (input[2] > 1.4199031747969257) {
                      var164 = -0.006478835910704722;
                  } else {
                      var164 = 0.00006191265300349596;
                  }
              }
          }
      }
      var var165;
      if (input[5] <= -29.59449508597042) {
          if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
              var165 = 0.024229324075564555;
          } else {
              if (input[6] <= -1.9882174223264164) {
                  if (input[4] <= -2.6534313318860563) {
                      var165 = -0.00871619195532941;
                  } else {
                      var165 = 0.013252524870344857;
                  }
              } else {
                  var165 = -0.022497667570589387;
              }
          }
      } else {
          if (input[5] <= -23.24721240218805) {
              if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                  var165 = -0.031228199636562856;
              } else {
                  if (input[5] <= -26.388170390808185) {
                      var165 = -0.008848751876155707;
                  } else {
                      var165 = 0.01072762217888466;
                  }
              }
          } else {
              if (input[30] > 0.000000000000000000000000000000000010000000180025095) {
                  var165 = -0.012634472830000408;
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var165 = 0.0036772952506460115;
                  } else {
                      var165 = -0.00006679662096493243;
                  }
              }
          }
      }
      var var166;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[13] > 7.500000000000001) {
                  var166 = 0.024823980129795867;
              } else {
                  var166 = -0.001673400705847395;
              }
          } else {
              if (input[5] > 1.7833279067643293) {
                  if (input[0] > 30.249536376932337) {
                      var166 = 0.0011715715680507101;
                  } else {
                      var166 = -0.01084986101736276;
                  }
              } else {
                  if (input[2] <= -0.9007680814598735) {
                      var166 = 0.020821410585711755;
                  } else {
                      var166 = 0.002030572319071645;
                  }
              }
          }
      } else {
          if (input[7] <= -1.4999999999999998) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  var166 = -0.023212153034317323;
              } else {
                  if (input[4] <= -3.2619166395046837) {
                      var166 = -0.01637991458557928;
                  } else {
                      var166 = 0.0033057710842736908;
                  }
              }
          } else {
              if (input[6] > 0.3551665137137319) {
                  if (input[0] > 28.941439086755278) {
                      var166 = -0.0005889656023506864;
                  } else {
                      var166 = -0.016452476441449353;
                  }
              } else {
                  if (input[6] <= -0.07527005098723467) {
                      var166 = 0.000157519587740358;
                  } else {
                      var166 = 0.006387121675724048;
                  }
              }
          }
      }
      var var167;
      if (input[5] > 27.141286553166832) {
          if (input[0] > 26.383030344586114) {
              if (input[6] <= -2.5554043664065276) {
                  if (input[4] <= -2.0408506225936174) {
                      var167 = -0.00037353917178815655;
                  } else {
                      var167 = -0.00855282925708738;
                  }
              } else {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var167 = 0.0026865276032524694;
                  } else {
                      var167 = -0.0006161985252751567;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 30.755186602054312) {
                      var167 = -0.039274550230298834;
                  } else {
                      var167 = -0.019714565720637733;
                  }
              } else {
                  var167 = 0.0030552681902225407;
              }
          }
      } else {
          if (input[4] > 0.9187848953214247) {
              if (input[10] > 1.5000000000000002) {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var167 = -0.028823191129458553;
                  } else {
                      var167 = -0.004951678594199755;
                  }
              } else {
                  if (input[4] > 2.8049613573678696) {
                      var167 = 0.022602796526391935;
                  } else {
                      var167 = -0.001778994539687078;
                  }
              }
          } else {
              if (input[0] > 48.47580151432786) {
                  if (input[2] <= -0.17292263602242408) {
                      var167 = -0.0041065558049403145;
                  } else {
                      var167 = 0.05520527976961329;
                  }
              } else {
                  if (input[4] <= -0.03399001277826245) {
                      var167 = 0.0007927838945413772;
                  } else {
                      var167 = 0.009111579670463207;
                  }
              }
          }
      }
      var var168;
      if (input[9] > 20.500000000000004) {
          if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[2] <= -0.43692512381129284) {
                  if (input[5] > 39.68230743130311) {
                      var168 = -0.028525237759420802;
                  } else {
                      var168 = 0.001673792898259046;
                  }
              } else {
                  if (input[4] <= -0.31292209129263854) {
                      var168 = 0.015493160910388788;
                  } else {
                      var168 = 0.0032247699957902035;
                  }
              }
          } else {
              if (input[4] > 3.4698611223847746) {
                  if (input[6] > 3.698631433228608) {
                      var168 = 0.00477862483486843;
                  } else {
                      var168 = -0.03366476210657383;
                  }
              } else {
                  if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                      var168 = 0.008019382423763462;
                  } else {
                      var168 = -0.0021226405675126973;
                  }
              }
          }
      } else {
          if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 2.5000000000000004) {
                      var168 = -0.0034671638480249243;
                  } else {
                      var168 = 0.010494474276650678;
                  }
              } else {
                  if (input[13] > 1.5000000000000002) {
                      var168 = 0.004750389975080203;
                  } else {
                      var168 = -0.013462476983136296;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var168 = 0.0007956040439569579;
              } else {
                  if (input[9] > 10.500000000000002) {
                      var168 = -0.006847575978224477;
                  } else {
                      var168 = 0.0020145073944432333;
                  }
              }
          }
      }
      var var169;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 6.995147082128496) {
              var169 = -0.01573917103426002;
          } else {
              if (input[4] > 5.244537663167775) {
                  if (input[0] > 53.257588413367706) {
                      var169 = 0.03211341635248246;
                  } else {
                      var169 = 0.0018959661007034783;
                  }
              } else {
                  if (input[3] > 0.8934818327409353) {
                      var169 = -0.013643447932437026;
                  } else {
                      var169 = 0.0009511069602498266;
                  }
              }
          }
      } else {
          if (input[2] <= -0.2707003273254145) {
              if (input[5] > 83.75558925058311) {
                  if (input[10] > 2.5000000000000004) {
                      var169 = 0.033528281826731884;
                  } else {
                      var169 = 0.0005755016818620888;
                  }
              } else {
                  if (input[6] <= -0.831454568954585) {
                      var169 = -0.0007568030987120096;
                  } else {
                      var169 = 0.00805986835821485;
                  }
              }
          } else {
              if (input[2] <= -0.2542332324482474) {
                  if (input[2] <= -0.26179501232682617) {
                      var169 = -0.0039019133596017563;
                  } else {
                      var169 = -0.03677911505321167;
                  }
              } else {
                  if (input[6] <= -4.096403012396194) {
                      var169 = 0.01170800831164113;
                  } else {
                      var169 = -0.0009022564831136896;
                  }
              }
          }
      }
      var var170;
      if (input[4] <= -8.76737386423564) {
          if (input[10] > 3.5000000000000004) {
              var170 = 0.016274020215888918;
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var170 = -0.03851745821761329;
              } else {
                  var170 = 0.005018256785044894;
              }
          }
      } else {
          if (input[6] <= -10.140707619951096) {
              var170 = 0.01289455411444741;
          } else {
              if (input[4] <= -7.712317663256087) {
                  if (input[6] <= -5.379413601618121) {
                      var170 = 0.01968503390714059;
                  } else {
                      var170 = -0.0044129625987775435;
                  }
              } else {
                  if (input[2] <= -1.9123784633518905) {
                      var170 = -0.012799233967002327;
                  } else {
                      var170 = -0.000017863699448740173;
                  }
              }
          }
      }
      var var171;
      if (input[8] <= -1.4999999999999998) {
          var171 = -0.011112150742013339;
      } else {
          if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 9.500000000000002) {
                      var171 = 0.010048683882546216;
                  } else {
                      var171 = -0.017105842539358037;
                  }
              } else {
                  if (input[13] > 2.5000000000000004) {
                      var171 = 0.004337927186457199;
                  } else {
                      var171 = 0.04127853923445287;
                  }
              }
          } else {
              if (input[4] <= -0.03399001277826245) {
                  if (input[4] <= -0.19071640176439533) {
                      var171 = -0.00046847400243273823;
                  } else {
                      var171 = -0.008897154126854495;
                  }
              } else {
                  if (input[6] <= -5.117681189325094) {
                      var171 = -0.011645941691085028;
                  } else {
                      var171 = 0.0006998139970878989;
                  }
              }
          }
      }
      var var172;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[3] > 1.5495200352880245) {
              var172 = 0.014328815319304841;
          } else {
              if (input[4] > 6.995147082128496) {
                  var172 = -0.015345599038082117;
              } else {
                  if (input[4] > 6.1425581839202765) {
                      var172 = 0.02241318034580826;
                  } else {
                      var172 = 0.0010236089108123572;
                  }
              }
          }
      } else {
          if (input[7] <= -1.4999999999999998) {
              if (input[2] <= -0.797423785428864) {
                  if (input[10] > 2.5000000000000004) {
                      var172 = -0.0003671150985609668;
                  } else {
                      var172 = -0.024692224428856362;
                  }
              } else {
                  if (input[10] > 2.5000000000000004) {
                      var172 = -0.002289265731998375;
                  } else {
                      var172 = 0.013382786936546745;
                  }
              }
          } else {
              if (input[6] > 0.3551665137137319) {
                  if (input[0] > 28.941439086755278) {
                      var172 = -0.0005838039202569649;
                  } else {
                      var172 = -0.015737187473584262;
                  }
              } else {
                  if (input[6] <= -0.07527005098723467) {
                      var172 = 0.00016645172078189394;
                  } else {
                      var172 = 0.006001163962858587;
                  }
              }
          }
      }
      var var173;
      if (input[5] > 27.141286553166832) {
          if (input[0] > 26.383030344586114) {
              if (input[6] <= -2.5554043664065276) {
                  if (input[13] > 10.500000000000002) {
                      var173 = -0.01009033652031682;
                  } else {
                      var173 = -0.0010163024941457122;
                  }
              } else {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var173 = 0.0025370157132677267;
                  } else {
                      var173 = -0.0005969328845478345;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 30.755186602054312) {
                      var173 = -0.03793198528449639;
                  } else {
                      var173 = -0.018835746524728896;
                  }
              } else {
                  var173 = 0.0029849429453044475;
              }
          }
      } else {
          if (input[4] > 0.9187848953214247) {
              if (input[10] > 1.5000000000000002) {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var173 = -0.027622407444140767;
                  } else {
                      var173 = -0.004663804135832734;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var173 = -0.00853827641274191;
                  } else {
                      var173 = 0.01894106285204808;
                  }
              }
          } else {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] <= -4.036293855178701) {
                      var173 = -0.0184178632010117;
                  } else {
                      var173 = 0.02709843176025485;
                  }
              } else {
                  if (input[2] > 0.25887622514763803) {
                      var173 = 0.014953737625928729;
                  } else {
                      var173 = 0.001012274910611812;
                  }
              }
          }
      }
      var var174;
      if (input[2] > 0.025809299484776383) {
          if (input[0] > 25.51590802753186) {
              if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 60.256910276410956) {
                      var174 = 0.011672876050060949;
                  } else {
                      var174 = -0.02287101332314124;
                  }
              } else {
                  if (input[6] <= -4.22423090678842) {
                      var174 = 0.019367380683479526;
                  } else {
                      var174 = -0.000277047105160814;
                  }
              }
          } else {
              var174 = -0.026756158744041882;
          }
      } else {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[4] <= -0.6688301121124586) {
                  if (input[4] <= -6.382133466621322) {
                      var174 = 0.028341852278278235;
                  } else {
                      var174 = -0.0030168031999064566;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var174 = 0.030224309295594904;
                  } else {
                      var174 = 0.00534990277522578;
                  }
              }
          } else {
              if (input[0] > 64.75395318316197) {
                  if (input[4] > 1.21504549149153) {
                      var174 = -0.027919063979749494;
                  } else {
                      var174 = -0.005241844649434977;
                  }
              } else {
                  if (input[3] <= -0.20134330740589654) {
                      var174 = -0.0005615482912480124;
                  } else {
                      var174 = 0.003356159764661964;
                  }
              }
          }
      }
      var var175;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[5] > 91.29004180028802) {
              if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                  var175 = -0.032414890720941676;
              } else {
                  var175 = 0.0017093509448085878;
              }
          } else {
              if (input[0] > 27.469470602855804) {
                  if (input[13] > 6.500000000000001) {
                      var175 = 0.015567853513549028;
                  } else {
                      var175 = -0.00234961502021969;
                  }
              } else {
                  var175 = -0.02315230470073832;
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] > 1.0518052223976289) {
                  if (input[0] > 63.47585974173415) {
                      var175 = 0.0011268105732847962;
                  } else {
                      var175 = -0.011275021924705704;
                  }
              } else {
                  if (input[9] > 21.500000000000004) {
                      var175 = 0.01892550996706124;
                  } else {
                      var175 = -0.00047532588837557034;
                  }
              }
          } else {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -1.1940748965409262) {
                      var175 = -0.008555198595195717;
                  } else {
                      var175 = 0.0019154681390704368;
                  }
              } else {
                  if (input[2] <= -1.315773426511249) {
                      var175 = 0.00774582702648367;
                  } else {
                      var175 = -0.0008025058380344556;
                  }
              }
          }
      }
      var var176;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[13] > 10.500000000000002) {
              if (input[10] > 3.5000000000000004) {
                  if (input[9] > 3.5000000000000004) {
                      var176 = -0.015332485207709263;
                  } else {
                      var176 = 0.010984027855705361;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var176 = -0.006534172594356015;
                  } else {
                      var176 = 0.009112276731474049;
                  }
              }
          } else {
              if (input[4] > 6.995147082128496) {
                  var176 = -0.015457658756443993;
              } else {
                  if (input[4] > 5.244537663167775) {
                      var176 = 0.01586958864056132;
                  } else {
                      var176 = 0.0013715556890104555;
                  }
              }
          }
      } else {
          if (input[3] <= -0.5340223873031661) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 3.5000000000000004) {
                      var176 = 0.006618755432121079;
                  } else {
                      var176 = -0.00787596855835962;
                  }
              } else {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var176 = -0.006002159832638805;
                  } else {
                      var176 = 0.009709352217884756;
                  }
              }
          } else {
              if (input[0] > 44.50111137696333) {
                  if (input[6] <= -2.620058240574581) {
                      var176 = -0.006845983216237671;
                  } else {
                      var176 = 0.0007401259855990298;
                  }
              } else {
                  if (input[13] > 9.500000000000002) {
                      var176 = 0.0038773323830702646;
                  } else {
                      var176 = -0.005643462913975507;
                  }
              }
          }
      }
      var var177;
      if (input[38] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 78.73527750225064) {
              var177 = 0.016074287684684056;
          } else {
              if (input[6] > 7.1728245343270265) {
                  if (input[10] > 2.5000000000000004) {
                      var177 = 0.02014133639991266;
                  } else {
                      var177 = 0.0017750901996873851;
                  }
              } else {
                  if (input[13] > 2.5000000000000004) {
                      var177 = -0.002974478319905745;
                  } else {
                      var177 = 0.0038854127516276416;
                  }
              }
          }
      } else {
          if (input[3] > 0.4535255126752083) {
              if (input[5] > 46.93129976544811) {
                  if (input[6] > 3.4821968878924623) {
                      var177 = 0.0013760026345388129;
                  } else {
                      var177 = -0.0031857592607381457;
                  }
              } else {
                  if (input[4] > 4.452431186048718) {
                      var177 = 0.00477773193167129;
                  } else {
                      var177 = -0.015741266276142193;
                  }
              }
          } else {
              if (input[7] > 1.5000000000000002) {
                  if (input[4] <= -1.7220934315061662) {
                      var177 = 0.031190887033061804;
                  } else {
                      var177 = 0.0015223797017384086;
                  }
              } else {
                  if (input[6] > 2.5493545797764527) {
                      var177 = 0.0031514883513319813;
                  } else {
                      var177 = 0.00018864125149195923;
                  }
              }
          }
      }
      var var178;
      if (input[5] > 19.544289135213152) {
          if (input[30] > 0.000000000000000000000000000000000010000000180025095) {
              var178 = -0.016068028680962798;
          } else {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 24.123903734081484) {
                      var178 = 0.0014746792389385083;
                  } else {
                      var178 = -0.02696130850453704;
                  }
              } else {
                  if (input[5] > 69.85608617600006) {
                      var178 = 0.0006527940869713305;
                  } else {
                      var178 = -0.002170830460446319;
                  }
              }
          }
      } else {
          if (input[6] > 3.957449210482031) {
              if (input[13] > 6.500000000000001) {
                  var178 = -0.005051960133604914;
              } else {
                  var178 = 0.032805831895779056;
              }
          } else {
              if (input[3] > 0.14816154989694033) {
                  if (input[4] > 3.02674812104328) {
                      var178 = -0.03385982808081423;
                  } else {
                      var178 = -0.002054074763635551;
                  }
              } else {
                  if (input[0] > 43.39903825771221) {
                      var178 = 0.010558685068660827;
                  } else {
                      var178 = 0.0004949014581328941;
                  }
              }
          }
      }
      var var179;
      if (input[5] > 92.60076342411848) {
          if (input[4] > 0.7977856053883731) {
              if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                  var179 = 0.020653701270249878;
              } else {
                  if (input[4] > 1.5491241530613575) {
                      var179 = -0.0013546214176415367;
                  } else {
                      var179 = 0.011330333327556813;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  var179 = -0.02714842555836878;
              } else {
                  if (input[6] > 1.006432761974532) {
                      var179 = -0.007444455303205039;
                  } else {
                      var179 = 0.00026607443939023707;
                  }
              }
          }
      } else {
          if (input[5] > 88.64965447194571) {
              if (input[3] <= -0.09825201155941231) {
                  var179 = 0.031038884076593345;
              } else {
                  if (input[4] <= -3.7749929394615718) {
                      var179 = -0.013270505209826944;
                  } else {
                      var179 = 0.006751856155659951;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -1.1411506569620806) {
                      var179 = -0.005220824915968803;
                  } else {
                      var179 = 0.010329803103524196;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var179 = -0.0032498518470709956;
                  } else {
                      var179 = 0.00023214663907518936;
                  }
              }
          }
      }
      var var180;
      if (input[6] > 5.776823337771391) {
          if (input[9] > 19.500000000000004) {
              if (input[4] > 3.747559616936297) {
                  if (input[6] > 7.572814452452991) {
                      var180 = -0.0018676283163647119;
                  } else {
                      var180 = 0.02609563583877866;
                  }
              } else {
                  var180 = -0.01013797729494708;
              }
          } else {
              if (input[2] > 0.6564316284823694) {
                  if (input[3] > 0.5647096098691142) {
                      var180 = -0.002708455159146128;
                  } else {
                      var180 = 0.014260722007699733;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var180 = 0.0057027926723021705;
                  } else {
                      var180 = -0.02435261061260641;
                  }
              }
          }
      } else {
          if (input[6] > 3.8237101336355157) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 67.94692510472329) {
                      var180 = 0.020216655472375653;
                  } else {
                      var180 = -0.0011911399904930393;
                  }
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var180 = -0.01663668329240164;
                  } else {
                      var180 = 0.0034197842198620855;
                  }
              }
          } else {
              if (input[3] > 0.8251442856487058) {
                  if (input[9] > 1.5000000000000002) {
                      var180 = -0.009213610956869935;
                  } else {
                      var180 = 0.021471534835283024;
                  }
              } else {
                  if (input[0] > 75.52030211082776) {
                      var180 = 0.007723029279149644;
                  } else {
                      var180 = -0.00003875255137112188;
                  }
              }
          }
      }
      var var181;
      if (input[5] > 27.141286553166832) {
          if (input[0] > 26.383030344586114) {
              if (input[0] > 27.865205959973) {
                  if (input[6] <= -2.398066420549097) {
                      var181 = -0.0028080679340924744;
                  } else {
                      var181 = 0.00026976273042587776;
                  }
              } else {
                  var181 = 0.017835627130085047;
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 30.755186602054312) {
                      var181 = -0.03644590475370153;
                  } else {
                      var181 = -0.017743679065408472;
                  }
              } else {
                  var181 = 0.0030055534060064865;
              }
          }
      } else {
          if (input[5] > 24.885282685569578) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 25.781461905908227) {
                      var181 = 0.009074855498181553;
                  } else {
                      var181 = 0.0315015624407193;
                  }
              } else {
                  if (input[0] > 44.161650469112) {
                      var181 = 0.019794469564646623;
                  } else {
                      var181 = -0.005400132231091901;
                  }
              }
          } else {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                      var181 = 0.03197516908248004;
                  } else {
                      var181 = -0.0064980805835482955;
                  }
              } else {
                  if (input[3] > 0.43692332172218623) {
                      var181 = -0.023585029934220656;
                  } else {
                      var181 = 0.0015355217015609077;
                  }
              }
          }
      }
      var var182;
      if (input[2] > 0.025809299484776383) {
          if (input[0] > 25.51590802753186) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 64.75395318316197) {
                      var182 = 0.010830869343786832;
                  } else {
                      var182 = -0.008564755693568793;
                  }
              } else {
                  if (input[6] <= -4.22423090678842) {
                      var182 = 0.02432603813368934;
                  } else {
                      var182 = -0.00011815567320033917;
                  }
              }
          } else {
              var182 = -0.02543880527827069;
          }
      } else {
          if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  var182 = 0.03365135041057187;
              } else {
                  if (input[5] > 43.306883112568904) {
                      var182 = 0.01852143900843822;
                  } else {
                      var182 = -0.0056495985815150215;
                  }
              }
          } else {
              if (input[2] <= -0.0719761568464675) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var182 = 0.001685521842237093;
                  } else {
                      var182 = -0.0018293177284774747;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var182 = -0.0036819593838386846;
                  } else {
                      var182 = 0.009987275603281151;
                  }
              }
          }
      }
      var var183;
      if (input[5] > 92.60076342411848) {
          if (input[4] > 0.7977856053883731) {
              if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                  var183 = 0.019341074147261755;
              } else {
                  if (input[2] > 0.12684171930706203) {
                      var183 = 0.0023245712992097083;
                  } else {
                      var183 = -0.010147438140387004;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  var183 = -0.026146364924206713;
              } else {
                  if (input[4] <= -6.711865554587188) {
                      var183 = -0.022652842688477837;
                  } else {
                      var183 = -0.0030611029512726856;
                  }
              }
          }
      } else {
          if (input[5] > 88.64965447194571) {
              if (input[3] <= -0.11156330253034764) {
                  var183 = 0.031183417659244414;
              } else {
                  if (input[4] <= -3.7749929394615718) {
                      var183 = -0.012020623764631706;
                  } else {
                      var183 = 0.006341764402232099;
                  }
              }
          } else {
              if (input[6] > 10.31060103068119) {
                  var183 = 0.014850839970734648;
              } else {
                  if (input[2] > 1.4199031747969257) {
                      var183 = -0.006276538487333561;
                  } else {
                      var183 = 0.00009964990089232232;
                  }
              }
          }
      }
      var var184;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[2] <= -0.27885231451531506) {
                  if (input[2] <= -0.5594853217452084) {
                      var184 = 0.004429555140449034;
                  } else {
                      var184 = -0.009154075602587037;
                  }
              } else {
                  if (input[3] > 0.07301218741877412) {
                      var184 = -0.006939975216088728;
                  } else {
                      var184 = 0.02247868213411559;
                  }
              }
          } else {
              if (input[6] <= -3.017878373503765) {
                  var184 = -0.02066166599847316;
              } else {
                  if (input[6] <= -2.0429136494001017) {
                      var184 = 0.018737168361164666;
                  } else {
                      var184 = -0.000073258447685977;
                  }
              }
          }
      } else {
          if (input[13] > 5.500000000000001) {
              if (input[7] > 1.5000000000000002) {
                  if (input[4] <= -3.2619166395046837) {
                      var184 = 0.035969781228500496;
                  } else {
                      var184 = 0.002881016179326525;
                  }
              } else {
                  if (input[5] > 80.00550695293408) {
                      var184 = -0.004361871179153864;
                  } else {
                      var184 = -0.00030245450462098764;
                  }
              }
          } else {
              if (input[2] <= -1.315773426511249) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var184 = -0.0016343300583326363;
                  } else {
                      var184 = 0.022285340843795028;
                  }
              } else {
                  if (input[6] <= -6.717684292131488) {
                      var184 = -0.016462219787314436;
                  } else {
                      var184 = 0.0005657313245000975;
                  }
              }
          }
      }
      var var185;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 52.55175265198409) {
              if (input[4] > 1.140378700310803) {
                  if (input[4] > 2.6350090914665336) {
                      var185 = -0.0004953346730937022;
                  } else {
                      var185 = 0.036102875429300664;
                  }
              } else {
                  if (input[4] <= -0.8989369849737693) {
                      var185 = -0.004849624322092965;
                  } else {
                      var185 = -0.046123903416890266;
                  }
              }
          } else {
              if (input[5] > 38.87182699364684) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var185 = 0.004575993360780433;
                  } else {
                      var185 = 0.03514019409842183;
                  }
              } else {
                  if (input[13] > 8.500000000000002) {
                      var185 = 0.017282779138927052;
                  } else {
                      var185 = -0.01419340161512165;
                  }
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] > 0.3147614493851478) {
                  if (input[0] > 62.753701799598225) {
                      var185 = 0.002782638916592216;
                  } else {
                      var185 = -0.010482932337202447;
                  }
              } else {
                  if (input[6] <= -1.8783643679700581) {
                      var185 = -0.0028765947583307538;
                  } else {
                      var185 = 0.007559163286245291;
                  }
              }
          } else {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var185 = -0.0009998099717760981;
                  } else {
                      var185 = 0.0035641981568268846;
                  }
              } else {
                  var185 = -0.00048044926136428393;
              }
          }
      }
      var var186;
      if (input[9] > 18.500000000000004) {
          if (input[0] > 86.25101283547333) {
              var186 = 0.02037849355184495;
          } else {
              if (input[7] <= -1.4999999999999998) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var186 = -0.02482781661085778;
                  } else {
                      var186 = -0.0019435336845390874;
                  }
              } else {
                  if (input[4] > 2.224830200500726) {
                      var186 = -0.002183736994363836;
                  } else {
                      var186 = 0.002265205411122064;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[10] > 2.5000000000000004) {
                  if (input[2] > 1.1219032542947727) {
                      var186 = -0.01595728443918915;
                  } else {
                      var186 = 0.0009666881739286355;
                  }
              } else {
                  if (input[3] > 0.31826535997168964) {
                      var186 = -0.011050569642535221;
                  } else {
                      var186 = -0.002115749293939974;
                  }
              }
          } else {
              if (input[5] > 72.02917243495783) {
                  if (input[6] <= -2.398066420549097) {
                      var186 = -0.010589223756727268;
                  } else {
                      var186 = -0.0005320999851505265;
                  }
              } else {
                  if (input[6] > 7.999681113877577) {
                      var186 = 0.016386396248682284;
                  } else {
                      var186 = 0.0006936954872729218;
                  }
              }
          }
      }
      var var187;
      if (input[5] > 117.01558275614404) {
          if (input[0] > 64.25004156967033) {
              if (input[6] <= -0.15050731119406482) {
                  var187 = -0.027916526361243196;
              } else {
                  if (input[2] > 0.34850749837570977) {
                      var187 = -0.001588930574629134;
                  } else {
                      var187 = 0.010716978423354478;
                  }
              }
          } else {
              if (input[6] > 2.7021091197227185) {
                  var187 = 0.007896833921986673;
              } else {
                  var187 = 0.02836377703972691;
              }
          }
      } else {
          if (input[5] > 100.90857751286742) {
              if (input[0] > 72.4839286421002) {
                  if (input[3] > 0.49090892248369816) {
                      var187 = -0.0065673782541013975;
                  } else {
                      var187 = -0.03255611036106676;
                  }
              } else {
                  if (input[4] <= -0.23350208572016248) {
                      var187 = -0.006408087360609685;
                  } else {
                      var187 = 0.003596104396730964;
                  }
              }
          } else {
              if (input[0] > 75.9664238348739) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var187 = 0.010238489565066582;
                  } else {
                      var187 = -0.003712055516324832;
                  }
              } else {
                  if (input[0] > 73.55579323924066) {
                      var187 = -0.0064685055460177755;
                  } else {
                      var187 = 0.00004353349808312155;
                  }
              }
          }
      }
      var var188;
      if (input[38] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
              var188 = 0.011435642555795402;
          } else {
              if (input[4] <= -0.5762604215079786) {
                  if (input[2] <= -1.315773426511249) {
                      var188 = 0.010786772510898813;
                  } else {
                      var188 = -0.0048766657454185226;
                  }
              } else {
                  if (input[5] > 64.80441652620755) {
                      var188 = 0.005027037220418383;
                  } else {
                      var188 = -0.0018855033751337073;
                  }
              }
          }
      } else {
          if (input[3] > 0.5298948855459753) {
              if (input[5] > 46.93129976544811) {
                  if (input[5] > 52.60526124172524) {
                      var188 = -0.0008047079708953799;
                  } else {
                      var188 = 0.014468162247260186;
                  }
              } else {
                  if (input[10] > 2.5000000000000004) {
                      var188 = -0.022712430108570575;
                  } else {
                      var188 = 0.0012998534359374319;
                  }
              }
          } else {
              if (input[7] > 1.5000000000000002) {
                  if (input[4] <= -2.0408506225936174) {
                      var188 = 0.030140168576371786;
                  } else {
                      var188 = 0.0014550547893080331;
                  }
              } else {
                  if (input[0] > 76.48950737788454) {
                      var188 = 0.010092245439697833;
                  } else {
                      var188 = 0.00038702449936625746;
                  }
              }
          }
      }
      var var189;
      if (input[8] <= -1.4999999999999998) {
          var189 = -0.010798450946164757;
      } else {
          if (input[5] <= -34.779391478962644) {
              if (input[14] > 0.000000000000000000000000000000000010000000180025095) {
                  var189 = 0.022064485858143162;
              } else {
                  if (input[4] > 0.36564692169617413) {
                      var189 = -0.019453528677761314;
                  } else {
                      var189 = 0.005954807564233787;
                  }
              }
          } else {
              if (input[5] <= -23.24721240218805) {
                  if (input[3] <= -0.3414643880554218) {
                      var189 = 0.0007598679254702818;
                  } else {
                      var189 = -0.025840264727975033;
                  }
              } else {
                  if (input[30] > 0.000000000000000000000000000000000010000000180025095) {
                      var189 = -0.01164527363075622;
                  } else {
                      var189 = 0.000089072179158804;
                  }
              }
          }
      }
      var var190;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 0.9715869529760879) {
              if (input[10] > 3.5000000000000004) {
                  if (input[2] <= -0.45302790421983913) {
                      var190 = 0.03337652342770869;
                  } else {
                      var190 = 0.006139987053204104;
                  }
              } else {
                  var190 = 0.00028917092780738447;
              }
          } else {
              if (input[4] <= -0.4950921444997715) {
                  if (input[4] <= -1.0376436871914176) {
                      var190 = 0.0007484263896738055;
                  } else {
                      var190 = 0.01658415471358454;
                  }
              } else {
                  if (input[2] > 1.0016590802373793) {
                      var190 = 0.011892822244816371;
                  } else {
                      var190 = -0.01179971727778352;
                  }
              }
          }
      } else {
          if (input[7] <= -1.4999999999999998) {
              if (input[5] <= -11.42528703884175) {
                  if (input[0] > 30.828549176161413) {
                      var190 = 0.026289077910953463;
                  } else {
                      var190 = 0.0007366039642056478;
                  }
              } else {
                  if (input[10] > 1.5000000000000002) {
                      var190 = -0.0029910345256064555;
                  } else {
                      var190 = -0.021470827370233078;
                  }
              }
          } else {
              if (input[3] <= -0.32611024270756656) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var190 = -0.0026423765665895;
                  } else {
                      var190 = 0.004413529306423286;
                  }
              } else {
                  if (input[0] > 26.383030344586114) {
                      var190 = -0.0003906821892134399;
                  } else {
                      var190 = -0.01763918685796979;
                  }
              }
          }
      }
      var var191;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[9] > 21.500000000000004) {
                  var191 = 0.02837060345800818;
              } else {
                  if (input[10] > 2.5000000000000004) {
                      var191 = 0.007772906904741198;
                  } else {
                      var191 = -0.004353667593202469;
                  }
              }
          } else {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -0.4647557580206713) {
                      var191 = -0.005266143841810856;
                  } else {
                      var191 = 0.008640783316433963;
                  }
              } else {
                  if (input[3] <= -0.8091842205187499) {
                      var191 = 0.0026391986750277374;
                  } else {
                      var191 = -0.003268937360053166;
                  }
              }
          }
      } else {
          if (input[2] <= -0.2707003273254145) {
              if (input[5] > 83.75558925058311) {
                  if (input[10] > 2.5000000000000004) {
                      var191 = 0.03163562411881697;
                  } else {
                      var191 = 0.0008872720022675848;
                  }
              } else {
                  if (input[6] <= -0.831454568954585) {
                      var191 = -0.0007300978629924801;
                  } else {
                      var191 = 0.0075910398814940955;
                  }
              }
          } else {
              if (input[2] <= -0.18032876532877087) {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var191 = -0.015041041691125549;
                  } else {
                      var191 = -0.003122846669479413;
                  }
              } else {
                  if (input[6] <= -4.032321514980188) {
                      var191 = 0.011356814752172963;
                  } else {
                      var191 = -0.0005407633955115194;
                  }
              }
          }
      }
      var var192;
      if (input[6] <= -6.069857858271648) {
          if (input[4] <= -4.21670651579148) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var192 = -0.014868232591676397;
                  } else {
                      var192 = 0.0074092057095207975;
                  }
              } else {
                  if (input[13] > 10.500000000000002) {
                      var192 = 0.03337088922730297;
                  } else {
                      var192 = 0.002316287154098971;
                  }
              }
          } else {
              if (input[4] <= -3.038533070624908) {
                  if (input[9] > 3.5000000000000004) {
                      var192 = -0.01947362496247148;
                  } else {
                      var192 = 0.002346516576689988;
                  }
              } else {
                  if (input[9] > 12.500000000000002) {
                      var192 = -0.012588733603897818;
                  } else {
                      var192 = 0.0007895818698731817;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[0] > 47.87234042553219) {
                  var192 = -0.009384660965758681;
              } else {
                  if (input[0] > 32.903904947513766) {
                      var192 = 0.024418025601301064;
                  } else {
                      var192 = 0.004359554200491759;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[5] > 24.0530548127776) {
                      var192 = -0.01526328692344836;
                  } else {
                      var192 = -0.0002151306761901023;
                  }
              } else {
                  if (input[6] <= -5.555294989730455) {
                      var192 = -0.014843836350618662;
                  } else {
                      var192 = 0.0001659024112642838;
                  }
              }
          }
      }
      var var193;
      if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[0] > 52.55175265198409) {
              if (input[4] > 1.140378700310803) {
                  if (input[6] > 2.96096381512298) {
                      var193 = 0.03151660964491846;
                  } else {
                      var193 = -0.0033842259893856865;
                  }
              } else {
                  if (input[4] <= -0.8989369849737693) {
                      var193 = -0.004530777339377265;
                  } else {
                      var193 = -0.04447656509539895;
                  }
              }
          } else {
              if (input[5] > 38.87182699364684) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var193 = 0.004321246604648165;
                  } else {
                      var193 = 0.0331183112451189;
                  }
              } else {
                  if (input[13] > 8.500000000000002) {
                      var193 = 0.016307412258631537;
                  } else {
                      var193 = -0.013498668879911309;
                  }
              }
          }
      } else {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[0] > 13.23529411764625) {
                  if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
                      var193 = 0.013334375619606157;
                  } else {
                      var193 = -0.003037741793317569;
                  }
              } else {
                  var193 = 0.023536241212695302;
              }
          } else {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -1.1940748965409262) {
                      var193 = -0.008253206274484207;
                  } else {
                      var193 = 0.0017362969261870646;
                  }
              } else {
                  if (input[6] <= -5.649766231839755) {
                      var193 = 0.005020694147922676;
                  } else {
                      var193 = -0.0008547217528573683;
                  }
              }
          }
      }
      var var194;
      if (input[6] <= -6.189019565280997) {
          if (input[4] <= -4.21670651579148) {
              if (input[2] <= -0.41786137249586686) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var194 = 0.018208310028877038;
                  } else {
                      var194 = 0.0016480455859311073;
                  }
              } else {
                  var194 = -0.014741785588991946;
              }
          } else {
              if (input[4] <= -3.0935790789862545) {
                  if (input[2] <= -1.285895375042583) {
                      var194 = -0.006964587073194498;
                  } else {
                      var194 = -0.02809973404305291;
                  }
              } else {
                  if (input[3] <= -0.6878497943953014) {
                      var194 = -0.00031702560392539203;
                  } else {
                      var194 = -0.02377923033785143;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[0] > 47.40082564351635) {
                  if (input[2] <= -0.7459791426473048) {
                      var194 = -0.024277940453385286;
                  } else {
                      var194 = -0.0017527971945151565;
                  }
              } else {
                  if (input[3] <= -0.6758514167523011) {
                      var194 = 0.00437455972519753;
                  } else {
                      var194 = 0.032642805526238224;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[5] > 24.0530548127776) {
                      var194 = -0.014545090777107332;
                  } else {
                      var194 = -0.000046175255893797143;
                  }
              } else {
                  if (input[6] <= -5.555294989730455) {
                      var194 = -0.01419224967013874;
                  } else {
                      var194 = 0.0001641725780112082;
                  }
              }
          }
      }
      var var195;
      if (input[4] <= -8.76737386423564) {
          if (input[13] > 4.500000000000001) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var195 = -0.03477510828390521;
              } else {
                  var195 = 0.000700005232990272;
              }
          } else {
              var195 = 0.01849352435140627;
          }
      } else {
          if (input[4] <= -7.394899536019147) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  var195 = 0.02771898126820235;
              } else {
                  if (input[5] > 76.21868548785203) {
                      var195 = -0.027087480688787358;
                  } else {
                      var195 = 0.006781330235439119;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 3.5000000000000004) {
                      var195 = -0.006232996181852742;
                  } else {
                      var195 = 0.007934570218491085;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var195 = -0.0019327919221890971;
                  } else {
                      var195 = 0.00011302962523664588;
                  }
              }
          }
      }
      var var196;
      if (input[13] > 10.500000000000002) {
          if (input[3] > 1.3340473457035107) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var196 = -0.03655400396872166;
              } else {
                  var196 = -0.004018826167104942;
              }
          } else {
              if (input[3] > 1.118593788827117) {
                  if (input[10] > 2.5000000000000004) {
                      var196 = -0.003995604037120709;
                  } else {
                      var196 = 0.023905233940968787;
                  }
              } else {
                  if (input[14] > 0.000000000000000000000000000000000010000000180025095) {
                      var196 = 0.013565856824831735;
                  } else {
                      var196 = -0.001555067091717371;
                  }
              }
          }
      } else {
          if (input[3] > 1.4918805968895918) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] > 1.9170530186274009) {
                      var196 = 0.005218779427277375;
                  } else {
                      var196 = -0.017857173087206062;
                  }
              } else {
                  if (input[5] > 76.21868548785203) {
                      var196 = 0.01823621408667518;
                  } else {
                      var196 = 0.000884074042025055;
                  }
              }
          } else {
              if (input[2] > 1.2229841138647866) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var196 = -0.01600689835913143;
                  } else {
                      var196 = -0.002322795685496994;
                  }
              } else {
                  if (input[6] > 2.753231205171612) {
                      var196 = 0.002142290548355058;
                  } else {
                      var196 = -0.00022993321392257888;
                  }
              }
          }
      }
      var var197;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[3] > 0.8934818327409353) {
              if (input[9] > 10.500000000000002) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var197 = -0.008446062224376652;
                  } else {
                      var197 = -0.030917113253755974;
                  }
              } else {
                  var197 = 0.003950124704976056;
              }
          } else {
              if (input[2] > 0.2831395178635617) {
                  if (input[3] > 0.3879938713040886) {
                      var197 = 0.0007231744913598658;
                  } else {
                      var197 = 0.021367080044772464;
                  }
              } else {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var197 = 0.005807906160863582;
                  } else {
                      var197 = -0.0009088353846324322;
                  }
              }
          }
      } else {
          if (input[2] <= -0.3112421825088057) {
              if (input[6] <= -4.156678023401004) {
                  if (input[4] <= -1.6767587965079047) {
                      var197 = 0.00015069673183811154;
                  } else {
                      var197 = -0.009896749721023938;
                  }
              } else {
                  if (input[5] > 83.75558925058311) {
                      var197 = 0.03300010274581829;
                  } else {
                      var197 = 0.003209801052922456;
                  }
              }
          } else {
              if (input[3] <= -0.20134330740589654) {
                  if (input[4] <= -5.041750399183811) {
                      var197 = 0.02258362097013501;
                  } else {
                      var197 = -0.007903471732999108;
                  }
              } else {
                  if (input[0] > 26.383030344586114) {
                      var197 = -0.00013824659610255546;
                  } else {
                      var197 = -0.0258364542877466;
                  }
              }
          }
      }
      var var198;
      if (input[6] > 5.776823337771391) {
          if (input[9] > 19.500000000000004) {
              if (input[4] > 3.747559616936297) {
                  if (input[6] > 7.572814452452991) {
                      var198 = -0.0016391728427735987;
                  } else {
                      var198 = 0.024669647947348033;
                  }
              } else {
                  var198 = -0.009672479834108115;
              }
          } else {
              if (input[2] > 0.6564316284823694) {
                  if (input[3] > 0.5647096098691142) {
                      var198 = -0.002470401441022442;
                  } else {
                      var198 = 0.013333974826927417;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var198 = 0.004797878528673487;
                  } else {
                      var198 = -0.02340656045668144;
                  }
              }
          }
      } else {
          if (input[6] > 3.8237101336355157) {
              if (input[4] <= -1.4884140029464057) {
                  if (input[0] > 61.592485969300654) {
                      var198 = 0.005789835554396802;
                  } else {
                      var198 = 0.044784914795307315;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var198 = 0.0066706519308252655;
                  } else {
                      var198 = -0.0032616206223469815;
                  }
              }
          } else {
              if (input[3] > 0.8251442856487058) {
                  if (input[9] > 1.5000000000000002) {
                      var198 = -0.008649399519795058;
                  } else {
                      var198 = 0.020272755506801642;
                  }
              } else {
                  if (input[3] > 0.7850434804160938) {
                      var198 = 0.011831488254071876;
                  } else {
                      var198 = 0.000002894305596575136;
                  }
              }
          }
      }
      var var199;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] <= -5.20604877356585) {
              if (input[10] > 1.5000000000000002) {
                  if (input[5] > 1.7833279067643293) {
                      var199 = -0.0021269246041311983;
                  } else {
                      var199 = 0.0138172973454058;
                  }
              } else {
                  var199 = 0.02139102164410432;
              }
          } else {
              if (input[6] > 0.5201967351303219) {
                  if (input[3] > 0.000000000000000000000000000000000010000000180025095) {
                      var199 = 0.0013881049477667846;
                  } else {
                      var199 = 0.014673121270473459;
                  }
              } else {
                  if (input[13] > 6.500000000000001) {
                      var199 = 0.0021378011222046847;
                  } else {
                      var199 = -0.0079410199629943;
                  }
              }
          }
      } else {
          if (input[7] <= -1.4999999999999998) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  var199 = -0.021892449107356445;
              } else {
                  if (input[4] <= -3.2619166395046837) {
                      var199 = -0.015559309649368434;
                  } else {
                      var199 = 0.0030379787975623198;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var199 = 0.011816894309114633;
              } else {
                  if (input[6] > 0.3551665137137319) {
                      var199 = -0.000902095104519197;
                  } else {
                      var199 = 0.0006611023501956479;
                  }
              }
          }
      }
      var var200;
      if (input[6] <= -6.069857858271648) {
          if (input[4] <= -3.9776333795063805) {
              if (input[2] <= -0.37162616348632066) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var200 = 0.01411832780614056;
                  } else {
                      var200 = 0.0006722649421976163;
                  }
              } else {
                  var200 = -0.015121189452954651;
              }
          } else {
              if (input[4] <= -3.038533070624908) {
                  if (input[9] > 3.5000000000000004) {
                      var200 = -0.02212310693586301;
                  } else {
                      var200 = 0.00547833317156025;
                  }
              } else {
                  if (input[0] > 47.22048117114918) {
                      var200 = -0.016295803748006033;
                  } else {
                      var200 = -0.0001794456569820995;
                  }
              }
          }
      } else {
          if (input[6] <= -5.858846461727939) {
              if (input[9] > 10.500000000000002) {
                  if (input[0] > 32.903904947513766) {
                      var200 = 0.04135084274615093;
                  } else {
                      var200 = 0.007138562502643169;
                  }
              } else {
                  var200 = -0.0028646462848359827;
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[6] <= -5.379413601618121) {
                      var200 = 0.009860704326954232;
                  } else {
                      var200 = -0.009781394652129861;
                  }
              } else {
                  if (input[3] <= -1.1437063176950601) {
                      var200 = 0.00908367685273447;
                  } else {
                      var200 = 0.00006575473749478443;
                  }
              }
          }
      }
      var var201;
      if (input[13] > 10.500000000000002) {
          if (input[3] > 1.3340473457035107) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var201 = -0.03517101919854562;
              } else {
                  var201 = -0.0036958534858581946;
              }
          } else {
              if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] > 1.010681701329975) {
                      var201 = 0.02078876723441493;
                  } else {
                      var201 = 0.0014612231741355742;
                  }
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var201 = -0.00808825391679112;
                  } else {
                      var201 = 0.00045207426229729175;
                  }
              }
          }
      } else {
          if (input[10] > 3.5000000000000004) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 8.500000000000002) {
                      var201 = -0.005130406228631416;
                  } else {
                      var201 = 0.006865610340598266;
                  }
              } else {
                  if (input[13] > 8.500000000000002) {
                      var201 = 0.011894605217898237;
                  } else {
                      var201 = -0.0052366928770018325;
                  }
              }
          } else {
              if (input[4] <= -8.76737386423564) {
                  var201 = -0.02115111781037748;
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var201 = 0.007960254131100492;
                  } else {
                      var201 = -0.0006408756262948933;
                  }
              }
          }
      }
      var var202;
      if (input[5] > 19.544289135213152) {
          if (input[30] > 0.000000000000000000000000000000000010000000180025095) {
              var202 = -0.014928588405466217;
          } else {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 24.123903734081484) {
                      var202 = 0.0013636074621275142;
                  } else {
                      var202 = -0.025535070349893347;
                  }
              } else {
                  if (input[5] > 69.85608617600006) {
                      var202 = 0.0007128158055435189;
                  } else {
                      var202 = -0.002114171250035982;
                  }
              }
          }
      } else {
          if (input[6] > 3.957449210482031) {
              if (input[13] > 6.500000000000001) {
                  var202 = -0.004279866007115929;
              } else {
                  var202 = 0.03105294973156013;
              }
          } else {
              if (input[3] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 2.5000000000000004) {
                      var202 = -0.0177975791687363;
                  } else {
                      var202 = 0.006942489050091462;
                  }
              } else {
                  if (input[3] <= -0.2072500793613881) {
                      var202 = -0.000008750054064664354;
                  } else {
                      var202 = 0.010517510518673678;
                  }
              }
          }
      }
      var var203;
      if (input[5] > 92.60076342411848) {
          if (input[4] > 0.7977856053883731) {
              if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                  var203 = 0.018134069345838746;
              } else {
                  if (input[4] > 1.5491241530613575) {
                      var203 = -0.0014409263403475769;
                  } else {
                      var203 = 0.010629352026715179;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  var203 = -0.024095127117510138;
              } else {
                  if (input[6] > 1.006432761974532) {
                      var203 = -0.0068974792084533915;
                  } else {
                      var203 = 0.0003718020696006738;
                  }
              }
          }
      } else {
          if (input[5] > 88.03613376248084) {
              if (input[3] > 0.4044684408354277) {
                  if (input[3] > 0.5474301788428937) {
                      var203 = 0.002926254739736479;
                  } else {
                      var203 = -0.016375898311379627;
                  }
              } else {
                  if (input[9] > 15.500000000000002) {
                      var203 = 0.03348370241772479;
                  } else {
                      var203 = 0.005827336882256274;
                  }
              }
          } else {
              if (input[4] > 2.1419746152525203) {
                  if (input[0] > 64.75395318316197) {
                      var203 = 0.0046247468068374795;
                  } else {
                      var203 = -0.002307588257640383;
                  }
              } else {
                  if (input[4] > 1.5945254787583292) {
                      var203 = 0.005353868500287837;
                  } else {
                      var203 = 0.00008103260699229081;
                  }
              }
          }
      }
      var var204;
      if (input[5] > 27.141286553166832) {
          if (input[0] > 26.383030344586114) {
              if (input[0] > 27.865205959973) {
                  if (input[6] <= -2.398066420549097) {
                      var204 = -0.0026902946874264415;
                  } else {
                      var204 = 0.0002558331845162128;
                  }
              } else {
                  var204 = 0.016985142554263713;
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 30.755186602054312) {
                      var204 = -0.03459588062900627;
                  } else {
                      var204 = -0.016127633509315682;
                  }
              } else {
                  var204 = 0.0033572006933424874;
              }
          }
      } else {
          if (input[5] > 24.885282685569578) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 25.781461905908227) {
                      var204 = 0.008466645624960035;
                  } else {
                      var204 = 0.02976243643338271;
                  }
              } else {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var204 = 0.009135206920359453;
                  } else {
                      var204 = -0.015721126367768967;
                  }
              }
          } else {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                      var204 = 0.02989800392511833;
                  } else {
                      var204 = -0.006075355654940676;
                  }
              } else {
                  if (input[3] > 0.43692332172218623) {
                      var204 = -0.02217987190220127;
                  } else {
                      var204 = 0.0014036742813264421;
                  }
              }
          }
      }
      var var205;
      if (input[8] <= -1.4999999999999998) {
          var205 = -0.010451046554716598;
      } else {
          if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 9.500000000000002) {
                      var205 = 0.009147117219935568;
                  } else {
                      var205 = -0.016733566088607398;
                  }
              } else {
                  if (input[13] > 2.5000000000000004) {
                      var205 = 0.004015238385328301;
                  } else {
                      var205 = 0.038234911063198866;
                  }
              }
          } else {
              if (input[4] > 5.42653906653272) {
                  if (input[4] > 5.636429675392096) {
                      var205 = 0.0007070763078296513;
                  } else {
                      var205 = 0.011823911105418883;
                  }
              } else {
                  if (input[4] > 3.9460979913492005) {
                      var205 = -0.002603443968939379;
                  } else {
                      var205 = 0.000011961224288354297;
                  }
              }
          }
      }
      var var206;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 6.995147082128496) {
              var206 = -0.014985053990951229;
          } else {
              if (input[4] > 5.244537663167775) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var206 = 0.02351228592986433;
                  } else {
                      var206 = -0.005414310745182598;
                  }
              } else {
                  if (input[4] > 4.982840162738646) {
                      var206 = -0.02195358343378538;
                  } else {
                      var206 = 0.0007811796618471382;
                  }
              }
          }
      } else {
          if (input[3] <= -0.5340223873031661) {
              if (input[3] <= -0.7393184317136119) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var206 = -0.010940924822123735;
                  } else {
                      var206 = 0.0024416158718710457;
                  }
              } else {
                  if (input[0] > 54.471194204717385) {
                      var206 = -0.017347020861041423;
                  } else {
                      var206 = 0.009374997486588677;
                  }
              }
          } else {
              if (input[0] > 44.50111137696333) {
                  if (input[6] <= -2.620058240574581) {
                      var206 = -0.006283786960876514;
                  } else {
                      var206 = 0.0006979544670102408;
                  }
              } else {
                  if (input[13] > 9.500000000000002) {
                      var206 = 0.003602593315042522;
                  } else {
                      var206 = -0.005251805810136328;
                  }
              }
          }
      }
      var var207;
      if (input[9] > 5.500000000000001) {
          if (input[9] > 7.500000000000001) {
              if (input[2] > 0.025809299484776383) {
                  if (input[4] <= -1.103961271626989) {
                      var207 = -0.0047751116889591435;
                  } else {
                      var207 = 0.0004340214043681681;
                  }
              } else {
                  if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                      var207 = 0.012331164383281207;
                  } else {
                      var207 = 0.0006353278408568198;
                  }
              }
          } else {
              if (input[0] > 57.62589042924083) {
                  if (input[0] > 62.753701799598225) {
                      var207 = -0.00395964647932762;
                  } else {
                      var207 = 0.013205734074585723;
                  }
              } else {
                  if (input[5] > 68.73201742693793) {
                      var207 = -0.02519287605125404;
                  } else {
                      var207 = -0.004672890118822065;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] <= -8.30864402369986) {
                  var207 = 0.017599578318887043;
              } else {
                  if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                      var207 = -0.014550677517326308;
                  } else {
                      var207 = -0.0009797063514834679;
                  }
              }
          } else {
              if (input[4] > 1.017111697377455) {
                  if (input[4] > 5.990368656568688) {
                      var207 = 0.010367585628389017;
                  } else {
                      var207 = -0.0039952676841982756;
                  }
              } else {
                  if (input[2] > 0.9689046583490236) {
                      var207 = 0.024522856266469908;
                  } else {
                      var207 = 0.003536629256819124;
                  }
              }
          }
      }
      var var208;
      if (input[6] > 5.776823337771391) {
          if (input[6] > 6.138234227742873) {
              if (input[3] > 0.2883931799611021) {
                  if (input[3] > 0.5647096098691142) {
                      var208 = -0.0006612784883839556;
                  } else {
                      var208 = 0.011822129825132515;
                  }
              } else {
                  var208 = -0.015283006644383958;
              }
          } else {
              if (input[2] > 1.3853947133785054) {
                  var208 = -0.025892637389699897;
              } else {
                  if (input[13] > 2.5000000000000004) {
                      var208 = -0.002119850330705802;
                  } else {
                      var208 = -0.02040824983772192;
                  }
              }
          }
      } else {
          if (input[6] > 3.8237101336355157) {
              if (input[4] <= -1.4884140029464057) {
                  if (input[0] > 61.592485969300654) {
                      var208 = 0.0056380786248594215;
                  } else {
                      var208 = 0.04190133585566827;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var208 = 0.006238459116566713;
                  } else {
                      var208 = -0.003155825637008627;
                  }
              }
          } else {
              if (input[2] > 1.0828963714962498) {
                  if (input[6] > 2.450311935013088) {
                      var208 = -0.020701390693723218;
                  } else {
                      var208 = 0.00967896343899034;
                  }
              } else {
                  if (input[4] > 7.214329904560428) {
                      var208 = 0.012842090227620968;
                  } else {
                      var208 = -0.00007662260077468587;
                  }
              }
          }
      }
      var var209;
      if (input[5] > 92.60076342411848) {
          if (input[13] > 8.500000000000002) {
              if (input[4] > 1.7593927560227316) {
                  if (input[2] > 0.3145628078167882) {
                      var209 = -0.005933849136531619;
                  } else {
                      var209 = 0.026955615496872462;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var209 = -0.02568630649305775;
                  } else {
                      var209 = -0.0056646181368431685;
                  }
              }
          } else {
              if (input[13] > 7.500000000000001) {
                  if (input[9] > 12.500000000000002) {
                      var209 = 0.03347501308070485;
                  } else {
                      var209 = -0.004034641389084761;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var209 = 0.007844266340615977;
                  } else {
                      var209 = -0.0031763334944098403;
                  }
              }
          }
      } else {
          if (input[5] > 88.03613376248084) {
              if (input[3] > 0.4044684408354277) {
                  if (input[5] > 91.91928172844878) {
                      var209 = 0.017481820084035423;
                  } else {
                      var209 = -0.0027617928136501033;
                  }
              } else {
                  if (input[9] > 15.500000000000002) {
                      var209 = 0.03162213995733718;
                  } else {
                      var209 = 0.005570988278289114;
                  }
              }
          } else {
              if (input[14] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] <= -10.071781663624618) {
                      var209 = 0.011533270163573726;
                  } else {
                      var209 = -0.0327838737015009;
                  }
              } else {
                  var209 = -0.00012151681598329065;
              }
          }
      }
      var var210;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[3] > 1.442442771255717) {
                  var210 = 0.028322474795904426;
              } else {
                  if (input[0] > 73.17190257813438) {
                      var210 = -0.02174438400616048;
                  } else {
                      var210 = 0.0034163183544430676;
                  }
              }
          } else {
              if (input[4] <= -6.2078673308808865) {
                  var210 = -0.018453179687504633;
              } else {
                  if (input[7] > 1.5000000000000002) {
                      var210 = -0.0157428417778441;
                  } else {
                      var210 = 0.0017040646080369569;
                  }
              }
          }
      } else {
          if (input[7] <= -1.4999999999999998) {
              if (input[9] > 14.500000000000002) {
                  if (input[4] <= -3.2619166395046837) {
                      var210 = -0.039136425080187574;
                  } else {
                      var210 = -0.006515453242541967;
                  }
              } else {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var210 = -0.015191342379715542;
                  } else {
                      var210 = 0.004022005290341755;
                  }
              }
          } else {
              if (input[6] > 0.3551665137137319) {
                  if (input[0] > 28.941439086755278) {
                      var210 = -0.0005589507642503606;
                  } else {
                      var210 = -0.01414144012192235;
                  }
              } else {
                  if (input[6] <= -0.07527005098723467) {
                      var210 = 0.00017663518264309668;
                  } else {
                      var210 = 0.005554709219314412;
                  }
              }
          }
      }
      var var211;
      if (input[9] > 18.500000000000004) {
          if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[5] > 96.12555884548514) {
                  if (input[13] > 5.500000000000001) {
                      var211 = 0.029308781207660187;
                  } else {
                      var211 = 0.00245495939849941;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var211 = 0.01064677421359031;
                  } else {
                      var211 = -0.0008677229015960716;
                  }
              }
          } else {
              if (input[3] > 0.9580914413420627) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var211 = -0.0010966230441524997;
                  } else {
                      var211 = -0.023467192705107068;
                  }
              } else {
                  if (input[2] > 0.6973436951559976) {
                      var211 = 0.011062570244645912;
                  } else {
                      var211 = -0.0011749425102645077;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[6] > 6.744411454960361) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var211 = -0.03286490773602833;
                  } else {
                      var211 = 0.00021315947431696007;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var211 = 0.001080870398120128;
                  } else {
                      var211 = -0.004786679831980649;
                  }
              }
          } else {
              if (input[5] > 72.02917243495783) {
                  var211 = -0.0013339435995487281;
              } else {
                  if (input[13] > 1.5000000000000002) {
                      var211 = 0.0013874433200095305;
                  } else {
                      var211 = -0.005479976542712978;
                  }
              }
          }
      }
      var var212;
      if (input[13] > 10.500000000000002) {
          if (input[3] > 1.3340473457035107) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var212 = -0.033714191895186256;
              } else {
                  var212 = -0.003592854810861988;
              }
          } else {
              if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 4.500000000000001) {
                      var212 = -0.012009677510041665;
                  } else {
                      var212 = 0.00592020466966231;
                  }
              } else {
                  if (input[6] > 2.805208362664828) {
                      var212 = -0.010532319812312374;
                  } else {
                      var212 = -0.0003179940895278327;
                  }
              }
          }
      } else {
          if (input[3] > 1.4918805968895918) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  var212 = -0.005303116918993323;
              } else {
                  if (input[5] > 76.21868548785203) {
                      var212 = 0.017305950532712784;
                  } else {
                      var212 = 0.0006047828953117041;
                  }
              }
          } else {
              if (input[2] > 1.2229841138647866) {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var212 = -0.015325576476052717;
                  } else {
                      var212 = -0.0019643169296003197;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var212 = 0.0014930674571084427;
                  } else {
                      var212 = -0.0004266525934243191;
                  }
              }
          }
      }
      var var213;
      if (input[8] <= -1.4999999999999998) {
          var213 = -0.010021585481359433;
      } else {
          if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[31] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 10.500000000000002) {
                      var213 = -0.023552799118679673;
                  } else {
                      var213 = 0.002780571479739355;
                  }
              } else {
                  if (input[6] <= -0.9700695059864084) {
                      var213 = 0.014737026847935304;
                  } else {
                      var213 = -0.0010139335126274306;
                  }
              }
          } else {
              if (input[38] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 78.73527750225064) {
                      var213 = 0.015453256185461325;
                  } else {
                      var213 = -0.001701977602130311;
                  }
              } else {
                  if (input[5] <= -23.24721240218805) {
                      var213 = -0.004080531533735998;
                  } else {
                      var213 = 0.0002491908046402939;
                  }
              }
          }
      }
      var var214;
      if (input[9] > 5.500000000000001) {
          if (input[9] > 7.500000000000001) {
              if (input[4] > 3.2032943389782225) {
                  if (input[5] > 8.95767471618312) {
                      var214 = 0.00042542710273529264;
                  } else {
                      var214 = 0.01537973777468115;
                  }
              } else {
                  if (input[4] > 2.344350703463393) {
                      var214 = -0.004865000672130141;
                  } else {
                      var214 = 0.00020883871119148074;
                  }
              }
          } else {
              if (input[0] > 57.62589042924083) {
                  if (input[6] <= -3.631949801469407) {
                      var214 = -0.02444828873259639;
                  } else {
                      var214 = 0.004114148012496298;
                  }
              } else {
                  if (input[5] > 73.625872260263) {
                      var214 = -0.02728948866424062;
                  } else {
                      var214 = -0.004762335226715606;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[7] <= -1.4999999999999998) {
                  var214 = 0.022677945061630792;
              } else {
                  if (input[5] > 0.000000000000000000000000000000000010000000180025095) {
                      var214 = -0.0012771888201506584;
                  } else {
                      var214 = -0.022354074834970455;
                  }
              }
          } else {
              if (input[4] <= -1.3242311696170128) {
                  if (input[3] > 0.9087956706751333) {
                      var214 = 0.04782296614409822;
                  } else {
                      var214 = 0.0025374119964183244;
                  }
              } else {
                  if (input[5] <= -12.958890163792335) {
                      var214 = 0.02786735631182375;
                  } else {
                      var214 = -0.0006407608188095771;
                  }
              }
          }
      }
      var var215;
      if (input[13] > 5.500000000000001) {
          if (input[4] <= -8.76737386423564) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var215 = -0.03411029568277495;
              } else {
                  var215 = 0.00023776382634609633;
              }
          } else {
              if (input[7] > 1.5000000000000002) {
                  if (input[4] <= -3.2619166395046837) {
                      var215 = 0.02792391928654092;
                  } else {
                      var215 = 0.0032927492478814083;
                  }
              } else {
                  if (input[5] > 80.00550695293408) {
                      var215 = -0.003742263109745361;
                  } else {
                      var215 = 0.00019203777402035494;
                  }
              }
          }
      } else {
          if (input[4] <= -8.18070102155914) {
              if (input[2] <= -0.31854767901734077) {
                  var215 = 0.006899833167616977;
              } else {
                  var215 = 0.029105533571530895;
              }
          } else {
              if (input[2] <= -1.315773426511249) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var215 = -0.0013178848447633418;
                  } else {
                      var215 = 0.02203990775909885;
                  }
              } else {
                  if (input[6] <= -7.033599270855093) {
                      var215 = -0.01685456633321655;
                  } else {
                      var215 = 0.00025460699107118795;
                  }
              }
          }
      }
      var var216;
      if (input[5] > 117.01558275614404) {
          if (input[0] > 64.25004156967033) {
              if (input[6] <= -0.22802093153587424) {
                  var216 = -0.02777218234898309;
              } else {
                  if (input[9] > 11.500000000000002) {
                      var216 = 0.011415046130875885;
                  } else {
                      var216 = -0.0012648417221299418;
                  }
              }
          } else {
              if (input[6] > 2.7021091197227185) {
                  var216 = 0.006731684656410987;
              } else {
                  var216 = 0.02656981795544823;
              }
          }
      } else {
          if (input[5] > 100.90857751286742) {
              if (input[2] <= -0.2707003273254145) {
                  var216 = -0.02245853680278072;
              } else {
                  if (input[0] > 72.4839286421002) {
                      var216 = -0.008086080681684883;
                  } else {
                      var216 = 0.0007274709781889368;
                  }
              }
          } else {
              if (input[0] > 75.9664238348739) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var216 = 0.009651354594153455;
                  } else {
                      var216 = -0.003216016929481253;
                  }
              } else {
                  if (input[0] > 73.55579323924066) {
                      var216 = -0.005982826545252418;
                  } else {
                      var216 = 0.00003159245840637456;
                  }
              }
          }
      }
      var var217;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 6.995147082128496) {
              var217 = -0.014451183663846415;
          } else {
              if (input[4] > 5.244537663167775) {
                  if (input[0] > 53.257588413367706) {
                      var217 = 0.02823991465077586;
                  } else {
                      var217 = 0.000008498291133759642;
                  }
              } else {
                  if (input[4] > 4.982840162738646) {
                      var217 = -0.021025343962116333;
                  } else {
                      var217 = 0.0007353423236913598;
                  }
              }
          }
      } else {
          if (input[4] <= -7.394899536019147) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  var217 = 0.03059595708402392;
              } else {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var217 = 0.026108029995122586;
                  } else {
                      var217 = -0.0076437427445778285;
                  }
              }
          } else {
              if (input[6] <= -2.676633891359932) {
                  if (input[4] > 2.3068085893122094) {
                      var217 = 0.015498994335519973;
                  } else {
                      var217 = -0.002830977549554878;
                  }
              } else {
                  if (input[2] <= -0.3112421825088057) {
                      var217 = 0.004994051179900481;
                  } else {
                      var217 = -0.0005248196008918265;
                  }
              }
          }
      }
      var var218;
      if (input[2] > 1.9623217741205061) {
          var218 = 0.0071446727687649245;
      } else {
          if (input[2] > 1.455433865589791) {
              if (input[13] > 10.500000000000002) {
                  var218 = -0.020815518528039503;
              } else {
                  if (input[13] > 7.500000000000001) {
                      var218 = 0.007768543326048285;
                  } else {
                      var218 = -0.007462412306008793;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var218 = 0.01106007667697855;
              } else {
                  if (input[4] > 8.495194805380047) {
                      var218 = -0.014402519956100755;
                  } else {
                      var218 = 0.00006818667881877498;
                  }
              }
          }
      }
      var var219;
      if (input[6] <= -6.069857858271648) {
          if (input[4] <= -3.9776333795063805) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 10.500000000000002) {
                      var219 = -0.018919448662270178;
                  } else {
                      var219 = 0.004137578064054773;
                  }
              } else {
                  if (input[13] > 10.500000000000002) {
                      var219 = 0.029818934919849573;
                  } else {
                      var219 = 0.0009625871336293133;
                  }
              }
          } else {
              if (input[4] <= -3.038533070624908) {
                  if (input[9] > 3.5000000000000004) {
                      var219 = -0.02110511190676425;
                  } else {
                      var219 = 0.0047557714162165575;
                  }
              } else {
                  if (input[9] > 12.500000000000002) {
                      var219 = -0.011984250834696153;
                  } else {
                      var219 = 0.0008942911721794779;
                  }
              }
          }
      } else {
          if (input[6] <= -5.858846461727939) {
              if (input[9] > 11.500000000000002) {
                  var219 = 0.0245291530083509;
              } else {
                  if (input[5] > 24.465570422759757) {
                      var219 = -0.017753366346055042;
                  } else {
                      var219 = 0.013629370202147016;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[6] <= -5.379413601618121) {
                      var219 = 0.00946066545106821;
                  } else {
                      var219 = -0.009322738560510527;
                  }
              } else {
                  if (input[3] <= -1.1437063176950601) {
                      var219 = 0.008522174980972831;
                  } else {
                      var219 = 0.00005918623882746757;
                  }
              }
          }
      }
      var var220;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[13] > 7.500000000000001) {
                  var220 = 0.022787554915638032;
              } else {
                  var220 = -0.0015991685879211991;
              }
          } else {
              if (input[6] <= -4.3612654214226945) {
                  if (input[10] > 1.5000000000000002) {
                      var220 = 0.0006903618485866208;
                  } else {
                      var220 = 0.01935645259044775;
                  }
              } else {
                  if (input[3] <= -0.3334230236094842) {
                      var220 = -0.006832681044395963;
                  } else {
                      var220 = 0.0018876132073494213;
                  }
              }
          }
      } else {
          if (input[7] <= -1.4999999999999998) {
              if (input[6] <= -8.30864402369986) {
                  var220 = -0.026897584597681212;
              } else {
                  if (input[0] > 13.23529411764625) {
                      var220 = -0.004081356438535786;
                  } else {
                      var220 = 0.022978177123708986;
                  }
              }
          } else {
              if (input[5] <= -3.0440431708916) {
                  if (input[3] > 0.15557235365106767) {
                      var220 = -0.0327602510099073;
                  } else {
                      var220 = -0.0015525101889440438;
                  }
              } else {
                  if (input[5] > 19.544289135213152) {
                      var220 = -0.0003467697451206619;
                  } else {
                      var220 = 0.003372710175223155;
                  }
              }
          }
      }
      var var221;
      if (input[0] > 75.12713279102289) {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[4] <= -1.528269700471031) {
                  if (input[3] > 0.9580914413420627) {
                      var221 = -0.0381199433344155;
                  } else {
                      var221 = 0.002440617466983635;
                  }
              } else {
                  if (input[5] > 102.00605058392648) {
                      var221 = -0.002029085490021523;
                  } else {
                      var221 = 0.014318686939531783;
                  }
              }
          } else {
              if (input[4] <= -1.6392603115067372) {
                  if (input[4] <= -2.8119106560654115) {
                      var221 = -0.0034238432811935244;
                  } else {
                      var221 = 0.05503773524032947;
                  }
              } else {
                  if (input[5] > 73.20719485808327) {
                      var221 = -0.005063098639047814;
                  } else {
                      var221 = -0.026801167873297047;
                  }
              }
          }
      } else {
          if (input[0] > 73.17190257813438) {
              if (input[7] > 1.5000000000000002) {
                  var221 = 0.010332829891893762;
              } else {
                  if (input[2] > 1.297700349078289) {
                      var221 = -0.030887312098014957;
                  } else {
                      var221 = -0.00800148682586209;
                  }
              }
          } else {
              if (input[3] > 1.4918805968895918) {
                  if (input[4] > 3.7952577159510352) {
                      var221 = 0.023345513783489574;
                  } else {
                      var221 = -0.004292617087334526;
                  }
              } else {
                  if (input[2] > 1.455433865589791) {
                      var221 = -0.007181027529434692;
                  } else {
                      var221 = 0.00004577412019523769;
                  }
              }
          }
      }
      var var222;
      if (input[9] > 5.500000000000001) {
          if (input[9] > 7.500000000000001) {
              if (input[7] <= -1.4999999999999998) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var222 = -0.01242875568497035;
                  } else {
                      var222 = 0.001902734534462837;
                  }
              } else {
                  if (input[2] > 0.025809299484776383) {
                      var222 = -0.0006898649410638348;
                  } else {
                      var222 = 0.0012598131681726904;
                  }
              }
          } else {
              if (input[4] > 3.02674812104328) {
                  if (input[2] <= -0.3543047252160269) {
                      var222 = 0.01027250597315977;
                  } else {
                      var222 = -0.013062188633805278;
                  }
              } else {
                  if (input[2] > 0.493948739122735) {
                      var222 = 0.007426918408228377;
                  } else {
                      var222 = -0.0038057886780463873;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[6] <= -8.30864402369986) {
                  var222 = 0.016625698484980127;
              } else {
                  if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                      var222 = -0.013898192524137938;
                  } else {
                      var222 = -0.0008641812215203299;
                  }
              }
          } else {
              if (input[4] > 1.017111697377455) {
                  if (input[6] <= -1.722908858603448) {
                      var222 = -0.017379322326707584;
                  } else {
                      var222 = 0.0015417869894271332;
                  }
              } else {
                  if (input[13] > 3.5000000000000004) {
                      var222 = 0.002217552165091013;
                  } else {
                      var222 = 0.017399189523000045;
                  }
              }
          }
      }
      var var223;
      if (input[4] > 4.912099304131096) {
          if (input[10] > 2.5000000000000004) {
              if (input[13] > 11.500000000000002) {
                  var223 = 0.03192536303228865;
              } else {
                  if (input[5] > 40.15455777421886) {
                      var223 = 0.006617670889859742;
                  } else {
                      var223 = -0.006465667231476806;
                  }
              }
          } else {
              if (input[0] > 52.55175265198409) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var223 = -0.01300345475372271;
                  } else {
                      var223 = 0.000015545784181291636;
                  }
              } else {
                  if (input[0] > 47.22048117114918) {
                      var223 = 0.019678963828957646;
                  } else {
                      var223 = -0.002968491618741218;
                  }
              }
          }
      } else {
          if (input[4] > 3.9460979913492005) {
              if (input[0] > 27.469470602855804) {
                  if (input[3] <= -0.5811484955150211) {
                      var223 = 0.02018042980976862;
                  } else {
                      var223 = -0.003810435489854913;
                  }
              } else {
                  var223 = -0.033771030679462306;
              }
          } else {
              if (input[4] > 3.84136763384246) {
                  if (input[0] > 46.694943750340066) {
                      var223 = 0.026689678476527354;
                  } else {
                      var223 = -0.005992260768611948;
                  }
              } else {
                  if (input[9] > 22.500000000000004) {
                      var223 = 0.003348935777617996;
                  } else {
                      var223 = -0.00018551992663389145;
                  }
              }
          }
      }
      var var224;
      if (input[4] <= -0.7791403766304014) {
          if (input[4] <= -2.1729741642181852) {
              if (input[3] > 0.3968921775675264) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var224 = -0.011664560163520875;
                  } else {
                      var224 = 0.003166653742226388;
                  }
              } else {
                  if (input[6] > 1.9775411669179508) {
                      var224 = 0.024087464833049948;
                  } else {
                      var224 = 0.0010867629893986299;
                  }
              }
          } else {
              if (input[0] > 74.32747876777766) {
                  if (input[10] > 3.5000000000000004) {
                      var224 = -0.004804140788234837;
                  } else {
                      var224 = 0.018550065126135527;
                  }
              } else {
                  if (input[2] <= -1.5107108589838323) {
                      var224 = 0.020123381632417725;
                  } else {
                      var224 = -0.004316990294935721;
                  }
              }
          }
      } else {
          if (input[4] <= -0.45083601189522843) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] > 0.6017056359364609) {
                      var224 = -0.01887850826768117;
                  } else {
                      var224 = 0.017389535076914913;
                  }
              } else {
                  if (input[13] > 2.5000000000000004) {
                      var224 = -0.005796933879046498;
                  } else {
                      var224 = 0.02583525466936873;
                  }
              }
          } else {
              if (input[4] <= -0.11306425342193112) {
                  if (input[9] > 13.500000000000002) {
                      var224 = 0.0011427420234476518;
                  } else {
                      var224 = -0.011676389222850463;
                  }
              } else {
                  var224 = 0.0003995900461622184;
              }
          }
      }
      var var225;
      if (input[6] <= -6.189019565280997) {
          if (input[4] <= -4.21670651579148) {
              if (input[4] <= -8.76737386423564) {
                  var225 = -0.014931569230920885;
              } else {
                  if (input[0] > 48.03337496443599) {
                      var225 = 0.016141554078143872;
                  } else {
                      var225 = 0.00010635552497225857;
                  }
              }
          } else {
              if (input[4] <= -3.527656877820794) {
                  if (input[5] > 10.256312745234089) {
                      var225 = -0.007887368628195036;
                  } else {
                      var225 = -0.03566788030408969;
                  }
              } else {
                  if (input[9] > 15.500000000000002) {
                      var225 = -0.017395608555404795;
                  } else {
                      var225 = -0.0011436196304652382;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[0] > 47.40082564351635) {
                  if (input[3] <= -0.42786091839734014) {
                      var225 = -0.022123816459174207;
                  } else {
                      var225 = -0.0015770421686803612;
                  }
              } else {
                  if (input[3] <= -0.6758514167523011) {
                      var225 = 0.0034904628181071855;
                  } else {
                      var225 = 0.029705317864315905;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[5] > 24.0530548127776) {
                      var225 = -0.013318573523077682;
                  } else {
                      var225 = 0.0005947422830142328;
                  }
              } else {
                  if (input[6] <= -5.555294989730455) {
                      var225 = -0.013674316189015705;
                  } else {
                      var225 = 0.00015193671266242178;
                  }
              }
          }
      }
      var var226;
      if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[3] > 0.5556748350105479) {
              if (input[4] > 0.4908216737328009) {
                  if (input[6] > 5.595339644259805) {
                      var226 = -0.022605334242194144;
                  } else {
                      var226 = -0.050884904214348395;
                  }
              } else {
                  var226 = 0.010094891257247635;
              }
          } else {
              if (input[2] > 0.5324867658975647) {
                  var226 = 0.03468214358196552;
              } else {
                  if (input[13] > 11.500000000000002) {
                      var226 = -0.027812222849980913;
                  } else {
                      var226 = 0.004509834271047258;
                  }
              }
          }
      } else {
          if (input[5] <= -29.59449508597042) {
              if (input[14] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -3.7039309301055208) {
                      var226 = 0.029055597852469573;
                  } else {
                      var226 = 0.007999366789209412;
                  }
              } else {
                  if (input[4] > 0.40537150626608415) {
                      var226 = -0.021484822570447835;
                  } else {
                      var226 = 0.011188113560351086;
                  }
              }
          } else {
              if (input[5] <= -23.24721240218805) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var226 = -0.02951909165451906;
                  } else {
                      var226 = 0.000054957944434084726;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var226 = 0.00378435817687994;
                  } else {
                      var226 = -0.0002525322820711732;
                  }
              }
          }
      }
      var var227;
      if (input[5] > 117.01558275614404) {
          if (input[0] > 64.25004156967033) {
              if (input[6] <= -0.22802093153587424) {
                  var227 = -0.026637542090482386;
              } else {
                  if (input[4] > 2.508196128766592) {
                      var227 = 0.01070919968462629;
                  } else {
                      var227 = -0.001612569815803826;
                  }
              }
          } else {
              if (input[6] > 2.7021091197227185) {
                  var227 = 0.006584968284501522;
              } else {
                  var227 = 0.025034799226596984;
              }
          }
      } else {
          if (input[5] > 100.90857751286742) {
              if (input[2] <= -0.2707003273254145) {
                  var227 = -0.021592003861049938;
              } else {
                  if (input[3] > 0.0059114272457157346) {
                      var227 = -0.0034083783967158417;
                  } else {
                      var227 = 0.016016771829000784;
                  }
              }
          } else {
              if (input[0] > 64.51311365713559) {
                  if (input[5] > 63.14063866439413) {
                      var227 = 0.003019468333919184;
                  } else {
                      var227 = -0.01578225420921316;
                  }
              } else {
                  if (input[5] > 76.56103677039384) {
                      var227 = -0.003523069768599404;
                  } else {
                      var227 = 0.00011326055493401122;
                  }
              }
          }
      }
      var var228;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[4] <= -5.426539082167905) {
              if (input[3] <= -0.9501843948200764) {
                  if (input[5] > 24.465570422759757) {
                      var228 = 0.024883523224090175;
                  } else {
                      var228 = 0.0014180544372326643;
                  }
              } else {
                  if (input[2] <= -0.27885231451531506) {
                      var228 = -0.01630016104391378;
                  } else {
                      var228 = 0.008708080446225694;
                  }
              }
          } else {
              if (input[4] <= -2.0776048705582624) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var228 = 0.009869243043317523;
                  } else {
                      var228 = -0.0031051742151712003;
                  }
              } else {
                  if (input[4] <= -0.03399001277826245) {
                      var228 = -0.00448859836929649;
                  } else {
                      var228 = 0.001932596645198111;
                  }
              }
          }
      } else {
          if (input[0] > 44.161650469112) {
              if (input[5] > 5.6160231700373044) {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var228 = 0.0023850604530032283;
                  } else {
                      var228 = -0.0008455175014341782;
                  }
              } else {
                  var228 = 0.02436626334542181;
              }
          } else {
              if (input[5] > 48.742262254800295) {
                  if (input[5] > 57.46002382311671) {
                      var228 = -0.00046340385652597464;
                  } else {
                      var228 = -0.023818682080198845;
                  }
              } else {
                  if (input[4] > 7.214329904560428) {
                      var228 = 0.023811739497691276;
                  } else {
                      var228 = -0.0011214599758310841;
                  }
              }
          }
      }
      var var229;
      if (input[6] <= -6.069857858271648) {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  var229 = -0.03709446790286727;
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var229 = -0.021924603208512028;
                  } else {
                      var229 = 0.0020098408496422825;
                  }
              }
          } else {
              if (input[4] <= -8.76737386423564) {
                  var229 = -0.017226450543779633;
              } else {
                  if (input[4] <= -6.540481985545479) {
                      var229 = 0.013715300112686396;
                  } else {
                      var229 = -0.0013793778874833045;
                  }
              }
          }
      } else {
          if (input[6] <= -5.858846461727939) {
              if (input[9] > 10.500000000000002) {
                  if (input[0] > 32.903904947513766) {
                      var229 = 0.03678679715121479;
                  } else {
                      var229 = 0.004990450369349371;
                  }
              } else {
                  var229 = -0.0029782459746842097;
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[5] > 24.0530548127776) {
                      var229 = -0.01239149650084418;
                  } else {
                      var229 = 0.0033469463060003314;
                  }
              } else {
                  if (input[3] <= -0.5448595876477775) {
                      var229 = 0.0017613161639725876;
                  } else {
                      var229 = -0.0001584929310057657;
                  }
              }
          }
      }
      var var230;
      if (input[8] <= -1.4999999999999998) {
          var230 = -0.009504601354600392;
      } else {
          if (input[5] <= -34.779391478962644) {
              if (input[14] > 0.000000000000000000000000000000000010000000180025095) {
                  var230 = 0.019075542557447832;
              } else {
                  if (input[4] > 0.36564692169617413) {
                      var230 = -0.017891488686861454;
                  } else {
                      var230 = 0.005105963806035408;
                  }
              }
          } else {
              if (input[5] <= -23.24721240218805) {
                  if (input[3] <= -0.3414643880554218) {
                      var230 = 0.0008290031078522132;
                  } else {
                      var230 = -0.02449867170773036;
                  }
              } else {
                  if (input[30] > 0.000000000000000000000000000000000010000000180025095) {
                      var230 = -0.01075194581509338;
                  } else {
                      var230 = 0.00008592197907760086;
                  }
              }
          }
      }
      var var231;
      if (input[2] <= -1.9123784633518905) {
          var231 = -0.006932756605460841;
      } else {
          if (input[3] <= -1.5218789267492705) {
              if (input[13] > 4.500000000000001) {
                  if (input[10] > 2.5000000000000004) {
                      var231 = -0.01288365444548213;
                  } else {
                      var231 = 0.00989101039176159;
                  }
              } else {
                  var231 = 0.02880990435656089;
              }
          } else {
              if (input[3] <= -1.4056918431732448) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var231 = -0.02378452361361028;
                  } else {
                      var231 = 0.0013085508530101297;
                  }
              } else {
                  if (input[2] <= -1.3479087857871586) {
                      var231 = 0.005091883160007267;
                  } else {
                      var231 = -0.00005433951146031473;
                  }
              }
          }
      }
      var var232;
      if (input[13] > 10.500000000000002) {
          if (input[5] > 91.91928172844878) {
              if (input[0] > 60.05785347067239) {
                  if (input[6] > 2.2593951888407307) {
                      var232 = -0.010511793548584166;
                  } else {
                      var232 = 0.004953547514244007;
                  }
              } else {
                  var232 = -0.02948454285877046;
              }
          } else {
              if (input[5] > 86.97895198216605) {
                  if (input[3] > 0.35661516567757845) {
                      var232 = 0.00735199832153368;
                  } else {
                      var232 = 0.04231173064950368;
                  }
              } else {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var232 = -0.007270995104141463;
                  } else {
                      var232 = 0.00038077117844804797;
                  }
              }
          }
      } else {
          if (input[10] > 3.5000000000000004) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -7.563562985888269) {
                      var232 = 0.031629257858778057;
                  } else {
                      var232 = 0.0033393698808384686;
                  }
              } else {
                  if (input[13] > 8.500000000000002) {
                      var232 = 0.011252864128969383;
                  } else {
                      var232 = -0.0049055650664192865;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] > 1.140378700310803) {
                      var232 = 0.023506169084282817;
                  } else {
                      var232 = -0.002768662247606302;
                  }
              } else {
                  if (input[9] > 21.500000000000004) {
                      var232 = 0.003284571490025728;
                  } else {
                      var232 = -0.0012662635385695602;
                  }
              }
          }
      }
      var var233;
      if (input[6] <= -6.069857858271648) {
          if (input[4] <= -3.9776333795063805) {
              if (input[2] <= -0.37162616348632066) {
                  if (input[6] <= -8.733381044857698) {
                      var233 = -0.0059221842161604945;
                  } else {
                      var233 = 0.0063387267402070895;
                  }
              } else {
                  var233 = -0.014465842629193378;
              }
          } else {
              if (input[4] <= -3.038533070624908) {
                  if (input[9] > 3.5000000000000004) {
                      var233 = -0.01977886353339761;
                  } else {
                      var233 = 0.004335008377878718;
                  }
              } else {
                  if (input[10] > 2.5000000000000004) {
                      var233 = 0.0020382562186973333;
                  } else {
                      var233 = -0.009437747594365576;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[0] > 47.87234042553219) {
                  var233 = -0.00842256107701506;
              } else {
                  if (input[5] > 32.80974921612399) {
                      var233 = 0.028556830659716443;
                  } else {
                      var233 = 0.005858126386786961;
                  }
              }
          } else {
              if (input[3] <= -1.4056918431732448) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var233 = -0.03038577302333094;
                  } else {
                      var233 = 0.008879789826210313;
                  }
              } else {
                  if (input[0] > 13.23529411764625) {
                      var233 = 0.00001563774137910124;
                  } else {
                      var233 = 0.00852992409998861;
                  }
              }
          }
      }
      var var234;
      if (input[13] > 5.500000000000001) {
          if (input[7] > 1.5000000000000002) {
              if (input[0] > 61.12545479965525) {
                  if (input[4] > 3.072780432443182) {
                      var234 = -0.0028819355253135175;
                  } else {
                      var234 = 0.014090172157697195;
                  }
              } else {
                  var234 = -0.016695209621726353;
              }
          } else {
              if (input[5] > 80.00550695293408) {
                  if (input[3] > 0.018446187825035498) {
                      var234 = -0.0055012288990843655;
                  } else {
                      var234 = 0.009134326116494713;
                  }
              } else {
                  if (input[0] > 79.32739770060017) {
                      var234 = 0.014169043732480478;
                  } else {
                      var234 = -0.0000871641876169074;
                  }
              }
          }
      } else {
          if (input[4] > 1.4603064204353786) {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -0.7097727399010926) {
                      var234 = -0.018920921885190053;
                  } else {
                      var234 = -0.0048407116144821545;
                  }
              } else {
                  if (input[4] > 3.4698611223847746) {
                      var234 = 0.004711440994261744;
                  } else {
                      var234 = -0.003196175792242434;
                  }
              }
          } else {
              if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] > 0.5754747040913045) {
                      var234 = 0.02066660683391293;
                  } else {
                      var234 = 0.0035367740795295166;
                  }
              } else {
                  if (input[31] > 0.000000000000000000000000000000000010000000180025095) {
                      var234 = 0.006193047816651143;
                  } else {
                      var234 = -0.0010301830574951966;
                  }
              }
          }
      }
      var var235;
      if (input[4] <= -0.7791403766304014) {
          if (input[4] <= -2.1729741642181852) {
              if (input[4] <= -2.548569004413761) {
                  if (input[10] > 1.5000000000000002) {
                      var235 = -0.0014121304471151849;
                  } else {
                      var235 = 0.0037165873465434896;
                  }
              } else {
                  if (input[6] > 2.1601279316659814) {
                      var235 = 0.025773760858275898;
                  } else {
                      var235 = 0.003704140271150401;
                  }
              }
          } else {
              if (input[2] <= -1.5107108589838323) {
                  var235 = 0.018960384439628043;
              } else {
                  if (input[6] <= -4.4242046780646325) {
                      var235 = -0.011859152500263821;
                  } else {
                      var235 = -0.001714402638785682;
                  }
              }
          }
      } else {
          if (input[4] <= -0.5385430840001747) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] > 0.26742813602864607) {
                      var235 = -0.0030649070668828902;
                  } else {
                      var235 = 0.020033119268430037;
                  }
              } else {
                  if (input[6] <= -1.6725312394562015) {
                      var235 = 0.015088513814677525;
                  } else {
                      var235 = -0.010725326848777104;
                  }
              }
          } else {
              if (input[6] <= -5.117681189325094) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var235 = 0.0017722564599090638;
                  } else {
                      var235 = -0.01934407880991725;
                  }
              } else {
                  if (input[8] > 0.000000000000000000000000000000000010000000180025095) {
                      var235 = 0.007897706117385514;
                  } else {
                      var235 = 0.00007930374948553583;
                  }
              }
          }
      }
      var var236;
      if (input[9] > 5.500000000000001) {
          if (input[9] > 7.500000000000001) {
              if (input[4] > 3.2032943389782225) {
                  if (input[5] > 8.95767471618312) {
                      var236 = 0.0003347550089815523;
                  } else {
                      var236 = 0.014569723052946097;
                  }
              } else {
                  if (input[4] > 2.344350703463393) {
                      var236 = -0.004619980078825953;
                  } else {
                      var236 = 0.00019067943021274753;
                  }
              }
          } else {
              if (input[0] > 57.62589042924083) {
                  if (input[6] <= -3.631949801469407) {
                      var236 = -0.023220564217493023;
                  } else {
                      var236 = 0.004116413535481154;
                  }
              } else {
                  if (input[6] > 5.3416607869209525) {
                      var236 = -0.024490111688236157;
                  } else {
                      var236 = -0.004162772890345472;
                  }
              }
          }
      } else {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[7] <= -1.4999999999999998) {
                  var236 = 0.02085783655961852;
              } else {
                  if (input[5] > 8.95767471618312) {
                      var236 = -0.000948718231099635;
                  } else {
                      var236 = -0.016707089135987625;
                  }
              }
          } else {
              if (input[6] <= -9.297970110269008) {
                  var236 = -0.017814245673033195;
              } else {
                  if (input[4] <= -1.3242311696170128) {
                      var236 = 0.007660388706151256;
                  } else {
                      var236 = 0.0005077459076704908;
                  }
              }
          }
      }
      var var237;
      if (input[4] <= -0.7791403766304014) {
          if (input[5] > 60.98789944376144) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] <= -1.3138899779576914) {
                      var237 = 0.002058503954883976;
                  } else {
                      var237 = -0.010124764650883966;
                  }
              } else {
                  if (input[3] > 0.8543238054389053) {
                      var237 = 0.016390927641814223;
                  } else {
                      var237 = -0.0007410461787892021;
                  }
              }
          } else {
              if (input[5] > 60.200564877650486) {
                  var237 = 0.02845040851597612;
              } else {
                  if (input[6] > 2.653758722583152) {
                      var237 = 0.01880922477827502;
                  } else {
                      var237 = -0.00006644734165035167;
                  }
              }
          }
      } else {
          if (input[4] <= -0.45083601189522843) {
              if (input[3] <= -0.24344553277095524) {
                  if (input[5] > 41.948811368473365) {
                      var237 = -0.02277671215193512;
                  } else {
                      var237 = 0.0005939529180550435;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var237 = 0.027750464928612856;
                  } else {
                      var237 = 0.003512283819130664;
                  }
              }
          } else {
              if (input[6] <= -5.117681189325094) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var237 = 0.0018346788724917518;
                  } else {
                      var237 = -0.01841692096994898;
                  }
              } else {
                  if (input[2] <= -0.6695227882503768) {
                      var237 = 0.004273803097313766;
                  } else {
                      var237 = -0.00014681321703786354;
                  }
              }
          }
      }
      var var238;
      if (input[5] > 117.01558275614404) {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              var238 = 0.020921321191388616;
          } else {
              if (input[9] > 12.500000000000002) {
                  if (input[4] > 1.140378700310803) {
                      var238 = 0.022214807878872783;
                  } else {
                      var238 = -0.0022466918589968007;
                  }
              } else {
                  if (input[3] > 1.0278550228976773) {
                      var238 = 0.018718704010661072;
                  } else {
                      var238 = -0.00454591763249618;
                  }
              }
          }
      } else {
          if (input[5] > 100.90857751286742) {
              if (input[2] <= -0.2707003273254145) {
                  var238 = -0.020861247596667735;
              } else {
                  if (input[0] > 72.4839286421002) {
                      var238 = -0.007321320300420576;
                  } else {
                      var238 = 0.0009544872644103716;
                  }
              }
          } else {
              if (input[0] > 64.51311365713559) {
                  if (input[5] > 63.14063866439413) {
                      var238 = 0.002860599487662052;
                  } else {
                      var238 = -0.01511057682554014;
                  }
              } else {
                  if (input[2] > 0.17583245489799232) {
                      var238 = -0.0019297153332479427;
                  } else {
                      var238 = 0.0004251984450581391;
                  }
              }
          }
      }
      var var239;
      if (input[4] <= -0.03399001277826245) {
          if (input[6] > 1.6843398442544266) {
              if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                  var239 = 0.030456271545117427;
              } else {
                  if (input[2] > 0.03878369967034035) {
                      var239 = -0.00020875767906139818;
                  } else {
                      var239 = 0.028155986237845928;
                  }
              }
          } else {
              if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -1.4153225106941174) {
                      var239 = 0.01485929709904879;
                  } else {
                      var239 = -0.003840843560371611;
                  }
              } else {
                  if (input[8] > 0.000000000000000000000000000000000010000000180025095) {
                      var239 = -0.014732603963566362;
                  } else {
                      var239 = 0.0007940318842069324;
                  }
              }
          }
      } else {
          if (input[6] <= -5.117681189325094) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var239 = 0.006632692831649929;
              } else {
                  if (input[10] > 2.5000000000000004) {
                      var239 = -0.0029050553570755936;
                  } else {
                      var239 = -0.04513635098291701;
                  }
              }
          } else {
              if (input[6] <= -2.620058240574581) {
                  if (input[13] > 1.5000000000000002) {
                      var239 = 0.010412782693442046;
                  } else {
                      var239 = -0.016146871631395575;
                  }
              } else {
                  if (input[6] <= -1.188675504753722) {
                      var239 = -0.006480476887995044;
                  } else {
                      var239 = 0.0007189019513575087;
                  }
              }
          }
      }
      var var240;
      if (input[3] > 0.7461525345222845) {
          if (input[2] > 0.622892131484913) {
              if (input[6] > 1.006432761974532) {
                  if (input[6] > 3.42896965457881) {
                      var240 = 0.0005726024597859125;
                  } else {
                      var240 = -0.008226196375738118;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var240 = -0.00820700510281347;
                  } else {
                      var240 = 0.028231565196270066;
                  }
              }
          } else {
              var240 = -0.02378089805512683;
          }
      } else {
          if (input[3] > 0.7342584171049911) {
              var240 = 0.01756168875119859;
          } else {
              if (input[0] > 67.17230718398928) {
                  if (input[5] > 61.34338824862519) {
                      var240 = 0.0049719549366482076;
                  } else {
                      var240 = -0.028900190303104673;
                  }
              } else {
                  if (input[0] > 65.68848758464974) {
                      var240 = -0.007965147606221018;
                  } else {
                      var240 = -0.00006153326653043755;
                  }
              }
          }
      }
      var var241;
      if (input[53] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[13] > 8.500000000000002) {
              var241 = 0.018407976876858242;
          } else {
              if (input[0] > 54.6459680035938) {
                  var241 = 0.013234454947392152;
              } else {
                  var241 = -0.01207758504427146;
              }
          }
      } else {
          if (input[13] > 5.500000000000001) {
              if (input[4] <= -8.76737386423564) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var241 = -0.03271726776522134;
                  } else {
                      var241 = 0.0006809692995610508;
                  }
              } else {
                  if (input[7] > 1.5000000000000002) {
                      var241 = 0.005707493841922116;
                  } else {
                      var241 = -0.000568770674631036;
                  }
              }
          } else {
              if (input[4] <= -7.712317663256087) {
                  if (input[10] > 3.5000000000000004) {
                      var241 = 0.0372380722825204;
                  } else {
                      var241 = 0.00014384497608026911;
                  }
              } else {
                  if (input[4] <= -3.841704337705677) {
                      var241 = -0.0045126090203235075;
                  } else {
                      var241 = 0.0009286018204984304;
                  }
              }
          }
      }
      var var242;
      if (input[6] > 5.776823337771391) {
          if (input[6] > 6.138234227742873) {
              if (input[3] > 0.2883931799611021) {
                  if (input[3] > 0.5647096098691142) {
                      var242 = -0.0005106355996911179;
                  } else {
                      var242 = 0.011271752163474334;
                  }
              } else {
                  var242 = -0.014429845548409058;
              }
          } else {
              if (input[13] > 2.5000000000000004) {
                  if (input[10] > 3.5000000000000004) {
                      var242 = -0.017165513543639103;
                  } else {
                      var242 = 0.001911509876109796;
                  }
              } else {
                  var242 = -0.020615652055122387;
              }
          }
      } else {
          if (input[6] > 3.8237101336355157) {
              if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 8.500000000000002) {
                      var242 = -0.008043119574724571;
                  } else {
                      var242 = 0.021153544810398134;
                  }
              } else {
                  if (input[4] <= -1.4884140029464057) {
                      var242 = 0.01841126895035987;
                  } else {
                      var242 = -0.0002442620723223289;
                  }
              }
          } else {
              if (input[2] > 1.0828963714962498) {
                  if (input[4] <= -1.8015029132402238) {
                      var242 = 0.009429369759932525;
                  } else {
                      var242 = -0.01969002666200477;
                  }
              } else {
                  if (input[4] > 7.214329904560428) {
                      var242 = 0.011801988837184462;
                  } else {
                      var242 = -0.0000832287616166368;
                  }
              }
          }
      }
      var var243;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[3] <= -0.456609706027228) {
              if (input[3] <= -0.767716948598279) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var243 = 0.006378236112378775;
                  } else {
                      var243 = -0.002500768521176315;
                  }
              } else {
                  if (input[4] <= -6.903177463922957) {
                      var243 = -0.03639755278821071;
                  } else {
                      var243 = -0.004251266114649893;
                  }
              }
          } else {
              if (input[9] > 17.500000000000004) {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var243 = 0.023137717419921065;
                  } else {
                      var243 = 0.004685804053031821;
                  }
              } else {
                  if (input[0] > 39.82089512340189) {
                      var243 = -0.0013669758430952326;
                  } else {
                      var243 = 0.011662552996208286;
                  }
              }
          }
      } else {
          if (input[2] <= -0.2707003273254145) {
              if (input[5] > 83.75558925058311) {
                  var243 = 0.018276423977829134;
              } else {
                  if (input[0] > 56.207921219246124) {
                      var243 = -0.009389339843674065;
                  } else {
                      var243 = 0.0012457456428657614;
                  }
              }
          } else {
              if (input[2] <= -0.2542332324482474) {
                  if (input[2] <= -0.26179501232682617) {
                      var243 = -0.003335105254380727;
                  } else {
                      var243 = -0.03481396264199017;
                  }
              } else {
                  if (input[6] <= -4.096403012396194) {
                      var243 = 0.011019687817844522;
                  } else {
                      var243 = -0.0007527230776566019;
                  }
              }
          }
      }
      var var244;
      if (input[8] <= -1.4999999999999998) {
          var244 = -0.009144662873973208;
      } else {
          if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 9.500000000000002) {
                      var244 = 0.008427382221488009;
                  } else {
                      var244 = -0.016270823607649525;
                  }
              } else {
                  if (input[13] > 2.5000000000000004) {
                      var244 = 0.0037760577612484594;
                  } else {
                      var244 = 0.03501938414991189;
                  }
              }
          } else {
              if (input[4] <= -0.03399001277826245) {
                  if (input[4] <= -0.19071640176439533) {
                      var244 = -0.0003674511856744586;
                  } else {
                      var244 = -0.008231501185638139;
                  }
              } else {
                  if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                      var244 = -0.010194048246655646;
                  } else {
                      var244 = 0.0006177799923853099;
                  }
              }
          }
      }
      var var245;
      if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[3] > 0.5556748350105479) {
              if (input[4] > 0.4908216737328009) {
                  if (input[6] > 5.595339644259805) {
                      var245 = -0.02158541394431502;
                  } else {
                      var245 = -0.04946226073431934;
                  }
              } else {
                  var245 = 0.008288234799754572;
              }
          } else {
              if (input[2] > 0.592086122059724) {
                  var245 = 0.04237958413592302;
              } else {
                  if (input[13] > 11.500000000000002) {
                      var245 = -0.026793890199349225;
                  } else {
                      var245 = 0.004569268882910407;
                  }
              }
          }
      } else {
          if (input[5] <= -29.59449508597042) {
              if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                  var245 = 0.02114154437817682;
              } else {
                  if (input[2] <= -0.27885231451531506) {
                      var245 = 0.009393230610162104;
                  } else {
                      var245 = -0.01721383000292516;
                  }
              }
          } else {
              if (input[5] <= -23.24721240218805) {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var245 = -0.02802258851173823;
                  } else {
                      var245 = 0.00037550162085901414;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var245 = 0.003450520160965533;
                  } else {
                      var245 = -0.00023663985215348476;
                  }
              }
          }
      }
      var var246;
      if (input[2] <= -1.9123784633518905) {
          var246 = -0.006666145885975684;
      } else {
          if (input[3] <= -1.5218789267492705) {
              if (input[13] > 4.500000000000001) {
                  if (input[10] > 2.5000000000000004) {
                      var246 = -0.012519723170528248;
                  } else {
                      var246 = 0.009687562521618424;
                  }
              } else {
                  var246 = 0.027258191926382697;
              }
          } else {
              if (input[3] <= -1.4056918431732448) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var246 = -0.022777963589969506;
                  } else {
                      var246 = 0.0013044560459135567;
                  }
              } else {
                  if (input[2] <= -1.3479087857871586) {
                      var246 = 0.004559479936993659;
                  } else {
                      var246 = -0.00004793462887805127;
                  }
              }
          }
      }
      var var247;
      if (input[5] > 92.60076342411848) {
          if (input[4] <= -5.642770726091707) {
              if (input[6] <= -1.188675504753722) {
                  var247 = -0.023707271762862404;
              } else {
                  var247 = -0.007059277019665373;
              }
          } else {
              if (input[13] > 11.500000000000002) {
                  if (input[3] > 0.3725720045298903) {
                      var247 = 0.0003377239559084611;
                  } else {
                      var247 = -0.03592550960733886;
                  }
              } else {
                  if (input[3] > 0.7126275434117413) {
                      var247 = -0.00439904214369033;
                  } else {
                      var247 = 0.003028482725770318;
                  }
              }
          }
      } else {
          if (input[5] > 84.17141564970066) {
              if (input[2] <= -0.36304404649009814) {
                  var247 = 0.028579274719121917;
              } else {
                  if (input[4] <= -3.841704337705677) {
                      var247 = -0.013225753854217738;
                  } else {
                      var247 = 0.003626045105847041;
                  }
              }
          } else {
              if (input[5] > 80.00550695293408) {
                  if (input[0] > 66.44755628362729) {
                      var247 = 0.0038933571600359655;
                  } else {
                      var247 = -0.011873155306669717;
                  }
              } else {
                  if (input[4] > 9.401150856775486) {
                      var247 = 0.017077781300679818;
                  } else {
                      var247 = 0.00007090968035780656;
                  }
              }
          }
      }
      var var248;
      if (input[6] <= -6.189019565280997) {
          if (input[4] <= -4.21670651579148) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var248 = -0.013669119161728624;
                  } else {
                      var248 = 0.0076064172061154865;
                  }
              } else {
                  if (input[13] > 10.500000000000002) {
                      var248 = 0.029043221985045088;
                  } else {
                      var248 = 0.002191748001434207;
                  }
              }
          } else {
              if (input[4] <= -3.527656877820794) {
                  if (input[2] <= -1.3815464400185) {
                      var248 = -0.0010363506679610733;
                  } else {
                      var248 = -0.0269785417225107;
                  }
              } else {
                  if (input[9] > 15.500000000000002) {
                      var248 = -0.01627146991031787;
                  } else {
                      var248 = -0.0008269696510890845;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[0] > 47.40082564351635) {
                  var248 = -0.010379810206556761;
              } else {
                  if (input[3] <= -0.6758514167523011) {
                      var248 = 0.0029412242692852955;
                  } else {
                      var248 = 0.02732289235242363;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var248 = -0.011117977893666177;
                  } else {
                      var248 = 0.002574749741744023;
                  }
              } else {
                  if (input[6] <= -5.555294989730455) {
                      var248 = -0.012747568767279558;
                  } else {
                      var248 = 0.00013907498796935313;
                  }
              }
          }
      }
      var var249;
      if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[8] > 0.000000000000000000000000000000000010000000180025095) {
              var249 = -0.01825476128203261;
          } else {
              if (input[20] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[7] > 0.000000000000000000000000000000000010000000180025095) {
                      var249 = -0.008150820739714456;
                  } else {
                      var249 = 0.015075027370099487;
                  }
              } else {
                  if (input[6] <= -6.189019565280997) {
                      var249 = -0.012789383984482287;
                  } else {
                      var249 = -0.0007911942915147072;
                  }
              }
          }
      } else {
          if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 2.5000000000000004) {
                      var249 = -0.0032472036332576886;
                  } else {
                      var249 = 0.012525469503991719;
                  }
              } else {
                  if (input[13] > 1.5000000000000002) {
                      var249 = 0.00536486846204891;
                  } else {
                      var249 = -0.01562941156254767;
                  }
              }
          } else {
              if (input[0] > 44.50111137696333) {
                  if (input[6] <= -8.025489093009648) {
                      var249 = 0.0314595221250403;
                  } else {
                      var249 = 0.0004343886728878001;
                  }
              } else {
                  if (input[0] > 39.82089512340189) {
                      var249 = -0.008863435244703175;
                  } else {
                      var249 = -0.00028527580309439305;
                  }
              }
          }
      }
      var var250;
      if (input[5] > 27.141286553166832) {
          if (input[0] > 26.383030344586114) {
              if (input[0] > 27.865205959973) {
                  if (input[6] <= -2.398066420549097) {
                      var250 = -0.002460434158818284;
                  } else {
                      var250 = 0.000250685694468737;
                  }
              } else {
                  var250 = 0.016168440888522585;
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 30.755186602054312) {
                      var250 = -0.03324374471419133;
                  } else {
                      var250 = -0.015243225870217742;
                  }
              } else {
                  var250 = 0.003110182130149381;
              }
          }
      } else {
          if (input[4] > 0.9187848953214247) {
              if (input[10] > 1.5000000000000002) {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var250 = -0.012404811644945462;
                  } else {
                      var250 = -0.0018288325653137158;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var250 = -0.00796478925893408;
                  } else {
                      var250 = 0.01741550758015148;
                  }
              }
          } else {
              if (input[0] > 48.47580151432786) {
                  if (input[2] <= -0.17292263602242408) {
                      var250 = -0.00442710052498281;
                  } else {
                      var250 = 0.04987605770992409;
                  }
              } else {
                  if (input[4] <= -0.03399001277826245) {
                      var250 = 0.00048449556162362444;
                  } else {
                      var250 = 0.008325860938978908;
                  }
              }
          }
      }
      var var251;
      if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 6.995147082128496) {
              var251 = -0.014313033494708347;
          } else {
              if (input[4] > 5.244537663167775) {
                  if (input[5] > 35.25256113656712) {
                      var251 = 0.018967243697074414;
                  } else {
                      var251 = -0.01069348389616795;
                  }
              } else {
                  if (input[4] > 4.982840162738646) {
                      var251 = -0.020570234475811074;
                  } else {
                      var251 = 0.000701181051778517;
                  }
              }
          }
      } else {
          if (input[2] <= -0.2707003273254145) {
              if (input[5] > 83.75558925058311) {
                  if (input[10] > 2.5000000000000004) {
                      var251 = 0.028132759853761888;
                  } else {
                      var251 = -0.0006260556502130174;
                  }
              } else {
                  if (input[6] <= -0.831454568954585) {
                      var251 = -0.0006377267153221281;
                  } else {
                      var251 = 0.006830606625377592;
                  }
              }
          } else {
              if (input[2] <= -0.18032876532877087) {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var251 = -0.013959471187886048;
                  } else {
                      var251 = -0.0026183410942670006;
                  }
              } else {
                  if (input[6] <= -4.032321514980188) {
                      var251 = 0.010414263830480826;
                  } else {
                      var251 = -0.00046666830344524067;
                  }
              }
          }
      }
      var var252;
      if (input[5] > 92.60076342411848) {
          if (input[6] <= -2.4472201593862972) {
              if (input[3] > 0.06654748911058106) {
                  var252 = -0.03157346900623156;
              } else {
                  var252 = -0.00004129719887817642;
              }
          } else {
              if (input[3] > 0.7126275434117413) {
                  if (input[6] > 1.2737941618992539) {
                      var252 = -0.004696002604553561;
                  } else {
                      var252 = 0.0172286556320184;
                  }
              } else {
                  if (input[13] > 11.500000000000002) {
                      var252 = -0.012738136422754629;
                  } else {
                      var252 = 0.0026917657080539796;
                  }
              }
          }
      } else {
          if (input[5] > 88.64965447194571) {
              if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 90.21846040958793) {
                      var252 = 0.00541403498734476;
                  } else {
                      var252 = 0.03643701907150076;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var252 = -0.011852116730012277;
                  } else {
                      var252 = 0.004528803947507747;
                  }
              }
          } else {
              if (input[6] > 10.31060103068119) {
                  var252 = 0.013641827609390506;
              } else {
                  if (input[2] > 1.4199031747969257) {
                      var252 = -0.005748266822298821;
                  } else {
                      var252 = 0.00008278950488954584;
                  }
              }
          }
      }
      var var253;
      if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[6] > 1.2737941618992539) {
              if (input[6] > 2.2112875900632827) {
                  if (input[10] > 1.5000000000000002) {
                      var253 = 0.0025067040712168087;
                  } else {
                      var253 = -0.012212751832145544;
                  }
              } else {
                  if (input[4] <= -0.9700141432400967) {
                      var253 = 0.007143735614369164;
                  } else {
                      var253 = -0.023375441482918376;
                  }
              }
          } else {
              if (input[9] > 21.500000000000004) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var253 = -0.0033031422944488084;
                  } else {
                      var253 = 0.03581930922647764;
                  }
              } else {
                  if (input[6] <= -1.8783643679700581) {
                      var253 = -0.004500657692844977;
                  } else {
                      var253 = 0.004659139650353953;
                  }
              }
          }
      } else {
          if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 2.5000000000000004) {
                      var253 = -0.0030783523586254587;
                  } else {
                      var253 = 0.011859393021231006;
                  }
              } else {
                  if (input[13] > 1.5000000000000002) {
                      var253 = 0.005071484314940427;
                  } else {
                      var253 = -0.014907712942138504;
                  }
              }
          } else {
              if (input[21] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
                      var253 = 0.03586998429815906;
                  } else {
                      var253 = 0.0008349114113037171;
                  }
              } else {
                  var253 = -0.0005779727122727274;
              }
          }
      }
      var var254;
      if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[4] > 0.9715869529760879) {
              if (input[10] > 3.5000000000000004) {
                  if (input[2] > 0.6017056359364609) {
                      var254 = 0.00046875461913240034;
                  } else {
                      var254 = 0.016773152995144588;
                  }
              } else {
                  if (input[4] > 1.2547559421013676) {
                      var254 = -0.0016085808063366327;
                  } else {
                      var254 = 0.02117464139029053;
                  }
              }
          } else {
              if (input[4] <= -0.4950921444997715) {
                  if (input[4] <= -1.0376436871914176) {
                      var254 = 0.00047067944134903273;
                  } else {
                      var254 = 0.01541046533560771;
                  }
              } else {
                  if (input[2] > 1.0016590802373793) {
                      var254 = 0.01125598374093012;
                  } else {
                      var254 = -0.011422657473718031;
                  }
              }
          }
      } else {
          if (input[2] <= -1.5649334836593047) {
              if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                  var254 = 0.009118848720703284;
              } else {
                  if (input[6] <= -7.2121924536177024) {
                      var254 = -0.020525955485901335;
                  } else {
                      var254 = 0.004026467953028946;
                  }
              }
          } else {
              if (input[2] <= -1.5107108589838323) {
                  var254 = 0.013808160606196232;
              } else {
                  if (input[6] <= -4.495641208044259) {
                      var254 = -0.001735525813299204;
                  } else {
                      var254 = 0.00009169236555892581;
                  }
              }
          }
      }
      var var255;
      if (input[5] > 19.544289135213152) {
          if (input[3] <= -1.3231254954991536) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 25.034626636612057) {
                      var255 = -0.009697923393604625;
                  } else {
                      var255 = -0.041038187204799924;
                  }
              } else {
                  var255 = 0.013150450174834093;
              }
          } else {
              if (input[2] <= -1.315773426511249) {
                  if (input[0] > 53.257588413367706) {
                      var255 = -0.013166802408745681;
                  } else {
                      var255 = 0.01476056199198933;
                  }
              } else {
                  if (input[6] <= -8.30864402369986) {
                      var255 = 0.018725799850223674;
                  } else {
                      var255 = -0.000302436860242598;
                  }
              }
          }
      } else {
          if (input[6] > 3.957449210482031) {
              if (input[13] > 4.500000000000001) {
                  if (input[2] > 0.5825270184100372) {
                      var255 = -0.014353997342070633;
                  } else {
                      var255 = 0.011940672238588074;
                  }
              } else {
                  var255 = 0.04399116537420811;
              }
          } else {
              if (input[4] > 4.452431186048718) {
                  if (input[2] > 0.21519627192871363) {
                      var255 = -0.04119591204553857;
                  } else {
                      var255 = -0.0036538321562004763;
                  }
              } else {
                  if (input[0] > 48.47580151432786) {
                      var255 = 0.025182290951255973;
                  } else {
                      var255 = 0.0007872130816668579;
                  }
              }
          }
      }
      var var256;
      if (input[8] <= -1.4999999999999998) {
          var256 = -0.008742022164258003;
      } else {
          if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[31] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[9] > 10.500000000000002) {
                      var256 = -0.022479173986255357;
                  } else {
                      var256 = 0.0019195547575221374;
                  }
              } else {
                  if (input[6] <= -0.9700695059864084) {
                      var256 = 0.013826873803204603;
                  } else {
                      var256 = -0.0012667203470131234;
                  }
              }
          } else {
              if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 11.500000000000002) {
                      var256 = -0.010546575523123703;
                  } else {
                      var256 = -0.0003870055315545575;
                  }
              } else {
                  if (input[20] > 0.000000000000000000000000000000000010000000180025095) {
                      var256 = -0.001698227228098323;
                  } else {
                      var256 = 0.0005580589046054174;
                  }
              }
          }
      }
      var var257;
      if (input[2] > 1.9623217741205061) {
          var257 = 0.006335929652484829;
      } else {
          if (input[2] > 1.455433865589791) {
              if (input[13] > 10.500000000000002) {
                  var257 = -0.019968599981356285;
              } else {
                  if (input[13] > 7.500000000000001) {
                      var257 = 0.0075524601558666395;
                  } else {
                      var257 = -0.006930014979633996;
                  }
              }
          } else {
              if (input[4] > 9.401150856775486) {
                  var257 = 0.00945083072961034;
              } else {
                  if (input[4] > 6.995147082128496) {
                      var257 = -0.006006861386901314;
                  } else {
                      var257 = 0.00012708729793322804;
                  }
              }
          }
      }
      var var258;
      if (input[4] > 4.912099304131096) {
          if (input[10] > 2.5000000000000004) {
              if (input[13] > 11.500000000000002) {
                  var258 = 0.030276691987106825;
              } else {
                  if (input[5] > 40.15455777421886) {
                      var258 = 0.00622151737339394;
                  } else {
                      var258 = -0.006177755585604561;
                  }
              }
          } else {
              if (input[0] > 52.55175265198409) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var258 = -0.0124719494057891;
                  } else {
                      var258 = 0.00002774390773028661;
                  }
              } else {
                  if (input[0] > 47.22048117114918) {
                      var258 = 0.01832426735840651;
                  } else {
                      var258 = -0.0031964111106190084;
                  }
              }
          }
      } else {
          if (input[4] > 3.9460979913492005) {
              if (input[0] > 27.469470602855804) {
                  if (input[3] <= -0.5811484955150211) {
                      var258 = 0.018686343621893;
                  } else {
                      var258 = -0.003693907988468463;
                  }
              } else {
                  var258 = -0.032725324306889535;
              }
          } else {
              if (input[4] > 3.84136763384246) {
                  if (input[0] > 46.694943750340066) {
                      var258 = 0.02497347827527265;
                  } else {
                      var258 = -0.005674491889853618;
                  }
              } else {
                  if (input[3] > 0.5298948855459753) {
                      var258 = -0.00140953765766994;
                  } else {
                      var258 = 0.00033319693680013943;
                  }
              }
          }
      }
      var var259;
      if (input[9] > 5.500000000000001) {
          if (input[9] > 7.500000000000001) {
              if (input[7] <= -1.4999999999999998) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var259 = -0.0119282540305738;
                  } else {
                      var259 = 0.001844905735279473;
                  }
              } else {
                  if (input[2] > 0.025809299484776383) {
                      var259 = -0.0006542042752809032;
                  } else {
                      var259 = 0.0011894569700630026;
                  }
              }
          } else {
              if (input[5] <= -18.17767320837807) {
                  var259 = -0.023073021587740807;
              } else {
                  if (input[0] > 29.926259701776768) {
                      var259 = -0.003976452778414388;
                  } else {
                      var259 = 0.010224494352832006;
                  }
              }
          }
      } else {
          if (input[13] > 5.500000000000001) {
              if (input[5] > 95.31025809183609) {
                  if (input[2] > 0.7084136072199805) {
                      var259 = -0.020687755738804343;
                  } else {
                      var259 = -0.0036494690742295416;
                  }
              } else {
                  if (input[49] > 0.000000000000000000000000000000000010000000180025095) {
                      var259 = 0.007953858165114928;
                  } else {
                      var259 = -0.000918299851300288;
                  }
              }
          } else {
              if (input[5] <= -11.42528703884175) {
                  var259 = 0.02460693024404733;
              } else {
                  if (input[5] > 99.13565472513949) {
                      var259 = 0.014657930483497748;
                  } else {
                      var259 = 0.0012869740817140491;
                  }
              }
          }
      }
      var var260;
      if (input[0] > 75.12713279102289) {
          if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[4] <= -1.528269700471031) {
                  if (input[3] > 0.9580914413420627) {
                      var260 = -0.036272150341185805;
                  } else {
                      var260 = 0.0026038192988842683;
                  }
              } else {
                  if (input[5] > 72.81783983553326) {
                      var260 = 0.006086861260087667;
                  } else {
                      var260 = 0.03529764077602915;
                  }
              }
          } else {
              if (input[4] <= -1.6392603115067372) {
                  if (input[4] <= -2.8119106560654115) {
                      var260 = -0.004427948685462031;
                  } else {
                      var260 = 0.04908341755605176;
                  }
              } else {
                  if (input[5] > 73.20719485808327) {
                      var260 = -0.004820396105077051;
                  } else {
                      var260 = -0.02592391010216724;
                  }
              }
          }
      } else {
          if (input[0] > 73.17190257813438) {
              if (input[7] > 1.5000000000000002) {
                  var260 = 0.009919698629897993;
              } else {
                  if (input[2] > 1.297700349078289) {
                      var260 = -0.029649886525462438;
                  } else {
                      var260 = -0.0075413292204770084;
                  }
              }
          } else {
              if (input[3] > 1.4918805968895918) {
                  if (input[4] > 3.7952577159510352) {
                      var260 = 0.021973304148051414;
                  } else {
                      var260 = -0.004151281726217789;
                  }
              } else {
                  if (input[2] > 1.455433865589791) {
                      var260 = -0.006413353594699658;
                  } else {
                      var260 = 0.000041477297558380004;
                  }
              }
          }
      }
      var var261;
      if (input[4] <= -0.03399001277826245) {
          if (input[6] > 1.6843398442544266) {
              if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                  var261 = 0.028011005916624445;
              } else {
                  if (input[2] > 0.03878369967034035) {
                      var261 = -0.00005030810008265665;
                  } else {
                      var261 = 0.02650300802330238;
                  }
              }
          } else {
              if (input[6] > 1.5037883131853527) {
                  if (input[4] <= -1.608899516503428) {
                      var261 = -0.005883150585874696;
                  } else {
                      var261 = -0.028305728535252372;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var261 = -0.002891701065553085;
                  } else {
                      var261 = 0.0006750542486429607;
                  }
              }
          }
      } else {
          if (input[6] <= -5.117681189325094) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  var261 = 0.006554683917376604;
              } else {
                  if (input[10] > 2.5000000000000004) {
                      var261 = -0.0028205998802037524;
                  } else {
                      var261 = -0.04394562786827382;
                  }
              }
          } else {
              if (input[6] <= -2.620058240574581) {
                  if (input[13] > 1.5000000000000002) {
                      var261 = 0.009865420086881795;
                  } else {
                      var261 = -0.015367528534273403;
                  }
              } else {
                  if (input[6] <= -1.188675504753722) {
                      var261 = -0.006293235424866182;
                  } else {
                      var261 = 0.0006856074652190229;
                  }
              }
          }
      }
      var var262;
      if (input[4] <= -2.1729741642181852) {
          if (input[3] > 0.3968921775675264) {
              if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                  var262 = 0.016542416815491776;
              } else {
                  if (input[0] > 46.53394954622157) {
                      var262 = -0.008073422691789463;
                  } else {
                      var262 = 0.021336004769669195;
                  }
              }
          } else {
              if (input[6] > 1.9775411669179508) {
                  if (input[9] > 10.500000000000002) {
                      var262 = 0.04252906789771931;
                  } else {
                      var262 = 0.00021898721541629927;
                  }
              } else {
                  if (input[6] > 1.5037883131853527) {
                      var262 = -0.022738633655806438;
                  } else {
                      var262 = 0.0013160678916686447;
                  }
              }
          }
      } else {
          if (input[6] <= -4.4242046780646325) {
              if (input[9] > 11.500000000000002) {
                  if (input[6] <= -5.465664259209454) {
                      var262 = 0.0007970935645521529;
                  } else {
                      var262 = -0.02122415022257448;
                  }
              } else {
                  if (input[13] > 10.500000000000002) {
                      var262 = 0.020794136946579403;
                  } else {
                      var262 = -0.002489737785592248;
                  }
              }
          } else {
              if (input[4] <= -1.8768784815380142) {
                  if (input[0] > 31.776869407021277) {
                      var262 = -0.011640440510564573;
                  } else {
                      var262 = 0.02683267486520416;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var262 = 0.004818898566522795;
                  } else {
                      var262 = 0.000019001328159138487;
                  }
              }
          }
      }
      var var263;
      if (input[0] > 66.95627012882493) {
          if (input[5] > 62.70267242553313) {
              if (input[0] > 69.60929903160356) {
                  if (input[13] > 1.5000000000000002) {
                      var263 = -0.0011865745144919299;
                  } else {
                      var263 = 0.010827283120788653;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var263 = 0.023367645973630696;
                  } else {
                      var263 = 0.004002983454912208;
                  }
              }
          } else {
              if (input[4] <= -0.42293878459745915) {
                  var263 = -0.009300309466964212;
              } else {
                  var263 = -0.03837940293143233;
              }
          }
      } else {
          if (input[0] > 65.68848758464974) {
              if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var263 = -0.00412863749433625;
                  } else {
                      var263 = -0.033894307469155525;
                  }
              } else {
                  if (input[5] > 96.8012803256159) {
                      var263 = -0.011826727866342247;
                  } else {
                      var263 = 0.003940208879218113;
                  }
              }
          } else {
              if (input[0] > 64.51311365713559) {
                  if (input[4] > 0.5334815324478203) {
                      var263 = 0.014200893202488008;
                  } else {
                      var263 = -0.003154169693435604;
                  }
              } else {
                  if (input[2] > 0.025809299484776383) {
                      var263 = -0.0013688879946163685;
                  } else {
                      var263 = 0.000529255774588645;
                  }
              }
          }
      }
      var var264;
      if (input[6] <= -6.069857858271648) {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  var264 = -0.034916992718857356;
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var264 = -0.020812161796689908;
                  } else {
                      var264 = 0.0029115635197616762;
                  }
              }
          } else {
              if (input[4] <= -8.76737386423564) {
                  var264 = -0.016745875530414935;
              } else {
                  if (input[4] <= -7.123374703856836) {
                      var264 = 0.016355255492615916;
                  } else {
                      var264 = -0.0007929127136386892;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[0] > 47.87234042553219) {
                  var264 = -0.007154114767074342;
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var264 = 0.01844582249035215;
                  } else {
                      var264 = 0.001442900928913634;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[6] <= -5.379413601618121) {
                      var264 = 0.00989717296771465;
                  } else {
                      var264 = -0.008313616637749485;
                  }
              } else {
                  if (input[3] <= -1.1437063176950601) {
                      var264 = 0.009014146192401217;
                  } else {
                      var264 = 0.00003785250090517997;
                  }
              }
          }
      }
      var var265;
      if (input[4] > 4.912099304131096) {
          if (input[10] > 2.5000000000000004) {
              if (input[13] > 11.500000000000002) {
                  var265 = 0.0285688710089933;
              } else {
                  if (input[5] > 40.15455777421886) {
                      var265 = 0.0058967132734847995;
                  } else {
                      var265 = -0.005888467454553511;
                  }
              }
          } else {
              if (input[0] > 52.55175265198409) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var265 = -0.01195027606042312;
                  } else {
                      var265 = 0.00003794491383647851;
                  }
              } else {
                  if (input[4] > 6.789481691669448) {
                      var265 = 0.01746381135620275;
                  } else {
                      var265 = -0.0036386826435972383;
                  }
              }
          }
      } else {
          if (input[4] > 3.9460979913492005) {
              if (input[0] > 27.469470602855804) {
                  if (input[9] > 20.500000000000004) {
                      var265 = -0.01370688277284101;
                  } else {
                      var265 = -0.0005579579879980973;
                  }
              } else {
                  var265 = -0.03161439340406736;
              }
          } else {
              if (input[4] > 3.747559616936297) {
                  if (input[9] > 6.500000000000001) {
                      var265 = 0.01482876403873926;
                  } else {
                      var265 = -0.011043262805765099;
                  }
              } else {
                  if (input[4] > 3.655683130085723) {
                      var265 = -0.008319278750665467;
                  } else {
                      var265 = 0.00002181767273639247;
                  }
              }
          }
      }
      var var266;
      if (input[9] > 18.500000000000004) {
          if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[5] > 96.12555884548514) {
                  if (input[13] > 5.500000000000001) {
                      var266 = 0.028076796452506537;
                  } else {
                      var266 = 0.002147796342632046;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var266 = 0.00998091047638909;
                  } else {
                      var266 = -0.0008474676629931159;
                  }
              }
          } else {
              if (input[4] > 4.047127624433007) {
                  if (input[6] > 3.8237101336355157) {
                      var266 = 0.00412146178619032;
                  } else {
                      var266 = -0.029207730596191712;
                  }
              } else {
                  if (input[2] > 1.103118178873732) {
                      var266 = -0.014349227032472382;
                  } else {
                      var266 = 0.0008971078919153282;
                  }
              }
          }
      } else {
          if (input[9] > 14.500000000000002) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 6.624365110353307) {
                      var266 = -0.030192008810098144;
                  } else {
                      var266 = 0.0011345372273552756;
                  }
              } else {
                  if (input[3] <= -0.4375447475940651) {
                      var266 = 0.005032065497240664;
                  } else {
                      var266 = -0.0078056403720816805;
                  }
              }
          } else {
              if (input[5] > 72.02917243495783) {
                  var266 = -0.0011922168614573274;
              } else {
                  if (input[6] > 7.999681113877577) {
                      var266 = 0.014882539489619368;
                  } else {
                      var266 = 0.0006550639920675734;
                  }
              }
          }
      }
      var var267;
      if (input[0] > 75.12713279102289) {
          if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[5] > 100.0020948535427) {
                  if (input[6] > 4.520603407956561) {
                      var267 = -0.010630230653921822;
                  } else {
                      var267 = 0.007005925771345706;
                  }
              } else {
                  var267 = 0.026220294015922033;
              }
          } else {
              if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] > 0.40537150626608415) {
                      var267 = -0.00457387071879384;
                  } else {
                      var267 = 0.022483026606717957;
                  }
              } else {
                  if (input[4] <= -3.3236286389454217) {
                      var267 = -0.013737480247328024;
                  } else {
                      var267 = 0.0002965594385000779;
                  }
              }
          }
      } else {
          if (input[0] > 73.17190257813438) {
              if (input[7] > 1.5000000000000002) {
                  var267 = 0.009416595385710583;
              } else {
                  if (input[6] > 5.86282993048025) {
                      var267 = -0.02350898244270576;
                  } else {
                      var267 = -0.006024442061591917;
                  }
              }
          } else {
              if (input[3] > 1.4918805968895918) {
                  if (input[4] > 3.7952577159510352) {
                      var267 = 0.020331352459819502;
                  } else {
                      var267 = -0.004063570215745083;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var267 = -0.0014176676479803073;
                  } else {
                      var267 = 0.0002591278713134747;
                  }
              }
          }
      }
      var var268;
      if (input[0] > 66.95627012882493) {
          if (input[5] > 62.70267242553313) {
              if (input[0] > 69.60929903160356) {
                  if (input[13] > 1.5000000000000002) {
                      var268 = -0.0010713460595292042;
                  } else {
                      var268 = 0.010348096180540634;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var268 = 0.02197774580492108;
                  } else {
                      var268 = 0.003819436721728256;
                  }
              }
          } else {
              if (input[4] <= -0.42293878459745915) {
                  var268 = -0.008848281454598364;
              } else {
                  var268 = -0.037026965582960814;
              }
          }
      } else {
          if (input[0] > 65.68848758464974) {
              if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[12] > 0.000000000000000000000000000000000010000000180025095) {
                      var268 = -0.0039409830832687655;
                  } else {
                      var268 = -0.03259746392393425;
                  }
              } else {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var268 = -0.008958789194792776;
                  } else {
                      var268 = 0.005202427270342338;
                  }
              }
          } else {
              if (input[0] > 64.51311365713559) {
                  if (input[4] > 0.5334815324478203) {
                      var268 = 0.013413002908723888;
                  } else {
                      var268 = -0.002971929793718594;
                  }
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var268 = -0.001636237422607902;
                  } else {
                      var268 = 0.00038010728862172155;
                  }
              }
          }
      }
      var var269;
      if (input[4] > 6.995147082128496) {
          if (input[0] > 37.06590588035515) {
              if (input[9] > 4.500000000000001) {
                  if (input[9] > 17.500000000000004) {
                      var269 = 0.004467074649601162;
                  } else {
                      var269 = -0.02073600387355169;
                  }
              } else {
                  if (input[0] > 51.60793357988327) {
                      var269 = 0.011463990650791829;
                  } else {
                      var269 = -0.015355388169871732;
                  }
              }
          } else {
              var269 = 0.021576207081924825;
          }
      } else {
          if (input[4] > 6.789481691669448) {
              var269 = 0.017568232243104356;
          } else {
              if (input[4] > 6.609695324748413) {
                  var269 = -0.011953989532078478;
              } else {
                  if (input[4] > 5.42653906653272) {
                      var269 = 0.0033551075947149747;
                  } else {
                      var269 = -0.00008863683133033898;
                  }
              }
          }
      }
      var var270;
      if (input[6] > 5.776823337771391) {
          if (input[6] > 5.946845407759343) {
              if (input[9] > 19.500000000000004) {
                  if (input[3] > 1.0278550228976773) {
                      var270 = -0.004253150256213283;
                  } else {
                      var270 = 0.015313473114418939;
                  }
              } else {
                  if (input[2] > 0.47564715492317694) {
                      var270 = -0.0008095019058430985;
                  } else {
                      var270 = -0.016116881264903616;
                  }
              }
          } else {
              if (input[3] > 0.7004948800207346) {
                  if (input[10] > 2.5000000000000004) {
                      var270 = -0.005961254447439499;
                  } else {
                      var270 = 0.009218939976233787;
                  }
              } else {
                  var270 = -0.032176308955535346;
              }
          }
      } else {
          if (input[6] > 3.8237101336355157) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 67.94692510472329) {
                      var270 = 0.01752812854889686;
                  } else {
                      var270 = -0.001860016501906145;
                  }
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var270 = -0.01532866128932389;
                  } else {
                      var270 = 0.003336642132296888;
                  }
              }
          } else {
              if (input[3] > 0.8251442856487058) {
                  if (input[9] > 1.5000000000000002) {
                      var270 = -0.007748003282537788;
                  } else {
                      var270 = 0.018757080467123134;
                  }
              } else {
                  if (input[3] > 0.7850434804160938) {
                      var270 = 0.011380366356674273;
                  } else {
                      var270 = -0.00000839256906656107;
                  }
              }
          }
      }
      var var271;
      if (input[5] > 92.60076342411848) {
          if (input[4] <= -5.642770726091707) {
              if (input[2] > 0.1610877750531525) {
                  var271 = -0.006434119108559379;
              } else {
                  var271 = -0.022306346339557314;
              }
          } else {
              if (input[13] > 11.500000000000002) {
                  if (input[3] > 0.3725720045298903) {
                      var271 = 0.0005656483615462148;
                  } else {
                      var271 = -0.03419957491820851;
                  }
              } else {
                  if (input[3] > 0.7126275434117413) {
                      var271 = -0.0039511879602436035;
                  } else {
                      var271 = 0.0026258481903552195;
                  }
              }
          }
      } else {
          if (input[5] > 83.75558925058311) {
              if (input[2] <= -0.36304404649009814) {
                  var271 = 0.026642265445896193;
              } else {
                  if (input[4] <= -3.841704337705677) {
                      var271 = -0.012966520465093856;
                  } else {
                      var271 = 0.0033679017906713426;
                  }
              }
          } else {
              if (input[5] > 80.00550695293408) {
                  if (input[0] > 66.44755628362729) {
                      var271 = 0.003096386613107712;
                  } else {
                      var271 = -0.012052897633189138;
                  }
              } else {
                  if (input[5] > 69.85608617600006) {
                      var271 = 0.0024107178679585823;
                  } else {
                      var271 = -0.00023276965156858345;
                  }
              }
          }
      }
      var var272;
      if (input[4] <= -2.1729741642181852) {
          if (input[3] > 0.3968921775675264) {
              if (input[2] > 1.049554179207316) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var272 = -0.017057955727631954;
                  } else {
                      var272 = 0.030936559612864095;
                  }
              } else {
                  if (input[0] > 55.88691867849784) {
                      var272 = -0.004149541246998778;
                  } else {
                      var272 = -0.017601894886032175;
                  }
              }
          } else {
              if (input[6] > 1.9775411669179508) {
                  if (input[9] > 10.500000000000002) {
                      var272 = 0.04003744529389207;
                  } else {
                      var272 = 0.0002051578409830715;
                  }
              } else {
                  if (input[5] <= -16.185744168434606) {
                      var272 = -0.008670328173160184;
                  } else {
                      var272 = 0.0014692925540203251;
                  }
              }
          }
      } else {
          if (input[6] <= -4.4242046780646325) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -1.058187321761838) {
                      var272 = -0.0029692267172905344;
                  } else {
                      var272 = -0.03272312462142318;
                  }
              } else {
                  if (input[9] > 10.500000000000002) {
                      var272 = -0.009211596493256324;
                  } else {
                      var272 = 0.006262313626255041;
                  }
              }
          } else {
              if (input[4] <= -1.8768784815380142) {
                  if (input[0] > 31.776869407021277) {
                      var272 = -0.011098407799586806;
                  } else {
                      var272 = 0.025208948456075072;
                  }
              } else {
                  var272 = 0.00025140811853097144;
              }
          }
      }
      var var273;
      if (input[6] <= -6.069857858271648) {
          if (input[4] <= -3.9776333795063805) {
              if (input[2] <= -0.37162616348632066) {
                  if (input[0] > 48.03337496443599) {
                      var273 = 0.012133218365859354;
                  } else {
                      var273 = -0.0002737474974853325;
                  }
              } else {
                  var273 = -0.014060824457220594;
              }
          } else {
              if (input[4] <= -3.038533070624908) {
                  if (input[9] > 3.5000000000000004) {
                      var273 = -0.018343534210948424;
                  } else {
                      var273 = 0.00392916065346712;
                  }
              } else {
                  if (input[7] <= -0.000000000000000000000000000000000010000000180025095) {
                      var273 = -0.0072054900033319165;
                  } else {
                      var273 = 0.0037628052987710133;
                  }
              }
          }
      } else {
          if (input[6] <= -5.649766231839755) {
              if (input[9] > 9.500000000000002) {
                  if (input[0] > 25.988158720935655) {
                      var273 = 0.01913039663364894;
                  } else {
                      var273 = -0.004014936920841844;
                  }
              } else {
                  if (input[0] > 34.80164837238513) {
                      var273 = -0.007917891624809796;
                  } else {
                      var273 = 0.01015354791086918;
                  }
              }
          } else {
              if (input[2] <= -1.181544842826422) {
                  if (input[4] <= -2.4525000035043685) {
                      var273 = 0.006985759601632018;
                  } else {
                      var273 = -0.008637155921038815;
                  }
              } else {
                  if (input[6] <= -5.555294989730455) {
                      var273 = -0.012077790354218196;
                  } else {
                      var273 = 0.0001304808918108091;
                  }
              }
          }
      }
      var var274;
      if (input[5] > 19.544289135213152) {
          if (input[30] > 0.000000000000000000000000000000000010000000180025095) {
              var274 = -0.014187284109484595;
          } else {
              if (input[3] <= -1.3231254954991536) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var274 = -0.019477565412307093;
                  } else {
                      var274 = 0.012617289276967503;
                  }
              } else {
                  if (input[2] <= -1.315773426511249) {
                      var274 = 0.008606053564486637;
                  } else {
                      var274 = -0.00018763716376471259;
                  }
              }
          }
      } else {
          if (input[6] > 5.524744883280329) {
              var274 = 0.021734877511651193;
          } else {
              if (input[3] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 2.5000000000000004) {
                      var274 = -0.01671696464228631;
                  } else {
                      var274 = 0.008243393240849;
                  }
              } else {
                  if (input[3] <= -0.09198715495658778) {
                      var274 = 0.0004915717960156475;
                  } else {
                      var274 = 0.01761911680419586;
                  }
              }
          }
      }
      var var275;
      if (input[3] <= -1.5218789267492705) {
          if (input[13] > 4.500000000000001) {
              if (input[10] > 2.5000000000000004) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var275 = -0.006454178057382367;
                  } else {
                      var275 = -0.022675561783677703;
                  }
              } else {
                  if (input[9] > 13.500000000000002) {
                      var275 = -0.010332313840819469;
                  } else {
                      var275 = 0.017856949022150154;
                  }
              }
          } else {
              var275 = 0.024123600413983613;
          }
      } else {
          if (input[3] <= -1.4056918431732448) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -1.4512477283604273) {
                      var275 = -0.008592717494907446;
                  } else {
                      var275 = -0.03136749016235464;
                  }
              } else {
                  var275 = 0.0036218127908855626;
              }
          } else {
              if (input[2] <= -1.3479087857871586) {
                  if (input[10] > 2.5000000000000004) {
                      var275 = 0.01113442020481465;
                  } else {
                      var275 = -0.0072742501572596475;
                  }
              } else {
                  if (input[6] <= -6.189019565280997) {
                      var275 = -0.0034346420893767815;
                  } else {
                      var275 = 0.00008183305009158632;
                  }
              }
          }
      }
      var var276;
      if (input[4] > 6.995147082128496) {
          if (input[0] > 37.06590588035515) {
              if (input[9] > 4.500000000000001) {
                  if (input[9] > 17.500000000000004) {
                      var276 = 0.003910521982608521;
                  } else {
                      var276 = -0.01978112983635125;
                  }
              } else {
                  if (input[0] > 51.60793357988327) {
                      var276 = 0.010927311808378177;
                  } else {
                      var276 = -0.014630863702723686;
                  }
              }
          } else {
              var276 = 0.02027635536564368;
          }
      } else {
          if (input[4] > 6.789481691669448) {
              var276 = 0.016635843056231798;
          } else {
              if (input[4] > 6.609695324748413) {
                  var276 = -0.011389443370246145;
              } else {
                  if (input[4] > 5.42653906653272) {
                      var276 = 0.0031529176657814693;
                  } else {
                      var276 = -0.00008242627340604502;
                  }
              }
          }
      }
      var var277;
      if (input[4] > 2.1419746152525203) {
          if (input[0] > 45.82856649399955) {
              if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 5.776823337771391) {
                      var277 = -0.005272506710241735;
                  } else {
                      var277 = 0.014181313552476291;
                  }
              } else {
                  if (input[6] <= -1.2732214212272153) {
                      var277 = -0.01419967167378898;
                  } else {
                      var277 = 0.00004116936311990315;
                  }
              }
          } else {
              if (input[10] > 1.5000000000000002) {
                  if (input[9] > 12.500000000000002) {
                      var277 = -0.013614946447798466;
                  } else {
                      var277 = -0.0013565619959982217;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var277 = -0.016791497222016817;
                  } else {
                      var277 = 0.01831360138262612;
                  }
              }
          }
      } else {
          if (input[4] > 1.7160674285510085) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 49.789732960670115) {
                      var277 = 0.002625496774669926;
                  } else {
                      var277 = 0.02783069894756654;
                  }
              } else {
                  if (input[3] > 1.13964173796312) {
                      var277 = 0.025322293105973528;
                  } else {
                      var277 = -0.002388314449449658;
                  }
              }
          } else {
              if (input[13] > 5.500000000000001) {
                  if (input[31] > 0.000000000000000000000000000000000010000000180025095) {
                      var277 = -0.005157466056449383;
                  } else {
                      var277 = -0.0002599906939474449;
                  }
              } else {
                  var277 = 0.001506855152533155;
              }
          }
      }
      var var278;
      if (input[5] > 27.141286553166832) {
          if (input[0] > 26.383030344586114) {
              if (input[28] > 0.000000000000000000000000000000000010000000180025095) {
                  var278 = 0.015043589485752457;
              } else {
                  if (input[6] <= -1.8783643679700581) {
                      var278 = -0.002179347122651123;
                  } else {
                      var278 = 0.00029652988500730124;
                  }
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 30.755186602054312) {
                      var278 = -0.03177382321803405;
                  } else {
                      var278 = -0.013909929371739856;
                  }
              } else {
                  var278 = 0.0026907774497418767;
              }
          }
      } else {
          if (input[5] > 24.885282685569578) {
              if (input[0] > 42.629776778712966) {
                  if (input[5] > 25.781461905908227) {
                      var278 = 0.003586549666524382;
                  } else {
                      var278 = 0.03662303454826758;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var278 = 0.013633537728863658;
                  } else {
                      var278 = -0.005438053993516666;
                  }
              }
          } else {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                      var278 = 0.027586193414857785;
                  } else {
                      var278 = -0.005631952403467899;
                  }
              } else {
                  if (input[3] > 0.43692332172218623) {
                      var278 = -0.021521021189475922;
                  } else {
                      var278 = 0.0011826678953572158;
                  }
              }
          }
      }
      var var279;
      if (input[4] <= -2.1729741642181852) {
          if (input[4] <= -2.548569004413761) {
              if (input[10] > 1.5000000000000002) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var279 = 0.0017510945031385076;
                  } else {
                      var279 = -0.003952807890761633;
                  }
              } else {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var279 = 0.03617304000349514;
                  } else {
                      var279 = 0.002279318513381558;
                  }
              }
          } else {
              if (input[10] > 1.5000000000000002) {
                  if (input[0] > 52.06853502461072) {
                      var279 = -0.0004964063288186262;
                  } else {
                      var279 = 0.01504305186895818;
                  }
              } else {
                  var279 = -0.005694000614265414;
              }
          }
      } else {
          if (input[6] <= -4.4242046780646325) {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[2] <= -1.058187321761838) {
                      var279 = -0.002635176367459215;
                  } else {
                      var279 = -0.031346920966799405;
                  }
              } else {
                  if (input[25] > 0.000000000000000000000000000000000010000000180025095) {
                      var279 = -0.0118146832621691;
                  } else {
                      var279 = 0.003924036205890128;
                  }
              }
          } else {
              if (input[4] <= -1.8768784815380142) {
                  if (input[0] > 31.776869407021277) {
                      var279 = -0.01057516966169799;
                  } else {
                      var279 = 0.02378423343829169;
                  }
              } else {
                  if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                      var279 = 0.004550083667024192;
                  } else {
                      var279 = -0.000016899970802310775;
                  }
              }
          }
      }
      var var280;
      if (input[8] <= -1.4999999999999998) {
          var280 = -0.008514491853874298;
      } else {
          if (input[8] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[4] > 0.44770045251324836) {
                  if (input[9] > 19.500000000000004) {
                      var280 = -0.028001296789142146;
                  } else {
                      var280 = 0.0008063026965543411;
                  }
              } else {
                  if (input[4] <= -0.23350208572016248) {
                      var280 = 0.004258759452515601;
                  } else {
                      var280 = 0.037839554464197206;
                  }
              }
          } else {
              if (input[22] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                      var280 = 0.015794225672928524;
                  } else {
                      var280 = -0.003935074803787388;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var280 = -0.0008489019257390065;
                  } else {
                      var280 = 0.0006190354703139774;
                  }
              }
          }
      }
      var var281;
      if (input[9] > 22.500000000000004) {
          if (input[23] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[4] > 0.21159223228679339) {
                  var281 = 0.0007075227930224354;
              } else {
                  var281 = 0.025428387235827483;
              }
          } else {
              if (input[5] > 42.4312767999516) {
                  if (input[5] > 57.46002382311671) {
                      var281 = -0.0007005036836056187;
                  } else {
                      var281 = -0.016702860866172183;
                  }
              } else {
                  if (input[18] > 0.000000000000000000000000000000000010000000180025095) {
                      var281 = 0.028312435921314605;
                  } else {
                      var281 = -0.004536559823753635;
                  }
              }
          }
      } else {
          if (input[10] > 3.5000000000000004) {
              if (input[30] > 0.000000000000000000000000000000000010000000180025095) {
                  var281 = 0.025461956512683605;
              } else {
                  if (input[6] > 7.999681113877577) {
                      var281 = 0.013069112596670061;
                  } else {
                      var281 = 0.0001965870419466638;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 2.358131217487968) {
                      var281 = 0.02522764061258785;
                  } else {
                      var281 = -0.0011460112913291658;
                  }
              } else {
                  if (input[2] <= -0.1375084104867184) {
                      var281 = -0.0020556043614216534;
                  } else {
                      var281 = 0.00015476403485649068;
                  }
              }
          }
      }
      var var282;
      if (input[6] > 5.776823337771391) {
          if (input[4] <= -0.7791403766304014) {
              var282 = -0.017757832416233712;
          } else {
              if (input[9] > 19.500000000000004) {
                  if (input[4] > 3.747559616936297) {
                      var282 = 0.012002663994642842;
                  } else {
                      var282 = -0.007094965447089158;
                  }
              } else {
                  if (input[2] > 0.6564316284823694) {
                      var282 = -0.0005547223491955493;
                  } else {
                      var282 = -0.011498906504976966;
                  }
              }
          }
      } else {
          if (input[4] > 7.214329904560428) {
              if (input[0] > 41.4508936947301) {
                  if (input[6] > 4.386551078430429) {
                      var282 = 0.011593111968845814;
                  } else {
                      var282 = -0.014463102649165088;
                  }
              } else {
                  var282 = 0.023451470635530106;
              }
          } else {
              if (input[0] > 90.37724474978073) {
                  var282 = -0.014154096045522788;
              } else {
                  if (input[6] > 3.8237101336355157) {
                      var282 = 0.002204554110322409;
                  } else {
                      var282 = -0.0001787287152066275;
                  }
              }
          }
      }
      var var283;
      if (input[4] > 2.1419746152525203) {
          if (input[4] > 3.114370403695782) {
              if (input[2] <= -0.72087477928065) {
                  if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                      var283 = 0.031086357563399378;
                  } else {
                      var283 = -0.0008956923678210956;
                  }
              } else {
                  if (input[5] > 40.99339472366089) {
                      var283 = 0.0017375298405933378;
                  } else {
                      var283 = -0.0039400273360642715;
                  }
              }
          } else {
              if (input[2] > 0.25887622514763803) {
                  if (input[13] > 9.500000000000002) {
                      var283 = -0.013418898761680488;
                  } else {
                      var283 = 0.0056794932851183914;
                  }
              } else {
                  if (input[13] > 8.500000000000002) {
                      var283 = 0.007501781932604561;
                  } else {
                      var283 = -0.012865953456872107;
                  }
              }
          }
      } else {
          if (input[4] > 1.7160674285510085) {
              if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                  var283 = -0.0182271031004216;
              } else {
                  if (input[9] > 2.5000000000000004) {
                      var283 = 0.008065384132069134;
                  } else {
                      var283 = -0.019884983511494703;
                  }
              }
          } else {
              if (input[13] > 5.500000000000001) {
                  if (input[31] > 0.000000000000000000000000000000000010000000180025095) {
                      var283 = -0.004914084660940528;
                  } else {
                      var283 = -0.00022287800021667315;
                  }
              } else {
                  if (input[6] > 2.600604898520747) {
                      var283 = 0.006268179913639565;
                  } else {
                      var283 = 0.0005968304493365408;
                  }
              }
          }
      }
      var var284;
      if (input[5] > 27.141286553166832) {
          if (input[0] > 26.383030344586114) {
              if (input[0] > 27.865205959973) {
                  if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                      var284 = 0.0011682780425238835;
                  } else {
                      var284 = -0.0008382041918606516;
                  }
              } else {
                  var284 = 0.015149432480255144;
              }
          } else {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 30.755186602054312) {
                      var284 = -0.030781139258798097;
                  } else {
                      var284 = -0.013211105821527456;
                  }
              } else {
                  var284 = 0.002519137892059809;
              }
          }
      } else {
          if (input[5] > 24.885282685569578) {
              if (input[3] <= -1.1666071606843709) {
                  var284 = -0.013946454038887751;
              } else {
                  if (input[4] > 1.4102933279560708) {
                      var284 = -0.0001144174977903933;
                  } else {
                      var284 = 0.01471552145227737;
                  }
              }
          } else {
              if (input[13] > 1.5000000000000002) {
                  if (input[32] > 0.000000000000000000000000000000000010000000180025095) {
                      var284 = 0.006713678740526416;
                  } else {
                      var284 = 0.00007549946703476606;
                  }
              } else {
                  if (input[4] <= -1.4059925816462056) {
                      var284 = -0.019100224958445128;
                  } else {
                      var284 = -0.0027737012237047574;
                  }
              }
          }
      }
      var var285;
      if (input[5] > 19.544289135213152) {
          if (input[30] > 0.000000000000000000000000000000000010000000180025095) {
              var285 = -0.014060993063103669;
          } else {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 24.123903734081484) {
                      var285 = 0.0012068874139412459;
                  } else {
                      var285 = -0.023813998977435597;
                  }
              } else {
                  if (input[5] > 69.85608617600006) {
                      var285 = 0.0007008438503610176;
                  } else {
                      var285 = -0.001904019926187621;
                  }
              }
          }
      } else {
          if (input[6] > 5.524744883280329) {
              var285 = 0.020386896318323963;
          } else {
              if (input[3] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 2.5000000000000004) {
                      var285 = -0.0159302908204261;
                  } else {
                      var285 = 0.007603009034996446;
                  }
              } else {
                  if (input[3] <= -0.09198715495658778) {
                      var285 = 0.0005546391294829421;
                  } else {
                      var285 = 0.01669295665841625;
                  }
              }
          }
      }
      var var286;
      if (input[3] > 0.5298948855459753) {
          if (input[5] > 46.93129976544811) {
              if (input[2] > 0.4277349085853263) {
                  if (input[2] > 0.46600133880606415) {
                      var286 = 0.0000034594683775072982;
                  } else {
                      var286 = 0.01731038044717923;
                  }
              } else {
                  if (input[3] > 0.5739461858304286) {
                      var286 = -0.0037774595679106295;
                  } else {
                      var286 = -0.023957911415807897;
                  }
              }
          } else {
              if (input[0] > 41.4508936947301) {
                  if (input[9] > 4.500000000000001) {
                      var286 = -0.011413776815205333;
                  } else {
                      var286 = -0.039264200756948885;
                  }
              } else {
                  var286 = 0.011266794666634711;
              }
          }
      } else {
          if (input[0] > 66.95627012882493) {
              if (input[2] > 0.07964264394560235) {
                  if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                      var286 = -0.005297789218821549;
                  } else {
                      var286 = 0.012649931975979925;
                  }
              } else {
                  if (input[4] <= -0.07525540048998729) {
                      var286 = 0.00011820922345260556;
                  } else {
                      var286 = -0.01949779826208438;
                  }
              }
          } else {
              if (input[24] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -0.456609706027228) {
                      var286 = -0.015415513988667452;
                  } else {
                      var286 = 0.0067352139896496984;
                  }
              } else {
                  if (input[0] > 65.44503760026167) {
                      var286 = -0.009421303774765463;
                  } else {
                      var286 = -0.00008819637836648453;
                  }
              }
          }
      }
      var var287;
      if (input[2] > 0.025809299484776383) {
          if (input[0] > 25.51590802753186) {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[10] > 2.5000000000000004) {
                      var287 = -0.010878979120101545;
                  } else {
                      var287 = 0.003046017374822038;
                  }
              } else {
                  if (input[6] <= -4.22423090678842) {
                      var287 = 0.023082690428220306;
                  } else {
                      var287 = -0.000018881318578686026;
                  }
              }
          } else {
              var287 = -0.023808106242072243;
          }
      } else {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[4] <= -1.3638478252284243) {
                      var287 = 0.0009826325111280064;
                  } else {
                      var287 = 0.022375134239642536;
                  }
              } else {
                  if (input[5] > 33.1636995781717) {
                      var287 = -0.01574817170743188;
                  } else {
                      var287 = 0.009499597522118396;
                  }
              }
          } else {
              if (input[0] > 69.60929903160356) {
                  if (input[4] <= -0.07525540048998729) {
                      var287 = -0.0010053884832892394;
                  } else {
                      var287 = -0.04550913680130049;
                  }
              } else {
                  if (input[2] > 0.01922684886344592) {
                      var287 = 0.016575946998775272;
                  } else {
                      var287 = 0.000025347834786837725;
                  }
              }
          }
      }
      var var288;
      if (input[3] <= -1.5218789267492705) {
          if (input[13] > 4.500000000000001) {
              if (input[10] > 2.5000000000000004) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var288 = -0.005976651278678772;
                  } else {
                      var288 = -0.021582296265901243;
                  }
              } else {
                  if (input[4] <= -2.9843671545002652) {
                      var288 = 0.019581362998134653;
                  } else {
                      var288 = -0.007787735544770691;
                  }
              }
          } else {
              var288 = 0.022896577537988082;
          }
      } else {
          if (input[3] <= -1.4056918431732448) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[3] <= -1.4512477283604273) {
                      var288 = -0.007912454742063833;
                  } else {
                      var288 = -0.03001310776182599;
                  }
              } else {
                  var288 = 0.003622821717528606;
              }
          } else {
              if (input[2] <= -1.3479087857871586) {
                  if (input[10] > 2.5000000000000004) {
                      var288 = 0.010740121086693429;
                  } else {
                      var288 = -0.006890297592467927;
                  }
              } else {
                  if (input[6] <= -6.189019565280997) {
                      var288 = -0.0031749059527107666;
                  } else {
                      var288 = 0.00006671561062788306;
                  }
              }
          }
      }
      var var289;
      if (input[4] <= -2.1729741642181852) {
          if (input[3] > 0.3968921775675264) {
              if (input[51] > 0.000000000000000000000000000000000010000000180025095) {
                  var289 = 0.016180277093637216;
              } else {
                  if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                      var289 = -0.031581934784645764;
                  } else {
                      var289 = -0.004166493294632429;
                  }
              }
          } else {
              if (input[6] > 1.9775411669179508) {
                  if (input[9] > 10.500000000000002) {
                      var289 = 0.03741574586181182;
                  } else {
                      var289 = -0.00023511122797135748;
                  }
              } else {
                  if (input[5] <= -16.185744168434606) {
                      var289 = -0.008130157989013993;
                  } else {
                      var289 = 0.0014566612116990152;
                  }
              }
          }
      } else {
          if (input[4] <= -0.7791403766304014) {
              if (input[10] > 4.500000000000001) {
                  if (input[3] > 0.6285639142159906) {
                      var289 = -0.02796655798347336;
                  } else {
                      var289 = 0.009050595900246147;
                  }
              } else {
                  if (input[0] > 73.97049088155427) {
                      var289 = 0.012088038252801494;
                  } else {
                      var289 = -0.004565847673002266;
                  }
              }
          } else {
              if (input[4] <= -0.45083601189522843) {
                  if (input[3] <= -0.24344553277095524) {
                      var289 = -0.003325329916916426;
                  } else {
                      var289 = 0.009947898685206262;
                  }
              } else {
                  if (input[4] <= -0.11306425342193112) {
                      var289 = -0.004716624480393876;
                  } else {
                      var289 = 0.00028034780185703494;
                  }
              }
          }
      }
      var var290;
      if (input[6] > 5.776823337771391) {
          if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
              if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] > 58.8496323370599) {
                      var290 = -0.022393959160467113;
                  } else {
                      var290 = 0.009155032007626782;
                  }
              } else {
                  if (input[2] > 1.5557519278225522) {
                      var290 = -0.011099133097091778;
                  } else {
                      var290 = 0.010622082869053459;
                  }
              }
          } else {
              if (input[9] > 19.500000000000004) {
                  if (input[9] > 20.500000000000004) {
                      var290 = 0.001919345544132771;
                  } else {
                      var290 = 0.03087896849658251;
                  }
              } else {
                  if (input[5] > 61.34338824862519) {
                      var290 = 0.0009790595986279157;
                  } else {
                      var290 = -0.011848769611510641;
                  }
              }
          }
      } else {
          if (input[4] > 7.214329904560428) {
              if (input[0] > 41.4508936947301) {
                  if (input[6] > 4.386551078430429) {
                      var290 = 0.011057495665256673;
                  } else {
                      var290 = -0.013780623355789777;
                  }
              } else {
                  var290 = 0.022333239979629663;
              }
          } else {
              if (input[0] > 90.37724474978073) {
                  var290 = -0.013598213944729438;
              } else {
                  if (input[6] > 3.8237101336355157) {
                      var290 = 0.0020456056303240462;
                  } else {
                      var290 = -0.00015812050091943276;
                  }
              }
          }
      }
      var var291;
      if (input[4] > 6.995147082128496) {
          if (input[0] > 37.06590588035515) {
              if (input[9] > 4.500000000000001) {
                  if (input[9] > 17.500000000000004) {
                      var291 = 0.003094513433387927;
                  } else {
                      var291 = -0.01894585076631781;
                  }
              } else {
                  if (input[0] > 51.60793357988327) {
                      var291 = 0.010320865921362424;
                  } else {
                      var291 = -0.013816822774318428;
                  }
              }
          } else {
              var291 = 0.017695625656599507;
          }
      } else {
          if (input[4] > 6.789481691669448) {
              var291 = 0.015562231914110006;
          } else {
              if (input[4] > 6.609695324748413) {
                  var291 = -0.010935513000985877;
              } else {
                  if (input[4] > 5.42653906653272) {
                      var291 = 0.002887130373241454;
                  } else {
                      var291 = -0.00006562288586319679;
                  }
              }
          }
      }
      var var292;
      if (input[2] > 0.025809299484776383) {
          if (input[0] > 25.51590802753186) {
              if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 60.256910276410956) {
                      var292 = 0.010189996025218896;
                  } else {
                      var292 = -0.021617597068017247;
                  }
              } else {
                  if (input[6] <= -4.22423090678842) {
                      var292 = 0.016703857933611923;
                  } else {
                      var292 = -0.00017539469808435277;
                  }
              }
          } else {
              var292 = -0.023006448975174138;
          }
      } else {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[2] <= -0.5707573139456269) {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var292 = 0.011519533370147042;
                  } else {
                      var292 = -0.0176352507644345;
                  }
              } else {
                  if (input[6] <= -3.955371694873149) {
                      var292 = 0.03879127894253906;
                  } else {
                      var292 = 0.006194349024938204;
                  }
              }
          } else {
              if (input[0] > 69.60929903160356) {
                  if (input[4] <= -0.07525540048998729) {
                      var292 = -0.0010365780209831703;
                  } else {
                      var292 = -0.04390097701106921;
                  }
              } else {
                  if (input[2] > 0.01922684886344592) {
                      var292 = 0.01562240556171434;
                  } else {
                      var292 = 0.00003499638782054103;
                  }
              }
          }
      }
      var var293;
      if (input[53] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[13] > 8.500000000000002) {
              var293 = 0.017462709299083442;
          } else {
              if (input[0] > 54.6459680035938) {
                  var293 = 0.01247937811102531;
              } else {
                  var293 = -0.011413412136628888;
              }
          }
      } else {
          if (input[5] > 19.544289135213152) {
              if (input[5] > 24.0530548127776) {
                  if (input[0] > 25.034626636612057) {
                      var293 = 0.00004511600238348596;
                  } else {
                      var293 = -0.011241807678860247;
                  }
              } else {
                  if (input[6] <= -3.0679910897894938) {
                      var293 = 0.004885237672803329;
                  } else {
                      var293 = -0.009206769378218065;
                  }
              }
          } else {
              if (input[9] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 5.524744883280329) {
                      var293 = 0.018860623805253027;
                  } else {
                      var293 = 0.00028578498757456696;
                  }
              } else {
                  var293 = 0.01693418166187755;
              }
          }
      }
      var var294;
      if (input[4] > 6.995147082128496) {
          if (input[0] > 43.39903825771221) {
              if (input[6] > 4.386551078430429) {
                  if (input[9] > 6.500000000000001) {
                      var294 = -0.011847173817653503;
                  } else {
                      var294 = 0.005081208260731499;
                  }
              } else {
                  var294 = -0.028042898046260353;
              }
          } else {
              if (input[13] > 5.500000000000001) {
                  var294 = 0.0022841213646192077;
              } else {
                  var294 = 0.024119143741778194;
              }
          }
      } else {
          if (input[4] > 6.789481691669448) {
              var294 = 0.014721602896144853;
          } else {
              if (input[4] > 6.609695324748413) {
                  var294 = -0.010365717448847907;
              } else {
                  if (input[2] > 1.3853947133785054) {
                      var294 = -0.003021940565610313;
                  } else {
                      var294 = 0.00013206929303472047;
                  }
              }
          }
      }
      var var295;
      if (input[5] > 92.60076342411848) {
          if (input[6] <= -2.4472201593862972) {
              if (input[3] > 0.06654748911058106) {
                  var295 = -0.030140795733234024;
              } else {
                  var295 = 0.000295709084737569;
              }
          } else {
              if (input[6] <= -1.6725312394562015) {
                  var295 = 0.014428118783773872;
              } else {
                  if (input[4] > 0.7977856053883731) {
                      var295 = 0.0012104510047473668;
                  } else {
                      var295 = -0.003744669094665862;
                  }
              }
          }
      } else {
          if (input[5] > 90.75609196671006) {
              if (input[29] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 64.25004156967033) {
                      var295 = 0.013880930160731747;
                  } else {
                      var295 = -0.026359032622910752;
                  }
              } else {
                  if (input[0] > 71.16997505228687) {
                      var295 = -0.0016598289954493546;
                  } else {
                      var295 = 0.027172062239676466;
                  }
              }
          } else {
              if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[13] > 6.500000000000001) {
                      var295 = 0.009906198654436203;
                  } else {
                      var295 = -0.004068706338906325;
                  }
              } else {
                  if (input[15] > 0.000000000000000000000000000000000010000000180025095) {
                      var295 = -0.002352474314488446;
                  } else {
                      var295 = 0.0002022930552147754;
                  }
              }
          }
      }
      var var296;
      if (input[4] > 2.1419746152525203) {
          if (input[0] > 45.82856649399955) {
              if (input[45] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[6] > 5.776823337771391) {
                      var296 = -0.005174120660425415;
                  } else {
                      var296 = 0.013292333326901544;
                  }
              } else {
                  if (input[3] > 0.8803735198967305) {
                      var296 = -0.004111605394417391;
                  } else {
                      var296 = 0.0009700088220768384;
                  }
              }
          } else {
              if (input[10] > 1.5000000000000002) {
                  if (input[9] > 12.500000000000002) {
                      var296 = -0.01279848298232603;
                  } else {
                      var296 = -0.0013150597677124708;
                  }
              } else {
                  if (input[11] > 0.000000000000000000000000000000000010000000180025095) {
                      var296 = -0.016019102445725672;
                  } else {
                      var296 = 0.017118790099026046;
                  }
              }
          }
      } else {
          if (input[4] > 1.7160674285510085) {
              if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 49.789732960670115) {
                      var296 = 0.002260263627576469;
                  } else {
                      var296 = 0.025893008335744424;
                  }
              } else {
                  if (input[3] > 1.13964173796312) {
                      var296 = 0.023670872431939386;
                  } else {
                      var296 = -0.0025029358799115433;
                  }
              }
          } else {
              if (input[13] > 5.500000000000001) {
                  if (input[5] > 64.80441652620755) {
                      var296 = -0.003205799025446057;
                  } else {
                      var296 = 0.0002708242534597317;
                  }
              } else {
                  var296 = 0.0014051357048542549;
              }
          }
      }
      var var297;
      if (input[53] > 0.000000000000000000000000000000000010000000180025095) {
          if (input[13] > 8.500000000000002) {
              var297 = 0.016537501008615875;
          } else {
              if (input[0] > 54.6459680035938) {
                  var297 = 0.011804026795260202;
              } else {
                  var297 = -0.010845993385349507;
              }
          }
      } else {
          if (input[6] > 0.3551665137137319) {
              if (input[0] > 28.941439086755278) {
                  if (input[4] <= -5.327365940140429) {
                      var297 = 0.015281922388769088;
                  } else {
                      var297 = -0.0003575177561910597;
                  }
              } else {
                  if (input[10] > 1.5000000000000002) {
                      var297 = -0.021493320718415396;
                  } else {
                      var297 = 0.01192391326465521;
                  }
              }
          } else {
              if (input[2] > 0.7872055857050603) {
                  var297 = 0.023331693632392406;
              } else {
                  if (input[7] > 1.5000000000000002) {
                      var297 = 0.012860084840870867;
                  } else {
                      var297 = 0.00009504228690996401;
                  }
              }
          }
      }
      var var298;
      if (input[5] > 27.141286553166832) {
          if (input[6] <= -2.5554043664065276) {
              if (input[13] > 10.500000000000002) {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var298 = -0.020737936686251728;
                  } else {
                      var298 = 0.0027137523557818647;
                  }
              } else {
                  if (input[12] <= -0.000000000000000000000000000000000010000000180025095) {
                      var298 = 0.005217581840891791;
                  } else {
                      var298 = -0.004635348001060122;
                  }
              }
          } else {
              if (input[17] > 0.000000000000000000000000000000000010000000180025095) {
                  var298 = 0.0018043697658398077;
              } else {
                  if (input[26] > 0.000000000000000000000000000000000010000000180025095) {
                      var298 = -0.005154212338138823;
                  } else {
                      var298 = 0.0002628635734883451;
                  }
              }
          }
      } else {
          if (input[4] > 0.9187848953214247) {
              if (input[10] > 1.5000000000000002) {
                  if (input[16] > 0.000000000000000000000000000000000010000000180025095) {
                      var298 = -0.026111821572356794;
                  } else {
                      var298 = -0.0037146993562157133;
                  }
              } else {
                  if (input[4] > 2.8049613573678696) {
                      var298 = 0.017809067006550838;
                  } else {
                      var298 = -0.0029768897071319913;
                  }
              }
          } else {
              if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[5] <= -4.036293855178701) {
                      var298 = -0.018225442612517774;
                  } else {
                      var298 = 0.02447144728307162;
                  }
              } else {
                  if (input[2] > 0.25887622514763803) {
                      var298 = 0.014734015039852527;
                  } else {
                      var298 = 0.0005925112705423121;
                  }
              }
          }
      }
      var var299;
      if (input[2] > 0.025809299484776383) {
          if (input[0] > 25.51590802753186) {
              if (input[33] > 0.000000000000000000000000000000000010000000180025095) {
                  if (input[0] > 60.256910276410956) {
                      var299 = 0.009028727938400571;
                  } else {
                      var299 = -0.020837737420399502;
                  }
              } else {
                  if (input[6] <= -4.22423090678842) {
                      var299 = 0.015699407311605983;
                  } else {
                      var299 = -0.0001709341195591251;
                  }
              }
          } else {
              var299 = -0.02203319339067272;
          }
      } else {
          if (input[27] > 0.000000000000000000000000000000000010000000180025095) {
              if (input[13] > 3.5000000000000004) {
                  if (input[13] > 4.500000000000001) {
                      var299 = 0.004572405802948026;
                  } else {
                      var299 = -0.02028118851640377;
                  }
              } else {
                  if (input[19] > 0.000000000000000000000000000000000010000000180025095) {
                      var299 = 0.033714389738446475;
                  } else {
                      var299 = -0.0011173522668470335;
                  }
              }
          } else {
              if (input[0] > 64.75395318316197) {
                  if (input[4] > 1.21504549149153) {
                      var299 = -0.02565567554407154;
                  } else {
                      var299 = -0.003925333871491065;
                  }
              } else {
                  if (input[3] <= -0.20134330740589654) {
                      var299 = -0.0005346675875155314;
                  } else {
                      var299 = 0.002900344802200548;
                  }
              }
          }
      }
      var var300;
      var300 = valensConfidenceSigmoid(var0 + var1 + var2 + var3 + var4 + var5 + var6 + var7 + var8 + var9 + var10 + var11 + var12 + var13 + var14 + var15 + var16 + var17 + var18 + var19 + var20 + var21 + var22 + var23 + var24 + var25 + var26 + var27 + var28 + var29 + var30 + var31 + var32 + var33 + var34 + var35 + var36 + var37 + var38 + var39 + var40 + var41 + var42 + var43 + var44 + var45 + var46 + var47 + var48 + var49 + var50 + var51 + var52 + var53 + var54 + var55 + var56 + var57 + var58 + var59 + var60 + var61 + var62 + var63 + var64 + var65 + var66 + var67 + var68 + var69 + var70 + var71 + var72 + var73 + var74 + var75 + var76 + var77 + var78 + var79 + var80 + var81 + var82 + var83 + var84 + var85 + var86 + var87 + var88 + var89 + var90 + var91 + var92 + var93 + var94 + var95 + var96 + var97 + var98 + var99 + var100 + var101 + var102 + var103 + var104 + var105 + var106 + var107 + var108 + var109 + var110 + var111 + var112 + var113 + var114 + var115 + var116 + var117 + var118 + var119 + var120 + var121 + var122 + var123 + var124 + var125 + var126 + var127 + var128 + var129 + var130 + var131 + var132 + var133 + var134 + var135 + var136 + var137 + var138 + var139 + var140 + var141 + var142 + var143 + var144 + var145 + var146 + var147 + var148 + var149 + var150 + var151 + var152 + var153 + var154 + var155 + var156 + var157 + var158 + var159 + var160 + var161 + var162 + var163 + var164 + var165 + var166 + var167 + var168 + var169 + var170 + var171 + var172 + var173 + var174 + var175 + var176 + var177 + var178 + var179 + var180 + var181 + var182 + var183 + var184 + var185 + var186 + var187 + var188 + var189 + var190 + var191 + var192 + var193 + var194 + var195 + var196 + var197 + var198 + var199 + var200 + var201 + var202 + var203 + var204 + var205 + var206 + var207 + var208 + var209 + var210 + var211 + var212 + var213 + var214 + var215 + var216 + var217 + var218 + var219 + var220 + var221 + var222 + var223 + var224 + var225 + var226 + var227 + var228 + var229 + var230 + var231 + var232 + var233 + var234 + var235 + var236 + var237 + var238 + var239 + var240 + var241 + var242 + var243 + var244 + var245 + var246 + var247 + var248 + var249 + var250 + var251 + var252 + var253 + var254 + var255 + var256 + var257 + var258 + var259 + var260 + var261 + var262 + var263 + var264 + var265 + var266 + var267 + var268 + var269 + var270 + var271 + var272 + var273 + var274 + var275 + var276 + var277 + var278 + var279 + var280 + var281 + var282 + var283 + var284 + var285 + var286 + var287 + var288 + var289 + var290 + var291 + var292 + var293 + var294 + var295 + var296 + var297 + var298 + var299);
      return [1.0 - var300, var300];
  }
  function valensConfidenceSigmoid(x) {
      if (x < 0.0) {
          var z = Math.exp(x);
          return z / (1.0 + z);
      }
      return 1.0 / (1.0 + Math.exp(-x));
  }


  // ============ CANLI GUVEN MOTORU (LightGBM) ============
  // Kullanici istegi: "terminal her an, hangi saniyede olursa olsun, o anki TUM stratejilerin +
  // gostergelerin durumuna bakip en cok desteklenen kurulumu yakalasin." Model Python'da egitilip
  // m2cgen ile SAF JAVASCRIPT'e (yukarida, hicbir sunucu/Python bagimliligi yok) donusturuldu.
  // Sadece VALENS_ML_TAGS listesindeki stratejileri taniyor - digerleri (emaCross, confluence, vb.)
  // skorlanmiyor (mlConfidenceMap'te yer almiyor), botTick'te eskisi gibi calismaya devam eder.
  const exhaustionBiasNow = detectReversalExhaustion(a, 8);
  // V2 (26 Eylul 2026): 177.245 gercek sinyal (2009-2018 egitim / 2019-2026 TEK SEFERLIK OOS,
  // runHistoricalBacktest'in AYNI mantigiyla 17 yillik H1 veriden cikarildi) uzerinde yeniden
  // egitildi - bu kez 12 eski ozelligin yanina, aynen bu oturumda doGrulanmis 2 yeni gercek sinyal
  // eklendi: macroTrend (200-gunluk SMA + 30/200 kesisimi, bkz fetchMacroTrend) ve month (eylul
  // mevsimselligi dahil, bkz Terminal Teshis Raporu). Sonuc: en guvenilir %20 dilimde kazanma lift'i
  // +1.45 puandan +2.37 puana cikti (AUC hemen hemen ayni kaldi, %51.3->%51.4 - beklenen, cunku bu 2
  // yeni ozellik sadece BELIRLI donem/stratejiler icin devreye giriyor, genel siralamayi degil dogru
  // ustteki dilimi guclendiriyor). asianFakeout/extremeMeanReversion bu veri araliginda hic ates
  // almadigi icin listeden dustu - bu bir regresyon degil, o iki strateji zaten cok nadir ates aliyor.
  const VALENS_ML_TAGS = ["bollSqueeze","chochSignal","divergenceChoch","equalHighsLows","fvgRetest","ifvg","insideBar","liquiditySweep","macdZeroCross","momentum","obFvgConfluence","orb","orbSweepFade","orderBlockMit","pocBounce","rsiDivergence","silverBullet","srTestReversal","ttmSqueeze","vwapPullback"];
  const VALENS_ML_THRESHOLD = 0.387550407252949;
  function valensBuildMlFeatures(tagKey, tagDir, tagMap, rsiV, adxV, macdV, ema921V, ema50200V, bollPctV, vwapDistV, structureBiasV, exhaustionBiasV, hourV, dowV, macroTrendV, monthV){
   const idx = VALENS_ML_TAGS.indexOf(tagKey);
   if(idx<0) return null;
   const input=[rsiV,adxV,macdV,ema921V,ema50200V,bollPctV,vwapDistV,structureBiasV,exhaustionBiasV,hourV,dowV,tagDir,macroTrendV,monthV];
   for(let i=0;i<VALENS_ML_TAGS.length;i++) input.push(tagMap[VALENS_ML_TAGS[i]]!=null?tagMap[VALENS_ML_TAGS[i]]:0);
   for(let i=0;i<VALENS_ML_TAGS.length;i++) input.push(i===idx?1:0);
   try{ return valensConfidenceScore(input)[1]; }catch(e){ return null; }
  }
  const mlTagMap={};
  (strategyTags||[]).forEach(tg=>{ if(tg.key!=='valensEliteScalp') mlTagMap[tg.key]=tg.dir; });
  const mlAtrSafe=(atrReal && atrReal>0)?atrReal:1;
  const mlDate=new Date(a[a.length-1].time*1000);
  const mlHour=mlDate.getUTCHours(), mlDow=mlDate.getUTCDay();
  const mlConfidenceMap={};
  (strategyTags||[]).forEach(tg=>{
   if(tg.key==='valensEliteScalp') return;
   const p=valensBuildMlFeatures(tg.key, tg.dir, mlTagMap,
    rsiReal!=null?rsiReal:50, adxReal!=null?adxReal:15, macdReal/mlAtrSafe,
    (ema9Real-ema21Real)/mlAtrSafe, (ema50Real-ema200Real)/mlAtrSafe,
    bollPctReal!==null?bollPctReal:50, (last-vwapReal)/mlAtrSafe,
    structureBiasNow, exhaustionBiasNow, mlHour, mlDow, window.valensMacroTrend||0, mlDate.getUTCMonth()+1);
   if(p!=null) mlConfidenceMap[tg.key]=p;
  });

  window.valensChartRead={
    trend: slope>0?1:slope<0?-1:0,
    fastTrend,
    pattern: pat?(pat.d==='bull'?1:pat.d==='bear'?-1:0):0,
    patternName: pat?pat.n:'',
    srBias, srText, fibBias, fibZone, strategyTags,
    structureBias: structureBiasNow,
    exhaustionBias: exhaustionBiasNow,
    mlConfidence: mlConfidenceMap,
    mlThreshold: VALENS_ML_THRESHOLD,
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
  if(trailedSLLine){ cs.removePriceLine(trailedSLLine); trailedSLLine=null; }
  if(eliteTrailedSLLine){ cs.removePriceLine(eliteTrailedSLLine); eliteTrailedSLLine=null; }
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
  fetchMacroTrend(sym);
  fetchScalpBias(sym);
  fetchCombo3Data(sym);
  loadHistory().then(()=>{
    drawSRLines(); connect(); connectTrades();
    // ---- EKSENİ YENİ FİYATA OTURT ----
    chart.priceScale('right').applyOptions({autoScale:true});
    showRecentRange();
  });
  setTimeout(resize,120);
 };
 setInterval(()=>{ if(curSym && binSym) fetchMainSR(curSym); }, 5*60*1000); // ana S/R'ı 5 dakikada bir tazele
 setInterval(()=>{ if(curSym && binSym) fetchMacroTrend(curSym); }, 30*60*1000); // günlük veri, sık tazelemeye gerek yok
 // ---- Zaman dilimi (15M/30M/1H/4H/1D) değiştiğinde GERÇEKTEN yeni aralıkta veri çeker ----
 // Önceden zaman dilimi butonları sadece başlık yazısını değiştiriyordu, veri her zaman 15m kalıyordu.
 window.valensSetInterval=function(){
  if(!binSym) return; // canlı veri akışı olmayan enstrüman (ör. SPX500) — yapacak bir şey yok
  if(ws){ws.close();ws=null;} if(tradeWs){tradeWs.close();tradeWs=null;}
  cs.setMarkers([]); trendSeries.setData([]); chanUp.setData([]); chanLo.setData([]);
  kelUp.setData([]); kelLo.setData([]);
  patternMarkers=[];
  fvgZoneLines.forEach(l=>cs.removePriceLine(l)); fvgZoneLines=[]; fvgMarker=null;
  if(trailedSLLine){ cs.removePriceLine(trailedSLLine); trailedSLLine=null; }
  if(eliteTrailedSLLine){ cs.removePriceLine(eliteTrailedSLLine); eliteTrailedSLLine=null; }
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
