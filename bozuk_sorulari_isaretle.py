from pathlib import Path
import json

giris_yolu = Path(r"D:\zemu\data\tests_final.json")
cikis_yolu = Path(r"D:\zemu\data\tests_marked.json")

with open(giris_yolu, "r", encoding="utf-8") as f:
    testler = json.load(f)

def soru_bozuk_mu(soru):
    sebepler = []

    soru_metni = soru.get("soruMetni", "")
    secenekler = soru.get("secenekler", {})
    ham_metin = soru.get("hamMetin", "")

    # 1) Şıklardan biri boşsa
    for harf in ["A", "B", "C", "D"]:
        if not secenekler.get(harf, "").strip():
            sebepler.append(f"{harf} şıkkı boş")

    # 2) Bir şık aşırı uzunsa başka soruyla karışmış olabilir
    for harf, metin in secenekler.items():
        if len(metin) > 80:
            sebepler.append(f"{harf} şıkkı çok uzun")

    # 3) Cevap anahtarı şıklara yapışmışsa
    if "CEVAP ANAHTARI" in ham_metin or any("CEVAP ANAHTARI" in v for v in secenekler.values()):
        sebepler.append("cevap anahtarı karışmış")

    # 4) Soru metni çok kısaysa veya anlamsız görünüyorsa
    if len(soru_metni.strip()) < 20:
        sebepler.append("soru metni çok kısa")

    # 5) PDF’den bozuk gelen özel karakterler varsa
    bozuk_karakterler = ["￾", "??", "5 5", " % ", " ' "]
    for karakter in bozuk_karakterler:
        if karakter in soru_metni or karakter in ham_metin:
            sebepler.append("sembol/karakter bozulması var")
            break

    # 6) Şekle bağlı soru olma ihtimali
    sekil_kelimeleri = ["şekil", "yandaki", "kareli", "açı", "doğru parçası", "konum", "görsel", "resim", "grafik", "yukarıdaki", "görseldeki", "tablo"]
    metin_kucuk = (soru_metni + " " + ham_metin).lower()

    if any(kelime in metin_kucuk for kelime in sekil_kelimeleri):
        sebepler.append("görsel/şekil içeren soru olabilir")

    return sebepler

for test in testler:
    for soru in test.get("sorular", []):
        sebepler = soru_bozuk_mu(soru)

        if sebepler:
            soru["bozukMu"] = True
            soru["apiGerekli"] = True
            soru["bozukSebepleri"] = sebepler
        else:
            soru["bozukMu"] = False
            soru["apiGerekli"] = False
            soru["bozukSebepleri"] = []

with open(cikis_yolu, "w", encoding="utf-8") as f:
    json.dump(testler, f, ensure_ascii=False, indent=2)

print("Bitti. tests_marked.json oluşturuldu.")