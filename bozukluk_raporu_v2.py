from pathlib import Path
import json
import re

GIRIS = Path(r"D:\zemu\data\tests_clean.json")
CIKIS = Path(r"D:\zemu\data\bozukluk_raporu_v2.txt")
EXPECTED_QUESTION_COUNT = 10

GORSel_KELIMELERI = [
    "şekil", "yandaki", "yukarıdaki", "kareli", "açı",
    "doğru parçası", "konum", "grafik", "tablo", "görsel"
]

# Bunlar gerçekten PDF karakter bozulması göstergesi.
# Tek başına "V" gibi normal harfleri koymuyoruz; çok fazla false positive yapıyor.
BOZUK_ISARETLER = [
    " ", "??", "5 5", "c^h", "g3464", "KL? ?", "AB? ?", "KL MN'", "KL MN="
]

def get_text(soru):
    secenekler = soru.get("secenekler") or {}
    return " ".join([
        str(soru.get("soruMetni", "") or ""),
        str(soru.get("hamMetin", "") or ""),
        " ".join(str(v or "") for v in secenekler.values())
    ])

def option(soru, harf):
    return str((soru.get("secenekler") or {}).get(harf, "") or "")

def is_visual_dependent(soru):
    text = get_text(soru).lower()
    return any(k in text for k in GORSel_KELIMELERI)

def detect_serious_reasons(soru):
    reasons = []

    for harf in ["A", "B", "C", "D"]:
        val = option(soru, harf).strip()

        if not val:
            reasons.append(f"{harf} şıkkı boş")

        if len(val) > 100:
            reasons.append(f"{harf} şıkkı çok uzun")

        if re.search(r"\b\d{1,2}\.\s", val):
            reasons.append(f"{harf} şıkkına başka soru karışmış")

        if len(re.findall(r"\b[A-D]\)", val)) >= 2:
            reasons.append(f"{harf} şıkkına başka seçenekler karışmış")

        if "CEVAP ANAHTARI" in val.upper():
            reasons.append("cevap anahtarı şıklara karışmış")

        if "--- SAYFA" in val.upper() or re.search(r"\bSAYFA\s+\d+", val.upper()):
            reasons.append("sayfa bilgisi şıklara karışmış")

    all_text = get_text(soru)

    if "CEVAP ANAHTARI" in all_text.upper():
        reasons.append("cevap anahtarı karışmış")

    if "--- SAYFA" in all_text.upper() or re.search(r"\bSAYFA\s+\d+", all_text.upper()):
        reasons.append("sayfa bilgisi karışmış")

    if any(x in all_text for x in BOZUK_ISARETLER):
        reasons.append("sembol/karakter bozulması var")

    soru_metni = str(soru.get("soruMetni", "") or "").strip()
    if len(soru_metni) < 20:
        reasons.append("soru metni çok kısa")

    return list(dict.fromkeys(reasons))

def status_for_question(soru):
    serious = detect_serious_reasons(soru)
    visual = is_visual_dependent(soru)

    if serious:
        return "BOZUK", serious

    if visual:
        return "GÖRSEL_GEREKLİ", ["metin/şıklar temiz görünüyor ama soru görsele bağlı"]

    return "TEMİZ", []

with open(GIRIS, "r", encoding="utf-8") as f:
    testler = json.load(f)

lines = []
lines.append("BOZUKLUK RAPORU V2")
lines.append(f"Kaynak: {GIRIS}")
lines.append("=" * 90)

for test in testler:
    test_adi = test.get("testAdi") or test.get("testId") or "Adsız test"
    sorular = test.get("sorular", [])

    lines.append("")
    lines.append(f"TEST: {test_adi}")
    lines.append("-" * 90)

    soru_nolari = sorted([
        s.get("soruNo") for s in sorular
        if isinstance(s.get("soruNo"), int)
    ])

    eksikler = [n for n in range(1, EXPECTED_QUESTION_COUNT + 1) if n not in soru_nolari]
    if eksikler:
        lines.append(f"EKSİK SORULAR: {eksikler}")

    counts = {
        "TEMİZ": 0,
        "GÖRSEL_GEREKLİ": 0,
        "BOZUK": 0
    }

    for soru in sorted(sorular, key=lambda x: x.get("soruNo", 999)):
        durum, reasons = status_for_question(soru)
        counts[durum] += 1

        if durum == "TEMİZ":
            continue

        soru_no = soru.get("soruNo", "?")
        lines.append("")
        lines.append(f"Soru {soru_no} — {durum}")
        lines.append("Sebepler:")
        for r in reasons:
            lines.append(f"  - {r}")

        if durum == "BOZUK":
            lines.append("Önerilen işlem:")
            lines.append("  - Gemini/crop ile bu soruyu yeniden JSON'a çevir")
        else:
            lines.append("Önerilen işlem:")
            lines.append("  - JSON metnine dokunma; sadece soru görselini sakla/göster")

        soru_metni = str(soru.get("soruMetni", "") or "").replace("\n", " ")
        lines.append("Kısa önizleme:")
        lines.append(f"  Metin: {soru_metni[:220]}")

        secenekler = soru.get("secenekler") or {}
        for harf in ["A", "B", "C", "D"]:
            val = str(secenekler.get(harf, "") or "").replace("\n", " ")
            lines.append(f"  {harf}: {val[:160]}")

    lines.append("")
    lines.append("ÖZET:")
    lines.append(f"  TEMİZ           : {counts['TEMİZ']}")
    lines.append(f"  GÖRSEL_GEREKLİ  : {counts['GÖRSEL_GEREKLİ']}")
    lines.append(f"  BOZUK           : {counts['BOZUK']}")
    if eksikler:
        lines.append(f"  EKSİK           : {len(eksikler)}")

with open(CIKIS, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Rapor oluşturuldu:")
print(CIKIS)