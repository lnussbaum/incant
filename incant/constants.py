from typing import Any, Dict

CLICK_STYLE: Dict[str, Dict[str, Any]] = {
    "success": {"fg": "green", "bold": True},
    "info": {"fg": "cyan"},
    "warning": {"fg": "yellow"},
    "error": {"fg": "red"},
    "header": {"fg": "magenta", "bold": True},
}
