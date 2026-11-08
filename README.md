# celers

**Requires the Celers app** ([celers.org](https://celers.org)): this package writes and reads automations; the app
runs them.

Write [Celers](https://celers.org) automations in Python. A flow you write is the same board the Celers canvas
shows: open it in the app, run it, schedule it, or let someone who does not write code change it there. A board
built in the app comes back as Python just as easily.

```python
from celers import Flow, Client

flow = Flow("Daily orders")
orders = flow.excel_read("orders.xlsx", sheet="Orders", variable="orders")
with flow.for_each(orders) as row:
    flow.navigate("https://shop.example/orders")
    flow.log(f"Order {row['Order']}")
flow.ask_person("Send the report?", kind="approve")

flow.save("daily_orders.celers.json")   # a file the app opens
Client().upload(flow)                   # or straight into the Celers app on this computer
```

- `celers.steps()` (or `celers steps` in a terminal) lists every step the canvas has, with its settings. A step or
  setting Celers does not have is refused when you write it, not when the board opens.
- `flow.step(type, label, **settings)` adds any step; `excel_read`, `excel_write`, `navigate`, `ask_person`, `log`,
  `for_each` and `when` are shortcuts.
- `Flow.load("board.json").to_python()` (or `celers python board.json`) writes a board as code.
- `Client(url, token)` reaches the Celers app: `CELERS_URL` and `CELERS_TOKEN` by default. The app runs the
  automations under your Celers plan; this package runs nothing itself and needs no other package.

Desktop and Citrix steps run on Windows computers with the Celers app.
