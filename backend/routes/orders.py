from flask import Blueprint, jsonify, request

import config
from models import order as om
from services import audit_service as audit
from services import blob_service as bs

bp = Blueprint("orders", __name__)
P, O = config.CONTAINERS["products"], config.CONTAINERS["orders"]


@bp.get("/api/orders")
def list_orders():
    orders = [d for d, _ in bs.list_json(O)]
    return jsonify(sorted(orders, key=lambda o: o["created_at"], reverse=True))


@bp.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    loaded = {}
    for it in data.get("items") or []:
        try:
            loaded[it["id"]] = bs.get_json(P, f"{it['id']}.json")
        except Exception:  # noqa
            raise ValueError("unknown product in cart")
    order = om.build(data, {k: v[0] for k, v in loaded.items()})
    done = []
    try:  # decrement stock with ETag guard; roll back if anything conflicts
        for line in order["items"]:
            prod, etag = loaded[line["product_id"]]
            prod = {**prod, "quantity": prod["quantity"] - line["quantity"]}
            bs.put_json(P, f"{prod['id']}.json", prod, etag=etag)
            done.append(line)
        bs.put_json(O, f"{order['id']}.json", order, create_only=True)
    except Exception:
        for line in done:
            p, e = bs.get_json(P, f"{line['product_id']}.json")
            p["quantity"] += line["quantity"]
            bs.put_json(P, f"{p['id']}.json", p, etag=e)
        raise
    audit.log_event("order_created", {"id": order["id"], "total": order["total"]})
    return jsonify(order), 201
