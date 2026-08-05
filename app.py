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

# ============ AI HABER ARAŞTIRMASI (Anthropic API + gerçek web araması) ============
# Kullanıcı bir haber konusu girdiğinde (ör. "Faiz kararı"), Claude'u GERÇEK web arama aracıyla
# çağırıp güncel internet verisine dayanan olası senaryolar üretir. Kesin tahmin İSTEMİYORUZ —
# modelden bilinçli olarak "olası senaryolar" istiyoruz, "şu kesin olacak" değil.
@st.cache_data(ttl=3600, show_spinner=False)
def get_ai_news_scenario(topic, instrument_label):
    key = ""
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    key = key or __import__("os").environ.get("ANTHROPIC_API_KEY", "")
    if not key or not topic:
        return {"available": False, "reason": "no_key", "diag": "no_key", "topic": topic}
    try:
        prompt = (
            f"Sen kurumsal bir makro-piyasa analistisin. Konu: \"{topic}\". "
            f"Bu konuyla ilgili GÜNCEL gelişmeleri web aramasıyla bul (tarih, kaynak belirt). "
            f"Sonra {instrument_label} için 2-3 KISA olası senaryo yaz, 'Eğer X olursa → genellikle Y beklenir' "
            f"formatında. KESİN TAHMİN YAPMA — sadece bilinen ilişkileri ve güncel bağlamı özetle. "
            f"En fazla 180 kelime, Türkçe, madde işaretli."
        )
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 700,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            },
            timeout=45,
        )
        status = r.status_code
        if status != 200:
            return {"available": False, "reason": "api_error", "diag": f"status={status} body={str(r.text)[:200]}", "topic": topic}
        data = r.json()
        text_parts = [b.get("text", "") for b in data.get("content", []) if isinstance(b, dict) and b.get("type") == "text"]
        text = "\n".join([t for t in text_parts if t]).strip()
        if not text:
            return {"available": False, "reason": "empty", "diag": "no text in response", "topic": topic}
        return {"available": True, "text": text, "topic": topic, "diag": f"status={status}"}
    except Exception as e:
        return {"available": False, "reason": "error", "diag": "exception: " + str(e)[:200], "topic": topic}

# Kullanıcının Streamlit'te (JS panelinin DIŞINDA, gerçek bir Streamlit widget'ında) girdiği konu.
# JS içindeki manuel haber formu bunu TETİKLEYEMEZ (components.html tek yönlüdür, Python'a geri
# veri gönderemez) — bu yüzden bu ayrı, gerçek bir Streamlit girişi olarak var.
if "ai_news_topic" not in st.session_state:
    st.session_state.ai_news_topic = ""
with st.expander("🔍 AI ile Haber Araştır (Claude + gerçek web araması, ücretli API)", expanded=False):
    st.caption("Not: Bu, JS panelindeki hızlı/kural-tabanlı manuel haber girişinden FARKLI bir araçtır — burada gerçekten internet taranır. Her sorgu Anthropic hesabınızda küçük bir ücrete tabidir (Anthropic Console'da fiyatlandırmaya bakın).")
    topic_input = st.text_input("Haber konusu (ör. 'Fed faiz kararı', 'ECB toplantısı')", key="ai_news_topic_input")
    if st.button("Araştır") and topic_input.strip():
        st.session_state.ai_news_topic = topic_input.strip()
    if st.session_state.ai_news_topic:
        with st.spinner("Claude web'de araştırıyor…"):
            _ai_result = get_ai_news_scenario(st.session_state.ai_news_topic, "XAU/USD ve genel piyasalar")
        if _ai_result.get("available"):
            st.markdown(f"**{_ai_result['topic']}**")
            st.markdown(_ai_result["text"])
        else:
            _reason = _ai_result.get("reason")
            if _reason == "no_key":
                st.info("Bunu kullanmak için Streamlit secrets'e `ANTHROPIC_API_KEY` eklemeniz gerekiyor (console.anthropic.com üzerinden alınır, ücretlidir).")
            else:
                st.warning(f"Araştırma başarısız oldu — diag: {_ai_result.get('diag')}")

AI_NEWS_JSON = _json.dumps(get_ai_news_scenario(st.session_state.ai_news_topic, "XAU/USD ve genel piyasalar") if st.session_state.ai_news_topic else {"available": False, "reason": "no_topic", "topic": ""})

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
.shell{min-height:0;flex:1;display:grid;grid-template-columns:270px minmax(540px,1fr) 310px;overflow:hidden}
aside{background:var(--panel);min-height:0;overflow:auto}.left{border-right:1px solid var(--line)}.right{border-left:1px solid var(--line)}
.ph{height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 13px;border-bottom:1px solid var(--line)}
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
.signal-main,.tradecard{background:var(--panel2);border:1px solid var(--line);border-radius:6px;padding:11px}
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
.stat{background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:8px 9px}
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
.event{margin:10px;border:1px solid var(--line);border-radius:6px;background:var(--panel2);overflow:hidden}
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
    <span>XAU/USD <b id="tk1">4,053.98</b></span><span>ECB Faiz Kararı: <b>%2.40</b></span><span>US İşsizlik Başvuruları: <b>187K</b></span><span>TCMB Faiz Kararı: <b>%37.00</b></span><span>Kurumsal akış ve haber verileri doğrulama gerektirir.</span>
    <span>XAU/USD <b>4,053.98</b></span><span>ECB Faiz Kararı: <b>%2.40</b></span><span>US İşsizlik Başvuruları: <b>187K</b></span><span>TCMB Faiz Kararı: <b>%37.00</b></span><span>Kurumsal akış ve haber verileri doğrulama gerektirir.</span>
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
      <div class="ph"><b data-i18n="teach_title">🎓 MANUEL ÖĞRETİM (kalıp hafızası)</b><span class="badge" id="teachBadge">—</span></div>
      <div style="padding:8px 9px;border-bottom:1px solid var(--line)">
        <div style="font-size:8px;color:var(--muted);margin-bottom:6px" data-i18n="teachHint">Gördüğünüz bir setup'ı (yön + koşullar + sonuç) girin. Aynı koşul kombinasyonu birkaç kez başarılı olursa sistem bunu otomatik olarak kendi strateji hafızasına ekler.</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:5px">
          <select id="tDir" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
            <option value="1" data-i18n-opt="teachBuy">AL (BUY)</option><option value="-1" data-i18n-opt="teachSell">SAT (SELL)</option>
          </select>
          <select id="tZone" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
            <option value="support" data-i18n-opt="teachSupport">Destekte</option><option value="resistance" data-i18n-opt="teachResistance">Dirençte</option><option value="none" data-i18n-opt="teachNoZone">Bölge Yok</option>
          </select>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:5px">
          <select id="tRsi" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
            <option value="oversold" data-i18n-opt="teachOversold">RSI Aşırı Satım</option><option value="neutral" data-i18n-opt="teachNeutralRsi">RSI Nötr</option><option value="overbought" data-i18n-opt="teachOverbought">RSI Aşırı Alım</option>
          </select>
          <select id="tFib" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
            <option value="none" data-i18n-opt="teachNoFib">Fib Yok</option><option value="shallow" data-i18n-opt="teachFibShallow">Fib 0-38.2</option><option value="golden" data-i18n-opt="teachFibGolden">Fib 50-61.8 (Altın)</option><option value="deep" data-i18n-opt="teachFibDeep">Fib 78.6+</option>
          </select>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:5px">
          <select id="tPattern" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
            <option value="none">Mum: Yok</option><option value="Hammer">Hammer</option><option value="Shooting Star">Shooting Star</option><option value="Doji">Doji</option><option value="Bull Engulf">Bull Engulf</option><option value="Bear Engulf">Bear Engulf</option>
          </select>
          <select id="tOutcome" style="background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono'">
            <option value="success" data-i18n-opt="teachSuccess">✓ Başarılı Oldu</option><option value="fail" data-i18n-opt="teachFail">✗ Başarısız Oldu</option>
          </select>
        </div>
        <input id="tNote" type="text" placeholder="Not (opsiyonel, sadece referans)" style="width:100%;background:#07101c;border:1px solid var(--line);color:var(--text);padding:5px;border-radius:3px;font:9px 'IBM Plex Mono';margin-bottom:6px">
        <div style="display:flex;gap:6px">
          <button id="tAdd" style="flex:1;background:var(--gold);color:#07101b;border:0;padding:6px;border-radius:4px;font:700 9px 'IBM Plex Mono';cursor:pointer" data-i18n="teachAdd">+ KAYDET</button>
          <button id="tShowLearned" style="background:transparent;color:var(--gold);border:1px solid var(--line);padding:6px 9px;border-radius:4px;font:9px 'IBM Plex Mono';cursor:pointer" data-i18n="teachShowLearned">Öğrenilenler</button>
        </div>
        <div id="learnedPatternsBox" style="display:none;margin-top:8px;max-height:180px;overflow:auto;font-size:9px"></div>
      </div>
      <div class="ph"><b data-i18n="order_flow_title">ORDER FLOW · YÜKLÜ İŞLEMLER</b><span class="badge" data-i18n="live">CANLI</span></div>
      <div class="simwarn" data-i18n="simwarn">🐋 BTC/kripto için Binance canlı YÜKLÜ (whale) emirleri gösterilir. Forex/endeks için agrega simülasyondur.</div>
      <div class="netdelta" id="netDelta">NET DELTA: — </div>
      <div id="flowFeed"></div>
    </aside>

    <section class="center">
      <div class="megaalert" id="fullAlignmentBanner" style="border-color:var(--gold);background:linear-gradient(90deg,rgba(212,175,55,.22),rgba(0,200,150,.12))"><span style="font-size:18px">🎯</span><div><b id="faBannerTitle" data-i18n="fullAlignmentTitle">TAM UYUM — KESİN İŞLEM</b><br><span id="faBannerBody">—</span></div></div>
      <div class="megaalert" id="megaAlert"><span style="font-size:16px">🚨</span><div><b id="megaAlertTitle" data-i18n="mega_alert_title">YÜKSEK POTANSİYELLİ SCALP</b><br><span id="megaAlertBody">—</span></div></div>

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
        <button class="tfbtn on" data-int="15">15M</button><button class="tfbtn" data-int="30">30M</button><button class="tfbtn" data-int="60">1H</button><button class="tfbtn" data-int="240">4H</button><button class="tfbtn" data-int="D">1D</button>
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
      <div class="ph" style="border-top:1px solid var(--line)"><b data-i18n="ai_news_title">🔍 AI HABER ARAŞTIRMASI</b><span class="badge" id="aiNewsBadge">—</span></div>
      <div id="aiNewsPanel" style="padding:8px 9px;max-height:220px;overflow:auto"><p style="color:var(--muted);font-size:10px" data-i18n="aiNewsHint">Yukarıdaki (sayfanın üstündeki) "AI ile Haber Araştır" kutusuna bir konu yazıp Araştır'a basın — sonuç burada görünecek.</p></div>
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
  ai_news_title:'🔍 AI HABER ARAŞTIRMASI',
  aiNewsHint:'Yukarıdaki (sayfanın üstündeki) "AI ile Haber Araştır" kutusuna bir konu yazıp Araştır\'a basın — sonuç burada görünecek.',
  aiNewsNoKey:'Bunun için Streamlit secrets\'e <code>ANTHROPIC_API_KEY</code> eklemeniz gerekiyor (console.anthropic.com — ücretlidir, her sorgu küçük bir maliyete tabidir).',
  aiNewsError:(diag)=>'Araştırma başarısız oldu. diag: '+diag,
  tightTpWarning:(pct)=>'⚠ Dar hedef / geniş stop yapısı (video kaynağında gözlemlenen orana göre): hedef stoptan küçük, bu yüzden başabaş noktası için en az %'+pct+' gerçek kazanma oranı gerekir. Kazanma oranı yüksek görünse bile, kayıplar kazançlardan büyük olur — dikkatli değerlendirin.',
  teach_title:'🎓 MANUEL ÖĞRETİM (kalıp hafızası)',
  teachHint:"Gördüğünüz bir setup'ı (yön + koşullar + sonuç) girin. Aynı koşul kombinasyonu birkaç kez başarılı olursa sistem bunu otomatik olarak kendi strateji hafızasına ekler.",
  teachBuy:'AL (BUY)', teachSell:'SAT (SELL)', teachSupport:'Destekte', teachResistance:'Dirençte', teachNoZone:'Bölge Yok',
  teachOversold:'RSI Aşırı Satım', teachNeutralRsi:'RSI Nötr', teachOverbought:'RSI Aşırı Alım',
  teachNoFib:'Fib Yok', teachFibShallow:'Fib 0-38.2', teachFibGolden:'Fib 50-61.8 (Altın)', teachFibDeep:'Fib 78.6+',
  teachSuccess:'✓ Başarılı Oldu', teachFail:'✗ Başarısız Oldu', teachAdd:'+ KAYDET', teachShowLearned:'Öğrenilenler',
  teachSaved:'Kaydedildi.', teachLearnedEmpty:'Henüz öğrenilmiş bir kalıp yok — aynı koşul kombinasyonu en az 3 kez başarılı (başarısızlığın en az 2 katı) olursa burada görünecek.',
  teachLearnedTitle:(n)=>n+' öğrenilmiş kalıp:',
  teachPatternDesc:(dir,zone,rsi,fib,pattern)=>(dir>0?'AL':'SAT')+' · '+zone+' · '+rsi+' · '+fib+' · '+pattern,
  teachStrategyLabel:(desc)=>'Öğrenilen Kalıp: '+desc,
  zoneSupport:'Destekte', zoneResistance:'Dirençte', zoneNone:'Bölge Yok',
  rsiOversold:'RSI Aşırı Satım', rsiNeutral:'RSI Nötr', rsiOverbought:'RSI Aşırı Alım',
  fibNone:'Fib Yok', fibShallow:'Fib 0-38.2', fibGolden:'Fib 50-61.8', fibDeep:'Fib 78.6+', patternNone:'Mum Yok',
  newsNoEvents:'Önümüzdeki günler için orta/yüksek etkili planlı haber bulunamadı.', newsNoTemplate:'Bu veri tipi için hazır senaryo şablonu yok — rakamları kendi analizinize göre değerlendirin.',
  newsSame:'Sonuç beklentiyle aynı geldi — belirgin bir yön sinyali yok.',
  newsBeat:'aştı', newsMiss:'ıskaladı', newsHigh:'YÜKSEK', newsMed:'ORTA',
  ccyStrengthens:'güçlendirir', ccyWeakens:'zayıflatır',
  xauPressureNote:' XAU/USD için genel eğilim: baskı (USD güçlü).', xauSupportNote:' XAU/USD için genel eğilim: destek (USD zayıf).',
  xauPressureScenario:' → XAU/USD üzerinde baskı yönünde etki beklenir.', xauSupportScenario:' → XAU/USD üzerinde destekleyici etki beklenir.',
  apiMissingBadge:'API YOK', newsCountBadge:n=>n+' HABER', defaultEventName:'Ekonomik Veri',
  ruleNfp:'İstihdam verisi', ruleUnrate:'İşsizlik oranı', ruleClaims:'İşsizlik başvuruları', ruleCpi:'Enflasyon (CPI)',
  ruleJolts:'JOLTS Açık İş Sayısı', ruleAdp:'ADP İstihdam Değişimi', ruleChallenger:'Challenger İşten Çıkarma',
  employmentFamilyNote:'📌 Bu, geniş "istihdam ailesi" verilerinden biri — JOLTS (açık iş sayısı), ADP, NFP (tarım dışı istihdam), İşsizlik Başvuruları ve İşsizlik Oranı birbiriyle ilişkilidir ve genelde birkaç gün arayla art arda gelir (ör. JOLTS → birkaç gün sonra İşsizlik Başvuruları → ayın ilk Cuma\'sı NFP). Piyasa bunları TEK TEK değil, biriktirdiği genel "işgücü piyasası zayıflıyor mu güçleniyor mu" resmine göre yorumlar — art arda gelen birkaç zayıf/güçlü veri, tek bir veriden daha belirleyicidir.',
  ruleGdp:'GSYH (GDP)', ruleRetail:'Perakende satışlar', rulePmi:'PMI', ruleRate:'Faiz kararı', ruleTrade:'Dış ticaret dengesi',
  noLiveFeedTitle:'● CANLI VERİ YOK', noLiveFeedDesc:"Bu enstrüman için Binance feed'i yok — TwelveData/OANDA API gerekir", noLiveShort:'canlı veri yok',
  goldOffsetLine:(sign,val)=>'PAXG proxy vs gerçek spot altın farkı: '+sign+val+'$ (MT5/OANDA ile karşılaştırırken bu farkı hesaba katın — ticker fiyatı zaten düzeltilmiştir, ama grafikteki S/R/giriş seviyeleri henüz düzeltilmemiştir)',
  zoneTop:'Bölge Üst', zoneBottom:'Bölge Alt', srNearZone:'konsolidasyon/hacim bölgesine yakın',
  mainResistance:'Ana Direnç (1H)', mainSupport:'Ana Destek (1H)', srNearMainSupport:'ana desteğe (1H) yakın', srNearMainResistance:'ana dirence (1H) yakın',
  tagEmaCross:'EMA Momentum Kesişimi (9/21 + MACD/RSI)', tagOrb:'Açılış Aralığı Kırılımı (ORB)', tagMomentum:'Ardışık Mum Momentum Kırılımı',
  tagLiquiditySweep:'Likidite Süpürme Dönüşü (200 EMA + VWAP Reddi)',
  tagRsiDivergence:'RSI Uyumsuzluğu (Divergence)', tagBollSqueeze:'Bollinger Sıkışması + Kırılımı',
  tagEmaPullback:"EMA21'e Geri Çekilme (Trend Devamı)", tagInsideBar:'İç Mum (Inside Bar) Kırılımı',
  tagFvgRetest:'Fair Value Gap Retest (ICT)', tagIfvg:'Inverse Fair Value Gap (ICT)', tagAmdCycle:'AMD Döngüsü (Accumulation-Manipulation-Distribution)',
  tagValuationZone:'Değerleme Ekstremi + Bölge Confluence', tagMacdZeroCross:'MACD Sıfır Çizgisi Kesişimi',
  tagScalpOrb:'ORB Scalp Varyantı (dar aralık)', tagNoWickRetest:'No Wick (Fitilsiz Mum) Geri Test',
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
  psarUpLbl:'▲ YÜKSELİŞ', psarDownLbl:'▼ DÜŞÜŞ', trendUp:'yükselen trend', trendDown:'düşen trend', trendFlat:'yatay',
  srNearSupport:l=>'desteğe yakın ('+l+')', srNearResistance:l=>'dirence yakın ('+l+')',
  srNearDynSupport:'dinamik desteğe (Dyn Support) yakın', srNearDynResistance:'dinamik dirence (Dyn Resistance) yakın',
  confluenceSuffix:' + Fib seviyesi confluence',
  conflictWarning:'⚠ KARIŞIK SİNYAL: başka bir strateji/analiz kazanan adayın TERS yönünde de güçlü bir sinyal veriyor. En iyi seçeneği yine de gösteriyoruz, ama bu bölgede görüşler bölünmüş — dikkatli olun.',
  conflictBadge:'⚠ KARIŞIK SİNYAL — dönüş bölgesi olabilir',
  noLastSignal:'Henüz bu seviyede sinyal verilmedi.',
  lastSignalLine:(dir,entry,tp,time)=>'Son sinyal: <b>'+dir+'</b> · Giriş '+entry+' → TP '+tp+' · '+time,
  risk_governor_title:'🛡 CHALLENGE RİSK YÖNETİCİSİ', risk_balance:'Bakiye ($)', risk_daily:'Günlük Kayıp Limiti (%)',
  risk_max:'Maks. Toplam Kayıp (%)', risk_target:'Kâr Hedefi (%)',
  risk_lotmin:'Lot (min)', risk_lotmax:'Lot (max)', risk_days:'Hedef Gün Sayısı', risk_start:'Başlangıç Tarihi',
  goal_progress_title:'🎯 HEDEFE İLERLEME (gerçek izlenen sonuçlardan)',
  goalDetailLine:(net,target,pctDone,daysLeft,paceNeeded,paceActual)=>
    'İzlenen net: <b>'+net+'</b> / $'+target+' hedef (%'+pctDone+'). Kalan: <b>'+daysLeft+' gün</b>. '+
    'Hedefe ulaşmak için günde ortalama <b>'+paceNeeded+'</b> gerekir — şu ana kadarki gerçek tempo: <b>'+paceActual+'/gün</b>. '+
    'Bu bir tahmindir, gerçek lot her işlemde kaydedilmediği için ortalama lot ('+t('avgLotNote')+') ile hesaplanır; garanti değildir.',
  avgLotNote:'lot aralığınızın ortalaması',
  trade_log_title:'📒 SİNYAL KAR/ZARAR TAKİBİ',
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
  ai_news_title:'🔍 AI NEWS RESEARCH',
  aiNewsHint:'Type a topic in the "AI Research News" box above (top of page) and click Research — the result will appear here.',
  aiNewsNoKey:'This needs an <code>ANTHROPIC_API_KEY</code> in Streamlit secrets (console.anthropic.com — paid, each query has a small cost).',
  aiNewsError:(diag)=>'Research failed. diag: '+diag,
  tightTpWarning:(pct)=>'⚠ Tight-target / wide-stop shape (matching the ratio observed in the video source): target is smaller than stop, so breakeven requires at least '+pct+'% real win rate. Even with a high-looking win rate, losses are bigger than wins — weigh this carefully.',
  teach_title:'🎓 MANUAL TEACHING (pattern memory)',
  teachHint:'Log a setup you saw (direction + conditions + outcome). If the same combination of conditions succeeds a few times, the system automatically adds it to its own strategy memory.',
  teachBuy:'BUY', teachSell:'SELL', teachSupport:'At Support', teachResistance:'At Resistance', teachNoZone:'No Zone',
  teachOversold:'RSI Oversold', teachNeutralRsi:'RSI Neutral', teachOverbought:'RSI Overbought',
  teachNoFib:'No Fib', teachFibShallow:'Fib 0-38.2', teachFibGolden:'Fib 50-61.8 (Golden)', teachFibDeep:'Fib 78.6+',
  teachSuccess:'✓ Succeeded', teachFail:'✗ Failed', teachAdd:'+ SAVE', teachShowLearned:'Learned',
  teachSaved:'Saved.', teachLearnedEmpty:'No learned pattern yet — once the same condition combination succeeds at least 3 times (at least 2x more than it fails), it will appear here.',
  teachLearnedTitle:(n)=>n+' learned pattern(s):',
  teachPatternDesc:(dir,zone,rsi,fib,pattern)=>(dir>0?'BUY':'SELL')+' · '+zone+' · '+rsi+' · '+fib+' · '+pattern,
  teachStrategyLabel:(desc)=>'Learned Pattern: '+desc,
  zoneSupport:'At Support', zoneResistance:'At Resistance', zoneNone:'No Zone',
  rsiOversold:'RSI Oversold', rsiNeutral:'RSI Neutral', rsiOverbought:'RSI Overbought',
  fibNone:'No Fib', fibShallow:'Fib 0-38.2', fibGolden:'Fib 50-61.8', fibDeep:'Fib 78.6+', patternNone:'No Candle',
  newsNoEvents:'No medium/high-impact scheduled news found for the coming days.', newsNoTemplate:'No ready-made scenario template for this data type — evaluate the raw numbers yourself.',
  newsSame:'Result matched expectations — no clear directional signal.',
  newsBeat:'beat', newsMiss:'missed', newsHigh:'HIGH', newsMed:'MEDIUM',
  ccyStrengthens:'strengthens', ccyWeakens:'weakens',
  xauPressureNote:' General tendency for XAU/USD: pressure (USD strong).', xauSupportNote:' General tendency for XAU/USD: support (USD weak).',
  xauPressureScenario:' → typically pressures XAU/USD.', xauSupportScenario:' → typically supports XAU/USD.',
  apiMissingBadge:'NO API', newsCountBadge:n=>n+' NEWS', defaultEventName:'Economic Data',
  ruleNfp:'Employment data', ruleUnrate:'Unemployment rate', ruleClaims:'Jobless claims', ruleCpi:'Inflation (CPI)',
  ruleJolts:'JOLTS Job Openings', ruleAdp:'ADP Employment Change', ruleChallenger:'Challenger Job Cuts',
  employmentFamilyNote:'📌 This is one of the broader "employment family" releases — JOLTS (job openings), ADP, NFP (payrolls), Jobless Claims, and the Unemployment Rate are all related and typically release a few days apart (e.g. JOLTS → Jobless Claims a few days later → NFP on the first Friday of the month). Markets tend to read these as a CUMULATIVE picture of labor-market strength/weakness rather than judging any single release in isolation — several consecutive weak/strong prints carry more weight than one data point.',
  ruleGdp:'GDP', ruleRetail:'Retail sales', rulePmi:'PMI', ruleRate:'Rate decision', ruleTrade:'Trade balance',
  noLiveFeedTitle:'● NO LIVE DATA', noLiveFeedDesc:'No Binance feed for this instrument — a TwelveData/OANDA API is required', noLiveShort:'no live data',
  goldOffsetLine:(sign,val)=>'PAXG proxy vs real spot gold gap: '+sign+val+'$ (factor this in when comparing to MT5/OANDA — the ticker price is already corrected, but chart S/R and entry levels are not yet corrected)',
  zoneTop:'Zone Top', zoneBottom:'Zone Bottom', srNearZone:'near consolidation/volume zone',
  mainResistance:'Main Resistance (1H)', mainSupport:'Main Support (1H)', srNearMainSupport:'near main support (1H)', srNearMainResistance:'near main resistance (1H)',
  tagEmaCross:'EMA Momentum Cross (9/21 + MACD/RSI)', tagOrb:'Opening Range Breakout (ORB)', tagMomentum:'Consecutive-Candle Momentum Breakout',
  tagLiquiditySweep:'Liquidity Sweep Reversal (200 EMA + VWAP Rejection)',
  tagRsiDivergence:'RSI Divergence', tagBollSqueeze:'Bollinger Squeeze Breakout',
  tagEmaPullback:'EMA21 Pullback (Trend Continuation)', tagInsideBar:'Inside Bar Breakout',
  tagFvgRetest:'Fair Value Gap Retest (ICT)', tagIfvg:'Inverse Fair Value Gap (ICT)', tagAmdCycle:'AMD Cycle (Accumulation-Manipulation-Distribution)',
  tagValuationZone:'Valuation Extreme + Zone Confluence', tagMacdZeroCross:'MACD Zero-Line Cross',
  tagScalpOrb:'ORB Scalp Variant (tight range)', tagNoWickRetest:'No Wick (Marubozu) Retest',
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
  psarUpLbl:'▲ UP', psarDownLbl:'▼ DOWN', trendUp:'uptrend', trendDown:'downtrend', trendFlat:'sideways',
  srNearSupport:l=>'near support ('+l+')', srNearResistance:l=>'near resistance ('+l+')',
  srNearDynSupport:'near dynamic support (Dyn Support)', srNearDynResistance:'near dynamic resistance (Dyn Resistance)',
  confluenceSuffix:' + Fib level confluence',
  conflictWarning:'⚠ MIXED SIGNAL: another strategy/analysis is giving a strong signal in the OPPOSITE direction from the winning candidate. We still show the best option, but opinion is split here — be careful.',
  conflictBadge:'⚠ MIXED SIGNAL — possible reversal zone',
  noLastSignal:'No signal has been given at this level yet.',
  lastSignalLine:(dir,entry,tp,time)=>'Last signal: <b>'+dir+'</b> · Entry '+entry+' → TP '+tp+' · '+time,
  risk_governor_title:'🛡 CHALLENGE RISK GOVERNOR', risk_balance:'Balance ($)', risk_daily:'Daily Loss Limit (%)',
  risk_max:'Max Total Loss (%)', risk_target:'Profit Target (%)',
  risk_lotmin:'Lot (min)', risk_lotmax:'Lot (max)', risk_days:'Target Days', risk_start:'Start Date',
  goal_progress_title:'🎯 PROGRESS TO TARGET (from real tracked results)',
  goalDetailLine:(net,target,pctDone,daysLeft,paceNeeded,paceActual)=>
    'Tracked net: <b>'+net+'</b> / $'+target+' target ('+pctDone+'%). Remaining: <b>'+daysLeft+' days</b>. '+
    'Reaching the target needs an average of <b>'+paceNeeded+'</b>/day — your actual tracked pace so far: <b>'+paceActual+'</b>/day. '+
    'This is an estimate — actual lot size isn\'t logged per trade, so it uses the average of your lot range ('+t('avgLotNote')+'); not a guarantee.',
  avgLotNote:'the average of your lot range',
  trade_log_title:'📒 SIGNAL P&L TRACKING',
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

function isMarketOpen(sym){
 if(sym==='BINANCE:BTCUSDT')return true;
 const d=new Date(),day=d.getUTCDay(),h=d.getUTCHours();
 if(sym==='OANDA:SPX500USD'){
   if(day===0||day===6)return false;
   const m=h*60+d.getUTCMinutes(); return m>=870 && m<=1260;
 }
 if(day===6)return false;
 if(day===0 && h<22)return false;
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
    return '<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 2px;border-bottom:1px solid var(--line);font-size:9px">'+
      '<div><b style="color:'+col+'">'+(win?t('tradeLogWin'):t('tradeLogLoss'))+' '+(tr.dir>0?'BUY':'SELL')+'</b> '+cfg.label+
      '<br><span style="color:var(--muted)">'+fmt(tr.entry)+' → '+fmt(hitPx)+' · '+fmtSigTime(tr.ts)+'</span></div>'+
      '<div style="color:'+col+';font-weight:700;white-space:nowrap">'+(tr.usd>=0?'+$':'-$')+Math.round(Math.abs(tr.usd)).toLocaleString('en-US')+'</div>'+
      '</div>';
  }).join('') + (trades.length>40?'<p style="font-size:8px;color:var(--muted);padding:4px 2px">+'+(trades.length-40)+'…</p>':'');
}

// ============ MANUEL ÖĞRETİM: KULLANICI KAYITLARINDAN GERÇEK KALIP ÇIKARIMI ============
// Bu "kara kutu" bir yapay zeka DEĞİLDİR — şeffaf bir kural türetme sistemidir: kullanıcı bir setup'ı
// (yön + gerçek, zaten hesaplanan koşullar: bölge/RSI durumu/Fib bölgesi/mum formasyonu) ve sonucunu
// (başarılı/başarısız) girer. AYNI koşul kombinasyonu yeterince (3+) başarılı olursa, sistem bunu
// gelecekte KENDİ bağımsız aday stratejisi olarak tanır (diğer 13 kalıp gibi).
const TEACH_KEY='valens_manual_teach';
function loadManualTeach(){ try{ const raw=localStorage.getItem(TEACH_KEY); return raw?JSON.parse(raw):[]; }catch(e){ return []; } }
function saveManualTeach(arr){ try{ localStorage.setItem(TEACH_KEY, JSON.stringify(arr)); }catch(e){} }
function comboKey(e){ return [e.dir,e.zone,e.rsi,e.fib,e.pattern].join('|'); }
function getLearnedPatterns(){
  const entries=loadManualTeach();
  const groups={};
  entries.forEach(e=>{
    const k=comboKey(e);
    if(!groups[k]) groups[k]={dir:e.dir, zone:e.zone, rsi:e.rsi, fib:e.fib, pattern:e.pattern, success:0, fail:0};
    if(e.outcome==='success') groups[k].success++; else groups[k].fail++;
  });
  return Object.values(groups).filter(g=>g.success>=3 && g.success>=g.fail*2);
}
function patternDescLabel(g){
  const zoneLbl={support:t('zoneSupport'),resistance:t('zoneResistance'),none:t('zoneNone')}[g.zone]||g.zone;
  const rsiLbl={oversold:t('rsiOversold'),neutral:t('rsiNeutral'),overbought:t('rsiOverbought')}[g.rsi]||g.rsi;
  const fibLbl={none:t('fibNone'),shallow:t('fibShallow'),golden:t('fibGolden'),deep:t('fibDeep')}[g.fib]||g.fib;
  const patLbl = g.pattern==='none' ? t('patternNone') : g.pattern;
  return t('teachPatternDesc')(g.dir, zoneLbl, rsiLbl, fibLbl, patLbl);
}
// Şu anki piyasa durumunu, öğretim formundakiyle AYNI kovalarla (bucket) etiketler — eşleştirme
// bu yüzden mekanik ve dürüsttür (metin ayrıştırma değil, aynı gerçek sayılardan gelir).
function currentConditionBuckets(rsi, cr){
  const rsiB = rsi<30?'oversold':rsi>70?'overbought':'neutral';
  const zoneB = (typeof cr.srBias==='number' && cr.srBias>0.3)?'support':(typeof cr.srBias==='number' && cr.srBias<-0.3)?'resistance':'none';
  const fibB = cr.fibZone || 'none';
  const patB = cr.patternName || 'none';
  return {rsi:rsiB, zone:zoneB, fib:fibB, pattern:patB};
}
function detectLearnedPatternMatches(rsi, cr){
  const learned=getLearnedPatterns();
  if(!learned.length) return [];
  const cur=currentConditionBuckets(rsi, cr);
  const matches=[];
  learned.forEach((g,idx)=>{
    if(g.zone===cur.zone && g.rsi===cur.rsi && g.fib===cur.fib && g.pattern===cur.pattern && (g.zone!=='none'||g.rsi!=='neutral'||g.fib!=='none'||g.pattern!=='none')){
      matches.push({key:'learned_'+idx, dir:g.dir, label:t('teachStrategyLabel')(patternDescLabel(g)), successRate:g.success/(g.success+g.fail)});
    }
  });
  return matches;
}
function updateTeachUI(){
  const badge=document.getElementById('teachBadge');
  if(badge) badge.textContent=getLearnedPatterns().length+'';
}
function renderLearnedPatternsBox(){
  const box=document.getElementById('learnedPatternsBox'); if(!box) return;
  const learned=getLearnedPatterns();
  if(!learned.length){ box.innerHTML='<p style="color:var(--muted);padding:6px 0">'+t('teachLearnedEmpty')+'</p>'; return; }
  let html='<p style="color:var(--gold);padding:4px 0">'+t('teachLearnedTitle')(learned.length)+'</p>';
  learned.forEach(g=>{
   html+='<div style="padding:4px 0;border-bottom:1px solid var(--line);color:var(--text)">'+
    (g.dir>0?'<span style="color:var(--green)">▲</span>':'<span style="color:var(--red)">▼</span>')+' '+patternDescLabel(g)+
    ' <span style="color:var(--muted)">('+g.success+'✓/'+g.fail+'✗)</span></div>';
  });
  box.innerHTML=html;
}
(function wireTeachForm(){
 const addBtn=document.getElementById('tAdd'), showBtn=document.getElementById('tShowLearned');
 if(!addBtn) return;
 addBtn.addEventListener('click', ()=>{
  const entry={
   dir: parseInt(document.getElementById('tDir').value,10),
   zone: document.getElementById('tZone').value,
   rsi: document.getElementById('tRsi').value,
   fib: document.getElementById('tFib').value,
   pattern: document.getElementById('tPattern').value,
   outcome: document.getElementById('tOutcome').value,
   note: document.getElementById('tNote').value||'',
   ts: Date.now(), sym: CUR
  };
  const arr=loadManualTeach(); arr.push(entry); saveManualTeach(arr);
  document.getElementById('tNote').value='';
  updateTeachUI(); renderLearnedPatternsBox();
  alert(t('teachSaved'));
 });
 if(showBtn) showBtn.addEventListener('click', ()=>{
  const box=document.getElementById('learnedPatternsBox');
  const showing = box.style.display!=='none';
  box.style.display = showing?'none':'block';
  if(!showing) renderLearnedPatternsBox();
 });
 updateTeachUI();
})();

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
  fvgRetest:t('tagFvgRetest'), ifvg:t('tagIfvg'), amdCycle:t('tagAmdCycle'), valuationZone:t('tagValuationZone'), macdZeroCross:t('tagMacdZeroCross'),
  scalpOrb:t('tagScalpOrb'), noWickRetest:t('tagNoWickRetest')};

 // ---- HER STRATEJİYİ BAĞIMSIZ BİR ADAY OLARAK DEĞERLENDİR ("bütün ihtimalleri test et, en uygununu ver") ----
 // Önceki tasarım: 23 şeyin TEK harmanlanmış skoruna bakılıyordu — güçlü ama tek bir kalıp (ör. temiz bir
 // likidite süpürmesi), ilgisiz bir gösterge (CCI, ADX vb.) katılmadığı için boğulabiliyordu. Şimdi: HER
 // strateji kendi tam koşulunu (kendi iç mantığında zaten TÜM şartları AND ile) sağladığında bağımsız bir
 // "aday" olur, kendi temel güvenine sahiptir; diğer göstergeler de aynı yöndeyse ek güven puanı alır.
 // O an en güçlü/en tam aday NİHAİ karar olur — genel bir "23'ün X'i aynı yönde olsun" şartı YOK artık.
 const STRATEGY_BASE_CONF={emaCross:72, orb:70, momentum:70, liquiditySweep:82, rsiDivergence:78, bollSqueeze:75, emaPullback:74, insideBar:68,
  fvgRetest:76, ifvg:77, amdCycle:85, valuationZone:73, macdZeroCross:66,
  scalpOrb:68, noWickRetest:75};
 function confirmBoost(dir){
  const agreeing=Object.keys(votes).filter(k=>votes[k]===dir).length;
  return Math.round((agreeing/totalBaseVotes)*25); // diğer 15 gösterge de aynı yöndeyse +0..+25 ek güven
 }
 let candidates=[];
 if(confluenceDir!==0){
  candidates.push({key:'confluence', dir:confluenceDir, confidence:confluenceConf, label:t('candidateConfluence')});
 }
 (cr.strategyTags||[]).forEach(tag=>{
  const base=STRATEGY_BASE_CONF[tag.key]||70;
  const confidence=Math.min(97, base+confirmBoost(tag.dir));
  candidates.push({key:tag.key, dir:tag.dir, confidence, label:tagLabels[tag.key]});
 });
 // Kullanıcının manuel öğrettiği ve yeterince (3+, başarısızlığın 2 katı) başarılı olmuş kalıplar —
 // güven, o kalıbın GERÇEK izlenen başarı oranına göre ölçeklenir (uydurma değil).
 (typeof detectLearnedPatternMatches==='function' ? detectLearnedPatternMatches(rsi, cr) : []).forEach(m=>{
  const confidence=Math.min(97, Math.round(65 + m.successRate*30 + confirmBoost(m.dir)*0.5));
  candidates.push({key:m.key, dir:m.dir, confidence, label:m.label});
 });

 let best=null;
 candidates.forEach(c=>{ if(!best || c.confidence>best.confidence) best=c; });

 const rawDir = best ? best.dir : 0;
 const conf = best ? best.confidence : 50;
 const THRESHOLD=87;

 // Şeffaflık: kazanan adayın TERS yönünde, ona yakın güvende başka bir aday varsa "karışık" işaretle —
 // ama yine de EN İYİ seçeneği veriyoruz, sadece bunun tartışmalı olabileceğini açıkça belirtiyoruz.
 const opposing = best ? candidates.filter(c=>c.dir===-best.dir && c.confidence>=(best.confidence-15)) : [];
 const conflicted = best!==null && opposing.length>0;

 const agreeCount = best ? candidates.filter(c=>c.dir===best.dir).length : 0;
 const totalVotes = candidates.length;
 const technicallyArmed = best!==null && conf>=THRESHOLD;
 const riskBlocked = isRiskBlocked();
 const armed = technicallyArmed && !riskBlocked;

 let sigText='◇ GÖZLEM', sigColor='var(--gold)';
 if(rawDir>0)sigText='▲ BUY'; else if(rawDir<0)sigText='▼ SELL';
 if(armed){sigText=rawDir>0?'▲ BUY':'▼ SELL';sigColor=rawDir>0?'var(--green)':'var(--red)';}

 const sigWhyEl=document.getElementById('sigWhy');
 if(sigWhyEl){
  let whyHtml = best ? t('winningCandidateLine')(best.label, conf) : t('noCandidateLine');
  if(conflicted) whyHtml += ' <span style="color:#ffb27a">'+t('conflictWarning')+'</span>';
  sigWhyEl.innerHTML = whyHtml;
 }

 const tagEl=document.getElementById('strategyTagLine');
 if(tagEl){
  if(candidates.length){
   const parts=candidates.slice().sort((a,b)=>b.confidence-a.confidence).map(c=>
    (c===best?'<b style="color:'+(c.dir>0?'var(--green)':'var(--red)')+'">':'')+c.label+' ('+c.confidence+'%)'+(c===best?'</b>':'')
   );
   tagEl.style.display='block'; tagEl.innerHTML=t('strategyTagPrefix')+parts.join(' · ');
  } else { tagEl.style.display='none'; tagEl.textContent=''; }
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
   if(winDir===0) return '<span style="color:var(--muted)">'+t('catNoVerdictYet')+'</span>';
   if(total===0) return '<span style="color:var(--muted)">'+t('catNoData')+'</span>';
   if(agree===total) return '<span style="color:var(--green)">✓ '+t('catFull')+'</span>';
   if(agree===0) return '<span style="color:var(--red)">✗ '+t('catNone')+'</span>';
   return '<span style="color:var(--gold)">◐ '+t('catPartial')+' ('+agree+'/'+total+')</span>';
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
   const scSL = atr ? (isTightTpOrb?atr*1.6:atr*1.0) : cfg.scSL;
   const scTP = atr ? (isTightTpOrb?atr*0.5:atr*2.0) : cfg.scTP;
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
   const scDist=Math.abs(scTpPx-scEntryPx), swDist=Math.abs(swTpPx-last);
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

   logArmedTrade(CUR, rawDir, scEntryPx, scTpPx, scStopPx);
   recordLastSignal(CUR,'scalp',rawDir,scEntryPx,scTpPx,scStopPx);
   recordLastSignal(CUR,'swing',rawDir,last,swTpPx,swStopPx);
 }else{
   ['scEntry','scStop','scTp','swEntry','swStop','swTp'].forEach(id=>document.getElementById(id).textContent='—');
   scStatusEl.className='trade-status wait';
   scStatusEl.textContent = (technicallyArmed && riskBlocked) ? t('riskBlockedStatus') : t('waitStatus')(THRESHOLD,conf);
   alertBox.classList.remove('show');
 }

 updateTradeOutcomes(CUR, last);
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
// XAU/USD grafiğimiz Binance'ın PAXG (tokenize altın) proxy'sinden geliyor — bu, gerçek MT5/OANDA spot
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
   btn.querySelector('strong').textContent=px.toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec});
   const pctEl=btn.querySelector('small.up, small.down')||btn.querySelector('small:last-child');
   if(pctEl){
    pctEl.className=pct>=0?'up':'down';
    pctEl.textContent=(pct>=0?'▲ +':'▼ ')+pct.toFixed(2)+'%';
   }
  }catch(e){ /* tek bir sembolün geçici hatası tüm şeridi bozmasın */ }
 }
}
updateGoldOffset().then(updateTickerBar);
setInterval(updateGoldOffset, 45000); // xaus.com adil kullanım kuralı: en az 30sn — 45sn kullanıyoruz
setInterval(updateTickerBar, 15000);

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
 if(window.valensRenderAiNews) window.valensRenderAiNews();
 updateTeachUI(); renderLearnedPatternsBox();
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
   dEl.textContent=c.date;
   const fundNet=c.fund_long-c.fund_short, bankNet=c.bank_long-c.bank_short;
   body.innerHTML=
    '<p><b>'+c.market+'</b> · OI: '+fmt(c.oi)+'</p>'+
    '<div class="scenario '+(fundNet>=0?'bull':'bear')+'"><b>'+(fundNet>=0?'▲':'▼')+' '+t('cotHedgeFunds')+':</b> '+
      (fundNet>=0?t('cotNetLong'):t('cotNetShort'))+' '+fmt(Math.abs(fundNet))+
      '<br>'+t('cotLong')+' '+fmt(c.fund_long)+' ('+chg(c.fund_dlong)+') · '+t('cotShort')+' '+fmt(c.fund_short)+' ('+chg(c.fund_dshort)+')</div>'+
    '<div class="scenario '+(bankNet>=0?'bull':'bear')+'"><b>'+(bankNet>=0?'▲':'▼')+' '+t('cotBanks')+':</b> '+
      (bankNet>=0?t('cotNetLong'):t('cotNetShort'))+' '+fmt(Math.abs(bankNet))+
      '<br>'+t('cotLong')+' '+fmt(c.bank_long)+' · '+t('cotShort')+' '+fmt(c.bank_short)+'</div>'+
    '<p style="font-size:8px;color:var(--muted);margin-top:5px">'+t('cotSourceNote')+'</p>';
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
/* ============ AI HABER ARAŞTIRMASI GÖRÜNTÜLEME ============ */
(function(){
 const AINEWS = __AI_NEWS_DATA__; // {available, text, topic, reason, diag}
 function renderAiNews(){
  const box=document.getElementById('aiNewsPanel'), badge=document.getElementById('aiNewsBadge');
  if(!box||!badge) return;
  if(!AINEWS || !AINEWS.topic){ badge.textContent='—'; box.innerHTML='<p style="color:var(--muted);font-size:10px">'+t('aiNewsHint')+'</p>'; return; }
  if(!AINEWS.available){
   badge.textContent=t('apiMissingBadge');
   const msg = AINEWS.reason==='no_key' ? t('aiNewsNoKey') : t('aiNewsError')(AINEWS.diag||AINEWS.reason||'');
   box.innerHTML='<p style="color:var(--muted);font-size:10px;line-height:1.6"><b>'+(AINEWS.topic||'')+'</b></p><p style="color:var(--muted);font-size:10px;line-height:1.6">'+msg+'</p>';
   return;
  }
  badge.textContent='✓';
  const bodyHtml=(AINEWS.text||'').replace(/\n/g,'<br>');
  box.innerHTML='<p style="color:var(--gold);font-size:10px;font-weight:700;margin-bottom:5px">'+AINEWS.topic+'</p><div style="color:var(--text);font-size:10px;line-height:1.6">'+bodyHtml+'</div>';
 }
 window.valensRenderAiNews=renderAiNews;
 renderAiNews();
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
 const INTERVAL_MAP={'15':'15m','30':'30m','60':'1h','240':'4h','D':'1d'};
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
 const resize=()=>chart.applyOptions({width:el.clientWidth,height:el.clientHeight});
 window.addEventListener('resize',resize); setTimeout(resize,150);

 let ohlc=[],ws=null,tradeWs=null,binSym=null,curSym=null,srLines=[],fibLines=[],dynSup,dynRes,patternMarkers=[],zoneLines=[];
 // "Ana destek/direnç" HER ZAMAN 1 saatlik mumlardan hesaplanır (kullanıcı hangi zaman dilimini
 // izlerse izlesin) — "scalp" destek/direnç ise o an izlenen aralığın kendi dinamik S/R'ıdır.
 let mainSR={sup:null,res:null}, mainSRLines=[];
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
 // ---- FAIR VALUE GAP (FVG) — ICT tanımı: 3 mumluk yapı, 1. mumun high/low'u ile 3. mumun low/high'ı
 // arasında boşluk (2. mum "displacement/güçlü hareket" mumu). Fiyat bu boşluğa geri dönüp (retest)
 // tepki verirse (dolmadan reddedilirse) bu klasik bir giriş noktasıdır. ----
 function findFVGs(a, lookback){
  const w=a.slice(-lookback-2,-1); let fvgs=[];
  for(let i=1;i<w.length-1;i++){
   const c1=w[i-1], c3=w[i+1];
   if(c1.high<c3.low) fvgs.push({dir:1, top:c3.low, bottom:c1.high});
   else if(c1.low>c3.high) fvgs.push({dir:-1, top:c1.low, bottom:c3.high});
  }
  return fvgs;
 }
 function detectFVGRetest(a){
  if(a.length<25) return null;
  const fvgs=findFVGs(a,20), curr=a[a.length-1];
  for(let i=fvgs.length-1;i>=0;i--){
   const f=fvgs[i];
   if(f.dir>0 && curr.low<=f.top && curr.close>f.bottom && curr.close>curr.open) return {key:'fvgRetest', dir:1};
   if(f.dir<0 && curr.high>=f.bottom && curr.close<f.top && curr.close<curr.open) return {key:'fvgRetest', dir:-1};
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
  return tags;
 }
 function drawSRLines(){
  srLines.forEach(l=>cs.removePriceLine(l)); srLines=[];
  const cfg=SYMS[curSym]; if(!cfg) return;
  cfg.sr.forEach(s=>{
   const px=(s.lo+s.hi)/2, isRes=s.type==='r';
   srLines.push(cs.createPriceLine({price:px,color:isRes?'#ff506d':'#00c896',lineWidth:2,lineStyle:0,axisLabelVisible:true,title:s.label}));
  });
 }
 // ---- ANA DESTEK/DİRENÇ: her zaman 1 saatlik mumlardan, o an izlenen zaman diliminden BAĞIMSIZ ----
 // "Ana destek direnç noktaları 1 saatlikten alınıyor" — kullanıcı 15dk'da bakarken bile bu arka planda
 // 1 saatlik veriden hesaplanır ve grafiğe kalın turuncu çizgilerle işaretlenir.
 async function fetchMainSR(sym){
  const bs=MAP[sym]; if(!bs){ mainSR={sup:null,res:null}; return; }
  try{
   const r=await fetch(`https://api.binance.com/api/v3/klines?symbol=${bs}&interval=1h&limit=100`);
   const d=await r.json();
   if(!Array.isArray(d)||!d.length) return;
   const highs=d.map(k=>+k[2]), lows=d.map(k=>+k[3]);
   mainSR={sup:Math.min(...lows), res:Math.max(...highs)};
   if(sym===curSym) drawMainSRLines();
  }catch(e){ /* sessizce yoksay — bu ikincil bir veri kaynağı, ana grafiği bozmasın */ }
 }
 function drawMainSRLines(){
  mainSRLines.forEach(l=>cs.removePriceLine(l)); mainSRLines=[];
  if(mainSR.sup==null||mainSR.res==null) return;
  mainSRLines.push(cs.createPriceLine({price:mainSR.res,color:'#ff8c42',lineWidth:2,lineStyle:0,axisLabelVisible:true,title:t('mainResistance')}));
  mainSRLines.push(cs.createPriceLine({price:mainSR.sup,color:'#ff8c42',lineWidth:2,lineStyle:0,axisLabelVisible:true,title:t('mainSupport')}));
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
 // ---- ATR bazlı volatilite zarfı (EMA20 ± ATR14*2) — TradingView ekranınızdaki renkli "volatilite bulutu"
 // konseptinin genel/klasik karşılığı (Keltner Channel). Trend yönüne göre renk değiştirir. ----
 function drawVolatilityBand(){
  if(ohlc.length<25){ kelUp.setData([]); kelLo.setData([]); return; }
  const closes=ohlc.map(c=>c.close), period=20, mult=2, k=2/(period+1);
  let ema=closes[0]; const emaSeries=[];
  closes.forEach((c,i)=>{ ema = i? c*k+ema*(1-k) : c; emaSeries.push(ema); });
  let trs=[0];
  for(let i=1;i<ohlc.length;i++){
   const cur=ohlc[i], prev=ohlc[i-1];
   trs.push(Math.max(cur.high-cur.low,Math.abs(cur.high-prev.close),Math.abs(cur.low-prev.close)));
  }
  const up=[], lo=[];
  for(let i=0;i<ohlc.length;i++){
   const start=Math.max(0,i-13), slice=trs.slice(start,i+1);
   const atr=slice.reduce((a,b)=>a+b,0)/slice.length;
   up.push({time:ohlc[i].time,value:+(emaSeries[i]+atr*mult).toFixed(4)});
   lo.push({time:ohlc[i].time,value:+(emaSeries[i]-atr*mult).toFixed(4)});
  }
  const bullish = closes[closes.length-1] >= emaSeries[emaSeries.length-1];
  const col = bullish ? 'rgba(0,200,150,.55)' : 'rgba(255,80,109,.55)';
  kelUp.applyOptions({color:col}); kelLo.applyOptions({color:col});
  kelUp.setData(up); kelLo.setData(lo);
 }
 // ---- Konsolidasyon / hacim birikim bölgesi tespiti — TradingView ekranınızdaki teal kutular gibi
 // dar-aralıklı, sıkışık fiyat pencerelerini gerçek OHLC'den bulur; bunlar geleceğe dönük S/R adayı olur. ----
 function detectConsolidationZones(){
  if(ohlc.length<40) return [];
  const N=6, atrRef=calcATR(ohlc,14)||( (ohlc[ohlc.length-1].high-ohlc[ohlc.length-1].low)||1 );
  let raw=[];
  for(let i=N;i<ohlc.length;i++){
   const w=ohlc.slice(i-N,i);
   const hi=Math.max(...w.map(c=>c.high)), lo=Math.min(...w.map(c=>c.low));
   if((hi-lo) < atrRef*1.2) raw.push({startIdx:i-N, endIdx:i-1, hi, lo});
  }
  let merged=[];
  raw.forEach(z=>{
   const last=merged[merged.length-1];
   if(last && z.startIdx<=last.endIdx+1){ last.endIdx=Math.max(last.endIdx,z.endIdx); last.hi=Math.max(last.hi,z.hi); last.lo=Math.min(last.lo,z.lo); }
   else merged.push(Object.assign({},z));
  });
  return merged.filter(z=>(z.endIdx-z.startIdx)>=N-1).slice(-6);
 }
 function drawZoneLines(){
  zoneLines.forEach(l=>cs.removePriceLine(l)); zoneLines=[];
  const zones=detectConsolidationZones();
  const last=ohlc[ohlc.length-1]?ohlc[ohlc.length-1].close:0;
  // sadece fiyata en yakın 2 bölgeyi çiz (grafik kirlenmesin)
  zones.map(z=>({z,dist:Math.min(Math.abs(last-z.hi),Math.abs(last-z.lo))})).sort((a,b)=>a.dist-b.dist).slice(0,2).forEach(({z})=>{
   zoneLines.push(cs.createPriceLine({price:z.hi,color:'rgba(20,184,166,.85)',lineWidth:1,lineStyle:3,axisLabelVisible:true,title:t('zoneTop')}));
   zoneLines.push(cs.createPriceLine({price:z.lo,color:'rgba(20,184,166,.85)',lineWidth:1,lineStyle:3,axisLabelVisible:true,title:t('zoneBottom')}));
  });
  return zones;
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
  drawVolatilityBand();
  const zones=drawZoneLines();
  const pat=pattern(ohlc);
  const lastTime=ohlc[ohlc.length-1].time;
  // Formasyon işaretleri KALICI: tespit edilen her mum formasyonu grafikte kalır, sadece o an
  // oluşmakta olan SON mumun girdisi (henüz mum kapanmadığı için) canlı güncellenir/kaldırılır.
  patternMarkers = patternMarkers.filter(m=>m.time!==lastTime);
  if(pat&&pat.d!=='neutral'){
   patternMarkers.push({time:lastTime, position:pat.d==='bull'?'belowBar':'aboveBar',
    color:pat.d==='bull'?'#00c896':'#ff506d', shape:pat.d==='bull'?'arrowUp':'arrowDown', text:pat.n});
  }
  if(patternMarkers.length>300) patternMarkers=patternMarkers.slice(-300); // makul bir üst sınır
  patternMarkers.sort((a,b)=>a.time-b.time); // lightweight-charts zaman sırası ister
  cs.setMarkers(patternMarkers);

  const last=ohlc[ohlc.length-1].close;
  const closes=ohlc.map(c=>c.close);
  const w=ohlc.slice(-60); let sx=0,sy=0,sxy=0,sxx=0;
  w.forEach((c,i)=>{sx+=i;sy+=c.close;sxy+=i*c.close;sxx+=i*i;});
  const slope=(w.length*sxy-sx*sy)/(w.length*sxx-sx*sx);
  const cfg=SYMS[curSym]; let srBias=0, srText='';
  if(cfg){cfg.sr.forEach(s=>{const mid=(s.lo+s.hi)/2,dist=Math.abs(last-mid)/last;
    if(dist<0.004){ if(s.type==='s'){srBias=0.5;srText=t('srNearSupport')(s.label);}
                    else{srBias=-0.5;srText=t('srNearResistance')(s.label);} }});}
  // ANA destek/direnç (1 saatlik, o an izlenen zaman diliminden BAĞIMSIZ) — en yüksek öncelikli S/R
  // kaynağıdır ("ana destek direnç noktaları 1 saatlikten alınıyor"). Şu an izlenen aralığın kendi
  // dinamik S/R'ı ("scalp" S/R) aşağıda ayrıca hesaba katılır, ama ana 1H seviyesi öncelik kazanır.
  if(mainSR && mainSR.sup!=null && mainSR.res!=null){
    const distMainSup=Math.abs(last-mainSR.sup)/last, distMainRes=Math.abs(last-mainSR.res)/last;
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
  const stochReal=calcStoch(ohlc,14);
  const adxReal=calcADXReal(ohlc,14);
  const atrReal=calcATR(ohlc,14);
  const vwapReal=calcVWAP(ohlc,96);
  const wrReal=calcWilliamsR(ohlc,14);
  const cciReal=calcCCI(ohlc,20);
  const psarReal=calcPSAR(ohlc);
  const pivotsReal=calcPivots(ohlc);
  const strategyTags=detectStrategyTags(ohlc, {rsi:rsiReal, macd:macdReal, ema9:ema9Real, ema21:ema21Real, ema200:ema200Real, vwap:vwapReal, zones:zones, bollPct:bollPctReal!==null?bollPctReal:50, srBias:srBias});

  window.valensChartRead={
    trend: slope>0?1:slope<0?-1:0,
    pattern: pat?(pat.d==='bull'?1:pat.d==='bear'?-1:0):0,
    patternName: pat?pat.n:'',
    srBias, srText, fibBias, fibZone, strategyTags,
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
 async function loadHistory(){
  const intv=currentBinInterval();
  // Önce önbellekten (varsa) anında göster — kullanıcı sayfayı her açtığında boş grafik görmesin
  const cached=loadOhlcCache(curSym,intv);
  if(cached && cached.length){ ohlc=cached; cs.setData(ohlc); chart.timeScale().fitContent(); analyze(); }
  try{
   // Binance REST API'de tek istekte alınabilecek azami mum sayısı 1000'dir — önceki 200 limiti
   // gereksiz yere veriyi kısıtlıyordu (15dk'da sadece ~50 saat; 1000 ile ~10 gün).
   const r=await fetch(`https://api.binance.com/api/v3/klines?symbol=${binSym}&interval=${intv}&limit=1000`);
   const d=await r.json();
   if(!Array.isArray(d))throw new Error('no data');
   ohlc=d.map(k=>({time:k[0]/1000,open:+k[1],high:+k[2],low:+k[3],close:+k[4],volume:+k[5]}));
   cs.setData(ohlc); chart.timeScale().fitContent(); analyze();
   saveOhlcCache(curSym,intv,ohlc);
  }catch(e){console.error('history err',e);}
 }
 function connect(){
  if(ws){ws.close();ws=null;}
  const intv=currentBinInterval();
  ws=new WebSocket(`wss://stream.binance.com:9443/ws/${binSym.toLowerCase()}@kline_${intv}`);
  ws.onmessage=ev=>{
   const k=JSON.parse(ev.data).k;
   const bar={time:k.t/1000,open:+k.o,high:+k.h,low:+k.l,close:+k.c,volume:+k.v};
   const last=ohlc[ohlc.length-1];
   if(last&&last.time===bar.time)ohlc[ohlc.length-1]=bar; else{ohlc.push(bar);if(ohlc.length>1000)ohlc.shift();}
   cs.update(bar); analyze();
   if(k.x) saveOhlcCache(curSym,intv,ohlc); // sadece mum KAPANDIĞINDA önbelleği güncelle (her tick'te yazmaya gerek yok)
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
  kelUp.setData([]); kelLo.setData([]);
  patternMarkers=[]; // farklı enstrümana geçince eski sembolün formasyon geçmişini taşıma
  e20.setData([]); e50.setData([]);
  srLines.forEach(l=>cs.removePriceLine(l)); srLines=[];
  fibLines.forEach(l=>cs.removePriceLine(l)); fibLines=[];
  zoneLines.forEach(l=>cs.removePriceLine(l)); zoneLines=[];
  mainSRLines.forEach(l=>cs.removePriceLine(l)); mainSRLines=[]; mainSR={sup:null,res:null};
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
  fetchMainSR(sym);
  loadHistory().then(()=>{
    drawSRLines(); connect(); connectTrades();
    // ---- EKSENİ YENİ FİYATA OTURT ----
    chart.priceScale('right').applyOptions({autoScale:true});
    chart.timeScale().fitContent();
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
  e20.setData([]); e50.setData([]);
  srLines.forEach(l=>cs.removePriceLine(l)); srLines=[];
  fibLines.forEach(l=>cs.removePriceLine(l)); fibLines=[];
  zoneLines.forEach(l=>cs.removePriceLine(l)); zoneLines=[];
  if(dynSup){cs.removePriceLine(dynSup);dynSup=null;}
  if(dynRes){cs.removePriceLine(dynRes);dynRes=null;}
  ohlc=[]; cs.setData([]);
  window.valensChartRead={};
  loadHistory().then(()=>{
   drawSRLines(); connect(); connectTrades();
   chart.priceScale('right').applyOptions({autoScale:true});
   chart.timeScale().fitContent();
  });
 };
 window.valensSetSymbol(CUR);
})();
</script>
</body>
</html>
"""

TERMINAL_HTML = TERMINAL_HTML.replace("__COT_DATA__", COT_JSON).replace("__ECON_DATA__", ECON_JSON).replace("__AI_NEWS_DATA__", AI_NEWS_JSON)
components.html(TERMINAL_HTML, height=1550, scrolling=True)
