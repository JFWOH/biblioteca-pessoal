import time
import os
import sys

def main():
    print("Forcing offline mode...")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

    t0 = time.time()
    print("Importing kokoro...")
    import kokoro
    t1 = time.time()
    print(f"Imported in {t1 - t0:.2f}s")

    print("Initializing pipeline...")
    t2 = time.time()
    pipeline = kokoro.KPipeline(lang_code='p')
    t3 = time.time()
    print(f"Pipeline initialized in {t3 - t2:.2f}s")

    print("Starting synthesis...")
    t4 = time.time()
    generator = pipeline("Olá, mundo. Este é um teste de velocidade de síntese no Kokoro.", voice='pf_dora', speed=1.0)
    
    first_chunk_received = False
    for i, result in enumerate(generator):
        if not first_chunk_received:
            t5 = time.time()
            print(f"Time to first chunk (TTFB): {t5 - t4:.2f}s")
            first_chunk_received = True
        
        gs, ps, audio = result
        print(f"Chunk {i} generated.")
    
    t6 = time.time()
    print(f"Total synthesis time: {t6 - t4:.2f}s")

if __name__ == '__main__':
    main()
