"""
Unit tests for query utilities.

Tests language detection, validation, and date query expansion.
"""

import pytest

from lokal_rag_mcp.query_utils import (
    detect_query_language,
    fn_expand_query_with_dates,
    validate_query_language,
)


class TestDetectQueryLanguage:
    """Tests for detect_query_language function."""

    def test_pure_russian(self):
        """Test detection of pure Russian text."""
        assert detect_query_language("документы за октябрь") == "ru"
        assert detect_query_language("какие есть статьи про машинное обучение") == "ru"
        assert detect_query_language("память команды проекты") == "ru"

    def test_pure_english(self):
        """Test detection of pure English text."""
        assert detect_query_language("documents from october") == "en"
        assert detect_query_language("machine learning articles") == "en"
        assert detect_query_language("what are the best practices") == "en"

    def test_mixed_queries(self):
        """Test detection of mixed language queries."""
        # Mixed queries should be detected as "mixed"
        assert detect_query_language("документы machine learning") == "mixed"
        assert detect_query_language("статьи про AI") == "mixed"
        assert detect_query_language("memory Claude teams") == "mixed"

    def test_proper_nouns(self):
        """Test queries with proper nouns (e.g., Claude, Python)."""
        # "память Claude команды" = 20 cyrillic, 6 latin = 23% latin → mixed
        result = detect_query_language("память Claude команды проекты")
        assert result == "mixed"

    def test_numbers_only(self):
        """Test queries with only numbers (should default to 'en')."""
        assert detect_query_language("2024 2025") == "en"
        assert detect_query_language("123 456") == "en"

    def test_mixed_with_numbers(self):
        """Test mixed queries with numbers."""
        assert detect_query_language("октябрь 2024") == "ru"
        assert detect_query_language("october 2024") == "en"


class TestValidateQueryLanguage:
    """Tests for validate_query_language function."""

    def test_valid_russian_query(self):
        """Test validation of valid Russian queries."""
        # Pure Russian with ru expected → valid
        assert validate_query_language("документы за октябрь", "ru") is None

    def test_valid_english_query(self):
        """Test validation of valid English queries."""
        # Pure English with en expected → valid
        assert validate_query_language("documents from october", "en") is None

    def test_invalid_russian_query_expects_english(self):
        """Test Russian query when English is expected."""
        error = validate_query_language("документы за октябрь", "en")
        assert error is not None
        assert error["error"] == "language_mismatch"
        assert error["detected_language"] == "ru"
        assert error["expected_language"] == "en"
        assert "translate" in error["suggestion_en"].lower()

    def test_invalid_english_query_expects_russian(self):
        """Test English query when Russian is expected."""
        error = validate_query_language("documents from october", "ru")
        assert error is not None
        assert error["error"] == "language_mismatch"
        assert error["detected_language"] == "en"
        assert error["expected_language"] == "ru"
        assert "перевед" in error["suggestion_ru"].lower()

    def test_mixed_query_majority_russian_expects_russian(self):
        """Test mixed query with Russian majority when Russian expected."""
        # "документы machine learning" = majority Russian
        result = validate_query_language("документы machine learning за октябрь", "ru")
        assert result is None  # Should pass - majority matches

    def test_mixed_query_majority_russian_expects_english(self):
        """Test mixed query with Russian majority when English expected."""
        # "память Claude команды" = majority Russian, expects English → error
        error = validate_query_language("память Claude команды проекты", "en")
        assert error is not None
        assert error["error"] == "language_mismatch"
        assert error["detected_language"] == "mixed_ru"
        assert error["expected_language"] == "en"

    def test_mixed_query_majority_english_expects_english(self):
        """Test mixed query with English majority when English expected."""
        # "machine learning про документы" = majority English
        result = validate_query_language("machine learning articles про AI", "en")
        assert result is None  # Should pass - majority matches

    def test_mixed_query_majority_english_expects_russian(self):
        """Test mixed query with English majority when Russian expected."""
        error = validate_query_language("machine learning articles про AI", "ru")
        assert error is not None
        assert error["error"] == "language_mismatch"
        assert error["detected_language"] == "mixed_en"

    def test_error_response_structure(self):
        """Test that error response has all required fields."""
        error = validate_query_language("documents from october", "ru")
        assert "error" in error
        assert "detected_language" in error
        assert "expected_language" in error
        assert "original_query" in error
        assert "suggestion_ru" in error
        assert "suggestion_en" in error


class TestExpandQueryWithDates:
    """Tests for fn_expand_query_with_dates function."""

    def test_russian_month_expansion(self):
        """Test expansion of Russian month names."""
        result = fn_expand_query_with_dates("документы за октябрь")
        assert "октябрь" in result
        assert "октября" in result
        assert "1 октября" in result
        assert "2 октября" in result
        assert "дат октября" in result

    def test_multiple_russian_months(self):
        """Test expansion with multiple Russian months."""
        result = fn_expand_query_with_dates("документы за июль и август")
        assert "июля" in result
        assert "августа" in result

    def test_english_month_expansion(self):
        """Test expansion of English month names."""
        result = fn_expand_query_with_dates("documents from october")
        assert "october" in result
        assert "oct" in result
        assert "1 october" in result
        assert "2 october" in result

    def test_no_month_in_query(self):
        """Test query without months returns unchanged."""
        query = "machine learning algorithms"
        result = fn_expand_query_with_dates(query)
        assert result == query

    def test_mixed_language_months(self):
        """Test query with both Russian and English months."""
        result = fn_expand_query_with_dates("октябрь october")
        assert "октября" in result
        assert "oct" in result

    def test_case_insensitive_expansion(self):
        """Test that expansion works regardless of case."""
        result = fn_expand_query_with_dates("Документы за Октябрь")
        assert "октября" in result.lower()

    def test_all_russian_months(self):
        """Test that all Russian months are supported."""
        months = [
            "январь", "февраль", "март", "апрель", "май", "июнь",
            "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"
        ]
        genitive = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]

        for nom, gen in zip(months, genitive):
            result = fn_expand_query_with_dates(f"документы за {nom}")
            assert gen in result

    def test_all_english_months(self):
        """Test that all English months are supported."""
        months = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ]
        abbrevs = [
            "jan", "feb", "mar", "apr", "may", "jun",
            "jul", "aug", "sep", "oct", "nov", "dec"
        ]

        for month, abbrev in zip(months, abbrevs):
            result = fn_expand_query_with_dates(f"documents from {month}")
            assert abbrev in result.lower()


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_language_validation_with_date_expansion(self):
        """Test that language validation works with date-expanded queries."""
        # Russian query with date
        query = "документы за октябрь"
        assert validate_query_language(query, "ru") is None
        expanded = fn_expand_query_with_dates(query)
        assert "октября" in expanded

    def test_mixed_query_with_technical_terms_and_dates(self):
        """Test realistic mixed query with technical terms and dates."""
        query = "документы про machine learning за октябрь"
        # Should pass validation (majority Russian)
        assert validate_query_language(query, "ru") is None
        # Should expand date
        expanded = fn_expand_query_with_dates(query)
        assert "октября" in expanded
        assert "machine learning" in expanded
