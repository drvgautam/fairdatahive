"""Unit tests for the S3 copy-tool helpers (no live object store)."""

from __future__ import annotations

from pathlib import Path

from scripts.migrate_objects import ManifestRow, load_manifest, write_manifest


def test_manifest_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    rows = [
        ManifestRow(
            bucket="fairdatahive-catalog",
            key="public/resource-a/abcd1234-data.csv",
            size=12,
            content_type="text/csv",
            sha256="abc",
            copied=True,
        ),
        ManifestRow(
            bucket="fairdatahive-catalog",
            key="public/resource-b/empty.bin",
            size=0,
            content_type="application/octet-stream",
        ),
    ]
    write_manifest(path, rows)
    loaded = load_manifest(path)
    assert [r.key for r in loaded] == [r.key for r in rows]
    assert loaded[0].copied is True
    assert loaded[0].sha256 == "abc"
    assert loaded[1].size == 0
    assert loaded[1].copied is False


def test_load_missing_manifest_is_empty(tmp_path: Path) -> None:
    assert load_manifest(tmp_path / "missing.jsonl") == []


def test_db_check_flags_missing_keys(tmp_path: Path, monkeypatch) -> None:
    import sqlalchemy
    from scripts import migrate_objects as migrate

    class _Result:
        def __iter__(self):
            return iter(
                [
                    ("public/resource-a/abcd1234-data.csv",),
                    ("public/resource-missing/ffff-gone.bin",),
                ]
            )

    class _Conn:
        def execute(self, _stmt):
            return _Result()

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    class _Engine:
        def connect(self):
            return _Conn()

    monkeypatch.setattr(sqlalchemy, "create_engine", lambda _url: _Engine())

    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            ManifestRow(
                bucket="fairdatahive-catalog",
                key="public/resource-a/abcd1234-data.csv",
                size=1,
            ),
            ManifestRow(
                bucket="fairdatahive-catalog",
                key="orphan-not-in-db.bin",
                size=1,
            ),
        ],
    )
    report = tmp_path / "report.json"
    args = migrate.build_parser().parse_args(
        [
            "--manifest",
            str(manifest),
            "db-check",
            "--database-url",
            "sqlite:///:memory:",
            "--report",
            str(report),
        ]
    )
    assert migrate.db_check(args) == 1
    body = report.read_text(encoding="utf-8")
    assert "public/resource-missing/ffff-gone.bin" in body
    assert "orphan-not-in-db.bin" in body
