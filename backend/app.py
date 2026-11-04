"""Flask REST API (Tier 2). Runs under gunicorn on port 5000 behind the internal load balancer."""
import logging
import socket

from azure.core.exceptions import (ClientAuthenticationError, HttpResponseError, ResourceExistsError,
                                   ResourceNotFoundError, ServiceRequestError)
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from routes import orders, products, storage
from services import audit_service as audit
from services.identity_service import token_status
from services import blob_service as bs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
for m in (products, orders, storage):
    app.register_blueprint(m.bp)


@app.get("/api/health")
def health():
    """Shallow by default (LB probe must not depend on Storage). ?deep=1 also checks token + Blob access."""
    body = {"status": "ok", "instance": socket.gethostname()}
    if request.args.get("deep"):
        body["token"] = token_status()
        try:
            body["containers"] = bs.list_containers()
        except Exception as e:  # noqa
            body.update(status="degraded", storage_error=str(e)[:300])
    return jsonify(body)


def _fail(code, error, msg):
    return jsonify({"error": error, "message": msg}), code


@app.errorhandler(Exception)
def handle(e):
    if isinstance(e, HTTPException):
        return _fail(e.code, e.name.upper().replace(" ", "_"), e.description)
    if isinstance(e, ValueError):
        return _fail(400, "BAD_REQUEST", str(e))
    if isinstance(e, ClientAuthenticationError):  # includes CredentialUnavailableError
        log.error("AUTHENTICATION FAILED: %s", e)
        audit.log_event("authentication_failure", {"error": str(e)[:300]})
        return _fail(503, "AUTHENTICATION_FAILED",
                     "Could not obtain a Microsoft Entra token. Is the managed identity enabled on this VMSS?")
    if isinstance(e, ResourceNotFoundError):
        return _fail(404, "NOT_FOUND", "Blob or container not found")
    if isinstance(e, ResourceExistsError):
        return _fail(409, "ALREADY_EXISTS", "Blob already exists")
    if isinstance(e, ServiceRequestError):
        log.error("STORAGE UNREACHABLE: %s", e)
        bs.state["last_status"] = "failed: unreachable"
        return _fail(503, "STORAGE_UNREACHABLE", "Cannot reach Blob endpoint (check private endpoint / DNS / NSG)")
    if isinstance(e, HttpResponseError):
        code = e.status_code or 500
        log.error("STORAGE ERROR %s: %s", code, e)
        bs.state["last_status"] = f"failed: HTTP {code}"
        if code in (401, 403):
            audit.log_event("authentication_failure", {"status": code})
            return _fail(403, "AUTHORIZATION_FAILED",
                         "Storage rejected the request: missing RBAC role (Storage Blob Data Contributor) "
                         "or blocked by network rules / broken private DNS")
        if code == 412:
            return _fail(409, "CONFLICT", "Blob was modified by someone else - reload and retry (ETag mismatch)")
        return _fail(code if 400 <= code < 600 else 500, "STORAGE_ERROR", str(e.message)[:300])
    log.exception("unhandled")
    return _fail(500, "INTERNAL_ERROR", "Unexpected server error")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
