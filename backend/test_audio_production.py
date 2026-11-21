"""Recorded audio checks: real short local MP3s, mocked SAPI, no provider calls."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from . import audio_production as audio


def write_wav(path, seconds):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, audio.SAMPLE_RATE, 0, 'NONE', 'not compressed'))
        # Nonzero alternating samples ensure this is actual decodable PCM.
        stream.writeframes(b'\x10\x00\xf0\xff' * round(seconds * audio.SAMPLE_RATE / 2))


class AudioProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls.fixture.name)
        for name, seconds in [('short', .3), ('long', .5)]:
            wav = cls.fixture_root / (name + '.wav')
            write_wav(wav, seconds)
            audio._encode(wav, cls.fixture_root / (name + '.mp3'))
        cls.mp3 = (cls.fixture_root / 'short.mp3').read_bytes()
        cls.short_duration = len(audio._decode_pcm(cls.fixture_root / 'short.mp3')) / audio.PCM_BYTES_PER_SECOND
        cls.long_duration = len(audio._decode_pcm(cls.fixture_root / 'long.mp3')) / audio.PCM_BYTES_PER_SECOND

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / 'media'
        self.root.mkdir()
        self.chapter = {
            'story_id': 'story-a', 'title': 'Evidence and limitations',
            'text': 'A claim. But uncertain.',
            'claim_source_ids': ['source-a'],
            'sources': [{'article_id': 'source-a', 'url': 'https://example.com/report'}],
            'turns': [
                {'speaker': 'maya', 'text': 'A claim.', 'source_ids': ['source-a']},
                {'speaker': 'leo', 'text': 'But uncertain.', 'source_ids': ['source-a']},
            ],
        }

    def tearDown(self):
        self.temporary.cleanup()

    def result(self):
        characters = list(''.join(turn['text'] for turn in self.chapter['turns']))
        step = self.short_duration / len(characters)
        boundary = len(self.chapter['turns'][0]['text'])
        return {
            'audio_base64': base64.b64encode(self.mp3).decode('ascii'),
            'alignment': {
                'characters': characters,
                'character_start_times_seconds': [index * step for index in range(len(characters))],
                'character_end_times_seconds': [(index + 1) * step for index in range(len(characters))],
            },
            'voice_segments': [
                {'voice_id': 'maya-voice', 'start_time_seconds': 0,
                 'end_time_seconds': boundary * step, 'dialogue_input_index': 0,
                 'character_start_index': 0, 'character_end_index': boundary},
                {'voice_id': 'leo-voice', 'start_time_seconds': boundary * step,
                 'end_time_seconds': self.short_duration, 'dialogue_input_index': 1,
                 'character_start_index': boundary, 'character_end_index': len(characters)},
            ],
        }

    def fake_sapi(self, turns, language, directory):
        items = []
        for index, turn in enumerate(turns):
            filename = f'{index}.wav'
            write_wav(directory / filename, .2 + index * .1)
            items.append({'file': filename, 'voice_id': turn['speaker'] + '-installed'})
        return items

    def chapter_audio(self, name='short', provider='microsoft-sapi'):
        target = self.root / (name + '.mp3')
        target.write_bytes((self.fixture_root / (name + '.mp3')).read_bytes())
        return {'url': '/media/' + target.name, 'duration_seconds': 999,
                'provider': provider, 'voice_ids': [provider + '-voice']}

    def test_natural_mp3_is_measured_and_script_is_unchanged(self):
        original = copy.deepcopy(self.chapter)
        value = audio.persist_natural_chapter(self.chapter, self.result(), self.root, 'safe-key')
        target = audio._media_file(value['url'], self.root)
        self.assertEqual(target.read_bytes(), self.mp3)
        self.assertAlmostEqual(value['duration_seconds'], self.short_duration, places=6)
        self.assertEqual(value['provider'], 'elevenlabs')
        self.assertEqual(value['voice_ids'], ['maya-voice', 'leo-voice'])
        self.assertEqual(self.chapter, original)
        self.assertEqual(value['alignment'], self.result()['alignment'])
        self.assertEqual(value['url'], audio.persist_natural_chapter(self.chapter, self.result(), self.root, 'safe-key')['url'])

    def test_natural_rejects_bad_base64_and_non_mp3(self):
        for encoded in ['bad!', '', base64.b64encode(b'not mp3').decode('ascii'),
                        base64.b64encode((self.fixture_root / 'short.wav').read_bytes()).decode('ascii')]:
            with self.subTest(encoded=encoded[:20]):
                value = self.result()
                value['audio_base64'] = encoded
                with self.assertRaises(ValueError):
                    audio.persist_natural_chapter(self.chapter, value, self.root, 'key')
        self.assertFalse(list(self.root.rglob('*.mp3')))

    def test_natural_rejects_corrupted_audio_even_with_mp3_header(self):
        value = self.result()
        value['audio_base64'] = base64.b64encode(b'ID3' + b'broken' * 20).decode('ascii')
        with self.assertRaises(ValueError):
            audio.persist_natural_chapter(self.chapter, value, self.root, 'key')
        self.assertFalse(list(self.root.rglob('*.mp3')))

    def test_alignment_must_cover_all_qualifications_and_have_valid_timing(self):
        variations = []
        value = self.result()
        value['alignment']['characters'][-1] = '!'
        variations.append(value)
        value = self.result()
        value['alignment']['character_start_times_seconds'][0] = -1
        variations.append(value)
        value = self.result()
        value['alignment']['character_end_times_seconds'][-1] = self.short_duration + 1
        variations.append(value)
        value = self.result()
        value['alignment']['character_start_times_seconds'][2] = float('nan')
        variations.append(value)
        value = self.result()
        value['alignment']['character_end_times_seconds'].pop()
        variations.append(value)
        for index, result in enumerate(variations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                audio.persist_natural_chapter(self.chapter, result, self.root, 'key')
        self.assertFalse(list(self.root.rglob('*.mp3')))

    def test_voice_segments_must_cover_every_input_with_two_consistent_voices(self):
        variations = []
        value = self.result()
        value['voice_segments'] = []
        variations.append(value)
        value = self.result()
        value['voice_segments'].pop()
        variations.append(value)
        for field, replacement in [('voice_id', 'maya-voice'), ('dialogue_input_index', 0),
                                   ('dialogue_input_index', True), ('start_time_seconds', -1),
                                   ('character_end_index', 999)]:
            value = self.result()
            value['voice_segments'][1][field] = replacement
            variations.append(value)
        for index, result in enumerate(variations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                audio.persist_natural_chapter(self.chapter, result, self.root, 'key')
        self.assertFalse(list(self.root.rglob('*.mp3')))

    def test_basic_audio_caches_full_approved_turns_and_measured_alignment(self):
        original = copy.deepcopy(self.chapter)
        with patch.object(audio, '_sapi_render', side_effect=self.fake_sapi) as synthesizer:
            value = audio.render_basic_chapter(self.chapter, 'en', self.root, '../never-a-path')
            cached = audio.render_basic_chapter(self.chapter, 'en', self.root, '../never-a-path')
        self.assertEqual(synthesizer.call_count, 1)
        self.assertEqual(cached, value)
        self.assertEqual(value['provider'], 'microsoft-sapi')
        self.assertAlmostEqual(value['duration_seconds'], .2 + .12 + .3, places=4)
        self.assertEqual(value['voice_ids'], ['maya-installed', 'leo-installed'])
        rendered = value['alignment']['turns']
        self.assertEqual([item['text'] for item in rendered], [item['text'] for item in self.chapter['turns']])
        self.assertEqual(rendered[0]['source_ids'], ['source-a'])
        self.assertAlmostEqual(rendered[1]['start_seconds'], .32, places=6)
        self.assertEqual(self.chapter, original)

    def test_basic_cache_invalidates_when_approved_text_or_language_changes(self):
        with patch.object(audio, '_sapi_render', side_effect=self.fake_sapi) as synthesizer:
            first = audio.render_basic_chapter(self.chapter, 'en', self.root, 'key')
            self.chapter['turns'][1]['text'] += ' With an added qualification.'
            changed = audio.render_basic_chapter(self.chapter, 'en', self.root, 'key')
            language = audio.render_basic_chapter(self.chapter, 'nl', self.root, 'key')
        self.assertEqual(synthesizer.call_count, 3)
        self.assertEqual(len({first['url'], changed['url'], language['url']}), 3)

    def test_corrupted_basic_cache_is_rendered_again(self):
        with patch.object(audio, '_sapi_render', side_effect=self.fake_sapi) as synthesizer:
            first = audio.render_basic_chapter(self.chapter, 'en', self.root, 'key')
            audio._media_file(first['url'], self.root).write_bytes(b'corrupted')
            second = audio.render_basic_chapter(self.chapter, 'en', self.root, 'key')
        self.assertEqual(synthesizer.call_count, 2)
        self.assertEqual(first['url'], second['url'])
        self.assertGreater(second['duration_seconds'], 0)

    def test_sapi_uses_fixed_file_and_json_input_instead_of_interpolated_text(self):
        self.chapter['turns'][0]['text'] = 'Quotes " & $(Write-Output injected) `; <speak>still text</speak>'
        captured = {}
        def run(arguments, **kwargs):
            captured['arguments'] = arguments
            request = json.loads(Path(arguments[-1]).read_text(encoding='utf-8'))
            captured['request'] = request
            Path(request['result_path']).write_text(json.dumps({'turns': [
                {'file': 'a.wav'}, {'file': 'b.wav'}]}), encoding='utf-8')
            return b''
        with tempfile.TemporaryDirectory(dir=self.root) as temporary, patch.object(audio, '_run', side_effect=run):
            audio._sapi_render(self.chapter['turns'], 'en', Path(temporary))
        self.assertIn('-File', captured['arguments'])
        self.assertNotIn('-Command', captured['arguments'])
        self.assertEqual(captured['request']['turns'], self.chapter['turns'])
        self.assertFalse(any(self.chapter['turns'][0]['text'] in item for item in captured['arguments']))

    def test_assembly_has_one_content_hash_file_and_sample_count_boundaries(self):
        first = copy.deepcopy(self.chapter)
        first['audio'] = self.chapter_audio('short')
        second = copy.deepcopy(self.chapter)
        second['story_id'] = 'story-b'
        second['audio'] = self.chapter_audio('long')
        edition = {'id': 'edition', 'chapters': [first, second], 'estimated_seconds': 999, 'language': 'en'}
        original = copy.deepcopy(edition)
        result = audio.combine_episode(edition, self.root)
        path = audio._media_file(result['episode_audio']['url'], self.root)
        self.assertEqual(path.stem, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result['audio_mode'], 'basic-audio')
        self.assertEqual(result['episode_audio']['timing_basis'], 'measured')
        self.assertAlmostEqual(result['chapters'][0]['start_seconds'], 0)
        self.assertAlmostEqual(result['chapters'][0]['end_seconds'], self.short_duration)
        self.assertAlmostEqual(result['chapters'][1]['start_seconds'], self.short_duration)
        self.assertAlmostEqual(result['chapters'][1]['end_seconds'], result['duration_seconds'])
        self.assertAlmostEqual(result['duration_seconds'], self.short_duration + self.long_duration, places=4)
        self.assertEqual(result['estimated_seconds'], result['duration_seconds'])
        self.assertEqual(result['chapters'][1]['turns'], original['chapters'][1]['turns'])
        self.assertEqual(result['chapters'][1]['sources'], original['chapters'][1]['sources'])
        self.assertEqual(edition, original)
        again = audio.combine_episode(edition, self.root)
        self.assertEqual(again['episode_audio']['url'], result['episode_audio']['url'])
        self.assertEqual(len(list((self.root / 'episodes').glob('*.mp3'))), 1)

    def test_assembly_modes_follow_actual_provider(self):
        for providers, mode in [(['elevenlabs'], 'elevenlabs'),
                                (['elevenlabs', 'microsoft-sapi'], 'mixed-audio')]:
            chapters = [{**self.chapter, 'audio': self.chapter_audio(provider=provider)} for provider in providers]
            with self.subTest(mode=mode):
                value = audio.combine_episode({'chapters': chapters}, self.root)
                self.assertEqual(value['audio_mode'], mode)

    def test_assembly_rejects_missing_audio_and_unsafe_urls(self):
        bad = ['https://example.com/a.mp3', '/media/../outside.mp3', '/media/%2e%2e/outside.mp3',
               '/media/C:/outside.mp3', '/media/short.mp3?x=1', '/media/..%5coutside.mp3', '/media/missing.mp3']
        for url in bad:
            chapter = {**self.chapter, 'audio': {'url': url}}
            with self.subTest(url=url), self.assertRaises(ValueError):
                audio.combine_episode({'chapters': [chapter]}, self.root)
        for edition in [{}, {'chapters': []}, {'chapters': [self.chapter]}]:
            with self.assertRaises(ValueError):
                audio.combine_episode(edition, self.root)

    def test_invalid_approved_turns_or_language_are_rejected_before_speech(self):
        with patch.object(audio, '_sapi_render') as synthesizer:
            for field, value in [('speaker', 'someone'), ('text', ''), ('source_ids', ['unknown'])]:
                chapter = copy.deepcopy(self.chapter)
                chapter['turns'][0][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    audio.render_basic_chapter(chapter, 'en', self.root, 'key')
            with self.assertRaises(ValueError):
                audio.render_basic_chapter(self.chapter, 'en;injected', self.root, 'key')
            synthesizer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
