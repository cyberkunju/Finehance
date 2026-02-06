"""Security middleware — input sanitization and output filtering."""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from app.middleware.input_guard import InputGuard, ThreatLevel
from app.middleware.output_guard import OutputGuard

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Applies InputGuard on POST/PUT/PATCH request bodies,
    and OutputGuard on JSON response bodies for AI endpoints.
    """

    def __init__(self, app, input_guard: InputGuard = None, output_guard: OutputGuard = None):
        super().__init__(app)
        self.input_guard = input_guard or InputGuard()
        self.output_guard = output_guard or OutputGuard()
        # Paths where output guard should filter responses
        self.ai_response_paths = {"/api/ai/chat", "/api/ai/analyze", "/api/ai/smart-advice"}

    # Paths exempt from input scanning (auth payloads contain "password" key)
    EXEMPT_PATHS = {
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/change-password",
        "/api/auth/profile",
    }

    async def dispatch(self, request: Request, call_next):
        # INPUT GUARD: Check POST/PUT/PATCH bodies (skip auth endpoints)
        if request.method in ("POST", "PUT", "PATCH") and request.url.path not in self.EXEMPT_PATHS:
            try:
                body = await request.body()
                if body:
                    text = body.decode("utf-8", errors="ignore")
                    result = self.input_guard.validate(text)
                    if not result.is_safe:
                        logger.warning(
                            "Input blocked: threat_level=%s, path=%s",
                            result.threat_level,
                            request.url.path,
                        )
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "Input rejected due to security concerns."},
                        )
            except Exception as e:
                logger.debug("Input guard error: %s", e)  # Don't crash the request on guard errors

        response = await call_next(request)

        # OUTPUT GUARD: Filter AI response bodies
        if request.url.path in self.ai_response_paths:
            # Only filter JSON responses
            if response.headers.get("content-type", "").startswith("application/json"):
                # Read and filter the response body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk

                text = body.decode("utf-8", errors="ignore")
                validation = self.output_guard.validate(text)

                if not validation.is_safe and validation.filtered_content:
                    body = validation.filtered_content.encode("utf-8")

                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )

        return response
