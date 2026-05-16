from pathlib import Path
import json
import re

GIRIS_YOLU = Path(r"D:\zemu\data\tests_with_images.json")
CIKIS_YOLU = Path(r"D:\zemu\data\tests_with_hints.json")


def metni_birlestir(soru):
    parcalar = [
        str(soru.get("soruMetni", "")),
        str(soru.get("hamMetin", "")),
    ]

    secenekler = soru.get("secenekler", {})
    if isinstance(secenekler, dict):
        parcalar.extend(str(v) for v in secenekler.values())

    return " ".join(parcalar).lower()


def ipucu_uret(soru):
    durum = str(soru.get("durum", "")).upper()
    metin = metni_birlestir(soru)

    # Görsel/bozuk sorular
    if durum in ["BOZUK", "GÖRSEL_İÇERİKLİ", "GORSEL_ICERIKLI"] or soru.get("soruGorselPath"):
        if "grafik" in metin:
            return "Grafikte verilen değerleri dikkatlice oku. En büyük, en küçük ya da karşılaştırma isteyen ifadeleri seçeneklerle eşleştir."
        if "tablo" in metin or "sıklık" in metin:
            return "Tablodaki satır ve sütun başlıklarına dikkat et. Verilen bilgileri seçeneklerdeki tabloyla karşılaştır."
        if "açı" in metin or "s(" in metin:
            return "Şekilde verilen açıları incele. Eş, bütünler ya da paralel doğrulardaki açı ilişkilerini düşün."
        if "paralel" in metin or "//" in metin:
            return "Doğruların yönlerini karşılaştır. Paralel doğrular kesişmez ve aynı doğrultuda ilerler."
        return "Soruyu görselden oku. Şekil, tablo veya verilen bilgileri dikkatlice inceleyip aşağıdaki A-B-C-D seçeneklerinden birini seç."

    # Yüzde / oran
    if "%" in metin or "yüzde" in metin:
        return "Yüzdeyi kesir ya da ondalık olarak düşün. Önce verilen kısmı bul, sonra sorunun istediği değeri hesapla."

    # Birim dönüşümü
    if any(kelime in metin for kelime in ["km", "metre", "m ", "cm", "mm", "dm"]):
        return "Önce bütün ölçüleri aynı birime çevir. Sonra eşitlikleri ya da karşılaştırmaları kontrol et."

    # Kesir
    if "kesir" in metin or "/" in metin or "pay" in metin or "payda" in metin:
        return "Kesirde payın ve paydanın neyi temsil ettiğini düşün. İşlem yapmadan önce verilen kurala göre kesri oluştur."

    # Geometri
    if any(kelime in metin for kelime in ["üçgen", "kare", "dikdörtgen", "çokgen", "kenar", "köşe", "köşegen", "paralelkenar"]):
        return "Şeklin özelliklerini hatırla. Kenar, köşe, açı ve köşegen bilgilerini seçeneklerle karşılaştır."

    # Grafik / tablo
    if "grafik" in metin:
        return "Grafikteki değerleri tek tek oku. Sorunun en büyük, en küçük veya fark gibi ne istediğine dikkat et."

    if "tablo" in metin:
        return "Tabloda verilen bilgileri sırayla kontrol et. Seçeneklerdeki değerleri sorudaki koşullarla karşılaştır."

    # İşlem sorusu
    if re.search(r"\d+\s*[\+\-\*/]\s*\d+", metin):
        return "İşlem önceliğine dikkat et. Önce parantez varsa onu, sonra çarpma-bölme ve toplama-çıkarma işlemlerini yap."

    # Genel ipucu
    return "Önce soru kökünde ne istendiğini bul. Sonra seçenekleri tek tek eleyerek doğru cevaba yaklaş."


with open(GIRIS_YOLU, "r", encoding="utf-8") as f:
    testler = json.load(f)

toplam = 0

for test in testler:
    for soru in test.get("sorular", []):
        soru["ipucu"] = ipucu_uret(soru)
        toplam += 1

with open(CIKIS_YOLU, "w", encoding="utf-8") as f:
    json.dump(testler, f, ensure_ascii=False, indent=2)

print(f"Bitti. {toplam} soruya ipucu eklendi.")
print(f"Oluşan dosya: {CIKIS_YOLU}")