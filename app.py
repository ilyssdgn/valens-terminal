"""
VALENS WEALTH - Advanced Signal Bot
TradingView gerçek veri + 38+ mum formasyonu + çoklu indikatör analizi
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import time
import warnings
warnings.filterwarnings('ignore')

# ──────────────────────────────────────────────
# BAĞIMLILIK KONTROL
# ──────────────────────────────────────────────
try:
    from tvDatafeed import TvDatafeed, Interval
    TV_OK = True
except ImportError:
    TV_OK = False
    print("[UYARI] tvdatafeed yüklü değil → pip install tvDatafeed")

try:
    import talib
    TALIB_OK = True
except ImportError:
    TALIB_OK = False
    print("[UYARI] TA-Lib yüklü değil → pip install TA-Lib  (Windows: wheel'den kur)")

try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False

# ──────────────────────────────────────────────
# AYARLAR
# ──────────────────────────────────────────────
SYMBOL       = "XAUUSD"
EXCHANGE     = "OANDA"
TIMEFRAME    = Interval.in_1_hour   # 1 saatlik ana TF
CANDLES      = 300                  # kaç mum çek
LOOP_SEC     = 60                   # kaç saniyede bir güncelle (saniye)

# Sinyal eşikleri
CONF_MIN     = 60    # min güven skoru (%)
RSI_OB       = 70    # aşırı alım
RSI_OS       = 30    # aşırı satım
ATR_MULT_SL  = 1.5   # stop-loss ATR çarpanı
ATR_MULT_TP  = 2.5   # take-profit ATR çarpanı

# Altın piyasa saatleri – Pazar 23:00 → Cuma 22:00 UTC
GOLD_OPEN_DOW  = 6   # Pazar (0=Pazartesi … 6=Pazar)
GOLD_CLOSE_DOW = 4   # Cuma
GOLD_OPEN_H    = 23  # Pazar 23:00 UTC
GOLD_CLOSE_H   = 22  # Cuma 22:00 UTC

# ──────────────────────────────────────────────
# PİYASA SAATLERİ
# ──────────────────────────────────────────────
def is_market_open() -> bool:
    """XAU/USD piyasası açık mı? (Pazar 23:00 UTC – Cuma 22:00 UTC)"""
    now = datetime.utcnow()
    dow = now.weekday()   # 0=Pzt … 6=Paz
    h   = now.hour

    # Cumartesi → kapalı
    if dow == 5:
        return False
    # Pazar → sadece 23:00+ açık
    if dow == 6:
        return h >= GOLD_OPEN_H
    # Cuma → sadece 22:00 öncesi açık
    if dow == GOLD_CLOSE_DOW:
        return h < GOLD_CLOSE_H
    # Pzt–Per → açık
    return True

def market_status() -> str:
    now = datetime.utcnow()
    if is_market_open():
        return f"✅ PİYASA AÇIK  [{now.strftime('%a %H:%M UTC')}]"
    return f"🔴 PİYASA KAPALI [{now.strftime('%a %H:%M UTC')}]"

# ──────────────────────────────────────────────
# VERİ ÇEKİMİ
# ──────────────────────────────────────────────
def fetch_data() -> pd.DataFrame:
    """TradingView'dan gerçek veri; yedek olarak yfinance."""
    if TV_OK:
        try:
            tv  = TvDatafeed()
            raw = tv.get_hist(SYMBOL, EXCHANGE, interval=TIMEFRAME, n_bars=CANDLES)
            if raw is not None and len(raw) > 50:
                raw = raw.rename(columns=str.lower)
                raw.index = pd.to_datetime(raw.index)
                return raw[["open","high","low","close","volume"]].dropna()
        except Exception as e:
            print(f"[TradingView hata] {e}")

    if YF_OK:
        try:
            raw = yf.download("GC=F", period="30d", interval="1h", progress=False)
            raw.columns = [c[0].lower() for c in raw.columns]
            return raw[["open","high","low","close","volume"]].dropna()
        except Exception as e:
            print(f"[yfinance hata] {e}")

    raise RuntimeError("Veri kaynağı yok! tvDatafeed veya yfinance kur.")

# ──────────────────────────────────────────────
# İNDİKATÖRLER
# ──────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    v = df["volume"].values.astype(float)

    # EMA
    df["ema9"]  = _ema(c, 9)
    df["ema21"] = _ema(c, 21)
    df["ema50"] = _ema(c, 50)
    df["ema200"]= _ema(c, 200)

    # RSI
    df["rsi"] = _rsi(c, 14)

    # MACD
    df["macd"], df["macd_sig"], df["macd_hist"] = _macd(c)

    # Bollinger Bands
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = _bbands(c, 20, 2)

    # ATR
    df["atr"] = _atr(h, l, c, 14)

    # Stochastic
    df["stoch_k"], df["stoch_d"] = _stoch(h, l, c)

    # Volume ortalaması
    df["vol_ma"] = pd.Series(v).rolling(20).mean().values
    df["vol_ratio"] = v / (df["vol_ma"] + 1e-9)

    # ADX
    df["adx"] = _adx(h, l, c, 14)

    # Destek / Direnç seviyeleri
    df["support"]    = _swing_low(l, 10)
    df["resistance"] = _swing_high(h, 10)

    return df

# ──────────────────────────────────────────────
# SADE HESAPLAMALAR (TA-Lib yoksa kullan)
# ──────────────────────────────────────────────
def _ema(c, n):
    s = pd.Series(c)
    return s.ewm(span=n, adjust=False).mean().values

def _rsi(c, n=14):
    s  = pd.Series(c)
    d  = s.diff()
    g  = d.clip(lower=0).rolling(n).mean()
    ls = (-d.clip(upper=0)).rolling(n).mean()
    rs = g / (ls + 1e-9)
    return (100 - 100 / (1 + rs)).values

def _macd(c, fast=12, slow=26, sig=9):
    s    = pd.Series(c)
    fast_e = s.ewm(span=fast, adjust=False).mean()
    slow_e = s.ewm(span=slow, adjust=False).mean()
    macd   = fast_e - slow_e
    signal = macd.ewm(span=sig, adjust=False).mean()
    hist   = macd - signal
    return macd.values, signal.values, hist.values

def _bbands(c, n=20, k=2):
    s   = pd.Series(c)
    mid = s.rolling(n).mean()
    std = s.rolling(n).std()
    return (mid + k*std).values, mid.values, (mid - k*std).values

def _atr(h, l, c, n=14):
    hl  = pd.Series(h) - pd.Series(l)
    hpc = (pd.Series(h) - pd.Series(c).shift()).abs()
    lpc = (pd.Series(l) - pd.Series(c).shift()).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.rolling(n).mean().values

def _stoch(h, l, c, k=14, d=3):
    hh = pd.Series(h).rolling(k).max()
    ll = pd.Series(l).rolling(k).min()
    ks = 100 * (pd.Series(c) - ll) / (hh - ll + 1e-9)
    ds = ks.rolling(d).mean()
    return ks.values, ds.values

def _adx(h, l, c, n=14):
    plus_dm  = pd.Series(h).diff().clip(lower=0)
    minus_dm = (-pd.Series(l).diff()).clip(lower=0)
    mask = plus_dm < minus_dm
    plus_dm[mask] = 0
    mask2 = minus_dm <= plus_dm
    minus_dm[mask2] = 0
    atr = pd.Series(_atr(h, l, c, n))
    plus_di  = 100 * plus_dm.rolling(n).mean()  / (atr + 1e-9)
    minus_di = 100 * minus_dm.rolling(n).mean() / (atr + 1e-9)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    return dx.rolling(n).mean().values

def _swing_low(l, n=10):
    s   = pd.Series(l)
    rol = s.rolling(n*2+1, center=True).min()
    out = np.where(s == rol, s, np.nan)
    return pd.Series(out).fillna(method="ffill").values

def _swing_high(h, n=10):
    s   = pd.Series(h)
    rol = s.rolling(n*2+1, center=True).max()
    out = np.where(s == rol, s, np.nan)
    return pd.Series(out).fillna(method="ffill").values

# ──────────────────────────────────────────────
# MUM FORMASYONU ANALİZİ (38 formasyon)
# ──────────────────────────────────────────────
def detect_candle_patterns(df: pd.DataFrame) -> list:
    """Son muma ait tüm formasyonları tespit et → [(isim, yön, güç)] listesi"""
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)

    patterns = []

    if TALIB_OK:
        # TA-Lib ile 38 formasyon
        PATTERN_FUNCS = {
            "Hammer"                : (talib.CDLHAMMER,        "bullish"),
            "Inverted Hammer"       : (talib.CDLINVERTEDHAMMER,"bullish"),
            "Bullish Engulfing"     : (talib.CDLENGULFING,     "both"),
            "Morning Star"          : (talib.CDLMORNINGSTAR,   "bullish"),
            "Morning Doji Star"     : (talib.CDLMORNINGDOJISTAR,"bullish"),
            "3 White Soldiers"      : (talib.CDL3WHITESOLDIERS,"bullish"),
            "Piercing Line"         : (talib.CDLPIERCING,      "bullish"),
            "Bullish Harami"        : (talib.CDLHARAMI,        "both"),
            "Bullish Harami Cross"  : (talib.CDLHARAMICROSS,   "both"),
            "Dragonfly Doji"        : (talib.CDLDRAGONFLYDOJI, "bullish"),
            "Matching Low"          : (talib.CDLMATCHINGLOW,   "bullish"),
            "Homing Pigeon"         : (talib.CDLHOMINGPIGEON,  "bullish"),
            "Ladder Bottom"         : (talib.CDLLADDERBOTTOM,  "bullish"),
            "3 Stars South"         : (talib.CDL3STARSINSOUTH, "bullish"),
            "Concealing Baby Swallow":(talib.CDLCONCEALBABYSWALL,"bullish"),
            "Takuri"                : (talib.CDLTAKURI,        "bullish"),
            "Shooting Star"         : (talib.CDLSHOOTINGSTAR,  "bearish"),
            "Hanging Man"           : (talib.CDLHANGINGMAN,    "bearish"),
            "Bearish Engulfing"     : (talib.CDLENGULFING,     "both"),
            "Evening Star"          : (talib.CDLEVENINGSTAR,   "bearish"),
            "Evening Doji Star"     : (talib.CDLEVENINGDOJISTAR,"bearish"),
            "3 Black Crows"         : (talib.CDL3BLACKCROWS,   "bearish"),
            "Dark Cloud Cover"      : (talib.CDLDARKCLOUDCOVER,"bearish"),
            "Gravestone Doji"       : (talib.CDLGRAVESTONEDOJI,"bearish"),
            "Bearish Harami"        : (talib.CDLHARAMI,        "both"),
            "Advance Block"         : (talib.CDLADVANCEBLOCK,  "bearish"),
            "2 Crows"               : (talib.CDL2CROWS,        "bearish"),
            "Identical 3 Crows"     : (talib.CDLIDENTICAL3CROWS,"bearish"),
            "Upside Gap 2 Crows"    : (talib.CDLUPSIDEGAP2CROWS,"bearish"),
            "Doji"                  : (talib.CDLDOJI,          "neutral"),
            "Long Legged Doji"      : (talib.CDLLONGLEGGEDDOJI,"neutral"),
            "Marubozu"              : (talib.CDLMARUBOZU,      "both"),
            "Spinning Top"          : (talib.CDLSPINNINGTOP,   "neutral"),
            "Abandoned Baby"        : (talib.CDLABANDONEDBABY, "both"),
            "Belt Hold"             : (talib.CDLBELTHOLD,      "both"),
            "Kicking"               : (talib.CDLKICKING,       "both"),
            "Tri-Star"              : (talib.CDLTRISTAR,       "both"),
            "Rising 3 Methods"      : (talib.CDLRISEFALL3METHODS,"both"),
        }

        for name, (fn, direction) in PATTERN_FUNCS.items():
            try:
                result = fn(o, h, l, c)
                val = int(result[-1])
                if val != 0:
                    strength = abs(val)  # 100 veya 200
                    if val > 0:
                        actual_dir = "bullish"
                    elif val < 0:
                        actual_dir = "bearish"
                    else:
                        actual_dir = "neutral"
                    patterns.append((name, actual_dir, strength))
            except:
                pass
    else:
        # Manuel basit formasyonlar (TA-Lib yoksa)
        patterns = _manual_patterns(o, h, l, c)

    return patterns

def _manual_patterns(o, h, l, c) -> list:
    """TA-Lib olmadan temel mum formasyonları"""
    patterns = []
    if len(o) < 4:
        return patterns

    # Son 3 mum
    o1, h1, l1, c1 = o[-4], h[-4], l[-4], c[-4]
    o2, h2, l2, c2 = o[-3], h[-3], l[-3], c[-3]
    o3, h3, l3, c3 = o[-2], h[-2], l[-2], c[-2]
    o0, h0, l0, c0 = o[-1], h[-1], l[-1], c[-1]

    body0   = abs(c0 - o0)
    rng0    = h0 - l0 + 1e-9
    upper_s = h0 - max(c0, o0)
    lower_s = min(c0, o0) - l0
    is_bull = c0 > o0
    is_bear = c0 < o0

    # Hammer (çekiç)
    if (lower_s > 2 * body0) and (upper_s < 0.3 * body0) and body0 > 0:
        if not is_bear:
            patterns.append(("Hammer", "bullish", 100))

    # Shooting Star
    if (upper_s > 2 * body0) and (lower_s < 0.3 * body0) and body0 > 0:
        if not is_bull:
            patterns.append(("Shooting Star", "bearish", 100))

    # Doji
    if body0 < 0.1 * rng0:
        patterns.append(("Doji", "neutral", 50))

    # Marubozu boğa
    if is_bull and upper_s < 0.05*rng0 and lower_s < 0.05*rng0 and body0 > 0.9*rng0:
        patterns.append(("Bullish Marubozu", "bullish", 100))

    # Marubozu ayı
    if is_bear and upper_s < 0.05*rng0 and lower_s < 0.05*rng0 and body0 > 0.9*rng0:
        patterns.append(("Bearish Marubozu", "bearish", 100))

    # Bullish Engulfing
    body_prev = abs(c3 - o3)
    if c3 < o3 and is_bull and c0 > o3 and o0 < c3 and body0 > body_prev:
        patterns.append(("Bullish Engulfing", "bullish", 100))

    # Bearish Engulfing
    if c3 > o3 and is_bear and c0 < o3 and o0 > c3 and body0 > body_prev:
        patterns.append(("Bearish Engulfing", "bearish", 100))

    # Morning Star (basit)
    b1 = abs(c2 - o2); b2 = abs(c3 - o3); b3 = body0
    if c2 < o2 and b2 > 2*b1 and c0 > o0 and b3 > 0.5*b2:
        patterns.append(("Morning Star", "bullish", 200))

    # Evening Star
    if c2 > o2 and b2 > 2*b1 and is_bear and b3 > 0.5*b2:
        patterns.append(("Evening Star", "bearish", 200))

    # Spinning Top
    if body0 < 0.3*rng0 and upper_s > 0.2*rng0 and lower_s > 0.2*rng0:
        patterns.append(("Spinning Top", "neutral", 50))

    return patterns

# ──────────────────────────────────────────────
# DESTEK / DİRENÇ YAKINI KONTROL
# ──────────────────────────────────────────────
def near_level(price: float, level: float, atr: float, mult=0.5) -> bool:
    return abs(price - level) <= mult * atr

# ──────────────────────────────────────────────
# SINYAL MOTORU
# ──────────────────────────────────────────────
def generate_signal(df: pd.DataFrame) -> dict:
    """
    Son mumu analiz et, tüm faktörleri birleştir, sinyal üret.
    Piyasa kapalıysa sinyal yok.
    """
    result = {
        "timestamp" : datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "price"     : float(df["close"].iloc[-1]),
        "signal"    : "BEKLE",
        "confidence": 0,
        "entry"     : None,
        "stop"      : None,
        "tp1"       : None,
        "tp2"       : None,
        "patterns"  : [],
        "reasons"   : [],
        "market"    : market_status(),
    }

    # Piyasa kapalıysa sinyal verme
    if not is_market_open():
        result["signal"] = "PİYASA KAPALI"
        result["reasons"] = ["XAU/USD piyasası şu an kapalı. Sinyal üretilmiyor."]
        return result

    row   = df.iloc[-1]
    price = float(row["close"])
    atr   = float(row["atr"]) if not np.isnan(row["atr"]) else price * 0.001

    bull_score = 0
    bear_score = 0
    reasons    = []

    # ── 1. TREND (EMA)
    ema9  = float(row["ema9"])
    ema21 = float(row["ema21"])
    ema50 = float(row["ema50"])
    ema200= float(row["ema200"])

    if price > ema200:
        bull_score += 10; reasons.append("✅ Fiyat EMA200 üzeri (uzun vadeli yükseliş)")
    else:
        bear_score += 10; reasons.append("❌ Fiyat EMA200 altı (uzun vadeli düşüş)")

    if ema9 > ema21 > ema50:
        bull_score += 15; reasons.append("✅ EMA9>21>50 → yükselen trend")
    elif ema9 < ema21 < ema50:
        bear_score += 15; reasons.append("❌ EMA9<21<50 → düşen trend")

    # ── 2. RSI
    rsi = float(row["rsi"])
    if rsi < RSI_OS:
        bull_score += 15; reasons.append(f"✅ RSI aşırı satım ({rsi:.1f})")
    elif rsi > RSI_OB:
        bear_score += 15; reasons.append(f"❌ RSI aşırı alım ({rsi:.1f})")
    elif 40 < rsi < 60:
        reasons.append(f"⚪ RSI nötr ({rsi:.1f})")
    elif rsi < 50:
        bear_score += 5
    else:
        bull_score += 5

    # ── 3. MACD
    macd_h = float(row["macd_hist"])
    macd_v = float(row["macd"])
    if macd_h > 0 and macd_v > 0:
        bull_score += 10; reasons.append("✅ MACD pozitif & histogram yeşil")
    elif macd_h < 0 and macd_v < 0:
        bear_score += 10; reasons.append("❌ MACD negatif & histogram kırmızı")
    elif macd_h > 0:
        bull_score += 5;  reasons.append("✅ MACD histogram dönüşü (yukarı)")
    elif macd_h < 0:
        bear_score += 5;  reasons.append("❌ MACD histogram dönüşü (aşağı)")

    # ── 4. BOLLINGER BANDS
    bb_upper = float(row["bb_upper"])
    bb_lower = float(row["bb_lower"])
    bb_mid   = float(row["bb_mid"])
    if price <= bb_lower:
        bull_score += 10; reasons.append("✅ Fiyat Bollinger alt bandında (aşırı satım)")
    elif price >= bb_upper:
        bear_score += 10; reasons.append("❌ Fiyat Bollinger üst bandında (aşırı alım)")
    elif price < bb_mid:
        bear_score += 3
    else:
        bull_score += 3

    # ── 5. STOCHASTIC
    stk = float(row["stoch_k"])
    std = float(row["stoch_d"])
    if stk < 20 and std < 20:
        bull_score += 10; reasons.append(f"✅ Stochastic aşırı satım ({stk:.1f})")
    elif stk > 80 and std > 80:
        bear_score += 10; reasons.append(f"❌ Stochastic aşırı alım ({stk:.1f})")
    if stk > std and stk < 50:
        bull_score += 5
    elif stk < std and stk > 50:
        bear_score += 5

    # ── 6. ADX (trend gücü)
    adx = float(row["adx"])
    if adx > 25:
        reasons.append(f"💪 Güçlü trend (ADX={adx:.1f})")
        # Trend yönü bonus
        if bull_score > bear_score:
            bull_score += 10
        else:
            bear_score += 10
    else:
        reasons.append(f"⚪ Zayıf trend (ADX={adx:.1f}) – konsolidasyon")

    # ── 7. HACİM
    vol_r = float(row["vol_ratio"])
    if vol_r > 1.5:
        reasons.append(f"📊 Yüksek hacim (x{vol_r:.1f} ort.) – sinyal güçlü")
        if bull_score > bear_score:
            bull_score += 8
        else:
            bear_score += 8
    elif vol_r < 0.5:
        reasons.append(f"📊 Düşük hacim (x{vol_r:.1f} ort.) – güvenilirlik düşük")
        bull_score -= 5
        bear_score -= 5

    # ── 8. DESTEK / DİRENÇ
    support    = float(row["support"])    if not np.isnan(row["support"])    else price - atr*3
    resistance = float(row["resistance"]) if not np.isnan(row["resistance"]) else price + atr*3

    at_support    = near_level(price, support,    atr)
    at_resistance = near_level(price, resistance, atr)

    if at_support:
        bull_score += 15; reasons.append(f"✅ Fiyat destek seviyesinde ({support:.2f})")
    if at_resistance:
        bear_score += 15; reasons.append(f"❌ Fiyat direnç seviyesinde ({resistance:.2f})")

    # ── 9. MUM FORMASYONLARI (en önemli bölüm)
    patterns = detect_candle_patterns(df)
    result["patterns"] = patterns

    for name, direction, strength in patterns:
        weight = int(strength / 10)  # 100→10 puan, 200→20 puan
        if direction == "bullish":
            bull_score += weight
            reasons.append(f"🕯️ BOĞA FORMASYONU: {name} (+{weight} puan)")
            # Destekte bullish formasyon → ekstra bonus
            if at_support:
                bull_score += 10
                reasons.append(f"   ⭐ {name} DESTEKTE → güçlü sinyal!")
        elif direction == "bearish":
            bear_score += weight
            reasons.append(f"🕯️ AYI FORMASYONU: {name} (+{weight} puan)")
            if at_resistance:
                bear_score += 10
                reasons.append(f"   ⭐ {name} DİRENÇTE → güçlü sinyal!")
        else:
            reasons.append(f"🕯️ NÖTR FORMASYON: {name}")

    # ── 10. KARAR
    total = bull_score + bear_score
    if total == 0:
        confidence = 0
    else:
        confidence = max(bull_score, bear_score) / total * 100

    signal = "BEKLE"
    if bull_score > bear_score and confidence >= CONF_MIN:
        signal = "AL"
    elif bear_score > bull_score and confidence >= CONF_MIN:
        signal = "SAT"

    entry = price
    if signal == "AL":
        stop  = entry - ATR_MULT_SL * atr
        tp1   = entry + ATR_MULT_TP * atr
        tp2   = entry + ATR_MULT_TP * 2 * atr
    elif signal == "SAT":
        stop  = entry + ATR_MULT_SL * atr
        tp1   = entry - ATR_MULT_TP * atr
        tp2   = entry - ATR_MULT_TP * 2 * atr
    else:
        stop = tp1 = tp2 = None

    result.update({
        "signal"    : signal,
        "confidence": round(confidence, 1),
        "entry"     : round(entry, 3) if entry else None,
        "stop"      : round(stop,  3) if stop  else None,
        "tp1"       : round(tp1,   3) if tp1   else None,
        "tp2"       : round(tp2,   3) if tp2   else None,
        "bull_score": bull_score,
        "bear_score": bear_score,
        "rsi"       : round(rsi, 1),
        "adx"       : round(adx, 1),
        "atr"       : round(atr, 3),
        "support"   : round(support, 3),
        "resistance": round(resistance, 3),
        "reasons"   : reasons,
    })

    return result

# ──────────────────────────────────────────────
# ÇIKTI YAZICI
# ──────────────────────────────────────────────
def print_signal(s: dict):
    sep = "═" * 60
    sig = s["signal"]
    color = ""
    if   sig == "AL":   emoji = "🟢 AL"
    elif sig == "SAT":  emoji = "🔴 SAT"
    elif sig == "PİYASA KAPALI": emoji = "🔒 PİYASA KAPALI"
    else:               emoji = "⚪ BEKLE"

    print(f"\n{sep}")
    print(f"  VALENS WEALTH · XAU/USD · {s['timestamp']}")
    print(f"  {s['market']}")
    print(sep)
    print(f"  Fiyat    : {s['price']:.3f}")
    print(f"  SİNYAL   : {emoji}  (Güven: %{s['confidence']})")

    if s["entry"]:
        print(f"  Giriş    : {s['entry']}")
        print(f"  Stop     : {s['stop']}")
        print(f"  TP1      : {s['tp1']}")
        print(f"  TP2      : {s['tp2']}")

    print(f"\n  📊 Skor  : Boğa {s.get('bull_score',0)} | Ayı {s.get('bear_score',0)}")
    if s.get("rsi"):
        print(f"  RSI={s['rsi']}  ADX={s['adx']}  ATR={s['atr']}")
        print(f"  Destek={s['support']}  Direnç={s['resistance']}")

    if s["patterns"]:
        print(f"\n  🕯️  Mum Formasyonları ({len(s['patterns'])} adet):")
        for name, direction, strength in s["patterns"]:
            d_icon = "🟢" if direction=="bullish" else ("🔴" if direction=="bearish" else "⚪")
            print(f"     {d_icon} {name} [{direction}] güç={strength}")

    print(f"\n  📋 Analiz Detayı:")
    for r in s["reasons"]:
        print(f"     {r}")

    print(sep)

# ──────────────────────────────────────────────
# ANA DÖNGÜ
# ──────────────────────────────────────────────
def run():
    print("=" * 60)
    print("  VALENS WEALTH – Gelişmiş Sinyal Botu Başlatıldı")
    print(f"  Sembol: {SYMBOL} | TF: 1H | Güncelleme: {LOOP_SEC}s")
    print("=" * 60)

    if not TV_OK:
        print("[UYARI] tvDatafeed yüklü değil. yfinance kullanılacak.")
    if not TALIB_OK:
        print("[UYARI] TA-Lib yüklü değil. Manuel formasyon analizi kullanılacak (38→10 formasyon).")

    while True:
        try:
            print(f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Veri çekiliyor...")
            df = fetch_data()
            df = add_indicators(df)
            sig = generate_signal(df)
            print_signal(sig)

        except Exception as e:
            print(f"[HATA] {e}")

        print(f"\n⏳ {LOOP_SEC} saniye bekleniyor...\n")
        time.sleep(LOOP_SEC)

# ──────────────────────────────────────────────
if __name__ == "__main__":
    run()
