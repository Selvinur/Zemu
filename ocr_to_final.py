"""
ocr_to_final.py — OCR raw JSON dosyalarını okuyup tests_final.json üretir.

Girdi:  data/ocr_raw/*.json  (mistral_ocr.py çıktıları)
Çıktı:  data/tests_final.json

Bu script, eski çok adımlı pipeline'ın (sorulari_parcala + cevap_anahtarini_isle)
tek adımlık birleştirilmiş halidir.
"""

import json
import re
from pathlib import Path

OCR_RAW_KLASORU = Path(r"D:\zemu\data\ocr_raw")
CIKIS_YOLU = Path(r"D:\zemu\data\tests_final.json")

tum_testler = []

for ocr_dosya in sorted(OCR_RAW_KLASORU.glob("*.json")):
    with open(ocr_dosya, "r", encoding="utf-8") as f:
        ocr_data = json.load(f)

    test_adi = ocr_data["testAdi"]
    print(f"İşleniyor: {test_adi}")

    # Tüm sayfaların markdown'larını birleştir
    tum_markdown = "\n\n".join(s["markdown"] for s in ocr_data["sayfalar"])

    # ── Cevap anahtarını çıkar ──────────────────────────
    cevap_haritasi = {}
    cevap_eslesmesi = re.search(
        r"CEVAP\s*ANAHTARI\s*:?\s*(.*?)(?:\n|$)",
        tum_markdown,
        flags=re.IGNORECASE
    )
    if cevap_eslesmesi:
        cevap_metin = cevap_eslesmesi.group(1)
        parcalar = re.findall(r"(\d+)\s*-\s*([A-Da-d])", cevap_metin)
        for no, harf in parcalar:
            cevap_haritasi[int(no)] = harf.upper()
        print(f"  Cevap anahtarı bulundu: {len(cevap_haritasi)} cevap")

    # ── Soruları ayrıştır ───────────────────────────────
    # Cevap anahtarı satırını ve sonrasını kaldır
    temiz_markdown = re.sub(
        r"CEVAP\s*ANAHTARI\s*:?.*$",
        "",
        tum_markdown,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Soru numarası ile başlayan blokları ayır
    # Örn: "1. ...", "2. ..." veya "1." paragraf başında
    soru_bloklari = re.split(r"\n(?=\d+\.\s)", temiz_markdown)

    sorular = []
    for blok in soru_bloklari:
        blok = blok.strip()
        if not blok:
            continue

        # Soru numarasını al
        numara_eslesme = re.match(r"^(\d+)\.\s*(.*)", blok, re.DOTALL)
        if not numara_eslesme:
            continue

        soru_no = int(numara_eslesme.group(1))
        soru_icerik = numara_eslesme.group(2).strip()

        # Şıkları ayır (A), B), C), D) veya A) B) C) D))
        secenekler = {"A": "", "B": "", "C": "", "D": ""}
        soru_metni = soru_icerik

        # Şıkları bul — çok satırlı destek
        secenek_eslesmesi = re.search(
            r"A\)\s*(.*?)\s*B\)\s*(.*?)\s*C\)\s*(.*?)\s*D\)\s*(.*?)$",
            soru_icerik,
            re.DOTALL
        )

        if secenek_eslesmesi:
            # Soru metni = şıklardan önceki kısım
            soru_metni = soru_icerik[:secenek_eslesmesi.start()].strip()
            secenekler["A"] = secenek_eslesmesi.group(1).strip()
            secenekler["B"] = secenek_eslesmesi.group(2).strip()
            secenekler["C"] = secenek_eslesmesi.group(3).strip()
            secenekler["D"] = secenek_eslesmesi.group(4).strip()

        # Görselleri soru metnine dahil et (markdown img formatında)
        gorseller = re.findall(r"!\[.*?\]\((.*?)\)", soru_metni)

        sorular.append({
            "soruNo": soru_no,
            "soruMetni": soru_metni,
            "secenekler": secenekler,
            "dogruCevap": cevap_haritasi.get(soru_no, ""),
            "gorseller": gorseller
        })

    # Soru numarasına göre sırala ve tekrarları kaldır
    gorulen = set()
    benzersiz_sorular = []
    for s in sorted(sorular, key=lambda x: x["soruNo"]):
        if s["soruNo"] not in gorulen:
            gorulen.add(s["soruNo"])
            benzersiz_sorular.append(s)

    tum_testler.append({
        "testId": test_adi,
        "testAdi": test_adi.replace("_", " ").replace("-", " "),
        "soruSayisi": len(benzersiz_sorular),
        "sorular": benzersiz_sorular
    })

    print(f"  {len(benzersiz_sorular)} soru ayrıştırıldı.")

# ── JSON olarak kaydet ──────────────────────────────────
with open(CIKIS_YOLU, "w", encoding="utf-8") as f:
    json.dump(tum_testler, f, ensure_ascii=False, indent=2)

print(f"\nBitti! {CIKIS_YOLU} oluşturuldu. ({len(tum_testler)} test)")
