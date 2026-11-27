"""Offline audio checks: run with python3 -m unittest discover -s tests -p test_audio_failures.py."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import config
from agents import audio_agent
from models import Stop, TripPlan


class AudioFailureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.plan = TripPlan('Mobile', stops=[Stop(name='Mobile', narration='Welcome to Mobile.')])
        self.output = config.audio_path(self.root, 1)

    def assert_clean_failure(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.rglob('*.partial.mp3')), [])

    def fake_client(self, chunks):
        return SimpleNamespace(text_to_speech=SimpleNamespace(convert=lambda **kwargs: chunks))

    def test_empty_narration_rejected_without_client(self):
        self.plan.stops[0].narration = ' '
        with patch.object(config, 'MOCK_MODE', False), patch.object(audio_agent, '_speech_client') as client:
            with self.assertRaisesRegex(ValueError, 'add a narration'):
                audio_agent.make_voiceovers(self.plan, self.root)
            client.assert_not_called()
        self.assert_clean_failure()

    def test_empty_stream_leaves_no_files(self):
        with patch.object(config, 'MOCK_MODE', False), patch.object(audio_agent, '_speech_client', return_value=self.fake_client(iter([]))):
            with self.assertRaisesRegex(RuntimeError, 'empty audio'):
                audio_agent.make_voiceovers(self.plan, self.root)
        self.assert_clean_failure()

    def test_interrupted_stream_leaves_no_files(self):
        def chunks():
            yield b'partial recording'
            raise ConnectionError('connection lost')
        with patch.object(config, 'MOCK_MODE', False), patch.object(audio_agent, '_speech_client', return_value=self.fake_client(chunks())):
            with self.assertRaises(RuntimeError):
                audio_agent.make_voiceovers(self.plan, self.root)
        self.assert_clean_failure()

    def test_empty_cached_file_is_regenerated_in_mock_mode(self):
        self.output.parent.mkdir()
        self.output.touch()
        def write_mock(path, narration):
            path.write_bytes(b'fake audio for file-handling test')
        with patch.object(config, 'MOCK_MODE', True), patch.object(audio_agent, 'make_mock_audio', side_effect=write_mock) as mock_audio, patch.object(audio_agent, '_speech_client') as client:
            self.assertEqual(audio_agent.make_voiceovers(self.plan, self.root), [self.output])
            mock_audio.assert_called_once()
            client.assert_not_called()
        self.assertGreater(self.output.stat().st_size, 0)
        self.assertEqual(list(self.root.rglob('*.partial.mp3')), [])

    def test_existing_nonempty_file_is_reused_without_client(self):
        self.output.parent.mkdir()
        self.output.write_bytes(b'existing audio')
        with patch.object(config, 'MOCK_MODE', False), patch.object(audio_agent, '_speech_client') as client:
            self.assertEqual(audio_agent.make_voiceovers(self.plan, self.root), [self.output])
            client.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'existing audio')

    def test_folder_error_has_actionable_message(self):
        self.output.parent.write_text('blocks audio directory')
        with patch.object(config, 'MOCK_MODE', True):
            with self.assertRaisesRegex(RuntimeError, 'output-folder permissions'):
                audio_agent.make_voiceovers(self.plan, self.root)
        self.assert_clean_failure()

    def test_rename_failure_cleans_temporary_file(self):
        with patch.object(config, 'MOCK_MODE', False), patch.object(audio_agent, '_speech_client', return_value=self.fake_client([b'audio'])), patch.object(Path, 'replace', side_effect=PermissionError('denied')):
            with self.assertRaisesRegex(RuntimeError, 'output-folder permissions'):
                audio_agent.make_voiceovers(self.plan, self.root)
        self.assert_clean_failure()


if __name__ == '__main__':
    unittest.main()
