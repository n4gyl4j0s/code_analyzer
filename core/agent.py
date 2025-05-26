# core/agent.py
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


# LangChain importok
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage

# Belső importok a projekt struktúrából
from config import settings
from core.llm_wrapper import LLMWithOutputFixer
from utils.callbacks import LLMInteractionLogger, ConsoleToolCallbackHandler
from prompts.react_template import create_prompt_template
from tools import initialize_tool_data, get_all_tools
from utils.logging_setup import MAIN_LOGGER_NAME
from utils.output_parser import llm_output_xml_parser_and_fixer



# Logger példányosítása
logger = logging.getLogger(MAIN_LOGGER_NAME)

# A külső, opcionális parserek importálása, ahogy az eredeti szkriptben volt
try:
    import ctags_parser
    HAS_CTAGS_PARSER = True
except ImportError:
    HAS_CTAGS_PARSER = False
    logging.warning("ctags_parser.py nem található, a ctags-specifikus funkciók nem lesznek elérhetők.")

try:
    import ast_parser
    HAS_AST_PARSER = True
except ImportError:
    HAS_AST_PARSER = False
    logging.warning("ast_parser.py nem található, az AST-specifikus funkciók nem lesznek elérhetők.")


def initialize_and_run_agent(
    project_root_abs_str: str,
    user_prompt_str: str,
    v1_context_file_abs_str: Optional[str],
    ctags_file_abs_str: Optional[str],
    ast_file_abs_str: Optional[str]
):
    """
    Ez a központi függvény, amely inicializálja és futtatja az ügynököt.
    """
    # 1. Adatok betöltése
    loaded_ctags_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
    loaded_ast_data: Optional[Dict[str, Dict[str, Any]]] = None
    loaded_narrative_context: Optional[str] = "Nincs elérhető projekt összefoglaló (V1 kontextus)."

    if v1_context_file_abs_str and Path(v1_context_file_abs_str).is_file():
        try:
            with open(v1_context_file_abs_str, "r", encoding="utf-8") as f:
                loaded_narrative_context = f.read().strip() or "A V1 kontextus fájl üres."
            logger.info(f"Narratív kontextus (V1) sikeresen betöltve.")
        except Exception as e:
            logger.error(f"Hiba a narratív kontextus betöltése közben: {e}")
            loaded_narrative_context = "Hiba történt a V1 kontextus fájl olvasása közben."

    if HAS_CTAGS_PARSER and ctags_file_abs_str and Path(ctags_file_abs_str).is_file():
        logger.info(f"Ctags fájl feldolgozása: {ctags_file_abs_str}")
        loaded_ctags_data = ctags_parser.parse_ctags_file(ctags_file_abs_str)
        if loaded_ctags_data: logger.info("Ctags adatok sikeresen betöltve.")

    if HAS_AST_PARSER and ast_file_abs_str and Path(ast_file_abs_str).is_file():
        logger.info(f"AST JSONL fájl feldolgozása: {ast_file_abs_str}")
        loaded_ast_data = ast_parser.parse_ast_jsonl_file(ast_file_abs_str)
        if loaded_ast_data: logger.info("AST adatok sikeresen betöltve.")

    # 2. Eszközök inicializálása
    initialize_tool_data(
        project_root=project_root_abs_str,
        ctags_data=loaded_ctags_data,
        ast_data=loaded_ast_data,
        narrative_context=loaded_narrative_context
    )

    # Elérhető eszközök és a stratégiai útmutató lekérése
    final_active_tools_list, final_strategic_guidance = get_all_tools()
    
    # 3. LLM és wrappereinek beállítása
    try:
        selected_api_url = settings.API_URLS.get(settings.SERVER_MODE)
        if not selected_api_url:
            raise KeyError(f"SERVER_MODE '{settings.SERVER_MODE}' nem található az API_URLS-ben.")
        logger.info(f"Kapcsolódás az LLM-hez: {selected_api_url}")

        thoughts_log_file_abs_path = Path.cwd() / settings.THOUGHTS_LOG_FILE_NAME
        direct_log_path = Path.cwd() / settings.DIRECT_LLM_INTERACTIONS_LOG_FILE_NAME

        # Log fájlok inicializálása (törlés és fejléc írás)
        for log_path in [thoughts_log_file_abs_path, direct_log_path]:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"Log inicializálva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}\n")
        
        file_logger_callback = LLMInteractionLogger()
        console_tool_callback = ConsoleToolCallbackHandler()
        
        base_llm_instance = ChatOpenAI(
            openai_api_base=selected_api_url,
            openai_api_key=settings.API_KEY,
            model_name=settings.MODEL_NAME,
            temperature=0.1,
            request_timeout=400,
            streaming=False,
            callbacks=[file_logger_callback]
        )
        
        llm_to_use = LLMWithOutputFixer(
            base_llm=base_llm_instance, 
            xml_parser_fixer_function=llm_output_xml_parser_and_fixer,
            thoughts_log_path=thoughts_log_file_abs_path,
            direct_interaction_log_filepath=direct_log_path
        )
        logger.info("LLM becsomagolva a kimenetjavító függvénnyel.")

    except Exception as e:
        logger.critical(f"Hiba az LLM inicializálása közben: {e}. Kilépés.", exc_info=True)
        return

    # 4. Fallback logika, ha nincsenek eszközök
    if not final_active_tools_list:
        logger.error("Nincsenek elérhető eszközök. Egyszerű LLM válaszadás következik.")
        try:
            fallback_prompt = [
                SystemMessage(content="Válaszolj a felhasználó kérdésére a megadott kontextus alapján."),
                HumanMessage(content=f"Kontextus:\n{loaded_narrative_context}\n\nKérdés: {user_prompt_str}")
            ]
            response = llm_to_use.invoke(fallback_prompt)
            print("\n--- LLM Válasz (eszközök nélkül) ---")
            print(response.content if hasattr(response, 'content') else str(response))
        except Exception as e_fallback:
            print(f"Hiba az alap LLM hívás közben: {e_fallback}")
        return

    # 5. Prompt és Agent létrehozása
    try:
        current_prompt_obj = create_prompt_template(final_active_tools_list, final_strategic_guidance)
        agent = create_react_agent(llm_to_use, final_active_tools_list, current_prompt_obj)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=final_active_tools_list,
            verbose=False, # A ConsoleToolCallbackHandler kezeli a kimenetet
            max_iterations=25,
            handle_parsing_errors=(
                "FORMÁTUM HIBA: A korábbi kimeneted nem volt a várt formátumban. "
                "Szigorúan kövesd a megadott XML formátumot. A hibás kimenet ezzel kezdődött: "
            ),
            callbacks=[console_tool_callback]
        )
    except Exception as e_agent:
        logger.critical(f"Hiba az agent létrehozása közben: {e_agent}", exc_info=True)
        return

    # 6. Agent futtatása
    logger.info(f"Agent inicializálva. Elérhető eszközök: {[tool.name for tool in final_active_tools_list]}")
    print(f"\n--- Kérdés az Agentnek a '{project_root_abs_str}' projektről ---")
    print(f"Kérdés: {user_prompt_str}")
    
    try:
        response = agent_executor.invoke({"input": user_prompt_str})
        print("\n--- Agent Végső Válasza ---")
        print("--- AGENT_FINAL_ANSWER_START ---")
        print(response.get('output', "Nem érkezett strukturált kimenet az agenttől."))
        print("--- AGENT_FINAL_ANSWER_END ---")
    except Exception as e:
        logger.error(f"Kritikus hiba az agent futtatása közben: {e}", exc_info=True)
        print(f"\nKritikus hiba történt az agent futtatása közben: {e}")