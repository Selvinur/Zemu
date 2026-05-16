"""
sorulari_kategorize_et.py — Soruları TEMİZ / GÖRSEL_İÇERİKLİ / BOZUK olarak sınıflandırır.

Girdi:  data/tests_clean.json   (eski parser çıktısı)
Çıktı:  data/tests_categorized.json
        data/kategori_raporu.txt

Pipeline:
  1) Cevap anahtarını ham metinden çıkar
  2) D şıkkından cevap anahtarı / sayfa bilgisi kalıntılarını temizle
  3) Satır bölünme tirelerini düzelt (aşa- ğıdaki → aşağıdaki)
  4) Her soruyu TEMİZ / GÖRSEL_İÇERİKLİ / BOZUK olarak sınıflandır
  5) Cevap anahtarından eksik soruları tespit et ve BOZUK olarak ekle
"""

import json
import re
import sys
import io
from pathlib import Path

# Windows terminal encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── Yollar ──────────────────────────────────────────────
GIRIS_YOLU = Path(r"D:\zemu\data\tests_clean.json")
CIKIS_JSON = Path(r"D:\zemu\data\tests_categorized.json")
CIKIS_RAPOR = Path(r"D:\zemu\data\kategori_raporu.txt")

# ── tests_clean.json oku ────────────────────────────────
with open(GIRIS_YOLU, "r", encoding="utf-8") as f:
    testler = json.load(f)

print(f"tests_clean.json okundu: {len(testler)} test\n")


# ═══════════════════════════════════════════════════════════
# Yardımcı fonksiyonlar
# ═══════════════════════════════════════════════════════════

def metin_temizle(metin):
    """Satır bölünme tirelerini ve gereksiz boşlukları temizler."""
    if not metin:
        return metin
    # "aşa- ğıdaki" → "aşağıdaki" (tire + boşluk + satır sonu)
    metin = re.sub(r'(\w)- (\w)', r'\1\2', metin)
    # "beklenmekte-\ndir" → "beklenmektedir"
    metin = re.sub(r'(\w)-\n(\w)', r'\1\2', metin)
    # Çoklu boşlukları teke indir
    metin = re.sub(r'  +', ' ', metin)
    # Baştaki soru numarasını kaldır
    metin = re.sub(r'^\d+\.\s*', '', metin).strip()
    return metin


def cevap_anahtari_cikar(test):
    """Testteki tüm ham metinlerden cevap anahtarını çıkarır."""
    cevap_haritasi = {}
    for soru in test.get("sorular", []):
        ham = soru.get("hamMetin", "")
        eslesme = re.search(r"CEVAP\s*ANAHTARI\s*:\s*(.*)", ham, flags=re.IGNORECASE)
        if eslesme:
            cevap_metin = eslesme.group(1)
            parcalar = re.findall(r"(\d+)\s*-\s*([A-Da-d])", cevap_metin)
            for no, harf in parcalar:
                cevap_haritasi[int(no)] = harf.upper()
    return cevap_haritasi


def d_sikkini_temizle(secenekler):
    """D şıkkından cevap anahtarı ve sayfa bilgisi kalıntılarını temizler."""
    if "D" not in secenekler:
        return secenekler

    d = secenekler["D"]
    # CEVAP ANAHTARI: ... kaldır
    d = re.sub(r"\s*CEVAP\s*ANAHTARI\s*:?.*$", "", d, flags=re.IGNORECASE).strip()
    # --- SAYFA X --- kaldır
    d = re.sub(r"\s*---\s*SAYFA\s*\d+\s*---.*$", "", d, flags=re.IGNORECASE | re.DOTALL).strip()
    # Sayfa numarası + "Matematik" kalıntıları
    d = re.sub(r"\s*\d+\s+Matematik.*$", "", d, flags=re.DOTALL).strip()
    # Sondaki "% 40" gibi görsel kalıntıları
    d = re.sub(r"\s*%\s*\d+\s*$", "", d).strip()
    # "6 ve 7. soruları aşağıdaki grafiğe göre cevaplayınız." kalıntıları
    d = re.sub(r"\s*\d+\s+ve\s+\d+\.\s+soruları.*$", "", d, flags=re.DOTALL).strip()
    # "Grafik: ..." kalıntıları
    d = re.sub(r"\s*Grafik:.*$", "", d, flags=re.DOTALL).strip()

    secenekler["D"] = d
    return secenekler


def kategorize_et(soru):
    """
    Soruyu analiz edip (durum, sebepler) döner.
    durum: "TEMİZ" | "GÖRSEL_İÇERİKLİ" | "BOZUK"
    """
    sebepler = []
    soru_metni = soru.get("soruMetni", "")
    secenekler = soru.get("secenekler", {})
    ham_metin = soru.get("hamMetin", "")
    birlesik = (soru_metni + " " + ham_metin + " " +
                " ".join(secenekler.values())).lower()

    # ── BOZUK kriterleri ────────────────────────────────

    # 1) Herhangi bir şık boş mu?
    for harf in ["A", "B", "C", "D"]:
        sik = secenekler.get(harf, "").strip()
        if not sik:
            sebepler.append(f"{harf} şıkkı boş")

    # 2) Bir şık çok uzun mu? (>120 karakter = başka soru/şık yapışmış olabilir)
    for harf, metin in secenekler.items():
        if len(metin.strip()) > 120:
            sebepler.append(f"{harf} şıkkı çok uzun ({len(metin)} karakter)")

    # 3) Şık içinde tekrar A) B) C) D) geçiyor mu?
    for harf, metin in secenekler.items():
        # Kendi harfi dışında başka şık harfi var mı?
        diger_harfler = [h for h in ["A", "B", "C", "D"] if h != harf]
        for diger in diger_harfler:
            if re.search(rf"\b{diger}\)\s", metin):
                sebepler.append(f"{harf} şıkkında {diger}) kalıntısı var")
                break

    # 4) Cevap anahtarı şıklara karışmış mı? (temizlemeden sonra hala varsa)
    for harf, metin in secenekler.items():
        if "CEVAP ANAHTARI" in metin.upper():
            sebepler.append("cevap anahtarı hala şıklarda")

    # 5) Sayfa bilgisi şıklara karışmış mı?
    for harf, metin in secenekler.items():
        if re.search(r"---\s*SAYFA", metin, re.IGNORECASE):
            sebepler.append(f"{harf} şıkkında sayfa bilgisi var")

    # 6) Soru metni çok kısa mı?
    if len(soru_metni.strip()) < 10:
        sebepler.append("soru metni çok kısa veya boş")

    # Tekrar eden sebepleri kaldır
    sebepler = list(dict.fromkeys(sebepler))

    if sebepler:
        return "BOZUK", sebepler

    # ── GÖRSEL_İÇERİKLİ kriterleri ─────────────────────
    gorsel_kelimeleri = [
        "şekil", "yandaki", "yukarıdaki", "kareli", "açı",
        "doğru parçası", "konum", "grafik", "tablo", "görsel",
        "resim", "görseldeki", "şekildeki", "aşağıdaki grafik",
        "ekran görüntüsü"
    ]

    metin_kucuk = (soru_metni + " " + ham_metin).lower()
    if any(kelime in metin_kucuk for kelime in gorsel_kelimeleri):
        return "GÖRSEL_İÇERİKLİ", []

    # ── TEMİZ ──────────────────────────────────────────
    return "TEMİZ", []


# ═══════════════════════════════════════════════════════════
# Ana işlem
# ═══════════════════════════════════════════════════════════
rapor_satirlari = ["=" * 60, "KATEGORİ RAPORU", "=" * 60, ""]

genel_sayac = {"TEMİZ": 0, "GÖRSEL_İÇERİKLİ": 0, "BOZUK": 0}
genel_toplam = 0

for test in testler:
    test_id = test.get("testId", "")
    test_adi = test.get("testAdi", "")
    print(f"{'=' * 60}")
    print(f"İşleniyor: {test_adi}")

    # 1) Cevap anahtarını çıkar
    cevap_haritasi = cevap_anahtari_cikar(test)
    if cevap_haritasi:
        print(f"  Cevap anahtarı: {len(cevap_haritasi)} cevap bulundu")

    # 2) Her soruyu işle
    kategori_sayac = {"TEMİZ": 0, "GÖRSEL_İÇERİKLİ": 0, "BOZUK": 0}
    kategori_listesi = {"TEMİZ": [], "GÖRSEL_İÇERİKLİ": [], "BOZUK": []}

    for soru in test.get("sorular", []):
        soru_no = soru.get("soruNo")

        # Cevap anahtarını ata
        if soru_no in cevap_haritasi and not soru.get("dogruCevap"):
            soru["dogruCevap"] = cevap_haritasi[soru_no]

        # D şıkkını temizle
        soru["secenekler"] = d_sikkini_temizle(soru.get("secenekler", {}))

        # Metin temizliği
        soru["soruMetni"] = metin_temizle(soru.get("soruMetni", ""))
        for harf in ["A", "B", "C", "D"]:
            if harf in soru["secenekler"]:
                soru["secenekler"][harf] = metin_temizle(soru["secenekler"][harf])

        # Kategorize et
        durum, sebepler = kategorize_et(soru)

        # Yeni alanları ekle, eski alanları kaldır
        soru["durum"] = durum
        soru["soruGorselPath"] = None
        soru["bozukSebepleri"] = sebepler
        soru["kaynak"] = "old_parser"

        # Eski alanları temizle
        soru.pop("bozukMu", None)
        soru.pop("apiGerekli", None)
        soru.pop("onarildi", None)
        soru.pop("onarimDetaylari", None)
        soru.pop("kaynakOCR", None)
        soru.pop("ipucu", None)
        soru.pop("hamMetin", None)
        soru.pop("gorseller", None)

        kategori_sayac[durum] += 1
        kategori_listesi[durum].append(soru_no)

        sebep_str = f" — {', '.join(sebepler)}" if sebepler else ""
        print(f"  Soru {soru_no:2d}: {durum}{sebep_str}")

    # 3) Eksik soruları tespit et (cevap anahtarından)
    mevcut_nolar = {s["soruNo"] for s in test.get("sorular", [])}
    eksik_nolar = []

    if cevap_haritasi:
        beklenen_nolar = set(cevap_haritasi.keys())
        eksik_nolar = sorted(beklenen_nolar - mevcut_nolar)

        for eksik_no in eksik_nolar:
            eksik_soru = {
                "soruNo": eksik_no,
                "soruMetni": "",
                "secenekler": {"A": "", "B": "", "C": "", "D": ""},
                "dogruCevap": cevap_haritasi.get(eksik_no, ""),
                "durum": "BOZUK",
                "soruGorselPath": None,
                "bozukSebepleri": ["eski parser tarafından çıkarılamadı"],
                "kaynak": "old_parser"
            }
            test["sorular"].append(eksik_soru)
            kategori_sayac["BOZUK"] += 1
            kategori_listesi["BOZUK"].append(eksik_no)
            print(f"  Soru {eksik_no:2d}: BOZUK — eski parser tarafından çıkarılamadı (eklendi)")

    # Soruları numara sırasına göre sırala
    test["sorular"].sort(key=lambda s: s.get("soruNo", 0))

    # Rapor satırlarını oluştur
    rapor_satirlari.append(f"Test: {test_adi}")
    for kat in ["TEMİZ", "GÖRSEL_İÇERİKLİ", "BOZUK"]:
        nolar = sorted(kategori_listesi[kat])
        nolar_str = ", ".join(str(n) for n in nolar) if nolar else "-"
        rapor_satirlari.append(f"  {kat:20s}: {kategori_sayac[kat]:2d} soru  ({nolar_str})")
    if eksik_nolar:
        rapor_satirlari.append(f"  {'EKSİK SORULAR':20s}: {', '.join(str(n) for n in eksik_nolar)}")
    rapor_satirlari.append("")

    for kat in kategori_sayac:
        genel_sayac[kat] += kategori_sayac[kat]
    genel_toplam += sum(kategori_sayac.values())

    print()

# ── Genel rapor ─────────────────────────────────────────
rapor_satirlari.append("-" * 40)
rapor_satirlari.append("GENEL ÖZET")
rapor_satirlari.append(f"  Toplam: {genel_toplam} soru")
for kat in ["TEMİZ", "GÖRSEL_İÇERİKLİ", "BOZUK"]:
    yuzde = (genel_sayac[kat] / genel_toplam * 100) if genel_toplam else 0
    rapor_satirlari.append(f"  {kat:20s}: {genel_sayac[kat]:2d} (%{yuzde:.0f})")
rapor_satirlari.append("")

# ── Kaydet ──────────────────────────────────────────────
with open(CIKIS_JSON, "w", encoding="utf-8") as f:
    json.dump(testler, f, ensure_ascii=False, indent=2)

with open(CIKIS_RAPOR, "w", encoding="utf-8") as f:
    f.write("\n".join(rapor_satirlari))

print("=" * 60)
print(f"tests_categorized.json oluşturuldu ({genel_toplam} soru)")
print(f"kategori_raporu.txt oluşturuldu")
print(f"  TEMİZ:            {genel_sayac['TEMİZ']}")
print(f"  GÖRSEL_İÇERİKLİ:  {genel_sayac['GÖRSEL_İÇERİKLİ']}")
print(f"  BOZUK:            {genel_sayac['BOZUK']}")
print("=" * 60)
