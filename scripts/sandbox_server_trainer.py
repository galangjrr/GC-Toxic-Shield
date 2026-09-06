import json
import pickle
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline

def train_model():
    print("Membaca dataset data_training.json...")
    with open("data_training.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    sentences = [item["text"] for item in data["sentences"]]
    labels = [item["label"] for item in data["sentences"]]
    
    print(f"Total data: {len(sentences)} kalimat.")
    
    # Membuat Pipeline ML
    # TfidfVectorizer: Memecah kalimat menjadi token, menghitung bobot per kata
    # LinearSVC: Support Vector Machine ringan untuk klasifikasi teks
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2))), 
        ('clf', LinearSVC(random_state=42, dual=False))
    ])
    
    print("Melatih model AI (Training)...")
    pipeline.fit(sentences, labels)
    
    # Menyimpan model (export)
    model_path = "nlp_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(pipeline, f)
        
    file_size = os.path.getsize(model_path) / 1024
    print(f"Model berhasil dilatih dan disimpan ke '{model_path}'!")
    print(f"Ukuran otak AI: {file_size:.2f} KB (Sangat Ringan!)")

if __name__ == "__main__":
    train_model()
