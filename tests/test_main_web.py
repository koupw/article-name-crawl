"""main.py Web 解耦层测试（RunOptions / 回调 / Rich 标记清理）"""

import pytest

from main import RunOptions, _strip_rich_markup


class TestRunOptions:
    def test_defaults(self):
        opts = RunOptions()
        assert opts.max_results == 50
        assert opts.dry_run is False
        assert opts.no_history is False
        assert opts.no_translate is False
        assert opts.min_citations is None
        assert opts.year_from is None

    def test_custom_values(self):
        opts = RunOptions(max_results=20, dry_run=True, no_translate=True)
        assert opts.max_results == 20
        assert opts.dry_run is True
        assert opts.no_translate is True


class TestStripRichMarkup:
    def test_removes_color_tags(self):
        assert _strip_rich_markup("[bold]hello[/bold]") == "hello"

    def test_removes_inline_color(self):
        assert _strip_rich_markup("[green]ok[/green]") == "ok"

    def test_mixed_text(self):
        raw = "[bold cyan]处理领域: FMCW[/bold cyan]"
        assert _strip_rich_markup(raw) == "处理领域: FMCW"

    def test_plain_text_unchanged(self):
        assert _strip_rich_markup("plain text") == "plain text"

    def test_empty_string(self):
        assert _strip_rich_markup("") == ""
