"""Tests for database module."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from tracker_bridge.db import connect, transaction


class TestConnect:
    def test_connect_creates_connection(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            conn = connect(db_path)
            assert isinstance(conn, sqlite3.Connection)
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)

    def test_connect_enables_foreign_keys(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            conn = connect(db_path)
            result = conn.execute("PRAGMA foreign_keys;").fetchone()
            assert result[0] == 1
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)

    def test_connect_sets_row_factory(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            conn = connect(db_path)
            assert conn.row_factory == sqlite3.Row
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)


class TestTransaction:
    def test_transaction_commits_on_success(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            conn = connect(db_path)
            conn.execute("CREATE TABLE test (id TEXT PRIMARY KEY)")

            with transaction(conn):
                conn.execute("INSERT INTO test (id) VALUES (?)", ("test-1",))

            result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
            assert result[0] == 1
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)

    def test_transaction_rolls_back_on_error(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            conn = connect(db_path)
            conn.execute("CREATE TABLE test (id TEXT PRIMARY KEY)")

            with pytest.raises(ValueError), transaction(conn):
                conn.execute("INSERT INTO test (id) VALUES (?)", ("test-1",))
                raise ValueError("test error")

            result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
            assert result[0] == 0
            conn.close()
        finally:
            db_path.unlink(missing_ok=True)
