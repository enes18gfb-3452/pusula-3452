"""Motorun tüm ayarları. ayarlar.json dosyasından okunur, yoksa varsayılanlar kullanılır."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields

# Örnek evren: likit, büyük BIST hisseleri. BIST 30 listesi dönem dönem değişir;
# kullanmadan önce güncel listeyle karşılaştırın.
VARSAYILAN_EVREN = [
    "AKBNK", "ASELS", "BIMAS", "EKGYO", "ENKAI", "EREGL", "FROTO", "GARAN",
    "ISCTR", "KCHOL", "KRDMD", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE",
    "TCELL", "THYAO", "TOASO", "TUPRS", "YKBNK", "TTKOM", "AEFES", "MGROS",
    "TAVHL", "ALARK",
]


@dataclass
class Ayarlar:
    # --- Genel ---
    mod: str = "sanal"                 # "sanal" veya "gercek"
    baslangic_sermaye: float = 100_000.0
    evren: list = field(default_factory=lambda: list(VARSAYILAN_EVREN))
    benchmark: str = "XU100"

    # --- Strateji: haftalık geri çekilme ---
    trend_sma: int = 200               # ana trend filtresi
    orta_sma: int = 50                 # orta vade trend teyidi
    cikis_sma: int = 5                 # fiyat bunun üstünde kapanınca kâr al
    rsi_periyot: int = 2
    rsi_giris: float = 10.0            # RSI bunun altındaysa geri çekilme var
    rsi_guclu: float = 5.0             # bunun altı "güçlü" sayılır
    hacim_carpani: float = 1.5         # hacim 20 gün ortalamasının bu katıysa +1 güç
    atr_periyot: int = 14
    stop_atr: float = 2.0              # zarar-durdur = giriş - 2 x ATR
    hedef_atr: float = 2.0             # hedef = giriş + 2 x ATR
    max_gun: int = 4                   # 4. günün kapanışında hâlâ açıksa 5. gün açılışta çık
    min_gunluk_islem_tl: float = 50_000_000.0
    min_guc: int = 1                   # 1 = zayıf dahil, 2 = orta ve güçlü, 3 = sadece güçlü

    # --- Risk ---
    islem_basina_risk: float = 0.01    # her işlemde sermayenin en fazla %1'i riske girer
    max_pozisyon_orani: float = 0.20   # tek hisseye en fazla %20
    max_pozisyon_sayisi: int = 5
    max_dusus_durdur: float = 0.10     # zirveden %10 düşüşte yeni işlem açma

    # --- Maliyet (aracı kurumunuza göre güncelleyin) ---
    komisyon_orani: float = 0.002      # alış ve satışta ayrı ayrı (BSMV dahil varsayım)
    kayma_orani: float = 0.001         # piyasa emrinde fiyat kayması varsayımı

    # --- Gerçek mod bağlantısı ---
    araci_kurum_adaptoru: str = ""     # örn. "benim_adaptorum:KurumAdaptoru"

    def dogrula(self) -> None:
        if self.mod not in ("sanal", "gercek"):
            raise ValueError("mod 'sanal' veya 'gercek' olmalı")
        if not 0 < self.islem_basina_risk <= 0.05:
            raise ValueError("islem_basina_risk 0 ile 0.05 arasında olmalı")
        if not 0 < self.max_pozisyon_orani <= 1:
            raise ValueError("max_pozisyon_orani 0 ile 1 arasında olmalı")
        if self.max_gun < 1 or self.max_gun > 5:
            raise ValueError("max_gun 1 ile 5 arasında olmalı (en fazla 1 hafta)")
        if self.stop_atr <= 0 or self.hedef_atr <= 0:
            raise ValueError("stop_atr ve hedef_atr pozitif olmalı")


def yukle(yol: str = "ayarlar.json") -> Ayarlar:
    a = Ayarlar()
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            veri = json.load(f)
        gecerli = {f.name for f in fields(Ayarlar)}
        for k, v in veri.items():
            if k in gecerli:
                setattr(a, k, v)
    a.dogrula()
    return a


def kaydet(a: Ayarlar, yol: str = "ayarlar.json") -> None:
    a.dogrula()
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(asdict(a), f, ensure_ascii=False, indent=2)
