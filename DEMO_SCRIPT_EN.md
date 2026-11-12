# Avanza demo — English presentation draft

Target: under three minutes, including brief screen transitions. The spoken script is below; presenter notes are separate and are not read aloud.

## Spoken script

We’ve built an interactive investment demo designed for Avanza Akademin, with a customer view showing how the same tools could support existing savers.

The idea is simple: help people understand their portfolio, compare choices, and see what those choices cost.

In Portfolio Check, we separate current holdings from a target allocation. Users can choose instruments, name them, and adjust their weights. They can see concentration, equity exposure, historical volatility, and Sharpe, which relates excess return to volatility. The historical period and data sources are visible.

The strategy simulator compares buy and hold with monthly or quarterly rebalancing over the same available history. It uses real market prices, including NAV histories for Avanza’s own funds, such as Avanza Zero. Results are shown in kronor and percentages.

Users can include brokerage and other selected costs, and compare estimated ISK and AF taxation. For AF, the “if I sold now” view includes estimated tax on unrealised gains, making the cost of selling visible.

We also added historical portfolio optimisation. Users can choose Sharpe, CAGR, Sortino, or drawdown, or define a custom formula, with minimum, exact, and maximum weights. We search on an earlier portion of the data, then check the chosen weights on later data. The search is before optional costs and taxes; net results are shown separately.

Finally, the customer demo supports sample accounts or imported holdings, cash, deposits, and optional sales. It turns target weights into a funded proposal while keeping current holdings unchanged.

This is a prototype, with no bank login or trade execution. Historical comparisons are not forecasts. The goal is to connect learning with a clearer understanding of portfolio decisions.

## Presenter notes — not spoken

- Open with the overview. Use “Portfolio Check” as the spoken English name for **Portföljkollen**.
- Show current allocation and target weights together, then the risk metrics. Avoid reading individual numbers aloud: values change with the selected data and settings.
- Have the historical strategy chart ready in a second tab, with Avanza Zero selected and a common period already loaded. Show the percentage view and the fee/tax controls rather than changing every setting live.
- Return to a prepared optimisation result in **Hitta en historisk fördelning**. Point to the search and later validation dates. Do not call it the guaranteed best portfolio or describe validation as a forecast. NAV already includes the fund’s ongoing charges; optional trading costs and account taxes are separate from the search objective.
- Finish in **Mitt konto · demo**, with the funded proposal already open. Explain that it demonstrates a possible customer flow. It is not connected to an Avanza account.
- Prefer prepared views to waiting for data or running a new optimisation during the timed presentation. Allow around 15 seconds in total for transitions and pointing.
- Background definitions remain in [DEMO_MANUS.md](DEMO_MANUS.md) and [OPTIMIZATION_AND_ACCOUNTS.md](OPTIMIZATION_AND_ACCOUNTS.md).
