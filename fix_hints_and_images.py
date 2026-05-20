import os
import sys
import json
import re
import time
from pathlib import Path
import requests

# Windows terminal encoding ayarı
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(r"D:\zemu")
HINTS_JSON_YOLU = BASE_DIR / "data" / "tests_with_hints.json"
CROP_KLASORU = BASE_DIR / "data" / "question_crops"

# Excluded tests (ezilmeyecek testler)
EXCLUDED_TESTS = {
    "30233234_Matematik_5_-_KazanYm_Tarama_Testi_-2",
    "Matematik5-Test-1",
    "Matematik 5 Kazanım Tarama Testi 1"
}

# API Anahtarı yükleme
api_key = None
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
    print("HATA: MISTRAL_API_KEY .env dosyasında bulunamadı!")
    sys.exit(1)

def call_mistral(prompt, system_instruction):
    api_url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 150
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            if response.status_code == 429:
                bekleme = (attempt + 1) * 5
                print(f"    [API Limiti] Çok hızlı istek atıldı, {bekleme} saniye bekleniyor...")
                time.sleep(bekleme)
                continue
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            print(f"    [HATA (API)]: {e}")
            return None
    return None

def generate_educational_hint(soru):
    dogru_cevap = soru.get("dogruCevap", "").strip()
    secenekler = soru.get("secenekler", {})
    soru_metni = soru.get("soruMetni", "")
    durum = soru.get("durum", "TEMİZ")
    
    secenekler_str = "\n".join([f"{k}) {v}" for k, v in secenekler.items() if v])
    prompt = f"Soru:\n{soru_metni}\n\nŞıklar:\n{secenekler_str}"
    
    dogru_secenek_metni = secenekler.get(dogru_cevap, "").strip() if dogru_cevap in secenekler else ""
    
    if durum == "GÖRSEL_İÇERİKLİ" or durum == "BOZUK" or "![img" in soru_metni:
        visual_rule = (
            "4. ÖNEMLİ: Bu soru görsel içeriklidir. Sen görseli göremiyorsun! Bu yüzden görseldeki nesnelerin "
            "konumlarını, yönlerini, sayılarını veya görseldeki spesifik detayları tarif etmeye (örn: '2 birim yukarıda', 'mavi çizgi', '3 adet çokgen') "
            "çalışma, çünkü yanlış tahmin edebilirsin! Bunun yerine öğrenciye görseli nasıl incelemesi gerektiğini söyleyen, "
            "kavramsal ve metodolojik bir ipucu ver. Örn: 'A noktasının B noktasına göre konumunu belirlemek için B'den başlayarak "
            "yatay ve dikey yönde kaç birim ilerlendiğini kareleri sayarak bulabilirsin.' veya 'Açının dik, dar ya da geniş "
            "açı olup olmadığını anlamak için kare çizgisini referans alabilirsin.'"
        )
    else:
        visual_rule = "4. Öğrenciye formülü, kuralı veya tanımı hatırlat."
        
    system_instruction = (
        "Sen 'Zemu' adında, ortaokul öğrencilerine yardımcı olan bir yapay zeka eğitim asistanısın.\n"
        f"Soru için DOĞRU CEVAP: '{dogru_cevap}' şıkkıdır (İçeriği: '{dogru_secenek_metni}').\n\n"
        "İPUCU HAZIRLAMA KURALLARI:\n"
        "1. Doğru cevabı doğrudan söyleme, öğrenciye çözümü kendisi bulması için sadece yol göster.\n"
        f"2. Doğru cevap şıkkının harfini ('{dogru_cevap}') veya doğru şıkkın içeriğinde geçen kelimeleri ('{dogru_secenek_metni}') "
        "KESİNLİKLE ipucunun içinde geçirme! Örneğin doğru şık 'Doğru parçası' ise, ipucunda 'doğru parçası' kelimesini kullanma.\n"
        "3. İpucunu çok kısa (en fazla 1-2 cümle) tut.\n"
        f"{visual_rule}\n"
        "5. Asla 'Zemu:', 'İşte ipucun:', 'Merhaba' gibi başlangıçlar yapma. Doğrudan ipucu cümlesini yaz."
    )
    
    return call_mistral(prompt, system_instruction)

def hint_needs_fixing(soru):
    hint = soru.get("ipucu_ai", "").strip()
    if not hint:
        return True
    
    hint_lower = hint.lower()
    
    # 1. Hata mesajları veya geçici ipuçları
    error_keywords = [
        "yoğunluk var", "teknik bir sorun", "cevap veremiyor", "hata:", 
        "odaklanamadım", "tekrar dener misin", "limit", "görselini inceleyerek doğru sonuca"
    ]
    if any(kw in hint_lower for kw in error_keywords):
        return True
        
    # 2. Doğru cevap A, B, C veya D ise
    dogru = soru.get("dogruCevap", "").strip().upper()
    if dogru in ["A", "B", "C", "D"]:
        # Harfin kendisini cevap olarak söylüyor mu? (Örn: "cevap B")
        letter_patterns = [
            rf"\b{dogru.lower()}\b\s*şık",
            rf"cevap\s*:\s*\b{dogru.lower()}\b",
            rf"cevap\s*\b{dogru.lower()}\b",
            rf"doğru\s*cevap\s*\b{dogru.lower()}\b",
            rf"doğru\s*şık\s*\b{dogru.lower()}\b"
        ]
        for pattern in letter_patterns:
            if re.search(pattern, hint_lower):
                return True
                
        # Şık içeriğini sızdırıyor mu?
        ans_text = soru["secenekler"].get(dogru, "").strip()
        if ans_text:
            ans_text_lower = ans_text.lower()
            if len(ans_text_lower) == 1:
                # Tek harflik şıklar (Örn: Soru 6'da B seçeneği E)
                if re.search(r"\b" + re.escape(ans_text_lower) + r"\b", hint_lower):
                    return True
            else:
                is_numeric = re.match(r"^[\d\s,.-]+$", ans_text) is not None
                if is_numeric:
                    # Sayısal değer sızdırma kalıpları
                    numeric_patterns = [
                        rf"cevap\s*{re.escape(ans_text_lower)}",
                        rf"{re.escape(ans_text_lower)}\s*olur",
                        rf"{re.escape(ans_text_lower)}\s*derecedir",
                        rf"{re.escape(ans_text_lower)}\s*derece\b",
                        rf"sonuç\s*{re.escape(ans_text_lower)}"
                    ]
                    if any(re.search(pat, hint_lower) for pat in numeric_patterns):
                        return True
                else:
                    # Genel metin şık sızdırma
                    if ans_text_lower in hint_lower:
                        return True
                        
        # 3. Görsel sorularda koordinat/yön sızdırma/tahmin etme
        durum = soru.get("durum", "TEMİZ")
        if durum == "GÖRSEL_İÇERİKLİ" or "![img" in soru.get("soruMetni", ""):
            directional_words = ["sağda", "solda", "aşağıda", "yukarıda", "güneyinde", "kuzeyinde", "doğusunda", "batısında"]
            if any(dw in hint_lower for dw in directional_words):
                return True
                
    return False

def main():
    if not HINTS_JSON_YOLU.exists():
        print("HATA: tests_with_hints.json dosyası bulunamadı!")
        return
        
    with open(HINTS_JSON_YOLU, "r", encoding="utf-8") as f:
        tests = json.load(f)
        
    print(f"Toplam {len(tests)} test yüklendi.")
    
    updated_count = 0
    regenerated_hints = 0
    
    for test in tests:
        test_id = test.get("testId")
        if test_id in EXCLUDED_TESTS:
            print(f"Skipping excluded test: {test_id}")
            continue
            
        print(f"\nProcessing test: {test_id}")
        
        for soru in test.get("sorular", []):
            soru_no = soru.get("soruNo")
            
            # 1. Görsel kontrolü ve durum güncellemesi
            crop_path = CROP_KLASORU / test_id / f"q{soru_no}.png"
            if crop_path.exists():
                soru["soruGorselPath"] = f"data/question_crops/{test_id}/q{soru_no}.png"
                if soru.get("durum") == "TEMİZ":
                    soru["durum"] = "GÖRSEL_İÇERİKLİ"
                    print(f"  Soru {soru_no}: Görsel bulundu, durum GÖRSEL_İÇERİKLİ yapıldı.")
            else:
                soru["soruGorselPath"] = None
                if soru.get("durum") == "GÖRSEL_İÇERİKLİ":
                    soru["durum"] = "TEMİZ"
                    print(f"  Soru {soru_no}: Görsel bulunamadı, durum TEMİZ yapıldı.")
            
            # 2. İpucu kontrolü ve gerekirse yeniden üretilmesi
            if hint_needs_fixing(soru):
                print(f"  Soru {soru_no}: İpucu yetersiz, hatalı veya sızdırıyor. Eskisi: '{soru.get('ipucu_ai')}'")
                new_hint = generate_educational_hint(soru)
                if new_hint:
                    soru["ipucu_ai"] = new_hint
                    print(f"    YENİ İPUCU: '{new_hint}'")
                    regenerated_hints += 1
                else:
                    print("    HATA: Yeni ipucu üretilemedi.")
                
                # API limitlerini korumak için kısa bekleme
                time.sleep(3.0)
                
        updated_count += 1
        
    # Değişiklikleri kaydet
    with open(HINTS_JSON_YOLU, "w", encoding="utf-8") as f:
        json.dump(tests, f, ensure_ascii=False, indent=2)
        
    print(f"\nİşlem tamamlandı!")
    print(f"Güncellenen test sayısı: {updated_count}")
    print(f"Yeniden üretilen AI ipucu sayısı: {regenerated_hints}")

if __name__ == "__main__":
    main()
