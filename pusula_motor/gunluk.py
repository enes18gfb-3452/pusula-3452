"""Günlük çalışma: her işlem günü kapanıştan sonra (ör. 18:30) bir kez çalıştırılır.

Çıktı: sinyaller.json — mobil uygulamanın okuyacağı dosya (portföy, açık pozisyonlar,
yarın açılışta yapılacak alım-satımlar ve her birinin sade dilde nedeni).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

from .araci_kurum import GercekYurutucu, adaptor_yukle
from .backtest import bar_sozlukleri
from .cekirdek import IslemCekirdegi
from .veri import evren_yukle

DURUM_DOSYASI = {"sanal": "durum_sanal.json", "gercek": "durum_gercek.json"}


def _oku(yol):
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    return None


def _yaz(yol, veri):
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2, default=str)
    os.replace(gecici, yol)


def gunluk_calistir(ayarlar, provider, klasor: str = ".", bugun: date | None = None) -> dict:
    bugun = bugun or date.today()
    veriler = evren_yukle(provider, ayarlar.evren, start=bugun - timedelta(days=450), end=bugun + timedelta(days=1))
    if not veriler:
        raise RuntimeError("Hiçbir hisse için veri alınamadı")
    barlar = bar_sozlukleri(veriler, ayarlar)
    tarihler = sorted({t for d in barlar.values() for t in d})
    durum_yolu = os.path.join(klasor, DURUM_DOSYASI[ayarlar.mod])
    durum = _oku(durum_yolu)

    if ayarlar.mod == "sanal":
        if durum:
            c = IslemCekirdegi.durumdan(ayarlar, durum)
            yeni = [t for t in tarihler if t.strftime("%Y-%m-%d") > (c.son_tarih or "")]
            olaylar = []
            for t in yeni:  # kaçırılan günler varsa sırayla işlenir
                c.gun_isle(t.strftime("%Y-%m-%d"), {s: d[t] for s, d in barlar.items() if t in d})
                olaylar += [f"{t:%d.%m} {o}" for o in c.gunluk_olaylar]
        else:
            # ilk çalıştırma: geçmişi simüle etme, sadece bugünün kapanışından sinyal üret
            c = IslemCekirdegi(ayarlar, ayarlar.baslangic_sermaye)
            t = tarihler[-1]
            c._kapanis(t.strftime("%Y-%m-%d"), {s: d[t] for s, d in barlar.items() if t in d})
            olaylar = c.gunluk_olaylar
        sonuc_durum, notlar, gonderilen = c.durum(), [], []
    else:
        adaptor = adaptor_yukle(ayarlar.araci_kurum_adaptoru)
        t = tarihler[-1]
        y = GercekYurutucu(ayarlar, adaptor, durum)
        r = y.gun_sonu(t.strftime("%Y-%m-%d"), {s: d[t] for s, d in barlar.items() if t in d})
        c, sonuc_durum, notlar, gonderilen = y.c, r["durum"], r["notlar"], r["gonderilen_emirler"]
        olaylar = y.c.gunluk_olaylar

    _yaz(durum_yolu, sonuc_durum)
    cikti = uygulama_ciktisi(ayarlar, c, olaylar, notlar, gonderilen)
    cikti["izleme"] = izleme_listesi(barlar, c)
    _yaz(os.path.join(klasor, "sinyaller.json"), cikti)
    return cikti


def _y(x, n=2):
    try:
        return None if x is None or x != x else round(float(x), n)
    except (TypeError, ValueError):
        return None


def izleme_listesi(barlar: dict, c: IslemCekirdegi, gun: int = 60) -> list[dict]:
    """Uygulamadaki liste ve grafikler için her hissenin son durumu ve son 60 günü."""
    alinacak = {b.sembol for b in c.bekleyen}
    liste = []
    for s, d in barlar.items():
        ts = sorted(d)
        if not ts:
            continue
        son = d[ts[-1]]
        onceki = d[ts[-2]]["close"] if len(ts) > 1 else son["close"]
        if s in c.pozisyonlar:
            durum = "SAT" if c.pozisyonlar[s].cikis_isareti else "PORTFOYDE"
        elif s in alinacak:
            durum = "AL"
        else:
            durum = "BEKLE"
        son_gunler = ts[-gun:]
        liste.append({
            "sembol": s, "durum": durum, "tarih": ts[-1].strftime("%Y-%m-%d"),
            "kapanis": _y(son["close"]), "degisim_yuzde": _y((son["close"] / onceki - 1) * 100),
            "rsi": _y(son.get("rsi"), 1), "trend_yukari": bool(
                _y(son.get("sma_trend")) and son["close"] > son["sma_trend"]
                and _y(son.get("sma_orta")) and son["sma_orta"] > son["sma_trend"]),
            "grafik": {
                "tarih": [t.strftime("%Y-%m-%d") for t in son_gunler],
                "kapanis": [_y(d[t]["close"]) for t in son_gunler],
                "sma5": [_y(d[t].get("sma_cikis")) for t in son_gunler],
                "sma200": [_y(d[t].get("sma_trend")) for t in son_gunler],
            },
        })
    sira = {"AL": 0, "SAT": 1, "PORTFOYDE": 2, "BEKLE": 3}
    liste.sort(key=lambda x: (sira[x["durum"]], x["sembol"]))
    return liste


def uygulama_ciktisi(ayarlar, c: IslemCekirdegi, olaylar, notlar, gonderilen) -> dict:
    oz = c.ozkaynak()
    bas = ayarlar.baslangic_sermaye if ayarlar.mod == "sanal" else (c.ozkaynak_egrisi[0][1] if c.ozkaynak_egrisi else oz)
    return {
        "olusturulma": datetime.now().isoformat(timespec="seconds"),
        "veri_tarihi": c.son_tarih,
        "mod": ayarlar.mod,
        "portfoy": {
            "ozkaynak": round(oz, 2), "nakit": round(c.nakit, 2),
            "baslangictan_getiri_yuzde": round((oz / bas - 1) * 100, 2) if bas else 0,
        },
        "acik_pozisyonlar": [
            {
                "sembol": p.sembol, "adet": p.adet, "giris": round(p.giris_fiyati, 2),
                "son": round(p.son_fiyat, 2), "stop": round(p.stop, 2), "hedef": round(p.hedef, 2),
                "kar_zarar_tl": round((p.son_fiyat - p.giris_fiyati) * p.adet, 2),
                "gun": p.gun_sayisi, "kalan_gun": max(ayarlar.max_gun - p.gun_sayisi, 0),
                "yarin_satilacak": bool(p.cikis_isareti), "satis_nedeni": p.cikis_isareti,
            }
            for p in c.pozisyonlar.values()
        ],
        "yarin_alinacak": [
            {
                "sembol": b.sembol, "aksiyon": "AL", "guc": {1: "zayıf", 2: "orta", 3: "güçlü"}[b.guc],
                "planlanan_adet": b.planlanan_adet, "yaklasik_fiyat": round(b.planlanan_fiyat, 2),
                "zarar_durdur": round(b.planlanan_fiyat - b.stop_mesafesi, 2),
                "hedef": round(b.planlanan_fiyat + b.hedef_mesafesi, 2),
                "en_kotu_senaryo_tl": round(b.planlanan_adet * b.stop_mesafesi, 2),
                "en_gec_cikis": f"{ayarlar.max_gun + 1}. işlem günü açılışı",
                "nedenler": b.nedenler,
            }
            for b in c.bekleyen
        ],
        "son_islemler": c.islemler[-10:],
        "bugunun_olaylari": olaylar,
        "kurum_notlari": notlar,
        "kuruma_gonderilen_emirler": gonderilen,
        "uyari": "Yatırım tavsiyesi değildir. Kararlar sizin sorumluluğunuzdadır.",
    }
