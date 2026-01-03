# ⚠️ Status: Archived / Experimental

**Note:** This repository was a proof-of-concept for running local LLMs with LangChain. It is no longer actively maintained as the workflow has migrated to cloud-native solutions (GitHub Copilot / VS Code Agent Mode). It remains as a reference implementation for custom LangChain agents and RAG pipelines — use it as an example, not a production-ready solution. Use at your own risk: the code may be outdated, incomplete, or contain security issues.

# Project Analyzer LLM Agent

This project is an intelligent agent written in Python, built on the [LangChain](https://www.langchain.com/) framework, that can analyze the source code of software projects and answer questions about the code. The agent uses several tools (shell commands, `ctags`, Abstract Syntax Tree analysis) to extract information.

The project is highly modular to make maintainability, testability, and extensibility easy.

## Installation and setup

### 1. Clone the repository:
```bash
git clone <repository_url>
cd <repository_folder>
```

### 2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate  # Windows
```

### 3. Install required Python packages:
```bash
pip install -r requirements.txt
```
*The `requirements.txt` should include at least: `langchain`, `langchain-openai`, `python-dotenv`, `tiktoken`.*

### 4. Create a `.env` file:
Create a `.env` file in the project root to store configuration variables. Use `.env.example` as a template and **do not commit** your `.env` file to version control.
```env
# LLM server URL (e.g., LM Studio, Oobabooga)
LLM_API_URL_L="http://localhost:1234/v1"

# Model name provided by the LLM server
LLM_MODEL_NAME="phi-4-14b-q6_k"

# Your LLM API key (leave blank in this example; put your actual key in your local .env)
LLM_API_KEY=
```

**Security note:** Do not store production API keys or secrets in this repository. Add `LLM_API_KEY` to your local `.env` (or use a secret manager) and ensure `.env` is listed in `.gitignore`. If you use CI/CD, configure secrets in your CI provider rather than committing them to the repo.

### 5. Install optional external tools:
For improved shell tool performance, installing `ripgrep` (`rg`) is recommended.

## Running

The application can be started from the command line via `main.py`.

**Example run:**
```bash
python main.py \
  --project-root "/path/to/your/project/to/analyze" \
  --prompt "Find all Java files that use the 'X-Forwarded-For' header and list the methods where it appears." \
  --ctags-file "/path/to/your/project/to/analyze/.analyzer_tags" \
  --ast-file "/path/to/your/project/to/analyze/ast_input.jsonl" \
  --debug
```

### Command-line arguments:
- `--project-root`: (Required) Path to the project root to analyze.
- `--prompt`: (Required) The question to ask the agent.
- `--v1-context-file`: (Optional) A text file containing a previous high-level analysis summary.
- `--ctags-file`: (Optional) Path to a pre-generated ctags data file. If not provided, the program looks for `.analyzer_tags` under `--project-root`.
- `--ast-file`: (Optional) Path to a pre-generated AST data file (.jsonl). If not provided, the program looks for `ast_input.jsonl` or `ast_input.jsonl.gz`.
- `--debug`: (Optional) Enable more verbose logging to the console.

## Project structure

The project is organized into packages and modules according to logical responsibilities.

```
project_analyzer/
│
├── config/
│   ├── __init__.py
│   └── settings.py
│
├── core/
│   ├── __init__.py
│   ├── agent.py
│   └── llm_wrapper.py
│
├── tools/
│   ├── __init__.py
│   ├── ast_tools.py
│   ├── code_tools.py
│   ├── project_context_tools.py
│   └── system_tools.py
│
├── utils/
│   ├── __init__.py
│   ├── callbacks.py
│   ├── output_parser.py
│   └── logging_setup.py
│
├── prompts/
│   ├── __init__.py
│   └── react_template.py
│
└── main.py
```

## Component details

### main.py (Entry point) ▶️
This script is responsible for starting the application. It handles command-line arguments, sets up configuration and logging, and invokes the central `core.agent` module.

### config/settings.py ⚙️
This module holds the project's static configuration in a single place. It is easy to modify without changing application logic and supports overriding values from a `.env` file.

### core/ (The core) 🧠
This package contains the main application logic that orchestrates other components.

- **agent.py**: The main orchestration logic. This module is responsible for coordinating all other components (LLM, tools, prompts), building the agent, and controlling execution.
- **llm_wrapper.py**: Defines a custom `LLMWithOutputFixer` class that wraps the standard LangChain LLM. Its responsibility is to run every LLM response through a fixer/parser before returning it to the agent, ensuring structured and clean outputs.

### tools/ (Tools package) 🧰
All agent tools are implemented inside a dedicated Python package and organized by concern.

- **__init__.py**: Package entry point. It initializes data needed by tools (e.g., AST data) and dynamically builds the list of active tools via `get_all_tools()`.
- **system_tools.py**: Tools for system and file-system interactions (e.g., `execute_shell_command`, `identify_project_characteristics`).
- **code_tools.py**: Tools that operate directly on source code (e.g., `get_code_snippet` to read code snippets, `search_ctags_symbols` for ctags-based searches).
- **ast_tools.py**: Tools for querying preprocessed Abstract Syntax Tree (AST) data, extracting deep structural information from code.
- **project_context_tools.py**: Tools for high-level, preprocessed project context (e.g., `get_project_summary_v1`).

### utils/ (Utility package) 🛠️
Contains general-purpose functions and classes used across the project.

- **logging_setup.py**: Sets up centralized logging behavior for the application.
- **callbacks.py**: Custom LangChain CallbackHandlers for detailed logging of LLM interactions and tool calls and for console output.
- **output_parser.py**: One of the project's critical helper modules; it transforms occasionally malformed textual LLM outputs into a clean, structured format that the agent can consume.

### prompts/ (Prompt templates) 📝
Separating large and complex prompts from code improves clarity and maintainability.

- **react_template.py**: Contains the main ReAct prompt template and the logic that dynamically constructs the final prompt based on the available tools.

