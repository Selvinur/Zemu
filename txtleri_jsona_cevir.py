from pathlib import Path
import json
import re

txt_klasoru = Path(r"D:\zemu\cikti")
json_yolu = Path(r"D:\zemu\data\tests_raw.json")

tum_testler = []

txt_dosyalari = list(txt_klasoru.glob("*.txt"))

for txt_yolu in txt_dosyalari:
    with open(txt_yolu, "r", encoding="utf-8") as f:
        icerik = f.read()

    satirlar = [satir.strip() for satir in icerik.splitlines() if satir.strip()]

    sorular = []
    aktif_soru = None

    for satir in satirlar:
        eslesme = re.match(r"^(\d+)\.", satir)

        if eslesme:
            if aktif_soru:
                sorular.append(aktif_soru)

            aktif_soru = {
                "soruNo": int(eslesme.group(1)),
                "hamMetin": satir
            }
        else:
            if aktif_soru:
                aktif_soru["hamMetin"] += " " + satir

    if aktif_soru:
        sorular.append(aktif_soru)

    test = {
        "testId": txt_yolu.stem,
        "testAdi": txt_yolu.stem,
        "sorular": sorular
    }

    tum_testler.append(test)

with open(json_yolu, "w", encoding="utf-8") as f:
    json.dump(tum_testler, f, ensure_ascii=False, indent=2)

print("Bitti. tests_raw.json oluşturuldu.")