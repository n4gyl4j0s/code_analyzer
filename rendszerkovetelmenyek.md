# Rendszerkövetelmények

## Hardver 🖥️

### Grafikus kártya (GPU)
- **Minimum:** 12 GB VRAM
- **Ajánlott modellek:** 
  - NVIDIA RTX 3060 (12GB)
  - RTX 3500 Ada
  - RTX 4060 Ti (16GB) vagy erősebb
- **Megjegyzés:** A megadott nyelvi modell (8B Q4_K_M) VRAM használata kb. 6-7 GB, de a rendszer és egyéb folyamatok miatt a 12 GB-os kártya stabil működést biztosít.

### Memória (RAM)
- **Minimum:** 32 GB

### Tárhely
- **Minimum:** 10 GB szabad hely a modelleknek és a Python környezetnek

## Szoftveres környezet ⚙️

### Operációs rendszer
- **Windows:** 10/11 (WSL2-vel)
- **Linux:** Ajánlott (pl. Ubuntu 22.04)
- **macOS:** Apple Silicon chipekkel

### Python verzió
- **Python 3.10** vagy **Python 3.11**

### LLM szerver
Egy OpenAI-kompatibilis API-t biztosító szoftver szükséges.

**Ajánlott szoftverek:**
- LM Studio
- Oobabooga Text Generation WebUI
- NVIDIA NIM

### Külső eszközök
- **`git`** - verziókezeléshez
- **`ripgrep` (`rg`)** - hatékony, kódban való kereséshez (opcionális, de erősen ajánlott)

## Nyelvi Modell Beállítása 🧠

### Ajánlott modell
- **Modell:** `Qwen2-7B-Instruct-GGUF` 
- **Forrás:** `Qwen/Qwen2-7B-Instruct-GGUF` repository
- **Verzió:** `q4_K_M` kvantált verzió (jó egyensúlyt kínál a méret és a teljesítmény között)

### Letöltés
A modellt az alábbi módokon lehet letölteni:
- LM Studio beépített keresőjével
- Közvetlenül a Hugging Face-ről

### Szerver beállítások
Az LLM szervert a következőképpen kell konfigurálni:
- **GPU terhelés:** Maximális (`GPU offload: max`)
- **API végpont:** Helyi szerver indítása (pl. `http://localhost:1234/v1`)

## Projekt előfeltételei 📋

A kódelemző teljes funkcionalitásához a vizsgálandó projekthez a következő, előfeldolgozott adatfájlokra lehet szükség:

### Ctags fájl
- **Fájl:** `tags` fájl
- **Generálás:** `ctags` programmal a projekt forráskódjából

### AST fájl
- **Fájl:** `ast_input.jsonl` fájl
- **Tartalom:** A forráskód Absztrakt Szintaxis Fáinak (AST) JSON reprezentációja

