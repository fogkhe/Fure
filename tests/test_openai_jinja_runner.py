import asyncio
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

import httpx2
from jinja2 import UndefinedError
from jsonschema.exceptions import ValidationError
from openai import APITimeoutError, AsyncOpenAI, BadRequestError

from fure.core.implementations import JinjaImplementation
from fure.core.runners import (
    OpenAIJinjaRunMeta,
    OpenAIJinjaRunner,
    OpenAIJinjaRunnerOptions,
)


class OpenAIJinjaRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.options = OpenAIJinjaRunnerOptions(
            timeout=10,
            api_key=None,
            base_url="http://localhost:11434/v1",
            model="test-model",
        )
        self.runner = OpenAIJinjaRunner(self.options)
        self.implementation = JinjaImplementation("Hello, {{ name }}!")
        self.response = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Hello back!"},
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        self.requests = []
        self.clients = []
        self.delay = 0
        self.status_code = 200
        self.started = asyncio.Event()
        self.cancelled = False
        self.transport_error = None
        self.client_factory = self.enterContext(
            patch(
                "fure.core.runners.jinja.openai.AsyncOpenAI",
                side_effect=self._create_client,
            )
        )

    def _create_client(self, **kwargs):
        client = AsyncOpenAI(
            **kwargs,
            max_retries=0,
            http_client=httpx2.AsyncClient(
                transport=httpx2.MockTransport(self._respond)
            ),
        )
        self.clients.append(client)
        return client

    async def _respond(self, request):
        self.requests.append(request)
        self.started.set()
        if self.transport_error is not None:
            raise self.transport_error
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return httpx2.Response(self.status_code, json=self.response)

    async def test_renders_prompt_and_returns_text_and_token_usage(self):
        result = await self.runner.run(self.implementation, {"name": "world"})

        self.assertEqual(result.output, "Hello back!")
        self.assertEqual(
            result.meta,
            OpenAIJinjaRunMeta(input_tokens=5, output_tokens=3, total_tokens=8),
        )
        self.assertGreaterEqual(result.duration, 0)
        request = self.requests[0]
        self.assertEqual(str(request.url), "http://localhost:11434/v1/chat/completions")
        self.assertEqual(
            json.loads(request.content),
            {
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello, world!"}],
            },
        )
        self.assertTrue(self.clients[0].is_closed())

    async def test_shared_vars_are_rendered_separately_from_user_input(self):
        implementation = JinjaImplementation("{{ vars.apiKey }}: {{ name }}")
        self.assertEqual(implementation.input_schema["required"], ["name"])
        await self.runner.run(
            implementation,
            {"name": "world", "vars": {"apiKey": "input"}},
            variables={"apiKey": "shared"},
        )
        self.assertEqual(
            json.loads(self.requests[0].content)["messages"],
            [{"role": "user", "content": "shared: world"}],
        )

    async def test_call_options_override_runner_options(self):
        options = OpenAIJinjaRunnerOptions(
            timeout=20,
            api_key="test-key",
            base_url="https://example.test/v1",
            model="other-model",
        )

        await self.runner.run(self.implementation, {"name": "world"}, options)

        request = self.requests[0]
        self.assertEqual(str(request.url), "https://example.test/v1/chat/completions")
        self.assertEqual(request.headers["authorization"], "Bearer test-key")
        self.assertEqual(json.loads(request.content)["model"], "other-model")
        self.client_factory.assert_called_once_with(
            api_key="test-key", base_url=options.base_url, timeout=20
        )

    async def test_none_api_key_supports_local_servers(self):
        await self.runner.run(self.implementation, {"name": "world"})

        self.client_factory.assert_called_once_with(
            api_key="none", base_url=self.options.base_url, timeout=10
        )

    async def test_absent_usage_is_reported_as_unknown(self):
        del self.response["usage"]

        result = await self.runner.run(self.implementation, {"name": "world"})

        self.assertEqual(
            result.meta,
            OpenAIJinjaRunMeta(
                input_tokens=None, output_tokens=None, total_tokens=None
            ),
        )

    async def test_empty_schema_keeps_text_response(self):
        content = '{"answer": "hello"}'
        self.response["choices"][0]["message"]["content"] = content

        implementation = JinjaImplementation("Hello!", output_schema={})
        result = await self.runner.run(implementation, None)

        self.assertEqual(result.output, content)
        self.assertNotIn("response_format", json.loads(self.requests[-1].content))

    async def test_structured_output_sends_strict_schema_and_parses_json(self):
        schema = {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        }
        implementation = JinjaImplementation("Hello, {{ name }}!", output_schema=schema)
        self.response["choices"][0]["message"]["content"] = '{"answer": "Hello back!"}'

        result = await self.runner.run(implementation, {"name": "world"})

        self.assertEqual(result.output, {"answer": "Hello back!"})
        self.assertEqual(
            result.meta,
            OpenAIJinjaRunMeta(input_tokens=5, output_tokens=3, total_tokens=8),
        )
        self.assertEqual(
            json.loads(self.requests[0].content)["response_format"],
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "output",
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        self.assertEqual(implementation.output_schema, schema)
        self.assertIs(schema["additionalProperties"], False)

    async def test_nested_schema_is_sent_without_changes(self):
        schema = {
            "type": "object",
            "properties": {
                "records": {"type": "array", "items": {"$ref": "#/$defs/Record"}},
                "optional": {
                    "anyOf": [
                        {"type": "object", "properties": {"flag": {"type": "boolean"}}},
                        {"type": "null"},
                    ]
                },
            },
            "$defs": {
                "Record": {
                    "type": "object",
                    "properties": {"value": {"type": "integer"}},
                }
            },
        }
        implementation = JinjaImplementation("Hello!", output_schema=schema)
        output = {"records": [{"value": 3}], "optional": None}
        self.response["choices"][0]["message"]["content"] = json.dumps(output)

        result = await self.runner.run(implementation, None)

        sent_schema = json.loads(self.requests[0].content)["response_format"][
            "json_schema"
        ]["schema"]
        self.assertEqual(sent_schema, schema)
        self.assertEqual(result.output, output)
        self.assertEqual(implementation.output_schema, schema)

    async def test_invalid_structured_json_raises(self):
        implementation = JinjaImplementation("Hello!", output_schema={"type": "object"})
        self.response["choices"][0]["message"]["content"] = '{"answer":'

        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            await self.runner.run(implementation, None)

    async def test_manual_output_sends_schema_instruction_without_response_format(self):
        schema = {
            "type": "object",
            "properties": {"answer": {"type": "integer"}},
            "required": ["answer"],
        }
        implementation = JinjaImplementation("Answer!", schema)
        self.response["choices"][0]["message"]["content"] = (
            '<think>{"draft": 1}</think>\n```json\n{"answer": 42}\n```'
        )
        options = replace(
            self.options, structured_outputs=False, reasoning_end_tags=("</think>",)
        )
        result = await self.runner.run(implementation, None, options)
        self.assertEqual(result.output, {"answer": 42})
        self.assertEqual(result.meta.total_tokens, 8)
        sent = json.loads(self.requests[0].content)
        self.assertNotIn("response_format", sent)
        self.assertIn(
            json.dumps(schema, ensure_ascii=False), sent["messages"][0]["content"]
        )

    async def test_both_json_modes_validate_the_schema_and_reject_ambiguous_output(
        self,
    ):
        implementation = JinjaImplementation(
            "Answer!",
            {
                "type": "object",
                "properties": {"answer": {"type": "integer"}},
                "required": ["answer"],
            },
        )
        for structured in (True, False):
            options = replace(self.options, structured_outputs=structured)
            self.response["choices"][0]["message"]["content"] = (
                '{"answer": "wrong type"}'
            )
            with (
                self.subTest(structured=structured),
                self.assertRaises(ValidationError),
            ):
                await self.runner.run(implementation, None, options)
            self.response["choices"][0]["message"]["content"] = (
                '{"answer": 1} {"answer": 2}'
            )
            with self.assertRaises(ValueError):
                await self.runner.run(implementation, None, options)

    async def test_manual_mode_empty_schema_keeps_plain_text(self):
        self.response["choices"][0]["message"]["content"] = "<think>draft</think>hello"
        result = await self.runner.run(
            JinjaImplementation("Hello!", {}),
            None,
            replace(
                self.options, structured_outputs=False, reasoning_end_tags=("</think>",)
            ),
        )
        self.assertEqual(result.output, "<think>draft</think>hello")
        self.assertNotIn("response_format", json.loads(self.requests[0].content))

    async def test_recursive_references_and_boolean_data_are_preserved(self):
        schema = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False, "examples": [True]},
                "child": {"anyOf": [{"$ref": "#"}, {"type": "null"}]},
            },
        }
        implementation = JinjaImplementation("Hello!", schema)
        output = {"enabled": False, "child": {"enabled": True, "child": None}}
        self.response["choices"][0]["message"]["content"] = json.dumps(output)

        result = await self.runner.run(implementation, None)

        self.assertEqual(result.output, output)
        sent_schema = json.loads(self.requests[0].content)["response_format"][
            "json_schema"
        ]["schema"]
        self.assertEqual(sent_schema, schema)
        self.assertEqual(implementation.output_schema, schema)

    async def test_root_reference_is_sent_without_changes(self):
        schema = {
            "$ref": "#/$defs/Result",
            "$defs": {
                "Result": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                }
            },
        }
        implementation = JinjaImplementation("Hello!", schema)
        self.response["choices"][0]["message"]["content"] = '{"answer": "hello"}'

        result = await self.runner.run(implementation, None)

        self.assertEqual(result.output, {"answer": "hello"})
        sent_schema = json.loads(self.requests[0].content)["response_format"][
            "json_schema"
        ]["schema"]
        self.assertEqual(sent_schema, schema)
        self.assertEqual(implementation.output_schema, schema)

    async def test_shared_nested_schema_is_sent_without_mutation(self):
        shared = {"type": "object", "properties": {"flag": {"type": "boolean"}}}
        schema = {"type": "object", "properties": {"first": shared, "second": shared}}
        implementation = JinjaImplementation("Hello!", schema)
        output = {"first": {"flag": True}, "second": {"flag": False}}
        self.response["choices"][0]["message"]["content"] = json.dumps(output)

        result = await self.runner.run(implementation, None)

        self.assertEqual(result.output, output)
        self.assertEqual(implementation.output_schema, schema)
        self.assertNotIn("additionalProperties", shared)

    async def test_incomplete_or_refused_structured_output_raises(self):
        implementation = JinjaImplementation("Hello!", output_schema={"type": "object"})
        cases = (
            ("length", None, "did not finish"),
            ("content_filter", None, "did not finish"),
            ("stop", "Unable to answer", "refused"),
        )
        for finish_reason, refusal, error in cases:
            self.response["choices"][0]["finish_reason"] = finish_reason
            self.response["choices"][0]["message"] = {
                "role": "assistant",
                "content": "{}",
                "refusal": refusal,
            }
            with (
                self.subTest(finish_reason=finish_reason, refusal=refusal),
                self.assertRaisesRegex(RuntimeError, error),
            ):
                await self.runner.run(implementation, None)

    async def test_schema_rejection_is_delegated_to_provider(self):
        implementation = JinjaImplementation("Hello!", output_schema={"not": {}})
        self.status_code = 400
        self.response = {
            "error": {"message": "Invalid schema", "type": "invalid_request_error"}
        }

        with self.assertRaises(BadRequestError):
            await self.runner.run(implementation, None)

        sent_schema = json.loads(self.requests[0].content)["response_format"][
            "json_schema"
        ]["schema"]
        self.assertEqual(sent_schema, {"not": {}})
        self.assertTrue(self.clients[0].is_closed())

    async def test_boolean_subschemas_are_sent_without_changes(self):
        schema = {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "additionalProperties": False,
        }
        implementation = JinjaImplementation("Hello!", output_schema=schema)
        self.response["choices"][0]["message"]["content"] = '{"answer": "hello"}'

        result = await self.runner.run(implementation, None)

        sent_schema = json.loads(self.requests[0].content)["response_format"][
            "json_schema"
        ]["schema"]
        self.assertEqual(sent_schema, schema)
        self.assertEqual(implementation.output_schema, schema)
        self.assertEqual(result.output, {"answer": "hello"})

    async def test_invalid_completion_raises(self):
        cases = (
            ([], "no choices"),
            (
                [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": None},
                    }
                ],
                "no text content",
            ),
        )
        for choices, message in cases:
            self.response["choices"] = choices
            with (
                self.subTest(choices=choices),
                self.assertRaisesRegex(RuntimeError, message),
            ):
                await self.runner.run(self.implementation, {"name": "world"})
            self.assertTrue(self.clients[-1].is_closed())

    async def test_sdk_timeout_propagates_and_closes_client(self):
        self.transport_error = httpx2.ReadTimeout("Request timed out")
        options = OpenAIJinjaRunnerOptions(
            timeout=0.01,
            api_key=None,
            base_url=self.options.base_url,
            model=self.options.model,
        )

        with self.assertRaises(APITimeoutError):
            await self.runner.run(self.implementation, {"name": "world"}, options)

        self.assertEqual(self.clients[0].timeout, 0.01)
        self.assertTrue(self.clients[0].is_closed())

    async def test_none_timeout_disables_deadline(self):
        self.delay = 0.01
        options = OpenAIJinjaRunnerOptions(
            timeout=None,
            api_key=None,
            base_url=self.options.base_url,
            model=self.options.model,
        )

        result = await self.runner.run(self.implementation, {"name": "world"}, options)

        self.assertEqual(result.output, "Hello back!")
        self.assertIsNone(self.clients[0].timeout)

    async def test_external_cancellation_propagates(self):
        self.delay = 0.2
        task = asyncio.create_task(
            self.runner.run(self.implementation, {"name": "world"})
        )
        await self.started.wait()

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(self.cancelled)
        self.assertTrue(self.clients[0].is_closed())

    async def test_render_errors_do_not_call_api(self):
        with self.assertRaises(UndefinedError):
            await self.runner.run(self.implementation, {})

        self.client_factory.assert_not_called()

    async def test_api_errors_propagate_and_close_client(self):
        self.status_code = 400
        self.response = {
            "error": {"message": "Invalid request", "type": "invalid_request_error"}
        }

        with self.assertRaises(BadRequestError):
            await self.runner.run(self.implementation, {"name": "world"})

        self.assertTrue(self.clients[0].is_closed())


if __name__ == "__main__":
    unittest.main()
