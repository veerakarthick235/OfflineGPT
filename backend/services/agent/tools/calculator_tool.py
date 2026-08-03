"""
Calculator Tool — safe math evaluation (no exec/eval exploits).

Uses Python's ast module to parse and evaluate only numeric expressions.
No code injection possible.

Registered triggers:
  "calculate", "what is 2+2", "compute", "solve", math-looking expressions
"""
from __future__ import annotations
import ast
import operator
from ..tool_registry import registry, ToolResult

# Safe operators only
_OPERATORS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.Mod:  operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    """Recursively evaluate an AST node using only safe operators."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left  = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"Unsupported unary: {op_type.__name__}")
        return _OPERATORS[op_type](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def evaluate(expression: str) -> float:
    """
    Safely evaluate a math expression string.
    Raises ValueError for invalid or unsafe expressions.
    """
    expression = expression.strip()
    # Replace common English words
    expression = expression.replace("×", "*").replace("÷", "/").replace("^", "**")
    tree = ast.parse(expression, mode="eval")
    return _safe_eval(tree.body)


@registry.tool(
    name        = "calculator",
    description = "Evaluate math expressions: arithmetic, powers, percentages",
    fast_triggers = [
        r"\b(calculate|compute|evaluate|solve|what\s+is)\s+[\d\s\+\-\*\/\(\)\^\.\%]+",
        r"\bhow\s+much\s+is\s+[\d]",
        r"\b\d+\s*[\+\-\*\/\^]\s*\d+",           # direct math: 2+2, 10*5
        r"\b\d+(\.\d+)?\s*%\s+of\s+\d+",          # 20% of 500
        r"\bsquare\s+root\s+of\b",
        r"\bsquared?\b|\bcubed?\b",
    ],
)
async def calculator_tool(expression: str = "", **kwargs) -> ToolResult:
    """Safely evaluate a math expression and return the result."""
    if not expression.strip():
        return ToolResult(
            tool    = "calculator",
            success = False,
            error   = "No expression provided",
        )

    # Try to extract just the numeric expression from the full message
    import re
    # Remove words like "calculate", "what is", etc.
    clean = re.sub(
        r"^\s*(calculate|compute|evaluate|solve|what\s+is|how\s+much\s+is)\s*",
        "", expression, flags=re.IGNORECASE
    ).strip()
    clean = clean.rstrip("?!.")

    try:
        result = evaluate(clean)

        # Format nicely
        if result == int(result):
            formatted = str(int(result))
        else:
            formatted = f"{result:.6g}"   # up to 6 significant figures

        context_text = f"[Calculator]\n{clean} = {formatted}"

        return ToolResult(
            tool    = "calculator",
            success = True,
            context = context_text,
            label   = f"{clean} = {formatted}",
            data    = {"expression": clean, "result": result, "formatted": formatted},
        )
    except Exception as e:
        return ToolResult(
            tool    = "calculator",
            success = False,
            error   = f"Could not evaluate: {e}",
            data    = {"expression": clean},
        )
