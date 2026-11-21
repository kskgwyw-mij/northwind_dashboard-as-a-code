from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_plotly


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


app_ui = ui.page_fluid(
    ui.h2("Northwind Sales Dashboard"),
    ui.tags.p(
        "Interactive dashboard over the Northwind Access dataset ",
        ui.tags.code("(CSV export) — built with Shiny for Python and Plotly."),
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_select(
                "category",
                "Product category",
                choices=CATEGORY_NAMES,
                selected="All",
            ),
            ui.input_select(
                "employee",
                "Sales employee",
                choices=EMPLOYEE_NAMES,
                selected="All",
            ),
            ui.input_date_range(
                "dates",
                "Order date range",
                start=DATE_MIN,
                end=DATE_MAX,
                min=DATE_MIN,
                max=DATE_MAX,
            ),
            ui.input_switch("exclude_discontinued", "Exclude discontinued", True),
        ),
        ui.row(
            ui.column(
                3,
                ui.value_box("Total revenue", ui.output_ui("rev")),
            ),
            ui.column(
                3,
                ui.value_box("Orders", ui.output_ui("orders")),
            ),
            ui.column(
                3,
                ui.value_box("Line items", ui.output_ui("lines")),
            ),
            ui.column(
                3,
                ui.value_box("Avg. order value", ui.output_ui("aov")),
            ),
        ),
        ui.row(
            ui.column(
                6,
                ui.card(
                    ui.card_header("Revenue over time"),
                    output_widget("revenue_time"),
                ),
            ),
            ui.column(
                6,
                ui.card(
                    ui.card_header("Revenue by category"),
                    output_widget("category_bar"),
                ),
            ),
        ),
        ui.row(
            ui.column(
                12,
                ui.card(
                    ui.card_header("Revenue by ship country"),
                    output_widget("revenue_country"),
                ),
            ),
        ),
        ui.row(
            ui.column(
                6,
                ui.card(
                    ui.card_header("Top 10 products by revenue"),
                    output_widget("top_products"),
                ),
            ),
            ui.column(
                6,
                ui.card(
                    ui.card_header("Top 10 customers by revenue"),
                    output_widget("top_customers"),
                ),
            ),
        ),
        ui.row(
            ui.column(
                6,
                ui.card(
                    ui.card_header("Revenue by employee"),
                    output_widget("employee_bar"),
                ),
            ),
            ui.column(
                6,
                ui.card(
                    ui.card_header("Order delivery performance"),
                    output_widget("delivery"),
                ),
            ),
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
        return f"{len(df()['OrderID'].nunique()):,}"

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
        fig = px.bar(monthly, x="Month", y="Revenue")
        fig.update_layout(margin=dict(t=20, b=10), yaxis_title="Revenue ($)")
        return fig

    @render_plotly
    def category_bar():
        d = df()
        if d.empty:
            return go.Figure()
        cat = d.groupby("CategoryName", as_index=False)["Revenue"].sum()
        cat = cat.sort_values("Revenue")
        fig = px.bar(cat, x="Revenue", y="CategoryName", orientation="h")
        fig.update_layout(margin=dict(t=20, b=10), xaxis_title="Revenue ($)")
        return fig

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
        fig.update_layout(margin=dict(t=20, b=10), xaxis_title="Revenue ($)")
        return fig

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
        fig.update_layout(margin=dict(t=20, b=10), xaxis_title="Revenue ($)")
        return fig

    @render_plotly
    def revenue_country():
        d = df()
        if d.empty:
            return go.Figure()
        country = d.groupby("ShipCountry", as_index=False)["Revenue"].sum()
        country = country.sort_values("Revenue", ascending=False)
        fig = px.bar(country, x="ShipCountry", y="Revenue")
        fig.update_layout(margin=dict(t=20, b=10), yaxis_title="Revenue ($)")
        return fig

    @render_plotly
    def employee_bar():
        d = df()
        if d.empty:
            return go.Figure()
        emp = d.groupby("Employee", as_index=False)["Revenue"].sum()
        emp = emp.sort_values("Revenue", ascending=False)
        fig = px.bar(emp, x="Employee", y="Revenue")
        fig.update_layout(margin=dict(t=20, b=10), yaxis_title="Revenue ($)")
        return fig

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
        fig.update_layout(
            margin=dict(t=20, b=10),
            xaxis_title="Days from order to shipment (capped at 30)",
            yaxis_title="Orders",
        )
        return fig


app = App(app_ui, server)
