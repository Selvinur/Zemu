from pathlib import Path
import re
import fitz  # pymupdf
from PIL import Image

PDF_KLASORU = Path(r"D:\zemu\kaynaklar")
CIKTI_KLASORU = Path(r"D:\zemu\data\question_crops")

ZOOM = 2.8

UST_BOSLUK = 12
ALT_BOSLUK = 8
SOL_BOSLUK = 8
SAG_BOSLUK = 8

SAYFA_UST_PAY = 70
SAYFA_ALT_PAY = 35

MIN_SORU_YUKSEKLIK = 120
MAX_SORU_YUKSEKLIK = 1200   # aşırı uzun crop olmasın
TRIM_PADDING = 10


def beyazlari_kirp(img_path, threshold=245, padding=10):
    """
    Görüntünün etrafındaki beyaz boşlukları kırpar.
    """
    img = Image.open(img_path).convert("RGB")
    gray = img.convert("L")

    # Beyaz olmayan pikselleri maskele
    mask = gray.point(lambda p: 0 if p > threshold else 255, mode="1")
    bbox = mask.getbbox()

    if bbox is None:
        return

    x0, y0, x1, y1 = bbox

    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(img.width, x1 + padding)
    y1 = min(img.height, y1 + padding)

    kirpilmis = img.crop((x0, y0, x1, y1))
    kirpilmis.save(img_path)


def satir_metni(line):
    return "".join(span.get("text", "") for span in line.get("spans", [])).strip()


def soru_numarasi_yakala(text):
    text = text.strip()
    m = re.match(r"^(\d{1,2})\.\s*$", text)
    if m:
        no = int(m.group(1))
        if 1 <= no <= 20:
            return no

    m = re.match(r"^(\d{1,2})\.\s+", text)
    if m:
        no = int(m.group(1))
        if 1 <= no <= 20:
            return no

    return None


def cevap_anahtari_y_bul(page):
    """
    Sayfada 'CEVAP ANAHTARI' yazısı varsa onun y koordinatını bulur.
    """
    data = page.get_text("dict")
    ys = []

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            text = satir_metni(line).upper()
            if "CEVAP ANAHTARI" in text:
                ys.append(line["bbox"][1])

    return min(ys) if ys else None


def soru_baslangiclarini_bul(page):
    """
    Sayfadaki soru başlangıçlarını bulur.
    Önce words ile arar, sonra line bazlı yakaladıklarıyla destekler.
    """
    page_width = page.rect.width
    orta_x = page_width / 2
    adaylar = []

    # 1) WORD bazlı bul
    words = page.get_text("words")
    for w in words:
        x0, y0, x1, y1, text, *_ = w
        text = str(text).strip()

        if y0 < SAYFA_UST_PAY or y0 > page.rect.height - SAYFA_ALT_PAY:
            continue

        # sadece "5." gibi tek başına numara
        if re.fullmatch(r"\d{1,2}\.", text):
            no = int(text[:-1])
            if 1 <= no <= 20:
                sutun = "sol" if x0 < orta_x else "sag"
                adaylar.append({
                    "soruNo": no,
                    "x0": x0,
                    "y0": y0,
                    "y1": y1,
                    "sutun": sutun,
                    "kaynak": "word"
                })

    # 2) LINE bazlı destekle
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            text = satir_metni(line)

            x0, y0, x1, y1 = line["bbox"]

            if y0 < SAYFA_UST_PAY or y0 > page.rect.height - SAYFA_ALT_PAY:
                continue

            no = soru_numarasi_yakala(text)
            if no is not None:
                sutun = "sol" if x0 < orta_x else "sag"
                adaylar.append({
                    "soruNo": no,
                    "x0": x0,
                    "y0": y0,
                    "y1": y1,
                    "sutun": sutun,
                    "kaynak": "line"
                })

    # Yakın duran tekrarları temizle
    adaylar = sorted(adaylar, key=lambda a: (a["sutun"], a["y0"], a["x0"]))

    temiz = []
    for item in adaylar:
        tekrar = False
        for t in temiz:
            if (
                t["sutun"] == item["sutun"]
                and t["soruNo"] == item["soruNo"]
                and abs(t["y0"] - item["y0"]) < 20
            ):
                tekrar = True
                break
        if not tekrar:
            temiz.append(item)

    # bazen sayfa altındaki alakasız "10." gibi şeyler yakalanabilir
    # bunları çok aşağıdaysa ele
    son_temiz = []
    for item in temiz:
        if item["y0"] > page.rect.height - 120:
            continue
        son_temiz.append(item)

    return son_temiz


def sutun_clip_rect(page, sutun, ust, alt):
    page_rect = page.rect
    orta_x = page_rect.width / 2

    if sutun == "sol":
        x0 = page_rect.x0 + SOL_BOSLUK
        x1 = orta_x - SAG_BOSLUK
    else:
        x0 = orta_x + SOL_BOSLUK
        x1 = page_rect.x1 - SAG_BOSLUK

    ust = max(page_rect.y0 + SAYFA_UST_PAY, ust)
    alt = min(page_rect.y1 - SAYFA_ALT_PAY, alt)

    return fitz.Rect(x0, ust, x1, alt)


def kirp_ve_kaydet(page, rect, cikti_yolu):
    pix = page.get_pixmap(
        matrix=fitz.Matrix(ZOOM, ZOOM),
        clip=rect,
        alpha=False
    )
    pix.save(str(cikti_yolu))
    beyazlari_kirp(cikti_yolu, padding=TRIM_PADDING)


def klasoru_temizle(klasor):
    for dosya in klasor.glob("q*.png"):
        try:
            dosya.unlink()
        except Exception:
            pass

    for dosya in klasor.glob("cevap_anahtari*.png"):
        try:
            dosya.unlink()
        except Exception:
            pass


def cevap_anahtari_kirp(page, cikti_klasoru, sayfa_no):
    y = cevap_anahtari_y_bul(page)
    if y is None:
        return

    rect = fitz.Rect(
        page.rect.x0 + 20,
        max(0, y - 10),
        page.rect.x1 - 20,
        page.rect.y1 - 10
    )

    dosya = cikti_klasoru / f"cevap_anahtari_sayfa{sayfa_no+1}.png"
    kirp_ve_kaydet(page, rect, dosya)
    print(f"  ✓ cevap_anahtari_sayfa{sayfa_no+1}.png oluşturuldu")


def sayfadaki_sorulari_kirp(page, baslangiclar, cikti_klasoru):
    cevap_y = cevap_anahtari_y_bul(page)

    for sutun in ["sol", "sag"]:
        sutun_sorulari = [b for b in baslangiclar if b["sutun"] == sutun]
        sutun_sorulari.sort(key=lambda x: x["y0"])

        if not sutun_sorulari:
            continue

        for i, item in enumerate(sutun_sorulari):
            soru_no = item["soruNo"]
            ust = item["y0"] - UST_BOSLUK

            alt_adaylari = []

            # bir sonraki soru varsa oraya kadar
            if i < len(sutun_sorulari) - 1:
                alt_adaylari.append(sutun_sorulari[i + 1]["y0"] - ALT_BOSLUK)

            # cevap anahtarı varsa oradan önce kes
            if cevap_y is not None and cevap_y > ust:
                alt_adaylari.append(cevap_y - 15)

            # sayfa sonu fallback
            alt_adaylari.append(page.rect.y1 - SAYFA_ALT_PAY)

            alt = min(alt_adaylari)

            # aşırı uzunsa sınırlayalım
            if alt - ust > MAX_SORU_YUKSEKLIK:
                alt = ust + MAX_SORU_YUKSEKLIK

            if alt - ust < MIN_SORU_YUKSEKLIK:
                print(f"  ! q{soru_no}.png çok küçük olacağı için atlandı.")
                continue

            rect = sutun_clip_rect(page, sutun, ust, alt)
            dosya = cikti_klasoru / f"q{soru_no}.png"

            kirp_ve_kaydet(page, rect, dosya)
            print(f"  ✓ q{soru_no}.png oluşturuldu ({sutun} sütun)")


def main():
    CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)

    pdfler = sorted(PDF_KLASORU.glob("*.pdf"))
    if not pdfler:
        print("PDF bulunamadı.")
        return

    for pdf_yolu in pdfler:
        test_id = pdf_yolu.stem
        test_cikti_klasoru = CIKTI_KLASORU / test_id
        test_cikti_klasoru.mkdir(parents=True, exist_ok=True)
        klasoru_temizle(test_cikti_klasoru)

        print("=" * 60)
        print(f"İşleniyor: {pdf_yolu.name}")

        doc = fitz.open(pdf_yolu)

        for sayfa_no, page in enumerate(doc):
            baslangiclar = soru_baslangiclarini_bul(page)

            if baslangiclar:
                ozet = [(b["soruNo"], b["sutun"]) for b in baslangiclar]
                print(f"  Sayfa {sayfa_no+1}: bulunanlar -> {ozet}")
                sayfadaki_sorulari_kirp(page, baslangiclar, test_cikti_klasoru)
            else:
                print(f"  Sayfa {sayfa_no+1}: soru bulunamadı.")

            # cevap anahtarını ayrı kırp
            cevap_anahtari_kirp(page, test_cikti_klasoru, sayfa_no)

        doc.close()

    print("=" * 60)
    print("Bitti. Soru kırpları oluşturuldu.")


if __name__ == "__main__":
    main()