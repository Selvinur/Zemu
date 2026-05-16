"""
bozuklari_onar.py — Eski pipeline'ın bozuk sorularını OCR verisiyle onarır.

Girdi:
  - data/tests_marked.json   (eski pipeline: soru yapısı + bozukluk bayrakları + cevap anahtarı)
  - data/ocr_raw/*.json       (Mistral OCR: zengin markdown + görseller)

Çıktı:
  - data/tests_final.json     (onarılmış, kullanıma hazır test verisi)

Strateji:
  1) tests_marked.json'dan tüm testleri ve bozukluk bilgilerini oku
  2) OCR raw verilerinden soru bazında markdown haritası oluştur
  3) Her bozuk soruyu, bozukluk nedenine göre OCR verisiyle tamir et
  4) Eski pipeline'da eksik olan soruları (3, 6 gibi) tamamen OCR'dan al
"""

import json
import re
from pathlib import Path

# ── Yollar ──────────────────────────────────────────────
MARKED_YOLU = Path(r"D:\zemu\data\tests_marked.json")
OCR_RAW_KLASORU = Path(r"D:\zemu\data\ocr_raw")
CIKIS_YOLU = Path(r"D:\zemu\data\tests_final.json")

# ── tests_marked.json oku ───────────────────────────────
with open(MARKED_YOLU, "r", encoding="utf-8") as f:
    testler = json.load(f)

print(f"tests_marked.json okundu: {len(testler)} test\n")


# ═══════════════════════════════════════════════════════════
# OCR verisinden soru haritası oluştur
# ═══════════════════════════════════════════════════════════
def ocr_soru_haritasi_olustur(ocr_data):
    """
    OCR JSON'dan {soruNo: {...}} şeklinde soru haritası döner.
    Her soru: soruMetni, secenekler, gorseller içerir.
    """
    # Tüm sayfaların markdown'larını birleştir
    tum_markdown = "\n\n".join(s["markdown"] for s in ocr_data["sayfalar"])

    # Cevap anahtarını ve sonrasını kaldır
    temiz_markdown = re.sub(
        r"CEVAP\s*ANAHTARI\s*:?.*$",
        "",
        tum_markdown,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Sayfa başlıklarını ve gereksiz satırları temizle
    temiz_markdown = re.sub(r"S\.\s*Sınıf", "", temiz_markdown)
    temiz_markdown = re.sub(r"\d+\.\s*Sınıf", "", temiz_markdown)
    temiz_markdown = re.sub(r"Matematik\n", "", temiz_markdown)
    temiz_markdown = re.sub(r"Dersim\s+T\w+\s+T\w+", "", temiz_markdown)
    temiz_markdown = re.sub(
        r"YALOVA\s+ÜÇME\s+DEĞERLENDİRME\s+MERKEZİ.*?MATEMATİK",
        "",
        temiz_markdown,
        flags=re.DOTALL
    )
    # "8. End" gibi artıkları temizle
    temiz_markdown = re.sub(r"\d+\.\s*End\b", "", temiz_markdown)
    # "B. Örnü" gibi artıkları temizle
    temiz_markdown = re.sub(r"[A-Z]\.\s*Örn\w*", "", temiz_markdown)

    # Soru bloklarına ayır
    # Soru numarasıyla başlayan blokları yakala
    soru_bloklari = re.split(r"\n(?=\d+\.\s)", temiz_markdown)

    harita = {}

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

        # Tekrar eden soru numaralarını birleştir (ilkine ekle)
        if soru_no in harita:
            # Eğer mevcut giriş şıksızsa ve bu blokta şıklar varsa, üzerine yaz
            if not any(harita[soru_no]["secenekler"].values()):
                # Bu blokta şıklar var mı kontrol et
                if re.search(r"A\)", soru_icerik):
                    pass  # Aşağıda parse edilecek, üzerine yazılacak
                else:
                    continue
            else:
                continue

        # Görselleri bul
        gorseller = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", soru_icerik)

        # Şıkları ayır
        secenekler = {"A": "", "B": "", "C": "", "D": ""}
        soru_metni = soru_icerik

        # Şıkları bul — A) ... B) ... C) ... D) ...
        secenek_eslesmesi = re.search(
            r"A\)\s*(.*?)\s*B\)\s*(.*?)\s*C\)\s*(.*?)\s*D\)\s*(.*?)$",
            soru_icerik,
            re.DOTALL
        )

        if secenek_eslesmesi:
            soru_metni = soru_icerik[:secenek_eslesmesi.start()].strip()
            secenekler["A"] = secenek_eslesmesi.group(1).strip()
            secenekler["B"] = secenek_eslesmesi.group(2).strip()
            secenekler["C"] = secenek_eslesmesi.group(3).strip()
            secenekler["D"] = secenek_eslesmesi.group(4).strip()

        # Şıklardan görsel referanslarını temizle
        for harf in ["A", "B", "C", "D"]:
            secenekler[harf] = re.sub(r"!\[.*?\]\(.*?\)", "", secenekler[harf]).strip()
            # Baştaki/sondaki boş satırları temizle
            secenekler[harf] = secenekler[harf].strip("\n ").strip()

        # Eğer bu soru zaten haritada varsa (duplicate), birleştir
        if soru_no in harita:
            eski = harita[soru_no]
            # Şıksız olana şıklı olanı tercih et
            if not any(eski["secenekler"].values()) and any(secenekler.values()):
                eski["secenekler"] = secenekler
                eski["soruMetni"] = soru_metni if soru_metni else eski["soruMetni"]
            # Görselleri birleştir
            mevcut_yollar = {g["yol"] for g in eski["gorseller"]}
            for g in [{"alt": g[0], "yol": g[1]} for g in gorseller]:
                if g["yol"] not in mevcut_yollar:
                    eski["gorseller"].append(g)
        else:
            harita[soru_no] = {
                "soruMetni": soru_metni,
                "secenekler": secenekler,
                "gorseller": [{"alt": g[0], "yol": g[1]} for g in gorseller],
                "hamMarkdown": blok
            }

    return harita


# ═══════════════════════════════════════════════════════════
# OCR verilerini test adına göre eşle
# ═══════════════════════════════════════════════════════════
ocr_haritalar = {}  # testId → {soruNo: {...}}

for ocr_dosya in OCR_RAW_KLASORU.glob("*.json"):
    with open(ocr_dosya, "r", encoding="utf-8") as f:
        ocr_data = json.load(f)
    test_adi = ocr_data["testAdi"]
    ocr_haritalar[test_adi] = ocr_soru_haritasi_olustur(ocr_data)
    print(f"OCR haritasi olusturuldu: {test_adi} -> {len(ocr_haritalar[test_adi])} soru")

print()


# ═══════════════════════════════════════════════════════════
# Bozuk soruları onar
# ═══════════════════════════════════════════════════════════
def gorsel_referansi_ekle(soru_metni, ocr_gorseller):
    """OCR'dan gelen görsel referanslarını soru metnine ekler."""
    if not ocr_gorseller:
        return soru_metni

    # Zaten görsel referansı varsa ekleme
    if "![" in soru_metni:
        return soru_metni

    # Görselleri soru metninin sonuna ekle
    for gorsel in ocr_gorseller:
        soru_metni += f"\n\n![{gorsel['alt']}]({gorsel['yol']})"

    return soru_metni


def secenekleri_onar(eski_secenekler, ocr_secenekler, sebepler):
    """Boş veya yapışık şıkları OCR'dan alır."""
    bos_siklar = any("şıkkı boş" in s for s in sebepler)
    uzun_siklar = any("şıkkı çok uzun" in s for s in sebepler)

    if bos_siklar or uzun_siklar:
        # Herhangi bir şık bozuksa, TÜM şıkları OCR'dan al
        # (çünkü D şıkkı da genelde bozuk oluyor ama tespit edilemiyor)
        ocr_dolu = any(ocr_secenekler.get(h, "").strip() for h in ["A", "B", "C", "D"])
        if ocr_dolu:
            yeni_secenekler = {}
            for harf in ["A", "B", "C", "D"]:
                ocr_sik = ocr_secenekler.get(harf, "").strip()
                # Görsel referanslarını şıklardan temizle
                ocr_sik = re.sub(r"!\[.*?\]\(.*?\)", "", ocr_sik).strip("\n ").strip()
                yeni_secenekler[harf] = ocr_sik
            return yeni_secenekler

    return dict(eski_secenekler)


def soru_metnini_onar(eski_metin, ocr_metin, sebepler):
    """Karakter bozulması veya kısa metin durumunda OCR metnini kullanır."""
    karakter_bozuk = any("sembol/karakter bozulması" in s for s in sebepler)
    cok_kisa = any("soru metni çok kısa" in s for s in sebepler)

    if karakter_bozuk or cok_kisa:
        if ocr_metin and len(ocr_metin) > len(eski_metin.strip()):
            return ocr_metin

    return eski_metin


def cevap_anahtarini_temizle(secenekler):
    """D şıkkındaki cevap anahtarı kalıntılarını temizler."""
    if "D" in secenekler:
        secenekler["D"] = re.sub(
            r"CEVAP\s*ANAHTARI\s*:?.*$",
            "",
            secenekler["D"],
            flags=re.IGNORECASE
        ).strip()
    return secenekler


# ── Ana onarım döngüsü ─────────────────────────────────
toplam_onarilan = 0
toplam_eklenen = 0

for test in testler:
    test_id = test.get("testId", "")
    test_adi = test.get("testAdi", "")

    # Bu test için OCR haritasını bul
    ocr_harita = ocr_haritalar.get(test_id, {})

    if not ocr_harita:
        print(f"[!] OCR verisi bulunamadi: {test_id}")
        continue

    print(f"{'='*60}")
    print(f"Test: {test_adi}")
    print(f"{'='*60}")

    # Eski pipeline'da mevcut soru numaralarını topla
    mevcut_soru_nolari = {s["soruNo"] for s in test.get("sorular", [])}

    # OCR'da olup eski pipeline'da olmayan soruları ekle
    for soru_no, ocr_soru in sorted(ocr_harita.items()):
        if soru_no not in mevcut_soru_nolari:
            # Tamamen OCR'dan al
            yeni_soru = {
                "soruNo": soru_no,
                "soruMetni": ocr_soru["soruMetni"],
                "secenekler": ocr_soru["secenekler"],
                "dogruCevap": "",  # Cevap anahtarı eski pipeline'dan gelecek
                "ipucu": "",
                "hamMetin": "",
                "bozukMu": False,
                "apiGerekli": False,
                "bozukSebepleri": [],
                "kaynakOCR": True
            }

            # Görselleri ekle
            yeni_soru["soruMetni"] = gorsel_referansi_ekle(
                yeni_soru["soruMetni"], ocr_soru["gorseller"]
            )

            test["sorular"].append(yeni_soru)
            toplam_eklenen += 1
            print(f"  [+] Soru {soru_no}: OCR'dan eklendi (eski pipeline'da yoktu)")

    # Soruları numara sırasına göre sırala
    test["sorular"].sort(key=lambda s: s.get("soruNo", 0))

    # Bozuk soruları onar
    for soru in test.get("sorular", []):
        soru_no = soru.get("soruNo")
        sebepler = soru.get("bozukSebepleri", [])
        bozuk_mu = soru.get("bozukMu", False)

        if not bozuk_mu:
            print(f"  [OK] Soru {soru_no}: Zaten temiz")
            continue

        ocr_soru = ocr_harita.get(soru_no)
        if not ocr_soru:
            print(f"  [!] Soru {soru_no}: OCR karsiligi bulunamadi, atlaniyor")
            continue

        print(f"  [ONARIM] Soru {soru_no}: Onariliyor... (sebepler: {', '.join(sebepler)})")

        onarim_yapildi = []

        # 1) Görsel/şekil içeren soru → OCR'dan görsel ekle
        if any("görsel" in s or "şekil" in s for s in sebepler):
            eski_metin = soru["soruMetni"]
            soru["soruMetni"] = gorsel_referansi_ekle(
                soru["soruMetni"], ocr_soru["gorseller"]
            )
            if soru["soruMetni"] != eski_metin:
                onarim_yapildi.append("görsel eklendi")

        # 2) Boş şıklar / yapışık şıklar → OCR'dan şıkları al
        if any("şıkkı boş" in s or "şıkkı çok uzun" in s for s in sebepler):
            eski_secenekler = dict(soru["secenekler"])
            soru["secenekler"] = secenekleri_onar(
                soru["secenekler"], ocr_soru["secenekler"], sebepler
            )
            if soru["secenekler"] != eski_secenekler:
                onarim_yapildi.append("şıklar onarıldı")

        # 3) Sembol/karakter bozulması → OCR metnini kullan
        if any("sembol" in s or "karakter" in s for s in sebepler):
            eski_metin = soru["soruMetni"]
            soru["soruMetni"] = soru_metnini_onar(
                soru["soruMetni"], ocr_soru["soruMetni"], sebepler
            )
            if soru["soruMetni"] != eski_metin:
                onarim_yapildi.append("metin onarıldı")

        # 4) Cevap anahtarı karışmış → D şıkkını temizle
        if any("cevap anahtarı" in s for s in sebepler):
            eski_d = soru["secenekler"].get("D", "")
            soru["secenekler"] = cevap_anahtarini_temizle(soru["secenekler"])
            if soru["secenekler"].get("D", "") != eski_d:
                onarim_yapildi.append("cevap anahtarı temizlendi")

        # 5) Soru metni çok kısa → OCR'dan al
        if any("soru metni çok kısa" in s for s in sebepler):
            eski_metin = soru["soruMetni"]
            soru["soruMetni"] = soru_metnini_onar(
                soru["soruMetni"], ocr_soru["soruMetni"], sebepler
            )
            if soru["soruMetni"] != eski_metin:
                onarim_yapildi.append("kısa metin genişletildi")

        # Onarım durumunu güncelle
        if onarim_yapildi:
            soru["bozukMu"] = False
            soru["onarildi"] = True
            soru["onarimDetaylari"] = onarim_yapildi
            toplam_onarilan += 1
            print(f"     [TAMAM] Onarimlar: {', '.join(onarim_yapildi)}")
        else:
            # OCR'dan komple al (fallback)
            soru["soruMetni"] = gorsel_referansi_ekle(
                ocr_soru["soruMetni"], ocr_soru["gorseller"]
            )
            soru["secenekler"] = ocr_soru["secenekler"]
            soru["bozukMu"] = False
            soru["onarildi"] = True
            soru["onarimDetaylari"] = ["OCR'dan tamamen yeniden alındı"]
            toplam_onarilan += 1
            print(f"     [TAMAM] Fallback: OCR'dan tamamen alindi")

    # Cevap anahtarını OCR'dan da kontrol et
    # (Eski pipeline'da eksik olan soruların cevap anahtarını OCR'dan al)
    ocr_dosya_yolu = OCR_RAW_KLASORU / f"{test_id}.json"
    tum_markdown = ""
    if ocr_dosya_yolu.exists():
        with open(ocr_dosya_yolu, "r", encoding="utf-8") as f:
            ocr_raw = json.load(f)
        tum_markdown = "\n\n".join(s["markdown"] for s in ocr_raw["sayfalar"])

    cevap_eslesmesi = re.search(
        r"CEVAP\s*ANAHTARI\s*:?\s*(.*?)(?:\n|$)",
        tum_markdown,
        flags=re.IGNORECASE
    )

    if cevap_eslesmesi:
        cevap_metin = cevap_eslesmesi.group(1)
        parcalar = re.findall(r"(\d+)\s*-\s*([A-Da-d])", cevap_metin)
        cevap_haritasi = {int(no): harf.upper() for no, harf in parcalar}

        for soru in test["sorular"]:
            soru_no = soru.get("soruNo")
            if not soru.get("dogruCevap") and soru_no in cevap_haritasi:
                soru["dogruCevap"] = cevap_haritasi[soru_no]
                print(f"  [CEVAP] Soru {soru_no}: Cevap anahtari eklendi -> {cevap_haritasi[soru_no]}")

    print()

# ── Sonucu kaydet ───────────────────────────────────────
# Son temizlik: tüm sorulara genel düzeltmeler uygula
for test in testler:
    for soru in test.get("sorular", []):
        soru.pop("apiGerekli", None)

        secenekler = soru.get("secenekler", {})

        # D şıkkından cevap anahtarı kalıntılarını temizle (tüm sorularda)
        if "D" in secenekler:
            secenekler["D"] = re.sub(
                r"\s*CEVAP\s*ANAHTARI\s*:?.*$",
                "",
                secenekler["D"],
                flags=re.IGNORECASE
            ).strip()
            # Soru numarası kalıntılarını temizle (ör: "1-B, 2-D...")
            secenekler["D"] = re.sub(
                r"\s*\d+-[A-D],?\s*\d+-[A-D].*$",
                "",
                secenekler["D"],
                flags=re.IGNORECASE
            ).strip()

        # Tüm şıklardan markdown tablo referanslarını düzelt
        for harf in ["A", "B", "C", "D"]:
            sik = secenekler.get(harf, "")
            # [tbl-X.md](tbl-X.md) referanslarını kaldır
            sik = re.sub(r"\[tbl-\d+\.md\]\(tbl-\d+\.md\)", "", sik).strip()
            # Soru metninden soru numarası kalıntılarını temizle
            sik = re.sub(r"^\d+\.\s*", "", sik).strip() if re.match(r"^\d+\.\s", sik) else sik
            # Yapışık soru numaralarını temizle (ör: "6 ve 7. soruları...")
            sik = re.sub(r"\s+\d+\s+ve\s+\d+\.\s+sorular.*$", "", sik, flags=re.DOTALL).strip()
            secenekler[harf] = sik

        # Soru metninden baştaki soru numarasını kaldır (ör: "1. ...")
        metin = soru.get("soruMetni", "")
        metin = re.sub(r"^\d+\.\s*", "", metin).strip()
        soru["soruMetni"] = metin

with open(CIKIS_YOLU, "w", encoding="utf-8") as f:
    json.dump(testler, f, ensure_ascii=False, indent=2)

print("=" * 60)
print(f"TAMAMLANDI! {CIKIS_YOLU}")
print(f"   Onarılan soru: {toplam_onarilan}")
print(f"   Eklenen soru:  {toplam_eklenen}")
print("=" * 60)
