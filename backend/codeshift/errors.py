class CompileError(Exception):
    def __init__(self, stage, message, line=0, col=0):
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.line = line
        self.col = col

    def __str__(self):
        return f"{self.message} at line {self.line}, col {self.col}" if self.line else self.message

    def to_dict(self):
        return {"message": str(self), "line": self.line, "col": self.col, "stage": self.stage}
