from pathlib import Path
import json

json_yolu = Path(r"D:\zemu\data\tests_marked.json")

with open(json_yolu, "r", encoding="utf-8") as f:
    testler = json.load(f)

print("\nAPI'ye gönderilecek bozuk sorular:\n")

for test in testler:
    test_adi = test.get("testAdi", test.get("testId"))

    for soru in test.get("sorular", []):
        if soru.get("apiGerekli") == True:
            print(f"{test_adi} - Soru {soru.get('soruNo')}")
            print("Sebepler:")
            for sebep in soru.get("bozukSebepleri", []):
                print(f"  - {sebep}")
            print("-" * 40)
            