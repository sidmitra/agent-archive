from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
from ..models import Session


class BaseParser(ABC):
    @abstractmethod
    def discover(self) -> List[Path]:
        """Return all session log file paths for this agent."""

    @abstractmethod
    def parse(self, filepath: Path) -> List[Session]:
        """Parse a single log file into Session objects."""
