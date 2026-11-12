"""Percentage presentation of existing results; no change to trading or tax rules."""
import numpy as np

PERCENTAGE_BASES = ("Startbeloppet", "Slutvärdet före avdrag", "Vinsten före avdrag")


def development_percent(values, initial_amount):
    if not np.isfinite(initial_amount) or initial_amount <= 0:
        raise ValueError("Startbeloppet måste vara positivt.")
    return (np.asarray(values, dtype=float) / initial_amount - 1) * 100


def deduction_report(result, account, path=0, base="Startbeloppet"):
    if account not in {"ISK", "AF"} or base not in PERCENTAGE_BASES:
        raise ValueError("Okänd kontotyp eller procentbas.")
    history, settings = result["history"], result["settings"]
    initial = float(result["initial_amount"])
    gross = float(history["gross"][-1, path])
    after_costs = float(history["after_costs"][-1, path])
    net = float(history["isk" if account == "ISK" else "af"][-1, path])
    preview = account == "AF" and settings.include_tax and settings.af_sale_view
    actual = {key: float(value[path]) for key, value in result["components"].items()}
    direct = {key: value + (float(result["af_sale_parts"][key][path]) if preview else 0.)
              for key, value in actual.items()}
    tax = 0.
    if settings.include_tax:
        tax = float(history["af_tax_if_sold"][-1, path]) if preview else float(result["tax_isk" if account == "ISK" else "tax_af"][path])
    rows = [("Kontoavgift", 0.), ("Courtage", direct["courtage"]),
            ("Valutaväxling", direct["fx"]), ("Antagen spread", direct["spread"]),
            ("Övriga handelsavgifter / köpskatt", direct["other"]),
            ("Extra löpande avgift", direct["ongoing"]),
            ("Följdeffekt på avkastning och exponering", gross - after_costs - sum(actual.values())),
            (f"Skatt · {account}", tax)]
    impact = gross - net
    rows.append(("Totalt avdrag och följdeffekter", impact))
    denominator = {"Startbeloppet": initial, "Slutvärdet före avdrag": gross,
                   "Vinsten före avdrag": gross - initial}[base]
    valid_base = bool(np.isfinite(denominator) and denominator > 0)
    return dict(base=base, denominator=denominator if valid_base else None,
                rows=[dict(label=label, amount=value, percent=value / denominator * 100 if valid_base else None)
                      for label, value in rows],
                gross=gross, net=net, gross_return=float(development_percent(gross, initial)),
                net_return=float(development_percent(net, initial)),
                return_impact_pp=-impact / initial * 100)
