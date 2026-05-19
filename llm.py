# YORUM SATIRLARINI KESİNLİKLE OKU !!!!

import os
import time
from pathlib import Path
from dotenv import load_dotenv
import requests
from rag_hafıza import DersHafizasi

load_dotenv()

class EgitimAsistani:
    def __init__(self, model="mistral-small-latest"): 
        self.model = model
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.api_key = os.getenv("MISTRAL_API_KEY")
        
        if not self.api_key:
            env_dosyasi = Path(r"D:\zemu\.env")
            if env_dosyasi.exists():
                try:
                    env_icerik = env_dosyasi.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    env_icerik = env_dosyasi.read_text(encoding="utf-16")
                for satir in env_icerik.splitlines():
                    if "MISTRAL_API_KEY=" in satir:
                        self.api_key = satir.split("=", 1)[1].strip().strip("'\"")
                        break
                        
        if not self.api_key:
            print("UYARI: .env dosyasında MISTRAL_API_KEY bulunamadı!")
            
        self.bellek = DersHafizasi() # Hafızayı LLM'in içine doğrudan bağladık
        
        self.ana_kurallar = """
        [KİMLİK VE ROL]
        Senin adın 'Zemu'. Ortaokul öğrencileri için geliştirilmiş, yapay zeka destekli bir eğitim ve test çözme asistanısın.
        Sen sert bir öğretmen değil, öğrencinin yanında oturan zeki, sabırlı ve eğlenceli bir çalışma arkadaşısın.

        [KARAKTER VE İLETİŞİM KURALLARI]
        1. Ortaokul düzeyine uygun, samimi, cesaretlendirici ve motive edici bir dil kullan.
        2. ASLA SORUNUN DOĞRU CEVABINI, DOĞRU ŞIKKI (A, B, C, D) VEYA ŞIKLARDAKİ CÜMLEYİ DOĞRUDAN SÖYLEME VE SORUYU ADIM ADIM ÇÖZME! Öğrencinin cevabı kendi bulması için ona sadece minik bir destek ol.
        3. İPUCU VEYA YÖNLENDİRME OLARAK ŞUNLARI YAPABİLİRSİN:
           - Sorudaki önemli bir kelimenin, kavramın veya formülün tanımını kısaca verebilirsin.
           - İşlem önceliğini (önce parantez içi, sonra çarpma-bölme vb.) hatırlatabilirsin.
           - Öğrencinin dikkat etmesi gereken yeri (Örn: "En küçük değeri istiyor, dikkat et") işaret edebilirsin.
        4. Karmaşık kelimeler yerine anlaşılır ve sade bir Türkçe kullan.

        [SİSTEM İŞLEYİŞİ]
        Sana kullanıcının sorusuyla birlikte, arka plandaki hafızadan (ders kitapları, eski sorular) bazı notlar "GİZLİ BAĞLAM" olarak iletilecek. 
        Bu bağlamı sadece öğrenciye ipucu vermek için kullan, öğrenciye "Hafızamda şu yazıyor" deme. Sen o konuyu zaten biliyormuşsun gibi doğal davran.
        Ayrıca sorunun DOĞRU CEVABI da gizli talimat olarak verilebilir, amacın o cevaba giden yolu işaret etmektir, cevabın kendisini söylemek DEĞİL.
        """
        
        self.mesaj_gecmisi = [
            {"role": "system", "content": self.ana_kurallar}
        ]
    
    def soru_cevapla(self, ogrenci_mesaji, gizli_talimat=""):
        # 1. RAG Hafızasından (Ders kitapları, eski sorular) bilgiyi otomatik çek
        hatirlanan_bilgiler = self.bellek.sorgula(soru=ogrenci_mesaji, limit=5)
        
        sistem_mesaji = ""
        if gizli_talimat:
            sistem_mesaji = f"[SİSTEM UYARISI: {gizli_talimat}]\n\n"
            
        # 2. Bağlamı (Context) hazırlayıp LLM'e çaktırmadan yedir
        if hatirlanan_bilgiler:
            baglam_metni = "\n- ".join(hatirlanan_bilgiler)
            zenginlestirilmis_prompt = (
                f"[GİZLİ BAĞLAM: Hafızandan şu ders notlarını ve eski soruları hatırlıyorsun:\n"
                f"- {baglam_metni}\n"
                f"Bu bilgileri kullanarak öğrenciye ipucu ver.]\n\n"
                f"{sistem_mesaji}Öğrenci: {ogrenci_mesaji}"
            )
        else:
            zenginlestirilmis_prompt = f"{sistem_mesaji}Öğrenci: {ogrenci_mesaji}"

        # 3. Mesajı kısa süreli hafızaya (RAM) ekle
        self.mesaj_gecmisi.append({"role": "user", "content": zenginlestirilmis_prompt})
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": self.mesaj_gecmisi,
            "temperature": 0.4,
            "max_tokens": 150
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload)
                
                # Eğer hız sınırına takılırsak bekle ve tekrar dene
                if response.status_code == 429:
                    bekleme = (attempt + 1) * 5
                    print(f"  [API Limiti] Çok hızlı istek atıldı, {bekleme} saniye bekleniyor...")
                    time.sleep(bekleme)
                    continue
                    
                response.raise_for_status() 
                res = response.json()["choices"][0]["message"]["content"].strip()
                
                # Asistanın cevabını sohbet geçmişine ekle
                self.mesaj_gecmisi.append({"role": "assistant", "content": res})
                
                # SON ON MESAJI DA EKLİYORUZ KISA SÜRELİ HAFIZAYA EĞER BİR ÜSTTEKİ KONU HAKKINDA BİR ŞEY TEKRAR SORARSA ANA HAFIZA İLE UĞRAŞMAYIP BURADAN BİLGİ GELİR.
                if len(self.mesaj_gecmisi) > 12:
                    self.mesaj_gecmisi = [self.mesaj_gecmisi[0]] + self.mesaj_gecmisi[-5:]
                    
                return res
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                self.mesaj_gecmisi.pop() # Hata olursa son eklenen öğrenci mesajını sil
                return f"Şu an teknik bir sorun yaşıyorum, soruna tam odaklanamadım. Lütfen tekrar dener misin? (Hata: {e})"
                
        self.mesaj_gecmisi.pop()
        return "Çok fazla yoğunluk var, Zemu şu an cevap veremiyor. Lütfen sayfayı yenileyip daha sonra tekrar dene."
        
# MAİN KODA BU KISIMI EKLERSEN ÇALIŞMAYA BAŞLAR.
"""
Main kodunu şunları eklersen yorumunu alırsın:
    from llm import EgitimAsistani

    Ollamabot = EğitimAsistanı()

    Yapay_zeka_cevabı = Ollamabot.soru_cevapla([Bu kısıma inputun ismi gelicek "ogrenci_mesajı" mesela]) 
"""