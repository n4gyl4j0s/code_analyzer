# code_retriever.py

import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

def get_code_snippet(
    file_path_str: str,
    start_line: int,
    end_line: Optional[int] = None,
    project_root_str: Optional[str] = None
) -> Optional[str]:
    """
    Retrieves a snippet of code from a file between specified line numbers.

    Line numbers are 1-based (as commonly used in editors and ctags).

    Args:
        file_path_str: Path to the source file (can be relative or absolute).
                       If relative, project_root_str must be provided.
        start_line: The 1-based starting line number of the snippet.
        end_line: The 1-based ending line number of the snippet (inclusive).
                  If None, only the start_line is retrieved. If equal to start_line,
                  only that single line is retrieved.
        project_root_str: Absolute path to the project's root directory.
                          Used to resolve relative file_path_str.

    Returns:
        The code snippet as a string, or None if an error occurs
        (e.g., file not found, invalid line numbers).
    """
    if start_line < 1:
        logger.error(f"Invalid start_line: {start_line}. Line numbers must be 1-based.")
        return None
    if end_line is not None and end_line < start_line:
        logger.error(f"Invalid end_line: {end_line}. Must be greater than or equal to start_line: {start_line}.")
        return None

    p_file_path = Path(file_path_str)
    absolute_file_path: Path

    if p_file_path.is_absolute():
        absolute_file_path = p_file_path
    elif project_root_str:
        p_project_root = Path(project_root_str)
        if not p_project_root.is_dir():
            logger.error(f"Project root is not a valid directory: {project_root_str}")
            return None
        absolute_file_path = p_project_root / p_file_path
    else:
        logger.error(f"File path '{file_path_str}' is relative, but project_root_str was not provided.")
        return None

    if not absolute_file_path.is_file():
        logger.warning(f"Source file not found at: {absolute_file_path}")
        return None

    try:
        with open(absolute_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Error reading file {absolute_file_path}: {e}")
        return None

    # Adjust line numbers to 0-based index for list access
    # start_line is 1-based, so list index is start_line - 1
    # end_line is 1-based inclusive, so list slice upper bound is end_line
    
    actual_start_index = start_line - 1
    
    # Determine the actual end index for slicing
    # If end_line is None, we might just take one line or a fixed number of lines.
    # For now, if end_line is None, let's just take the start_line.
    # If end_line is provided, it's inclusive, so slice up to end_line.
    actual_end_index_exclusive: int
    if end_line is None:
        actual_end_index_exclusive = actual_start_index + 1
    else:
        actual_end_index_exclusive = end_line # Python slice [a:b] goes up to b-1

    if actual_start_index < 0 or actual_start_index >= len(lines):
        logger.warning(
            f"Start line {start_line} is out of bounds for file {absolute_file_path} "
            f"(0 to {len(lines)-1} lines available)."
        )
        return None
    
    # Ensure end_index for slicing is within bounds
    actual_end_index_exclusive = min(actual_end_index_exclusive, len(lines))
    
    if actual_start_index >= actual_end_index_exclusive and end_line is not None : # Only warn if end_line was specified and implies empty/invalid range
         logger.warning(
            f"Calculated empty or invalid line range ({start_line}-{end_line}) "
            f"for file {absolute_file_path} after bounds adjustment."
        )
         return "" # Return empty string for valid but empty range

    snippet_lines: List[str] = lines[actual_start_index:actual_end_index_exclusive]
    
    return "".join(snippet_lines)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    test_proj_root = Path("dummy_project_root")
    test_proj_root.mkdir(exist_ok=True)
    
    dummy_file_content1 = """Line 1: This is the first line.
Line 2: This is the second line.
Line 3: Middle line of the snippet.
Line 4: Another middle line.
Line 5: This is the fifth line.
Line 6: This is outside the snippet.
"""
    # dummy_file1_path most már abszolút útvonal lesz a dummy könyvtáron belül
    dummy_file1_path_abs = (test_proj_root / "test_file.txt").resolve()
    with open(dummy_file1_path_abs, "w", encoding="utf-8") as f:
        f.write(dummy_file_content1)

    dummy_file_content2 = "Single line file.\n"
    dummy_file2_path_abs = (test_proj_root / "single_line.txt").resolve()
    with open(dummy_file2_path_abs, "w", encoding="utf-8") as f:
        f.write(dummy_file_content2)
    
    logger.info(f"Dummy project root: {test_proj_root.resolve()}")
    logger.info(f"Dummy file 1: {dummy_file1_path_abs}")
    logger.info(f"Dummy file 2: {dummy_file2_path_abs}")

    # --- Test cases ---
    logger.info("\n--- Testing get_code_snippet ---")
    
    # A get_code_snippet-nek átadott fájlnév (első argumentum)
    # a project_root_str-hez képest relatív.
    file1_relative_to_proj_root = dummy_file1_path_abs.name # "test_file.txt"
    file2_relative_to_proj_root = dummy_file2_path_abs.name # "single_line.txt"


    # Test 1: Valid range
    snippet1 = get_code_snippet(file1_relative_to_proj_root, 2, 4, project_root_str=str(test_proj_root.resolve()))
    logger.info(f"Test 1 (Lines 2-4 from {file1_relative_to_proj_root}):\n>>>\n{snippet1}<<<")
    expected1 = "Line 2: This is the second line.\nLine 3: Middle line of the snippet.\nLine 4: Another middle line.\n"
    assert snippet1 == expected1, f"Test 1 FAILED. Expected:\n{expected1}\nGot:\n{snippet1}"

    # Test 2: Single line (end_line specified)
    snippet2 = get_code_snippet(file1_relative_to_proj_root, 3, 3, project_root_str=str(test_proj_root.resolve()))
    logger.info(f"Test 2 (Line 3 from {file1_relative_to_proj_root}):\n>>>\n{snippet2}<<<")
    expected2 = "Line 3: Middle line of the snippet.\n"
    assert snippet2 == expected2, f"Test 2 FAILED. Expected:\n{expected2}\nGot:\n{snippet2}"

    # Test 3: Single line (end_line is None)
    snippet3 = get_code_snippet(file1_relative_to_proj_root, 1, None, project_root_str=str(test_proj_root.resolve()))
    logger.info(f"Test 3 (Line 1 from {file1_relative_to_proj_root}, end_line=None):\n>>>\n{snippet3}<<<")
    expected3 = "Line 1: This is the first line.\n"
    assert snippet3 == expected3, f"Test 3 FAILED. Expected:\n{expected3}\nGot:\n{snippet3}"
    
    # Test 4: To end of file
    snippet4 = get_code_snippet(file1_relative_to_proj_root, 5, 100, project_root_str=str(test_proj_root.resolve())) # end_line too high
    logger.info(f"Test 4 (Lines 5-end from {file1_relative_to_proj_root}):\n>>>\n{snippet4}<<<")
    expected4 = "Line 5: This is the fifth line.\nLine 6: This is outside the snippet.\n"
    assert snippet4 == expected4, f"Test 4 FAILED. Expected:\n{expected4}\nGot:\n{snippet4}"

    # Test 5: Start line out of bounds (too high)
    snippet5 = get_code_snippet(file1_relative_to_proj_root, 10, 12, project_root_str=str(test_proj_root.resolve()))
    logger.info(f"Test 5 (Start line too high): {snippet5}")
    assert snippet5 is None, "Test 5 FAILED. Expected None."

    # Test 6: Start line out of bounds (0 or negative)
    snippet6 = get_code_snippet(file1_relative_to_proj_root, 0, 2, project_root_str=str(test_proj_root.resolve()))
    logger.info(f"Test 6 (Start line 0): {snippet6}")
    assert snippet6 is None, "Test 6 FAILED. Expected None."

    # Test 7: end_line < start_line
    snippet7 = get_code_snippet(file1_relative_to_proj_root, 3, 1, project_root_str=str(test_proj_root.resolve()))
    logger.info(f"Test 7 (end_line < start_line): {snippet7}")
    assert snippet7 is None, "Test 7 FAILED. Expected None."
    
    # Test 8: File not found (using a non-existent relative path)
    snippet8 = get_code_snippet("non_existent_file.txt", 1, 1, project_root_str=str(test_proj_root.resolve()))
    logger.info(f"Test 8 (File not found): {snippet8}")
    assert snippet8 is None, "Test 8 FAILED. Expected None."

    # Test 9: Single line file, get line 1
    snippet9 = get_code_snippet(file2_relative_to_proj_root, 1, 1, project_root_str=str(test_proj_root.resolve()))
    logger.info(f"Test 9 (Single line from {file2_relative_to_proj_root}):\n>>>\n{snippet9}<<<")
    expected9 = "Single line file.\n"
    assert snippet9 == expected9, f"Test 9 FAILED. Expected:\n{expected9}\nGot:\n{snippet9}"

    # Test 10: Relative path without project_root - this tests if the file happens to be in CWD
    # To make this test robust for the error case (project_root needed for non-CWD relative paths),
    # we ensure the path is unlikely to be in CWD unless CWD is dummy_project_root.
    # We'll use a path that is relative to dummy_project_root.
    # If CWD is dummy_project_root, then file1_relative_to_proj_root ("test_file.txt") would be found.
    # If CWD is NOT dummy_project_root, then "test_file.txt" alone will likely not be found without project_root.
    if Path.cwd().resolve() == test_proj_root.resolve():
        logger.info(f"Skipping Test 10 (CWD is dummy_project_root, relative path '{file1_relative_to_proj_root}' would be found).")
        # Optionally, test successful case:
        # snippet10_success = get_code_snippet(file1_relative_to_proj_root, 1, 1, project_root_str=None)
        # assert snippet10_success is not None, "Test 10 (CWD is dummy_project_root) FAILED for finding file."
    else:
        snippet10_fail = get_code_snippet(file1_relative_to_proj_root, 1, 1, project_root_str=None)
        logger.info(f"Test 10 (Relative path '{file1_relative_to_proj_root}', no project_root, CWD is not dummy_project_root): {snippet10_fail}")
        assert snippet10_fail is None, f"Test 10 FAILED. Expected None for relative path '{file1_relative_to_proj_root}' without project_root when CWD is not the project_root."


    # Test 11: Absolute path (should ignore project_root if provided)
    snippet11 = get_code_snippet(str(dummy_file1_path_abs), 2, 3, project_root_str="should_be_ignored_due_to_abs_path")
    logger.info(f"Test 11 (Absolute path '{str(dummy_file1_path_abs)}'):\n>>>\n{snippet11}<<<")
    expected11 = "Line 2: This is the second line.\nLine 3: Middle line of the snippet.\n"
    assert snippet11 == expected11, f"Test 11 FAILED. Expected:\n{expected11}\nGot:\n{snippet11}"

    logger.info("\n--- All CodeRetriever tests finished (if no asserts failed) ---")

    # Clean up dummy project (optional)
    # import shutil
    # shutil.rmtree(test_proj_root)