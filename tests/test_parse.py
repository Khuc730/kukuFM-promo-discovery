from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parse import ParseError, parse_episode, timestamp_to_seconds


class ParserTests(unittest.TestCase):
    def test_timestamp(self):
        self.assertEqual(timestamp_to_seconds("01:02.50", source="test"), 62.5)

    def test_rejects_bad_timestamp(self):
        with self.assertRaises(ParseError):
            timestamp_to_seconds("1:62", source="test")

    def test_parse_sample_episode(self):
        # Set KUKU_SAMPLE_EPISODE to a local .txt screenplay before running this test.
        import os
        sample = os.environ.get("KUKU_SAMPLE_EPISODE")
        if not sample:
            self.skipTest("Set KUKU_SAMPLE_EPISODE to a screenplay path")
        episode = parse_episode(sample)
        self.assertGreater(len(episode.scenes), 0)
        self.assertGreater(sum(len(s.elements) for s in episode.scenes), 0)


if __name__ == "__main__":
    unittest.main()
