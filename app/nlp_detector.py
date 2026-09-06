import os
import pickle
import logging

try:
    import sklearn
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger("GCToxicShield.NLPDetector")

class NLPDetector:
    def __init__(self, model_path="nlp_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.is_loaded = False
        
        self.load_model()

    def load_model(self):
        if not SKLEARN_AVAILABLE:
            logger.warning("Scikit-Learn tidak terpasang. NLP tidak aktif.")
            return False

        if not os.path.exists(self.model_path):
            logger.warning(f"Model NLP tidak ditemukan di {self.model_path}.")
            return False

        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            self.is_loaded = True
            logger.info("Model NLP berhasil dimuat.")
            return True
        except Exception as e:
            logger.error(f"Gagal memuat model NLP: {e}")
            self.is_loaded = False
            return False

    def is_toxic(self, text: str) -> bool:
        """
        Gunakan model AI untuk memprediksi apakah teks kotor.
        Kembalikan True jika toxic (label 1), False jika tidak (label 0).
        """
        if not self.is_loaded or self.model is None:
            return False
        
        try:
            prediction = self.model.predict([text])
            return bool(prediction[0] == 1)
        except Exception as e:
            logger.error(f"Kesalahan saat AI memprediksi teks: {e}")
            return False
