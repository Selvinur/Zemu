from pathlib import Path
import json
import re
import concurrent.futures
import threading
import time
from llm import EgitimAsistani

GIRIS_YOLU = Path(r"D:\zemu\data\tests_with_images.json")
CIKIS_YOLU = Path(r"D:\zemu\data\tests_with_hints.json")

# Zemu'yu başlat
print("Zemu (Yapay Zeka Asistanı) başlatılıyor, lütfen bekleyin...")
zemu_asistan = EgitimAsistani()
print("Zemu hazır! İpuçları oluşturuluyor...")

# Dosya kaydetme kilidi (Thread-safe)
save_lock = threading.Lock()
islem_goren_soru_sayisi = 0
toplam_islem = 0

def metni_birlestir(soru):
    parcalar = [
        str(soru.get("soruMetni", "")),
        str(soru.get("hamMetin", "")),
    ]

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

def asistan_ile_ipucu_al(soru, test_index, soru_index, testler):
    global islem_goren_soru_sayisi
    
    # Statik birinci ipucu (Eğer yoksa üret)
    if not soru.get("ipucu"):
        soru["ipucu"] = ipucu_uret(soru)
    
    # Eğer zaten AI ipucu üretilmişse atla (Kaldığı yerden devam etme özelliği)
    if soru.get("ipucu_ai"):
        return
        
    tam_soru_metni = metni_birlestir(soru)
    
    # Doğru cevabı bul
    dogru_cevap_harfi = soru.get("dogruCevap", "")
    
    basit_prompt = f"Şu soruyu çözemiyorum, bana doğrudan cevabı söylemeden sadece 1 cümlelik nokta atışı bir ipucu verir misin?\n\nSoru: {tam_soru_metni}"
    gizli_kural = f"Sen Zemu'sun. Doğru cevap {dogru_cevap_harfi} şıkkıdır ama BUNU VEYA ŞIKKIN İÇERİĞİNİ KESİNLİKLE SÖYLEME! Sadece bir kural hatırlat. DİKKAT: 'Anladım', 'Merhaba', 'Zemu:', 'İşte ipucun:' gibi giriş kelimeleri ASLA kullanma! Doğrudan ipucunu yaz."
    
    print(f"Soru {soru_index+1} için Zemu'dan ipucu alınıyor... (İşlem {islem_goren_soru_sayisi+1}/{toplam_islem})")
    ai_ipucu = zemu_asistan.soru_cevapla(basit_prompt, gizli_talimat=gizli_kural)
    soru["ipucu_ai"] = ai_ipucu
    
    # İşlem gören soru sayısını artır ve anlık kaydet
    with save_lock:
        islem_goren_soru_sayisi += 1
        # Her 5 soruda bir dosyaya kaydet
        if islem_goren_soru_sayisi % 5 == 0:
            with open(CIKIS_YOLU, "w", encoding="utf-8") as f:
                json.dump(testler, f, ensure_ascii=False, indent=2)
            print(f"--- 💾 Ara Kayıt Alındı: {islem_goren_soru_sayisi}/{toplam_islem} soru işlendi. ---")

def ana_islem():
    global toplam_islem
    
    # Kaldığı yerden devam etmesi için önce çıktı dosyasını kontrol et
    if CIKIS_YOLU.exists():
        print("Mevcut ipucu dosyası bulundu, kaldığı yerden devam edilecek...")
        with open(CIKIS_YOLU, "r", encoding="utf-8") as f:
            testler = json.load(f)
    else:
        print("Yeni ipucu dosyası oluşturulacak...")
        with open(GIRIS_YOLU, "r", encoding="utf-8") as f:
            testler = json.load(f)

    # Toplam işlem yapılması gereken soru sayısını hesapla
    islem_gereken_sorular = []
    for t_idx, test in enumerate(testler):
        for s_idx, soru in enumerate(test.get("sorular", [])):
            if not soru.get("ipucu_ai"):
                islem_gereken_sorular.append((soru, t_idx, s_idx))
                
    toplam_islem = len(islem_gereken_sorular)
    print(f"Toplam {toplam_islem} soru için ipucu üretilecek.")
    
    if toplam_islem == 0:
        print("Tüm soruların zaten ipucu var. İşlem bitti.")
        return

    # Seri işleme (API limitlerine takılmamak için 1.5 saniye bekleme ile)
    for soru, t_idx, s_idx in islem_gereken_sorular:
        try:
            asistan_ile_ipucu_al(soru, t_idx, s_idx, testler)
            time.sleep(3) # Mistral Free API kısıtlamalarına takılmamak için 3 saniye bekle
        except Exception as exc:
            print(f"Bir soruda hata oluştu: {exc}")

    # En son her şeyi tekrar kaydet
    with open(CIKIS_YOLU, "w", encoding="utf-8") as f:
        json.dump(testler, f, ensure_ascii=False, indent=2)

    print(f"Bitti! İşlemler {CIKIS_YOLU} dosyasına kaydedildi.")

if __name__ == "__main__":
    ana_islem()