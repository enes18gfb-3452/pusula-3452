"""Geçmiş gerçek veriyle strateji testi."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from .cekirdek import IslemCekirdegi
from .gostergeler import gosterge_ekle


def bar_sozlukleri(veriler: dict[str, pd.DataFrame], ayarlar) -> dict[str, dict]:
    """{sembol: {Timestamp: {kolon: değer}}} — hızlı gün gün erişim için."""
    return {s: gosterge_ekle(df, ayarlar).to_dict("index") for s, df in veriler.items()}


@dataclass
class Sonuc:
    ozet: dict
    islemler: pd.DataFrame
    egri: pd.DataFrame


def backtest_calistir(veriler: dict[str, pd.DataFrame], ayarlar, benchmark: pd.DataFrame | None = None,
                      baslangic=None, bitis=None) -> Sonuc:
    barlar = bar_sozlukleri(veriler, ayarlar)
    tarihler = sorted({t for d in barlar.values() for t in d})
    if baslangic is not None:
        tarihler = [t for t in tarihler if t >= pd.Timestamp(baslangic)]
    if bitis is not None:
        tarihler = [t for t in tarihler if t <= pd.Timestamp(bitis)]
    if not tarihler:
        raise ValueError("Test için tarih yok")

    c = IslemCekirdegi(ayarlar, ayarlar.baslangic_sermaye)
    for t in tarihler:
        gunun = {s: d[t] for s, d in barlar.items() if t in d}
        c.gun_isle(t.strftime("%Y-%m-%d"), gunun)

    # test sonunda açık kalanları son kapanıştan kapat
    son = tarihler[-1].strftime("%Y-%m-%d")
    for p in list(c.pozisyonlar.values()):
        c._sat(p, p.son_fiyat, son, "Test sonu")
    if c.ozkaynak_egrisi:
        c.ozkaynak_egrisi[-1] = (son, c.ozkaynak())

    islemler = pd.DataFrame(c.islemler)
    egri = pd.DataFrame(c.ozkaynak_egrisi, columns=["tarih", "ozkaynak"]).set_index("tarih")
    return Sonuc(ozet=ozet_hesapla(islemler, egri, ayarlar, benchmark, tarihler), islemler=islemler, egri=egri)


def ozet_hesapla(islemler, egri, ayarlar, benchmark, tarihler) -> dict:
    bas, son = ayarlar.baslangic_sermaye, float(egri["ozkaynak"].iloc[-1])
    gun = max((tarihler[-1] - tarihler[0]).days, 1)
    yillik = (son / bas) ** (365 / gun) - 1 if son > 0 else -1
    zirve = egri["ozkaynak"].cummax()
    max_dusus = float(((egri["ozkaynak"] - zirve) / zirve).min())

    o = {
        "baslangic": tarihler[0].strftime("%Y-%m-%d"),
        "bitis": tarihler[-1].strftime("%Y-%m-%d"),
        "baslangic_sermaye": bas,
        "bitis_sermaye": round(son, 2),
        "toplam_getiri_yuzde": round((son / bas - 1) * 100, 2),
        "yillik_getiri_yuzde": round(yillik * 100, 2),
        "max_dusus_yuzde": round(max_dusus * 100, 2),
        "islem_sayisi": int(len(islemler)),
    }
    if len(islemler):
        kazanan = islemler[islemler["net_kar_tl"] > 0]
        kaybeden = islemler[islemler["net_kar_tl"] <= 0]
        brut_k, brut_z = kazanan["net_kar_tl"].sum(), -kaybeden["net_kar_tl"].sum()
        o.update({
            "kazanma_orani_yuzde": round(len(kazanan) / len(islemler) * 100, 1),
            "ort_kazanc_yuzde": round(float(kazanan["getiri_yuzde"].mean()), 2) if len(kazanan) else 0.0,
            "ort_kayip_yuzde": round(float(kaybeden["getiri_yuzde"].mean()), 2) if len(kaybeden) else 0.0,
            "kar_faktoru": round(float(brut_k / brut_z), 2) if brut_z > 0 else math.inf,
            "ort_gun": round(float(islemler["gun"].mean()), 2),
            "en_uzun_gun": int(islemler["gun"].max()),
            "cikis_nedenleri": islemler["cikis_nedeni"].str.split(":").str[0].value_counts().to_dict(),
        })
    if benchmark is not None and len(benchmark):
        b = benchmark["close"]
        b = b[(b.index >= tarihler[0]) & (b.index <= tarihler[-1])]
        if len(b) > 1:
            o["endeks_getiri_yuzde"] = round((b.iloc[-1] / b.iloc[0] - 1) * 100, 2)
            bz = b.cummax()
            o["endeks_max_dusus_yuzde"] = round(float(((b - bz) / bz).min()) * 100, 2)
    return o


def ozet_metni(o: dict) -> str:
    satirlar = [
        f"Dönem              : {o['baslangic']} → {o['bitis']}",
        f"Sermaye            : {o['baslangic_sermaye']:,.0f} ₺ → {o['bitis_sermaye']:,.0f} ₺",
        f"Toplam getiri      : %{o['toplam_getiri_yuzde']}",
        f"Yıllık getiri      : %{o['yillik_getiri_yuzde']}",
        f"En büyük düşüş     : %{o['max_dusus_yuzde']}",
        f"İşlem sayısı       : {o['islem_sayisi']}",
    ]
    if o.get("islem_sayisi"):
        satirlar += [
            f"Kazanma oranı      : %{o['kazanma_orani_yuzde']}",
            f"Ort. kazanç/kayıp  : %{o['ort_kazanc_yuzde']} / %{o['ort_kayip_yuzde']}",
            f"Kâr faktörü        : {o['kar_faktoru']}",
            f"Ort./en uzun süre  : {o['ort_gun']} / {o['en_uzun_gun']} işlem günü",
            f"Çıkış nedenleri    : {o['cikis_nedenleri']}",
        ]
    if "endeks_getiri_yuzde" in o:
        satirlar += [
            f"Endeks (al-tut)    : %{o['endeks_getiri_yuzde']} getiri, %{o['endeks_max_dusus_yuzde']} en büyük düşüş",
            "Sonuç              : " + (
                "Strateji endeksi geçti." if o["toplam_getiri_yuzde"] > o["endeks_getiri_yuzde"]
                else "Strateji endeksi GEÇEMEDİ. Bu ayarlarla gerçek paraya geçmeyin."
            ),
        ]
    return "\n".join(satirlar).replace(",", ".")
