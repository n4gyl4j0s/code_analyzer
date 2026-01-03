# System Requirements

## Hardware 🖥️

### Graphics card (GPU)
- **Minimum:** 12 GB VRAM
- **Recommended models:**
  - NVIDIA RTX 3060 (12GB)
  - RTX 3500 Ada
  - RTX 4060 Ti (16GB) or stronger
- **Note:** The example language model (8B Q4_K_M) uses roughly 6–7 GB VRAM; but allowing for OS and other processes, a 12 GB card gives more stable operation.

### Memory (RAM)
- **Minimum:** 32 GB

### Storage
- **Minimum:** 10 GB free space for models and the Python environment

## Software environment ⚙️

### Operating system
- **Windows:** 10/11 (WSL2 recommended)
- **Linux:** Recommended (e.g., Ubuntu 22.04)
- **macOS:** Apple Silicon (M1/M2) supported

### Python version
- **Python 3.10** or **Python 3.11**

### LLM server
A software that provides an OpenAI-compatible API endpoint is required to run local models.

**Recommended software:**
- LM Studio
- Oobabooga (Text Generation WebUI)
- NVIDIA NIM

### External tools
- **`git`** — for version control
- **`ripgrep` (`rg`)** — fast code search (optional but strongly recommended)

## Language model setup 🧠

### Recommended model
- **Model:** `Qwen3-8B-Instruct-GGUF`
- **Source:** `Qwen/Qwen3-8B-Instruct-GGUF`
- **Version:** `q4_K_M` quantized version (good balance between size and performance)

### Download
Models can be obtained via:
- The built-in search in LM Studio
- Direct download from Hugging Face or other model repositories

### Server configuration
Configure your LLM server with the following recommended settings:
- **GPU offload:** max (use GPU as much as possible)
- **API endpoint:** run a local server, e.g. `http://localhost:1234/v1`

## Project prerequisites 📋

The code analyzer may require some preprocessed files from the project being analyzed:

### Ctags file
- **File:** a `tags` file
- **Generation:** produce it using `ctags` against the project source tree

### AST file
- **File:** `ast_input.jsonl`
- **Content:** JSON lines representing Abstract Syntax Trees (ASTs) of the source code
