"""Teknik göstergeler. Hepsi yalnızca o güne kadarki veriyi kullanır (geleceğe bakmaz)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi(close: pd.Series, n: int) -> pd.Series:
    """Wilder RSI."""
    delta = close.diff()
    kazanc = delta.clip(lower=0)
    kayip = -delta.clip(upper=0)
    ort_k = kazanc.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ort_y = kayip.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = ort_k / ort_y.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out = out.where(ort_y != 0, 100.0)
    return out.where(ort_k.notna())


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    onceki = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - onceki).abs(), (df["low"] - onceki).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def gosterge_ekle(df: pd.DataFrame, a) -> pd.DataFrame:
    out = df.copy()
    out["sma_trend"] = sma(out["close"], a.trend_sma)
    out["sma_orta"] = sma(out["close"], a.orta_sma)
    out["sma_cikis"] = sma(out["close"], a.cikis_sma)
    out["rsi"] = rsi(out["close"], a.rsi_periyot)
    out["atr"] = atr(out, a.atr_periyot)
    out["hacim20"] = sma(out["volume"], 20)
    out["islem_tl20"] = sma(out["close"] * out["volume"], 20)
    return out
