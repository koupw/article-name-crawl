"""report_writer.py 纯函数单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.report_writer import _normalize_image_refs


class TestNormalizeImageRefs:
    def test_standard_md_with_path(self):
        text = "See ![](report/images/figure-1.jpg) for details."
        result = _normalize_image_refs(text)
        assert "![[images/figure-1.jpg|800]]" in result
        assert "![](" not in result or "images/" not in result.split("![[")[0]

    def test_bare_wikilink(self):
        text = "The diagram ![[figure-2.jpg]] shows the architecture."
        result = _normalize_image_refs(text)
        assert "![[images/figure-2.jpg|800]]" in result

    def test_wikilink_with_size(self):
        text = "See ![[figure-3.png|600]] here."
        result = _normalize_image_refs(text)
        assert "![[images/figure-3.png|800]]" in result

    def test_already_normalized(self):
        text = "![[images/figure-1.jpg|800]] is good."
        result = _normalize_image_refs(text)
        # 应该是幂等的（不产生双重 images/images/）
        assert result == text

    def test_no_image_ref(self):
        text = "This paragraph has no image references at all."
        result = _normalize_image_refs(text)
        assert result == text

    def test_multiple_images(self):
        text = "A: ![](report/images/figure-1.jpg) B: ![[figure-2.png]]"
        result = _normalize_image_refs(text)
        assert "![[images/figure-1.jpg|800]]" in result
        assert "![[images/figure-2.png|800]]" in result
