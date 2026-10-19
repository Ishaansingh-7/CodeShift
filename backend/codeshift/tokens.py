from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    col: int

    def to_dict(self):
        return {"kind": self.kind, "text": self.text, "line": self.line, "col": self.col}
