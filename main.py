# main.py
import argparse
import logging
from pathlib import Path

# A .env fájl betöltése a legelső lépés kell, hogy legyen
from dotenv import load_dotenv
load_dotenv()
import os
import sys
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Belső importok a projekt struktúrából
from utils.logging_setup import configure_logging, MAIN_LOGGER_NAME
from core.agent import initialize_and_run_agent

# A fő logger példányosítása, miután a configure_logging lefutott
logger = logging.getLogger(MAIN_LOGGER_NAME)


def main_cli():
    """
    Parancssori interfész (CLI) beállítása és futtatása.
    """
    parser = argparse.ArgumentParser(
        description="Projekt Elemző V2.3 - LLM-vezérelt lekérdező (Refaktorált)"
    )
    parser.add_argument("--project-root", required=True, help="A vizsgálandó projekt gyökérkönyvtára.")
    parser.add_argument("--prompt", required=True, help="A kérdés, amit fel szeretnél tenni a projekttel kapcsolatban.")
    parser.add_argument("--v1-context-file", default=None, help="Opcionális: A V1 elemző által generált kontextusfájl.")
    parser.add_argument("--ctags-file", default=None, help="Opcionális: A ctags fájl (pl. .analyzer_tags) útvonala.")
    parser.add_argument("--ast-file", default=None, help="Opcionális: Az AST JSONL fájl (pl. ast_input.jsonl) útvonala.")
    parser.add_argument("--debug", action="store_true", help="Részletesebb naplózás bekapcsolása.")
    
    args = parser.parse_args()

    # A naplózás beállítása az argumentumok alapján
    configure_logging(args.debug)

    # Abszolút útvonalak létrehozása és alapértelmezett fájlok keresése
    project_root_abs = str(Path(args.project_root).resolve())
    v1_context_abs = str(Path(args.v1_context_file).resolve()) if args.v1_context_file else None
    ctags_file_abs = str(Path(args.ctags_file).resolve()) if args.ctags_file else None
    ast_file_abs = str(Path(args.ast_file).resolve()) if args.ast_file else None

    # Alapértelmezett ctags fájl keresése, ha nincs megadva
    if not ctags_file_abs and project_root_abs:
        ctags_default_path = Path(project_root_abs) / ".analyzer_tags"
        if ctags_default_path.is_file():
            ctags_file_abs = str(ctags_default_path)
            logger.info(f"Alapértelmezett ctags fájl használata: {ctags_file_abs}")

    # Alapértelmezett AST fájl keresése, ha nincs megadva (tömörítettet is)
    if not ast_file_abs and project_root_abs:
        ast_default_path = Path(project_root_abs) / "ast_input.jsonl"
        ast_default_path_gz = Path(project_root_abs) / "ast_input.jsonl.gz"
        if ast_default_path.is_file():
            ast_file_abs = str(ast_default_path)
            logger.info(f"Alapértelmezett AST fájl használata: {ast_file_abs}")
        elif ast_default_path_gz.is_file():
            ast_file_abs = str(ast_default_path_gz)
            logger.info(f"Alapértelmezett tömörített AST fájl használata: {ast_file_abs}")

    # Az agent indítása a feldolgozott argumentumokkal
    initialize_and_run_agent(
        project_root_abs_str=project_root_abs,
        user_prompt_str=args.prompt,
        v1_context_file_abs_str=v1_context_abs,
        ctags_file_abs_str=ctags_file_abs,
        ast_file_abs_str=ast_file_abs,
    )

if __name__ == "__main__":
    main_cli()