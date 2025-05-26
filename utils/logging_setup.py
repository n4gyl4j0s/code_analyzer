# utils/logging_setup.py
import logging

# A loggerek nevének definiálása, hogy más modulok is hivatkozhassanak rájuk.
# Bár a getLogger bárhol hívható stringgel, ez a megoldás a konzisztenciát segíti.
MAIN_LOGGER_NAME = "projekt_elemzo_v2.3"
FIXER_LOGGER_NAME = "llm_output_fixer"
XML_FIXER_LOGGER_NAME = "llm_xml_output_fixer"
TOOLS_LOGGER_NAME = "v2_tools"

def configure_logging(debug_mode: bool):
    """
    Beállítja az alkalmazás naplózási szintjeit és formátumát.

    Args:
        debug_mode (bool): Ha True, részletesebb (DEBUG) naplózást kapcsol be
                           a saját modulokhoz.
    """
    # Alapvető logging konfiguráció beállítása
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Loggerek példányosítása
    main_logger = logging.getLogger(MAIN_LOGGER_NAME)
    fixer_logger = logging.getLogger(FIXER_LOGGER_NAME)
    xml_fixer_logger = logging.getLogger(XML_FIXER_LOGGER_NAME)
    tools_logger = logging.getLogger(TOOLS_LOGGER_NAME)
    
    # Külső könyvtárak loggereinek lekérése a zaj csökkentéséhez
    langchain_logger = logging.getLogger("langchain")
    langchain_core_logger = logging.getLogger("langchain_core")
    langchain_openai_logger = logging.getLogger("langchain_openai")
    httpx_logger = logging.getLogger("httpx")
    httpcore_logger = logging.getLogger("httpcore")
    openai_logger = logging.getLogger("openai")

    if debug_mode:
        # Részletesebb naplózás bekapcsolása a saját modulokra
        main_logger.setLevel(logging.DEBUG)
        fixer_logger.setLevel(logging.DEBUG)
        xml_fixer_logger.setLevel(logging.DEBUG)
        tools_logger.setLevel(logging.DEBUG)

        # LangChain komponensek INFO szinten tartása, hogy ne legyen túl zajos
        langchain_logger.setLevel(logging.INFO)
        langchain_core_logger.setLevel(logging.INFO)
        langchain_openai_logger.setLevel(logging.INFO)

        # HTTP és egyéb külső libraryk zajának csökkentése
        httpx_logger.setLevel(logging.WARNING)
        httpcore_logger.setLevel(logging.WARNING)
        openai_logger.setLevel(logging.WARNING)
        
        main_logger.info("Debug mód aktiválva, részletes naplózás bekapcsolva.")
    else:
        # Alapértelmezett (nem debug) esetben a saját loggereket is INFO-ra állítjuk
        main_logger.setLevel(logging.INFO)
        fixer_logger.setLevel(logging.INFO)
        xml_fixer_logger.setLevel(logging.INFO)
        tools_logger.setLevel(logging.INFO)
        
        # A külső könyvtárak alapértelmezetten INFO szinten maradnak a basicConfig miatt,
        # de itt expliciten is beállíthatjuk őket, ha szükséges.
        # Pl. httpx zajának csökkentése alap módban is hasznos lehet.
        httpx_logger.setLevel(logging.WARNING)
        httpcore_logger.setLevel(logging.WARNING)
        openai_logger.setLevel(logging.WARNING)