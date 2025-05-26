# ast_parser.py

import json
import logging
import gzip
from pathlib import Path
from typing import Dict, Any, Union, TextIO

logger = logging.getLogger(__name__)

def _get_file_opener(file_path: Path) -> Union[TextIO, gzip.GzipFile]:
    """
    Helper function to open a .jsonl or .jsonl.gz file for reading in text mode.
    """
    if file_path.name.endswith(".gz"):
        return gzip.open(file_path, 'rt', encoding='utf-8')
    else:
        return open(file_path, 'r', encoding='utf-8')

def parse_ast_jsonl_file(ast_jsonl_file_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Parses an AST data file in JSONL format (one JSON object per line,
    where each object represents AST-like data for a single source file).

    Each line is expected to be a JSON object with at least "file" and "data" keys.
    Example line: {"file": "path/to/file.java", "data": { ... AST details ... }}

    Args:
        ast_jsonl_file_path: The path to the .jsonl or .jsonl.gz file.

    Returns:
        A dictionary where:
            - Keys are file paths (from the "file" field in each JSON line).
            - Values are the corresponding "data" objects (dictionaries)
              containing the AST-like information for that file.
        Returns an empty dictionary if the file is not found or an error occurs.
    """
    p_ast_file = Path(ast_jsonl_file_path)
    if not p_ast_file.is_file():
        logger.error(f"AST JSONL file not found: {ast_jsonl_file_path}")
        return {}

    ast_data_by_file: Dict[str, Dict[str, Any]] = {}
    line_number = 0
    try:
        with _get_file_opener(p_ast_file) as f:
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue # Skip empty lines

                try:
                    json_obj = json.loads(line)
                    
                    if not isinstance(json_obj, dict):
                        logger.warning(f"Line {line_number} in '{p_ast_file.name}' is not a JSON object, skipping: {line[:100]}...")
                        continue

                    file_key = json_obj.get("file")
                    data_value = json_obj.get("data")

                    if file_key is None or data_value is None:
                        logger.warning(
                            f"Line {line_number} in '{p_ast_file.name}' is missing 'file' or 'data' key, skipping. "
                            f"Keys found: {list(json_obj.keys())}"
                        )
                        continue
                    
                    if not isinstance(file_key, str):
                        logger.warning(
                            f"Line {line_number} in '{p_ast_file.name}': 'file' key is not a string, skipping. Value: {file_key}"
                        )
                        continue
                    
                    if not isinstance(data_value, dict):
                        logger.warning(
                            f"Line {line_number} in '{p_ast_file.name}' for file '{file_key}': "
                            f"'data' key is not a dictionary, skipping. Type: {type(data_value)}"
                        )
                        continue

                    if file_key in ast_data_by_file:
                        logger.warning(
                            f"Duplicate file key '{file_key}' found at line {line_number} in '{p_ast_file.name}'. "
                            f"Overwriting previous entry."
                        )
                    
                    ast_data_by_file[file_key] = data_value

                except json.JSONDecodeError as jde:
                    logger.warning(f"JSON decode error at line {line_number} in '{p_ast_file.name}': {jde}. Line: '{line[:100]}...'")
                except Exception as e_inner: # Catch other potential errors during processing a line
                    logger.error(f"Error processing line {line_number} in '{p_ast_file.name}': {e_inner}. Line: '{line[:100]}...'")
        
        if ast_data_by_file:
            logger.info(f"Successfully parsed AST data for {len(ast_data_by_file)} files from '{ast_jsonl_file_path}'.")
        else:
            logger.info(f"No valid AST data entries found or parsed from '{ast_jsonl_file_path}'.")
            
    except FileNotFoundError: # Should be caught by the initial check, but good to have
        logger.error(f"AST JSONL file not found (should not happen here): {ast_jsonl_file_path}")
        return {}
    except gzip.BadGzipFile:
        logger.error(f"Bad GZIP file: {ast_jsonl_file_path}. The file may be corrupted or not a valid gzip archive.")
        return {}
    except Exception as e:
        logger.error(f"An unexpected error occurred while parsing AST JSONL file {ast_jsonl_file_path}: {e}", exc_info=True)
        return {}
        
    return ast_data_by_file

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Létrehozunk egy dummy .jsonl fájlt a teszteléshez
    dummy_jsonl_content = [
        {"file": "src/com/example/App.java", "data": {"classes": [{"name": "App", "methods": [{"name": "main"}]}], "controllers": []}},
        {"file": "src/com/example/Util.java", "data": {"classes": [{"name": "Util", "fields": [{"name": "MAX_COUNT"}]}], "records": [{"name": "Point"}]}},
        {"file": "src/com/example/Controller.java", "data": {"controllers": [{"name": "MyController", "endpoints": ["/api/data"]}]}},
        "This is not a valid JSON line.", # Hibás sor tesztelése
        {"file": "src/com/example/NoData.java"}, # Hiányzó "data" kulcs tesztelése
        {"nofile_key": "some_value", "data": {"info": "test"}}, # Hiányzó "file" kulcs
        {"file": "src/com/example/App.java", "data": {"classes": [{"name": "AppUpdated", "methods": []}]}}, # Duplikált fájlkulcs
    ]
    test_jsonl_file = "dummy_ast_index.jsonl"
    with open(test_jsonl_file, "w", encoding="utf-8") as f:
        for entry in dummy_jsonl_content:
            if isinstance(entry, dict):
                f.write(json.dumps(entry) + "\n")
            else:
                f.write(entry + "\n") # Hibás sor írása

    logger.info(f"Attempting to parse dummy AST JSONL file: {test_jsonl_file}")
    parsed_ast_data = parse_ast_jsonl_file(test_jsonl_file)

    if parsed_ast_data:
        logger.info("AST JSONL parsing successful. Parsed data overview:")
        logger.info(f"Total files parsed: {len(parsed_ast_data)}")
        for file_p, data_obj in list(parsed_ast_data.items())[:3]: # Első 3 elem mintája
            logger.debug(f"  File: {file_p}")
            logger.debug(f"    Data keys: {list(data_obj.keys())}")
            if "classes" in data_obj and data_obj["classes"]:
                logger.debug(f"    First class name (if any): {data_obj['classes'][0].get('name', 'N/A')}")
        
        # Ellenőrizzük a duplikált fájl felülírását
        if "src/com/example/App.java" in parsed_ast_data:
            app_data = parsed_ast_data["src/com/example/App.java"]
            if app_data["classes"][0]["name"] == "AppUpdated":
                logger.info("Test for duplicate file key override: PASSED (last entry for 'src/com/example/App.java' was used).")
            else:
                logger.error("Test for duplicate file key override: FAILED.")
    else:
        logger.error("AST JSONL parsing failed or no data returned.")

    # Tömörített fájl tesztelése (opcionális, ha van .gz fájlod)
    dummy_gz_file = "dummy_ast_index.jsonl.gz"
    try:
        with gzip.open(dummy_gz_file, "wt", encoding="utf-8") as f_gz: # 'wt' a text módhoz
             for entry in dummy_jsonl_content[:3]: # Csak az első pár érvényes sort tegyük bele
                if isinstance(entry, dict) and "file" in entry and "data" in entry:
                    f_gz.write(json.dumps(entry) + "\n")
        
        logger.info(f"Attempting to parse dummy GZIPPED AST JSONL file: {dummy_gz_file}")
        parsed_gz_data = parse_ast_jsonl_file(dummy_gz_file)
        if parsed_gz_data:
            logger.info(f"GZIPPED AST JSONL parsing successful. Total files parsed: {len(parsed_gz_data)}")
        else:
            logger.error("GZIPPED AST JSONL parsing failed.")
    except Exception as e_gz_test:
        logger.error(f"Error during GZIP test setup or parsing: {e_gz_test}")


    # Clean up dummy files (optional)
    # import os
    # os.remove(test_jsonl_file)
    # if Path(dummy_gz_file).exists():
    #    os.remove(dummy_gz_file)