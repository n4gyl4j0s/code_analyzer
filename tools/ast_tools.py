# tools/ast_tools.py
import logging
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

# Belső importok a projekt struktúrából
from utils.output_parser import clean_llm_action_input
from config.settings import MAX_AST_RESULT_LEN

# Logger példányosítása a modulhoz
logger = logging.getLogger(__name__)

# Megjegyzés: Ez a modul a 'tools' csomag globális változóitól függ,
# amelyeket a tools/__init__.py-ban lévő `initialize_tool_data` állít be.
# Különösen a `_ast_data_global` változótól.
_ast_data_global: Optional[Dict[str, Dict[str, Any]]] = None


# --- AST Lekérdező Segédfüggvények ---

def _ast_get_file_data(file_path: str) -> Optional[Dict[str, Any]]:
    """Segédfüggvény: Visszaadja egy adott fájl AST adatait a globális tárolóból."""
    if _ast_data_global is None:
        logger.warning("_ast_get_file_data: Globális AST adatok nincsenek betöltve.")
        return None
    
    data_for_file = _ast_data_global.get(file_path)
    if data_for_file is None:
        logger.warning(f"_ast_get_file_data: Nem található AST adat a '{file_path}' fájlhoz.")
        filename_only = Path(file_path).name
        similar_keys = [k for k in _ast_data_global.keys() if filename_only in k]
        if similar_keys:
            logger.debug(f"  Lehetséges hasonló kulcsok az AST adatokban: {similar_keys[:5]}")
    return data_for_file

def ast_get_method_parameters(file_path: str, class_name: Optional[str], method_name: str) -> List[Dict[str, str]]:
    """Lekéri egy metódus paramétereit az AST adatokból."""
    logger.debug(f"ast_get_method_parameters: file='{file_path}', class='{class_name}', method='{method_name}'")
    file_data = _ast_get_file_data(file_path)
    if not file_data: return []

    for cls_obj in file_data.get("classes", []):
        if class_name is not None and cls_obj.get("name") != class_name: continue
        for method_obj in cls_obj.get("methods", []):
            if method_obj.get("name") == method_name:
                return method_obj.get("parameters", [])
    return []

def ast_get_element_annotations(file_path: str, element_name: str, element_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lekéri egy osztály vagy metódus annotációit az AST adatokból."""
    logger.debug(f"ast_get_element_annotations: file='{file_path}', element='{element_name}', type='{element_type}'")
    file_data = _ast_get_file_data(file_path)
    if not file_data: return []
    
    all_found_annotations = []
    for cls_obj in file_data.get("classes", []):
        if element_type in ("class", None) and cls_obj.get("name") == element_name:
            all_found_annotations.extend(cls_obj.get("annotations", []))
        if element_type in ("method", None):
            for method_obj in cls_obj.get("methods", []):
                if method_obj.get("name") == element_name:
                    all_found_annotations.extend(method_obj.get("annotations", []))
    return all_found_annotations

def ast_get_class_fields(file_path: str, class_name: str) -> List[Dict[str, Any]]:
    """Lekéri egy adott osztály mezőit (fields) az AST adatokból."""
    logger.debug(f"ast_get_class_fields: file='{file_path}', class='{class_name}'")
    file_data = _ast_get_file_data(file_path)
    if not file_data: return []

    for cls_obj in file_data.get("classes", []):
        if cls_obj.get("name") == class_name:
            return cls_obj.get("fields", [])
    return []

def ast_find_method_calls_in_method(file_path: str, class_name: Optional[str], method_name: str, callee_name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lekéri a metódushívásokat egy adott metóduson belül az AST adatokból."""
    logger.debug(f"ast_find_method_calls: file='{file_path}', method='{method_name}', filter='{callee_name_filter}'")
    file_data = _ast_get_file_data(file_path)
    if not file_data: return []

    for cls_obj in file_data.get("classes", []):
        if class_name is not None and cls_obj.get("name") != class_name: continue
        for method_obj in cls_obj.get("methods", []):
            if method_obj.get("name") == method_name:
                calls = method_obj.get("calls", [])
                if callee_name_filter:
                    return [call for call in calls if isinstance(call, dict) and call.get("name") == callee_name_filter]
                return calls
    return []

def ast_get_file_structure_summary(file_path: str) -> Any:
    """Visszaadja a teljes AST struktúrát egy fájlhoz."""
    return _ast_get_file_data(file_path) or {"error": f"Nincs AST adat: {file_path}"}

def ast_get_controllers_in_file(file_path: str) -> Any:
    """Kilistázza az összes 'controller' szerepű osztályt a fájlból."""
    file_data = _ast_get_file_data(file_path)
    if not file_data: return {"error": f"Nincs AST adat: {file_path}"}
    return [
        {"name": cls.get("name"), "annotations": cls.get("annotations")}
        for cls in file_data.get("classes", []) if cls.get("role") == "controller"
    ]

def ast_get_endpoints_from_file(file_path: str) -> Any:
    """Kilistázza az összes végpontot a fájlban, azok részleteivel."""
    file_data = _ast_get_file_data(file_path)
    if not file_data: return {"error": f"Nincs AST adat: {file_path}"}
    
    endpoints = []
    for cls in file_data.get("classes", []):
        class_name = cls.get("name")
        class_base_path = ""
        for anno in cls.get("annotations", []):
            if anno.get("name") == "RequestMapping":
                class_base_path = anno.get("parameters", {}).get("value", "").strip('"\'')
                break
        for method in cls.get("methods", []):
            if method.get("is_endpoint"):
                endpoint_path = method.get("endpoint_path", "").strip('"\'')
                full_path = (class_base_path.rstrip("/") + "/" + endpoint_path.lstrip("/")).strip()
                endpoints.append({
                    "class_name": class_name,
                    "method_name": method.get("name"),
                    "http_method": method.get("http_method"),
                    "full_path": full_path,
                    "parameters": method.get("parameters"),
                })
    return endpoints


# --- Fő AST Eszköz Wrapper ---

def tool_wrapper_query_ast(action_input_str: str) -> str:
    """LangChain Eszköz: Lekérdezéseket végez a betöltött AST adatokon."""
    logger.info(f"Eszköz HÍVVA: query_ast_data, input: {action_input_str}")

    if _ast_data_global is None:
        return "Hiba: AST adatok nincsenek betöltve. Ez az eszköz nem használható."
    
    action_input_str = clean_llm_action_input(action_input_str)
    
    try:
        args = json.loads(action_input_str)
        query_type = args.get("query_type")
        file_path = args.get("file_path")

        if not query_type: return "Hiba: Hiányzó 'query_type' argumentum."
        if not file_path: return "Hiba: Hiányzó 'file_path' argumentum."

        result_data: Any
        if query_type == "get_method_parameters":
            if not args.get("method_name"): return "Hiba: Hiányzó 'method_name'."
            result_data = ast_get_method_parameters(file_path, args.get("class_name"), args["method_name"])
        elif query_type == "get_element_annotations":
            if not args.get("element_name"): return "Hiba: Hiányzó 'element_name'."
            result_data = ast_get_element_annotations(file_path, args["element_name"], args.get("element_type"))
        elif query_type == "get_class_fields":
            if not args.get("class_name"): return "Hiba: Hiányzó 'class_name'."
            result_data = ast_get_class_fields(file_path, args["class_name"])
        elif query_type == "find_method_calls":
            if not args.get("method_name"): return "Hiba: Hiányzó 'method_name'."
            result_data = ast_find_method_calls_in_method(file_path, args.get("class_name"), args["method_name"], args.get("callee_name_filter"))
        elif query_type == "get_file_structure_summary":
            result_data = ast_get_file_structure_summary(file_path)
        elif query_type == "get_controllers_in_file":
            result_data = ast_get_controllers_in_file(file_path)
        elif query_type == "get_endpoints_from_file":
            result_data = ast_get_endpoints_from_file(file_path)
        else:
            return f"Hiba: Ismeretlen 'query_type': {query_type}."

        if not result_data:
            return f"A lekérdezés ('{query_type}') nem hozott eredményt, vagy a kért elem nem létezik."

        json_result_str = json.dumps(result_data, indent=2, ensure_ascii=False, default=str)
        if len(json_result_str) > MAX_AST_RESULT_LEN:
            logger.warning(f"AST eredmény túl hosszú ({len(json_result_str)}), csonkolva.")
            return json_result_str[:MAX_AST_RESULT_LEN] + "\n... [EREDMÉNY CSONKOLVA] ..."
        return json_result_str

    except json.JSONDecodeError:
        return "Hiba: Az eszköz ('query_ast_data') bemenete nem érvényes JSON."
    except Exception as e:
        logger.error(f"Hiba a 'query_ast_data' eszközben: {e}", exc_info=True)
        return f"Hiba a 'query_ast_data' eszköz futása közben: {str(e)}"