from pathlib import Path
from pypdf import PdfReader

kaynak_klasoru = Path(r"D:\zemu\kaynaklar")
cikti_klasoru = Path(r"D:\zemu\cikti")

cikti_klasoru.mkdir(exist_ok=True)

pdf_dosyalari = list(kaynak_klasoru.glob("*.pdf"))

if not pdf_dosyalari:
    print("PDF bulunamadı.")
else:
    for pdf_yolu in pdf_dosyalari:
        print(f"İşleniyor: {pdf_yolu.name}")

        reader = PdfReader(str(pdf_yolu))
        tum_metin = []

        for i, sayfa in enumerate(reader.pages, start=1):
            metin = sayfa.extract_text()
            tum_metin.append(f"\n--- SAYFA {i} ---\n")
            tum_metin.append(metin if metin else "")

        txt_adi = pdf_yolu.stem + ".txt"
        txt_yolu = cikti_klasoru / txt_adi

        with open(txt_yolu, "w", encoding="utf-8") as f:
            f.write("\n".join(tum_metin))

        print(f"Kaydedildi: {txt_yolu.name}")

    print("\nBitti.")