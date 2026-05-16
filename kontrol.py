"""Hizli kontrol scripti"""
import json
import sys
import io
from pathlib import Path

# Windows terminal encoding sorununu coz
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open(Path(r"D:\zemu\data\tests_final.json"), "r", encoding="utf-8") as f:
    testler = json.load(f)

for test in testler:
    print(f"\n{'='*60}")
    print(f"Test: {test['testAdi']} ({len(test['sorular'])} soru)")
    print(f"{'='*60}")

    for soru in test["sorular"]:
        no = soru["soruNo"]
        bozuk = soru.get("bozukMu", False)
        onarildi = soru.get("onarildi", False)
        cevap = soru.get("dogruCevap", "?")
        gorsel = "![" in soru.get("soruMetni", "")

        # Sık durumu
        siklar = soru.get("secenekler", {})
        bos_siklar = [h for h in ["A","B","C","D"] if not siklar.get(h, "").strip()]
        uzun_siklar = [h for h in ["A","B","C","D"] if len(siklar.get(h, "")) > 60]

        durum = "TEMIZ"
        if bozuk:
            durum = "BOZUK"
        elif onarildi:
            durum = "ONARILDI"

        satir = f"  Soru {no:2d} | {durum:9s} | Cevap: {cevap} | Gorsel: {'EVET' if gorsel else 'HAYIR':5s}"

        if bos_siklar:
            satir += f" | BOS SIKLAR: {','.join(bos_siklar)}"
        if uzun_siklar:
            satir += f" | UZUN SIKLAR: {','.join(uzun_siklar)}"

        print(satir)

        # Siklari goster
        for harf in ["A","B","C","D"]:
            sik = siklar.get(harf, "")
            if len(sik) > 50:
                sik = sik[:50] + "..."
            sik = sik.replace("\n", " ")
            print(f"         {harf}) {sik}")
