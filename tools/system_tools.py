# tools/system_tools.py
import os
import logging
import json
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import fnmatch
from collections import Counter

# Belső importok a projekt struktúrából
from utils.output_parser import clean_llm_action_input
from config.settings import (
    ALLOWED_SHELL_COMMANDS, 
    MAX_SHELL_OUTPUT_LENGTH, 
    SHELL_TIMEOUT_SECONDS
)

# Logger példányosítása a modulhoz
logger = logging.getLogger(__name__)

# Megjegyzés: Ez a modul a 'tools' csomag globális változóitól függ,
# amelyeket a tools/__init__.py-ban lévő `initialize_tool_data` állít be.
# Különösen a `_project_root_global` változótól.
_project_root_global: Optional[str] = None


# --- Projekt Információ Azonosító Eszköz ---

def _internal_identify_project_info_logic(start_path_abs: str) -> Dict[str, Any]:
    """
    Belső logikai függvény a projekt információk azonosításához.
    Változatlanul átvéve a v2_tools.py-ból.
    """
    project_info: Dict[str, Any] = {
        "project_path_analyzed": start_path_abs,
        "language": None, "frameworks": [], "build_tool": None,
        "source_dirs": [], "test_dirs": [], "config_files_found": [],
        "common_files_found": [], "top_file_extensions": [],
        "confidence": "Undetermined"
    }
    indicators_found = 0
    lang_indicators = Counter()
    ext_counts = Counter()
    framework_indicators = Counter()

    build_files_map = {
        "pom.xml": {"lang": "Java", "tool": "Maven"},
        "build.gradle": {"lang": "Java/Kotlin", "tool": "Gradle"},
        "build.gradle.kts": {"lang": "Kotlin", "tool": "Gradle"},
        "package.json": {"lang": "JavaScript/TypeScript", "tool": "npm/yarn"},
        "composer.json": {"lang": "PHP", "tool": "Composer"},
        "requirements.txt": {"lang": "Python", "tool": "pip"},
        "setup.py": {"lang": "Python", "tool": "setuptools/pip"},
        "Pipfile": {"lang": "Python", "tool": "pipenv"},
        "pyproject.toml": {"lang": "Python", "tool": "Poetry/pip"},
        "go.mod": {"lang": "Go", "tool": "Go Modules"},
        "Cargo.toml": {"lang": "Rust", "tool": "Cargo"},
        re.compile(r".*\.csproj$"): {"lang": "C#", "tool": ".NET CLI/MSBuild"},
        re.compile(r".*\.sln$"): {"lang": ".NET Solution", "tool": ".NET CLI/MSBuild"},
    }
    framework_files_map = {
        "application.properties": "Spring Boot", "application.yml": "Spring Boot",
        "settings.py": "Django", "manage.py": "Django", "wsgi.py": "Python Web (Django/Flask)",
        "artisan": "Laravel", "server.js": "Node.js (Express/Other)", "app.js": "Node.js",
        "next.config.js": "Next.js", "angular.json": "Angular", "vue.config.js": "Vue.js",
        "WEB-INF": "Java EE/Servlet", "node_modules": "Node.js Ecosystem",
        "docker-compose.yml": "Docker", "Dockerfile": "Docker", "Jenkinsfile": "Jenkins",
        "tsconfig.json": {"lang_refine": "TypeScript", "framework_note": "TypeScript Project"},
    }
    common_source_dirs_patterns = [r"^src$", r"^app$", r"^lib$", r"^\w+Service$"]
    common_test_dirs_patterns = [r"^test$", r"^tests$", r"^spec$"]

    scan_depth = 2
    start_level = start_path_abs.count(os.sep)

    try:
        for dirpath, dirnames, filenames in os.walk(start_path_abs, topdown=True):
            current_level = os.path.abspath(dirpath).count(os.sep) - start_level
            relative_dirpath = os.path.relpath(dirpath, start_path_abs)
            if relative_dirpath == ".": relative_dirpath = ""

            for fname in filenames:
                project_info["common_files_found"].append(os.path.join(relative_dirpath, fname).replace("\\", "/"))
                for pattern, info in build_files_map.items():
                    if (isinstance(pattern, str) and fname == pattern) or \
                       (not isinstance(pattern, str) and hasattr(pattern, "match") and pattern.match(fname)):
                        project_info["build_tool"] = info["tool"]
                        lang_indicators[info["lang"]] += 5
                        project_info["config_files_found"].append(fname)
                        if info["lang"] != ".NET Solution": project_info["language"] = info["lang"]
                for pattern, fw_info in framework_files_map.items():
                    if (isinstance(pattern, str) and fname == pattern) or \
                       (not isinstance(pattern, str) and hasattr(pattern, "match") and pattern.match(fname)):
                        framework_name = fw_info if isinstance(fw_info, str) else fw_info.get("framework_note", "Unknown")
                        if framework_name not in project_info["frameworks"]: project_info["frameworks"].append(framework_name)
                        if fname not in project_info["config_files_found"]: project_info["config_files_found"].append(fname)
                        if isinstance(fw_info, dict) and "lang_refine" in fw_info:
                            project_info["language"] = fw_info["lang_refine"]
                ext = os.path.splitext(fname)[1].lower().strip('.')
                if ext: ext_counts[ext] += 1
            for dname in list(dirnames):
                full_d_path = os.path.join(relative_dirpath, dname).replace("\\", "/")
                for pattern_str in common_source_dirs_patterns:
                    if re.fullmatch(pattern_str, dname, re.IGNORECASE):
                        if full_d_path not in project_info["source_dirs"]: project_info["source_dirs"].append(full_d_path)
                for pattern_str in common_test_dirs_patterns:
                    if re.fullmatch(pattern_str, dname, re.IGNORECASE):
                        if full_d_path not in project_info["test_dirs"]: project_info["test_dirs"].append(full_d_path)
            if current_level >= scan_depth - 1:
                dirnames[:] = []
    except Exception as e:
        project_info["error"] = f"Hiba a projekt információk azonosítása közben: {str(e)}"

    if project_info["language"] is None and ext_counts:
        ext_to_lang = {"java": "Java", "kt": "Kotlin", "py": "Python", "js": "JavaScript", "ts": "TypeScript", "go": "Go", "php": "PHP", "cs": "C#"}
        relevant_ext_counts = Counter({ext: count for ext, count in ext_counts.items() if ext in ext_to_lang})
        if relevant_ext_counts:
            top_ext, _ = relevant_ext_counts.most_common(1)[0]
            project_info["language"] = ext_to_lang[top_ext]
    
    if framework_indicators:
        project_info["dominant_framework"] = framework_indicators.most_common(1)[0][0]

    project_info["top_file_extensions"] = [{"extension": ext, "count": count} for ext, count in ext_counts.most_common(3)]
    project_info["all_config_files_found"] = list(set(project_info["config_files_found"]))
    project_info.pop("config_files_found", None)
    project_info["common_files_found_count"] = len(project_info.pop("common_files_found", []))

    if project_info["build_tool"]: project_info["confidence"] = "High"
    elif project_info["language"] and project_info["source_dirs"]: project_info["confidence"] = "Medium"
    elif framework_indicators: project_info["confidence"] = "Low"
    
    return project_info


def tool_wrapper_identify_project_info(action_input_str: str) -> str:
    """LangChain Eszköz: Azonosítja a projekt jellemzőit a fájlrendszer alapján."""
    logger.info(f"Eszköz HÍVVA: identify_project_info, input: {action_input_str}")
    action_input_str = clean_llm_action_input(action_input_str)
    path_to_analyze = _project_root_global

    try:
        args = json.loads(action_input_str)
        path_arg = args.get("path")
        if path_arg and isinstance(path_arg, str):
            path_arg_clean = path_arg.strip().strip("'\"")
            if path_arg_clean:
                if Path(path_arg_clean).is_absolute(): path_to_analyze = str(Path(path_arg_clean).resolve())
                elif _project_root_global: path_to_analyze = str((Path(_project_root_global) / path_arg_clean).resolve())
                else: path_to_analyze = str(Path(path_arg_clean).resolve())
        
        if not path_to_analyze:
            return "Hiba: Nem sikerült meghatározni az elemzendő útvonalat."
        if not os.path.isdir(path_to_analyze):
            return f"Hiba: Az útvonal nem létező könyvtár: '{path_to_analyze}'"

        logger.info(f"Projekt információk azonosítása itt: {path_to_analyze}")
        project_details = _internal_identify_project_info_logic(path_to_analyze)
        return json.dumps(project_details, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return "Hiba: Az eszköz ('identify_project_info') bemenete nem érvényes JSON."
    except Exception as e:
        logger.error(f"Hiba az 'identify_project_info' eszközben: {e}", exc_info=True)
        return f"Hiba az 'identify_project_info' eszköz futása közben: {str(e)}"


# --- Shell Parancs Futtató Eszköz ---

def tool_wrapper_execute_shell_command(action_input_str: str) -> str:
    """LangChain Eszköz: Végrehajt egy shell parancsot a projekt gyökérkönyvtárában."""
    logger.info(f"Eszköz HÍVVA: execute_shell_command, input: {action_input_str}")
    command_to_run = None
    
    action_input_str = clean_llm_action_input(action_input_str)
    logger.debug(f"Shell eszköz: A tisztítás utáni input: '{action_input_str}'")

    try:
        args = json.loads(action_input_str)
        command_to_run = args.get("command")
        if not command_to_run or not isinstance(command_to_run, str):
            return "HIBA: Érvénytelen vagy hiányzó 'command' kulcs a JSON inputban."

        command_parts = command_to_run.split()
        if not command_parts: return "HIBA: Üres parancsot kapott."

        base_command = os.path.basename(command_parts[0])
        if base_command not in ALLOWED_SHELL_COMMANDS:
            logger.warning(f"Tiltott shell parancs kísérlete: {command_to_run}")
            return f"HIBA: A '{base_command}' parancs nem engedélyezett."

        current_working_directory = _project_root_global if _project_root_global else str(Path.cwd())
        logger.info(f"Shell parancs futtatása: [{command_to_run}] a '{current_working_directory}' könyvtárban.")

        process = subprocess.run(
            command_to_run, shell=True, capture_output=True, text=True,
            encoding='utf-8', errors='ignore', timeout=SHELL_TIMEOUT_SECONDS,
            cwd=current_working_directory, check=False
        )

        stdout, stderr, return_code = process.stdout, process.stderr, process.returncode
        output_parts = []
        
        # Specifikus hibakódok kezelése
        if return_code == 2:
            # Fájl/könyvtár nem található (pl. rg, find, ls esetén)
            if "No such file or directory" in stderr or "cannot access" in stderr:
                output_parts.append("❌ FÁJL/KÖNYVTÁR NEM TALÁLHATÓ:")
                output_parts.append(f"A megadott útvonal nem létezik: {stderr.strip()}")
                output_parts.append("\n💡 JAVASLAT: Ellenőrizd az útvonalat vagy használd a 'find' vagy 'ls' parancsot a helyes útvonal megtalálásához.")
                output_parts.append("Például: 'find . -name \"*.java\" -type f' vagy 'ls -la services/'")
                return "\n".join(output_parts)
        
        elif return_code == 1:
            # Általában "nincs találat" (pl. rg, grep esetén)
            if not stdout and not stderr:
                output_parts.append("❌ NINCS TALÁLAT:")
                output_parts.append("A keresési feltételeknek megfelelő eredmény nem található.")
                output_parts.append("\n💡 JAVASLAT: Próbálj más keresési mintát vagy ellenőrizd, hogy a célkönyvtár létezik-e.")
                return "\n".join(output_parts)
            elif "No such file or directory" in stderr:
                output_parts.append("❌ FÁJL/KÖNYVTÁR NEM TALÁLHATÓ:")
                output_parts.append(f"A keresés célpontja nem létezik: {stderr.strip()}")
                output_parts.append("\n💡 JAVASLAT: Ellenőrizd az útvonalat vagy használd szélesebb keresési mintát.")
                return "\n".join(output_parts)
                
        if stdout and stdout.strip():
            output_parts.append("✅ KIMENET:")
            if len(stdout) > MAX_SHELL_OUTPUT_LENGTH:
                output_parts.append(f"--- (csonkolva {MAX_SHELL_OUTPUT_LENGTH} karakternél) ---")
                output_parts.append(stdout[:MAX_SHELL_OUTPUT_LENGTH])
                output_parts.append("[...KIMENET CSONKOLVA...]")
            else:
                output_parts.append("---")
                output_parts.append(stdout.strip())
                output_parts.append("---")
        
        if stderr and stderr.strip():
            output_parts.append("\n⚠️ HIBAKIMENET:")
            output_parts.append("---")
            output_parts.append(stderr.strip())
            output_parts.append("---")

        if not stdout.strip() and not stderr.strip():
            if return_code == 0:
                 output_parts.append("✅ A parancs sikeresen lefutott, de nem adott vissza kimenetet.")
            else:
                 output_parts.append(f"❌ A parancs hibával fejeződött be (kód: {return_code}), de nem adott hibaüzenetet.")

        final_output = "\n".join(output_parts).strip()
        logger.info(f"Shell eszköz válasz (előnézet): {final_output[:500]}...")
        return final_output

    except json.JSONDecodeError:
        return "HIBA: Az eszköz bemenete nem érvényes JSON formátum: {\"command\": \"parancs_itt\"}"
    except subprocess.TimeoutExpired:
        logger.warning(f"Shell parancs időtúllépés: {command_to_run}")
        return f"❌ IDŐTÚLLÉPÉS: A parancs futtatása {SHELL_TIMEOUT_SECONDS} másodperc után megszakadt."
    except Exception as e:
        logger.error(f"Váratlan hiba a shell eszközben: {e}", exc_info=True)
        return f"❌ VÁRATLAN HIBA: {str(e)}"