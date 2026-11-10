# Pusula'yı iPhone'unuza kurma

Toplam süre yaklaşık 15 dakika. Bilgisayarda yapmanız daha kolaydır, iPhone'dan da olur.
Uygulama App Store'a çıkmaz; adresini yalnızca siz bilirsiniz ve veriler şifrelidir.

## 1. GitHub hesabı açın
github.com adresinden ücretsiz hesap açın.

## 2. Yeni depo oluşturun
1. Sağ üstte **+ → New repository**.
2. Ad: tahmin edilmesi zor bir şey seçin (ör. `pusula-7k2m`). Adres bundan oluşacak.
3. **Public** seçin (ücretsiz yayın için gerekli; verileriniz yine de şifreli kalır).
4. **Create repository**.

## 3. Dosyaları yükleyin
1. Depoda **uploading an existing file** bağlantısına tıklayın.
2. Zip'i açtığınız klasördeki her şeyi sürükleyip bırakın (`pusula_motor`, `docs`, `tests`
   klasörleri ve `pusula.py`, `yayinla.py`, `ayarlar.json`, `requirements.txt` dosyaları).
3. **Commit changes**.

`.github` klasörü gizli olduğu için çoğu bilgisayarda sürüklenmez. Onu elle ekleyin:
1. **Add file → Create new file**.
2. Dosya adı kutusuna tam olarak `.github/workflows/gunluk.yml` yazın.
3. Zip'teki `.github/workflows/gunluk.yml` dosyasının içeriğini yapıştırın, **Commit changes**.

## 4. Şifrenizi belirleyin
1. **Settings → Secrets and variables → Actions → New repository secret**.
2. Name: `PUSULA_SIFRE`
3. Secret: en az 12 karakterlik bir şifre. Uygulamayı açarken bunu gireceksiniz; kaybederseniz
   veriler okunamaz, yeni şifre koyup baştan başlarsınız.

## 5. Motorun yazma iznini açın
**Settings → Actions → General → Workflow permissions → Read and write permissions → Save**.

## 6. Yayını açın
**Settings → Pages → Build and deployment → Source: GitHub Actions** seçin.
Adresiniz şöyle olacak: `https://KULLANICI-ADINIZ.github.io/DEPO-ADINIZ/`

## 7. Motoru ilk kez çalıştırın
**Actions → Pusula günlük çalışma → Run workflow**. 2-3 dakika sürer. Yeşil tik görünce hazır.
Bundan sonra hafta içi her gün 18:40'ta kendiliğinden çalışır.

## 8. iPhone'a ekleyin
1. iPhone'da **Safari** ile adresinizi açın.
2. Şifrenizi girin, "Bu cihazda hatırla" işaretli kalsın.
3. Alttaki **Paylaş** düğmesi → **Ana Ekrana Ekle** → **Ekle**.

Artık ana ekranınızda Pusula simgesi var; normal bir uygulama gibi tam ekran açılır.

## Sık karşılaşılanlar
- **"Henüz veri yok"**: 7. adım tamamlanmamış ya da Pages henüz yayınlanmamış. Birkaç dakika bekleyin.
- **"Şifre yanlış"**: uygulamaya girdiğiniz şifre `PUSULA_SIFRE` ile birebir aynı olmalı.
- **Actions kırmızı çarpı**: işin içine tıklayıp hata mesajını bana gönderin.
- **Kuralları değiştirmek**: depodaki `ayarlar.json` dosyasını GitHub'da düzenleyin (kalem simgesi).
  Değişiklik bir sonraki akşam çalışmasında geçerli olur.
