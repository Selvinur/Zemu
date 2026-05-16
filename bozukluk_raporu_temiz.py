from pathlib import Path
import json
import re

GIRIS = Path(r"D:\zemu\data\tests_clean.json")
CIKIS = Path(r"D:\zemu\data\bozukluk_raporu_temiz.txt")

EXPECTED_QUESTION_COUNT = 10

def option_text(soru, harf):
    secenekler = soru.get("secenekler") or {}
    return str(secenekler.get(harf, "") or "")

def detect_reasons(soru):
    reasons = []
    actions = []

    soru_no = soru.get("soruNo")
    soru_metni = str(soru.get("soruMetni", "") or "")
    ham_metin = str(soru.get("hamMetin", "") or "")
    secenekler = soru.get("secenekler") or {}

    combined = " ".join([
        soru_metni,
        ham_metin,
        " ".join(str(v or "") for v in secenekler.values())
    ])

    # 1) Boş şıklar
    for harf in ["A", "B", "C", "D"]:
        val = option_text(soru, harf).strip()
        if not val:
            reasons.append(f"{harf} şıkkı boş")
            actions.append("Gemini/crop ile şıkları çıkar")

    # 2) Aşırı uzun şık
    for harf in ["A", "B", "C", "D"]:
        val = option_text(soru, harf).strip()
        if len(val) > 80:
            reasons.append(f"{harf} şıkkı çok uzun")
            actions.append("Şık sınırı kaymış olabilir, crop ile düzelt")

    # 3) Şık içine başka soru veya başka şık karışmış mı?
    for harf in ["A", "B", "C", "D"]:
        val = option_text(soru, harf)
        if re.search(r"\b\d{1,2}\.\s", val):
            reasons.append(f"{harf} şıkkına başka soru karışmış")
            actions.append("Soru bölme hatası, crop/Gemini gerekir")

        # Bir şıkkın içinde tekrar A) B) C) D) varsa
        if len(re.findall(r"\b[A-D]\)", val)) >= 2:
            reasons.append(f"{harf} şıkkına başka seçenekler karışmış")
            actions.append("Şıkları yeniden çıkar")

    # 4) Cevap anahtarı karışması
    if "CEVAP ANAHTARI" in combined.upper():
        reasons.append("cevap anahtarı karışmış")
        actions.append("Cevap anahtarını metinden ayır")

    # 5) Sayfa bilgisi karışması
    if "--- SAYFA" in combined.upper() or re.search(r"\bSAYFA\s+\d+", combined.upper()):
        reasons.append("sayfa bilgisi soruya/şıklara karışmış")
        actions.append("Sayfa ayırıcılarını temizle")

    # 6) Bozuk sembol / karakter
    bozuk_isaretler = [" ", "??", "5 5", "c^h", "V", "g3464"]
    if any(x in combined for x in bozuk_isaretler):
        reasons.append("sembol/karakter bozulması var")
        actions.append("Matematik sembolleri için crop/Gemini gerekir")

    # 7) Görsele bağlı soru
    gorsel_kelimeleri = [
        "şekil", "yandaki", "yukarıdaki", "kareli", "açı",
        "doğru parçası", "konum", "grafik", "tablo", "görsel"
    ]
    lower = combined.lower()
    if any(k in lower for k in gorsel_kelimeleri):
        reasons.append("görsel/şekil bağımlı soru")
        actions.append("Soru görseli saklanmalı; metin tek başına yetmeyebilir")

    # 8) Soru metni çok kısa
    if len(soru_metni.strip()) < 20:
        reasons.append("soru metni çok kısa")
        actions.append("Soru metni yeniden çıkarılmalı")

    # 9) Soru numarası yoksa / garipse
    if soru_no is None:
        reasons.append("soru numarası yok")
        actions.append("Soru numarası manuel/AI ile bulunmalı")

    # Tekilleştir
    reasons = list(dict.fromkeys(reasons))
    actions = list(dict.fromkeys(actions))

    return reasons, actions

with open(GIRIS, "r", encoding="utf-8") as f:
    testler = json.load(f)

lines = []
lines.append("BOZUKLUK RAPORU")
lines.append(f"Kaynak: {GIRIS}")
lines.append("=" * 80)

for test in testler:
    test_adi = test.get("testAdi") or test.get("testId") or "Adsız test"
    sorular = test.get("sorular", [])

    lines.append("")
    lines.append(f"TEST: {test_adi}")
    lines.append("-" * 80)

    soru_nolari = sorted([
        s.get("soruNo") for s in sorular
        if isinstance(s.get("soruNo"), int)
    ])

    if soru_nolari:
        eksikler = [n for n in range(1, EXPECTED_QUESTION_COUNT + 1) if n not in soru_nolari]
        fazlalar = [n for n in soru_nolari if n < 1 or n > EXPECTED_QUESTION_COUNT]

        if eksikler:
            lines.append(f"EKSİK SORULAR: {eksikler}")
        if fazlalar:
            lines.append(f"BEKLENMEYEN SORU NUMARALARI: {fazlalar}")
    else:
        lines.append("UYARI: Bu testte okunabilir soru numarası yok.")

    bozuk_sayisi = 0

    for soru in sorted(sorular, key=lambda x: x.get("soruNo", 999)):
        reasons, actions = detect_reasons(soru)

        if not reasons:
            continue

        bozuk_sayisi += 1
        soru_no = soru.get("soruNo", "?")

        lines.append("")
        lines.append(f"Soru {soru_no}")
        lines.append("Sebepler:")
        for r in reasons:
            lines.append(f"  - {r}")

        lines.append("Önerilen işlem:")
        for a in actions:
            lines.append(f"  - {a}")

        lines.append("Kısa önizleme:")
        soru_metni = str(soru.get("soruMetni", "") or "").replace("\n", " ")
        lines.append(f"  Metin: {soru_metni[:220]}")

        secenekler = soru.get("secenekler") or {}
        for harf in ["A", "B", "C", "D"]:
            val = str(secenekler.get(harf, "") or "").replace("\n", " ")
            lines.append(f"  {harf}: {val[:160]}")

    if bozuk_sayisi == 0:
        lines.append("Bu testte bozuk görünen soru yok.")
    else:
        lines.append("")
        lines.append(f"Toplam bozuk/kontrol gereken soru: {bozuk_sayisi}")

with open(CIKIS, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Rapor oluşturuldu:")
print(CIKIS)