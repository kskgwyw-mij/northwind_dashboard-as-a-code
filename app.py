from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_plotly

import pandas as pd
import plotly.express as px
from starlette.middleware.gzip import GZipMiddleware
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_data():
    orders = pd.read_csv(
        "Orders.csv", parse_dates=["OrderDate", "RequiredDate", "ShippedDate"]
    )
    details = pd.read_csv("Order_Details.csv")
    products = pd.read_csv("Products.csv")
    customers = pd.read_csv("Customers.csv")
    employees = pd.read_csv("Employees.csv")
    categories = pd.read_csv("Categories.csv")
    shippers = pd.read_csv("Shippers.csv")

    lines = details.merge(orders, on="OrderID").merge(products, on="ProductID")
    lines = lines.merge(categories, on="CategoryID")
    lines = lines.merge(
        employees[["EmployeeID", "LastName", "FirstName"]], on="EmployeeID"
    )
    lines["Employee"] = lines["LastName"] + ", " + lines["FirstName"]
    lines = lines.merge(
        shippers, left_on="ShipVia", right_on="ShipperID", how="left"
    )
    lines["Shipper"] = lines["CompanyName"]

    orders = orders.merge(customers, on="CustomerID")
    orders = orders.merge(employees, on="EmployeeID")
    orders["Employee"] = orders["LastName"] + ", " + orders["FirstName"]

    lines["Revenue"] = (
        lines["UnitPrice_x"] * lines["Quantity"] * (1 - lines["Discount"])
    )
    return orders, lines


ORDERS, LINES = load_data()

CATEGORY_NAMES = ["All"] + sorted(LINES["CategoryName"].unique().tolist())
EMPLOYEE_NAMES = ["All"] + sorted(LINES["Employee"].unique().tolist())

DATE_MIN = ORDERS["OrderDate"].min().date()
DATE_MAX = ORDERS["OrderDate"].max().date()

COMPACT = dict(
    height=205,
    margin=dict(l=36, r=12, t=6, b=22),
    font=dict(size=9),
    showlegend=False,
    hoverlabel=dict(font=dict(size=10)),
)

ZOOM_JS = """
document.addEventListener('contextmenu', function (ev) {
  const gd = ev.target.closest && ev.target.closest('.js-plotly-plot');
  if (!gd) return;
  ev.preventDefault();
  const ax = gd._fullLayout && gd._fullLayout.xaxis;
  if (!ax || !ax.range) return;
  const [a, b] = ax.range.map(Number);
  const c = (a + b) / 2;
  const half = (b - a) * (ev.shiftKey ? 0.75 : 0.25);
  Plotly.relayout(gd, {'xaxis.range': [c - half, c + half]});
}, true);
document.addEventListener('dblclick', function (ev) {
  const gd = ev.target.closest && ev.target.closest('.js-plotly-plot');
  if (!gd) return;
  Plotly.relayout(gd, {'xaxis.autorange': true});
}, true);
"""

COMPACT_CSS = """
body { font-size: 0.85rem; padding: 0.4rem 0.8rem; }
h2 { font-size: 1.15rem; margin: 0.1rem 0; }
.card { border: none; box-shadow: 0 1px 3px rgba(0,0,0,.18);
        margin-bottom: 0.35rem; }
.card-header { font-size: 0.78rem; font-weight: 600; padding: 0.2rem 0.6rem; }
.card-body { padding: 0.15rem 0.3rem 0.3rem 0.3rem; }
.value-box { padding: 0.25rem 0.6rem; min-height: 0; }
.value-box h5 { font-size: 0.7rem; opacity: 0.8; margin-bottom: 0; }
.value-box-value { font-size: 1rem !important; }
.hint { font-size: 0.7rem; color: #888; margin: 0 0 0.3rem 0; }
.js-plotly-plot { cursor: crosshair; }
"""


def filter_lines(cat, emp, start, end):
    df = LINES
    if cat != "All":
        df = df[df["CategoryName"] == cat]
    if emp != "All":
        df = df[df["Employee"] == emp]
    mask = (df["OrderDate"] >= pd.Timestamp(start)) & (
        df["OrderDate"] <= pd.Timestamp(end)
    )
    return df[mask]


def compact_fig(fig, ytitle=None):
    fig.update_layout(**COMPACT)
    if ytitle:
        fig.update_yaxes(title_text=ytitle, title_font=dict(size=9))
    else:
        fig.update_yaxes(title=None, tickfont=dict(size=9))
    fig.update_xaxes(title=None, tickfont=dict(size=9))
    return fig


app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.style(COMPACT_CSS),
        ui.tags.script(ZOOM_JS),
    ),
    ui.h2("Northwind Sales Dashboard"),
    ui.tags.p(
        "The Northwind Access dataset (CSV export)",
        ui.tags.code(" — Shiny for Python + Plotly"),
        ui.tags.em(
            " · Right-click a chart to zoom in on center (Shift = out, double-click to reset)"
        ),
        ui.tags.br(),
        ui.tags.span("", class_="hint"),
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_select(
                "category", "Category", choices=CATEGORY_NAMES, selected="All"
            ),
            ui.input_select(
                "employee",
                "Employee",
                choices=EMPLOYEE_NAMES,
                selected="All",
            ),
            ui.input_date_range(
                "dates",
                "Order dates",
                start=DATE_MIN,
                end=DATE_MAX,
                min=DATE_MIN,
                max=DATE_MAX,
            ),
            ui.input_switch(
                "exclude_discontinued", "Exclude discontinued", True
            ),
            width=210,
        ),
        ui.layout_columns(
            ui.value_box("Revenue", ui.output_ui("rev")),
            ui.value_box("Orders", ui.output_ui("orders")),
            ui.value_box("Line items", ui.output_ui("lines")),
            ui.value_box("Avg. order value", ui.output_ui("aov")),
            col_widths=(3, 3, 3, 3),
        ),
        ui.layout_columns(
            ui.card(
                ui.card_header("Revenue over time (bars) with freight $ / freight %"),
                output_widget("revenue_time"),
                fillable=True,
            ),
            ui.card(
                ui.card_header("Revenue by category"),
                output_widget("category_bar"),
                fillable=True,
            ),
            ui.card(
                ui.card_header("Revenue by ship country"),
                output_widget("revenue_country"),
                fillable=True,
            ),
            col_widths=(4, 4, 4),
        ),
        ui.layout_columns(
            ui.card(
                ui.card_header("Revenue by shipper"),
                output_widget("revenue_shipper"),
                fillable=True,
            ),
            ui.card(
                ui.card_header("Revenue by employee"),
                output_widget("employee_bar"),
                fillable=True,
            ),
            ui.card(
                ui.card_header("Top 10 products"),
                output_widget("top_products"),
                fillable=True,
            ),
            col_widths=(4, 4, 4),
        ),
        ui.layout_columns(
            ui.card(
                ui.card_header("Top 10 customers"),
                output_widget("top_customers"),
                fillable=True,
            ),
            ui.card(
                ui.card_header("Order delivery (days to ship)"),
                output_widget("delivery"),
                fillable=True,
            ),
            col_widths=(6, 6),
        ),
    ),
)


def server(input, output, session):
    @reactive.calc
    def df():
        start, end = input.dates()
        d = filter_lines(input.category(), input.employee(), start, end)
        if input.exclude_discontinued():
            d = d[d["Discontinued"].astype(str) != "True"]
        return d

    @reactive.calc
    def base_revenue():
        start, end = input.dates()
        mask = (
            ORDERS["OrderDate"] >= pd.Timestamp(start)
        ) & (ORDERS["OrderDate"] <= pd.Timestamp(end))
        o = ORDERS[mask]
        if input.employee() != "All":
            o = o[o["Employee"] == input.employee()]
        return o

    def fmt_money(v):
        return f"${v:,.0f}"

    @render.ui
    def rev():
        return fmt_money(df()["Revenue"].sum())

    @render.ui
    def orders():
        return f"{df()['OrderID'].nunique():,}"

    @render.ui
    def lines():
        return f"{len(df()):,}"

    @render.ui
    def aov():
        d = df()
        n = d["OrderID"].nunique()
        return fmt_money(d["Revenue"].sum() / n) if n else "—"

    @render_plotly
    def revenue_time():
        d = df().copy()
        if d.empty:
            return go.Figure()
        d["Month"] = d["OrderDate"].dt.to_period("M").dt.to_timestamp()
        monthly = d.groupby("Month", as_index=False)["Revenue"].sum()

        o = base_revenue().copy()
        o["Month"] = o["OrderDate"].dt.to_period("M").dt.to_timestamp()
        freight = o.groupby("Month", as_index=False)["Freight"].sum()

        ratio = freight.merge(monthly, on="Month", how="inner")
        ratio["FreightPct"] = 100 * ratio["Freight"] / ratio["Revenue"]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(
            x=monthly["Month"],
            y=monthly["Revenue"],
            name="Revenue",
            customdata=ratio.set_index("Month")["FreightPct"]
            .reindex(monthly["Month"])
            .values,
            hovertemplate=(
                "Revenue: $%{y:,.0f}"
                "<br>Freight: %{customdata:.2f}%<extra></extra>"
            ),
        )
        fig.add_scatter(
            x=ratio["Month"],
            y=ratio["Freight"],
            name="Freight ($)",
            mode="lines+markers",
            line=dict(color="firebrick"),
            hovertemplate="Freight: $%{y:,.2f}<extra>Freight ($)</extra>",
            secondary_y=True,
        )
        fig.add_scatter(
            x=ratio["Month"],
            y=ratio["FreightPct"],
            name="Freight %",
            mode="lines+markers",
            line=dict(color="dimgray"),
            customdata=ratio.set_index("Month")["Revenue"].values,
            hovertemplate=(
                "Freight: %{y:.2f}% of revenue"
                " (%{customdata:$,.0f})<extra>Freight %</extra>"
            ),
            yaxis="y3",
        )
        fig.update_layout(
            margin=dict(l=36, r=30, t=6, b=22),
            height=205,
            font=dict(size=9),
            legend=dict(orientation="h", font=dict(size=9), y=1.14),
            hovermode="x unified",
            yaxis3=dict(
                side="right", ticksuffix="%", showgrid=False,
                tickfont=dict(size=9),
            ),
        )
        fig.update_yaxes(title_text="Revenue ($)", secondary_y=False,
                         title_font=dict(size=9), tickfont=dict(size=9))
        fig.update_yaxes(title_text="Freight ($)", secondary_y=True,
                         title_font=dict(size=9), tickfont=dict(size=9))
        fig.update_xaxes(title=None, tickfont=dict(size=9))
        return fig

    @render_plotly
    def category_bar():
        d = df()
        if d.empty:
            return go.Figure()
        cat = d.groupby("CategoryName", as_index=False)["Revenue"].sum()
        cat = cat.sort_values("Revenue")
        fig = px.bar(cat, x="Revenue", y="CategoryName", orientation="h")
        fig.update_traces(hovertemplate="%{y}: $%{x:,.0f}<extra></extra>")
        return compact_fig(fig)

    @render_plotly
    def top_products():
        d = df()
        if d.empty:
            return go.Figure()
        top = (
            d.groupby("ProductName", as_index=False)["Revenue"]
            .sum()
            .nlargest(10, "Revenue")
            .sort_values("Revenue")
        )
        fig = px.bar(top, x="Revenue", y="ProductName", orientation="h")
        fig.update_traces(hovertemplate="%{y}: $%{x:,.0f}<extra></extra>")
        fig.update_yaxes(tickfont=dict(size=8))
        return compact_fig(fig)

    @render_plotly
    def top_customers():
        o = base_revenue()
        rev_by_customer = (
            df().groupby("CustomerID", as_index=False)["Revenue"].sum()
        )
        cust = o[["CustomerID", "CompanyName"]].drop_duplicates()
        merged = rev_by_customer.merge(cust, on="CustomerID")
        merged = merged.nlargest(10, "Revenue").sort_values("Revenue")
        fig = px.bar(merged, x="Revenue", y="CompanyName", orientation="h")
        fig.update_traces(hovertemplate="%{y}: $%{x:,.0f}<extra></extra>")
        fig.update_yaxes(tickfont=dict(size=8))
        return compact_fig(fig)

    @render_plotly
    def employee_bar():
        d = df()
        if d.empty:
            return go.Figure()
        emp = d.groupby("Employee", as_index=False)["Revenue"].sum()
        emp["Employee"] = emp["Employee"].str.split(", ").str[1]
        emp = emp.sort_values("Revenue", ascending=False)
        fig = px.bar(emp, x="Employee", y="Revenue")
        fig.update_traces(hovertemplate="%{x}: $%{y:,.0f}<extra></extra>")
        return compact_fig(fig)

    @render_plotly
    def revenue_country():
        d = df()
        if d.empty:
            return go.Figure()
        country = d.groupby("ShipCountry", as_index=False)["Revenue"].sum()
        country = country.sort_values(
            "Revenue", ascending=True
        ).tail(10)
        fig = px.bar(country, x="Revenue", y="ShipCountry", orientation="h")
        fig.update_traces(hovertemplate="%{y}: $%{x:,.0f}<extra></extra>")
        return compact_fig(fig)

    @render_plotly
    def revenue_shipper():
        d = df()
        if d.empty:
            return go.Figure()
        sh = d.groupby("Shipper", as_index=False)["Revenue"].sum()
        sh = sh.sort_values("Revenue", ascending=True)
        fig = px.bar(sh, x="Revenue", y="Shipper", orientation="h")
        fig.update_traces(hovertemplate="%{y}: $%{x:,.0f}<extra></extra>")
        return compact_fig(fig)

    @render_plotly
    def delivery():
        o = base_revenue().copy()
        if o.empty:
            return go.Figure()
        shipped = o.dropna(subset=["ShippedDate"]).copy()
        shipped["Delay"] = (
            shipped["ShippedDate"] - shipped["OrderDate"]
        ).dt.days
        counts = shipped["Delay"].clip(upper=30).value_counts().sort_index()
        fig = px.bar(x=counts.index, y=counts.values)
        fig.update_traces(hovertemplate="%{x} days: %{y} orders<extra></extra>")
        return compact_fig(fig)


class GzippedApp(App):
    def init_starlette_app(self):
        starlette_app = super().init_starlette_app()
        starlette_app.add_middleware(GZipMiddleware, minimum_size=1024)
        return starlette_app


app = GzippedApp(app_ui, server)
