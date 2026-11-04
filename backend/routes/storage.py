"""Dashboard + Blob Explorer API. Browser never sees credentials; it only talks to these routes."""
import json
import os
import socket

from flask import Blueprint, Response, jsonify, request
from werkzeug.utils import secure_filename

import config
from services import audit_service as audit
from services import blob_service as bs
from services.identity_service import token_status

bp = Blueprint("storage", __name__)
EXT_TYPES = {".json": "application/json", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".png": "image/png", ".webp": "image/webp"}


def _container(c):
    if c not in config.CONTAINERS.values():
        raise ValueError("unknown container")
    return c


@bp.get("/api/storage/info")
def info():
    counts, last_upload = bs.stats()
    return jsonify({"account": config.STORAGE_ACCOUNT_NAME, "endpoint": config.BLOB_ENDPOINT,
                    "containers": list(config.CONTAINERS.values()),
                    "total_products": counts["products"], "total_images": counts["images"],
                    "total_orders": counts["orders"], "total_audit_events": counts["audit"],
                    "last_upload": last_upload, "last_success_op": bs.state["last_success_op"],
                    "last_success_at": bs.state["last_success_at"], "upload_status": bs.state["last_status"],
                    "auth": "Managed Identity (DefaultAzureCredential)", "token": token_status(),
                    "served_by": socket.gethostname()})


@bp.get("/api/storage/containers")
def containers():
    return jsonify(bs.list_containers())


@bp.get("/api/storage/containers/<c>/blobs")
def blobs(c):
    return jsonify(bs.list_blobs(_container(c)))


@bp.get("/api/storage/blob/<c>/<path:name>")
def blob(c, name):
    data, ctype = bs.download(_container(c), name)
    headers = {"X-Content-Type-Options": "nosniff"}
    if request.args.get("download"):
        headers["Content-Disposition"] = f'attachment; filename="{os.path.basename(name)}"'
    return Response(data, mimetype=ctype, headers=headers)


@bp.get("/api/images/<path:name>")
def image(name):
    data, ctype = bs.download(config.CONTAINERS["images"], name)
    return Response(data, mimetype=ctype, headers={"Cache-Control": "public, max-age=300",
                                                    "X-Content-Type-Options": "nosniff"})


@bp.post("/api/storage/upload")
def upload():
    c = _container(request.form.get("container", ""))
    f = request.files.get("file")
    if not f:
        raise ValueError("file is required")
    name = secure_filename(f.filename or "")
    ctype = EXT_TYPES.get(os.path.splitext(name)[1].lower())
    if not name or not ctype:
        raise ValueError("allowed: .json .jpg .png .webp")
    data = f.read(config.MAX_IMAGE_BYTES + 1)
    if len(data) > config.MAX_IMAGE_BYTES:
        raise ValueError("file larger than 5 MB")
    if ctype == "application/json":
        json.loads(data)  # must be valid JSON
    bs.upload_blob(c, name, data, ctype)
    audit.log_event("explorer_upload", {"container": c, "name": name})
    return jsonify({"uploaded": f"{c}/{name}"}), 201


@bp.delete("/api/storage/blob/<c>/<path:name>")
def delete_blob(c, name):
    c = _container(c)
    if not (name.startswith("test-") or c == config.CONTAINERS["backups"]):
        raise ValueError("Explorer may only delete 'test-*' blobs or blobs in application-backups")
    bs.delete(c, name)
    audit.log_event("explorer_delete", {"container": c, "name": name})
    return jsonify({"deleted": f"{c}/{name}"})
