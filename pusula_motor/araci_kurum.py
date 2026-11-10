"""Sanal ve gerçek mod.

Sanal mod: emirler gerçek piyasa verisiyle, gerçekleşmiş gibi simüle edilir. Para yoktur.
Gerçek mod: aynı kararlar lisanslı bir aracı kurumun API'sine emir olarak gönderilir.

Gerçek moda geçmek için kurumunuzun API'sine bağlanan bir KurumAdaptoru yazmanız ve
ayarlar.json içindeki "araci_kurum_adaptoru" alanına "modul:Sinif" olarak girmeniz gerekir.
Adaptör yoksa veya bağlantı testi başarısızsa motor gerçek moda geçmeyi reddeder.
"""
from __future__ import annotations

import importlib

from .ayarlar import kaydet, yukle
from .cekirdek import IslemCekirdegi, Pozisyon


class KurumAdaptoru:
    """Kurumunuzun API'si için doldurmanız gereken arayüz."""

    def baglanti_testi(self) -> None:
        """Bağlantı yoksa hata fırlatın."""
        raise NotImplementedError

    def nakit(self) -> float:
        raise NotImplementedError

    def pozisyonlar(self) -> dict[str, dict]:
        """{"THYAO": {"adet": 16, "maliyet": 306.5}, ...}"""
        raise NotImplementedError

    def emir_gonder(self, sembol: str, yon: str, adet: int, tip: str = "piyasa",
                    fiyat: float | None = None) -> str:
        """yon: "al" | "sat"; tip: "piyasa" | "limit" | "zarar_durdur". Emir numarası döndürür."""
        raise NotImplementedError

    def acik_emirleri_iptal_et(self, sembol: str) -> None:
        raise NotImplementedError


def adaptor_yukle(spec: str) -> KurumAdaptoru:
    if not spec or ":" not in spec:
        raise RuntimeError(
            "Aracı kurum adaptörü tanımlı değil. Gerçek mod için kurumunuzun API'sine bağlanan "
            "bir adaptör gerekir (ayarlar.json > araci_kurum_adaptoru)."
        )
    modul, sinif = spec.split(":", 1)
    return getattr(importlib.import_module(modul), sinif)()


def mod_degistir(yeni_mod: str, onay: bool = False, ayarlar_yolu: str = "ayarlar.json") -> str:
    """Uygulamadaki 'Gerçek paraya geç' butonunun arka ucu."""
    a = yukle(ayarlar_yolu)
    if yeni_mod == a.mod:
        return f"Zaten {yeni_mod} moddasınız."
    if yeni_mod == "gercek":
        if not onay:
            raise RuntimeError("Gerçek paraya geçiş için açık onay gerekli.")
        adaptor = adaptor_yukle(a.araci_kurum_adaptoru)
        adaptor.baglanti_testi()
    a.mod = yeni_mod
    kaydet(a, ayarlar_yolu)
    return "Gerçek mod açıldı. Yeni emirler aracı kurumunuza gönderilecek." if yeni_mod == "gercek" \
        else "Sanal moda dönüldü. Gerçek hesaba emir gönderilmeyecek."


class GercekYurutucu:
    """Gerçek modda günlük çalışma: kurumla uzlaş, karar ver, yarının emirlerini gönder."""

    def __init__(self, ayarlar, adaptor: KurumAdaptoru, durum: dict | None):
        self.a = ayarlar
        self.k = adaptor
        self.c = IslemCekirdegi.durumdan(ayarlar, durum) if durum else IslemCekirdegi(ayarlar, adaptor.nakit())

    def _uzlas(self, tarih: str, barlar: dict) -> list[str]:
        notlar = []
        kurum = self.k.pozisyonlar()
        # kurumda kapanmış (zarar-durdur / hedef / satış gerçekleşmiş) pozisyonlar
        for s in list(self.c.pozisyonlar):
            if s not in kurum or kurum[s]["adet"] <= 0:
                p = self.c.pozisyonlar[s]
                self.k.acik_emirleri_iptal_et(s)  # karşı emir (hedef/stop) açıkta kalmasın
                fiyat = barlar.get(s, {}).get("close", p.son_fiyat)
                self.c._sat(p, fiyat, tarih, p.cikis_isareti or "Kurumda kapandı")
                notlar.append(f"{s} kurumda kapanmış görünüyor; kayıt yaklaşık fiyatla kapatıldı.")
        # dünkü alış emirlerinden gerçekleşenler
        bekleyen = {b.sembol: b for b in self.c.bekleyen}
        for s, bilgi in kurum.items():
            if s in self.c.pozisyonlar or bilgi["adet"] <= 0:
                continue
            b = bekleyen.get(s)
            fiyat = bilgi["maliyet"]
            stop = fiyat - (b.stop_mesafesi if b else self.a.stop_atr * fiyat * 0.03)
            hedef = fiyat + (b.hedef_mesafesi if b else self.a.hedef_atr * fiyat * 0.03)
            self.c.pozisyonlar[s] = Pozisyon(
                sembol=s, adet=int(bilgi["adet"]), giris_fiyati=fiyat, giris_tarihi=tarih,
                stop=stop, hedef=hedef, giris_komisyonu=fiyat * bilgi["adet"] * self.a.komisyon_orani,
                son_fiyat=fiyat, nedenler=b.nedenler if b else ["Kurumda bulunan pozisyon"],
            )
            self.k.emir_gonder(s, "sat", int(bilgi["adet"]), "zarar_durdur", round(stop, 2))
            self.k.emir_gonder(s, "sat", int(bilgi["adet"]), "limit", round(hedef, 2))
            notlar.append(f"{s} alışı gerçekleşti; zarar-durdur ve hedef emirleri kuruma iletildi.")
        self.c.bekleyen = []
        self.c.nakit = self.k.nakit()
        return notlar

    def gun_sonu(self, tarih: str, barlar: dict) -> dict:
        notlar = self._uzlas(tarih, barlar)
        self.c.gunluk_olaylar = []
        self.c._kapanis(tarih, barlar)
        gonderilen = []
        for p in self.c.pozisyonlar.values():
            if p.cikis_isareti:
                self.k.acik_emirleri_iptal_et(p.sembol)
                self.k.emir_gonder(p.sembol, "sat", p.adet, "piyasa")
                gonderilen.append(f"SAT {p.sembol} {p.adet} adet (açılışta) · {p.cikis_isareti}")
        for b in self.c.bekleyen:
            self.k.emir_gonder(b.sembol, "al", b.planlanan_adet, "piyasa")
            gonderilen.append(f"AL {b.sembol} {b.planlanan_adet} adet (açılışta)")
        return {"notlar": notlar, "gonderilen_emirler": gonderilen, "durum": self.c.durum()}
