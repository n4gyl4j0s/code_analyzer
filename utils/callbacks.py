# utils/callbacks.py
import logging
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

# LangChain és Core importok
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.agents import AgentAction, AgentFinish

# Konfiguráció importálása
from config.settings import LLM_INTERACTION_LOG_FILE

# Logger példányosítása a modulhoz
logger = logging.getLogger(__name__)


def extract_and_save_thought(full_llm_output: str, thoughts_log_filepath: Path):
    """
    Kinyeri a 'Thought:' részt az LLM kimenetéből és elmenti a megadott fájlba.
    """
    try:
        # Reguláris kifejezés a "Thought:" és az azt követő tartalom kinyerésére.
        # A (?i) a case-insensitive illeszkedést biztosítja a "Thought:"-ra.
        # A (.*?) a lehető legkevesebb karaktert illeszti (non-greedy).
        # A (?=\n\s*(?:Action:|Final Answer:|$)) egy pozitív előretekintés, ami biztosítja,
        # hogy a gondolat a következő Action:, Final Answer: vagy a string vége előttig tartson.
        match = re.search(r"^\s*Thought:(.*?)(?=\n\s*(?:Action:|Final Answer:|$))", full_llm_output, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        
        if match:
            thought_to_save = match.group(1).strip()

            if thought_to_save: # Csak akkor mentsünk, ha van érdemi tartalom
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                log_entry = f"[{timestamp}] Thought:\n{thought_to_save}\n{'-'*70}\n"
                try:
                    # Győződj meg róla, hogy a log fájl könyvtára létezik
                    thoughts_log_filepath.parent.mkdir(parents=True, exist_ok=True)
                    with open(thoughts_log_filepath, "a", encoding="utf-8") as f:
                        f.write(log_entry)
                        f.flush() # Biztosítjuk az azonnali írást
                    logger.info(f"Thought sikeresen mentve a '{thoughts_log_filepath}' fájlba.")
                except Exception as e:
                    logger.error(f"HIBA a thought mentése közben a '{thoughts_log_filepath}' fájlba: {e}")
            # else:
            #     logger.debug("Nem található érdemi Thought tartalom a mentéshez az adott LLM kimenetben (a regex illeszkedés után üres volt).")
        # else:
        #     logger.debug("Nem található 'Thought:' prefix és tartalom (a megadott mintával) az LLM kimenetben a mentéshez.")
            
    except Exception as e:
        logger.error(f"Hiba a Thought kinyerése vagy mentése közben: {e}", exc_info=True)


class LLMInteractionLogger(BaseCallbackHandler):
    """Logolja az LLM interakciókat egy fájlba, MOST DEBUG ÜZENETEKKEL."""
    def __init__(self, log_file: str = LLM_INTERACTION_LOG_FILE):
        print(f"DEBUG KÉPERNYŐRE: LLMInteractionLogger __init__ meghívva. Log fájl: {log_file}") # Képernyőre ír
        self.log_file = log_file
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"\n\nLOGGER INITIALIZED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}\n")
            print(f"DEBUG KÉPERNYŐRE: Log fájl ({self.log_file}) sikeresen inicializálva __init__-ben.")
        except Exception as e:
            print(f"DEBUG KÉPERNYŐRE: HIBA a log fájl ({self.log_file}) inicializálásakor __init__-ben: {e}")

    def _log(self, message: str):
        # print(f"DEBUG KÉPERNYŐRE: LLMInteractionLogger._log meghívva, üzenet eleje: {message[:70]}...") # Ez túl zajos lehet
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception as e:
            print(f"DEBUG KÉPERNYŐRE: HIBA az LLMInteractionLogger._log metódusban a fájlba írás közben ({self.log_file}): {e}")

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> Any:
        print("DEBUG KÉPERNYŐRE: LLMInteractionLogger -> on_llm_start MEGHÍVVA!") # Képernyőre ír
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"\n{'='*20} LLM Kérés (V2.3) ({timestamp}) {'='*20}\n"
        for i, prompt_text in enumerate(prompts):
            log_entry += f"-- Prompt {i+1} --\n{prompt_text}\n----\n"
        log_entry += f"{'='*55}\n"
        self._log(log_entry)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        print("DEBUG KÉPERNYŐRE: LLMInteractionLogger -> on_llm_end MEGHÍVVA!") # Képernyőre ír
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"\n{'~'*20} LLM Válasz (V2.3) ({timestamp}) {'~'*20}\n"
        
        if response.generations and response.generations[0]:
             generation_instance = response.generations[0][0]
             raw_text = ""
             if hasattr(generation_instance, 'text'):
                 raw_text = generation_instance.text
             elif hasattr(generation_instance, 'message') and hasattr(generation_instance.message, 'content'):
                 raw_text = generation_instance.message.content
             else:
                 raw_text = str(generation_instance)
             log_entry += f"-- Nyers Válasz --\n{raw_text}\n----\n"
        
        log_entry += "-- Metaadatok --\n" 
        if response.llm_output:
            try:
                log_entry += f"{json.dumps(response.llm_output, indent=2, ensure_ascii=False)}\n"
                token_usage = response.llm_output.get('token_usage', {})
                if token_usage:
                    prompt_tokens = token_usage.get('prompt_tokens', 'N/A')
                    completion_tokens = token_usage.get('completion_tokens', 'N/A')
                    total_tokens = token_usage.get('total_tokens', 'N/A')
                    log_entry += (f"Kinyert token adatok: Prompt={prompt_tokens}, Válasz={completion_tokens}, Összesen={total_tokens}\n")
            except Exception as e_json:
                log_entry += f"HIBA a metaadatok feldolgozása közben: {e_json}\nNyers metaadatok: {str(response.llm_output)}\n"
        else:
            log_entry += "Figyelmeztetés: Az 'llm_output' mező nem volt elérhető vagy üres volt a válaszban.\n"
        
        log_entry += "----\n"
        log_entry += f"{'~'*60}\n"
        self._log(log_entry)

    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> Any:
        print(f"DEBUG KÉPERNYŐRE: LLMInteractionLogger -> on_llm_error MEGHÍVVA! Hiba: {error}") # Képernyőre ír
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"\n{'!'*20} LLM Hiba (V2.3) ({timestamp}) {'!'*20}\n"
        log_entry += f"{type(error).__name__}: {error}\n{'!'*49}\n"
        self._log(log_entry)
        logging.error(f"LLM Hiba naplózva (V2.3): {error}", exc_info=True) # A fő loggerbe is írunk


class ConsoleToolCallbackHandler(BaseCallbackHandler):
    """Egyedi Callback Handler, ami a konzolra írja az agent eszközhívásait és eredményeit."""
    def on_agent_action(self, action: AgentAction, color: Optional[str] = None, **kwargs: Any) -> Any:
        tool_input_str = str(action.tool_input)
        if isinstance(action.tool_input, dict):
            tool_input_str = json.dumps(action.tool_input, ensure_ascii=False, indent=2)
        elif isinstance(action.tool_input, str) and action.tool_input.startswith("{"): # Próbáljuk JSON-ként formázni, ha annak tűnik
            try:
                parsed_json = json.loads(action.tool_input)
                tool_input_str = json.dumps(parsed_json, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass # Marad string, ha nem valid JSON

        max_input_len = 200
        truncated_input = tool_input_str[:max_input_len] + "..." if len(tool_input_str) > max_input_len else tool_input_str
        print(f"\n🔎 AGENT ACTION:\n   Eszköz: {action.tool}\n   Bemenet:\n{truncated_input}")

    def on_tool_end(self, output: str, name: str, color: Optional[str] = None, **kwargs: Any) -> Any:
        print(f"\n💡 ESZKÖZ EREDMÉNYE ({name}):")
        max_len = 300
        # Egyszerűsítjük a kimenet megjelenítését: újsorok cseréje, majd rövidítés
        display_output = output.replace('\n', ' ').strip()
        if len(display_output) > max_len:
            display_output = display_output[:max_len] + "..."
        print(f"   Kimenet (rövidítve): {display_output}\n")

    def on_agent_finish(self, finish: AgentFinish, color: Optional[str] = None, **kwargs: Any) -> Any:
        print(f"\n🏁 AGENT BEFEJEZTE A MUNKÁT (Final Answer generálva).")