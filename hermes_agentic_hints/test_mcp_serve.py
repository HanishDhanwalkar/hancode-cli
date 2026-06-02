from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from hermes_agentic_hints import mcp_serve
from hermes_agentic_hints.state import SessionDB


class MCPServeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_agentic_home = os.environ.get("AGENTIC_HOME")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AGENTIC_HOME"] = self.tmp.name

        self.home = Path(self.tmp.name)
        self.sessions_dir = self.home / "sessions"
        self.sessions_dir.mkdir(parents=True)
        self.session_id = "session-1"
        self.session_key = "telegram:chat-1"
        self.session_path = self.sessions_dir / f"{self.session_id}.json"

        self._write_index()
        self._write_messages([
            {
                "id": "m1",
                "role": "user",
                "content": "hello hermes",
                "timestamp": 1,
            },
            {
                "id": "m2",
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "hello back"},
                    {"type": "image_url", "image_url": {"url": "https://example.test/a.png"}},
                ],
                "timestamp": 2,
            },
        ])

    def tearDown(self) -> None:
        if self._old_agentic_home is None:
            os.environ.pop("AGENTIC_HOME", None)
        else:
            os.environ["AGENTIC_HOME"] = self._old_agentic_home
        self.tmp.cleanup()

    def _write_index(self) -> None:
        (self.sessions_dir / "sessions.json").write_text(
            json.dumps(
                {
                    self.session_key: {
                        "session_id": self.session_id,
                        "platform": "telegram",
                        "chat_type": "private",
                        "display_name": "Hermes Test Chat",
                        "updated_at": "2026-06-02T10:00:00",
                        "origin": {
                            "platform": "telegram",
                            "chat_id": "chat-1",
                            "chat_name": "Hermes Test Chat",
                            "user_name": "Tester",
                        },
                    }
                }
            ),
            encoding="utf-8",
        )

    def _write_messages(self, messages: list[dict]) -> None:
        self.session_path.write_text(
            json.dumps({"messages": messages}),
            encoding="utf-8",
        )

    def _tools(self) -> dict:
        server = mcp_serve.create_mcp_server(event_bridge=mcp_serve.EventBridge())
        return server.tools

    def test_conversation_message_attachment_and_channel_tools(self) -> None:
        tools = self._tools()

        conversations = json.loads(tools["conversations_list"]())
        self.assertEqual(conversations["count"], 1)
        self.assertEqual(conversations["conversations"][0]["session_key"], self.session_key)

        conversation = json.loads(tools["conversation_get"](self.session_key))
        self.assertEqual(conversation["display_name"], "Hermes Test Chat")
        self.assertEqual(conversation["chat_id"], "chat-1")

        messages = json.loads(tools["messages_read"](self.session_key, limit=10))
        self.assertEqual(messages["count"], 2)
        self.assertEqual(messages["messages"][1]["content"], "hello back")

        attachments = json.loads(tools["attachments_fetch"](self.session_key, "m2"))
        self.assertEqual(attachments["count"], 1)
        self.assertEqual(attachments["attachments"][0]["type"], "image")

        channels = json.loads(tools["channels_list"]())
        self.assertEqual(channels["channels"][0]["target"], "telegram:chat-1")

    def test_permissions_round_trip(self) -> None:
        bridge = mcp_serve.EventBridge()
        bridge._pending_approvals["approval-1"] = {
            "id": "approval-1",
            "session_key": self.session_key,
            "created_at": "2026-06-02T10:00:01",
        }
        tools = mcp_serve.create_mcp_server(event_bridge=bridge).tools

        open_permissions = json.loads(tools["permissions_list_open"]())
        self.assertEqual(open_permissions["count"], 1)

        response = json.loads(tools["permissions_respond"]("approval-1", "allow-once"))
        self.assertTrue(response["resolved"])

        events = json.loads(tools["events_poll"]())
        self.assertEqual(events["events"][0]["type"], "approval_resolved")

    def test_event_bridge_polls_json_session_archives(self) -> None:
        bridge = mcp_serve.EventBridge()
        db = SessionDB()

        bridge._poll_once(db)
        first_poll = bridge.poll_events()
        self.assertEqual(len(first_poll["events"]), 2)

        self._write_messages([
            {
                "id": "m1",
                "role": "user",
                "content": "hello hermes",
                "timestamp": 1,
            },
            {
                "id": "m2",
                "role": "assistant",
                "content": "hello back",
                "timestamp": 2,
            },
            {
                "id": "m3",
                "role": "user",
                "content": "new live message",
                "timestamp": 3,
            },
        ])
        future = time.time() + 5
        os.utime(self.session_path, (future, future))

        bridge._poll_once(db)
        second_poll = bridge.poll_events(after_cursor=first_poll["next_cursor"])
        self.assertEqual(len(second_poll["events"]), 1)
        self.assertEqual(second_poll["events"][0]["message_id"], "m3")


if __name__ == "__main__":
    unittest.main()
