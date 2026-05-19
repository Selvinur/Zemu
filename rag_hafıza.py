# YORUM SATIRLARINI KESİNLİKLE OKU !!!!


import chromadb
import ollama
import os
import hashlib

class DersHafizasi:
    def __init__(self, collection_name="egitim_bellek"): # Vektör data base ismi bu olucak. İstersen değiştir. !!
        
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VektorDB")
        
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def bellege_yaz(self, metin, kategori="konu_anlatimi"):
        """
        kategori: "konu_anlatimi", "eski_soru" veya "ders_kitabi" olabilir.
        Böylece ileride sadece sorularda arama yap vs. diyebiliriz.
        """
        if not metin or not metin.strip():
            return 
        
        # BURADA HAFIZAYA KAYDEDİYOR.    
        try:
            # Gömme işlemi için narin ve hızlı bir model (Önceden indirilmiş olmalı: ollama pull nomic-embed-text)
            embedding = ollama.embeddings(model="nomic-embed-text", prompt=metin)["embedding"]
            metin_hash = hashlib.md5(metin.encode("utf-8")).hexdigest()
            
            self.collection.upsert(
                documents=[metin],
                embeddings=[embedding],
                metadatas=[{"kategori": kategori}], 
                ids=[metin_hash]
            )
        except Exception as e:
            print(f"[SİSTEM UYARISI] Ders belleğine yazma başarısız: {e}")

    # ALAKALI OLAN 5 MESAJ YETERLİ OLUR DİYE DÜŞÜNDÜM BU KISIMI DEĞİŞTİRİRSİN.
    # HAFIZAYA NE EKLERSEN ONA GÖRE DEĞİŞİR NE GETİRCEĞİ İNŞALLAH ÇALIŞIR :).
    def sorgula(self, soru, limit=5):
        """Öğrencinin sorusuna en çok benzeyen ders notlarını getirir."""
        try:
            embedding = ollama.embeddings(model="nomic-embed-text", prompt=soru)["embedding"]
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )
            if results["documents"] and results["documents"][0]:
                return results["documents"][0] 
            return []
        
        except Exception as e:
            print(f"[SİSTEM UYARISI] Ders belleği sorgusu başarısız: {e}")
            return []