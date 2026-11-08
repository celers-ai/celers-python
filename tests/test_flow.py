import json

import pytest

from celers import Flow, FlowError, steps, to_python


def _orders():
    flow = Flow("Daily orders")
    orders = flow.excel_read("orders.xlsx", sheet="Orders", variable="orders")
    with flow.for_each(orders) as row:
        flow.navigate("https://shop.example/orders")
        flow.log(f"Order {row['Order']}")
    flow.ask_person("Send the report?", kind="approve")
    return flow


def test_a_flow_is_a_board_with_its_steps_linked_in_order():
    g = _orders().graph()
    kinds = [n["type"] for n in g["nodes"]]
    assert kinds == ["excel_read", "for", "navigate", "log", "ask_person"]
    links = {(e["source"], e["sourceHandle"], e["target"]) for e in g["edges"]}
    assert links == {("py-excel_read-1", None, "py-for-1"), ("py-for-1", "body", "py-navigate-1"),
                     ("py-navigate-1", None, "py-log-1"), ("py-for-1", "next", "py-ask_person-1")}
    log = next(n for n in g["nodes"] if n["type"] == "log")
    assert log["data"]["config"]["message"] == 'Order {{row["Order"]}}'
    loop = next(n for n in g["nodes"] if n["type"] == "for")
    assert loop["data"]["config"]["loop"] == {"iterable": "orders", "variable": "row"}


def test_a_step_or_setting_the_canvas_does_not_have_is_refused():
    f = Flow("x")
    with pytest.raises(FlowError, match="no step"):
        f.step("teleport")
    with pytest.raises(FlowError, match="does not take colour"):
        f.step("navigate", url="https://a.example", colour="red")
    assert "navigate" in steps() and "url" in steps()["navigate"]["settings"]


def test_a_board_saved_comes_back_and_turns_into_python_that_makes_it_again(tmp_path):
    flow = _orders()
    path = flow.save(tmp_path / "orders.celers.json")
    again = Flow.load(path)
    assert again.graph() == flow.graph() and again.name == "Daily orders"
    code = to_python(again)
    assert "with flow.for_each('orders'" in code and "flow.step('ask_person'" in code
    scope = {}
    exec(compile(code.replace("flow.save(", "_saved = ("), "board.py", "exec"), scope)
    remade = scope["flow"].graph()
    assert [n["type"] for n in remade["nodes"]] == [n["type"] for n in flow.graph()["nodes"]]
    assert len(remade["edges"]) == len(flow.graph()["edges"])


def test_a_condition_takes_its_steps_on_its_true_side():
    f = Flow("COD")
    with f.when({"left": "{{row['Payment']}}", "operator": "==", "right": "COD"}):
        f.log("Call to confirm")
    f.log("Done")
    g = f.graph()
    assert {(e["source"], e["sourceHandle"], e["target"]) for e in g["edges"]} == {
        ("py-if-1", "true", "py-log-1"), ("py-if-1", "next", "py-log-2")}
    json.dumps(g)
