# tools/code_tools.py
import os
import logging
import json
from typing import Optional, List, Dict, Any

# Belső importok a projekt struktúrából
from utils.output_parser import clean_llm_action_input
from config.settings import MAX_SNIPPET_LENGTH, MAX_RETURNED_TAGS

# Logger példányosítása a modulhoz
logger = logging.getLogger(__name__)

# A code_retriever.py-t a projekt gyökeréből próbáljuk importálni
# (feltéve, hogy a main.py beállította a sys.path-ot)
try:
    import code_retriever #
    _HAS_CODE_RETRIEVER_MODULE = True
    logger.info("code_retriever.py sikeresen importálva a tools.code_tools modulba.")
except ImportError:
    _HAS_CODE_RETRIEVER_MODULE = False
    logger.warning("tools/code_tools.py: code_retriever.py modul nem található a projekt gyökerében. A get_code_snippet eszköz nem lesz működőképes.")

_project_root_global: Optional[str] = None
_ctags_data_global: Optional[Dict[str, List[Dict[str, Any]]]] = None # Ezt a parsolt adatot kapja az __init__.py-ból



# --- Kódrészlet Olvasó Eszköz ---

def tool_wrapper_get_code_snippet(action_input_str: str) -> str:
    """
    LangChain Eszköz: Beolvas egy kódrészletet fájlból sorszámok alapján.
    """
    logger.info(f"Eszköz HÍVVA: get_code_snippet, input: {action_input_str}")
    action_input_str = clean_llm_action_input(action_input_str)
    
    if not _HAS_CODE_RETRIEVER_MODULE:
        return "Hiba: A kódrészlet-olvasó modul (code_retriever.py) nem érhető el."
    if not _project_root_global:
        logger.warning("get_code_snippet: Projekt gyökér nincs beállítva. Csak abszolút útvonalak fognak működni.")
    
    try:
        args = json.loads(action_input_str)
        file_path_relative = args.get("file_path")
        start_line_str = args.get("start_line")
        end_line_str = args.get("end_line")

        if not file_path_relative or not isinstance(file_path_relative, str):
            return "Hiba: Érvénytelen vagy hiányzó 'file_path' argumentum."
        if start_line_str is None:
            return "Hiba: Hiányzó 'start_line' argumentum."

        try:
            start_line_int = int(start_line_str)
        except (ValueError, TypeError):
            return f"Hiba: A 'start_line' ({start_line_str}) nem érvényes egész szám."

        end_line_int: Optional[int] = None
        if end_line_str is not None:
            try:
                end_line_int = int(end_line_str)
            except (ValueError, TypeError):
                return f"Hiba: Az 'end_line' ({end_line_str}) nem érvényes egész szám."
        
        # A code_retriever.py-ban lévő függvény hívása
        snippet = code_retriever.get_code_snippet(
            file_path_str=file_path_relative,
            start_line=start_line_int,
            end_line=end_line_int,
            project_root_str=_project_root_global
        )
        
        if snippet is None:
            return (f"Kódrészlet nem található vagy nem olvasható a '{file_path_relative}' fájlból "
                    f"(sorok: {start_line_int}-{end_line_int if end_line_int else start_line_int}).")
        
        if len(snippet) > MAX_SNIPPET_LENGTH:
            logger.warning(f"Kiolvasott kódrészlet ({file_path_relative}) túl hosszú, csonkolva.")
            csonkolt_snippet = snippet[:MAX_SNIPPET_LENGTH] + f"\n... [KÓDRÉSZLET CSONKOLVA] ..."
            return csonkolt_snippet
            
        return f"Kódrészlet a '{file_path_relative}' fájlból (sorok: {start_line_int}-{end_line_int if end_line_int else start_line_int}):\n```\n{snippet}\n```"

    except json.JSONDecodeError:
        return "Hiba: Az eszköz ('get_code_snippet') bemenete nem érvényes JSON."
    except Exception as e:
        logger.error(f"Hiba a 'get_code_snippet' eszközben: {e}", exc_info=True)
        return f"Hiba a 'get_code_snippet' eszköz futása közben: {str(e)}"


# --- Ctags Szimbólumkereső Eszköz ---

def tool_wrapper_search_ctags(action_input_str: str) -> str:
    """
    LangChain Eszköz: Keres egy szimbólumot a betöltött Ctags adatokban.
    """
    logger.info(f"Eszköz HÍVVA: search_ctags_symbols, input: {action_input_str}")

    if _ctags_data_global is None:
        return "Hiba: Ctags adatok nincsenek betöltve. Ez az eszköz nem használható."
    
    action_input_str = clean_llm_action_input(action_input_str)
    
    try:
        args = json.loads(action_input_str)
        symbol_name_to_find = args.get("symbol_name")
        filepath_hint_str = args.get("filepath_hint")

        if not symbol_name_to_find or not isinstance(symbol_name_to_find, str):
            return "Hiba: Érvénytelen vagy hiányzó 'symbol_name' argumentum."
        
        logger.debug(f"Ctags keresés: szimbólum='{symbol_name_to_find}', fájl tipp='{filepath_hint_str}'")

        found_tags: List[Dict[str, Any]] = []

        for file_path_from_ctags, tags_in_file_list in _ctags_data_global.items():
            if filepath_hint_str:
                normalized_hint = os.path.normpath(filepath_hint_str)
                normalized_ctags_path = os.path.normpath(file_path_from_ctags)
                if normalized_ctags_path != normalized_hint:
                    continue

            for tag_info in tags_in_file_list:
                if tag_info.get("name") == symbol_name_to_find:
                    tag_copy = tag_info.copy()
                    tag_copy["_source_file"] = file_path_from_ctags
                    found_tags.append(tag_copy)
        
        if not found_tags:
            return f"A '{symbol_name_to_find}' szimbólum nem található a Ctags adatokban" \
                   f"{f' (a(z) {filepath_hint_str} fájlra szűrve)' if filepath_hint_str else ''}."

        if len(found_tags) > MAX_RETURNED_TAGS:
            logger.info(f"Túl sok ({len(found_tags)}) ctags találat, az első {MAX_RETURNED_TAGS} kerül visszaadásra.")
            response_tags = found_tags[:MAX_RETURNED_TAGS]
            message = (f"Ctags találatok '{symbol_name_to_find}' szimbólumra "
                       f"({len(found_tags)} összesen, első {MAX_RETURNED_TAGS} megjelenítve):\n"
                       f"{json.dumps(response_tags, indent=2, ensure_ascii=False)}")
        else:
            message = (f"Ctags találatok '{symbol_name_to_find}' szimbólumra:\n"
                       f"{json.dumps(found_tags, indent=2, ensure_ascii=False)}")
        
        return message

    except json.JSONDecodeError:
        return "Hiba: Az eszköz ('search_ctags_symbols') bemenete nem érvényes JSON."
    except Exception as e:
        logger.error(f"Hiba a 'search_ctags_symbols' eszközben: {e}", exc_info=True)
        return f"Hiba a 'search_ctags_symbols' eszköz futása közben: {str(e)}"