"""report_writer.py 纯函数单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.report_writer import _normalize_image_refs


class TestNormalizeImageRefs:
    def test_standard_md_with_path(self):
        """带路径的标准 md → images/ 相对路径"""
        text = "See ![](report/images/figure-1.jpg) for details."
        result = _normalize_image_refs(text)
        assert "![](images/figure-1.jpg)" in result
        assert "report/" not in result

    def test_bare_wikilink(self):
        """裸 wikilink → 标准 md"""
        text = "The diagram ![[figure-2.jpg]] shows the architecture."
        result = _normalize_image_refs(text)
        assert "![Figure 2](images/figure-2.jpg)" in result

    def test_bare_wikilink_png(self):
        """裸 wikilink png → 标准 md"""
        text = "See ![[figure-3.png]] here."
        result = _normalize_image_refs(text)
        assert "![Figure 3](images/figure-3.png)" in result

    def test_wikilink_with_path(self):
        """wikilink 含 images/ 路径 → 标准 md"""
        text = "See ![[some/images/figure-4.jpg|800]] here."
        result = _normalize_image_refs(text)
        assert "![Figure 4](images/figure-4.jpg)" in result

    def test_clean_stale_alt(self):
        """清理 LLM 残留：![Figure figure-1](...) → ![Figure 1](...)"""
        text = "![Figure figure-1.jpg](images/figure-1.jpg) shows the setup."
        result = _normalize_image_refs(text)
        assert "![Figure 1](images/figure-1.jpg)" in result
        assert "figure figure-" not in result

    def test_no_image_ref(self):
        """无图片引用时保持原文不变"""
        text = "This paragraph has no image references at all."
        result = _normalize_image_refs(text)
        assert result == text

    def test_multiple_images(self):
        """多张图片混合格式 → 全部归一化"""
        text = "A: ![](report/images/figure-1.jpg) B: ![[figure-2.png]]"
        result = _normalize_image_refs(text)
        assert "![](images/figure-1.jpg)" in result
        assert "![Figure 2](images/figure-2.png)" in result
