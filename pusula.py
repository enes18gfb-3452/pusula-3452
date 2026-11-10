"""Pusula motoru komut satırı.

  python pusula.py backtest                 # gerçek geçmiş veriyle stratejiyi test et
  python pusula.py backtest --baslangic 2021-01-01
  python pusula.py gunluk                   # kapanıştan sonra çalıştır, sinyaller.json üretir
  python pusula.py mod gercek --onay        # gerçek paraya geç (aracı kurum adaptörü gerekir)
  python pusula.py mod sanal                # sanal moda dön
  python pusula.py --csv klasor ...         # Yahoo yerine kendi CSV verinizi kullanın
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from pusula_motor.araci_kurum import mod_degistir
from pusula_motor.ayarlar import kaydet, yukle
from pusula_motor.backtest import backtest_calistir, ozet_metni
from pusula_motor.gunluk import gunluk_calistir
from pusula_motor.veri import CsvProvider, YahooProvider, evren_yukle


def main(argv=None):
    p = argparse.ArgumentParser(description="Pusula motoru")
    p.add_argument("--ayarlar", default="ayarlar.json")
    p.add_argument("--csv", help="Veri için CSV klasörü (varsayılan: Yahoo Finance)")
    alt = p.add_subparsers(dest="komut", required=True)

    b = alt.add_parser("backtest")
    b.add_argument("--baslangic")
    b.add_argument("--bitis")
    b.add_argument("--cikti", default="backtest_sonuc")

    alt.add_parser("gunluk")

    m = alt.add_parser("mod")
    m.add_argument("yeni_mod", choices=["sanal", "gercek"])
    m.add_argument("--onay", action="store_true", help="Gerçek paraya geçişi onaylıyorum")

    args = p.parse_args(argv)
    if not os.path.exists(args.ayarlar):
        kaydet(yukle("__yok__"), args.ayarlar)
        print(f"Varsayılan ayarlar oluşturuldu: {args.ayarlar}")
    a = yukle(args.ayarlar)
    provider = CsvProvider(args.csv) if args.csv else YahooProvider()

    if args.komut == "backtest":
        veriler = evren_yukle(provider, a.evren)
        try:
            endeks = provider.history(a.benchmark)
        except Exception as e:
            print(f"Uyarı: endeks verisi alınamadı ({e})")
            endeks = None
        s = backtest_calistir(veriler, a, endeks, args.baslangic, args.bitis)
        os.makedirs(args.cikti, exist_ok=True)
        s.islemler.to_csv(os.path.join(args.cikti, "islemler.csv"), index=False)
        s.egri.to_csv(os.path.join(args.cikti, "sermaye_egrisi.csv"))
        with open(os.path.join(args.cikti, "ozet.json"), "w", encoding="utf-8") as f:
            json.dump(s.ozet, f, ensure_ascii=False, indent=2, default=str)
        print(ozet_metni(s.ozet))
        print(f"\nAyrıntılar: {args.cikti}/")

    elif args.komut == "gunluk":
        c = gunluk_calistir(a, provider)
        print(f"Mod: {c['mod']} · veri tarihi: {c['veri_tarihi']}")
        print(f"Özkaynak: {c['portfoy']['ozkaynak']:,.2f} ₺".replace(",", "."))
        for o in c["bugunun_olaylari"]:
            print("  " + o)
        for y in c["yarin_alinacak"]:
            print(f"  YARIN AL {y['sembol']} {y['planlanan_adet']} adet (~{y['yaklasik_fiyat']} ₺, {y['guc']})")
        for x in c["acik_pozisyonlar"]:
            if x["yarin_satilacak"]:
                print(f"  YARIN SAT {x['sembol']} · {x['satis_nedeni']}")
        print("sinyaller.json güncellendi.")

    elif args.komut == "mod":
        try:
            print(mod_degistir(args.yeni_mod, args.onay, args.ayarlar))
        except Exception as e:
            print(f"Mod değiştirilemedi: {e}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
