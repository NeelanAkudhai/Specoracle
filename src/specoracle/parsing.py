import json
import re
from typing import Any, Optional

def extract_json(text: str) -> Optional[Any]:
    """Extract and parse the first balanced JSON array or object from text."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    for start_char, end_char in [('[', ']'), ('{', '}')]:
        start_idx = cleaned.find(start_char)
        if start_idx != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start_idx, len(cleaned)):
                c = cleaned[i]
                if c == '"' and not escape:
                    in_string = not in_string
                elif not in_string:
                    if c == start_char:
                        depth += 1
                    elif c == end_char:
                        depth -= 1
                        if depth == 0:
                            candidate = cleaned[start_idx : i + 1]
                            try:
                                return json.loads(candidate)
                            except Exception:
                                pass
                if c == '\\' and not escape:
                    escape = True
                else:
                    escape = False

    return None

def extract_code(text: str) -> str:
    """Extract Python code from markdown code fences or return raw text."""
    if not text:
        return ""
    pattern = r"```(?:python)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()
