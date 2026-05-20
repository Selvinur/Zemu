import os
import sys
import json
import re
import base64
import time
import io
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
from mistralai.client import Mistral

# Windows terminal encoding sorunlarını önlemek için stdout ayarı
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Zemu Yapay Zeka Asistanı modülünü içe aktar
from llm import EgitimAsistani

# Temel Yollar
BASE_DIR = Path(r"D:\zemu")
PDF_KLASORU = BASE_DIR / "kaynaklar"
DATA_DIR = BASE_DIR / "data"
OCR_RAW_KLASORU = DATA_DIR / "ocr_raw"
IMAGES_KLASORU = DATA_DIR / "images"
CROP_KLASORU = DATA_DIR / "question_crops"
HINTS_JSON_YOLU = DATA_DIR / "tests_with_hints.json"

# Halihazırda var olan ve el ile düzenlenmiş testlerin ID'leri (Ezilmemesi gerekenler)
EXCLUDED_TESTS = {
    "30233234_Matematik_5_-_KazanYm_Tarama_Testi_-2",
    "Matematik5-Test-1",
    "Matematik 5 Kazanım Tarama Testi 1"
}

# Görsel Kırpma Parametreleri
ZOOM = 2.8
UST_BOSLUK = 12
ALT_BOSLUK = 8
SOL_BOSLUK = 8
SAG_BOSLUK = 8
SAYFA_UST_PAY = 70
SAYFA_ALT_PAY = 35
MIN_SORU_YUKSEKLIK = 120
MAX_SORU_YUKSEKLIK = 1200
TRIM_PADDING = 10

# Mistral İstemcisini Hazırla
api_key = os.environ.get("MISTRAL_API_KEY")
if not api_key:
    env_dosyasi = BASE_DIR / ".env"
    if env_dosyasi.exists():
        try:
            env_icerik = env_dosyasi.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            env_icerik = env_dosyasi.read_text(encoding="utf-16")
        for satir in env_icerik.splitlines():
            if "MISTRAL_API_KEY=" in satir:
                api_key = satir.split("=", 1)[1].strip().strip("'\"")
                break

if not api_key:
    print("HATA: MISTRAL_API_KEY bulunamadı.")
    sys.exit(1)

client = Mistral(api_key=api_key)

# ── Kırpma Yardımcı Fonksiyonları ──
def beyazlari_kirp(img_path, threshold=245, padding=10):
    img = Image.open(img_path).convert("RGB")
    gray = img.convert("L")
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
    page_width = page.rect.width
    orta_x = page_width / 2
    adaylar = []
    words = page.get_text("words")
    for w in words:
        x0, y0, x1, y1, text, *_ = w
        text = str(text).strip()
        if y0 < SAYFA_UST_PAY or y0 > page.rect.height - SAYFA_ALT_PAY:
            continue
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
    adaylar = sorted(adaylar, key=lambda a: (a["sutun"], a["y0"], a["x0"]))
    temiz = []
    for item in adaylar:
        tekrar = False
        for t in temiz:
            if (t["sutun"] == item["sutun"] and t["soruNo"] == item["soruNo"] and abs(t["y0"] - item["y0"]) < 20):
                tekrar = True
                break
        if not tekrar:
            temiz.append(item)
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
    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), clip=rect, alpha=False)
    pix.save(str(cikti_yolu))
    beyazlari_kirp(cikti_yolu, padding=TRIM_PADDING)

def crop_pdf_questions(pdf_path, test_id):
    test_crop_klasoru = CROP_KLASORU / test_id
    test_crop_klasoru.mkdir(parents=True, exist_ok=True)
    
    # Klasörü temizle
    for f in test_crop_klasoru.glob("q*.png"):
        f.unlink()
    for f in test_crop_klasoru.glob("cevap_anahtari*.png"):
        f.unlink()

    print(f"  Görseller kırpılıyor: {pdf_path.name}")
    doc = fitz.open(pdf_path)
    for sayfa_no, page in enumerate(doc):
        baslangiclar = soru_baslangiclarini_bul(page)
        if baslangiclar:
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
                    if i < len(sutun_sorulari) - 1:
                        alt_adaylari.append(sutun_sorulari[i + 1]["y0"] - ALT_BOSLUK)
                    if cevap_y is not None and cevap_y > ust:
                        alt_adaylari.append(cevap_y - 15)
                    alt_adaylari.append(page.rect.y1 - SAYFA_ALT_PAY)
                    alt = min(alt_adaylari)
                    if alt - ust > MAX_SORU_YUKSEKLIK:
                        alt = ust + MAX_SORU_YUKSEKLIK
                    if alt - ust < MIN_SORU_YUKSEKLIK:
                        continue
                    rect = sutun_clip_rect(page, sutun, ust, alt)
                    dosya = test_crop_klasoru / f"q{soru_no}.png"
                    kirp_ve_kaydet(page, rect, dosya)
                    
        # Cevap anahtarını kırp
        cevap_y = cevap_anahtari_y_bul(page)
        if cevap_y is not None:
            rect = fitz.Rect(page.rect.x0 + 20, max(0, cevap_y - 10), page.rect.x1 - 20, page.rect.y1 - 10)
            dosya = test_crop_klasoru / f"cevap_anahtari_sayfa{sayfa_no+1}.png"
            kirp_ve_kaydet(page, rect, dosya)
    doc.close()

# ── Metin Temizleme Yardımcı Fonksiyonları ──
def metin_temizle(metin):
    if not metin:
        return metin
    metin = re.sub(r'(\w)- (\w)', r'\1\2', metin)
    metin = re.sub(r'(\w)-\n(\w)', r'\1\2', metin)
    metin = re.sub(r'  +', ' ', metin)
    metin = re.sub(r'^\d+\.\s*', '', metin).strip()
    return metin

def d_sikkini_temizle(secenekler):
    if "D" not in secenekler:
        return secenekler
    d = secenekler["D"]
    d = re.sub(r"\s*CEVAP\s*ANAHTARI\s*:?.*$", "", d, flags=re.IGNORECASE).strip()
    d = re.sub(r"\s*---\s*SAYFA\s*\d+\s*---.*$", "", d, flags=re.IGNORECASE | re.DOTALL).strip()
    d = re.sub(r"\s*\d+\s+Matematik.*$", "", d, flags=re.DOTALL).strip()
    d = re.sub(r"\s*%\s*\d+\s*$", "", d).strip()
    d = re.sub(r"\s*\d+\s+ve\s+\d+\.\s+soruları.*$", "", d, flags=re.DOTALL).strip()
    d = re.sub(r"\s*Grafik:.*$", "", d, flags=re.DOTALL).strip()
    secenekler["D"] = d
    return secenekler

# ── Kategorizasyon ──
def kategorize_et(soru):
    sebepler = []
    soru_metni = soru.get("soruMetni", "")
    secenekler = soru.get("secenekler", {})
    ham_metin = soru.get("hamMetin", "")
    birlesik = (soru_metni + " " + ham_metin + " " + " ".join(secenekler.values())).lower()

    for harf in ["A", "B", "C", "D"]:
        sik = secenekler.get(harf, "").strip()
        if not sik:
            sebepler.append(f"{harf} şıkkı boş")

    for harf, metin in secenekler.items():
        if len(metin.strip()) > 120:
            sebepler.append(f"{harf} şıkkı çok uzun ({len(metin)} karakter)")

    for harf, metin in secenekler.items():
        diger_harfler = [h for h in ["A", "B", "C", "D"] if h != harf]
        for diger in diger_harfler:
            if re.search(rf"\b{diger}\)\s", metin):
                sebepler.append(f"{harf} şıkkında {diger}) kalıntısı var")
                break

    for harf, metin in secenekler.items():
        if "CEVAP ANAHTARI" in metin.upper():
            sebepler.append("cevap anahtarı hala şıklarda")

    for harf, metin in secenekler.items():
        if re.search(r"---\s*SAYFA", metin, re.IGNORECASE):
            sebepler.append(f"{harf} şıkkında sayfa bilgisi var")

    if len(soru_metni.strip()) < 10:
        sebepler.append("soru metni çok kısa veya boş")

    sebepler = list(dict.fromkeys(sebepler))
    if sebepler:
        return "BOZUK", sebepler

    gorsel_kelimeleri = [
        "şekil", "yandaki", "yukarıdaki", "kareli", "açı",
        "doğru parçası", "konum", "grafik", "tablo", "görsel",
        "resim", "görseldeki", "şekildeki", "aşağıdaki grafik",
        "ekran görüntüsü"
    ]
    metin_kucuk = (soru_metni + " " + ham_metin).lower()
    if any(kelime in metin_kucuk for kelime in gorsel_kelimeleri):
        return "GÖRSEL_İÇERİKLİ", []

    return "TEMİZ", []

# ── İpucu Yardımcı Fonksiyonları ──
def metni_birlestir(soru):
    parcalar = [str(soru.get("soruMetni", ""))]
    secenekler = soru.get("secenekler", {})
    if isinstance(secenekler, dict):
        for harf, secenek_metni in secenekler.items():
            parcalar.append(f"{harf}) {secenek_metni}")
    return " ".join(parcalar).lower()

def ipucu_uret(soru):
    durum = str(soru.get("durum", "")).upper()
    metin = metni_birlestir(soru)
    if durum in ["BOZUK", "GÖRSEL_İÇERİKLİ", "GORSEL_ICERIKLI"] or soru.get("soruGorselPath"):
        if "grafik" in metin:
            return "Grafikte verilen değerleri dikkatlice oku. En büyük, en küçük ya da karşılaştırma isteyen ifadeleri seçeneklerle eşleştir."
        if "tablo" in metin or "sıklık" in metin:
            return "Tablodaki satır ve sütun başlıklarına dikkat et. Verilen bilgileri seçeneklerdeki tabloyla karşılaştır."
        if "açı" in metin or "s(" in metin:
            return "Şekilde verilen açıları incele. Eş, bütünler ya da paralel doğrulardaki açı ilişkilerini düşün."
        if "paralel" in metin or "//" in metin:
            return "Doğruların yönlerini karşılaştır. Paralel doğrular kesişmez ve aynı doğrultuda ilerler."
        return "Soruyu görselden oku. Şekil, tablo veya verilen bilgileri dikkatlice inceleyip aşağıdaki A-B-C-D seçeneklerinden birini seç."
    if "%" in metin or "yüzde" in metin:
        return "Yüzdeyi kesir ya da ondalık olarak düşün. Önce verilen kısmı bul, sonra sorunun istediği değeri hesapla."
    if any(kelime in metin for kelime in ["km", "metre", "m ", "cm", "mm", "dm"]):
        return "Önce bütün ölçüleri aynı birime çevir. Sonra eşitlikleri ya da karşılaştırmaları kontrol et."
    if "kesir" in metin or "/" in metin or "pay" in metin or "payda" in metin:
        return "Kesirde payın ve paydanın neyi temsil ettiğini düşün. İşlem yapmadan önce verilen kurala göre kesri oluştur."
    if any(kelime in metin for kelime in ["üçgen", "kare", "dikdörtgen", "çokgen", "kenar", "köşe", "köşegen", "paralelkenar"]):
        return "Şeklin özelliklerini hatırla. Kenar, köşe, açı ve köşegen bilgilerini seçeneklerle karşılaştır."
    if "grafik" in metin:
        return "Grafikteki değerleri tek tek oku. Sorunun en büyük, en küçük veya fark gibi ne istediğine dikkat et."
    if "tablo" in metin:
        return "Tabloda verilen bilgileri sırayla kontrol et. Seçeneklerdeki değerleri sorudaki koşullarla karşılaştır."
    if re.search(r"\d+\s*[\+\-\*/]\s*\d+", metin):
        return "İşlem önceliğine dikkat et. Önce parantez varsa onu, sonra çarpma-bölme ve toplama-çıkarma işlemlerini yap."
    return "Önce soru kökünde ne istendiğini bul. Sonra seçenekleri tek tek eleyerek doğru cevaba yaklaş."

# ── Tek Bir PDF Dosyasını İşleme Pipeline'ı ──
def process_single_pdf(pdf_path):
    test_id = pdf_path.stem
    print(f"\n{'-'*65}")
    print(f"İşleniyor: {pdf_path.name}")
    print(f"{'-'*65}")

    # Adım 1: Görselleri Kırp
    crop_pdf_questions(pdf_path, test_id)

    # Adım 2: Mistral OCR İşlemleri (Ön bellek kontrolü ile)
    ocr_json_yolu = OCR_RAW_KLASORU / f"{test_id}.json"
    if ocr_json_yolu.exists():
        print(f"  Bulundu (cached OCR): {ocr_json_yolu.name}")
        with open(ocr_json_yolu, "r", encoding="utf-8") as f:
            ocr_data = json.load(f)
    else:
        print("  OCR API isteği gönderiliyor...")
        with open(pdf_path, "rb") as f:
            pdf_base64 = base64.standard_b64encode(f.read()).decode("utf-8")
        try:
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{pdf_base64}"
                },
                include_image_base64=True
            )
        except Exception as e:
            print(f"  HATA: OCR API başarısız oldu - {e}")
            return None

        # Görselleri Kaydet
        gorsel_klasoru = IMAGES_KLASORU / test_id
        gorsel_klasoru.mkdir(parents=True, exist_ok=True)
        gorsel_haritasi = {}
        for sayfa in ocr_response.pages:
            sayfa_no = sayfa.index
            for img_idx, img in enumerate(sayfa.images):
                if not img.image_base64:
                    continue
                if img.image_base64.startswith("data:image/png"):
                    uzanti = "png"
                    b64_data = img.image_base64.split(",", 1)[1]
                elif img.image_base64.startswith("data:image/jpeg") or img.image_base64.startswith("data:image/jpg"):
                    uzanti = "jpg"
                    b64_data = img.image_base64.split(",", 1)[1]
                else:
                    uzanti = "png"
                    b64_data = img.image_base64

                dosya_adi = f"sayfa{sayfa_no}_img{img_idx}.{uzanti}"
                dosya_yolu = gorsel_klasoru / dosya_adi
                with open(dosya_yolu, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                placeholder = img.id if hasattr(img, "id") and img.id else f"img-{img_idx}.jpeg"
                gorsel_haritasi[placeholder] = f"data/images/{test_id}/{dosya_adi}"

        # JSON Verisini İnşa Et
        ocr_data = {
            "testAdi": test_id,
            "sayfaSayisi": len(ocr_response.pages),
            "gorselHaritasi": gorsel_haritasi,
            "sayfalar": []
        }
        for sayfa in ocr_response.pages:
            markdown = sayfa.markdown
            for placeholder, gercek_yol in gorsel_haritasi.items():
                markdown = markdown.replace(f"({placeholder})", f"({gercek_yol})")
            ocr_data["sayfalar"].append({
                "sayfaNo": sayfa.index,
                "markdown": markdown,
                "gorselSayisi": len(sayfa.images)
            })
        
        OCR_RAW_KLASORU.mkdir(parents=True, exist_ok=True)
        with open(ocr_json_yolu, "w", encoding="utf-8") as f:
            json.dump(ocr_data, f, ensure_ascii=False, indent=2)

    # Adım 3: Markdown'dan Soruları ve Cevap Anahtarını Ayrıştır
    tum_markdown = "\n\n".join(s["markdown"] for s in ocr_data["sayfalar"])
    cevap_haritasi = {}
    cevap_eslesmesi = re.search(r"CEVAP\s*ANAHTARI\s*:?\s*(.*?)(?:\n|$)", tum_markdown, flags=re.IGNORECASE)
    if cevap_eslesmesi:
        cevap_metin = cevap_eslesmesi.group(1)
        parcalar = re.findall(r"(\d+)\s*-\s*([A-Da-d])", cevap_metin)
        for no, harf in parcalar:
            cevap_haritasi[int(no)] = harf.upper()
        print(f"  Cevap anahtarı çözüldü: {len(cevap_haritasi)} soru")

    temiz_markdown = re.sub(r"CEVAP\s*ANAHTARI\s*:?.*$", "", tum_markdown, flags=re.IGNORECASE | re.DOTALL)
    soru_bloklari = re.split(r"\n(?=\d+\.\s)", temiz_markdown)
    sorular = []
    
    for blok in soru_bloklari:
        blok = blok.strip()
        if not blok:
            continue
        numara_eslesme = re.match(r"^(\d+)\.\s*(.*)", blok, re.DOTALL)
        if not numara_eslesme:
            continue
        soru_no = int(numara_eslesme.group(1))
        soru_icerik = numara_eslesme.group(2).strip()

        secenekler = {"A": "", "B": "", "C": "", "D": ""}
        soru_metni = soru_icerik
        secenek_eslesmesi = re.search(r"A\)\s*(.*?)\s*B\)\s*(.*?)\s*C\)\s*(.*?)\s*D\)\s*(.*?)$", soru_icerik, re.DOTALL)
        if secenek_eslesmesi:
            soru_metni = soru_icerik[:secenek_eslesmesi.start()].strip()
            secenekler["A"] = secenek_eslesmesi.group(1).strip()
            secenekler["B"] = secenek_eslesmesi.group(2).strip()
            secenekler["C"] = secenek_eslesmesi.group(3).strip()
            secenekler["D"] = secenek_eslesmesi.group(4).strip()

        # Şık Temizliği
        for harf in ["A", "B", "C", "D"]:
            secenekler[harf] = re.sub(r"!\[.*?\]\(.*?\)", "", secenekler[harf]).strip()
            secenekler[harf] = metin_temizle(secenekler[harf])
        secenekler = d_sikkini_temizle(secenekler)

        # Soru Metni Temizliği
        soru_metni = metin_temizle(soru_metni)

        # Kategorize Et
        soru_obj = {
            "soruNo": soru_no,
            "soruMetni": soru_metni,
            "secenekler": secenekler,
            "dogruCevap": cevap_haritasi.get(soru_no, ""),
            "hamMetin": blok
        }
        durum, sebepler = kategorize_et(soru_obj)
        soru_obj["durum"] = durum
        soru_obj["bozukSebepleri"] = sebepler
        soru_obj["kaynak"] = "mistral_ocr"

        # Görsel Yolu Eşleme
        soru_obj["soruGorselPath"] = None
        if durum in ["BOZUK", "GÖRSEL_İÇERİKLİ"]:
            crop_path = CROP_KLASORU / test_id / f"q{soru_no}.png"
            if crop_path.exists():
                soru_obj["soruGorselPath"] = f"data/question_crops/{test_id}/q{soru_no}.png"
                print(f"  [GÖRSEL] Soru {soru_no} -> q{soru_no}.png görseli bağlandı")

        soru_obj.pop("hamMetin", None)
        sorular.append(soru_obj)

    # Numaraya göre sırala
    sorular.sort(key=lambda s: s["soruNo"])

    # Eksik olan ve parser tarafından çıkarılamayan soruları ekle
    mevcut_nolar = {s["soruNo"] for s in sorular}
    if cevap_haritasi:
        for ans_no in sorted(cevap_haritasi.keys()):
            if ans_no not in mevcut_nolar:
                eksik_soru = {
                    "soruNo": ans_no,
                    "soruMetni": "",
                    "secenekler": {"A": "", "B": "", "C": "", "D": ""},
                    "dogruCevap": cevap_haritasi[ans_no],
                    "durum": "BOZUK",
                    "soruGorselPath": None,
                    "bozukSebepleri": ["OCR metinden ayrıştırılamadı"],
                    "kaynak": "mistral_ocr"
                }
                crop_path = CROP_KLASORU / test_id / f"q{ans_no}.png"
                if crop_path.exists():
                    eksik_soru["soruGorselPath"] = f"data/question_crops/{test_id}/q{ans_no}.png"
                sorular.append(eksik_soru)

    sorular.sort(key=lambda s: s["soruNo"])

    # Adım 4: Zemu ile Yapay Zeka İpuçları Üret
    print("  Zemu ile yapay zeka ipuçları üretiliyor, API limitleri için her soruda 3 saniye bekleniyor...")
    zemu_asistan = EgitimAsistani()
    for idx, soru in enumerate(sorular):
        soru["ipucu"] = ipucu_uret(soru)
        
        tam_soru_metni = metni_birlestir(soru)
        dogru_cevap_harfi = soru.get("dogruCevap", "")
        
        basit_prompt = f"Şu soruyu çözemiyorum, bana doğrudan cevabı söylemeden sadece 1 cümlelik nokta atışı bir ipucu verir misin?\n\nSoru: {tam_soru_metni}"
        gizli_kural = f"Sen Zemu'sun. Doğru cevap {dogru_cevap_harfi} şıkkıdır ama BUNU VEYA ŞIKKIN İÇERİĞİNİ KESİNLİKLE SÖYLEME! Sadece bir kural hatırlat. DİKKAT: 'Anladım', 'Merhaba', 'Zemu:', 'İşte ipucun:' gibi giriş kelimeleri ASLA kullanma! Doğrudan ipucunu yaz."
        
        print(f"    Soru {soru['soruNo']} için AI ipucu oluşturuluyor...")
        try:
            ai_ipucu = zemu_asistan.soru_cevapla(basit_prompt, gizli_talimat=gizli_kural)
            soru["ipucu_ai"] = ai_ipucu
        except Exception as exc:
            print(f"    HATA (AI): {exc}")
            soru["ipucu_ai"] = "Soru görselini inceleyerek doğru sonuca ulaşabilirsin."
        
        time.sleep(3)  # Mistral API rate limit koruması

    test_obj = {
        "testId": test_id,
        "testAdi": test_id,
        "sorular": sorular
    }
    return test_obj

# ── Ana Yürütücü ──
def main():
    print("Zemu Yeni Test Ekleme Pipeline'ı Başlatılıyor...")
    
    # 1. Mevcut testleri yükle
    if HINTS_JSON_YOLU.exists():
        with open(HINTS_JSON_YOLU, "r", encoding="utf-8") as f:
            existing_tests = json.load(f)
    else:
        existing_tests = []
        
    existing_ids = {t["testId"] for t in existing_tests}
    print(f"Mevcut {len(existing_ids)} test koruma altında: {existing_ids}")
    
    # 2. kaynaklar klasöründeki yeni PDF'leri bul
    all_pdfs = sorted(PDF_KLASORU.glob("*.pdf"))
    new_pdfs = [p for p in all_pdfs if p.stem not in existing_ids and p.stem not in EXCLUDED_TESTS]
    
    if not new_pdfs:
        print("İşlenecek yeni PDF bulunamadı.")
        return
        
    print(f"{len(new_pdfs)} adet yeni PDF bulundu ve işlenecek:")
    for p in new_pdfs:
        print(f" - {p.name}")
        
    # 3. Her PDF'i tek tek işle ve sonuca ekle
    updated_tests = list(existing_tests)
    for p in new_pdfs:
        test_obj = process_single_pdf(p)
        if test_obj:
            updated_tests.append(test_obj)
            # Her test bittiğinde anlık kaydet (güvenlik için)
            with open(HINTS_JSON_YOLU, "w", encoding="utf-8") as f:
                json.dump(updated_tests, f, ensure_ascii=False, indent=2)
            print(f"💾 Ara Kayıt Başarılı: {p.stem} eklendi.")
            
    print("\nTÜM YENİ TESTLER BAŞARIYLA EKLENDİ!")
    print(f"Veri dosyası güncellendi: {HINTS_JSON_YOLU}")

if __name__ == "__main__":
    main()
