"""Workdir retention (F-08).

Cloned workdirs were never removed, for any repository, ever, so disk grew with
the number of distinct repositories anyone ever submitted. On a fixed cloud
volume that is a slow outage.

Eviction is not free, which is why it is off by default and why these tests
pin the boundaries rather than just the happy path.
"""

from pathlib import Path

from dcode_worker.stages.prune import prune_workdirs


def _workdirs(base: Path, names: list[str]) -> None:
    for index, name in enumerate(names):
        path = base / name
        path.mkdir(parents=True)
        (path / "file.py").write_text("x", encoding="utf-8")
        # Distinct mtimes, oldest first in list order.
        import os

        os.utime(path, (1_000_000 + index, 1_000_000 + index))


def test_disabled_by_default(tmp_path: Path) -> None:
    """keep=0 keeps the previous behaviour, so no existing deployment changes."""
    _workdirs(tmp_path, ["a", "b", "c"])

    assert prune_workdirs(tmp_path, keep=0, protect="new") == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a", "b", "c"]


def test_evicts_oldest_first(tmp_path: Path) -> None:
    _workdirs(tmp_path, ["oldest", "middle", "newest"])

    evicted = prune_workdirs(tmp_path, keep=2, protect="incoming")

    # keep=2 with an incoming repo leaves room for exactly one existing one.
    assert evicted == ["oldest", "middle"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["newest"]


def test_never_evicts_the_repository_being_cloned(tmp_path: Path) -> None:
    """It is the directory the caller is on its way to writing."""
    _workdirs(tmp_path, ["target", "other"])

    prune_workdirs(tmp_path, keep=1, protect="target")

    assert (tmp_path / "target").is_dir()
    assert not (tmp_path / "other").exists()


def test_the_protected_repository_occupies_a_slot(tmp_path: Path) -> None:
    """Otherwise `keep` is off by one and the cap is quietly exceeded."""
    _workdirs(tmp_path, ["a", "b", "c"])

    prune_workdirs(tmp_path, keep=3, protect="incoming")

    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert len(remaining) == 2, "two existing + the incoming one is the cap"


def test_a_missing_base_directory_is_not_an_error(tmp_path: Path) -> None:
    """First boot on an empty volume."""
    assert prune_workdirs(tmp_path / "absent", keep=5, protect="x") == []


def test_a_file_in_the_base_directory_is_ignored(tmp_path: Path) -> None:
    _workdirs(tmp_path, ["a"])
    (tmp_path / "stray.txt").write_text("not a workdir", encoding="utf-8")

    prune_workdirs(tmp_path, keep=1, protect="incoming")

    assert (tmp_path / "stray.txt").is_file()


def test_an_undeletable_workdir_does_not_fail_the_index(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Reclaiming space is best-effort; indexing is the job.

    Failing the pipeline because a stale directory would not delete would turn
    a housekeeping problem into an outage.
    """
    _workdirs(tmp_path, ["stubborn", "fine"])

    import dcode_worker.stages.prune as prune_module

    def refuse(path: str) -> None:
        raise OSError("device or resource busy")

    monkeypatch.setattr(prune_module.shutil, "rmtree", refuse)  # type: ignore[attr-defined]

    assert prune_workdirs(tmp_path, keep=1, protect="incoming") == []
