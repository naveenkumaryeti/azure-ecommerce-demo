import re
import uuid

from flask import Blueprint, jsonify, request

import config
from models import product as pm
from services import audit_service as audit
from services import blob_service as bs

bp = Blueprint("products", __name__)
ID_RE = re.compile(r"^[A-Za-z0-9-]{3,40}$")
P = config.CONTAINERS["products"]
IMG = config.CONTAINERS["images"]


def _id(pid):
    if not ID_RE.match(pid):
        raise ValueError("invalid product id")
    return f"{pid}.json"


def _out(d, etag):
    return {**d, "etag": etag}


def _magic_ok(data, ctype):
    return ((ctype == "image/jpeg" and data[:3] == b"\xff\xd8\xff") or
            (ctype == "image/png" and data[:4] == b"\x89PNG") or
            (ctype == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))


@bp.get("/api/products")
def list_products():
    items = [_out(d, e) for d, e in bs.list_json(P)]
    return jsonify(sorted(items, key=lambda p: p.get("created_at", ""), reverse=True))


@bp.get("/api/products/<pid>")
def get_product(pid):
    d, e = bs.get_json(P, _id(pid))
    return jsonify(_out(d, e))


@bp.post("/api/products")
def create_product():
    p = pm.build(request.get_json(silent=True) or {})
    etag = bs.put_json(P, f"{p['id']}.json", p, create_only=True)
    audit.log_event("product_created", {"id": p["id"], "name": p["name"]})
    return jsonify(_out(p, etag)), 201


@bp.put("/api/products/<pid>")
def update_product(pid):
    name = _id(pid)
    existing, current = bs.get_json(P, name)
    etag = request.headers.get("If-Match") or current  # client ETag wins -> detects concurrent edits
    p = pm.build(request.get_json(silent=True) or {}, existing)
    new = bs.put_json(P, name, p, etag=etag)
    audit.log_event("product_updated", {"id": pid})
    return jsonify(_out(p, new))


@bp.delete("/api/products/<pid>")
def delete_product(pid):
    name = _id(pid)
    existing, current = bs.get_json(P, name)
    bs.delete(P, name, etag=request.headers.get("If-Match") or current)
    if existing.get("image_url"):
        try:
            bs.delete(IMG, existing["image_url"].split("/")[-1])
        except Exception:  # noqa
            pass
    audit.log_event("product_deleted", {"id": pid})
    return jsonify({"deleted": pid})


@bp.post("/api/products/<pid>/image")
def upload_image(pid):
    name = _id(pid)
    f = request.files.get("image")
    if not f:
        raise ValueError("image file is required (form field 'image')")
    ctype = f.mimetype
    if ctype not in config.ALLOWED_IMAGE_TYPES:
        raise ValueError("only JPG, PNG and WebP images are allowed")
    data = f.read(config.MAX_IMAGE_BYTES + 1)
    if len(data) > config.MAX_IMAGE_BYTES:
        raise ValueError("image larger than 5 MB")
    if not _magic_ok(data, ctype):
        raise ValueError("file content does not match its image type")
    existing, etag = bs.get_json(P, name)
    img_name = f"{pid}-{uuid.uuid4().hex[:8]}.{config.ALLOWED_IMAGE_TYPES[ctype]}"
    bs.upload_blob(IMG, img_name, data, ctype)
    old = existing.get("image_url")
    existing["image_url"] = f"{IMG}/{img_name}"
    existing["updated_at"] = pm.now()
    new = bs.put_json(P, name, existing, etag=etag)
    if old:
        try:
            bs.delete(IMG, old.split("/")[-1])
        except Exception:  # noqa
            pass
    audit.log_event("product_image_uploaded", {"id": pid, "image": img_name})
    return jsonify(_out(existing, new))
