from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class Space:
    name: str
    url: str


@dataclass
class Change:
    space_name: str
    change_type: str  # added|modified|removed
    item_id: str
    title: str
    url: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
