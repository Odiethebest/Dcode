"""Common HTTP error helpers for the API gateway."""

from fastapi import HTTPException


def not_implemented(milestone: str, reference: str) -> HTTPException:
    """501 with a milestone tag — used on stubbed endpoints during scaffold."""
    return HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "milestone": milestone,
            "reference": reference,
        },
    )
