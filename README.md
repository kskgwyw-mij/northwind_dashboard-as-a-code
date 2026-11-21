# northwind_dashboard-as-a-code
Data dive build a dashboard without powerbi with an access database as source.

The Northwind Traders Access database (`Northwind.MDB`) is exported to CSVs;
see `schema.md` for the table relations and ERD.

## Interactive dashboard (Shiny for Python + Plotly)

```bash
pip install -r requirements.txt
shiny run app.py --reload
```

Then open the printed URL (default http://127.0.0.1:8000).

Features:

- KPIs: total revenue, orders, line items, average order value
- Revenue over time (monthly), by category, and by sales employee
- Top 10 products and top 10 customers by revenue
- Order delivery performance (days from order to shipment)
- Filters: product category, sales employee, order date range,
  and an option to exclude discontinued products

Revenue is computed per line item as
`UnitPrice * Quantity * (1 - Discount)`.
