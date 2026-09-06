import pickle
import os
import sys

def run_client():
    model_path = "nlp_model.pkl"
    if not os.path.exists(model_path):
        print(f"Error: Otak AI '{model_path}' belum ada.")
        print("Harap jalankan 'python sandbox_server_trainer.py' terlebih dahulu untuk melatih otak AI.")
        sys.exit(1)

    print("Memuat Otak AI ke dalam memori Client...")
    with open(model_path, "rb") as f:
        pipeline = pickle.load(f)
        
    print("[+] Otak AI (GC Toxic Shield Client) Siap digunakan!\n")
    print("Ketikan kalimat apapun untuk dites. Ketik 'exit' untuk keluar.")
    print("-" * 50)
    
    while True:
        try:
            text = input("Anda (Transkripsi) > ")
            if text.lower() == 'exit':
                break
            
            if not text.strip():
                continue
                
            # Melakukan tebakan (prediksi) sentimen
            prediction = pipeline.predict([text])[0]
            
            # (Opsional) Mengambil confidence score
            # LinearSVC menggunakan decision_function untuk melihat margin
            score = pipeline.decision_function([text])[0]
            
            if prediction == 1:
                print(f"AI: [DIBLOKIR] (TOXIC) - Kalimat mengandung sentimen ujaran kebencian! (Score: {score:.2f})")
            else:
                print(f"AI: [AMAN] (SAFE) - Kalimat bernada netral/positif. (Score: {score:.2f})")
            print("-" * 50)
            
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    run_client()
