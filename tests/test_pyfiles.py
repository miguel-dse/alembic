from __future__ import annotations

import pathlib
import sys
import tempfile

from alembic.testing import eq_
from alembic.testing import is_
from alembic.testing import mock
from alembic.testing.fixtures import TestBase
from alembic.util import pyfiles


class PyfilesTest(TestBase):
    @staticmethod
    def _cleanup_modules(*module_names):
        for module_name in module_names:
            sys.modules.pop(module_name, None)

    @staticmethod
    def _spec_side_effect(path_to_fail):
        original = pyfiles.importlib.util.spec_from_file_location
        expected_path = pathlib.Path(path_to_fail).resolve()

        def go(name, location, *args, **kwargs):
            if pathlib.Path(location).resolve() == expected_path:
                return None
            return original(name, location, *args, **kwargs)

        return go

    def test_load_module_py_falls_back_to_import_module(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = pathlib.Path(tempdir)
            pkg = root / "pkg"
            migrations = pkg / "migrations"

            pkg.mkdir()
            migrations.mkdir()

            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (migrations / "env.py").write_text(
                "VALUE = 'env'\n", encoding="utf-8"
            )

            try:
                with (
                    mock.patch(
                        "alembic.util.pyfiles.importlib.util.spec_from_file_location",
                        side_effect=self._spec_side_effect(
                            migrations / "env.py"
                        ),
                    ),
                    mock.patch.object(pyfiles.sys, "path", [tempdir]),
                ):
                    module = pyfiles.load_module_py(
                        "env_py", migrations / "env.py"
                    )
            finally:
                self._cleanup_modules(
                    "pkg.migrations.env", "pkg.migrations", "pkg"
                )

            eq_(module.__name__, "pkg.migrations.env")
            eq_(module.VALUE, "env")

    def test_load_module_py_falls_back_for_revision_modules(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = pathlib.Path(tempdir)
            pkg = root / "pkg"
            versions = pkg / "migrations" / "versions"

            versions.mkdir(parents=True)
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            revision_path = versions / "1234_revision.py"
            revision_path.write_text(
                "revision = '1234'\n", encoding="utf-8"
            )

            try:
                with (
                    mock.patch(
                        "alembic.util.pyfiles.importlib.util.spec_from_file_location",
                        side_effect=self._spec_side_effect(revision_path),
                    ),
                    mock.patch.object(pyfiles.sys, "path", [tempdir]),
                ):
                    module = pyfiles.load_module_py(
                        "1234_revision_py", revision_path
                    )
            finally:
                self._cleanup_modules(
                    "pkg.migrations.versions.1234_revision",
                    "pkg.migrations.versions",
                    "pkg.migrations",
                    "pkg",
                )

            eq_(module.__name__, "pkg.migrations.versions.1234_revision")
            eq_(module.revision, "1234")

    def test_load_module_py_reloads_existing_module_on_fallback(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = pathlib.Path(tempdir)
            pkg = root / "pkg"
            migrations = pkg / "migrations"

            pkg.mkdir()
            migrations.mkdir()

            (pkg / "__init__.py").write_text("", encoding="utf-8")
            path = migrations / "env.py"
            path.write_text("VALUE = 'old'\n", encoding="utf-8")

            try:
                with (
                    mock.patch(
                        "alembic.util.pyfiles.importlib.util.spec_from_file_location",
                        side_effect=self._spec_side_effect(path),
                    ),
                    mock.patch.object(pyfiles.sys, "path", [tempdir]),
                ):
                    first = pyfiles.load_module_py("env_py", path)
                    path.write_text(
                        "VALUE = 'new'\n__reload_token__ = object()\n",
                        encoding="utf-8",
                    )
                    second = pyfiles.load_module_py("env_py", path)
            finally:
                self._cleanup_modules(
                    "pkg.migrations.env", "pkg.migrations", "pkg"
                )

            is_(first, second)
            eq_(second.VALUE, "new")
            eq_(hasattr(second, "__reload_token__"), True)
