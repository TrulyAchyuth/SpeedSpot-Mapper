"""The JSON response envelope used by every API endpoint (see docs/API.md).

Success: {"data": ..., "meta": {...}}
Error:   {"error": {"code": "...", "message": "...", "details": {...}}}
"""
from flask import jsonify


class ApiError(Exception):
    """Raise inside an API view to return a consistent JSON error."""

    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def ok(data, meta: dict | None = None, status: int = 200):
    body = {"data": data}
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status


def error_response(code: str, message: str, status: int, details: dict | None = None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status
