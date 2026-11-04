import uuid
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(data, existing=None):
    """Validate input and return the product dict that is stored as products/{id}.json."""
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("name is required")
    try:
        price, qty = float(data.get("price")), int(data.get("quantity"))
    except (TypeError, ValueError):
        raise ValueError("price and quantity must be numbers")
    if price < 0 or qty < 0:
        raise ValueError("price and quantity must be >= 0")
    p = dict(existing or {})
    p.update(id=p.get("id") or "PROD-" + uuid.uuid4().hex[:8].upper(), name=name,
             category=str(data.get("category") or "General").strip(), price=price, quantity=qty,
             description=str(data.get("description", "")).strip()[:1000],
             image_url=p.get("image_url", ""))
    p.setdefault("created_at", now())
    p["updated_at"] = now()
    return p
