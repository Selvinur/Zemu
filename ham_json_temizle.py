from pathlib import Path
import json

giris_yolu = Path(r"D:\zemu\data\tests_raw.json")
cikis_yolu = Path(r"D:\zemu\data\tests_filtered.json")

with open(giris_yolu, "r", encoding="utf-8") as f:
    testler = json.load(f)

temiz_testler = []

for test in testler:
    temiz_sorular = []

    for soru in test.get("sorular", []):
        ham_metin = soru.get("hamMetin", "")

        if "?" in ham_metin and "A)" in ham_metin and "B)" in ham_metin:
            temiz_sorular.append(soru)

    if temiz_sorular:
        temiz_testler.append({
            "testId": test.get("testId"),
            "testAdi": test.get("testAdi"),
            "sorular": temiz_sorular
        })

with open(cikis_yolu, "w", encoding="utf-8") as f:
    json.dump(temiz_testler, f, ensure_ascii=False, indent=2)

print("Bitti. tests_filtered.json oluşturuldu.")
