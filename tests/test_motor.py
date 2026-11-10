"""Motorun mantık testleri. Sentetik veri yalnızca kuralların doğru işlediğini sınar;
stratejinin kârlılığı hakkında bir şey söylemez (bunun için gerçek veriyle backtest yapın)."""
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pusula_motor.araci_kurum import GercekYurutucu, KurumAdaptoru, mod_degistir
from pusula_motor.ayarlar import Ayarlar, kaydet, yukle
from pusula_motor.backtest import backtest_calistir, bar_sozlukleri
from pusula_motor.gostergeler import rsi, sma
from pusula_motor.risk import adet_hesapla
from pusula_motor.veri import CsvProvider


def sentetik(seed, n=900, yukselis=0.0006, oynaklik=0.02, baslangic=100.0):
    r = np.random.default_rng(seed)
    getiriler = r.normal(yukselis, oynaklik, n)
    # ara sıra 2-3 günlük sert düşüşler ekle
    for i in r.choice(np.arange(250, n - 5), size=25, replace=False):
        getiriler[i:i + 3] -= 0.025
    kapanis = baslangic * np.exp(np.cumsum(getiriler))
    acilis = kapanis * (1 + r.normal(0, 0.006, n))
    yuksek = np.maximum(acilis, kapanis) * (1 + np.abs(r.normal(0, 0.008, n)))
    dusuk = np.minimum(acilis, kapanis) * (1 - np.abs(r.normal(0, 0.008, n)))
    hacim = r.integers(2_000_000, 6_000_000, n).astype(float)
    idx = pd.bdate_range("2021-01-04", periods=n)
    return pd.DataFrame({"open": acilis, "high": yuksek, "low": dusuk, "close": kapanis, "volume": hacim}, index=idx)


def evren(k=8):
    return {f"HS{i:02d}": sentetik(i) for i in range(k)}


class Gostergeler(unittest.TestCase):
    def test_rsi_aralik(self):
        r = rsi(sentetik(1)["close"], 2).dropna()
        self.assertTrue(((r >= 0) & (r <= 100)).all())

    def test_rsi_hep_yukselen(self):
        s = pd.Series(np.arange(1, 50, dtype=float))
        self.assertAlmostEqual(rsi(s, 2).iloc[-1], 100.0)

    def test_sma(self):
        s = pd.Series([1.0, 2, 3, 4, 5])
        self.assertEqual(sma(s, 5).iloc[-1], 3.0)

    def test_gelecege_bakmaz(self):
        a = Ayarlar()
        df = sentetik(3)
        tam = bar_sozlukleri({"X": df}, a)["X"]
        kesik = bar_sozlukleri({"X": df.iloc[:600]}, a)["X"]
        t = df.index[599]
        for k in ("sma_trend", "rsi", "atr", "sma_cikis"):
            self.assertAlmostEqual(tam[t][k], kesik[t][k], places=9)


class Risk(unittest.TestCase):
    def test_risk_sinirlari(self):
        a = Ayarlar()
        adet = adet_hesapla(100_000, 100_000, 100.0, 95.0, a)
        self.assertLessEqual(adet * 5, 100_000 * a.islem_basina_risk + 1e-9)
        self.assertLessEqual(adet * 100, 100_000 * a.max_pozisyon_orani)

    def test_gecersiz_stop(self):
        self.assertEqual(adet_hesapla(100_000, 100_000, 100.0, 101.0, Ayarlar()), 0)

    def test_nakit_siniri(self):
        self.assertLessEqual(adet_hesapla(100_000, 1_000, 100.0, 99.0, Ayarlar()) * 100, 1_000)


class Backtest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Ayarlar(min_gunluk_islem_tl=1.0)
        cls.s = backtest_calistir(evren(), cls.a)

    def test_islem_var(self):
        self.assertGreater(self.s.ozet["islem_sayisi"], 10)

    def test_en_fazla_bir_hafta(self):
        self.assertLessEqual(self.s.islemler["gun"].max(), self.a.max_gun + 1)
        for _, r in self.s.islemler.iterrows():
            takvim = (pd.Timestamp(r["cikis_tarihi"]) - pd.Timestamp(r["giris_tarihi"])).days
            self.assertLessEqual(takvim, 7, r.to_dict())

    def test_pozisyon_ve_nakit(self):
        self.assertTrue((self.s.egri["ozkaynak"] > 0).all())

    def test_kayip_siniri(self):
        # tek işlemde kayıp, gap ve maliyetler hariç sermayenin ~%1'ini aşmamalı
        zarar = self.s.islemler[self.s.islemler["cikis_nedeni"] == "Zarar-durdur"]["net_kar_tl"]
        if len(zarar):
            self.assertGreater(zarar.min(), -self.a.baslangic_sermaye * 0.02)

    def test_cikis_nedenleri_gecerli(self):
        izinli = ("Zarar-durdur", "Hedef", "Toparlanma", "Süre", "Test sonu")
        for n in self.s.islemler["cikis_nedeni"]:
            self.assertTrue(n.startswith(izinli), n)

    def test_csv_saglayici(self):
        with tempfile.TemporaryDirectory() as d:
            sentetik(5).to_csv(os.path.join(d, "ABC.csv"), index_label="date")
            df = CsvProvider(d).history("ABC")
            self.assertEqual(list(df.columns), ["open", "high", "low", "close", "volume"])


class SahteKurum(KurumAdaptoru):
    def __init__(self, bagli=True):
        self.bagli, self.emirler, self._poz, self._nakit = bagli, [], {}, 100_000.0

    def baglanti_testi(self):
        if not self.bagli:
            raise ConnectionError("bağlantı yok")

    def nakit(self):
        return self._nakit

    def pozisyonlar(self):
        return self._poz

    def emir_gonder(self, sembol, yon, adet, tip="piyasa", fiyat=None):
        self.emirler.append((sembol, yon, adet, tip, fiyat))
        return str(len(self.emirler))

    def acik_emirleri_iptal_et(self, sembol):
        self.emirler.append((sembol, "iptal"))


class Modlar(unittest.TestCase):
    def test_adaptorsuz_gercege_gecilmez(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "ayarlar.json")
            kaydet(Ayarlar(), yol)
            with self.assertRaises(RuntimeError):
                mod_degistir("gercek", onay=True, ayarlar_yolu=yol)
            self.assertEqual(yukle(yol).mod, "sanal")

    def test_onaysiz_gercege_gecilmez(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "ayarlar.json")
            kaydet(Ayarlar(), yol)
            with self.assertRaises(RuntimeError):
                mod_degistir("gercek", onay=False, ayarlar_yolu=yol)

    def test_gercek_yurutucu_emir_gonderir(self):
        a = Ayarlar(min_gunluk_islem_tl=1.0)
        barlar = bar_sozlukleri(evren(), a)
        k = SahteKurum()
        y = GercekYurutucu(a, k, None)
        tarihler = sorted({t for d in barlar.values() for t in d})
        gonderildi = False
        for t in tarihler[250:]:
            r = y.gun_sonu(t.strftime("%Y-%m-%d"), {s: d[t] for s, d in barlar.items() if t in d})
            if r["gonderilen_emirler"]:
                gonderildi = True
                break
        self.assertTrue(gonderildi)
        self.assertTrue(any(e[1] == "al" for e in k.emirler))


if __name__ == "__main__":
    unittest.main(verbosity=2)
