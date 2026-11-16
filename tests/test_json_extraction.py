import unittest

from fure.utils.json_extraction import extract_json


class JSONExtractionTests(unittest.TestCase):
    def test_whole_values_and_fenced_values_keep_their_types(self):
        for text, expected in [
            ('{"answer": [true, null]}', {"answer": [True, None]}),
            ('"hello"', "hello"),
            ("false", False),
            ("null", None),
            ("42", 42),
            ("[1, 2]", [1, 2]),
        ]:
            for content in (text, f"Here is the result:\n```json\n{text}\n```\nDone."):
                with self.subTest(content=content):
                    self.assertEqual(extract_json(content), expected)

    def test_nested_json_is_one_value_and_strings_do_not_close_containers_or_fences(
        self,
    ):
        text = 'Result: {"nested": [{"value": "} ] ``` escaped \\""}]}.'
        expected = {"nested": [{"value": '} ] ``` escaped "'}]}
        self.assertEqual(extract_json(text), expected)
        self.assertEqual(extract_json("```JSON\n" + text[8:-1] + "\n```"), expected)

    def test_reasoning_stripping_is_explicit_and_can_be_disabled(self):
        text = '<think>{"draft": true}</think>\n{"answer": 42}'
        self.assertEqual(extract_json(text, ("</think>",)), {"answer": 42})
        with self.assertRaises(ValueError):
            extract_json(text)
        self.assertEqual(extract_json("<THINK>draft</THINK>\n42", ("</think>",)), 42)
        self.assertEqual(
            extract_json('{"text": "</think>"}', ("</think>",)), {"text": "</think>"}
        )

    def test_invalid_ambiguous_and_non_json_responses_are_rejected(self):
        for text in (
            "",
            "no JSON",
            "1 2",
            "{} {}",
            "{} []",
            "{} true",
            "{} null",
            "{} 42",
            '{} "another value"',
            "```json\n{}\n```\n```json\n[]\n```",
            "```json\n{}\n```\n{}",
            '{"a": {"nested": true}',
            '{"a": 1, "a": 2}',
            '{"value": NaN}',
            '{"value": Infinity}',
            '{"value": 1e999}',
            '{"bad": "unterminated}',
            '```json\n{"bad":\n```',
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                extract_json(text)
