"""Data layer: flexible column detection, cleaning, filtering, KPIs and aggregations (pandas)."""
import re
import numpy as np
import pandas as pd
import insights as ins

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
LOW_MARGIN = 5.0  # a margin below this % is flagged "needs attention"

# canonical name -> accepted names (lower-case, no spaces/underscores/symbols)
ALIASES = {
    "order_id": ["orderid", "ordernumber", "orderno"],
    "date": ["orderdate", "date", "purchasedate", "orderdatetime", "ordereddate"],
    "category": ["category", "productcategory", "department"],
    "product": ["productname", "product", "itemname", "item", "title"],
    "quantity": ["quantity", "qty", "unitssold", "units"],
    "sales": ["sales", "revenue", "totalsales", "salesamount", "amount", "ordervalue"],
    "profit": ["profit", "netprofit", "profitamount"],
    "status": ["orderstatus", "status"],
    "payment": ["paymentmethod", "payment", "paymenttype", "paymode"],
    "fulfillment": ["fulfillmentmethod", "fulfilmentmethod", "fulfillment", "fulfilment", "fulfillmentchannel",
                    "fulfilmentchannel", "fulfillmenttype", "fulfilmenttype"],
    "state": ["state", "shipstate", "customerstate", "shippingstate", "region"],
}
REQUIRED = [k for k in ALIASES if k != "order_id"]
PRETTY = {"date": "Order Date", "category": "Category", "product": "Product Name", "quantity": "Quantity",
          "sales": "Sales", "profit": "Profit", "status": "Order Status", "payment": "Payment Method",
          "fulfillment": "Fulfillment Method", "state": "State"}


def _norm(name):
    """Lower-case, drop spaces/underscores/symbols, and ignore a trailing currency tag like '_INR'."""
    return re.sub(r"inr$", "", re.sub(r"[^a-z0-9]", "", str(name).lower()))


def clean(raw):
    """Map columns, parse dates/numbers safely, drop or fill bad values. Raises ValueError with a friendly message."""
    if raw is None or raw.empty:
        raise ValueError("The file is empty.")
    cols = {_norm(c): c for c in raw.columns}
    mapping = {}
    for canon, names in ALIASES.items():
        for n in names:
            if n in cols and cols[n] not in mapping.values():
                mapping[canon] = cols[n]
                break
    missing = [PRETTY[k] for k in REQUIRED if k not in mapping]
    if missing:
        raise ValueError("Missing column(s): " + ", ".join(missing) +
                         ". Please include them (names are matched ignoring case, spaces and underscores).")
    df = pd.DataFrame({k: raw[v] for k, v in mapping.items()})
    if "order_id" not in df:
        df.insert(0, "order_id", [f"ORD-{i + 1:06d}" for i in range(len(df))])
    df["order_id"] = df["order_id"].astype(str)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")           # unparseable dates -> NaT -> dropped
    for c in ("quantity", "sales", "profit"):                          # strip ₹ and commas, coerce to numbers
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[₹,\s]", "", regex=True), errors="coerce")
    df = df.dropna(subset=["date", "sales"])
    df["quantity"] = df["quantity"].fillna(1).clip(lower=0)
    df["profit"] = df["profit"].fillna(0.0)                            # negative profit is kept on purpose (losses)
    df = df[df["sales"] >= 0]

    for c in ("category", "product", "status", "payment", "fulfillment", "state"):
        df[c] = df[c].fillna("Unknown").astype(str).str.strip().replace({"": "Unknown", "nan": "Unknown"})
    df["status"] = df["status"].map(_status)
    if df.empty:
        raise ValueError("No usable rows were found after cleaning (check the date and sales columns).")
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["period"] = df["date"].dt.strftime("%Y-%m")
    return df.reset_index(drop=True)


def _status(s):
    t = s.lower()
    for key, name in (("cancel", "Cancelled"), ("return", "Returned"), ("deliver", "Delivered"), ("ship", "Shipped")):
        if key in t:
            return name
    return s.title()


def filter_options(df, year=None):
    """Dropdown values. If a year is given, only months that really have data in that year are offered."""
    mdf = df[df["year"] == int(year)] if year not in (None, "", "all") and str(year).isdigit() else df
    return {
        "years": sorted(int(y) for y in df["year"].unique()),
        "months": [{"value": m, "name": MONTHS[m - 1]} for m in sorted(int(x) for x in mdf["month"].unique())],
        "categories": sorted(df["category"].unique().tolist()),
        "states": sorted(df["state"].unique().tolist()),
        "statuses": sorted(df["status"].unique().tolist()),
        "date_min": df["date"].min().strftime("%Y-%m-%d"),
        "date_max": df["date"].max().strftime("%Y-%m-%d"),
    }


def apply_filters(df, args):
    """args: year, month, category, state, status ('' or 'all' = no filter)."""
    def pick(k):
        v = args.get(k, "")
        return None if v in ("", "all", None) else v
    try:
        if pick("year"):
            df = df[df["year"] == int(pick("year"))]
        if pick("month"):
            df = df[df["month"] == int(pick("month"))]
    except ValueError:
        pass
    for key, op in (("from", "ge"), ("to", "le")):          # optional date range (YYYY-MM-DD), both ends included
        v = pick(key)
        ts = pd.to_datetime(v, errors="coerce") if v else pd.NaT
        if pd.notna(ts):
            df = df[df["date"] >= ts] if op == "ge" else df[df["date"] < ts + pd.Timedelta(days=1)]
    for key, col in (("category", "category"), ("state", "state"), ("status", "status")):
        if pick(key):
            df = df[df[col] == pick(key)]
    return df


def _f(x):
    return round(float(x), 2)


def _group(df, col):
    g = df.groupby(col).agg(sales=("sales", "sum"), profit=("profit", "sum"),
                            units=("quantity", "sum"), orders=("order_id", "nunique")).reset_index()
    g["margin"] = np.where(g["sales"] > 0, g["profit"] / g["sales"] * 100, 0.0)
    g["attention"] = (g["profit"] < 0) | (g["margin"] < LOW_MARGIN)
    return g.sort_values("sales", ascending=False)


def _rows(g, col):
    return [{"name": str(r[col]), "sales": _f(r["sales"]), "profit": _f(r["profit"]), "units": int(r["units"]),
             "orders": int(r["orders"]), "margin": _f(r["margin"]), "attention": bool(r["attention"])}
            for _, r in g.iterrows()]


def overview(df):
    if df.empty:
        return {"empty": True}
    sales, profit = df["sales"].sum(), df["profit"].sum()
    orders, units = df["order_id"].nunique(), int(df["quantity"].sum())
    margin = profit / sales * 100 if sales else 0.0
    aov = sales / orders if orders else 0.0
    t = df.groupby("period").agg(sales=("sales", "sum"), profit=("profit", "sum"))
    t = t.reindex(pd.period_range(t.index.min(), t.index.max(), freq="M").strftime("%Y-%m"), fill_value=0.0)  # months with no orders show as 0
    labels = pd.to_datetime(t.index + "-01").strftime("%b %Y").tolist()
    s, p = [_f(x) for x in t["sales"]], [_f(x) for x in t["profit"]]
    kpis = [
        {"label": "Total Sales", "display": ins.fmt_inr(sales), "icon": "💰"},
        {"label": "Total Profit", "display": ins.fmt_inr(profit), "icon": "📈", "bad": bool(profit < 0)},
        {"label": "Total Orders", "display": ins.indian(orders), "icon": "🧾"},
        {"label": "Total Units Sold", "display": ins.indian(units), "icon": "📦"},
        {"label": "Average Order Value", "display": ins.fmt_inr(aov), "icon": "🛒"},
        {"label": "Profit Margin", "display": ins.pct(margin), "icon": "％", "bad": bool(margin < LOW_MARGIN)},
    ]
    return {"kpis": kpis, "trend": {"labels": labels, "sales": s, "profit": p},
            "insights": {"trend": ins.trend(labels, s, p)}}


def products(df):
    if df.empty:
        return {"empty": True}
    cats = _rows(_group(df, "category"), "category")
    top = _rows(_group(df, "product").head(10), "product")
    return {"categories": cats, "top_products": top, "insights": ins.categories(cats, top)}


def orders(df):
    if df.empty:
        return {"empty": True}
    total = df["order_id"].nunique()
    by_status = df.groupby("status")["order_id"].nunique()
    n = lambda k: int(by_status.get(k, 0))
    rate = lambda k: n(k) / total * 100 if total else 0.0
    rates = {"delivered_rate": rate("Delivered"), "return_rate": rate("Returned"), "cancel_rate": rate("Cancelled")}
    kpis = [
        {"label": "Delivered Orders", "display": ins.indian(n("Delivered")), "icon": "✅"},
        {"label": "Shipped Orders", "display": ins.indian(n("Shipped")), "icon": "🚚"},
        {"label": "Returned Orders", "display": ins.indian(n("Returned")), "icon": "↩️", "bad": n("Returned") > 0},
        {"label": "Cancelled Orders", "display": ins.indian(n("Cancelled")), "icon": "❌", "bad": n("Cancelled") > 0},
        {"label": "Return Rate", "display": ins.pct(rates["return_rate"]), "icon": "％", "bad": rates["return_rate"] > 10},
        {"label": "Cancellation Rate", "display": ins.pct(rates["cancel_rate"]), "icon": "％", "bad": rates["cancel_rate"] > 10},
    ]
    order = [s for s in ("Delivered", "Shipped", "Returned", "Cancelled") if s in by_status.index]
    order += [s for s in by_status.index if s not in order]
    status_chart = {"labels": order, "values": [n(s) for s in order]}

    cat = df.groupby("category").agg(orders=("order_id", "nunique")).reset_index()
    for st in ("Returned", "Cancelled"):
        cat[st] = cat["category"].map(df[df["status"] == st].groupby("category")["order_id"].nunique()).fillna(0).astype(int)
    cat["rate"] = np.where(cat["orders"] > 0, (cat["Returned"] + cat["Cancelled"]) / cat["orders"] * 100, 0.0)
    cat = cat.sort_values("rate", ascending=False)
    lost = df.loc[df["status"].isin(["Returned", "Cancelled"]), "sales"].sum()
    gross = df["sales"].sum()
    worst = ({"name": cat.iloc[0]["category"], "rate": float(cat.iloc[0]["rate"])}
             if lost > 0 and len(cat) else None)
    return {"kpis": kpis, "status_chart": status_chart,
            "category_loss": {"labels": cat["category"].tolist(), "returned": cat["Returned"].tolist(),
                              "cancelled": cat["Cancelled"].tolist()},
            "insights": ins.orders(rates, lost, lost / gross * 100 if gross else 0.0, worst)}


def geo(df):
    if df.empty:
        return {"empty": True}
    pay = _rows(_group(df, "payment"), "payment")
    ful = _rows(_group(df, "fulfillment"), "fulfillment")
    st = _rows(_group(df, "state"), "state")
    insight = ins.channels(pay, ful)
    insight["state"] = ins.states(st)
    return {"payment": pay, "fulfillment": ful, "states": st, "insights": insight}

