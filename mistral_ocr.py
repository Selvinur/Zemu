"""
mistral_ocr.py — PDF'leri Mistral OCR API ile işleyip metin + görsel çıkarır.

Kullanım:
  1) MISTRAL_API_KEY ortam değişkenini ayarla
  2) python mistral_ocr.py

Girdi:  kaynaklar/*.pdf
Çıktı:  data/ocr_raw/{test_adi}.json   (ham OCR yanıtı)
        data/images/{test_adi}/         (çıkarılan görseller)
"""

import os
import sys
import json
import base64
from pathlib import Path
from mistralai.client import Mistral

# ── Ayarlar ──────────────────────────────────────────────
KAYNAK_KLASORU = Path(r"D:\zemu\kaynaklar")
OCR_RAW_KLASORU = Path(r"D:\zemu\data\ocr_raw")
IMAGES_KLASORU = Path(r"D:\zemu\data\images")

# ── API key kontrolü ────────────────────────────────────
api_key = os.environ.get("MISTRAL_API_KEY")

# .env dosyasından da oku (fallback)
if not api_key:
    env_dosyasi = Path(r"D:\zemu\.env")
    if env_dosyasi.exists():
        try:
            env_icerik = env_dosyasi.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            env_icerik = env_dosyasi.read_text(encoding="utf-16")
        for satir in env_icerik.splitlines():
            if satir.startswith("MISTRAL_API_KEY="):
                api_key = satir.split("=", 1)[1].strip().strip("'\"")
                break

if not api_key:
    print("HATA: MISTRAL_API_KEY bulunamadı.")
    print("Seçenek 1: PowerShell'de $env:MISTRAL_API_KEY='sk-xxxxx'")
    print("Seçenek 2: D:\\zemu\\.env dosyasına MISTRAL_API_KEY=sk-xxxxx yaz")
    sys.exit(1)

client = Mistral(api_key=api_key)

# ── Klasörleri oluştur ──────────────────────────────────
OCR_RAW_KLASORU.mkdir(parents=True, exist_ok=True)
IMAGES_KLASORU.mkdir(parents=True, exist_ok=True)

# ── PDF dosyalarını bul ─────────────────────────────────
pdf_dosyalari = list(KAYNAK_KLASORU.glob("*.pdf"))

if not pdf_dosyalari:
    print("kaynaklar/ klasöründe PDF bulunamadı.")
    sys.exit(1)

print(f"{len(pdf_dosyalari)} PDF bulundu.\n")

# ── Her PDF'i işle ──────────────────────────────────────
for pdf_yolu in pdf_dosyalari:
    test_adi = pdf_yolu.stem
    print(f"{'='*60}")
    print(f"İşleniyor: {pdf_yolu.name}")
    print(f"{'='*60}")

    # 1) PDF'i base64 encode et
    with open(pdf_yolu, "rb") as f:
        pdf_base64 = base64.standard_b64encode(f.read()).decode("utf-8")

    print(f"  PDF boyutu: {len(pdf_base64) // 1024} KB (base64)")

    # 2) Mistral OCR API'ye gönder
    print("  OCR işlemi başlatılıyor...")
    try:
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{pdf_base64}"
            },
            include_image_base64=True
        )
    except Exception as e:
        print(f"  HATA: OCR işlemi başarısız — {e}")
        continue

    print(f"  OCR tamamlandı! {len(ocr_response.pages)} sayfa işlendi.")

    # 3) Görselleri kaydet
    gorsel_klasoru = IMAGES_KLASORU / test_adi
    gorsel_klasoru.mkdir(parents=True, exist_ok=True)

    gorsel_haritasi = {}  # placeholder -> gerçek dosya yolu

    for sayfa in ocr_response.pages:
        sayfa_no = sayfa.index
        for img_idx, img in enumerate(sayfa.images):
            # img.id = placeholder adı (ör: "img-0.jpeg")
            # img.image_base64 = base64 encoded görsel
            if not img.image_base64:
                continue

            # Base64 verisinden dosya uzantısını belirle
            if img.image_base64.startswith("data:image/png"):
                uzanti = "png"
                b64_data = img.image_base64.split(",", 1)[1]
            elif img.image_base64.startswith("data:image/jpeg") or img.image_base64.startswith("data:image/jpg"):
                uzanti = "jpg"
                b64_data = img.image_base64.split(",", 1)[1]
            else:
                # Data URI prefix yoksa doğrudan base64
                uzanti = "png"
                b64_data = img.image_base64

            dosya_adi = f"sayfa{sayfa_no}_img{img_idx}.{uzanti}"
            dosya_yolu = gorsel_klasoru / dosya_adi

            try:
                with open(dosya_yolu, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                print(f"  Görsel kaydedildi: {dosya_yolu.name}")
            except Exception as e:
                print(f"  Görsel kaydetme hatası: {e}")
                continue

            # Placeholder → dosya yolu eşlemesi
            placeholder = img.id if hasattr(img, "id") and img.id else f"img-{img_idx}.jpeg"
            gorsel_haritasi[placeholder] = f"data/images/{test_adi}/{dosya_adi}"

    # 4) Ham OCR yanıtını JSON olarak kaydet
    ocr_data = {
        "testAdi": test_adi,
        "sayfaSayisi": len(ocr_response.pages),
        "gorselHaritasi": gorsel_haritasi,
        "sayfalar": []
    }

    for sayfa in ocr_response.pages:
        markdown = sayfa.markdown

        # Markdown'daki görsel placeholder'ları gerçek yollarla değiştir
        for placeholder, gercek_yol in gorsel_haritasi.items():
            markdown = markdown.replace(f"({placeholder})", f"({gercek_yol})")

        ocr_data["sayfalar"].append({
            "sayfaNo": sayfa.index,
            "markdown": markdown,
            "gorselSayisi": len(sayfa.images)
        })

    ocr_json_yolu = OCR_RAW_KLASORU / f"{test_adi}.json"
    with open(ocr_json_yolu, "w", encoding="utf-8") as f:
        json.dump(ocr_data, f, ensure_ascii=False, indent=2)

    print(f"  OCR JSON kaydedildi: {ocr_json_yolu.name}")
    print(f"  Toplam görsel: {len(gorsel_haritasi)}")
    print()

print("="*60)
print("Tüm PDF'ler işlendi!")
print(f"OCR çıktıları: {OCR_RAW_KLASORU}")
print(f"Görseller: {IMAGES_KLASORU}")
print("="*60)
