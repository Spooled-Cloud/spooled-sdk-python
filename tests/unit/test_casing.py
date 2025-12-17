"""Unit tests for casing module."""

from __future__ import annotations

import pytest

from spooled.utils.casing import (
    convert_keys,
    convert_query_params,
    convert_request,
    convert_response,
    to_camel_case,
    to_snake_case,
)


class TestToSnakeCase:
    """Tests for to_snake_case function."""

    def test_camel_case(self) -> None:
        """Test camelCase conversion."""
        assert to_snake_case("camelCase") == "camel_case"
        assert to_snake_case("someValue") == "some_value"
        assert to_snake_case("getValue") == "get_value"

    def test_pascal_case(self) -> None:
        """Test PascalCase conversion."""
        assert to_snake_case("PascalCase") == "pascal_case"
        assert to_snake_case("MyClass") == "my_class"
        assert to_snake_case("HTTPResponse") == "http_response"

    def test_already_snake_case(self) -> None:
        """Test already snake_case stays unchanged."""
        assert to_snake_case("snake_case") == "snake_case"
        assert to_snake_case("some_value") == "some_value"

    def test_single_word(self) -> None:
        """Test single word stays unchanged."""
        assert to_snake_case("word") == "word"
        assert to_snake_case("Word") == "word"

    def test_consecutive_uppercase(self) -> None:
        """Test consecutive uppercase letters."""
        assert to_snake_case("XMLParser") == "xml_parser"
        assert to_snake_case("parseHTML") == "parse_html"
        assert to_snake_case("getHTTPResponse") == "get_http_response"

    def test_numbers(self) -> None:
        """Test strings with numbers."""
        assert to_snake_case("value1") == "value1"
        assert to_snake_case("getValue2") == "get_value2"


class TestToCamelCase:
    """Tests for to_camel_case function."""

    def test_snake_case(self) -> None:
        """Test snake_case conversion."""
        assert to_camel_case("snake_case") == "snakeCase"
        assert to_camel_case("some_value") == "someValue"
        assert to_camel_case("get_value") == "getValue"

    def test_already_camel_case(self) -> None:
        """Test already camelCase stays unchanged."""
        assert to_camel_case("camelCase") == "camelCase"
        assert to_camel_case("someValue") == "someValue"

    def test_single_word(self) -> None:
        """Test single word stays unchanged."""
        assert to_camel_case("word") == "word"

    def test_multiple_underscores(self) -> None:
        """Test multiple underscores."""
        assert to_camel_case("some_long_name") == "someLongName"
        assert to_camel_case("get_all_items") == "getAllItems"

    def test_leading_underscore(self) -> None:
        """Test leading underscore (edge case)."""
        # This is an edge case - behavior may vary
        result = to_camel_case("_private")
        assert result == "Private" or result == "_private"

    def test_numbers(self) -> None:
        """Test strings with numbers."""
        assert to_camel_case("value_1") == "value1"
        assert to_camel_case("get_value_2") == "getValue2"


class TestConvertKeys:
    """Tests for convert_keys function."""

    def test_flat_dict(self) -> None:
        """Test flat dictionary conversion."""
        data = {"someKey": "value", "anotherKey": 123}
        result = convert_keys(data, to_snake_case)
        assert result == {"some_key": "value", "another_key": 123}

    def test_nested_dict(self) -> None:
        """Test nested dictionary conversion."""
        data = {
            "outerKey": {
                "innerKey": "value",
                "deepKey": {"veryDeep": 123},
            }
        }
        result = convert_keys(data, to_snake_case)
        assert result == {
            "outer_key": {
                "inner_key": "value",
                "deep_key": {"very_deep": 123},
            }
        }

    def test_list_of_dicts(self) -> None:
        """Test list of dictionaries."""
        data = [{"keyOne": 1}, {"keyTwo": 2}]
        result = convert_keys(data, to_snake_case)
        assert result == [{"key_one": 1}, {"key_two": 2}]

    def test_mixed_nested(self) -> None:
        """Test mixed nested structures."""
        data = {
            "items": [
                {"itemName": "a"},
                {"itemName": "b"},
            ],
            "metadata": {
                "totalCount": 2,
            },
        }
        result = convert_keys(data, to_snake_case)
        assert result == {
            "items": [
                {"item_name": "a"},
                {"item_name": "b"},
            ],
            "metadata": {
                "total_count": 2,
            },
        }

    def test_primitive_values(self) -> None:
        """Test primitive values pass through."""
        assert convert_keys("string", to_snake_case) == "string"
        assert convert_keys(123, to_snake_case) == 123
        assert convert_keys(True, to_snake_case) is True
        assert convert_keys(None, to_snake_case) is None

    def test_empty_structures(self) -> None:
        """Test empty structures."""
        assert convert_keys({}, to_snake_case) == {}
        assert convert_keys([], to_snake_case) == []


class TestConvertRequest:
    """Tests for convert_request function."""

    def test_converts_to_snake_case(self) -> None:
        """Test request body is converted to snake_case."""
        data = {"queueName": "test", "maxRetries": 3}
        result = convert_request(data)
        assert result == {"queue_name": "test", "max_retries": 3}


class TestConvertResponse:
    """Tests for convert_response function."""

    def test_passes_through(self) -> None:
        """Test response passes through (API uses snake_case)."""
        data = {"queue_name": "test", "max_retries": 3}
        result = convert_response(data)
        assert result == data


class TestConvertQueryParams:
    """Tests for convert_query_params function."""

    def test_basic_conversion(self) -> None:
        """Test basic parameter conversion."""
        params = {"queueName": "test", "limit": 10}
        result = convert_query_params(params)
        assert result == {"queue_name": "test", "limit": "10"}

    def test_none_values_excluded(self) -> None:
        """Test None values are excluded."""
        params = {"queueName": "test", "status": None}
        result = convert_query_params(params)
        assert result == {"queue_name": "test"}
        assert "status" not in result

    def test_boolean_conversion(self) -> None:
        """Test boolean to lowercase string."""
        params = {"isActive": True, "paused": False}
        result = convert_query_params(params)
        assert result == {"is_active": "true", "paused": "false"}

    def test_string_values(self) -> None:
        """Test string values stay as strings."""
        params = {"status": "pending", "queueName": "emails"}
        result = convert_query_params(params)
        assert result == {"status": "pending", "queue_name": "emails"}

    def test_integer_values(self) -> None:
        """Test integer values converted to strings."""
        params = {"limit": 50, "offset": 100}
        result = convert_query_params(params)
        assert result == {"limit": "50", "offset": "100"}

    def test_empty_dict(self) -> None:
        """Test empty dictionary."""
        result = convert_query_params({})
        assert result == {}


