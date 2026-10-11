
"""WSL/Linux local registry: serialized promotions with audited rollback."""

import fcntl
import json
import os
import tempfile

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .registry import (
    active_version,
    list_versions,
    model_dir,
    registry_root,
)
from .prediction import load_model


def _report(version, root):
    path = model_dir(version, root) / "evaluation.json"

    return (
        json.loads(path.read_text(encoding="utf-8"))
        if path.is_file()
        else None
    )


def registry_status(root=None):
    root = Path(root) if root is not None else registry_root()
    active = active_version(root)
    entries = []

    for version in list_versions(root):
        metadata = json.loads(
            (model_dir(version, root) / "metadata.json").read_text(
                encoding="utf-8"
            )
        )

        entries.append({
            "version": version,
            "active": version == active,
            "kind": metadata.get("kind"),
            "threshold": metadata.get("threshold"),
            "evaluation": _report(version, root),
        })

    return {
        "active_version": active,
        "versions": entries,
    }


@contextmanager
def _exclusive_registry(root):
    """Allow only one activation operation at a time."""

    root.mkdir(parents=True, exist_ok=True)

    with (root / ".activation.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _events(root):
    path = root / "activation_history.jsonl"

    if not path.exists():
        return []

    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def switch_model(
    version,
    *,
    confirm,
    root=None,
    allow_rollback=False,
):
    root = Path(root) if root is not None else registry_root()

    if confirm != f"ACTIVATE {version}":
        raise ValueError(
            f"Type ACTIVATE {version} to confirm"
        )

    with _exclusive_registry(root):

        # Read the current version AFTER acquiring the lock.
        current = active_version(root)

        if version == current:
            raise ValueError(
                "Requested model is already active"
            )

        # model_dir also validates version naming.
        directory = model_dir(version, root)

        if not directory.is_dir():
            raise FileNotFoundError(
                "Requested model version does not exist"
            )

        if allow_rollback:
            history = _events(root)

            if (
                not history
                or history[-1].get("from") != version
                or history[-1].get("to") != current
            ):
                raise ValueError(
                    "Rollback must target the immediate previous active model"
                )

        else:
            report = _report(version, root)

            if (
                not report
                or report.get("champion_version") != current
            ):
                raise ValueError(
                    "A comparison against the current champion is required"
                )

            if (
                report.get("candidate_version") != version
                or report.get("approved_for_review") is not True
            ):
                raise ValueError(
                    "Candidate did not meet automatic comparison criteria"
                )

        # Validate trusted candidate artifacts before switching.
        load_model(
            version,
            str(root.resolve()),
        )

        event = {
            "from": current,
            "to": version,
            "reason": (
                "rollback"
                if allow_rollback
                else "reviewed_promotion"
            ),
            "recorded_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        # Write a unique temporary pointer.
        fd, temporary_name = tempfile.mkstemp(
            prefix=".active-",
            suffix=".json",
            dir=root,
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as stream:
                json.dump(
                    {"version": version},
                    stream,
                )
                stream.flush()
                os.fsync(stream.fileno())

            # Atomic pointer replacement.
            os.replace(
                temporary_name,
                root / "active.json",
            )

        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

        # Clear this process's model-loading cache.
        load_model.cache_clear()

        # Persist an audit record.
        with (
            root / "activation_history.jsonl"
        ).open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(event) + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())

        return {
            "previous": current,
            "active_version": version,
            "reason": event["reason"],
        }
