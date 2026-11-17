"""Flask app: serves the dashboard page and JSON API routes. All numbers come from data_processing (pandas).
Uploaded files are kept in data/. Each browser tab chooses its own file (the `file` query parameter), so two
people using the app never change each other's view."""
import io
import os
import threading
import uuid
import datetime as dt
import pandas as pd
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

import data_processing as dp

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
EXTS = (".xlsx", ".xlsm", ".csv")
ALL = "__all__"                       # special value: every saved file combined
UNSAVED = "unsaved:"                  # prefix for an uploaded file that has not been saved yet
UNSAVED_DIR = os.path.join(DATA_DIR, "_unsaved")   # uploads wait here until you press "Save file"
os.makedirs(UNSAVED_DIR, exist_ok=True)           # an empty data folder is fine: the page then asks for an upload
for _n in os.listdir(UNSAVED_DIR):                # unsaved uploads do not survive a restart
    try:
        os.remove(os.path.join(UNSAVED_DIR, _n))
    except OSError:
        pass

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB upload limit
LOCK = threading.RLock()
CACHE = {}                            # name -> (file mtime, cleaned dataframe)


def stamp(ts=None):
    return (dt.datetime.fromtimestamp(ts) if ts else dt.datetime.now()).strftime("%d %b %Y, %I:%M %p")


def list_files():
    """Data files in the data folder, newest first."""
    out = []
    for n in os.listdir(DATA_DIR):
        p = os.path.join(DATA_DIR, n)
        if n.lower().endswith(EXTS) and not n.startswith("~$") and os.path.isfile(p):
            out.append({"name": n, "mtime": os.path.getmtime(p), "size": os.path.getsize(p)})
    return sorted(out, key=lambda f: f["mtime"], reverse=True)


def read_any(src, name):
    """Read a CSV or Excel file (path or file-like object) into a raw dataframe."""
    if name.lower().endswith(".csv"):
        try:
            return pd.read_csv(src)
        except UnicodeDecodeError:
            if hasattr(src, "seek"):
                src.seek(0)
            return pd.read_csv(src, encoding="latin-1")
    return pd.read_excel(src, engine="openpyxl")


def show_name(name):
    """Name for display: drops the 'unsaved:' prefix and the random token in front of an unsaved upload."""
    if name.startswith(UNSAVED):
        return name[len(UNSAVED):].split("__", 1)[-1]
    return name


def load_clean(name):
    """Cleaned dataframe of one file (saved in data/, or unsaved in data/_unsaved); cached until the file changes."""
    folder = UNSAVED_DIR if name.startswith(UNSAVED) else DATA_DIR
    path = os.path.join(folder, os.path.basename(name[len(UNSAVED):] if name.startswith(UNSAVED) else name))
    mtime = os.path.getmtime(path)
    hit = CACHE.get(name)
    if hit and hit[0] == mtime:
        return hit[1], mtime
    df = dp.clean(read_any(path, name))
    CACHE[name] = (mtime, df)
    while len(CACHE) > 8:
        CACHE.pop(next(iter(CACHE)))
    return df, mtime


def resolve(name):
    """-> (dataframe or None, display name, updated text) for the requested file ('' = newest, ALL = combined)."""
    files = list_files()
    if name.startswith(UNSAVED) and os.path.isfile(os.path.join(UNSAVED_DIR, os.path.basename(name[len(UNSAVED):]))):
        try:
            df, mtime = load_clean(name)
            return df, show_name(name) + " (not saved yet)", stamp(mtime)
        except Exception:
            pass
    if not files:
        return None, "", ""
    names = [f["name"] for f in files]
    if name == ALL and len(files) > 1:
        parts = []
        for n in names:
            try:
                parts.append(load_clean(n)[0])
            except Exception:
                app.logger.warning("Skipping unreadable file in combined view: %s", n)
        if parts:
            df = pd.concat(parts, ignore_index=True).drop_duplicates()   # identical rows from overlapping files count once
            return df, "All saved files combined", stamp(files[0]["mtime"])
    if name not in names:
        name = names[0]
    try:
        df, mtime = load_clean(name)
    except Exception:
        return None, name, ""
    return df, name, stamp(mtime)


def current():
    with LOCK:
        df, name, updated = resolve(request.args.get("file", ""))
    if df is None:
        return None, {"source": name, "updated": "", "rows": 0, "from": "", "to": ""}
    d = df["date"]
    return df, {"source": name, "updated": updated, "rows": int(len(df)),
                "from": d.min().strftime("%b %Y"), "to": d.max().strftime("%b %Y")}


def respond(builder):
    """Apply the request's filters, build the payload, attach meta; never leak a stack trace to the browser."""
    df, m = current()
    if df is None:
        return jsonify(empty=True, nodata=True, meta=m)
    try:
        payload = builder(dp.apply_filters(df, request.args))
        payload["meta"] = m
        return jsonify(payload)
    except Exception:
        app.logger.exception("API error")
        return jsonify(error="Something went wrong while calculating this page."), 500


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/filters")
def api_filters():
    df, m = current()
    if df is None:
        return jsonify(years=[], months=[], categories=[], states=[], statuses=[], nodata=True, meta=m)
    return jsonify({**dp.filter_options(df, request.args.get("year")), "meta": m})


@app.route("/api/files")
def api_files():
    """Files you can choose from; `default` is the newest one."""
    files = list_files()
    return jsonify(files=[{"name": f["name"], "updated": stamp(f["mtime"]), "size_kb": max(1, round(f["size"] / 1024))} for f in files],
                   default=files[0]["name"] if files else "")


@app.route("/api/delete", methods=["POST"])
def api_delete():
    name = (request.get_json(silent=True) or {}).get("name", "")
    if name not in [f["name"] for f in list_files()]:      # only exact names from the folder listing are accepted
        return jsonify(error="That file is not available any more."), 404
    with LOCK:
        os.remove(os.path.join(DATA_DIR, name))
        CACHE.pop(name, None)
    return jsonify(ok=True, message=f"Deleted {name}.")


@app.route("/api/overview")
def api_overview():
    return respond(dp.overview)


@app.route("/api/products")
def api_products():
    return respond(dp.products)


@app.route("/api/orders")
def api_orders():
    return respond(dp.orders)


@app.route("/api/geo")
def api_geo():
    return respond(dp.geo)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Accept CSV/XLSX, validate columns and show it. It is only a preview until the user presses Save file."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Please choose a CSV or Excel file."), 400
    stem, ext = os.path.splitext(os.path.basename(f.filename))
    ext = ext.lower()
    if ext not in EXTS:
        return jsonify(error="Unsupported file type. Please upload a .csv or .xlsx file."), 400
    name = (secure_filename(stem) or "upload_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")) + ext
    content = f.read()
    try:
        df = dp.clean(read_any(io.BytesIO(content), name))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception:
        app.logger.exception("Upload failed")
        return jsonify(error="Could not read that file. Please check it is a valid CSV or Excel file."), 400
    stored = f"{uuid.uuid4().hex[:8]}__{name}"        # random prefix keeps different people's uploads apart
    with LOCK:
        path = os.path.join(UNSAVED_DIR, stored)
        with open(path, "wb") as fh:
            fh.write(content)
        CACHE[UNSAVED + stored] = (os.path.getmtime(path), df)
    return jsonify(ok=True, name=UNSAVED + stored,
                   message=f"Loaded {len(df):,} rows from {name}. Click Save file to keep it for next time.")


@app.route("/api/save", methods=["POST"])
def api_save():
    """Move an unsaved upload into the data folder so it is listed under Saved files from now on."""
    name = (request.get_json(silent=True) or {}).get("name", "")
    stored = os.path.basename(name[len(UNSAVED):]) if name.startswith(UNSAVED) else ""
    src = os.path.join(UNSAVED_DIR, stored)
    if not stored or not os.path.isfile(src):
        return jsonify(error="There is no unsaved file to save."), 404
    final = stored.split("__", 1)[-1]
    replaced = os.path.exists(os.path.join(DATA_DIR, final))
    with LOCK:
        os.replace(src, os.path.join(DATA_DIR, final))   # same name as a saved file = replaces it
        CACHE.pop(name, None)
        CACHE.pop(final, None)
    return jsonify(ok=True, name=final, message=(f"Saved {final} (replaced the earlier saved file with the same name)."
                                                   if replaced else f"Saved {final}. Open it any time from Saved files."))


if __name__ == "__main__":
    # Runs on your own computer only (127.0.0.1).
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("DASHBOARD_DEBUG") == "1")
