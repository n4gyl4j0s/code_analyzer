# ⚠️ Állapot: Archivált / Kísérleti

**Megjegyzés:** Ez a repository egy bizonyíték a helyi LLM-ek LangChain-nel való futtatására. Már nincs aktívan karbantartva, mivel a munkafolyamat cloud-native megoldásokra (GitHub Copilot / VS Code Agent Mode) költözött. Referenciaimplementációként szolgál egyedi LangChain ügynökökhöz és RAG pipeline-okhoz — használja példaként, ne éles megoldásként. Használat saját felelősségre: a kód elavult, hiányos vagy biztonsági kockázatokat tartalmazhat.

# Projekt Elemző LLM Ügynök

Ez a projekt egy Python nyelven írt, [LangChain](https://www.langchain.com/) keretrendszerre épülő intelligens ügynök, amely képes szoftverprojektek forráskódjának elemzésére és a kóddal kapcsolatos kérdések megválaszolására. Az ügynök különböző eszközöket használ (shell parancsok, `ctags`, Absztrakt Szintaxis Fa elemzés) az információk kinyeréséhez.

A projekt erősen modularizált, hogy a karbantarthatóság, tesztelhetőség és bővíthetőség a lehető legegyszerűbb legyen.

## Telepítés és beállítás

### 1. Klónozza a repository-t:
```bash
git clone <repository_url>
cd <repository_mappa>
```

### 2. Hozzon létre egy virtuális környezetet (ajánlott):
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate  # Windows
```

### 3. Telepítse a szükséges Python csomagokat:
```bash
pip install -r requirements.txt
```
*A `requirements.txt` fájlnak legalább a következőket kell tartalmaznia: `langchain`, `langchain-openai`, `python-dotenv`, `tiktoken`.*

### 4. Hozzon létre egy `.env` fájlt:
Hozza létre a projekt gyökérkönyvtárában a `.env` fájlt a konfigurációs változók tárolására. Használja a ` .env.example` fájlt sablonként, és **ne** töltse fel a `.env` fájlt a verziókezelőbe.
```env
# Az LLM szerver címe (pl. LM Studio, Oobabooga)
LLM_API_URL_L="http://localhost:1234/v1"

# A használt modell neve (az LLM szerver által megadott)
LLM_MODEL_NAME="phi-4-14b-q6_k"

# Az LLM API kulcsod (ebben a példában üresen hagyjuk; a saját kulcsodat a helyi .env fájlba írjad)
LLM_API_KEY=
```

**Biztonsági megjegyzés:** Ne tárolj éles API kulcsokat vagy titkokat ebben a repository-ban. Add hozzá a `LLM_API_KEY`-t a helyi `.env`-edhez (vagy használj secret managert), és ügyelj rá, hogy a `.env` szerepeljen a `.gitignore`-ban. CI/CD használatakor a titkokat a CI rendszerben konfiguráld, ne a repo-ban.

### 5. Telepítse a külső eszközöket (opcionális):
A `shell` eszköz hatékonyabb használatához ajánlott a `ripgrep` (`rg`) telepítése.

## Futtatás

A program a `main.py` szkripten keresztül indítható parancssorból.

**Példa a futtatásra:**
```bash
python main.py \
  --project-root "/path/to/your/project/to/analyze" \
  --prompt "Keresd meg az összes olyan Java fájlt, amely az 'X-Forwarded-For' headert használja, és listázd a metódusokat, amelyekben előfordul." \
  --ctags-file "/path/to/your/project/to/analyze/.analyzer_tags" \
  --ast-file "/path/to/your/project/to/analyze/ast_input.jsonl" \
  --debug
```

### Parancssori argumentumok:
- `--project-root`: (Kötelező) A vizsgálandó projekt gyökérkönyvtára.
- `--prompt`: (Kötelező) A kérdés, amit az ügynöknek szegezünk.
- `--v1-context-file`: (Opcionális) Egy korábbi, magas szintű elemzés szöveges összefoglalóját tartalmazó fájl.
- `--ctags-file`: (Opcionális) Az előre generált ctags adatfájl útvonala. Ha nincs megadva, a program keresi a `--project-root` alatt `.analyzer_tags` néven.
- `--ast-file`: (Opcionális) Az előre generált AST adatfájl (.jsonl) útvonala. Ha nincs megadva, a program keresi `ast_input.jsonl` vagy `ast_input.jsonl.gz` néven.
- `--debug`: (Opcionális) Részletesebb naplózás bekapcsolása a konzolra.

## Projekt felépítése

A projekt logikai egységek mentén csomagokba és modulokba van szervezve.

```
projekt_elemzo/
│
├── config/
│   ├── __init__.py
│   └── settings.py
│
├── core/
│   ├── __init__.py
│   ├── agent.py
│   └── llm_wrapper.py
│
├── tools/
│   ├── __init__.py
│   ├── ast_tools.py
│   ├── code_tools.py
│   ├── project_context_tools.py
│   └── system_tools.py
│
├── utils/
│   ├── __init__.py
│   ├── callbacks.py
│   ├── output_parser.py
│   └── logging_setup.py
│
├── prompts/
│   ├── __init__.py
│   └── react_template.py
│
└── main.py
```

## Komponensek részletezése

### main.py (Belépési Pont) ▶️
Ez a szkript az alkalmazás indításáért felel. Csak a parancssori argumentumok feldolgozását, a konfiguráció és a naplózás beállítását, valamint a központi `core.agent` modul meghívását végzi.

### config/settings.py ⚙️
Ez a modul felel a projekt statikus konfigurációjáért, egy központi helyre gyűjtve a beállításokat. Könnyen módosítható anélkül, hogy a program logikájába bele kellene nyúlni. Támogatja az értékek `.env` fájlból való felülírását.

### core/ (A mag) 🧠
Itt található az alkalmazás központi logikája, amely összefogja a többi komponenst.

- **agent.py**: A fő vezérlési logika. Ez a modul felelős az összes többi komponens (LLM, eszközök, promptok) összehangolásáért, az ügynök felépítéséért és a futtatás vezérléséért.
- **llm_wrapper.py**: Egy egyedi `LLMWithOutputFixer` osztályt definiál, amely becsomagolja a standard LangChain LLM-et. A felelőssége, hogy minden LLM-választ átfuttasson egy javító parseren, mielőtt az visszakerülne az ügynökhöz, így biztosítva a strukturált és tiszta kimenetet.

### tools/ (Eszközök csomagja) 🧰
Az ügynök által használható összes eszköz logikája egy önálló Python csomagba került, témakörök szerint bontva.

- **__init__.py**: A csomag "kapuja". Inicializálja az eszközökhöz szükséges adatokat (pl. AST adatok) és dinamikusan összeállítja az aktív eszközök listáját a `get_all_tools()` függvénnyel.
- **system_tools.py**: A rendszerrel és a fájlrendszerrel való általános interakciókért felelős eszközök (pl. `execute_shell_command`, `identify_project_characteristics`).
- **code_tools.py**: A forráskóddal közvetlenül foglalkozó eszközök (pl. `get_code_snippet` a kódrészletek olvasásához, `search_ctags_symbols` a ctags alapú kereséshez).
- **ast_tools.py**: Az előfeldolgozott Absztrakt Szintaxis Fa (AST) adatok lekérdezéséért felelős eszközök, amelyek mély, strukturális információkat nyernek ki a kódból.
- **project_context_tools.py**: A projekt magas szintű, előfeldolgozott kontextusával kapcsolatos eszközök (pl. `get_project_summary_v1`).

### utils/ (Segédfüggvények csomagja) 🛠️
Általános célú, a projekt több pontján is felhasználható függvényeket és osztályokat tartalmaz.

- **logging_setup.py**: Központilag állítja be az alkalmazás naplózási (logging) viselkedését.
- **callbacks.py**: Egyedi LangChain CallbackHandler-ek az LLM-interakciók és eszközhívások részletes naplózásához és konzolon való megjelenítéséhez.
- **output_parser.py**: A projekt egyik legfontosabb segédmodulja, amely az LLM által generált, esetenként hibás szöveges kimenetet alakítja át tiszta, strukturált formátumra, amit az ügynök fel tud dolgozni.

### prompts/ (Prompt Sablonok) 📝
A nagyméretű és komplex promptok elkülönítése a kódtól nagyban javítja az átláthatóságot és a karbantarthatóságot.

- **react_template.py**: Tartalmazza a fő ReAct prompt sablont és azt a logikát, amely dinamikusan, a rendelkezésre álló eszközök alapján építi fel a végső promptot.
