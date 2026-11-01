"""Error handling: JSON errors for /api/*, friendly HTML pages everywhere else."""
from flask import render_template, request
from werkzeug.exceptions import HTTPException, InternalServerError

from .utils.responses import ApiError, error_response

# Plain-language messages; public pages must never show technical jargon.
FRIENDLY = {
    400: ("bad_request", "Something about that request didn't look right."),
    404: ("not_found", "We couldn't find what you were looking for."),
    405: ("method_not_allowed", "That action isn't supported here."),
    409: ("conflict", "That has already been received."),
    413: ("payload_too_large", "That request was too large."),
    429: ("rate_limited", "You're going a little fast. Please wait a moment and try again."),
    500: ("server_error", "Something went wrong on our side. Please try again shortly."),
    503: ("service_unavailable", "SpeedSpot is temporarily unavailable. Please try again shortly."),
}


def _is_api_request() -> bool:
    return request.path.startswith("/api/")


def _render(status: int):
    code, message = FRIENDLY.get(status, FRIENDLY[500])
    if _is_api_request():
        return error_response(code, message, status)
    return render_template("errors.html", status=status, message=message, page_title="Oops"), status


def register(app) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return error_response(exc.code, exc.message, exc.status, exc.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return _render(exc.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        app.logger.exception("Unhandled error")
        return _render(InternalServerError.code)
