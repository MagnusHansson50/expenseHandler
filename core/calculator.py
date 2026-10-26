"""Summaries of purchases.

Pure functions on Pandas DataFrames with the columns Price and (for grouping) Category.
"""

import pandas as pd

UNCATEGORIZED = "Other"


def total_cost(df):
    """Return the summed Price of all rows, rounded to öre."""
    if df.empty:
        return 0.0
    return round(float(pd.to_numeric(df["Price"], errors="coerce").sum()), 2)


def sum_by_category(df):
    """Return total Price per Category, largest first.

    The result is indexed by Category with a single Price column, ready for
    `st.bar_chart`. Rows without a category are counted as 'Other'.
    """
    if df.empty:
        return pd.DataFrame(columns=["Price"], index=pd.Index([], name="Category"))

    summary = (
        df.assign(
            Category=df["Category"].fillna(UNCATEGORIZED).replace("", UNCATEGORIZED),
            Price=pd.to_numeric(df["Price"], errors="coerce"),
        )
        .groupby("Category")[["Price"]]
        .sum()
        .round(2)
        .sort_values("Price", ascending=False)
    )
    return summary
