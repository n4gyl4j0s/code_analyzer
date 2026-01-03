# core/agent.py
import logging
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


# LangChain importok
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.agents import AgentAction, AgentFinish

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

# Most már a projekt gyökeréből importáljuk ezeket,
# miután a main.py beállította a sys.path-ot.
try:
    import ctags_parser #
    HAS_CTAGS_PARSER = True
    logger.info("ctags_parser.py sikeresen importálva.")
except ImportError:
    HAS_CTAGS_PARSER = False
    logger.warning("ctags_parser.py nem található a projekt gyökerében, a ctags-specifikus funkciók nem lesznek elérhetők.")

try:
    import ast_parser #
    HAS_AST_PARSER = True
    logger.info("ast_parser.py sikeresen importálva.")
except ImportError:
    HAS_AST_PARSER = False
    logger.warning("ast_parser.py nem található a projekt gyökerében, az AST-specifikus funkciók nem lesznek elérhetők.")


def initialize_and_run_agent(
    project_root_abs_str: str,
    user_prompt_str: str,
    v1_context_file_abs_str: Optional[str],
    ctags_file_abs_str: Optional[str],
    ast_file_abs_str: Optional[str]
):
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

    # Ctags adatok betöltése és parsolása, HA a ctags_parser importálható volt
    if HAS_CTAGS_PARSER and ctags_file_abs_str and Path(ctags_file_abs_str).is_file():
        logger.info(f"Ctags fájl feldolgozása indul: {ctags_file_abs_str}")
        try:
            loaded_ctags_data = ctags_parser.parse_ctags_file(ctags_file_abs_str) #
            if loaded_ctags_data:
                logger.info(f"Ctags adatok sikeresen betöltve és parsolva ({len(loaded_ctags_data)} fájlhoz).")
            else:
                logger.info(f"A ctags parsolás nem adott vissza adatot a '{ctags_file_abs_str}' fájlból.")
        except Exception as e:
            logger.error(f"Hiba a ctags fájl feldolgozása közben ({ctags_file_abs_str}): {e}", exc_info=True)
    elif ctags_file_abs_str:
        logger.warning(f"Megadott ctags adatfájl nem található ({ctags_file_abs_str}) vagy a ctags_parser nem érhető el.")

    # AST adatok betöltése és parsolása, HA az ast_parser importálható volt
    if HAS_AST_PARSER and ast_file_abs_str and Path(ast_file_abs_str).is_file():
        logger.info(f"AST JSONL fájl feldolgozása indul: {ast_file_abs_str}")
        try:
            loaded_ast_data = ast_parser.parse_ast_jsonl_file(ast_file_abs_str) #
            if loaded_ast_data:
                logger.info(f"AST adatok sikeresen betöltve és parsolva ({len(loaded_ast_data)} fájlhoz).")
            else:
                logger.info(f"Az AST parsolás nem adott vissza adatot a '{ast_file_abs_str}' fájlból.")
        except Exception as e:
            logger.error(f"Hiba az AST fájl feldolgozása közben ({ast_file_abs_str}): {e}", exc_info=True)
    elif ast_file_abs_str:
        logger.warning(f"Megadott AST adatfájl nem található ({ast_file_abs_str}) vagy az ast_parser nem érhető el.")

    # Eszközök inicializálása a PARSOLT adatokkal
    initialize_tool_data(
        project_root=project_root_abs_str,
        ctags_data=loaded_ctags_data,       # Itt már a parsolt adatokat adjuk át
        ast_data=loaded_ast_data,         # Itt már a parsolt adatokat adjuk át
        narrative_context=loaded_narrative_context
    )

    final_active_tools_list, final_strategic_guidance = get_all_tools()
    
    try:
        selected_api_url = settings.API_URLS.get(settings.SERVER_MODE)
        if not selected_api_url:
            raise KeyError(f"SERVER_MODE '{settings.SERVER_MODE}' nem található az API_URLS-ben.")
        logger.info(f"Kapcsolódás az LLM-hez: {selected_api_url}")

        thoughts_log_file_abs_path = Path.cwd() / settings.THOUGHTS_LOG_FILE_NAME
        direct_log_path = Path.cwd() / settings.DIRECT_LLM_INTERACTIONS_LOG_FILE_NAME

        for log_path in [thoughts_log_file_abs_path, direct_log_path]:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"Log inicializálva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}\n")
        
        file_logger_callback = LLMInteractionLogger()
        
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

    # === AGENT ÉS PROMPT LÉTREHOZÁSA (EZ A RÉSZ VÁLTOZATLAN) ===
    try:
        current_prompt_obj = create_prompt_template(final_active_tools_list, final_strategic_guidance)
        agent = create_react_agent(llm_to_use, final_active_tools_list, current_prompt_obj)
    except Exception as e_agent:
        logger.critical(f"Hiba az agent létrehozása közben: {e_agent}", exc_info=True)
        return

    # ==========================================================================================
    # === EGYSZERŰSÍTETT VEZÉRLÉSI CIKLUS (UNIVERZÁLIS, MÉRET ALAPÚ CSONKOLÁSSAL) ===
    # ==========================================================================================

    tool_map = {tool.name: tool for tool in final_active_tools_list}
    intermediate_steps = []
    max_iterations = 25

    logger.info(f"Agent inicializálva, egyedi futtatási ciklus indul. Elérhető eszközök: {[tool.name for tool in final_active_tools_list]}")
    print(f"\n--- Kérdés az Agentnek a '{project_root_abs_str}' projektről ---")
    print(f"Kérdés: {user_prompt_str}")

    for i in range(max_iterations):
        try:
            output = agent.invoke({
                "input": user_prompt_str,
                "intermediate_steps": intermediate_steps
            })

            if isinstance(output, AgentFinish):
                final_answer = output.return_values.get("output", "Nem érkezett strukturált kimenet.")
                print("\n--- Agent Végső Válasza ---")
                print("--- AGENT_FINAL_ANSWER_START ---")
                print(final_answer)
                print("--- AGENT_FINAL_ANSWER_END ---")
                break

            if isinstance(output, AgentAction):
                if output.log:
                    print(f"\n🤔 Gondolat: {output.log.strip()}")
                
                tool_name = output.tool
                tool_input = output.tool_input
                print(f"🛠️ Eszköz hívás: {tool_name} | Bemenet: {tool_input}")
                
                observation = ""
                try:
                    if tool_name in tool_map:
                        tool_to_use = tool_map[tool_name]
                        observation = tool_to_use.invoke(tool_input)
                    else:
                        observation = f"HIBA: Nincs ilyen eszköz: '{tool_name}'"
                
                except json.JSONDecodeError:
                    observation = (
                        f"HIBA: Az eszköz '{tool_name}' bemenete nem érvényes JSON formátum. "
                        f"A hibás bemenet, amit küldtél: ```{tool_input}```\n"
                        "💡 JAVASLAT: Győződj meg róla, hogy a bemenet egy valid JSON string, ami egy objektumot ír le."
                    )
                except Exception as tool_error:
                    observation = f"HIBA az eszköz '{tool_name}' futtatása közben: {tool_error}"

                # *** EGYSZERŰSÍTETT, UNIVERZÁLIS KIMENET CSONKOLÁSA ***
                original_size = len(str(observation))
                # Csak akkor csonkolunk, ha a kimenet nagy ÉS nem tűnik hibaüzenetnek.
                if original_size > 1500 and "HIBA:" not in observation and "❌" not in observation:
                    observation = (
                        f"## Az eszköz ({tool_name}) kimenete túl hosszú (méret: {original_size} karakter), "
                        f"ezért a prompt röviden tartása érdekében csonkolva lett. A parancs sikeresen lefutott. ##"
                    )

                intermediate_steps.append((output, str(observation)))

        except Exception as e:
            logger.error(f"Kritikus hiba az agent futtatása közben a(z) {i+1}. lépésben: {e}", exc_info=True)
            print(f"\nKritikus hiba történt az agent futtatása közben: {e}")
            break
    else:
        print("\n--- Az Agent elérte a maximális iterációs limitet anélkül, hogy befejezte volna a munkát. ---")