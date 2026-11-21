import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from . import server
from .article_store import read_article,store_articles


class ArticleStoreTests(unittest.TestCase):
    def test_original_text_languages_and_upsert_remain_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'articles.db'
            german='Eine Meldung über Märkte.\n\nDie nächste Zeile bleibt vollständig.'
            english='A complete report. '+('The following sentence contains all original words. '*50)
            rows=[{'$id':'en','text_content':english,'language':'en'},
                  {'$id':'de','text_content':german,'language':'de'}]
            self.assertEqual(store_articles(rows,database),2)
            for row in rows:
                body=read_article(row['$id'],database)
                self.assertEqual(' '.join(' '.join(body['paragraphs']).split()),' '.join(row['text_content'].split()))
                self.assertEqual(body['language'],row['language'])
            self.assertIsNone(read_article('missing',database))
            store_articles([{'$id':'en','text_content':'Updated complete report.'}],database)
            self.assertEqual(read_article('en',database)['paragraphs'],['Updated complete report.'])
            self.assertEqual(read_article('de',database)['paragraphs'],german.split('\n\n'))

    def test_reader_api_returns_private_original_and_missing_is_404(self):
        with patch.object(server,'read_article',return_value={'article_id':'en','paragraphs':['Complete source text.']}):
            response=server.article('en')
            self.assertEqual(response.headers['cache-control'],'private, no-store')
            self.assertEqual(json.loads(response.body)['paragraphs'],['Complete source text.'])
        with patch.object(server,'read_article',return_value=None):
            with self.assertRaises(HTTPException) as error:server.article('missing')
            self.assertEqual(error.exception.status_code,404)
