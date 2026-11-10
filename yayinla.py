"""Motoru çalıştırır, sonucu şifreleyip docs/ klasörüne koyar (telefon uygulaması oradan okur).

GitHub Actions her iş günü akşamı bunu çalıştırır. Şifre PUSULA_SIFRE ortam değişkeninden
gelir; uygulamada da aynı şifreyi girersiniz. Depo herkese açık olsa bile verileriniz
şifresi olmadan okunamaz.

  PUSULA_SIFRE=... python yayinla.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from datetime import date, timedelta

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pusula_motor.ayarlar import yukle
from pusula_motor.gunluk import DURUM_DOSYASI, gunluk_calistir
from pusula_motor.veri import YahooProvider

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
TEKRAR = 250_000


def _anahtar(sifre: str, tuz: bytes) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=tuz, iterations=TEKRAR).derive(sifre.encode())


def sifrele(veri: dict, sifre: str) -> dict:
    tuz, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_anahtar(sifre, tuz)).encrypt(iv, json.dumps(veri, ensure_ascii=False, default=str).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": TEKRAR, "salt": b(tuz), "iv": b(iv), "ct": b(ct)}


def coz(paket: dict, sifre: str) -> dict:
    d = lambda k: base64.b64decode(paket[k])
    return json.loads(AESGCM(_anahtar(sifre, d("salt"))).decrypt(d("iv"), d("ct"), None))


def _oku(yol):
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    return None


def _yaz(yol, veri):
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False)


def egri_ekle(cikti: dict, durum: dict, provider, benchmark: str) -> None:
    egri = durum.get("ozkaynak_egrisi", [])[-180:]
    nokta = [{"t": t, "oz": round(v, 2)} for t, v in egri]
    if len(nokta) > 1:
        try:
            b = provider.history(benchmark, start=date.fromisoformat(nokta[0]["t"]) - timedelta(days=7))["close"]
            ilk = None
            for n in nokta:
                gecmis = b[b.index <= n["t"]]
                if len(gecmis):
                    ilk = ilk or float(gecmis.iloc[-1])
                    n["endeks"] = round(nokta[0]["oz"] * float(gecmis.iloc[-1]) / ilk, 2)
        except Exception as e:
            print(f"Uyarı: endeks verisi alınamadı ({e})")
    cikti["egri"] = nokta


def main() -> int:
    sifre = os.environ.get("PUSULA_SIFRE", "")
    if len(sifre) < 8:
        print("PUSULA_SIFRE ortam değişkeni en az 8 karakter olmalı.")
        return 1
    os.makedirs(DOCS, exist_ok=True)
    a = yukle("ayarlar.json")
    provider = YahooProvider(cache_klasoru=None)
    durum_enc = os.path.join(DOCS, f"durum_{a.mod}.enc.json")

    with tempfile.TemporaryDirectory() as tmp:
        eski = _oku(durum_enc)
        if eski:
            _yaz(os.path.join(tmp, DURUM_DOSYASI[a.mod]), coz(eski, sifre))
        cikti = gunluk_calistir(a, provider, klasor=tmp)
        durum = _oku(os.path.join(tmp, DURUM_DOSYASI[a.mod]))

    egri_ekle(cikti, durum, provider, a.benchmark)
    cikti["ayarlar"] = {
        "max_gun": a.max_gun, "islem_basina_risk": a.islem_basina_risk,
        "max_pozisyon_sayisi": a.max_pozisyon_sayisi, "baslangic_sermaye": a.baslangic_sermaye,
        "gercek_mod_hazir": bool(a.araci_kurum_adaptoru),
    }
    _yaz(durum_enc, sifrele(durum, sifre))
    _yaz(os.path.join(DOCS, "veri.enc.json"), sifrele(cikti, sifre))
    print(f"Yayınlandı: {cikti['veri_tarihi']} · {len(cikti['yarin_alinacak'])} yeni sinyal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
