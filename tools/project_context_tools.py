# tools/project_context_tools.py
import logging
from typing import Optional

# Belső importok
from utils.output_parser import clean_llm_action_input

# Logger példányosítása
logger = logging.getLogger(__name__)

# Megjegyzés: Ez a modul a 'tools' csomag globális változóitól függ,
# amelyeket a tools/__init__.py-ban lévő `initialize_tool_data` állít be.
_narrative_context_global: Optional[str] = None


def tool_wrapper_get_v1_summary(action_input_str: str) -> str:
    """
    LangChain Eszköz: Visszaadja a projekt V1 analízise során generált
    általános, szöveges összefoglalóját (narratív kontextus).
    JSON input: {} (nem vár argumentumot).
    """
    logger.info(f"Eszköz HÍVVA: get_project_summary_v1, input: {action_input_str}")
    
    # Bár az eszköz nem használja az inputot, a tisztítás és a logolás
    # a konzisztencia és a hibakeresés miatt hasznos.
    cleaned_input = clean_llm_action_input(action_input_str).strip()
    if cleaned_input and cleaned_input != "{}":
        logger.warning(
            f"A 'get_project_summary_v1' eszköz nem várt argumentumot, de kapott: '{cleaned_input}'"
        )

    if (
        _narrative_context_global
        and not _narrative_context_global.startswith("Nincs elérhető")
        and not _narrative_context_global.startswith("Figyelem:")
        and not _narrative_context_global.startswith("Hiba:")
    ):
        logger.info("V1 narratív kontextus sikeresen visszaadva.")
        # Itt is lehetne csonkolni, ha a kontextus extrém hosszú lenne,
        # de feltételezzük, hogy már egy összefoglalt szöveg.
        return _narrative_context_global
    else:
        logger.info("V1 narratív kontextus nem áll rendelkezésre.")
        return "Projekt összefoglaló (V1 analízis alapján) nem áll rendelkezésre."