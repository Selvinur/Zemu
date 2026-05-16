from pathlib import Path
import json
import re

giris_yolu = Path(r"D:\zemu\data\tests_clean.json")
cikis_yolu = Path(r"D:\zemu\data\tests_final.json")

with open(giris_yolu, "r", encoding="utf-8") as f:
    testler = json.load(f)

for test in testler:
    cevap_haritasi = {}

    # 1) Bu testin içindeki tüm ham metinlerde cevap anahtarı ara
    for soru in test.get("sorular", []):
        ham = soru.get("hamMetin", "")

        eslesme = re.search(r"CEVAP\s*ANAHTARI\s*:\s*(.*)", ham, flags=re.IGNORECASE)
        if eslesme:
            cevap_metin = eslesme.group(1)

            # örn: 1-B, 2-D, 3-B ...
            parcalar = re.findall(r"(\d+)\s*-\s*([A-D])", cevap_metin, flags=re.IGNORECASE)
            for no, harf in parcalar:
                cevap_haritasi[int(no)] = harf.upper()

    # 2) Sorulara doğru cevapları yaz ve cevap anahtarı kısmını D şıkkından temizle
    for soru in test.get("sorular", []):
        soru_no = soru.get("soruNo")
        if soru_no in cevap_haritasi:
            soru["dogruCevap"] = cevap_haritasi[soru_no]

        if "secenekler" in soru and "D" in soru["secenekler"]:
            soru["secenekler"]["D"] = re.sub(
                r"CEVAP\s*ANAHTARI\s*:.*$",
                "",
                soru["secenekler"]["D"],
                flags=re.IGNORECASE
            ).strip()

with open(cikis_yolu, "w", encoding="utf-8") as f:
    json.dump(testler, f, ensure_ascii=False, indent=2)

print("Bitti. tests_final.json oluşturuldu.")
