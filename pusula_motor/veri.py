"""Gerçek piyasa verisi.

Varsayılan kaynak Yahoo Finance'tir (yfinance paketi). BIST hisseleri ".IS" ekiyle
çekilir (THYAO -> THYAO.IS). Veriler günlük ve gecikmelidir; strateji günlük kapanışla
çalıştığı için bu yeterlidir. Ticari kullanımda lisanslı bir veri sağlayıcıya geçin:
DataProvider sınıfından türeyen yeni bir sağlayıcı yazmanız yeterli.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd

KOLONLAR = ["open", "high", "low", "close", "volume"]


def temizle(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    eksik = [k for k in KOLONLAR if k not in df.columns]
    if eksik:
        raise ValueError(f"Eksik kolonlar: {eksik}")
    df = df[KOLONLAR].copy()
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["close"] > 0) & (df["high"] >= df["low"])]
    df["volume"] = df["volume"].fillna(0)
    return df


class DataProvider:
    def history(self, symbol: str, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        raise NotImplementedError


class YahooProvider(DataProvider):
    def __init__(self, cache_klasoru: str | None = "veri_onbellek"):
        self.cache = cache_klasoru

    @staticmethod
    def ticker(symbol: str) -> str:
        return symbol if "." in symbol else f"{symbol}.IS"

    def history(self, symbol, start=None, end=None):
        try:
            import yfinance as yf
        except ImportError as e:
            raise RuntimeError("yfinance yüklü değil: pip install yfinance") from e
        start = start or (date.today() - timedelta(days=365 * 6))
        end = end or (date.today() + timedelta(days=1))
        raw = yf.Ticker(self.ticker(symbol)).history(
            start=str(start), end=str(end), auto_adjust=True, actions=False
        )
        if raw is None or raw.empty:
            raise RuntimeError(f"{symbol} için veri gelmedi")
        df = temizle(raw)
        if self.cache:
            os.makedirs(self.cache, exist_ok=True)
            df.to_csv(os.path.join(self.cache, f"{symbol}.csv"), index_label="date")
        return df


class CsvProvider(DataProvider):
    """Klasördeki SEMBOL.csv dosyalarını okur (date, open, high, low, close, volume)."""

    def __init__(self, klasor: str):
        self.klasor = klasor

    def history(self, symbol, start=None, end=None):
        yol = os.path.join(self.klasor, f"{symbol}.csv")
        if not os.path.exists(yol):
            raise RuntimeError(f"{yol} bulunamadı")
        df = pd.read_csv(yol)
        tarih = next(c for c in df.columns if c.lower() in ("date", "tarih", "datetime"))
        df = temizle(df.set_index(tarih))
        if start:
            df = df[df.index >= pd.Timestamp(start)]
        if end:
            df = df[df.index <= pd.Timestamp(end)]
        return df


def evren_yukle(provider: DataProvider, semboller, start=None, end=None, uyari=print) -> dict[str, pd.DataFrame]:
    sonuc = {}
    for s in semboller:
        try:
            df = provider.history(s, start, end)
            if len(df) > 0:
                sonuc[s] = df
        except Exception as e:  # tek hissedeki hata tüm çalışmayı durdurmasın
            uyari(f"Uyarı: {s} atlandı ({e})")
    return sonuc
