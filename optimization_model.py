"""Historical portfolio search, constrained weights and chronological validation.

The objective is measured before optional trading fees/account taxes, on the
same buy-and-hold/monthly/quarterly value path used for the comparison. No
validation observation is read by the optimizer. Results are best found, not
a claim of global optimality or future performance.
"""
import ast
import hashlib
import operator
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from risk_model import sharpe_from_values

OBJECTIVES = ("Sharpe", "CAGR", "Sortino", "Lägsta max drawdown", "Egen formel")
MODES = ("Buy and hold", "Månadsvis rebalansering", "Kvartalsvis rebalansering")
FIELDS = ("Sharpe", "CAGR", "Sortino", "MaxDrawdown", "Volatilitet")
MIN_TRAIN = 252
MIN_VALIDATION = 63
WEIGHT_CONDITIONS = ("min", "=", "max")


def weight_condition_bounds(conditions, percentages):
    """Translate inclusive percentage conditions into portfolio-weight bounds."""
    conditions = list(conditions)
    try:
        percentages = np.asarray(percentages, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("Ange en vikt mellan 0 och 100 % för varje instrument.") from error
    if (percentages.ndim != 1 or not conditions or len(conditions) != len(percentages)
            or not np.isfinite(percentages).all() or (percentages < 0).any() or (percentages > 100).any()):
        raise ValueError("Ange en vikt mellan 0 och 100 % för varje instrument.")
    if any(condition not in WEIGHT_CONDITIONS for condition in conditions):
        raise ValueError("Välj min, = eller max för varje instrument.")
    values = percentages / 100
    lower = np.array([value if condition in ("min", "=") else 0. for condition, value in zip(conditions, values)])
    upper = np.array([value if condition in ("max", "=") else 1. for condition, value in zip(conditions, values)])
    return lower, upper


class Formula:
    """A small arithmetic language. Python evaluation is never used."""
    operators = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}

    def __init__(self, expression):
        if not isinstance(expression, str) or not expression.strip() or len(expression) > 200:
            raise ValueError("Ange en formel med högst 200 tecken.")
        try:
            self.tree = ast.parse(expression, mode="eval").body
        except SyntaxError as error:
            raise ValueError("Formeln kunde inte tolkas. Använd mått, tal, +, -, *, / och parenteser.") from error
        if len(list(ast.walk(self.tree))) > 80:
            raise ValueError("Formeln är för omfattande.")
        self._validate(self.tree, 0)
        if not any(isinstance(node, ast.Name) for node in ast.walk(self.tree)):
            raise ValueError("Formeln behöver innehålla minst ett portföljmått.")

    def _validate(self, node, depth):
        if depth > 12:
            raise ValueError("Formeln har för många nivåer.")
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not np.isfinite(node.value) or abs(node.value) > 1e6:
                raise ValueError("Formelns tal måste vara ändliga och högst en miljon i absolutvärde.")
        elif isinstance(node, ast.Name) and node.id.casefold() in {field.casefold() for field in FIELDS}:
            pass
        elif isinstance(node, ast.BinOp) and type(node.op) in self.operators:
            self._validate(node.left, depth + 1)
            self._validate(node.right, depth + 1)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            self._validate(node.operand, depth + 1)
        else:
            raise ValueError("Tillåtna mått är Sharpe, CAGR, Sortino, MaxDrawdown och Volatilitet. Endast enkel matematik tillåts.")

    def evaluate(self, metrics):
        values = {key.casefold(): value for key, value in metrics.items()}
        def calculate(node):
            if isinstance(node, ast.Constant):
                return float(node.value)
            if isinstance(node, ast.Name):
                try:
                    return values[node.id.casefold()]
                except KeyError as error:
                    raise ValueError("Ett mått i formeln saknas i underlaget.") from error
            if isinstance(node, ast.UnaryOp):
                value = calculate(node.operand)
                return -value if isinstance(node.op, ast.USub) else value
            left, right = calculate(node.left), calculate(node.right)
            if isinstance(node.op, ast.Div) and abs(right) < 1e-12:
                raise ValueError("Formeln ger division med noll.")
            return self.operators[type(node.op)](left, right)
        result = calculate(self.tree)
        if not np.isfinite(result):
            raise ValueError("Formeln använder ett mått som saknar definierat värde.")
        return float(result)


def curve_metrics(values, dates, risk_free_pct=2., target_pct=0.):
    values = np.asarray(values, dtype=float)
    dates = pd.DatetimeIndex(dates)
    if len(values) != len(dates) or len(values) < 2 or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("En positiv värdekurva med minst två datum behövs.")
    days = (dates[-1] - dates[0]).total_seconds() / 86400
    if days <= 0 or not -100 < target_pct or not np.isfinite(target_pct):
        raise ValueError("Kontrollera datum och årlig målavkastning.")
    returns = values[1:] / values[:-1] - 1
    target_daily = np.expm1(np.log1p(target_pct / 100) / 252)
    downside = np.sqrt(np.mean(np.minimum(returns - target_daily, 0) ** 2))
    sortino = (returns.mean() - target_daily) / downside * np.sqrt(252) if downside > 1e-12 else np.nan
    with np.errstate(over="ignore"):
        cagr = np.expm1(np.log(values[-1] / values[0]) * 365.25 / days) * 100
    return {"Sharpe": float(sharpe_from_values(values, risk_free_pct)[0]), "CAGR": float(cagr),
            "Sortino": float(sortino), "MaxDrawdown": float(np.max(1 - values / np.maximum.accumulate(values)) * 100),
            "Volatilitet": float(np.std(returns, ddof=1) * np.sqrt(252) * 100),
            "Utveckling": float((values[-1] / values[0] - 1) * 100)}


def curve_factory(prices, mode):
    if mode not in MODES:
        raise ValueError("Okänd rebalanseringsregel.")
    values = prices.to_numpy(dtype=float)
    if len(values) < 2 or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Gemensamma, positiva kurser behövs för alla instrument.")
    if mode == MODES[0]:
        relative = values / values[0]
        return lambda weights: relative @ weights
    periods = prices.index.to_period("M" if mode == MODES[1] else "Q")
    ends = np.flatnonzero(periods[:-1] != periods[1:]).tolist() + [len(values) - 1]
    segments, start = [], 0
    for end in ends:
        segments.append((start, end, values[start:end + 1] / values[start]))
        start = end
    def curve(weights):
        output = np.ones(len(values))
        wealth = 1.
        for start, end, relative in segments:
            output[start:end + 1] = wealth * (relative @ weights)
            wealth = output[end]
        return output
    return curve


def project_weights(vector, lower, upper):
    vector = np.asarray(vector, dtype=float)
    lower, upper = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    if (not np.isfinite(np.r_[vector, lower, upper]).all() or (lower < 0).any() or (upper > 1).any()
            or (lower > upper).any() or lower.sum() > 1 + 1e-9 or upper.sum() < 1 - 1e-9):
        raise ValueError("Viktgränserna går inte ihop: minsta vikter får summera till högst 100 % och högsta till minst 100 %.")
    lo, hi = float(np.min(vector - upper)) - 1, float(np.max(vector - lower)) + 1
    for _ in range(70):
        middle = (lo + hi) / 2
        if np.clip(vector - middle, lower, upper).sum() > 1:
            lo = middle
        else:
            hi = middle
    return np.clip(vector - (lo + hi) / 2, lower, upper)


def input_fingerprint(prices, config):
    import json
    digest = hashlib.sha256(pd.util.hash_pandas_object(prices, index=True).to_numpy().tobytes())
    digest.update(str(list(prices.columns)).encode())
    digest.update(json.dumps(config, sort_keys=True, default=str).encode())
    return digest.hexdigest()


def optimize_portfolio(prices, lower, upper, initial=None, objective="Sharpe", formula="", mode=MODES[0],
                       risk_free_pct=2., target_pct=0., train_share=.7, starts=5,
                       min_train=MIN_TRAIN, min_validation=MIN_VALIDATION):
    if objective not in OBJECTIVES or not .5 <= train_share <= .8:
        raise ValueError("Kontrollera optimeringsmål och periodindelning.")
    observations = len(prices) - 1
    split = int(observations * train_share)
    if split < min_train or observations - split < min_validation:
        raise ValueError(f"Sökningen behöver minst {min_train} dagsavkastningar i sökperioden och {min_validation} i den senare valideringen. Välj längre gemensam historik eller färre instrument.")
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("Kursdatum måste vara unika och i stigande ordning.")
    lower, upper = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    count = len(prices.columns)
    if lower.shape != (count,) or upper.shape != (count,):
        raise ValueError("Varje instrument behöver viktgränser.")
    seed = np.full(count, 1 / count) if initial is None else np.asarray(initial, dtype=float)
    seed = project_weights(seed, lower, upper)
    train, validation = prices.iloc[:split + 1], prices.iloc[split:]
    train_curve = curve_factory(train, mode)
    expression = Formula(formula) if objective == "Egen formel" else None
    def score(weights):
        metrics = curve_metrics(train_curve(weights), train.index, risk_free_pct, target_pct)
        value = expression.evaluate(metrics) if expression else (-metrics["MaxDrawdown"] if objective == "Lägsta max drawdown" else metrics[objective])
        if not np.isfinite(value):
            raise ValueError("Målet saknar definierat värde i sökperioden.")
        return value
    def loss(weights):
        try:
            return -score(weights)
        except (ValueError, FloatingPointError, ZeroDivisionError):
            return 1e12
    rng = np.random.default_rng(42)
    seeds = [seed, project_weights(np.full(count, 1 / count), lower, upper)]
    seeds += [project_weights(rng.dirichlet(np.ones(count)), lower, upper) for _ in range(max(0, starts - 2))]
    best, best_score, succeeded = None, -np.inf, False
    unique = abs(lower.sum() - 1) < 1e-10 or abs(upper.sum() - 1) < 1e-10
    for start in seeds:
        candidate = start
        if not unique:
            result = minimize(loss, start, method="SLSQP", bounds=list(zip(lower, upper)),
                              constraints=[{"type": "eq", "fun": lambda weights: weights.sum() - 1}],
                              options={"maxiter": 120, "ftol": 1e-9})
            if not result.success:
                continue
            candidate = project_weights(result.x, lower, upper)
        for weights in (candidate, start):
            value = -loss(weights)
            if value > -1e11:
                succeeded = True
                if value > best_score:
                    best, best_score = weights.copy(), value
    if not succeeded:
        raise ValueError("Sökningen kunde inte hitta en konvergerad fördelning med ett definierat mått. Kontrollera historik, mål och viktgränser.")
    validation_values = curve_factory(validation, mode)(best)
    validation_metrics = curve_metrics(validation_values, validation.index, risk_free_pct, target_pct)
    return dict(weights=best, score=best_score, train_metrics=curve_metrics(train_curve(best), train.index, risk_free_pct, target_pct),
                validation_metrics=validation_metrics, train=train, validation=validation,
                train_values=train_curve(best), validation_values=validation_values,
                mode=mode, objective=objective, formula=formula, risk_free_pct=risk_free_pct, target_pct=target_pct,
                lower=lower, upper=upper, starts=len(seeds), observations=observations)
