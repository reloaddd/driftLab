
"""Model registry API with administrator authentication."""

import os
import secrets

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
)
from pydantic import BaseModel

from driftlab.day8_registry import (
    registry_status,
    switch_model,
)

router = APIRouter(
    prefix="/registry",
    tags=["Model Registry"],
)


class Approval(BaseModel):
    version: str
    confirmation: str


def require_admin(
    x_driftlab_admin_key: str | None = Header(default=None),
):
    """Protect operations that can change the live model."""

    expected = os.environ.get("DRIFTLAB_ADMIN_KEY")

    # Fail closed if no administrator key is configured.
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Registry administration is not configured",
        )

    if (
        not x_driftlab_admin_key
        or not secrets.compare_digest(
            x_driftlab_admin_key,
            expected,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="Administrator authorization required",
        )


@router.get("/status")
def status():
    return registry_status()


@router.post("/promote")
def promote(
    body: Approval,
    _admin=Depends(require_admin),
):
    try:
        return switch_model(
            body.version,
            confirm=body.confirmation,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/rollback")
def rollback(
    body: Approval,
    _admin=Depends(require_admin),
):
    try:
        return switch_model(
            body.version,
            confirm=body.confirmation,
            allow_rollback=True,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
