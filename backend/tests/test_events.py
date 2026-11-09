import env  # noqa: F401
import json
import unittest

from app.config import settings
from app.runtime.events import DoneEvent, ToolCallEvent, to_sse


class ToSseTests(unittest.TestCase):
    def test_env_overrides_real_settings(self):
        self.assertEqual(settings.environment, "test")
        self.assertIn("localhost:5432/test", settings.database_url)

    def test_frame_has_event_name_and_json_data(self):
        frame = to_sse(ToolCallEvent(id="call_1", name="now", args={"z": "1"}))
        event_line, data_line, *_ = frame.split("\n")
        self.assertEqual(event_line, "event: tool_call")
        self.assertEqual(
            json.loads(data_line.removeprefix("data: ")),
            {"type": "tool_call", "id": "call_1", "name": "now", "args": {"z": "1"}},
        )

    def test_frame_ends_with_blank_line(self):
        self.assertTrue(to_sse(DoneEvent(reply="hi")).endswith("\n\n"))

    def test_newlines_in_text_stay_on_one_data_line(self):
        frame = to_sse(DoneEvent(reply="line one\nline two"))
        self.assertEqual(len(frame.strip().split("\n")), 2)


if __name__ == "__main__":
    unittest.main()
