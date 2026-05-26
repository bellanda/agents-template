"""Minimal API exceptions.

These subclass FastAPI's ``HTTPException`` so they are handled natively — no
custom exception handler needed. ``config/uploads.py`` raises ``BadRequestError``
for invalid MIME/size/corrupt-image per rule ``uploads.md`` (never ``ValueError``).
Projects with a richer error envelope can swap these for their own framework.
"""

from fastapi import HTTPException, status


class BadRequestError(HTTPException):
    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Not found") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
