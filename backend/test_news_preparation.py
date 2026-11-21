"""Source quote validation, durable news preparation and conservative grouping."""
import contextlib
import copy
import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import news_preparation as news
from .cloud_client import CloudError


class NewsPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / 'data').mkdir()
        (self.root / 'media').mkdir()
        self.database = self.root / 'test.db'
        self.path = self.root / 'data' / 'catalog.json'
        self.clock = dt.datetime(2026, 11, 21, 12, tzinfo=dt.timezone.utc)
        self.source = {'article_id': 'article-new', 'headline': 'Original untranslated headline',
                       'outlet': 'Evidence Daily', 'language': 'en', 'date': self.clock.isoformat(),
                       'url': 'https://example.com/new-report', 'translation_key': 'article-new'}
        self.original = {'article_id': 'article-new', 'title': self.source['headline'], 'outlet': 'Evidence Daily',
                         'language': 'en', 'date': self.clock.isoformat(),
                         'paragraphs': ['The company reported revenue growth of 10 percent.',
                                        'The company said the outlook remains uncertain and is not a guarantee.']}
        self.imported = {'id': 'item-new', 'title': self.source['headline'], 'titles': {'en': self.source['headline']},
                         'summary': 'Open the original report.', 'summaries': {}, 'tags': ['technology'],
                         'sources': [copy.deepcopy(self.source)], 'claim_source_ids': [],
                         'published_at': self.clock.isoformat(), 'updated_at': self.clock.isoformat(),
                         'fresh_import': True, 'curated': False, 'entities': ['Example Company'], 'art': 'sage'}
        self.existing = {'id': 'story-existing', 'title': 'Previous company results', 'titles': {'en': 'Previous company results'},
                         'summary': 'Older checked facts remain separate.', 'summaries': {'en': 'Older checked facts remain separate.'},
                         'tags': ['technology'], 'sources': [{'article_id': 'older-article', 'headline': 'Original older headline',
                              'language': 'de', 'outlet': 'Other Outlet', 'date': '2026-11-19T12:00:00+00:00'}],
                         'claim_source_ids': ['older-article'], 'claims': [{'article_id': 'older-article',
                              'quote': 'Original older evidence.', 'text': 'Older checked facts.'}],
                         'published_at': '2026-11-19T12:00:00+00:00', 'updated_at': '2026-11-19T12:00:00+00:00',
                         'curated': True, 'entities': ['Example Company']}
        self.catalog = {'version': 'original', 'as_of': '2026-11-19T12:00:00+00:00',
                        'topics': [{'id': 'technology', 'label': 'Technology & AI'}],
                        'stories': [copy.deepcopy(self.existing), copy.deepcopy(self.imported)], 'stats': {}}
        self.write_catalog()
        self.svc = SimpleNamespace(ROOT=self.root, CATALOG_PATH=self.path, CATALOG=copy.deepcopy(self.catalog),
            conn=self.connection, now=lambda: self.clock.isoformat(), refresh_catalog=self.refresh,
            read_article=lambda identifier: copy.deepcopy(self.original) if identifier == 'article-new' else None)
        self.config = {'ai_ready': True}
        self.connection_patch = patch.object(news.cloud_client, 'connection', side_effect=lambda *args: self.config)
        self.connection_patch.start()
        self.audio_patch = patch.object(news.audio_production, 'render_basic_chapter', side_effect=self.render)
        self.renderer = self.audio_patch.start()

    def tearDown(self):
        self.audio_patch.stop()
        self.connection_patch.stop()
        self.temporary.cleanup()

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def write_catalog(self):
        self.path.write_text(json.dumps(self.catalog, ensure_ascii=False), encoding='utf-8')

    def refresh(self):
        self.svc.CATALOG = json.loads(self.path.read_text(encoding='utf-8'))

    def response(self):
        return {'ok': True, 'story': {
            'title': 'Company growth and its limits',
            'titles': {'en': 'Company growth and its limits', 'nl': 'Groei van het bedrijf en de beperkingen',
                       'de': 'Unternehmenswachstum und seine Grenzen'},
            'summaries': {'en': 'The company reported revenue growth of 10 percent. Its outlook remains uncertain.',
                          'nl': 'Het bedrijf meldt een omzetgroei van 10 procent. De vooruitzichten blijven onzeker.',
                          'de': 'Das Unternehmen meldet ein Umsatzwachstum von 10 Prozent. Der Ausblick bleibt unsicher.'},
            'tags': [{'id': 'news-example-company', 'label': 'Example Company', 'parent': 'technology'}],
            'claims': [{'article_id': 'article-new', 'quote': self.original['paragraphs'][0],
                        'text': 'The company reported revenue growth of 10 percent.'},
                       {'article_id': 'article-new', 'quote': self.original['paragraphs'][1],
                        'text': 'The outlook remains uncertain.'}],
            'claim_source_ids': ['article-new'], 'relation': 'new', 'evidence_review': {'passed': True}},
            'usage': {'input_tokens': 100, 'output_tokens': 80, 'model': 'test-model', 'api_key': 'do-not-persist'}}

    def render(self, chapter, language, media, key):
        path = Path(media) / (key + '.mp3')
        path.write_bytes(b'ID3mock')
        return {'url': '/media/' + path.name, 'duration_seconds': 10, 'provider': 'microsoft-sapi',
                'voice_ids': ['installed-' + language]}

    def prepared(self):
        catalog = json.loads(self.path.read_text(encoding='utf-8'))
        return next(story for story in catalog['stories'] if story['id'] == 'item-new')

    def row(self):
        with self.connection() as db:
            return dict(db.execute('SELECT * FROM news_preparations ORDER BY created_at LIMIT 1').fetchone())

    def advance(self):
        self.clock += dt.timedelta(minutes=4)

    def test_disconnected_ai_performs_no_provider_calls_or_mutation(self):
        self.config['ai_ready'] = False
        original = self.path.read_bytes()
        with patch.object(news.cloud_client, 'invoke') as invoke:
            self.assertFalse(news.process_one(self.svc))
            invoke.assert_not_called()
        self.assertEqual(self.path.read_bytes(), original)
        self.renderer.assert_not_called()

    def test_checked_publication_preserves_originals_languages_and_creates_three_sourced_audios(self):
        original = copy.deepcopy(self.original)
        original_source = copy.deepcopy(self.source)
        with patch.object(news.cloud_client, 'invoke', return_value=self.response()) as invoke:
            self.assertTrue(news.process_one(self.svc))
            self.assertFalse(news.process_one(self.svc))
        self.assertEqual(invoke.call_count, 1)
        request = invoke.call_args.args[1]
        self.assertEqual(request['paragraphs'], original['paragraphs'])
        self.assertEqual(request['title'], original['title'])
        story = self.prepared()
        self.assertTrue(story['curated'])
        self.assertEqual(story['sources'], [original_source])
        self.assertEqual(self.original, original)
        self.assertEqual(story['original_titles']['article-new']['title'], self.source['headline'])
        self.assertEqual(story['original_titles']['article-new']['language'], 'en')
        self.assertTrue(story['translation_provenance']['nl']['translated_by_ai'])
        self.assertFalse(story['translation_provenance']['en']['translated_by_ai'])
        self.assertEqual(story['summary_source_ids'], {'en': ['article-new'], 'nl': ['article-new'], 'de': ['article-new']})
        self.assertEqual(self.renderer.call_count, 3)
        manifest = json.loads((self.root / 'data' / 'demo-story-audio.json').read_text())
        self.assertEqual(set(manifest['stories']['item-new']), {'en', 'nl', 'de'})
        for language, audio in manifest['stories']['item-new'].items():
            self.assertEqual(audio['provider'], 'microsoft-sapi')
            self.assertEqual(audio['source_ids'], ['article-new'])
            self.assertEqual(audio['language'], language)
        for call in self.renderer.call_args_list:
            chapter = call.args[0]
            self.assertIn('Evidence Daily', chapter['turns'][0]['text'])
            self.assertEqual(chapter['turns'][0]['source_ids'], ['article-new'])
        self.assertEqual(self.row()['state'], 'ready')
        usage = json.loads(self.row()['usage'])
        self.assertEqual(usage['input_tokens'], 100)
        self.assertNotIn('api_key', usage)
        catalog = json.loads(self.path.read_text())
        self.assertNotEqual(catalog['version'], 'original')
        self.assertEqual(catalog['as_of'], self.clock.isoformat())
        self.assertIn('news-example-company', story['tags'])
        topic = next(topic for topic in catalog['topics'] if topic['id'] == 'news-example-company')
        self.assertTrue(topic['dynamic'])

    def test_fabricated_quote_cannot_curate_or_create_audio(self):
        response = self.response()
        response['story']['claims'][0]['quote'] = 'This fabricated quotation does not occur in the original.'
        with patch.object(news.cloud_client, 'invoke', return_value=response) as invoke:
            self.assertTrue(news.process_one(self.svc))
            self.assertFalse(news.process_one(self.svc))
        self.assertEqual(invoke.call_count, 1)
        self.assertFalse(self.prepared()['curated'])
        self.assertEqual(self.prepared()['claim_source_ids'], [])
        self.assertEqual(self.row()['state'], 'failed')
        self.renderer.assert_not_called()

    def test_wrong_source_or_new_number_or_failed_review_cannot_publish(self):
        request = news._request(self.svc, self.imported, self.catalog)
        for mutation in ['claim-source', 'summary-source', 'claim-number', 'summary-number', 'review', 'missing-language']:
            response = self.response()
            story = response['story']
            if mutation == 'claim-source':
                story['claims'][0]['article_id'] = 'older-article'
            elif mutation == 'summary-source':
                story['claim_source_ids'].append('older-article')
            elif mutation == 'claim-number':
                story['claims'][0]['text'] = 'The company reported 99 percent growth.'
            elif mutation == 'summary-number':
                story['summaries']['nl'] = 'De omzet steeg met 99 procent.'
            elif mutation == 'review':
                story['evidence_review']['passed'] = False
            else:
                story['summaries'].pop('de')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                news._validate(response, request, self.catalog)

    def test_related_development_stays_separate_and_does_not_overwrite_older_checked_claims(self):
        response = self.response()
        response['story'].update({'related_story_id': 'story-existing', 'relation': 'same-event'})
        with patch.object(news.cloud_client, 'invoke', return_value=response):
            news.process_one(self.svc)
        catalog = json.loads(self.path.read_text())
        older = next(story for story in catalog['stories'] if story['id'] == 'story-existing')
        self.assertEqual(older, self.existing)
        self.assertEqual(len(catalog['stories']), 2)
        story = self.prepared()
        self.assertEqual(story['related_story_id'], 'story-existing')
        self.assertEqual(story['relation'], 'same-event')
        self.assertEqual(story['merge_policy'], 'separate-reviewed-coverage')
        self.assertEqual(story['claim_source_ids'], ['article-new'])
        self.assertNotIn('older-article', story['summary_source_ids']['en'])

    def test_unknown_semantic_reference_is_never_merged_or_linked(self):
        response = self.response()
        response['story'].update({'related_story_id': 'not-a-candidate', 'relation': 'translation'})
        with patch.object(news.cloud_client, 'invoke', return_value=response):
            news.process_one(self.svc)
        story = self.prepared()
        self.assertEqual(story['relation'], 'new')
        self.assertNotIn('related_story_id', story)
        self.assertEqual(story['sources'], [self.source])

    def test_existing_multiple_original_languages_and_source_metadata_survive(self):
        second = {**self.source, 'article_id': 'article-dutch', 'headline': 'Oorspronkelijke Nederlandse kop',
                  'language': 'nl', 'date': '2026-11-20T10:00:00+00:00'}
        self.catalog['stories'][1]['sources'].append(copy.deepcopy(second))
        self.write_catalog()
        with patch.object(news.cloud_client, 'invoke', return_value=self.response()):
            news.process_one(self.svc)
        story = self.prepared()
        self.assertEqual(story['sources'], [self.source, second])
        self.assertEqual(story['original_titles']['article-dutch'], {'title': second['headline'], 'language': 'nl'})
        self.assertEqual(story['claim_source_ids'], ['article-new'])

    def test_audio_failure_resumes_saved_response_without_model_regeneration(self):
        original_renderer = self.render
        calls = []
        def render(chapter, language, media, key):
            calls.append(language)
            if calls == ['en', 'nl']:
                raise RuntimeError('Temporary local voice error')
            return original_renderer(chapter, language, media, key)
        with patch.object(news.cloud_client, 'invoke', return_value=self.response()) as invoke, patch.object(news.audio_production, 'render_basic_chapter', side_effect=render):
            self.assertTrue(news.process_one(self.svc))
            self.assertTrue(self.prepared()['curated'])
            self.assertEqual(self.row()['state'], 'waiting_retry')
            self.assertFalse(news.process_one(self.svc))
            self.advance()
            self.assertTrue(news.process_one(self.svc))
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(calls, ['en', 'nl', 'nl', 'de'])
        self.assertEqual(self.row()['state'], 'ready')

    def test_provider_retry_is_bounded_and_keeps_story_unpublished_until_reviewed(self):
        with patch.object(news.cloud_client, 'invoke', side_effect=CloudError('busy', retryable=True)) as invoke:
            for _ in range(3):
                self.assertTrue(news.process_one(self.svc))
                self.advance()
            self.assertFalse(news.process_one(self.svc))
        self.assertEqual(invoke.call_count, 3)
        self.assertFalse(self.prepared()['curated'])
        self.assertEqual(self.row()['state'], 'failed')

    def test_at_most_one_new_story_per_call_and_unrelated_manifest_entries_survive(self):
        second = copy.deepcopy(self.imported)
        second.update({'id': 'item-second'})
        self.catalog['stories'].append(second)
        self.write_catalog()
        sidecar = self.root / 'data' / 'demo-story-audio.json'
        sidecar.write_text(json.dumps({'stories': {'old-story': {'en': {'url': '/media/old.mp3'}}}}))
        with patch.object(news.cloud_client, 'invoke', return_value=self.response()) as invoke:
            self.assertTrue(news.process_one(self.svc))
        self.assertEqual(invoke.call_count, 1)
        catalog = json.loads(self.path.read_text())
        self.assertFalse(next(story for story in catalog['stories'] if story['id'] == 'item-second')['curated'])
        self.assertEqual(json.loads(sidecar.read_text())['stories']['old-story'], {'en': {'url': '/media/old.mp3'}})

    def test_invalid_dynamic_tag_cannot_modify_catalog_taxonomy(self):
        request = news._request(self.svc, self.imported, self.catalog)
        for identifier, parent in [('Bad ID!', 'technology'), ('x' * 65, 'technology'), ('valid-tag', 'not-a-base'), ('technology', 'markets')]:
            response = self.response()
            response['story']['tags'][0].update({'id': identifier, 'parent': parent})
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                news._validate(response, request, self.catalog)

    def test_nearest_twenty_candidates_are_metadata_only_and_use_entities_and_time(self):
        for index in range(30):
            story = copy.deepcopy(self.existing)
            story.update({'id': f'older-{index}', 'title': 'A distant unrelated subject', 'entities': [],
                          'updated_at': '2020-01-01T00:00:00+00:00'})
            self.catalog['stories'].append(story)
        nearby = news._candidates(self.imported, self.catalog)
        self.assertEqual(len(nearby), 20)
        self.assertEqual(nearby[0]['id'], 'story-existing')
        self.assertNotIn('sources', nearby[0])
        self.assertNotIn('claims', nearby[0])


class LocalizedNumberChecks(unittest.TestCase):
    def test_nested_usage_keeps_token_counts_without_credentials_or_prompts(self):
        usage = {'preparation': {'input_tokens': 100, 'output_tokens': 20,
                    'input_tokens_details': {'cached_tokens': 40, 'cache_write_tokens_details': {'ttl_30m_tokens': 10}},
                    'api_key': 'secret', 'prompt': 'private source'},
                 'review': {'output_tokens': 30, 'model': 'gpt-6.1-sol'}, 'access_token': 'secret'}
        checked = news._usage_only(usage)
        self.assertEqual(checked['preparation']['input_tokens_details']['cache_write_tokens_details']['ttl_30m_tokens'], 10)
        self.assertEqual(checked['review']['output_tokens'], 30)
        self.assertNotIn('secret', json.dumps(checked))
        self.assertNotIn('private source', json.dumps(checked))

    def test_dutch_clock_time_is_not_a_new_thousands_value(self):
        self.assertEqual(news._numbers('at 11:20 with 2.4 percent', 'en'), news._numbers('om 11.20 uur met 2,4 procent', 'nl'))
        self.assertNotEqual(news._numbers('11.20 dollars', 'en'), news._numbers('1120 dollars', 'en'))


if __name__ == '__main__':
    unittest.main()
