from pathlib import Path
import json

DATA_DIR = Path(r"D:\zemu\data")

def tum_sorulari_getir(veri):
    sorular = []
    if isinstance(veri, list):
        for test in veri:
            if isinstance(test, dict):
                for soru in test.get("sorular", []):
                    sorular.append(soru)
    return sorular

def say_json_izi(sorular):
    toplam = len(sorular)

    onarildi = sum(1 for s in sorular if s.get("onarildi"))
    kaynak_ocr = sum(1 for s in sorular if s.get("kaynakOCR"))
    api_gerekli = sum(1 for s in sorular if s.get("apiGerekli"))
    bozuk = sum(1 for s in sorular if s.get("bozukMu"))

    gorsel_ref = 0
    bos_sik = 0
    uzun_sik = 0
    cevap_anahtari = 0
    bozuk_karakter = 0

    for s in sorular:
        metin = s.get("soruMetni", "") or ""
        ham = s.get("hamMetin", "") or ""
        secenekler = s.get("secenekler", {}) or {}

        if "![" in metin or "data/images" in metin:
            gorsel_ref += 1

        for harf in ["A", "B", "C", "D"]:
            val = str(secenekler.get(harf, "") or "")
            if not val.strip():
                bos_sik += 1
            if len(val) > 80:
                uzun_sik += 1
            if "CEVAP ANAHTARI" in val.upper():
                cevap_anahtari += 1

        if "CEVAP ANAHTARI" in ham.upper():
            cevap_anahtari += 1

        if any(x in (metin + " " + ham) for x in [" ", "??", "5 5"]):
            bozuk_karakter += 1

    return {
        "toplam_soru": toplam,
        "bozukMu": bozuk,
        "apiGerekli": api_gerekli,
        "onarildi": onarildi,
        "kaynakOCR": kaynak_ocr,
        "gorselRef": gorsel_ref,
        "bosSik": bos_sik,
        "uzunSik": uzun_sik,
        "cevapAnahtari": cevap_anahtari,
        "bozukKarakter": bozuk_karakter,
    }

print("\nJSON DOSYA RAPORU\n" + "=" * 120)

for path in sorted(DATA_DIR.glob("*.json")):
    try:
        with open(path, "r", encoding="utf-8") as f:
            veri = json.load(f)

        sorular = tum_sorulari_getir(veri)
        r = say_json_izi(sorular)

        print(f"\nDOSYA: {path.name}")
        print(f"  toplam_soru    : {r['toplam_soru']}")
        print(f"  bozukMu        : {r['bozukMu']}")
        print(f"  apiGerekli     : {r['apiGerekli']}")
        print(f"  onarildi       : {r['onarildi']}")
        print(f"  kaynakOCR      : {r['kaynakOCR']}")
        print(f"  gorselRef      : {r['gorselRef']}")
        print(f"  bosSik         : {r['bosSik']}")
        print(f"  uzunSik        : {r['uzunSik']}")
        print(f"  cevapAnahtari  : {r['cevapAnahtari']}")
        print(f"  bozukKarakter  : {r['bozukKarakter']}")

    except Exception as e:
        print(f"\nDOSYA: {path.name}")
        print(f"  OKUNAMADI: {e}")

print("\nBitti.")