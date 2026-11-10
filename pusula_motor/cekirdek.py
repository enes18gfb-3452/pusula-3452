"""İşlem çekirdeği: backtest de sanal mod da aynı kuralları buradan çalıştırır.

Bir işlem günü üç adımda işlenir:
  1. Açılış: dünden kalan satış ve alış emirleri açılış fiyatından gerçekleşir.
  2. Gün içi: zarar-durdur veya hedefe dokunan pozisyonlar kapanır.
     (Aynı gün ikisine de dokunduysa temkinli davranılır: zarar-durdur sayılır.)
  3. Kapanış: çıkış koşulları kontrol edilir, yeni giriş sinyalleri yarın için sıraya alınır.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .risk import adet_hesapla, yeni_islem_durdurulsun_mu
from .strateji import giris_sinyali, kapanista_cikis_nedeni


@dataclass
class Pozisyon:
    sembol: str
    adet: int
    giris_fiyati: float
    giris_tarihi: str
    stop: float
    hedef: float
    giris_komisyonu: float
    son_fiyat: float
    gun_sayisi: int = 0
    cikis_isareti: str | None = None
    nedenler: list = field(default_factory=list)


@dataclass
class BekleyenAlis:
    sembol: str
    sinyal_tarihi: str
    planlanan_adet: int
    planlanan_fiyat: float
    stop_mesafesi: float
    hedef_mesafesi: float
    guc: int
    nedenler: list = field(default_factory=list)


class IslemCekirdegi:
    def __init__(self, ayarlar, nakit: float):
        self.a = ayarlar
        self.nakit = float(nakit)
        self.pozisyonlar: dict[str, Pozisyon] = {}
        self.bekleyen: list[BekleyenAlis] = []
        self.islemler: list[dict] = []
        self.ozkaynak_egrisi: list[tuple[str, float]] = []
        self.zirve = float(nakit)
        self.son_tarih: str | None = None
        self.gunluk_olaylar: list[str] = []

    # ------------------------------------------------------------ yardımcılar
    def ozkaynak(self) -> float:
        return self.nakit + sum(p.adet * p.son_fiyat for p in self.pozisyonlar.values())

    def _sat(self, p: Pozisyon, fiyat: float, tarih: str, neden: str) -> None:
        tutar = p.adet * fiyat
        kom = tutar * self.a.komisyon_orani
        self.nakit += tutar - kom
        net = (fiyat - p.giris_fiyati) * p.adet - p.giris_komisyonu - kom
        maliyet = p.giris_fiyati * p.adet + p.giris_komisyonu
        self.islemler.append({
            "sembol": p.sembol, "giris_tarihi": p.giris_tarihi, "cikis_tarihi": tarih,
            "adet": p.adet, "giris_fiyati": round(p.giris_fiyati, 4), "cikis_fiyati": round(fiyat, 4),
            "net_kar_tl": round(net, 2), "getiri_yuzde": round(net / maliyet * 100, 3),
            "gun": p.gun_sayisi, "cikis_nedeni": neden,
        })
        self.gunluk_olaylar.append(f"SATILDI {p.sembol} {p.adet} adet @ {fiyat:.2f} ₺ · {neden}")
        del self.pozisyonlar[p.sembol]

    # ------------------------------------------------------------ gün adımları
    def gun_isle(self, tarih: str, barlar: dict[str, dict]) -> None:
        self.gunluk_olaylar = []
        self._acilis(tarih, barlar)
        self._gun_ici(tarih, barlar)
        self._kapanis(tarih, barlar)

    def _acilis(self, tarih, barlar):
        kay = self.a.kayma_orani
        # önce satışlar (nakit serbest kalsın)
        for p in list(self.pozisyonlar.values()):
            if p.cikis_isareti and p.sembol in barlar:
                self._sat(p, barlar[p.sembol]["open"] * (1 - kay), tarih, p.cikis_isareti)
        # sonra alışlar
        bekleyen, self.bekleyen = self.bekleyen, []
        for b in bekleyen:
            bar = barlar.get(b.sembol)
            if bar is None or b.sembol in self.pozisyonlar:
                continue
            if len(self.pozisyonlar) >= self.a.max_pozisyon_sayisi:
                break
            fiyat = bar["open"] * (1 + kay)
            stop = fiyat - b.stop_mesafesi
            # açılış planlanan zarar-durdurun altındaysa kurulum bozulmuştur: girme
            if bar["open"] <= b.planlanan_fiyat - b.stop_mesafesi:
                self.gunluk_olaylar.append(f"ATLANDI {b.sembol}: açılış zarar-durdur seviyesinin altında")
                continue
            adet = min(b.planlanan_adet, adet_hesapla(self.ozkaynak(), self.nakit, fiyat, stop, self.a))
            if adet <= 0:
                continue
            tutar = adet * fiyat
            kom = tutar * self.a.komisyon_orani
            self.nakit -= tutar + kom
            self.pozisyonlar[b.sembol] = Pozisyon(
                sembol=b.sembol, adet=adet, giris_fiyati=fiyat, giris_tarihi=tarih,
                stop=stop, hedef=fiyat + b.hedef_mesafesi, giris_komisyonu=kom,
                son_fiyat=fiyat, nedenler=b.nedenler,
            )
            self.gunluk_olaylar.append(f"ALINDI {b.sembol} {adet} adet @ {fiyat:.2f} ₺")

    def _gun_ici(self, tarih, barlar):
        kay = self.a.kayma_orani
        for p in list(self.pozisyonlar.values()):
            bar = barlar.get(p.sembol)
            if bar is None:
                continue
            o, h, l = bar["open"], bar["high"], bar["low"]
            if o <= p.stop:
                self._sat(p, o * (1 - kay), tarih, "Zarar-durdur (açılış seviyenin altında)")
            elif l <= p.stop:
                self._sat(p, p.stop * (1 - kay), tarih, "Zarar-durdur")
            elif h >= p.hedef:
                self._sat(p, max(p.hedef, o), tarih, "Hedef fiyata ulaşıldı")

    def _kapanis(self, tarih, barlar):
        # açık pozisyonları güncelle, çıkış işaretle
        serbest_kalacak_nakit = 0.0
        for p in self.pozisyonlar.values():
            bar = barlar.get(p.sembol)
            if bar is None:
                continue
            p.son_fiyat = bar["close"]
            p.gun_sayisi += 1
            neden = kapanista_cikis_nedeni(p.gun_sayisi, bar, self.a)
            if neden:
                p.cikis_isareti = neden
                serbest_kalacak_nakit += p.adet * p.son_fiyat * (1 - self.a.komisyon_orani)

        oz = self.ozkaynak()
        self.zirve = max(self.zirve, oz)
        self.ozkaynak_egrisi.append((tarih, oz))
        self.son_tarih = tarih

        if yeni_islem_durdurulsun_mu(oz, self.zirve, self.a):
            self.gunluk_olaylar.append("Yeni işlem durduruldu: sermaye zirveden belirlenen sınırın üzerinde düştü")
            return

        kalacak = sum(1 for p in self.pozisyonlar.values() if not p.cikis_isareti)
        bos_yer = self.a.max_pozisyon_sayisi - kalacak
        if bos_yer <= 0:
            return

        adaylar = []
        for sembol, bar in barlar.items():
            if sembol in self.pozisyonlar:
                continue
            s = giris_sinyali(sembol, tarih, bar, self.a)
            if s:
                adaylar.append(s)
        adaylar.sort(key=lambda s: (-s.guc, s.rsi))

        nakit = self.nakit + serbest_kalacak_nakit
        for s in adaylar[:bos_yer]:
            adet = adet_hesapla(oz, nakit, s.kapanis, s.stop, self.a)
            if adet <= 0:
                continue
            nakit -= adet * s.kapanis * (1 + self.a.komisyon_orani + self.a.kayma_orani)
            self.bekleyen.append(BekleyenAlis(
                sembol=s.sembol, sinyal_tarihi=tarih, planlanan_adet=adet,
                planlanan_fiyat=s.kapanis, stop_mesafesi=self.a.stop_atr * s.atr,
                hedef_mesafesi=self.a.hedef_atr * s.atr, guc=s.guc, nedenler=s.nedenler,
            ))

    # ------------------------------------------------------------ kayıt
    def durum(self) -> dict:
        return {
            "nakit": self.nakit, "zirve": self.zirve, "son_tarih": self.son_tarih,
            "pozisyonlar": [asdict(p) for p in self.pozisyonlar.values()],
            "bekleyen": [asdict(b) for b in self.bekleyen],
            "islemler": self.islemler,
            "ozkaynak_egrisi": self.ozkaynak_egrisi,
        }

    @classmethod
    def durumdan(cls, ayarlar, d: dict) -> "IslemCekirdegi":
        c = cls(ayarlar, d["nakit"])
        c.zirve = d.get("zirve", c.nakit)
        c.son_tarih = d.get("son_tarih")
        c.pozisyonlar = {p["sembol"]: Pozisyon(**p) for p in d.get("pozisyonlar", [])}
        c.bekleyen = [BekleyenAlis(**b) for b in d.get("bekleyen", [])]
        c.islemler = d.get("islemler", [])
        c.ozkaynak_egrisi = [tuple(x) for x in d.get("ozkaynak_egrisi", [])]
        return c
