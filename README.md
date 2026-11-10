# Pusula Motoru

BIST hisselerinde **en fazla 1 hafta** elde tutulan işlemler için sinyal ve işlem motoru.
Gerçek piyasa verisiyle çalışır. Önce sanal parayla işlem yapar; tek komutla (uygulamada tek
butonla) gerçek paraya geçer.

> Yatırım tavsiyesi değildir. Kısa vadeli işlem uzun vadeli yatırımdan daha risklidir ve
> kâr garantisi yoktur. Gerçek paraya geçmeden önce backtest ve sanal mod sonuçlarına bakın.

## Kurulum

```bash
pip install -r requirements.txt
```

## Kullanım

```bash
python pusula.py backtest                       # gerçek geçmiş veriyle strateji testi
python pusula.py backtest --baslangic 2021-01-01
python pusula.py gunluk                         # her işlem günü kapanıştan sonra (ör. 18:30)
python pusula.py mod gercek --onay              # gerçek paraya geç
python pusula.py mod sanal                      # sanal moda dön
python -m unittest tests.test_motor -v          # testler
```

İlk çalıştırmada `ayarlar.json` oluşur; tüm kurallar oradan değiştirilir.

## Strateji: haftalık geri çekilme

Ana trendi yukarı olan likit bir hisse birkaç günde sert düştüğünde, kısa süreli toparlanmanın
bir kısmını alıp çıkmayı hedefler.

**Giriş** (kapanışa göre, ertesi gün açılışta):
1. Fiyat 200 günlük ortalamanın üstünde ve 50 günlük ort. 200 günlüğün üstünde (trend yukarı)
2. RSI(2) < 10 (sert kısa vadeli düşüş)
3. 20 günlük ortalama işlem hacmi ≥ 50 milyon ₺ (likidite)

Sinyal gücü: RSI(2) < 5 ise +1, hacim 20 günlük ortalamanın 1,5 katıysa +1 (zayıf / orta / güçlü).

**Çıkış** (hangisi önce olursa):
| Kural | Ne zaman |
|---|---|
| Zarar-durdur | Giriş − 2 × ATR, gün içinde dokunursa |
| Hedef | Giriş + 2 × ATR, gün içinde dokunursa |
| Toparlanma bitti | Kapanış 5 günlük ortalamanın üstündeyse ertesi açılışta |
| Süre doldu | 4. günün kapanışında hâlâ açıksa 5. gün açılışında (en fazla 1 hafta) |

**Risk:** her işlemde sermayenin en fazla %1'i riske girer, tek hisseye en fazla %20,
en fazla 5 açık pozisyon. Sermaye zirveden %10 düşerse yeni işlem açılmaz.

## Veri

Varsayılan kaynak Yahoo Finance (`THYAO` → `THYAO.IS`): ücretsiz, günlük ve gecikmeli.
Strateji gün sonu kapanışla karar verdiği için gecikme sorun değildir. Ticari kullanım için
lisanslı bir veri sağlayıcıya geçin (`veri.py` içinde `DataProvider` sınıfından türetin) ya
da `--csv klasor` ile kendi verinizi verin.

## Sanal ve gerçek mod

- **Sanal:** kararlar gerçek veriyle alınır, emirler simüle edilir. Durum `durum_sanal.json`.
- **Gerçek:** aynı kararlar aracı kurumunuza emir olarak gider. Durum `durum_gercek.json`.

Gerçek mod için kurumunuzun API'sine bağlanan bir adaptör gerekir: `araci_kurum.py` içindeki
`KurumAdaptoru` sınıfını kurumunuzun API'siyle doldurun ve `ayarlar.json` içinde
`"araci_kurum_adaptoru": "modul_adi:SinifAdi"` olarak girin. Adaptör yoksa, bağlantı testi
başarısızsa ya da onay verilmezse motor gerçek moda geçmez.

## Uygulamayla bağlantı

`gunluk` komutu `sinyaller.json` üretir: portföy, açık pozisyonlar, yarın alınacak ve
satılacak hisseler, her birinin zarar-durdur/hedef seviyesi, en kötü senaryo kaybı ve sade
dilde nedenleri. Mobil uygulama bu dosyayı (ileride bir API üzerinden) okur.

## Dosyalar

| Dosya | Görev |
|---|---|
| `pusula_motor/ayarlar.py` | Tüm kurallar ve sınırlar |
| `pusula_motor/veri.py` | Gerçek veri (Yahoo, CSV) |
| `pusula_motor/gostergeler.py` | SMA, RSI, ATR |
| `pusula_motor/strateji.py` | Giriş ve çıkış kuralları, nedenler |
| `pusula_motor/risk.py` | Pozisyon büyüklüğü, düşüş freni |
| `pusula_motor/cekirdek.py` | Gün gün işlem simülasyonu (backtest ve sanal mod ortak) |
| `pusula_motor/backtest.py` | Geçmiş test ve rapor |
| `pusula_motor/gunluk.py` | Günlük çalışma, `sinyaller.json` |
| `pusula_motor/araci_kurum.py` | Mod geçişi, gerçek mod yürütücüsü, kurum adaptörü arayüzü |
