import uuid
from models.product import now


def build(data, products):
    """products: {id: product}. Returns the order dict stored as orders/{id}.json."""
    items, cust = data.get("items") or [], data.get("customer") or {}
    if not items:
        raise ValueError("cart is empty")
    for k in ("name", "email", "address"):
        if not str(cust.get(k, "")).strip():
            raise ValueError(f"customer {k} is required")
    lines, total = [], 0.0
    for it in items:
        p = products.get(it.get("id"))
        qty = int(it.get("quantity", 0))
        if not p or qty < 1:
            raise ValueError("invalid item in cart")
        if p["quantity"] < qty:
            raise ValueError(f"insufficient stock for {p['name']}")
        lines.append({"product_id": p["id"], "name": p["name"], "price": p["price"], "quantity": qty})
        total += p["price"] * qty
    return {"id": "ORD-" + uuid.uuid4().hex[:10].upper(),
            "customer": {k: str(cust[k]).strip() for k in ("name", "email", "address")},
            "items": lines, "total": round(total, 2), "status": "PLACED", "created_at": now()}
