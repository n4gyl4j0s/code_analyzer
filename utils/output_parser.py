# utils/output_parser.py
import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Loggerek példányosítása a modulhoz
fixer_logger = logging.getLogger("llm_output_fixer")
xml_fixer_logger = logging.getLogger("llm_xml_output_fixer")
tools_logger = logging.getLogger("v2_tools") # A clean_llm_action_input használja

# Ezt a függvényt az llm_output_xml_parser_and_fixer hívja fallback-ként.
def llm_output_fixer_function(raw_llm_output_text: str) -> str:
    """
    Javított verzió a kimenet-tisztítónak, amely kezeli a problémás eseteket.
    """
    # Használj egy dedikált loggert, ha van, egyébként az alap loggert.
    current_logger = logging.getLogger("llm_output_fixer") if logging.getLogger("llm_output_fixer").hasHandlers() else logging.getLogger()

    # Debug célokra mentsük el a bemenetet egy külön fájlba is
    debug_input_path = Path("debug_fixer_input.txt")
    try:
        with open(debug_input_path, "w", encoding="utf-8") as f:
            f.write(f"FIXER BEMENET [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]:\n{raw_llm_output_text}")
        current_logger.info(f"Fixer bemenet mentve: {debug_input_path}")
    except Exception as e_debug:
        current_logger.error(f"Hiba a debug fájl írásakor: {e_debug}")

    current_logger.debug(f"--- LLM Kimenet FIXER ELŐTT ---\n{raw_llm_output_text}\n-------------------------------")
    if not raw_llm_output_text:
        current_logger.warning("Üres LLM kimenet érkezett a fixerhez.")
        return ""
    
    corrected_text = raw_llm_output_text.strip()

    # 0. Többszöri karakterkonverzió-problémák detektálása és javítása
    encoding_issue_patterns = {
        'Ã©': 'é', 'Ã¡': 'á', 'Ã³': 'ó', 'Ã­': 'í', 'Ãº': 'ú', 'Ã¼': 'ü', 'Å': 'ő', 'Å±': 'ű'
    }
    for wrong, correct in encoding_issue_patterns.items():
        if wrong in corrected_text:
            corrected_text = corrected_text.replace(wrong, correct)
            current_logger.info(f"Karakterkódolási probléma javítva: '{wrong}' -> '{correct}'")

    # "Smart quotes" / "Fancy quotes" cseréje standard idézőjelekre
    smart_quotes_replacements = {
        '\u201c': '"',  # Nyitó görbe idézőjel
        '\u201d': '"',  # Záró görbe idézőjel
        '“': '"',      # Alternatív nyitó görbe
        '”': '"'      # Alternatív záró görbe
    }
    original_text_before_smart_quotes_fix = corrected_text
    for smart_quote, standard_char in smart_quotes_replacements.items():
        if smart_quote in corrected_text:
            corrected_text = corrected_text.replace(smart_quote, standard_char)
    
    if original_text_before_smart_quotes_fix != corrected_text:
        current_logger.info("Smart quotes/fancy quotes javítva standard karakterekre.")

    # 0.b Felesleges elválasztók és üres sorok eltávolítása
    lines = corrected_text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line in ["---", "----", "```", "="*10, "="*20, "-"*10, "-"*20]:
            continue
        if stripped_line == "" and cleaned_lines and cleaned_lines[-1].strip() == "":
            continue
        cleaned_lines.append(line)
    
    while cleaned_lines and cleaned_lines[0].strip() == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1].strip() == "":
        cleaned_lines.pop()
    
    if cleaned_lines:
        corrected_text = "\n".join(cleaned_lines).strip()
        current_logger.debug(f"Felesleges elválasztók/üres sorok eltávolítása után: {corrected_text[:150]}...")

    # 1. Markdown JSON keretek eltávolítása
    if corrected_text.startswith("```json") and corrected_text.endswith("```"):
        corrected_text = corrected_text[len("```json"): -len("```")].strip()
        current_logger.info("JSON markdown ```json keret eltávolítva.")
    elif corrected_text.startswith("```") and corrected_text.endswith("```"):
        temp_content = corrected_text[len("```"): -len("```")].strip()
        if temp_content.startswith("{") and temp_content.endswith("}"):
            corrected_text = temp_content
            current_logger.info("Markdown ``` keret eltávolítva JSON tartalomról.")

    # 2. Kulcsszavak normalizálása és magyar->angol csere
    replacements = [
        (r"^\s*(?:\*\* *)?(?:### )?Végső válasz\s*:", "Final Answer:", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Gondolat\s*:", "Thought:", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Akció\s*:", "Action:", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Akció Bemenete\s*:", "Action Input:", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Válasz\s*:", "Final Answer:", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Final\s+Thought\s*:", "Thought:", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Final\s+Action\s*:", "Action:", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Thought\s*:\s*", "Thought: ", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Action\s*:\s*", "Action: ", re.IGNORECASE | re.MULTILINE),
        (r"^\s*Action Input\s*:\s*", "Action Input: ", re.IGNORECASE | re.MULTILINE),
        (r"^\s*(?:\*\* *)?Final Answer\s*:\s*", "Final Answer: ", re.IGNORECASE | re.MULTILINE),
        (r"^\s*\*\*Thought\*\*\s*:\s*", "Thought: ", re.IGNORECASE | re.MULTILINE),
        (r"^\s*\*\*Action\*\*\s*:\s*", "Action: ", re.IGNORECASE | re.MULTILINE),
        (r"^\s*\*\*Action Input\*\*\s*:\s*", "Action Input: ", re.IGNORECASE | re.MULTILINE),
        (r"^\s*\*\*Final Answer\*\*\s*:\s*", "Final Answer: ", re.IGNORECASE | re.MULTILINE),
        (r"Action Input:(.*?)Observation:", r"Action Input:\1", re.DOTALL),
    ]
    
    text_before_keyword_norm = corrected_text
    for pattern, replacement, flags in replacements:
        corrected_text = re.sub(pattern, replacement, corrected_text, flags=flags)
    if text_before_keyword_norm != corrected_text:
        current_logger.info(f"Kulcsszó normalizálás/csere történt.")

    # 2.b. Action Input: {} -> Action Input: "{}" javítás
    corrected_text_before_ai_fix = corrected_text
    corrected_text = re.sub(r"(^\s*Action Input\s*:\s*)(\{\s*\})(?=\s*(?:$|\n))", r'\1"{}"', corrected_text, flags=re.MULTILINE)
    if corrected_text_before_ai_fix != corrected_text:
        current_logger.info("Action Input: {} javítva Action Input: \"{}\"-re.")

    # 3. Hiányzó `Thought:` prefix pótlása
    if not re.search(r"^\s*Thought:", corrected_text, re.MULTILINE | re.IGNORECASE) and \
       not (corrected_text.strip().startswith("{") and corrected_text.strip().endswith("}")):
        action_pos = corrected_text.find("Action:")
        final_answer_pos = corrected_text.find("Final Answer:")
        first_keyword_pos = -1
        if action_pos != -1 and final_answer_pos != -1: first_keyword_pos = min(action_pos, final_answer_pos)
        elif action_pos != -1: first_keyword_pos = action_pos
        elif final_answer_pos != -1: first_keyword_pos = final_answer_pos

        if first_keyword_pos != -1:
            if first_keyword_pos > 0:
                prose_before_keyword = corrected_text[:first_keyword_pos].strip()
                if prose_before_keyword:
                    corrected_text = f"Thought: {prose_before_keyword}\n{corrected_text[first_keyword_pos:]}"
                    current_logger.info("Hiányzó 'Thought:' prefix hozzáadva (próza alapján).")
                else:
                    corrected_text = f"Thought: A következő lépést tervezem.\n{corrected_text[first_keyword_pos:]}"
                    current_logger.info("Hiányzó 'Thought:' prefix hozzáadva (üres szöveg + Action/Final Answer).")
            else:
                corrected_text = f"Thought: A következő lépést tervezem.\n{corrected_text}"
                current_logger.info("Hiányzó 'Thought:' prefix hozzáadva (Action/Final Answer az elején).")
        elif corrected_text.strip():
            corrected_text = f"Thought: {corrected_text}\nFinal Answer: Sajnos nem tudtam megfelelő formátumban válaszolni."
            current_logger.info("Nincs ReAct formátum, a teljes szöveg Thought + alapértelmezett Final Answer-ként kezelve.")

    # 4. "Both Action and Final Answer" kezelése
    if "Final Answer:" in corrected_text and "Action:" in corrected_text:
        final_answer_pos = corrected_text.rfind("Final Answer:")
        action_pos = corrected_text.rfind("Action:", 0, final_answer_pos)
        if action_pos != -1:
            thought_before_fa_str = corrected_text[:final_answer_pos]
            last_thought_match = list(re.finditer(r"Thought:", thought_before_fa_str, re.IGNORECASE | re.MULTILINE))
            if last_thought_match:
                last_thought_pos = last_thought_match[-1].start()
                if last_thought_pos < action_pos < final_answer_pos:
                    corrected_text = corrected_text[:action_pos].rstrip() + "\n" + corrected_text[final_answer_pos:]
                    current_logger.warning("Action és Final Answer is volt. Final Answer priorizálva, Action blokk eltávolítva.")
            else:
                corrected_text = f"Thought: A végső választ adom meg.\n{corrected_text[final_answer_pos:]}"
                current_logger.warning("Final Answer és Action is volt, de Thought nem. Általános Thought hozzáadva.")

    # 5. Hiányzó Action Input kezelése
    if "Action:" in corrected_text and "Action Input:" not in corrected_text:
        action_match = re.search(r"Action:\s*([^\n]+)", corrected_text)
        if action_match:
            action_name = action_match.group(1).strip()
            action_pos = action_match.start()
            next_part_match = re.search(r"\n(Thought:|Final Answer:)", corrected_text[action_pos:])
            if next_part_match:
                insert_pos = action_pos + next_part_match.start()
                corrected_text = corrected_text[:insert_pos] + "\nAction Input: {}" + corrected_text[insert_pos:]
            else:
                corrected_text = corrected_text + "\nAction Input: {}"
            current_logger.warning(f"Hiányzó 'Action Input:' hozzáadva az '{action_name}' Action után.")
            
    # X. Biztosítsuk, hogy a kimenet ReAct szöveges formátumú legyen, NE csak egy JSON string.
    # Ez a lépés akkor fut le, ha a corrected_text egy JSON stringnek tűnik,
    # de nem tartalmazza már a "Thought:", "Action:" stringeket (mert pl. a 0. vagy 1. lépés eltávolította őket).
    # Vagy ha az LLM eleve csak egy JSON objektumot adott vissza.
    is_likely_json_but_not_react_string = False
    if corrected_text.strip().startswith("{") and corrected_text.strip().endswith("}"):
        if not (re.search(r"^\s*Thought:", corrected_text, re.IGNORECASE | re.MULTILINE) and \
                (re.search(r"^\s*Action:", corrected_text, re.IGNORECASE | re.MULTILINE) or \
                 re.search(r"^\s*Final Answer:", corrected_text, re.IGNORECASE | re.MULTILINE))):
            is_likely_json_but_not_react_string = True

    if is_likely_json_but_not_react_string:
        try:
            data = json.loads(corrected_text.strip()) # Próbáljuk meg JSON-ként parse-olni
            if isinstance(data, dict):
                # Speciális JSON formátumok kezelése, amelyekben más kulcsneveket használnak
                # De átalakíthatók standard Thought/Action/Action Input/Final Answer formára
                
                # 1. eset: 'thought', 'action', 'action_input' kulcsok (snake_case)
                if 'thought' in data and ('action' in data or 'final_answer' in data):
                    current_logger.info("Snake case JSON kulcsok átalakítása ReAct formátumra.")
                    thought_value = data.get('thought', '')
                    
                    if 'action' in data:
                        action_value = data.get('action', '')
                        action_input_value = data.get('action_input', {})
                        new_output_parts = [
                            f"Thought: {thought_value}",
                            f"Action: {action_value}",
                            f"Action Input: {json.dumps(action_input_value)}"
                        ]
                    else:  # final_answer
                        final_answer_value = data.get('final_answer', '')
                        new_output_parts = [
                            f"Thought: {thought_value}",
                            f"Final Answer: {final_answer_value}"
                        ]
                    
                    corrected_text = "\n".join(new_output_parts)
                    current_logger.info("JSON snake_case formátum átalakítva standard ReAct szöveggé.")
                
                # 2. eset: 'Thought', 'Action', 'ActionInput', 'FinalAnswer' kulcsok (CamelCase)
                elif 'Thought' in data and ('Action' in data or 'FinalAnswer' in data):
                    current_logger.info("CamelCase JSON kulcsok átalakítása ReAct formátumra.")
                    thought_value = data.get('Thought', '')
                    
                    if 'Action' in data:
                        action_value = data.get('Action', '')
                        action_input_value = data.get('ActionInput', {})
                        new_output_parts = [
                            f"Thought: {thought_value}",
                            f"Action: {action_value}",
                            f"Action Input: {json.dumps(action_input_value)}"
                        ]
                    else:  # FinalAnswer
                        final_answer_value = data.get('FinalAnswer', '')
                        new_output_parts = [
                            f"Thought: {thought_value}",
                            f"Final Answer: {final_answer_value}"
                        ]
                    
                    corrected_text = "\n".join(new_output_parts)
                    current_logger.info("JSON CamelCase formátum átalakítva standard ReAct szöveggé.")
                
                # 3. eset: Standard 'Thought', 'Action', 'Action Input', 'Final Answer' kulcsok
                elif "Thought" in data and ("Action" in data or "Final Answer" in data):
                    current_logger.info("A fixer kimenete valószínűleg JSON volt, átalakítás ReAct szöveges formátumra.")
                    new_output_parts = [f"Thought: {data['Thought']}"]
                    if "Action" in data:
                        new_output_parts.append(f"Action: {data['Action']}")
                        action_input_val = data.get("Action Input") # .get() használata, mert lehet, hogy nincs
                        
                        if action_input_val is None:
                            new_output_parts.append(f"Action Input: {{}}")
                        elif isinstance(action_input_val, (dict, list)):
                            new_output_parts.append(f"Action Input: {json.dumps(action_input_val)}")
                        else: # Ha string vagy más primitív típus
                            action_input_str = str(action_input_val)
                            # Ha ez a string már egy valid JSON string (pl. "{}"), akkor ne idézőjelezzük újra
                            try:
                                json.loads(action_input_str) # Próba parse-olni
                                if (action_input_str.startswith("{") and action_input_str.endswith("}")) or \
                                   (action_input_str.startswith("[") and action_input_str.endswith("]")):
                                    new_output_parts.append(f"Action Input: {action_input_str}")
                                else: # Ha parse-olható, de nem objektum/tömb string, akkor idézőjelezzük
                                    new_output_parts.append(f"Action Input: {json.dumps(action_input_str)}")
                            except json.JSONDecodeError: # Ha nem parse-olható stringként, akkor sima stringként idézőjelezzük
                                new_output_parts.append(f"Action Input: {json.dumps(action_input_str)}")
                                
                    elif "Final Answer" in data:
                        new_output_parts.append(f"Final Answer: {data['Final Answer']}")
                    
                    if len(new_output_parts) > 1: # Csak ha sikerült legalább Thought + (Action vagy FinalAnswer)
                        corrected_text = "\n".join(new_output_parts)
                else:
                    # Nem standard JSON, próbáljunk meg valami használhatót csinálni belőle
                    thought_keys = ['thought', 'thinking', 'reason', 'reasoning', 'analysis']
                    action_keys = ['action', 'tool', 'function', 'command']
                    action_input_keys = ['action_input', 'input', 'tool_input', 'args', 'arguments', 'params']
                    final_answer_keys = ['final_answer', 'answer', 'response', 'result', 'conclusion']
                    
                    # Keresünk megfelelő kulcsokat a dict-ben
                    thought_value = None
                    for key in thought_keys:
                        if key in data:
                            thought_value = data[key]
                            break
                    
                    is_final_answer = False
                    action_value = None
                    for key in action_keys:
                        if key in data:
                            action_value = data[key]
                            break
                    
                    action_input_value = None
                    for key in action_input_keys:
                        if key in data:
                            action_input_value = data[key]
                            break
                    
                    final_answer_value = None
                    for key in final_answer_keys:
                        if key in data:
                            final_answer_value = data[key]
                            is_final_answer = True
                            break
                    
                    # Ha van megfelelő kulcs, akkor előállítjuk a ReAct formátumot
                    if thought_value:
                        new_output_parts = [f"Thought: {thought_value}"]
                        
                        if is_final_answer and final_answer_value:
                            new_output_parts.append(f"Final Answer: {final_answer_value}")
                        elif action_value:
                            new_output_parts.append(f"Action: {action_value}")
                            if action_input_value:
                                # Ha dict vagy list, akkor JSON.stringify
                                if isinstance(action_input_value, (dict, list)):
                                    new_output_parts.append(f"Action Input: {json.dumps(action_input_value)}")
                                else:
                                    new_output_parts.append(f"Action Input: {action_input_value}")
                            else:
                                new_output_parts.append("Action Input: {}")
                        
                        if len(new_output_parts) > 1: # Csak ha sikerült legalább Thought + (Action vagy FinalAnswer)
                            corrected_text = "\n".join(new_output_parts)
                            current_logger.info("Nem standard JSON kulcsokból ReAct formátumú szöveg létrehozva.")
            
            # Ha a JSON egy lista, és tartalmazza a ReAct formátum részeket
            elif isinstance(data, list):
                # Nézzük meg, hogy a lista elemei lehetnek-e ReAct lépések
                # Például: [{"role": "thought", "content": "..."}, {"role": "action", "content": "..."}]
                new_output_parts = []
                
                for item in data:
                    if isinstance(item, dict) and "role" in item and "content" in item:
                        role = item["role"].lower()
                        content = item["content"]
                        
                        if role == "thought":
                            new_output_parts.append(f"Thought: {content}")
                        elif role in ["action", "tool"]:
                            new_output_parts.append(f"Action: {content}")
                        elif role in ["action_input", "tool_input"]:
                            new_output_parts.append(f"Action Input: {content}")
                        elif role in ["final_answer", "answer"]:
                            new_output_parts.append(f"Final Answer: {content}")
                
                if len(new_output_parts) >= 2:  # Legalább Thought + (Action vagy FinalAnswer)
                    corrected_text = "\n".join(new_output_parts)
                    current_logger.info("JSON lista átalakítva ReAct formátumra.")
                
        except json.JSONDecodeError:
            current_logger.debug("A corrected_text nem volt valid JSON (az X. pontban), vagy már a várt szöveges formátumban van.")
        except Exception as e_json_to_react:
            current_logger.error(f"Hiba a JSON -> ReAct szöveg átalakítás közben (X. pont): {e_json_to_react}")

    # Utolsó ellenőrzés: van megfelelő Thought: és (Action: + Action Input:) vagy Final Answer: ?
    has_thought = re.search(r"^\s*Thought:", corrected_text, re.MULTILINE | re.IGNORECASE) is not None
    has_action = re.search(r"^\s*Action:", corrected_text, re.MULTILINE | re.IGNORECASE) is not None
    has_action_input = re.search(r"^\s*Action Input:", corrected_text, re.MULTILINE | re.IGNORECASE) is not None
    has_final_answer = re.search(r"^\s*Final Answer:", corrected_text, re.MULTILINE | re.IGNORECASE) is not None
    
    # Ha van Action, de nincs Action Input, adjunk hozzá egy üres Action Input-ot
    if has_action and not has_action_input:
        # Keresünk mintát, ahol Action után rögtön Final Answer vagy Thought következik
        action_without_input_match = re.search(r"(^\s*Action:[^\n]*\n)(?:\s*(?:Thought:|Final Answer:))", corrected_text, re.MULTILINE)
        if action_without_input_match:
            # Beszúrjuk az Action Input-ot az Action után
            insertion_point = action_without_input_match.start(2)
            corrected_text = corrected_text[:insertion_point] + "Action Input: {}\n" + corrected_text[insertion_point:]
            current_logger.warning("Action után hiányzó Action Input beszúrva.")
        elif has_action and corrected_text.strip().endswith(re.search(r"^\s*Action:[^\n]*", corrected_text, re.MULTILINE).group(0)):
            # Az Action a válasz végén van
            corrected_text = corrected_text.strip() + "\nAction Input: {}"
            current_logger.warning("Action után hiányzó Action Input beszúrva a válasz végére.")
    
    # Ha van Thought, de sem Action, sem Final Answer nincs
    if has_thought and not has_action and not has_final_answer:
        corrected_text = corrected_text.strip() + "\nFinal Answer: Sajnos nem tudtam megfelelő formátumban válaszolni a kérdésedre."
        current_logger.warning("Thought után hiányzó Action vagy Final Answer. Alapértelmezett Final Answer hozzáadva.")
    
    # Ha nincs Thought, de van Action vagy Final Answer, adjunk hozzá egy alap Thought-ot
    if not has_thought and (has_action or has_final_answer):
        if has_final_answer:
            first_final_pos = re.search(r"^\s*Final Answer:", corrected_text, re.MULTILINE | re.IGNORECASE).start()
            corrected_text = "Thought: Megvan a végső válasz.\n" + corrected_text[first_final_pos:]
            current_logger.warning("Final Answer előtt hiányzó Thought. Alap Thought hozzáadva.")
        elif has_action:
            first_action_pos = re.search(r"^\s*Action:", corrected_text, re.MULTILINE | re.IGNORECASE).start()
            corrected_text = "Thought: A következő lépést tervezem.\n" + corrected_text[first_action_pos:]
            current_logger.warning("Action előtt hiányzó Thought. Alap Thought hozzáadva.")

    debug_output_path = Path("debug_fixer_output.txt")
    try:
        with open(debug_output_path, "w", encoding="utf-8") as f:
            f.write(f"FIXER KIMENET [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]:\n{corrected_text}")
        current_logger.info(f"Fixer kimenet mentve: {debug_output_path}")
    except Exception as e_debug:
        current_logger.error(f"Hiba a debug kimeneti fájl írásakor: {e_debug}")

    if raw_llm_output_text.strip() != corrected_text:
        current_logger.info(f"--- LLM Kimenet FIXER UTÁN (végleges) ---\n{corrected_text}\n------------------------------")
    else:
        current_logger.debug("LLM kimenet javító (fixer) nem végzett érdemi módosítást.")
        
    return corrected_text


# --- XML Parser és Fixer ---

def clean_tag_content(content: str, tag_name: str, is_json_content: bool = False) -> str:
    """Tisztítási funkció a tagekből kinyert tartalomhoz."""
    if content is None: return ""
    cleaned = content.strip()
    fence_match = re.match(r"^```(?:\w+)?\n(.*?)\n```$", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    elif cleaned.startswith("```") and cleaned.endswith("```"):
        temp_content = cleaned[3:-3].strip()
        if temp_content or is_json_content:
            cleaned = temp_content
            xml_fixer_logger.info(f"Markdown ``` keret eltávolítva a '{tag_name}' tag tartalmából.")
    if not is_json_content:
        lines = cleaned.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line in ["---", "----", "```", "="*10, "="*20, "-"*10, "-"*20]: continue
            if stripped_line == "" and cleaned_lines and cleaned_lines[-1].strip() == "": continue
            cleaned_lines.append(line)
        while cleaned_lines and cleaned_lines[0].strip() == "": cleaned_lines.pop(0)
        while cleaned_lines and cleaned_lines[-1].strip() == "": cleaned_lines.pop()
        if cleaned_lines or (not cleaned_lines and cleaned == ""):
            cleaned = "\n".join(cleaned_lines)
    return cleaned.strip()

def extract_single_tag_content(xml_string: str, tag_name: str) -> Optional[str]:
    """Egyetlen, elsőként talált egyszerű XML-szerű tag tartalmának kinyerése."""
    if not xml_string: return None
    match = re.search(f"<{tag_name}>(.*?)</{tag_name}>", xml_string, re.DOTALL)
    return match.group(1).strip() if match else None

def find_all_top_level_tag_contents(xml_string: str, tag_name: str) -> List[str]:
    """Minden legfelső szintű, megadott nevű tag tartalmát kinyeri listaként."""
    if not xml_string: return []
    matches = re.findall(f"<{tag_name}>(.*?)</{tag_name}>", xml_string, re.DOTALL)
    return [match.strip() for match in matches]


def llm_output_xml_parser_and_fixer(raw_llm_output_text: str) -> str:
    """
    Hibrid feldolgozó, amely először XML-t próbál értelmezni, majd fallback-el a kulcsszavas formátumra.
    """
    xml_fixer_logger.debug(f"--- LLM Kimenet (Hibrid XML/Fallback Fixer) ELŐTT ---\n{raw_llm_output_text}\n---")
    
    # --- 1. FÁZIS: Elsődleges próbálkozás az XML feldolgozásával ---

    # 1a. Karakterkódolási problémák és külső keretek javítása
    corrected_text_encoded = raw_llm_output_text
    encoding_issue_patterns = {
        'Ã©': 'é', 'Ã¡': 'á', 'Ã³': 'ó', 'Ã­': 'í', 'Ãº': 'ú', 'Ã¼': 'ü', 'Å': 'ő', 'Å±': 'ű',
        'Ã‰': 'É', 'Ã?': 'Á', 'Ã“': 'Ó', 'Ã?': 'Í', 'Ãš': 'Ú', 'Ãœ': 'Ü', 'Å?': 'Ő', 'Å°': 'Ű'
    }
    for wrong, correct in encoding_issue_patterns.items():
        if wrong in corrected_text_encoded:
            corrected_text_encoded = corrected_text_encoded.replace(wrong, correct)

    temp_cleaned_outer = corrected_text_encoded.strip()
    if temp_cleaned_outer.startswith("```xml") and temp_cleaned_outer.endswith("```"):
        temp_cleaned_outer = temp_cleaned_outer[len("```xml"):-len("```")].strip()
    elif temp_cleaned_outer.startswith("```") and temp_cleaned_outer.endswith("```"):
        potential_inner_content = temp_cleaned_outer[len("```"):-len("```")].strip()
        if not (potential_inner_content.startswith("{") and potential_inner_content.endswith("}")):
            temp_cleaned_outer = potential_inner_content
    
    corrected_text_for_block_search = temp_cleaned_outer

    # 1b. <llm_response> blokkok keresése
    all_response_blocks = find_all_top_level_tag_contents(corrected_text_for_block_search, "llm_response")

    # Ha találtunk XML blokkot, feldolgozzuk azt
    if all_response_blocks:
        if len(all_response_blocks) > 1:
            xml_fixer_logger.warning(f"Több ({len(all_response_blocks)}) '<llm_response>' blokk található. Az UTOLSÓT használjuk.")
        response_block_content_to_parse = all_response_blocks[-1]

        # Belső tagek kinyerése és tisztítása
        raw_thought = extract_single_tag_content(response_block_content_to_parse, "thought")
        thought_content_cleaned = clean_tag_content(raw_thought, "thought")
        action_tool_raw_check = extract_single_tag_content(response_block_content_to_parse, "action_tool")
        final_answer_raw_check = extract_single_tag_content(response_block_content_to_parse, "final_answer_text")

        if not thought_content_cleaned:
            if final_answer_raw_check is not None:
                thought_content_cleaned = "A végső választ adom meg."
            elif action_tool_raw_check is not None:
                 thought_content_cleaned = "A következő lépést tervezem."

        action_tool_content_cleaned = clean_tag_content(action_tool_raw_check, "action_tool")
        raw_action_param_json = extract_single_tag_content(response_block_content_to_parse, "action_param_json")
        action_param_json_cleaned = clean_tag_content(raw_action_param_json, "action_param_json", is_json_content=True)
        final_answer_content_cleaned = clean_tag_content(final_answer_raw_check, "final_answer_text")

        # ReAct string összeállítása az XML adatokból
        final_react_string = ""
        if action_tool_content_cleaned:
            action_param_final = "{}"
            if action_param_json_cleaned:
                try:
                    json.loads(action_param_json_cleaned)
                    action_param_final = action_param_json_cleaned
                except json.JSONDecodeError:
                    xml_fixer_logger.warning(f"Az '<action_param_json>' tartalma ('{action_param_json_cleaned[:100]}...') nem valid JSON. Próbálkozás stringként való idézőjelezéssel.")
                    try:
                        action_param_final = json.dumps(action_param_json_cleaned.strip())
                    except:
                         action_param_final = "{}"
            final_react_string = f"Thought: {thought_content_cleaned}\nAction: {action_tool_content_cleaned}\nAction Input: {action_param_final}"
        elif final_answer_content_cleaned:
            final_react_string = f"Thought: {thought_content_cleaned}\nFinal Answer: {final_answer_content_cleaned}"
        elif thought_content_cleaned:
             final_react_string = f"Thought: {thought_content_cleaned}\nFinal Answer: A gondolatmenetet követően nem sikerült egyértelmű akciót vagy végső választ kinyerni a formázott LLM kimenetből."
        
        if final_react_string:
            xml_fixer_logger.info("Sikeres feldolgozás XML-ként.")
            xml_fixer_logger.debug(f"--- LLM Kimenet (Hibrid Fixer) UTÁN (XML ág) ---\n{final_react_string}\n---")
            return final_react_string

    # 2. FÁZIS: Fallback a kulcsszavas feldolgozásra
    xml_fixer_logger.warning("Nem található érvényes <llm_response> tag. Fallback a kulcsszavas ReAct formátumra.")
    fallback_result = llm_output_fixer_function(raw_llm_output_text)

    if "Action:" in fallback_result or "Final Answer:" in fallback_result:
        xml_fixer_logger.info("Sikeres feldolgozás fallback (kulcsszavas) módban.")
        return fallback_result

    # 3. FÁZIS: Végső hiba
    xml_fixer_logger.error("Sem az XML, sem a kulcsszavas feldolgozás nem tudta értelmezni a kimenetet.")
    return "Thought: Feldolgozási hiba.\nFinal Answer: Nem sikerült feldolgozni az LLM válaszát."


# --- Eszköz Bemenet Tisztító ---

def clean_llm_action_input(raw_input: str) -> str:
    """
    Megtisztítja az LLM által az eszközöknek adott bemeneti stringet a gyakori formázási hibáktól.
    """
    if not isinstance(raw_input, str) or not raw_input.strip():
        tools_logger.debug("clean_llm_action_input: Üres vagy nem string input, '{}' visszaadva.")
        return "{}"

    text_to_clean = raw_input.strip()
    tools_logger.debug(f"Tisztítás kezdete, nyers (stripelt) input: '{text_to_clean[:200]}...'")

    # 1. "Smart quotes" (görbe idézőjelek) cseréje standard, egyenes idézőjelekre.
    smart_quotes_replacements = {'\u201c': '"', '\u201d': '"', '“': '"', '”': '"'}
    original_text_before_smart_quotes_fix = text_to_clean
    for smart, standard in smart_quotes_replacements.items():
        if smart in text_to_clean:
            text_to_clean = text_to_clean.replace(smart, standard)
    if original_text_before_smart_quotes_fix != text_to_clean:
        tools_logger.info("Smart quotes javítva a clean_llm_action_input-ban.")

    # 2. Markdown kódblokk eltávolítása (pl. ```json...```)
    code_block_match = re.search(r"```(?:json|JSON)?\s*([\s\S]*?)\s*```", text_to_clean, re.DOTALL)
    if code_block_match:
        text_to_clean = code_block_match.group(1).strip()
        tools_logger.debug("Markdown kódblokk eltávolítva.")
        
    # 3. Felesleges záró karakterek (pl. '>', '">') eltávolítása a string végéről.
    original_before_rstrip = text_to_clean
    text_to_clean = text_to_clean.rstrip('>" ')
    if original_before_rstrip != text_to_clean:
        removed_part = original_before_rstrip[len(text_to_clean):]
        tools_logger.info(f"Felesleges záró karakterek ('{removed_part}') eltávolítva az Action Input végéről.")

    # =================================================================================
    # === ÚJ JAVÍTÁS: Hiányzó JSON lezáró karakter '}' pótlása ===
    # =================================================================================
    # Ellenőrizzük, hogy a string egy JSON objektumnak tűnik-e, aminek csak a végéről hiányzik a '}'.
    # Pl. `{"command": "..."` helyett `{"command": "..."}`
    if text_to_clean.startswith('{"') and text_to_clean.endswith('"') and not text_to_clean.endswith('"}'):
        original_for_log = text_to_clean
        # Betesszük a hiányzó '}' a string vége és az utolsó idézőjel közé.
        text_to_clean = text_to_clean[:-1] + '}"'
        tools_logger.info(f"Hiányzó '}}' pótolva a JSON stringben. Eredeti: '{original_for_log}', Javított: '{text_to_clean}'")
    # =================================================================================
    # === JAVÍTÁS VÉGE ===
    # =================================================================================

    # 5. Ha a tisztítás után üres lett a string, adjunk vissza egy valid üres JSON-t.
    if not text_to_clean.strip():
        tools_logger.debug("A tisztítási folyamat végén az input üres lett. '{}' visszaadva.")
        return "{}"
        
    tools_logger.info(f"A `clean_llm_action_input` által visszaadott tisztított string: '{text_to_clean[:200]}...'")
    return text_to_clean