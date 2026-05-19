import os
import fitz  # PyMuPDF
from rag_hafıza import DersHafizasi

def metni_parcalara_bol(metin, max_karakter=1500):
    """
    Uzun metinleri daha küçük parçalara (chunk) böler,
    böylece vektör araması daha verimli olur ve limitlere takılmaz.
    """
    parcalar = []
    for i in range(0, len(metin), max_karakter):
        parcalar.append(metin[i:i + max_karakter])
    return parcalar

def kitaplari_vektore_ekle():
    kitaplar_dizini = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kitaplar")
    bellek = DersHafizasi()
    
    if not os.path.exists(kitaplar_dizini):
        print(f"[HATA] Kitaplar dizini bulunamadı: {kitaplar_dizini}")
        return

    pdf_dosyalari = [f for f in os.listdir(kitaplar_dizini) if f.lower().endswith(".pdf")]
    
    if not pdf_dosyalari:
        print("[BİLGİ] 'kitaplar' klasöründe PDF dosyası bulunamadı.")
        return

    print(f"Toplam {len(pdf_dosyalari)} kitap bulundu. İşlem başlıyor...")
    toplam_parca = 0

    for dosya_adi in pdf_dosyalari:
        dosya_yolu = os.path.join(kitaplar_dizini, dosya_adi)
        print(f"\n[{dosya_adi}] işleniyor...")
        
        try:
            doc = fitz.open(dosya_yolu)
            kitap_metni = ""
            
            for sayfa in doc:
                text = sayfa.get_text("text")
                if text:
                    kitap_metni += text + "\n"
                    
            # Metni temizle ve parçalara böl
            kitap_metni = " ".join(kitap_metni.split())
            parcalar = metni_parcalara_bol(kitap_metni, max_karakter=1500)
            
            for i, parca in enumerate(parcalar):
                # Her bir parçayı "ders_kitabi" kategorisiyle hafızaya yaz
                bellek.bellege_yaz(parca, kategori="ders_kitabi")
                
                if (i + 1) % 100 == 0:
                    print(f"  - {dosya_adi}: {i + 1} parça eklendi...")
            
            toplam_parca += len(parcalar)
            print(f"[{dosya_adi}] tamamlandı. ({len(parcalar)} parça eklendi)")
            
        except Exception as e:
            print(f"[HATA] {dosya_adi} işlenirken bir sorun oluştu: {e}")

    print(f"\nİşlem bitti! Toplam {toplam_parca} parça bilgi hafızaya eklendi.")

if __name__ == "__main__":
    kitaplari_vektore_ekle()
