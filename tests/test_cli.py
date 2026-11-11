"""Tests for the Doca command line interface."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from doca.cli import build_parser, main


class ParserTests(unittest.TestCase):
    def test_parser_accepts_every_command(self) -> None:
        parser = build_parser()
        self.assertEqual(parser.parse_args(["init"]).command, "init")
        self.assertEqual(parser.parse_args(["build"]).command, "build")
        self.assertEqual(parser.parse_args(["serve"]).command, "serve")
        self.assertEqual(parser.parse_args(["new", "guides/intro"]).command, "new")

    def test_defaults(self) -> None:
        parser = build_parser()
        build = parser.parse_args(["build"])
        self.assertEqual(build.dir, ".")
        self.assertFalse(build.quiet)
        serve = parser.parse_args(["serve"])
        self.assertEqual(serve.port, 8000)
        self.assertEqual(serve.host, "127.0.0.1")
        new = parser.parse_args(["new", "page"])
        self.assertEqual(new.name, "page")

    def test_version_flag(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit) as context:
            with redirect_stdout(StringIO()):
                parser.parse_args(["--version"])
        self.assertEqual(context.exception.code, 0)

    def test_no_command_prints_help(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([]), 1)
        self.assertIn("doca", output.getvalue())


class CommandTests(unittest.TestCase):
    def test_init_build_and_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["init", str(root)]), 0)

            self.assertTrue((root / "doca.json").exists())
            self.assertTrue((root / "docs" / "index.md").exists())
            self.assertTrue((root / "docs" / "getting-started.md").exists())
            self.assertTrue((root / "docs" / "configuration.md").exists())
            self.assertTrue((root / ".gitignore").exists())

            config = json.loads((root / "doca.json").read_text())
            self.assertEqual(config["title"], "Doca Docs")

            with redirect_stdout(StringIO()):
                self.assertEqual(main(["-C", str(root), "build"]), 0)
            self.assertTrue((root / "site" / "index.html").exists())

            with redirect_stdout(StringIO()):
                self.assertEqual(main(["-C", str(root), "new", "guides/deploy", "--title", "Deploy"]), 0)
            page = root / "docs" / "guides" / "deploy.md"
            self.assertTrue(page.exists())
            self.assertIn("title: Deploy", page.read_text())

    def test_init_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            with redirect_stdout(StringIO()):
                main(["init", str(root)])
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["init", str(root)]), 0)

    def test_new_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with redirect_stdout(StringIO()):
                main(["init", str(root)])
            error = StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(["-C", str(root), "new", "index"]), 1)
            self.assertIn("already exists", error.getvalue())

    def test_new_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with redirect_stdout(StringIO()):
                main(["init", str(root)])
            with redirect_stderr(StringIO()):
                self.assertEqual(main(["-C", str(root), "new", "../escape"]), 1)

    def test_build_without_config_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            error = StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(["-C", tmp, "build"]), 1)
            self.assertIn("doca.json", error.getvalue())


if __name__ == "__main__":
    unittest.main()
