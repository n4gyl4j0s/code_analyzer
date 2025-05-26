# tools/__init__.py
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# LangChain import
from langchain.agents import Tool

# A csomag al-moduljainak importálása
from . import system_tools
from . import code_tools
from . import ast_tools
from . import project_context_tools

logger = logging.getLogger(__name__)

# Csomag-szintű globális változók az adatok tárolására
_project_root_global: Optional[str] = None
_ctags_data_global: Optional[Dict[str, List[Dict[str, Any]]]] = None
_ast_data_global: Optional[Dict[str, Dict[str, Any]]] = None
_narrative_context_global: Optional[str] = None


def initialize_tool_data(
    project_root: str,
    ctags_data: Optional[Dict[str, List[Dict[str, Any]]]],
    ast_data: Optional[Dict[str, Dict[str, Any]]],
    narrative_context: Optional[str]
):
    """
    Inicializálja az eszközök által használt adatokat és a projekt gyökerét.
    Beállítja a csomag-szintű globális változókat, és átadja őket
    az al-moduloknak is.
    """
    global _project_root_global, _ctags_data_global, _ast_data_global, _narrative_context_global
    
    _project_root_global = project_root
    _ctags_data_global = ctags_data
    _ast_data_global = ast_data
    _narrative_context_global = narrative_context

    # Az adatok beállítása az al-modulok saját globális változóiban is
    system_tools._project_root_global = _project_root_global
    code_tools._project_root_global = _project_root_global
    code_tools._ctags_data_global = _ctags_data_global
    ast_tools._ast_data_global = _ast_data_global
    project_context_tools._narrative_context_global = _narrative_context_global

    logger.info("Eszközadatok sikeresen inicializálva a 'tools' csomagban.")
    logger.debug(f"  Projekt gyökér: {_project_root_global}")
    logger.debug(f"  Ctags adatok betöltve: {True if _ctags_data_global else False}")
    logger.debug(f"  AST adatok betöltve: {True if _ast_data_global else False}")
    logger.debug(f"  Narratív kontextus elérhető: {True if _narrative_context_global else False}")


def get_all_tools() -> Tuple[List[Tool], str]:
    """
    Összeállítja az elérhető eszközök listáját és a hozzájuk tartozó
    stratégiai útmutatót a betöltött adatok alapján.

    Returns:
        Tuple[List[Tool], str]: Egy tuple, amely tartalmazza a Tool objektumok
                                listáját és a dinamikusan generált útmutatót.
    """
    final_active_tools_list: List[Tool] = []

    # --- Eszközök definiálása és hozzáadása a listához ---

    # 1. Shell Eszköz
    shell_tool_description = (
        f"Végrehajt egy shell parancsot a rendszeren. Engedélyezett parancsok: {system_tools.ALLOWED_SHELL_COMMANDS}. "
        f"A bemenetnek érvényes JSON-nak kell lennie: {{'command': 'parancs argumentumokkal'}}. "
        f"KRITIKUS: A parancson belüli idézőjeleket helyesen kell escapelni (\\\" a stringen belül).\n\n"
        f"Példák:\n"
        f"- Könyvtár tartalmának listázása: {{'command': 'ls -la src/main'}}\n"
        f"- Könyvtárfa listázása 2 szint mélyen: {{'command': 'tree -L 2'}}\n"
        f"- Fájl tartalmának megtekintése: {{'command': 'cat pom.xml'}}\n"
        f"- Keresés egy fájltípusban (`rg`): {{'command': 'rg \\\"X-Forwarded-For\\\" src --type java -l'}}\n"
        f"- Keresés több fájltípusban (`rg`): {{'command': 'rg \\\"Exception\\\" . --type java --type xml -C 3'}}\n"
        f"- Fájl keresése név alapján (`find`): {{'command': 'find . -name \\\"MyClass.java\\\" -print'}}\n"
        f"- Komplex keresés `find` és `grep` paranccsal: {{'command': 'find . -type f \\\\( -name \\\"*.java\\\" -o -name \\\"*.js\\\" \\\\) -exec grep -l \\\"X-Forwarded-For\\\" {{}} \\\\;'}}"
        )
    shell_tool = Tool(
        name="execute_shell_command",
        func=system_tools.tool_wrapper_execute_shell_command,
        description=shell_tool_description
    )
    final_active_tools_list.append(shell_tool)

    # 2. Projekt Jellemzők Azonosító Eszköz
    identify_project_tool = Tool(
        name="identify_project_characteristics",
        func=system_tools.tool_wrapper_identify_project_info,
        description=("Azonosítja egy projekt főbb jellemzőit (nyelv, keretrendszerek, stb.) a fájlrendszer alapján. "
                     "JSON input: {'path': 'opcionális_könyvtár'}. Ha a 'path' nincs megadva, a projekt gyökerét elemzi.")
    )
    final_active_tools_list.append(identify_project_tool)

    # 3. Kódrészlet Olvasó Eszköz (feltételes)
    if code_tools._HAS_CODE_RETRIEVER_MODULE:
        code_snippet_tool = Tool(
            name="get_code_snippet",
            func=code_tools.tool_wrapper_get_code_snippet,
            description=("Beolvas egy kódrészletet fájlból sorszámok alapján. "
                         "JSON input: {'file_path': 'src/My.java', 'start_line': 10, 'end_line': 25 (opc.)}.")
        )
        final_active_tools_list.append(code_snippet_tool)

    # 4. V1 Összefoglaló Eszköz (feltételes)
    v1_summary_available = (_narrative_context_global and not _narrative_context_global.startswith("Nincs elérhető"))
    if v1_summary_available:
        v1_summary_tool = Tool(
            name="get_project_summary_v1",
            func=project_context_tools.tool_wrapper_get_v1_summary,
            description=("Visszaadja a projekt magas szintű, szöveges összefoglalóját egy korábbi (V1) elemzés alapján. "
                         "Nem vár argumentumokat (JSON input: {}).")
        )
        final_active_tools_list.append(v1_summary_tool)

    # 5. Ctags Kereső Eszköz (feltételes)
    if _ctags_data_global:
        ctags_tool = Tool(
            name="search_ctags_symbols",
            func=code_tools.tool_wrapper_search_ctags,
            description=("Keres egy szimbólum (függvény, osztály, stb.) definícióját a Ctags indexben. "
                         "JSON input: {'symbol_name': 'keresett_nev', 'filepath_hint': 'opc_fajl_utvonal'}.")
        )
        final_active_tools_list.append(ctags_tool)

    # 6. AST Lekérdező Eszköz (feltételes)
    if _ast_data_global:
        ast_tool_description = """Előfeldolgozott AST (Absztrakt Szintaxis Fa) adatok lekérdezése adott fájlra. Input: JSON {'file_path': '...', 'query_type': '...', ...}. Az AST adatok gazdagok (osztályszerepkör, végpont-részletek: útvonal, HTTP metódus). PRIORITÁS: Strukturális/szemantikus elemzésre, főleg kontrollerek/végpontok azonosítására, ha az AST elérhető. Előtte le kell kérni a releváns fileok listáját pl: rg -l "@(RequestMapping|GetMapping|PostMapping)" --glob "*Controller.java"
Támogatott 'query_type'-ok (kulcsok: file_path mindenhol kötelező):
1. 'get_method_parameters': Metódus paraméterei. További kulcsok: 'method_name', (opc: 'class_name'). Példa: {"query_type": "get_method_parameters", "file_path": "src/main/hu/example/controller/MyController.java", "class_name": "C", "method_name": "m"}
2. 'get_element_annotations': Osztály/metódus annotációi. További kulcsok: 'element_name', (opc: 'element_type': "class"|"method"). Példa: {"query_type": "get_element_annotations", "file_path": "src/main/hu/example/controller/MyController.java", "element_name": "C", "element_type": "class"}
3. 'get_class_fields': Osztály mezői. További kulcsok: 'class_name'. Példa: {"query_type": "get_class_fields", "file_path": "src/main/hu/example/controller/MyController.java", "class_name": "C"}
4. 'find_method_calls': Metódushívások metóduson belül. További kulcsok: 'method_name', (opc: 'class_name', 'callee_name_filter'). Példa: {"query_type": "find_method_calls", "file_path": "src/main/hu/example/controller/MyController.java", "method_name": "m"}
5. 'get_file_structure_summary': Fájl teljes AST JSON struktúrája. Óvatosan (nagy kimenet); specifikusabb query-k jobbak. Példa: {"query_type": "get_file_structure_summary", "file_path": "src/main/hu/example/controller/MyController.java"}
6. 'get_controllers_in_file': Kontroller osztályok listája fájlból (név, annotációk, AST). Példa: {"query_type": "get_controllers_in_file", "file_path": "src/main/hu/example/controller/MyController.java"}
7. 'get_endpoints_from_file': Fájl összes HTTP végpontja (osztály, metódus, útvonal, HTTP metódus, paraméterek). PREFERÁLT végpontfelderítésre. Példa: {"query_type": "get_endpoints_from_file", "file_path": "src/main/hu/example/controller/MyController.java"}
Válasz: JSON lista/dictionary vagy hibaüzenet."""
        ast_tool = Tool(
            name="query_ast_data",
            func=ast_tools.tool_wrapper_query_ast,
            description=ast_tool_description
        )
        final_active_tools_list.append(ast_tool)

    # --- Stratégiai Útmutató Dinamikus Generálása ---
    
    strategic_guidance_parts = []
    if v1_summary_available: strategic_guidance_parts.append("Kezdd a `get_project_summary_v1` eszközzel a magas szintű áttekintésért.")
    else: strategic_guidance_parts.append("A V1 projekt összefoglaló (`get_project_summary_v1`) nem érhető el.")
    
    if _ctags_data_global: strategic_guidance_parts.append("Szimbólum definíciókhoz használd a `search_ctags_symbols` eszközt.")
    else: strategic_guidance_parts.append("A Ctags alapú szimbólumkeresés (`search_ctags_symbols`) NEM elérhető.")

    if _ast_data_global: strategic_guidance_parts.append("Részletes kódszerkezeti lekérdezésekhez az `query_ast_data` a preferált.")
    else: strategic_guidance_parts.append("Az AST alapú kódelemzés (`query_ast_data`) NEM elérhető.")

    if not v1_summary_available and not _ctags_data_global and not _ast_data_global:
        strategic_guidance_parts.append(
            "Mivel semmilyen előfeldolgozott adat nem áll rendelkezésre, kövesd ezt a stratégiát: "
            "1. `identify_project_characteristics` a technológiai stack megértéséhez. "
            "2. `execute_shell_command` a mélyebb feltáráshoz (`ls`, `rg`). "
            "3. `get_code_snippet` a releváns kódrészletek vizsgálatához."
        )
    
    final_strategic_guidance = " ".join(strategic_guidance_parts)
    logger.debug(f"Dinamikusan generált stratégiai útmutató: {final_strategic_guidance}")

    return final_active_tools_list, final_strategic_guidance