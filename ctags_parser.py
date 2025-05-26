# ctags_parser.py

import logging
from typing import Dict, List, Optional, Any

# Modul szintű logger beállítása az újrafelhasználhatóság érdekében.
# A hívó alkalmazás (pl. projekt_elemzo.py) fogja konfigurálni a root loggert.
logger = logging.getLogger(__name__)

def _parse_ctags_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single line from a ctags output file.

    A ctags line typically has the format:
    tagName<TAB>tagFile<TAB>tagAddress[;"<TAB>extensionFields...]

    The `tagAddress` can be a line number or a search pattern (e.g., /pattern/).
    Extension fields are key:value pairs, e.g., "kind:c", "line:123".
    This parser is specifically tailored for ctags output generated with
    --fields containing at least n, e, K, z (line, end_line, kind, signature).

    Args:
        line: A single line read from the ctags file.

    Returns:
        A dictionary containing the parsed tag information if successful,
        otherwise None (e.g., for header lines or parse errors).
        The dictionary structure includes:
        {
            "name": str,                  # Tag name
            "file": str,                  # File path where the tag is defined
            "address_raw": str,           # The raw tag address (content of the 3rd field, ;" removed)
            "pattern": Optional[str],     # Cleaned search pattern (if address is a pattern)
            "line": Optional[int],        # Start line number of the tag definition
            "end_line": Optional[int],    # End line number of the tag definition (from 'e' field)
            "kind": Optional[str],        # Kind of tag (from 'K' field, e.g., "class", "method")
            "signature": Optional[str],   # Signature (from 'z' field, e.g., method parameters)
            "class_scope": Optional[str], # Containing class/scope (from 'class' extension field)
            "enum_scope": Optional[str],  # Containing enum (from 'enum' extension field)
            "other_fields": Dict[str, Any] # Any other extension fields found
        }
    """
    line = line.strip()
    if not line or line.startswith("!_TAG_"):
        return None

    parts = line.split('\t')
    if len(parts) < 3:
        logger.warning(f"Skipping malformed ctags line (less than 3 tab-separated parts): \"{line}\"")
        return None

    tag_name = parts[0]
    file_path = parts[1]
    # The third field is the Ex command (address), potentially ending with ;"
    # This ;" is part of the address field itself, not a separator for extension fields
    # (extension fields are separated by tabs from parts[3] onwards).
    raw_address_field_content = parts[2]
    
    address_part_for_parsing = raw_address_field_content
    if raw_address_field_content.endswith(';"'):
        address_part_for_parsing = raw_address_field_content[:-2]

    tag_info: Dict[str, Any] = {
        "name": tag_name,
        "file": file_path,
        "address_raw": address_part_for_parsing,
        "pattern": None,
        "line": None,
        "end_line": None,
        "kind": None,
        "signature": None,
        "class_scope": None,
        "enum_scope": None,
        "other_fields": {}
    }

    # Process extension fields (from parts[3] onwards)
    for ext_field_str in parts[3:]:
        key_original, value_str = "", ""
        is_flag_field = False

        if ':' in ext_field_str:
            key_original, value_str = ext_field_str.split(':', 1)
            key_original = key_original.strip()
            value_str = value_str.strip()
        else:
            key_original = ext_field_str.strip()
            is_flag_field = True
            value_str = "true" # Represent flags as boolean True after parsing if needed

        # Handle known/expected fields from --fields=+neKz and examples
        if key_original == 'line' or key_original == 'n':
            try:
                tag_info["line"] = int(value_str)
            except ValueError:
                logger.warning(f"Could not parse 'line' number \"{value_str}\" for tag \"{tag_name}\" in \"{file_path}\".")
        elif key_original == 'end' or key_original == 'e':
            try:
                tag_info["end_line"] = int(value_str)
            except ValueError:
                logger.warning(f"Could not parse 'end_line' number \"{value_str}\" for tag \"{tag_name}\" in \"{file_path}\".")
        elif key_original == 'kind' or key_original == 'K':
            tag_info["kind"] = value_str
        elif key_original == 'signature' or key_original == 'z':
            tag_info["signature"] = value_str
        elif key_original == 'class': # As seen in your example
            tag_info["class_scope"] = value_str
        elif key_original == 'enum': # As seen in your example
            tag_info["enum_scope"] = value_str
        else:
            # Store any other unrecognized/additional extension fields in other_fields
            if is_flag_field:
                tag_info["other_fields"][key_original] = True
            else:
                tag_info["other_fields"][key_original] = value_str
    
    # Refine 'pattern' and 'line' based on address_part_for_parsing,
    # taking into account information potentially already set from extension fields.

    # 1. If address is an explicit regex pattern (e.g., /^pattern$/)
    if address_part_for_parsing.startswith('/') and address_part_for_parsing.endswith('/'):
        if tag_info["pattern"] is None: # Only set if not already set by an explicit "pattern:" extension
            tag_info["pattern"] = address_part_for_parsing[1:-1] # Store without leading/trailing /
    
    # 2. If 'line' was NOT set by an extension field, try to parse address_part_for_parsing as a line number.
    elif tag_info["line"] is None:
        try:
            tag_info["line"] = int(address_part_for_parsing)
        except ValueError:
            # Not a number, and not a /pattern/ (already handled).
            # So, if 'pattern' is still None, treat address_part_for_parsing as a non-regex pattern.
            if tag_info["pattern"] is None:
                tag_info["pattern"] = address_part_for_parsing
    
    # 3. If 'line' WAS set by an extension field, but address_part_for_parsing is different 
    #    AND not an explicit regex, then address_part_for_parsing is likely a (non-regex) pattern.
    elif tag_info["line"] is not None and str(tag_info["line"]) != address_part_for_parsing \
            and not (address_part_for_parsing.startswith('/') and address_part_for_parsing.endswith('/')):
        if tag_info["pattern"] is None: # Only set if pattern not already defined
            tag_info["pattern"] = address_part_for_parsing

    # Final fallback: if line is still None but pattern contains only digits, it's likely a line number.
    if tag_info["line"] is None and tag_info["pattern"] is not None:
        if tag_info["pattern"].isdigit():
            try:
                # This case handles if address_part_for_parsing was "123" but line: ext field was missing
                tag_info["line"] = int(tag_info["pattern"])
                tag_info["pattern"] = None # It was a line number, not a pattern
            except ValueError: # Should not happen if isdigit() is true
                pass
                
    return tag_info

def parse_ctags_file(ctags_file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parses a ctags file and organizes the tags by the file they appear in.

    Args:
        ctags_file_path: The absolute or relative path to the ctags file.

    Returns:
        A dictionary where:
            - Keys are file paths (as they appear in the ctags file, usually relative).
            - Values are lists of tag dictionaries (parsed by _parse_ctags_line)
              found in that file.
        Returns an empty dictionary if the file is not found or an error occurs during parsing.
    """
    tags_by_file: Dict[str, List[Dict[str, Any]]] = {}
    try:
        with open(ctags_file_path, 'r', encoding='utf-8', errors='ignore') as f_ctags:
            for line_content in f_ctags:
                tag = _parse_ctags_line(line_content)
                if tag:
                    file_key = tag["file"]
                    if file_key not in tags_by_file:
                        tags_by_file[file_key] = []
                    tags_by_file[file_key].append(tag)
        
        if tags_by_file:
            total_tags = sum(len(tags) for tags in tags_by_file.values())
            logger.info(f"Successfully parsed {total_tags} tags from {len(tags_by_file)} files in '{ctags_file_path}'.")
        else:
            # File might be empty or contain no valid tags
            logger.info(f"No valid tags found or parsed from '{ctags_file_path}'.")

    except FileNotFoundError:
        logger.error(f"Ctags file not found: {ctags_file_path}")
        return {} # Return empty dict on file not found
    except Exception as e:
        logger.error(f"An unexpected error occurred while parsing ctags file {ctags_file_path}: {e}", exc_info=True)
        return {} # Return empty dict on other errors
        
    return tags_by_file

if __name__ == '__main__':
    # Basic test and usage example
    # Configure logging for standalone testing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create a dummy ctags file for testing
    dummy_ctags_content = """!_TAG_FILE_FORMAT	2	/extended format; --format=1 will not append ;" to lines/
!_TAG_FILE_SORTED	1	/0=unsorted, 1=sorted, 2=foldcase/
!_TAG_PROGRAM_AUTHOR	Universal Ctags Team	//
!_TAG_PROGRAM_NAME	Universal Ctags	/Derived from Exuberant Ctags/
!_TAG_PROGRAM_URL	https://ctags.io/	/official website/
!_TAG_PROGRAM_VERSION	6.0.0	/cb3344a4/
ACCEPTED	src/main/java/hu/idomsoft/pidprovider/enums/PidStatus.java	/^	 ACCEPTED("credential_accepted"),$/;"	kind:enumConstant	line:8	enum:PidStatus	file:	end:8
ACTIVE	src/main/java/hu/idomsoft/pidprovider/enums/szlkk/SZLKKUserState.java	/^	 ACTIVE("AKTIV"),$/;"	kind:enumConstant	line:12	enum:SZLKKUserState	file:	end:12
ALGORITHM	src/main/java/hu/idomsoft/pidprovider/utils/JWTUtil.java	/^		 public static final String ALGORITHM = "alg";$/;"	kind:field	line:40	class:JWTUtil.Claims	end:40
MyClass	src/main/java/com/example/MyClass.java	/^public class MyClass {$/;"	kind:class	line:10	end:50
myMethod	src/main/java/com/example/MyClass.java	/myMethod(int param1, String param2)/;"	kind:method	line:15	signature:(int param1, String param2)	class:MyClass	access:public	end:25
myVariable	src/main/java/com/example/MyClass.java	20;"	kind:variable	line:20	class:MyClass	type:int
anotherFunc	another_module.py	/^def anotherFunc():$/;"	kind:function	line:5	end:10
"""
    test_ctags_file = "dummy_tags.txt"
    with open(test_ctags_file, "w", encoding="utf-8") as f:
        f.write(dummy_ctags_content)

    logger.info(f"Attempting to parse dummy ctags file: {test_ctags_file}")
    parsed_data = parse_ctags_file(test_ctags_file)

    if parsed_data:
        logger.info("Parsing successful. Parsed data overview:")
        for file_path, tags_in_file in parsed_data.items():
            logger.info(f"  File: {file_path} ({len(tags_in_file)} tags)")
            for i, tag_item in enumerate(tags_in_file):
                if i < 2: # Print details for the first few tags per file
                    logger.debug(f"    Tag: {tag_item}")
    else:
        logger.error("Parsing failed or no data returned.")

    # Example of how to access specific tag info
    if "src/main/java/com/example/MyClass.java" in parsed_data:
        my_class_tags = parsed_data["src/main/java/com/example/MyClass.java"]
        for tag in my_class_tags:
            if tag["name"] == "myMethod":
                logger.info(f"Found myMethod: Line={tag.get('line')}, Kind={tag.get('kind')}, Signature={tag.get('signature')}, ClassScope={tag.get('class_scope')}")
                logger.info(f"Full details for myMethod: {tag}")


    # Clean up dummy file (optional)
    # import os
    # os.remove(test_ctags_file)