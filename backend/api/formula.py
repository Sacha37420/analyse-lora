"""Évaluation des formules des grandeurs calculées, sans ``eval``.

Une formule est écrite par tout titulaire d'un accès au capteur (membres de
``amis`` et ``famille`` compris). Elle n'est donc jamais passée à ``eval`` :
``eval(..., {'__builtins__': {}})`` n'est pas un bac à sable, l'objet de base
reste joignable par ``().__class__.__base__.__subclasses__()``.

La formule est analysée (``ast.parse(mode='eval')``) puis parcourue nœud par
nœud ; tout nœud absent de la liste ci-dessous la fait refuser.

Syntaxe acceptée — c'est celle des exemples du README, du guide, de l'aide de
saisie et des tests, plus ce qui sert à les combiner :

* nombres (``3``, ``2.5``, ``1e-3``) ; ``True``/``False`` ;
* ``row['champ']``, éventuellement ``row['a']['b']`` ou ``row['liste'][0]`` :
  clés constantes (chaîne ou entier) seulement, et ``row`` n'apparaît que là ;
* ``+ - * / // % **``, ``+x``, ``-x``, ``not x``, ``and``, ``or`` ;
* comparaisons (``< <= > >= == !=``, chaînées comprises) ;
* ``a if condition else b`` ;
* appels de fonctions par leur nom seul : celles de ``math`` (sauf
  ``factorial``, ``comb`` et ``perm``, dont le coût n'est pas borné), plus
  ``abs``, ``round``, ``min``, ``max`` ; arguments positionnels seulement ;
* constantes ``pi``, ``e``, ``tau``, ``inf``, ``nan``.

Refusé : attributs (``x.y``), lambdas, compréhensions, listes/dicts/ensembles
littéraux, chaînes hors d'une clé de ``row``, appels par mot-clé ou ``*args``,
tout autre nom, affectations (``:=``), f-strings.

Gardes à l'évaluation : les opérateurs arithmétiques n'acceptent que des
nombres (un champ texte de ``row`` multiplié par un entier ne fabrique plus une
chaîne géante), et ``**`` passe en flottant dès que l'exposant ou la base
deviennent grands (``9**9**9`` ne bloque plus le serveur : il déborde).
"""
from __future__ import annotations

import ast
import math
import operator

MAX_FORMULA_LENGTH = 500


class FormulaError(ValueError):
    """Formule refusée (syntaxe hors liste, trop longue, mal formée)."""


_EXCLUDED_MATH = {'factorial', 'comb', 'perm'}

FUNCTIONS = {
    name: getattr(math, name)
    for name in dir(math)
    if not name.startswith('_') and callable(getattr(math, name)) and name not in _EXCLUDED_MATH
}
FUNCTIONS.update({'abs': abs, 'round': round, 'min': min, 'max': max})

CONSTANTS = {'pi': math.pi, 'e': math.e, 'tau': math.tau, 'inf': math.inf, 'nan': math.nan}

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: None,  # _pow, avec garde
}
_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_}
_CMPOPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
}

_INT_POW_MAX_EXP = 64
_INT_POW_MAX_BASE = 2 ** 64


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, complex)


def _pow(a, b):
    if (isinstance(a, int) and isinstance(b, int)
            and 0 <= b <= _INT_POW_MAX_EXP and abs(a) <= _INT_POW_MAX_BASE):
        return a ** b
    return float(a) ** float(b)


# ── Validation (à l'enregistrement et avant toute évaluation) ────────────────

def _check_row_subscript(node: ast.Subscript) -> None:
    key = node.slice
    if not (isinstance(key, ast.Constant) and type(key.value) in (str, int)):
        raise FormulaError("La clé de row[...] doit être une chaîne ou un entier écrit en clair.")
    value = node.value
    if isinstance(value, ast.Subscript):
        _check_row_subscript(value)
    elif not (isinstance(value, ast.Name) and value.id == 'row'):
        raise FormulaError("Seul row peut être indexé : row['champ'].")


def _check(node: ast.AST) -> None:
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float, bool):
            raise FormulaError("Seuls les nombres sont acceptés comme valeurs écrites en clair.")
    elif isinstance(node, ast.Subscript):
        _check_row_subscript(node)
    elif isinstance(node, ast.Name):
        if node.id not in CONSTANTS:
            raise FormulaError(f"Nom inconnu : {node.id}. Utilisez row['champ'].")
    elif isinstance(node, ast.BinOp):
        if type(node.op) not in _BINOPS:
            raise FormulaError("Opérateur non autorisé.")
        _check(node.left)
        _check(node.right)
    elif isinstance(node, ast.UnaryOp):
        if type(node.op) not in _UNARYOPS:
            raise FormulaError("Opérateur non autorisé.")
        _check(node.operand)
    elif isinstance(node, ast.BoolOp):
        for v in node.values:
            _check(v)
    elif isinstance(node, ast.Compare):
        if any(type(op) not in _CMPOPS for op in node.ops):
            raise FormulaError("Comparaison non autorisée.")
        _check(node.left)
        for c in node.comparators:
            _check(c)
    elif isinstance(node, ast.IfExp):
        _check(node.test)
        _check(node.body)
        _check(node.orelse)
    elif isinstance(node, ast.Call):
        if not (isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS):
            raise FormulaError("Fonction non autorisée (fonctions de math, abs, round, min, max).")
        if node.keywords:
            raise FormulaError("Les arguments nommés ne sont pas acceptés.")
        for a in node.args:
            if isinstance(a, ast.Starred):
                raise FormulaError("*args n'est pas accepté.")
            _check(a)
    else:
        raise FormulaError(f"Élément non autorisé dans une formule : {type(node).__name__}.")


def compile_formula(formula) -> ast.Expression:
    """Analyse et valide ; lève FormulaError si la formule est refusée."""
    if not isinstance(formula, str) or not formula.strip():
        raise FormulaError("Formule vide.")
    if len(formula) > MAX_FORMULA_LENGTH:
        raise FormulaError(f"Formule trop longue ({MAX_FORMULA_LENGTH} caractères au plus).")
    try:
        tree = ast.parse(formula.strip(), mode='eval')
    except (SyntaxError, ValueError, MemoryError, RecursionError) as exc:
        raise FormulaError(f"Formule mal formée : {exc.__class__.__name__}.") from None
    try:
        _check(tree.body)
    except RecursionError:
        raise FormulaError("Formule trop imbriquée.") from None
    return tree


# ── Évaluation ───────────────────────────────────────────────────────────────

def _eval(node: ast.AST, row):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Subscript):
        return _eval_subscript(node, row)
    if isinstance(node, ast.Name):
        return CONSTANTS[node.id]
    if isinstance(node, ast.BinOp):
        a, b = _eval(node.left, row), _eval(node.right, row)
        if not (_is_number(a) and _is_number(b)):
            raise TypeError('opérande non numérique')
        if isinstance(node.op, ast.Pow):
            return _pow(a, b)
        return _BINOPS[type(node.op)](a, b)
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, row)
        if not isinstance(node.op, ast.Not) and not _is_number(v):
            raise TypeError('opérande non numérique')
        return _UNARYOPS[type(node.op)](v)
    if isinstance(node, ast.BoolOp):
        is_and = isinstance(node.op, ast.And)
        v = None
        for sub in node.values:
            v = _eval(sub, row)
            if bool(v) != is_and:
                return v
        return v
    if isinstance(node, ast.Compare):
        left = _eval(node.left, row)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, row)
            if not _CMPOPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _eval(node.body, row) if _eval(node.test, row) else _eval(node.orelse, row)
    if isinstance(node, ast.Call):
        return FUNCTIONS[node.func.id](*[_eval(a, row) for a in node.args])
    raise FormulaError(type(node).__name__)  # inatteignable après compile_formula


def _eval_subscript(node: ast.Subscript, row):
    base = row if isinstance(node.value, ast.Name) else _eval_subscript(node.value, row)
    return base[node.slice.value]


def evaluate(tree: ast.Expression, row):
    """Évalue une formule déjà validée ; lève une exception en cas d'erreur."""
    return float(_eval(tree.body, row))


def safe_eval(formula, row):
    """Valeur de la formule sur une lecture, ou None si refusée ou en erreur."""
    try:
        return evaluate(compile_formula(formula), row)
    except Exception:
        return None
