from pathlib import Path
import json

GIRIS_YOLU = Path(r"D:\zemu\data\tests_categorized.json")
CIKIS_YOLU = Path(r"D:\zemu\data\tests_with_images.json")
CROP_KLASORU = Path(r"D:\zemu\data\question_crops")


def gorsel_gerekli_mi(soru):
    durum = str(soru.get("durum", "")).upper()
    bozuk_mu = soru.get("bozukMu", False)
    api_gerekli = soru.get("apiGerekli", False)

    if durum in ["BOZUK", "GÖRSEL_İÇERİKLİ", "GORSEL_ICERIKLI"]:
        return True

    if bozuk_mu is True:
        return True

    if api_gerekli is True:
        return True

    return False


with open(GIRIS_YOLU, "r", encoding="utf-8") as f:
    testler = json.load(f)

toplam = 0
gorsel_baglanan = 0
eksik = 0

for test in testler:
    test_id = test.get("testId") or test.get("testAdi") or "bilinmeyen_test"
    test_crop_klasoru = CROP_KLASORU / test_id

    print("=" * 60)
    print(f"Test: {test_id}")

    for soru in test.get("sorular", []):
        soru_no = soru.get("soruNo")

        # Önce herkeste görsel yolunu temizle
        soru["soruGorselPath"] = None

        # Sadece bozuk / görsel içerikli sorulara görsel bağla
        if not gorsel_gerekli_mi(soru):
            continue

        toplam += 1

        beklenen_gorsel = test_crop_klasoru / f"q{soru_no}.png"

        if beklenen_gorsel.exists():
            # HTML için Windows ters slash değil, normal slash kullanıyoruz
            soru["soruGorselPath"] = (
                f"data/question_crops/{test_id}/q{soru_no}.png"
            )
            gorsel_baglanan += 1
            print(f"✓ Soru {soru_no} -> görsel bağlandı")
        else:
            eksik += 1
            print(f"X Soru {soru_no} -> görsel bulunamadı: q{soru_no}.png")

with open(CIKIS_YOLU, "w", encoding="utf-8") as f:
    json.dump(testler, f, ensure_ascii=False, indent=2)

print("=" * 60)
print("tests_with_images.json oluşturuldu")
print(f"Görsel gereken soru: {toplam}")
print(f"Görsel bağlanan: {gorsel_baglanan}")
print(f"Eksik: {eksik}")