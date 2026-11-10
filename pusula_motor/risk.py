"""Pozisyon büyüklüğü ve sermaye koruma kuralları."""
from __future__ import annotations

import math


def adet_hesapla(ozkaynak: float, nakit: float, giris: float, stop: float, a) -> int:
    """Zarar-durdur çalışırsa kayıp sermayenin islem_basina_risk oranını geçmeyecek adet."""
    hisse_basi_risk = giris - stop
    if giris <= 0 or hisse_basi_risk <= 0:
        return 0
    risk_adet = math.floor(ozkaynak * a.islem_basina_risk / hisse_basi_risk)
    tavan_adet = math.floor(ozkaynak * a.max_pozisyon_orani / giris)
    nakit_adet = math.floor(nakit / (giris * (1 + a.komisyon_orani + a.kayma_orani)))
    return max(0, min(risk_adet, tavan_adet, nakit_adet))


def yeni_islem_durdurulsun_mu(ozkaynak: float, zirve: float, a) -> bool:
    return zirve > 0 and (zirve - ozkaynak) / zirve >= a.max_dusus_durdur
