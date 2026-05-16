from pathlib import Path
import json
import re

giris_yolu = Path(r"D:\zemu\data\tests_filtered.json")
cikis_yolu = Path(r"D:\zemu\data\tests_clean.json")

with open(giris_yolu, "r", encoding="utf-8") as f:
    testler = json.load(f)

temiz_testler = []

for test in testler:
    yeni_sorular = []

    for soru in test.get("sorular", []):
        ham = soru.get("hamMetin", "").strip()

        eslesme = re.search(
            r"^(.*?)\s*A\)\s*(.*?)\s*B\)\s*(.*?)\s*C\)\s*(.*?)\s*D\)\s*(.*)$",
            ham
        )

        if eslesme:
            soru_metni = eslesme.group(1).strip()
            secenek_a = eslesme.group(2).strip()
            secenek_b = eslesme.group(3).strip()
            secenek_c = eslesme.group(4).strip()
            secenek_d = eslesme.group(5).strip()

            yeni_sorular.append({
                "soruNo": soru.get("soruNo"),
                "soruMetni": soru_metni,
                "secenekler": {
                    "A": secenek_a,
                    "B": secenek_b,
                    "C": secenek_c,
                    "D": secenek_d
                },
                "dogruCevap": "",
                "ipucu": "",
                "hamMetin": ham
            })
        else:
            yeni_sorular.append({
                "soruNo": soru.get("soruNo"),
                "soruMetni": "",
                "secenekler": {
                    "A": "",
                    "B": "",
                    "C": "",
                    "D": ""
                },
                "dogruCevap": "",
                "ipucu": "",
                "hamMetin": ham
            })

    temiz_testler.append({
        "testId": test.get("testId"),
        "testAdi": test.get("testAdi"),
        "sorular": yeni_sorular
    })

with open(cikis_yolu, "w", encoding="utf-8") as f:
    json.dump(temiz_testler, f, ensure_ascii=False, indent=2)

print("Bitti. tests_clean.json oluşturuldu.")