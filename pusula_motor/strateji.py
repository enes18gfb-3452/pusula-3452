"""Haftalık geri çekilme stratejisi.

Fikir: Ana trendi yukarı olan likit bir hisse birkaç günde sert düştüğünde, kısa süreli
bir toparlanma sık görülür. Bu toparlanmanın bir kısmını alıp en geç 1 hafta içinde çıkılır.

Giriş (günlük kapanışa göre, ertesi gün açılışta):
  1. Kapanış > 200 günlük ortalama ve 50 günlük ort. > 200 günlük ort.  (ana trend yukarı)
  2. RSI(2) < 10                                                        (sert kısa geri çekilme)
  3. 20 günlük ortalama işlem hacmi >= 50 milyon ₺                      (kolay alınıp satılabilir)

Çıkış (hangisi önce olursa):
  - Zarar-durdur: giriş - 2 x ATR (gün içinde dokunursa)
  - Hedef: giriş + 2 x ATR (gün içinde dokunursa)
  - Toparlanma bitti: kapanış 5 günlük ortalamanın üstünde -> ertesi açılışta sat
  - Süre doldu: 4. günün kapanışında hâlâ açıksa -> 5. gün açılışında sat

Bu strateji kâr garantisi vermez. Kullanmadan önce gerçek veriyle backtest yapın.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def _tr(x: float, n: int = 1) -> str:
    """Türkçe ondalık: 5.9 -> 5,9"""
    return f"{x:.{n}f}".replace(".", ",")


def _gecerli(*degerler) -> bool:
    return all(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in degerler)


@dataclass
class GirisSinyali:
    sembol: str
    tarih: str
    kapanis: float
    atr: float
    rsi: float
    guc: int
    stop: float
    hedef: float
    nedenler: list = field(default_factory=list)

    @property
    def guc_metni(self) -> str:
        return {1: "zayıf", 2: "orta", 3: "güçlü"}[self.guc]


def giris_sinyali(sembol: str, tarih: str, bar: dict, a) -> GirisSinyali | None:
    c, st, so, r, at = bar.get("close"), bar.get("sma_trend"), bar.get("sma_orta"), bar.get("rsi"), bar.get("atr")
    hacim, h20, tl20 = bar.get("volume"), bar.get("hacim20"), bar.get("islem_tl20")
    if not _gecerli(c, st, so, r, at, h20, tl20) or at <= 0:
        return None
    if not (c > st and so > st):
        return None
    if not r < a.rsi_giris:
        return None
    if tl20 < a.min_gunluk_islem_tl:
        return None

    guc = 1
    if r < a.rsi_guclu:
        guc += 1
    hacim_kat = (hacim / h20) if h20 else 0
    if hacim_kat >= a.hacim_carpani:
        guc += 1
    if guc < a.min_guc:
        return None

    nedenler = [
        f"Ana trend yukarı: fiyat {a.trend_sma} günlük ortalamanın %{_tr((c / st - 1) * 100)} üzerinde.",
        f"Kısa vadeli sert düşüş: RSI({a.rsi_periyot}) {_tr(r)}. Strateji bu tür düşüşlerden sonraki "
        f"birkaç günlük toparlanmayı hedefler.",
    ]
    if hacim_kat >= a.hacim_carpani:
        nedenler.append(f"Hacim 20 günlük ortalamanın {_tr(hacim_kat)} katı: satış baskısı doruğa çıkmış olabilir.")
    nedenler.append(f"Likidite yeterli: günlük ortalama işlem {tl20 / 1e6:,.0f} milyon ₺.".replace(",", "."))

    return GirisSinyali(
        sembol=sembol, tarih=tarih, kapanis=c, atr=at, rsi=r, guc=guc,
        stop=c - a.stop_atr * at, hedef=c + a.hedef_atr * at, nedenler=nedenler,
    )


def kapanista_cikis_nedeni(gun_sayisi: int, bar: dict, a) -> str | None:
    c, s5 = bar.get("close"), bar.get("sma_cikis")
    if _gecerli(c, s5) and c > s5:
        return f"Toparlanma tamamlandı: fiyat {a.cikis_sma} günlük ortalamanın üzerine çıktı."
    if gun_sayisi >= a.max_gun:
        return f"Süre doldu: {a.max_gun} işlem günü tamamlandı (en fazla 1 hafta kuralı)."
    return None
