from lead_generation_app.backend.base_scraper import (
    safe_json, deep_get, merge_dicts, split_name, try_regex,
    EMAIL_RE, NAME_RE, TITLE_RE,
)


def test_safe_json_valid():
    assert safe_json('{"a": 1}') == {"a": 1}


def test_safe_json_invalid():
    assert safe_json('not json') is None


def test_safe_json_empty():
    assert safe_json('') is None


def test_deep_get_nested():
    d = {"a": {"b": {"c": "value"}}}
    assert deep_get(d, "a", "b", "c") == "value"


def test_deep_get_missing():
    d = {"a": 1}
    assert deep_get(d, "b") == ""


def test_deep_get_empty_dict():
    assert deep_get({}, "a", "b") == ""


def test_merge_dicts_both():
    a = {"x": 1, "y": None}
    b = {"y": 2, "z": 3}
    result = merge_dicts(a, b)
    assert result == {"x": 1, "y": 2, "z": 3}


def test_merge_dicts_first_none():
    assert merge_dicts(None, {"a": 1}) == {"a": 1}


def test_merge_dicts_second_none():
    assert merge_dicts({"a": 1}, None) == {"a": 1}


def test_merge_dicts_both_none():
    assert merge_dicts(None, None) is None


def test_split_name_full():
    assert split_name("John Smith") == ("John", "Smith")


def test_split_name_single():
    assert split_name("John") == ("John", "")


def test_split_name_multi():
    assert split_name("John Michael Smith") == ("John", "Michael Smith")


def test_split_name_empty():
    assert split_name("") == ("", "")


def test_split_name_whitespace():
    assert split_name("  John  Smith  ") == ("John", "Smith")


class FakeNode:
    def __init__(self, text):
        self._text = text

    def css(self, selector):
        class FakeCSS:
            @staticmethod
            def getall():
                return [self._text]

            @staticmethod
            def get():
                return self._text

        return FakeCSS()

    def __str__(self):
        return self._text


def test_try_regex_with_email_name_title():
    html_text = "John Smith is the CEO of Acme Corp. Email: john@acme.com"
    node = FakeNode(html_text)
    result = try_regex(node)
    assert result["first_name"] == "John"
    assert result["last_name"] == "Smith"
    assert "CEO" in result["title"]
    assert result["email"] == "john@acme.com"


def test_try_regex_no_match():
    node = FakeNode("Nothing relevant here 12345")
    result = try_regex(node)
    assert result["first_name"] == ""
    assert result["last_name"] == ""
    assert result["email"] == ""


def test_email_re():
    assert EMAIL_RE.findall("contact me at test@example.com") == ["test@example.com"]
    assert EMAIL_RE.findall("no email here") == []


def test_name_re():
    assert NAME_RE.findall("John Smith") == [("John", "Smith")]
    assert NAME_RE.findall("short") == []


def test_title_re():
    assert TITLE_RE.findall("CEO of Acme")
    assert TITLE_RE.findall("Founder and President")
    assert not TITLE_RE.findall("Just a regular worker")
