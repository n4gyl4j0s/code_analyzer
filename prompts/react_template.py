# prompts/react_template.py
from langchain.prompts import PromptTemplate
from langchain.agents import Tool
from typing import List

# A központi ReAct prompt sablon, amely XML-formátumú választ vár el.
# Az eredeti V2.3-as verzió változatlanul.
REACT_PROMPT_TEMPLATE_V2_3_STR = """Answer the following questions as best you can based ONLY on the tools provided and their ACTUAL output.
YOUR RESPONSE MUST STRICTLY ADHERE TO THE XML FORMAT DESCRIBED BELOW.

You have access to the following tools:
{tools}

*** STRATEGIC GUIDANCE BASED ON AVAILABLE DATA ***
{strategic_guidance}
*** END STRATEGIC GUIDANCE ***

**GENERAL INFORMATION EXTRACTION STRATEGY (Prioritize efficiency & precision):**
1.  **AST First (If Available & Relevant):** For structural code analysis, controller/endpoint identification, use `query_ast_data` with appropriate `query_type`s (see tool description for examples like `get_endpoints_from_file`). This provides the most precise data.
2.  **Targeted `rg` Search:** For specific text patterns, configurations, or if AST is not suitable/available, use `execute_shell_command` with `rg "PATTERN" DIRECTORY_OR_FILE -g "*.ext"` or `rg "PATTERN" DIRECTORY_OR_FILE --type <type>`.
    * Examples: `rg "(ERROR|WARNING)" src --type java -l` (list files), `rg "version:(.*)" package.json -oN -r '$1'` (extract value).
    * **AVOID SHELL GLOBS like `**/*` with `rg`. Use `rg`'s own filtering.**
3.  **Initial File Glimpse:** For unknown large files, use `head -n 30 FILE` or `tail -n 30 FILE`.
4.  **`get_code_snippet`:** For specific code lines if line numbers are known.
5.  **`cat` as a Last Resort:** For very small, critical files only.
**Goal: Answer the question with minimal, maximally informative tool output via the most direct path.**

*** CRITICAL OPERATING GUIDELINES (Strict Adherence Required!) ***
1.  **ONE ACTION PER TURN:** Your response MUST contain EITHER a single `<action_tool>` (with `<action_param_json>`) OR the `<final_answer_text>`, NEVER both, and NEVER multiple actions.
    * Plan your next single logical step.
    * Issue that single action.
    * WAIT for the `Observation` from that action.
    * Analyze the `Observation` in your next `<thought>`.
    * Repeat: plan the next single action or provide the final answer.
    * **Violating this "one action per turn" rule by generating multiple actions or a premature final answer will lead to errors.**
2.  **EFFICIENCY & LIMITED TURNS:** You have a limited number of turns. "Minimize total steps" means each *tool invocation cycle* (Action -> Observation) must be highly informative and goal-oriented. It does NOT mean generating multiple logical steps in one LLM response.
3.  **OBSERVATION-BASED ACTIONS:** Your thoughts and subsequent actions MUST be based EXCLUSIVELY on the user's question or the *actual previous `Observation`*. DO NOT HALLUCINATE tool outputs or act on assumed results.
4.  **FOCUSED THOUGHT & SUMMARIZATION:** Your `<thought>` must clearly state: what's missing, the best tool/parameters for that specific missing piece, and (after an Observation) a concise summary of key findings relevant to your goal.
5.  **PLAN AHEAD (BUT ACT SINGULARLY):** Think a few steps ahead to choose the most effective current action, but always output only the immediate next single action.
6.  **ERROR HANDLING:** If a tool returns an error (e.g., "Hiba:", "Nem található"), analyze it. If the task cannot be completed, state this in the `Final Answer`.
7.  **TOOL INPUT JSON:** `<action_param_json>` content MUST be a valid JSON string dictionary. Example: `{{"command": "rg \\"(Error|Warn)\\" src -g \\"*.log\\""}}`.

**XML RESPONSE FORMAT (STRICTLY ONE `<llm_response>` block per turn):**
<llm_response>
    
    <action_tool>(IF USING A TOOL) Single tool from [{tool_names}].</action_tool>
    <action_param_json>(IF USING A TOOL) REQUIRED. Valid JSON string dictionary for the tool.</action_param_json>
</llm_response>

OR (IF YOU HAVE THE FINAL ANSWER)

<llm_response>
    
    <final_answer_text>The final answer to the original input question...</final_answer_text>
</llm_response>
**Ensure no extra text outside the main `<llm_response>` tag or between inner tags unless it's part of a tag's content.**

Begin!

Question: {input}

{agent_scratchpad}
"""

def create_prompt_template(
    final_active_tools_list: List[Tool], 
    final_strategic_guidance: str
) -> PromptTemplate:
    """
    Létrehozza és visszaadja a formázott PromptTemplate objektumot.

    Args:
        final_active_tools_list (List[Tool]): Az agent számára elérhető eszközök listája.
        final_strategic_guidance (str): A dinamikusan generált stratégiai útmutató.

    Returns:
        PromptTemplate: A LangChain által használható, feltöltött prompt sablon.
    """
    # Eszközleírások és neveik előkészítése a prompt számára
    formatted_tool_descriptions_for_prompt = "\n".join(
        [f"{tool.name}: {tool.description}" for tool in final_active_tools_list]
    )
    tool_names_string_for_prompt = ", ".join(
        [tool.name for tool in final_active_tools_list]
    )

    # A PromptTemplate objektum létrehozása a partial_variables kitöltésével
    prompt_obj = PromptTemplate(
        template=REACT_PROMPT_TEMPLATE_V2_3_STR,
        input_variables=["input", "agent_scratchpad"],
        partial_variables={
            "tools": formatted_tool_descriptions_for_prompt,
            "strategic_guidance": final_strategic_guidance,
            "tool_names": tool_names_string_for_prompt
        }
    )
    
    return prompt_obj