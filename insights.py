"""Plain-English insight sentences, generated from the data (never hardcoded).
Also holds the Indian-style number formatters used in those sentences."""
import re


def fmt_inr(v):
    """12345678 -> '₹1.23 Cr', 250000 -> '₹2.50 Lakh', 4500 -> '₹4,500'."""
    v = float(v)
    sign, a = ("-" if v < 0 else ""), abs(v)
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:,.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:,.2f} Lakh"
    return f"{sign}₹{indian(a)}"


def indian(n):
    """Indian digit grouping: 1234567 -> '12,34,567'."""
    s = str(int(round(abs(float(n)))))
    if len(s) > 3:
        s = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", s[:-3]) + "," + s[-3:]
    return ("-" if float(n) < 0 else "") + s


def pct(v):
    return f"{float(v):.1f}%"


def _change_word(change):
    if change > 1:
        return "improving"
    if change < -1:
        return "declining"
    return "steady"


def trend(labels, sales, profit):
    """Compare the first half of the period with the second half."""
    n = len(labels)
    if n < 2:
        return "Only one month of data is available, so a trend cannot be shown yet."
    h = n // 2

    def chg(series):
        a = sum(series[:h]) / h
        b = sum(series[h:]) / (n - h)
        return ((b - a) / abs(a) * 100) if a else 0.0

    cs, cp = chg(sales), chg(profit)
    best = labels[sales.index(max(sales))]
    return (f"Sales are {_change_word(cs)} ({cs:+.1f}% in the recent half vs the earlier half) and profit is "
            f"{_change_word(cp)} ({cp:+.1f}%); the strongest month was {best}.")


def categories(cats, products):
    """cats/products: lists of dicts with name, sales, profit, units, margin, attention."""
    top_s = max(cats, key=lambda c: c["sales"])
    top_p = max(cats, key=lambda c: c["profit"])
    top_u = max(cats, key=lambda c: c["units"])
    total = sum(c["sales"] for c in cats) or 1
    weak = [c["name"] for c in cats if c["attention"]]
    out = {
        "sales": f"{top_s['name']} generates the highest sales at {fmt_inr(top_s['sales'])} ({pct(top_s['sales'] / total * 100)} of the total).",
        "profit": (f"{top_p['name']} earns the most profit at {fmt_inr(top_p['profit'])}."
                   + (f" Needs attention (low or negative margin): {', '.join(weak)}." if weak else " No category is running at a low margin.")),
        "units": f"{top_u['name']} sells the most units ({indian(top_u['units'])}).",
    }
    if products:
        tp = products[0]
        losers = [p["name"] for p in products if p["profit"] < 0]
        out["products"] = (f"{tp['name']} is the best-selling product at {fmt_inr(tp['sales'])}."
                           + (f" In red: {', '.join(losers[:3])} lose money." if losers else ""))
    return out


def orders(kpi, lost, lost_share, worst):
    return {
        "status": (f"{pct(kpi['delivered_rate'])} of orders are delivered; {pct(kpi['return_rate'])} are returned "
                   f"and {pct(kpi['cancel_rate'])} are cancelled."),
        "loss": (f"Returns and cancellations put {fmt_inr(lost)} of sales at risk ({pct(lost_share)} of gross sales)"
                 + (f"; {worst['name']} loses the most at {pct(worst['rate'])} of its orders." if worst else ".")),
    }


def _share(rows, key="sales"):
    t = sum(r[key] for r in rows) or 1
    return rows[0][key] / t * 100


def channels(pay, ful):
    tp = max(pay, key=lambda r: r["sales"])
    bp = max(pay, key=lambda r: r["profit"])
    tf = max(ful, key=lambda r: r["sales"])
    bf = max(ful, key=lambda r: r["margin"])
    return {
        "payment": (f"{tp['name']} brings the most sales ({fmt_inr(tp['sales'])}); {bp['name']} earns the most profit "
                    f"({fmt_inr(bp['profit'])})."),
        "fulfillment": (f"{tf['name']} drives the most sales ({fmt_inr(tf['sales'])}); "
                        f"{bf['name']} has the best profit margin ({pct(bf['margin'])})."),
    }


def states(rows):
    out = {}
    for key, label, f in (("sales", "sales", fmt_inr), ("profit", "profit", fmt_inr), ("orders", "orders", indian)):
        ranked = sorted(rows, key=lambda r: r[key], reverse=True)[:3]
        total = sum(r[key] for r in rows) or 1
        share = sum(r[key] for r in ranked) / total * 100
        names = ", ".join(r["name"] for r in ranked)
        out[key] = f"Top markets by {label}: {names} - together {pct(share)} of the total (leader: {f(ranked[0][key])})."
    return out
