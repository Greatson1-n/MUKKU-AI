import ast
import math
import operator
from typing import Union

# Allowed operators
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Allowed math functions
FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
}

# Allowed constants
CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

class SafeCalculatorVisitor(ast.NodeVisitor):
    def visit(self, node):
        method_name = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    # For older Python AST compatibility (Num)
    def visit_Num(self, node):
        return node.n

    def visit_Name(self, node):
        name = node.id.lower()
        if name in CONSTANTS:
            return CONSTANTS[name]
        raise ValueError(f"Unknown variable or constant: '{node.id}'")

    def visit_UnaryOp(self, node):
        op_type = type(node.op)
        if op_type in OPERATORS:
            operand = self.visit(node.operand)
            return OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")

    def visit_BinOp(self, node):
        op_type = type(node.op)
        if op_type in OPERATORS:
            left = self.visit(node.left)
            right = self.visit(node.right)
            # Guard against huge power exponentiation
            if op_type is ast.Pow and (abs(right) > 1000 or (abs(left) > 1000 and right > 10)):
                raise ValueError("Exponentiation result exceeds safe computation threshold")
            return OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id.lower()
            if func_name in FUNCTIONS:
                args = [self.visit(arg) for arg in node.args]
                return FUNCTIONS[func_name](*args)
            raise ValueError(f"Unsupported math function: '{node.func.id}'")
        raise ValueError("Dynamic or nested function calls are not permitted")

    def generic_visit(self, node):
        raise ValueError(f"Expression contains unsupported construct: {node.__class__.__name__}")

def calculate(expression: str) -> str:
    """Safely evaluates a mathematical expression string using an AST parser."""
    clean_expr = expression.strip().replace("^", "**").replace("×", "*").replace("÷", "/")
    # Remove percentage signs like 25% -> (25/100)
    # Simple percentage handling:
    try:
        tree = ast.parse(clean_expr, mode='eval')
        visitor = SafeCalculatorVisitor()
        result = visitor.visit(tree)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return str(result)
    except Exception as e:
        return f"Calculation Error: {str(e)}"
