"""Celers: automations in Python that are the same boards the Celers canvas shows (https://celers.org).

    from celers import Flow, Client

    flow = Flow("Daily orders")
    orders = flow.excel_read("orders.xlsx", sheet="Orders", variable="orders")
    with flow.for_each(orders) as row:
        flow.log(f"Order {row['Order']}")
    Client().upload(flow)     # a project in the Celers app on this computer

``celers.steps()`` lists every step and its settings. ``Flow.load(path).to_python()`` turns a board saved from the
app back into code.
"""
from .client import CelersError, Client
from .flow import Flow, FlowError, Var, steps, to_python

__version__ = "0.1.0"
__all__ = ["Flow", "FlowError", "Var", "steps", "to_python", "Client", "CelersError", "__version__"]
