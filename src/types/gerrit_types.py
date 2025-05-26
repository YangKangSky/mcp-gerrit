# Gerrit相关类型定义

from dataclasses import dataclass
from typing import Optional

@dataclass
class GerritContext:
    host: str
    user: str
    http_password: Optional[str] = None 