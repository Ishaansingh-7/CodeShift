from ..c.lexer import OPS, Lexer

KEYWORDS = {
    "if", "else", "while", "for", "do", "return", "break", "continue", "switch", "case", "default", "class", "public",
    "private", "protected", "static", "final", "new", "import", "package", "this", "super", "null", "true", "false",
    "try", "catch", "finally", "throw", "throws", "interface", "extends", "implements", "var", "instanceof", "enum",
}
TYPES = {"int", "long", "short", "byte", "char", "boolean", "void", "float", "double", "String", "StringBuilder", "ArrayList",
         "List", "LinkedHashMap", "HashMap", "Map", "TreeSet", "HashSet", "Set"}


class JavaLexer(Lexer):
    KEYWORDS, TYPES, BUILTINS, OPS, PRE = KEYWORDS, TYPES, set(), [">>>=", ">>>"] + OPS, False


def lex(code):
    return JavaLexer(code).run()
