# Amazon India Dashboard

A simple management dashboard for Manoj to submit to Ravi: Sales, Profit, Products, Orders, Order Status,
Payment, Fulfillment and Geographic performance in one place, with an auto-written "Key Insight" under every chart.

## Setup and run (Python 3.10+)
```bash
cd amazon_india_dashboard
pip install -r requirements.txt
python app.py                       # then open http://127.0.0.1:5000
```
The `data` folder starts empty. Run the app, click **Upload Data** and choose your .xlsx or .csv. Every file you upload is kept in `data`, and the **Data file** box at the top lets you switch between them (filters reset when you switch). Uploading a file with the same name replaces that one; other files stay. To remove a file, delete it from the `data` folder. At start-up the newest file is shown.
You can also swap files with **Upload Data** in the browser (the uploaded file replaces the one in `data`).

## Using the dashboard
1. **Upload Data** opens a file as a preview. The **Data file** box then says "not saved yet" (orange).
2. **Save file** keeps it in the `data` folder, so it is there next time you open the dashboard. An upload you do not save
   is gone when the app restarts (the browser warns you before you leave the page).
3. **Saved files** lists every file you saved, with date and size. **Open** shows that file's dashboard; **Delete** removes it
   (asks first). "All saved files combined" merges them (identical rows count once). When the app starts it opens the newest saved file.
4. **Filters:** Year, Month, Category, State, Order Status and a From/To date range update every KPI and chart.
   **Reset Filters** clears them; opening another file also resets them. Each browser tab keeps its own file choice.
5. Required columns (matched ignoring case, spaces, underscores and a trailing "_INR"): Order Date, Category, Product Name,
   Quantity, Sales, Profit, Order Status, Payment Method, Fulfillment Method, State (Order ID optional).
   A bad file gives a clear message and nothing changes. Saving a file with the same name replaces that saved file.
6. **Save image** on each chart downloads it as a PNG. **Download PDF / Print** prints the four tabs on landscape A4
   (choose "Save as PDF"). **Dark mode** is in the top bar.

## How numbers are defined
Sales and Profit include every order in the filter. Returned/Cancelled sales are reported as "revenue at risk"
on tab 3. Rates are based on unique order IDs. Cleaning: unparseable dates or sales rows are dropped, missing
quantity becomes 1, missing profit becomes 0, negative profit is kept.

## Project layout
`app.py` routes - `data_processing.py` cleaning/KPIs - `insights.py` sentences - 
`templates/index.html` - `static/css/style.css` - `static/js/dashboard.js`

## What the screens look like
- **Top bar:** SAPPHiRE IQ logo left, title centre, amazon wordmark right, filters and buttons below, gradient line underneath.
- **Tab 1:** six KPI cards, then a bar+line chart of monthly sales vs profit.
- **Tab 2:** three category charts (sales, profit with red loss bars, units donut), top-10 product bars plus a table with red "Needs attention" rows.
- **Tab 3:** six order KPIs, status donut, returns vs cancellations by category.
- **Tab 4:** payment and fulfillment bar charts, plus a state ranking with a Sales / Profit / Orders toggle.
