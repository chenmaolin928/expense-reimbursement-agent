import pytest
from app.services.text_quality_assessor import TextQualityAssessor, QualityAssessment


@pytest.fixture
def assessor():
    return TextQualityAssessor()


class TestTextQualityAssessor:
    def test_normal_text_scores_high(self, assessor):
        text = "差旅费报销标准：员工出差期间，住宿费标准为每天不超过500元。" * 15
        result = assessor.assess(text)
        assert result.confidence >= 0.7
        assert result.recommendation == "direct_llm"
        assert result.char_count > 0

    def test_short_text_scores_medium(self, assessor):
        text = "报销标准"
        result = assessor.assess(text)
        assert result.confidence < 0.7
        assert result.char_count == 4

    def test_garbled_text_recommends_force_ocr(self, assessor):
        text = "ÿþ报销标准¼¼½½"
        result = assessor.assess(text)
        assert result.recommendation == "force_ocr"

    def test_slightly_garbled_recommends_ocr_merge(self, assessor):
        garbled = "\x00\x01\x02" * 5
        clean = "差旅费报销标准" * 10
        result = assessor.assess(garbled + clean)
        assert result.recommendation in ("ocr_merge", "force_ocr")

    def test_empty_text_force_ocr(self, assessor):
        result = assessor.assess("")
        assert result.recommendation == "force_ocr"
        assert result.confidence == 0.0

    def test_text_with_control_chars_high_ratio(self, assessor):
        """大量控制字符应判定为 garbled"""
        text = "\x00\x01\x02\x03\x04\x05" * 20
        result = assessor.assess(text)
        assert result.recommendation == "force_ocr"

    def test_text_boundary_50_chars(self, assessor):
        """恰好 50 字符应判定为低置信度"""
        text = "a" * 50
        result = assessor.assess(text)
        assert result.recommendation == "force_ocr"

    def test_text_just_above_50_chars(self, assessor):
        """51 字符干净文本应判定 direct_llm"""
        text = "差旅费报销标准每天不超过500元。" * 3  # > 50 chars
        result = assessor.assess(text)
        assert result.recommendation == "direct_llm"
