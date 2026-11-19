"""Prompt files (prompts/README.md conventions).

- Header lines start with '#'. The system message follows a line that is exactly '### SYSTEM',
  the user message a line that is exactly '### USER'. Split on those whole lines only.
- Placeholders are {{name}}. '<<<' and '>>>' are removed from every filled value first (FR-17),
  so ticket text cannot forge the delimiters. After filling, no '{{' may remain.
- prompt_version for the decision log comes from the first header line: '# PR-02 classify  v1.0'
  -> 'PR-02 v1.0'.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path("prompts")
_SYS = re.compile(r"^### SYSTEM[ \t]*$", re.MULTILINE)
_USR = re.compile(r"^### USER[ \t]*$", re.MULTILINE)
_HEAD = re.compile(r"^#\s*(PR-\d+)\s+\S+\s+v(\d+(?:\.\d+)*)", re.MULTILINE)
_SLOT = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def strip_delimiters(s: str) -> str:
    return (s or "").replace("<<<", "").replace(">>>", "")


@dataclass(frozen=True)
class Prompt:
    path: Path
    version: str  # e.g. "PR-02 v1.0"
    system: str
    user: str

    def render(self, **values: str) -> tuple[str, str]:
        clean = {k: strip_delimiters(str(v)) for k, v in values.items()}

        def fill(t: str) -> str:
            def sub(m: re.Match) -> str:
                if m.group(1) not in clean:
                    raise KeyError(f"{self.version}: no value for {{{{{m.group(1)}}}}}")
                return clean[m.group(1)]
            return _SLOT.sub(sub, t)

        system, user = fill(self.system), fill(self.user)
        if "{{" in system or "{{" in user:
            raise ValueError(f"{self.version}: unfilled placeholder after render")
        return system, user


def load_prompt(relpath: str, root: Path = PROMPTS_DIR) -> Prompt:
    path = Path(root) / relpath
    text = path.read_text(encoding="utf-8")
    s, u = _SYS.search(text), _USR.search(text)
    if not s or not u or u.start() < s.start():
        raise ValueError(f"{path}: needs a '### SYSTEM' line followed by a '### USER' line")
    head = _HEAD.search(text[: s.start()])
    if not head:
        raise ValueError(f"{path}: first header line must look like '# PR-xx name  vX.Y'")
    return Prompt(path, f"{head.group(1)} v{head.group(2)}",
                  text[s.end(): u.start()].strip(), text[u.end():].strip())
