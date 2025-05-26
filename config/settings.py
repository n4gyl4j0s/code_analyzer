# config/settings.py
import os
from dotenv import load_dotenv

# A .env fájl betöltése a konfiguráció felülírásához.
# Ezt a fő belépési pont (main.py) hívja meg, de itt is lehet,
# hogy a modul önmagában is használható legyen teszteléshez.
load_dotenv()

# --- LLM és API Konfiguráció ---
# Az alapértelmezett szerver mód. A .env fájl felülírhatja.
SERVER_MODE = os.getenv("SERVER_MODE", "L") # Alapértelmezés 'L' (localhost)

# API végpontok a különböző szerver módokhoz.
API_URLS = {
    'L': os.getenv("LLM_API_URL_L", "http://localhost:1234/v1"),
    'H': os.getenv("LLM_API_URL_H", "http://192.168.0.1:1234/v1"),
    'I': os.getenv("LLM_API_URL_I", "http://10.1.2.3:30868/v1")
}

# A használt LLM modell neve és az API kulcs.
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "phi-4-14b-q6_k")


# --- Naplózási Fájlnevek ---
# Ezeket a fájlokat a projekt gyökérkönyvtárában fogja létrehozni a script.
THOUGHTS_LOG_FILE_NAME = "llm_thoughts_v2.3.log"
DIRECT_LLM_INTERACTIONS_LOG_FILE_NAME = "llm_interactions_direct_v2.3.log"
LLM_INTERACTION_LOG_FILE = "llm_interactions_v2.3.log" # A BaseCallbackHandler számára

# --- Shell Eszköz Konfiguráció ---
# Engedélyezett shell parancsok listája.
ALLOWED_SHELL_COMMANDS = ['ls', 'pwd', 'cat', 'head', 'tail', 'find', 'rg', 'grep', 'file', 'tree', 'wc']

# A shell parancsok kimenetének maximális hossza karakterekben.
MAX_SHELL_OUTPUT_LENGTH = 15000

# A shell parancsok időtúllépési határa másodpercekben.
SHELL_TIMEOUT_SECONDS = 45

# --- Kódelemző Eszközök Konfigurációja ---
# Az AST és Ctags eszközök által visszaadott eredmények maximális hossza.
MAX_AST_RESULT_LEN = 15000
MAX_RETURNED_TAGS = 5

# A kódrészlet-olvasó által visszaadott snippet maximális hossza.
MAX_SNIPPET_LENGTH = 15000