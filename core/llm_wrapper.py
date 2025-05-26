# core/llm_wrapper.py
import logging
import json
import os
import tiktoken
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Callable
from datetime import datetime

# LangChain és Core importok
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.outputs import LLMResult, ChatResult, ChatGeneration
from langchain_core.messages import BaseMessage, AIMessage

# Belső importok a projekt struktúrából
from utils.output_parser import llm_output_xml_parser_and_fixer
from utils.callbacks import extract_and_save_thought
from utils.logging_setup import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)
xml_fixer_logger = logging.getLogger("llm_xml_output_fixer")


class LLMWithOutputFixer(BaseChatModel):
    """
    Egy egyedi BaseChatModel wrapper, amely elfogja a base_llm kimenetét,
    és egy megadott "fixer" függvényen keresztül megtisztítja, mielőtt visszaadná.
    Ez biztosítja, hogy az agent mindig a várt formátumú szöveget kapja.
    """
    base_llm: BaseChatModel
    xml_parser_fixer_function: Callable[[str], str]
    thoughts_log_path: Path
    direct_interaction_log_filepath: Optional[Path] = None

    def _log_to_direct_file(self, title: str, content: str):
        """Naplózási függvény a direkt LLM interakciókhoz."""
        log_file_path_to_use = self.direct_interaction_log_filepath
        if not log_file_path_to_use:
            log_file_path_to_use = Path(os.getcwd()) / "direct_interaction_log_fallback.txt"
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            log_entry = f"\n\n{'='*10} {title} ({timestamp}) {'='*10}\n{content}\n{'='*(22 + len(title))}\n"
            
            log_file_path_to_use.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file_path_to_use, "a", encoding="utf-8") as f:
                f.write(log_entry)
                f.flush()
        except Exception as e:
            print(f"❌ HIBA a direkt logfájlba ('{log_file_path_to_use}') írás közben: {e}")

    def _extract_original_text_robust(self, generation_item: Any, context_info: str = "") -> str:
        """Robusztus kinyerő az LLM szöveges válaszához."""
        original_text = ""
        if hasattr(generation_item, 'message') and isinstance(generation_item.message, BaseMessage) and hasattr(generation_item.message, 'content'):
            if isinstance(generation_item.message.content, str):
                return generation_item.message.content.strip()
            elif isinstance(generation_item.message.content, list):
                text_parts = [part["text"] for part in generation_item.message.content if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)]
                if text_parts:
                    return "\n".join(text_parts).strip()
        
        if hasattr(generation_item, 'text') and isinstance(generation_item.text, str):
            return generation_item.text.strip()
        
        return str(generation_item) if not original_text else original_text.strip()

    def _format_messages_for_log(self, messages: List[BaseMessage]) -> str:
        """Segédfüggvény a messages lista formázásához logolási célokra."""
        prompt_str_for_log = []
        try:
            for m_idx, m in enumerate(messages):
                msg_log = f"-- Message {m_idx} ({type(m).__name__}) --\n"
                if isinstance(m.content, str):
                    msg_log += f"{m.content}\n"
                elif isinstance(m.content, list):
                    for part_idx, part in enumerate(m.content):
                        if isinstance(part, dict) and part.get("type") == "text":
                            msg_log += f"  Part {part_idx} (text): {part.get('text', '')}\n"
                        else:
                            msg_log += f"  Part {part_idx} (other type): {str(part)[:100]}...\n"
                else:
                    msg_log += f"{str(m.content)[:500]}...\n"
                prompt_str_for_log.append(msg_log)
        except Exception as e_promptlog:
            prompt_str_for_log.append(f"<Error logging prompt messages: {e_promptlog}>")
        return "".join(prompt_str_for_log)

    def _process_generations(
        self,
        raw_chat_result: ChatResult,
        log_context_prefix: str = ""
    ) -> tuple[List[ChatGeneration], List[str], bool]:
        """Belső segédfüggvény a generációk feldolgozásához, _generate és _agenerate is használja."""
        all_processed_generations: List[ChatGeneration] = []
        full_raw_response_text_for_log: List[str] = []
        valid_content_obtained_overall = False
        
        generations_to_process = []
        if raw_chat_result.generations:
            if isinstance(raw_chat_result.generations[0], list):
                if raw_chat_result.generations[0]:
                    generations_to_process = raw_chat_result.generations[0]
            elif isinstance(raw_chat_result.generations[0], ChatGeneration):
                generations_to_process = raw_chat_result.generations
            else:
                 xml_fixer_logger.warning(f"{log_context_prefix}: Ismeretlen generációs struktúra: {type(raw_chat_result.generations[0])}")

        if not generations_to_process:
            xml_fixer_logger.warning(f"{log_context_prefix}: Nincsenek feldolgozható generációk a `raw_chat_result`-ban.")
            return all_processed_generations, full_raw_response_text_for_log, valid_content_obtained_overall

        for idx, generation_item in enumerate(generations_to_process):
            context_info = f"{log_context_prefix} (item {idx})"
            original_text_for_parser = self._extract_original_text_robust(generation_item, f"{context_info}_for_parser")

            if not original_text_for_parser or len(original_text_for_parser.strip()) < 5:
                continue
            
            full_raw_response_text_for_log.append(f"-- Generation Item {idx} (Nyers) --\n{original_text_for_parser}")
            
            corrected_react_string = self.xml_parser_fixer_function(original_text_for_parser)
            
            if self.thoughts_log_path:
                extract_and_save_thought(corrected_react_string, self.thoughts_log_path)

            new_message_kwargs = {}
            message_id_to_use = None
            if hasattr(generation_item, 'message') and isinstance(generation_item.message, AIMessage):
                new_message_kwargs = generation_item.message.additional_kwargs.copy() if generation_item.message.additional_kwargs else {}
                message_id_to_use = generation_item.message.id
            
            new_ai_message = AIMessage(content=corrected_react_string, additional_kwargs=new_message_kwargs or {}, id=message_id_to_use)
            gen_info = generation_item.generation_info if hasattr(generation_item, 'generation_info') else None
            all_processed_generations.append(ChatGeneration(message=new_ai_message, generation_info=gen_info))
            
            valid_content_obtained_overall = True
            break

        return all_processed_generations, full_raw_response_text_for_log, valid_content_obtained_overall

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        
        prompt_tokens_client_calculated = -1
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            current_prompt_tokens = sum(len(encoding.encode(m.content)) for m in messages if isinstance(m.content, str))
            prompt_tokens_client_calculated = current_prompt_tokens
            logger.info(f"KLIENSOLDALI SZÁMÍTÁS: A kérés (prompt) becsült tokenjeinek száma: {prompt_tokens_client_calculated}")
        except Exception as e_tiktoken:
            logger.warning(f"Hiba a kérés tokenjeinek kliensoldali számolása közben: {e_tiktoken}")

        prompt_str_for_log = self._format_messages_for_log(messages)
        self._log_to_direct_file("LLM Kérés (_generate)", prompt_str_for_log)

        raw_chat_result = self.base_llm._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        
        metadata_log_lines = ["LLM Válasz Metaadatok (direkt logolás az LLMWithOutputFixer-ből):"]
        prompt_tokens_server, completion_tokens_server, total_tokens_server = "N/A", "N/A", "N/A"

        if hasattr(raw_chat_result, 'llm_output') and raw_chat_result.llm_output:
            try:
                metadata_log_lines.append(json.dumps(raw_chat_result.llm_output, indent=2, ensure_ascii=False))
                token_usage = raw_chat_result.llm_output.get('token_usage', {})
                if token_usage:
                    prompt_tokens_server = token_usage.get('prompt_tokens', 'N/A')
                    completion_tokens_server = token_usage.get('completion_tokens', 'N/A')
                    total_tokens_server = token_usage.get('total_tokens', 'N/A')
            except Exception as e:
                metadata_log_lines.append(f"JSON HIBÁVAL: {e}")
        
        self._log_to_direct_file("LLM KÖZVETLEN METAADATOK (_generate)", "\n".join(metadata_log_lines))

        comparison_log_entry = [
            "--- Token Számvetés ---",
            f"  Kliens (tiktoken) - Prompt: {prompt_tokens_client_calculated if prompt_tokens_client_calculated != -1 else 'Hiba'}",
            f"  Szerver (jelentett) - Prompt: {prompt_tokens_server}",
            f"  Szerver (jelentett) - Válasz: {completion_tokens_server}",
            f"  Szerver (jelentett) - Összesen: {total_tokens_server}",
            "-----------------------"
        ]
        self._log_to_direct_file("TOKEN ÖSSZEHASONLÍTÁS (_generate)", "\n".join(comparison_log_entry))
        for line in comparison_log_entry: logger.info(line)

        all_processed_generations, raw_texts_for_log, valid_content = self._process_generations(raw_chat_result, "_generate")

        if raw_texts_for_log:
            self._log_to_direct_file("LLM NYERS VÁLASZ SZÖVEG (_generate)", "\n".join(raw_texts_for_log))
        
        if not valid_content:
            error_message = "Thought: Hiba a válasz feldolgozása közben (_generate).\nFinal Answer: Nem sikerült feldolgozni az LLM válaszát."
            new_ai_message = AIMessage(content=error_message)
            if not all_processed_generations:
                 all_processed_generations.append(ChatGeneration(message=new_ai_message))
        
        return ChatResult(generations=all_processed_generations, llm_output=raw_chat_result.llm_output)

    # Megjegyzés: Az eredeti fájlban két _agenerate metódus volt.
    # A második, részletesebb, több hibakereső logikát tartalmazó verziót használjuk.
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """
        Az _generate metódus aszinkron változata. Ugyanazokat a javításokat tartalmazza.
        """
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            prompt_tokens = sum(len(encoding.encode(m.content)) for m in messages if isinstance(m.content, str))
            logger.info(f"KLIENSOLDALI SZÁMÍTÁS (ASYNC): A kérés (prompt) becsült tokenjeinek száma: {prompt_tokens}")
        except Exception as e_tiktoken:
            logger.warning(f"Hiba a kérés tokenjeinek kliensoldali (async) számolása közben: {e_tiktoken}")
        
        prompt_str_for_log = self._format_messages_for_log(messages)
        self._log_to_direct_file("LLM Kérés (Async)", prompt_str_for_log.strip())

        raw_chat_result = await self.base_llm._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        
        all_processed_generations: List[ChatGeneration] = []
        full_raw_response_text_for_log = []
        
        print(f"DEBUG: Raw chat result típusa (async): {type(raw_chat_result)}")

        valid_content_obtained = False
        
        generation_source = raw_chat_result.generations if raw_chat_result.generations else []
        for i, generation_item_or_list in enumerate(generation_source):
            generation_list = generation_item_or_list if isinstance(generation_item_or_list, list) else [generation_item_or_list]
            
            found_content_in_list = False
            for j, generation_item in enumerate(generation_list):
                context_info = f"_agenerate (gen_list {i}, item {j})"
                raw_text_for_log = self._extract_original_text_robust(generation_item, f"{context_info}_raw_for_log")
                
                if not raw_text_for_log or len(raw_text_for_log) < 20:
                    print(f"DEBUG {context_info}: Kihagyva, túl rövid a tartalom ({len(raw_text_for_log)} chr)")
                    continue
                
                if found_content_in_list:
                    print(f"DEBUG {context_info}: Kihagyva, már találtunk tartalmat ebben a listában.")
                    continue
                    
                found_content_in_list = True
                valid_content_obtained = True
                full_raw_response_text_for_log.append(f"-- Gen Item {j} --\n{raw_text_for_log}")
                
                print(f"\nDEBUG (Async): Fixer bemenete ({context_info}):\n>>>\n{raw_text_for_log}\n<<<\n")
                
                # Itt a fixer_function-t hívjuk, de a wrapper a xml_parser_fixer_function-t kapja meg
                # a példányosításkor, így az fog lefutni.
                corrected_text = self.xml_parser_fixer_function(raw_text_for_log)

                print(f"\nDEBUG (Async): Fixer kimenete ({context_info}):\n>>>\n{corrected_text}\n<<<\n")

                if self.thoughts_log_path:
                    extract_and_save_thought(corrected_text, self.thoughts_log_path)

                new_message_kwargs = {}
                message_id = None
                if hasattr(generation_item, 'message') and isinstance(generation_item.message, AIMessage):
                    new_message_kwargs = generation_item.message.additional_kwargs.copy() if generation_item.message.additional_kwargs else {}
                    message_id = generation_item.message.id
                
                new_ai_message = AIMessage(content=corrected_text, additional_kwargs=new_message_kwargs or {}, id=message_id)
                gen_info = generation_item.generation_info if hasattr(generation_item, 'generation_info') else None
                all_processed_generations.append(ChatGeneration(message=new_ai_message, generation_info=gen_info))
        
        if not valid_content_obtained:
            # Ide kerül az alternatív kinyerési logika, ha a standard módszer csődöt mond
            # ... (az eredeti fájl alternatív és végső hibakezelési logikája)
            error_message = "Nem sikerült feldolgozni az LLM aszinkron válaszát."
            new_ai_message = AIMessage(content=f"Thought: Hiba az aszinkron válasz feldolgozása közben.\nFinal Answer: {error_message}")
            all_processed_generations.append(ChatGeneration(message=new_ai_message))
            print("KRITIKUS HIBA (Async): Nem sikerült értelmes tartalmat kinyerni a válaszból!")
        
        self._log_to_direct_file("LLM Nyers Válasz (Async, fixer előtt)", "\n".join(full_raw_response_text_for_log))
        
        return ChatResult(generations=all_processed_generations, llm_output=raw_chat_result.llm_output)

    @property
    def _llm_type(self) -> str:
        return "llm_with_output_fixer"