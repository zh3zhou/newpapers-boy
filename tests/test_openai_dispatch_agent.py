#!/usr/bin/env python

import unittest

from scripts.openai_dispatch_agent import (
    add_citation_links,
    build_prompt,
    extract_output_text,
    strip_markdown_fence,
)


class OpenAIDispatchAgentTests(unittest.TestCase):
    def test_prompt_requires_diverse_art_web_search_sources(self):
        prompt = build_prompt("2026-07-24", "agent contract", "content config")

        self.assertIn("广域 web search", prompt)
        self.assertIn("不得从固定站点抓取或默认只查 MoMA", prompt)
        self.assertIn("默认目标 5 条艺术内容", prompt)
        self.assertIn("至少 3 个相互独立的", prompt)
        self.assertIn("同一来源最多 2 条", prompt)

    def test_extracts_only_message_output_text(self):
        payload = {
            "output": [
                {"type": "web_search_call"},
                {"type": "message", "content": [
                    {"type": "output_text", "text": "# title"},
                    {"type": "refusal", "refusal": "no"},
                ]},
            ]
        }
        self.assertEqual(extract_output_text(payload), "# title")

    def test_strips_markdown_fence(self):
        self.assertEqual(strip_markdown_fence("```markdown\n# title\n```"), "# title")

    def test_materializes_web_search_citation_urls(self):
        text = "Source"
        annotations = [{
            "type": "url_citation",
            "start_index": 0,
            "end_index": 6,
            "url": "https://example.com/paper",
        }]
        self.assertEqual(
            add_citation_links(text, annotations),
            "[Source](https://example.com/paper)",
        )


if __name__ == "__main__":
    unittest.main()
