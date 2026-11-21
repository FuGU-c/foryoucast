"""Meaningful scheduler tests using an isolated database, no API calls."""
import contextlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import worker


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name)/'test.db'
        with self.connection() as db:
            db.executescript('CREATE TABLE deliveries(profile_id TEXT,day TEXT,job_id TEXT,PRIMARY KEY(profile_id,day)); CREATE TABLE jobs(id TEXT PRIMARY KEY,profile_id TEXT,state TEXT,payload TEXT,result TEXT,error TEXT,created_at TEXT,updated_at TEXT);')
        self.patches = [
            patch.object(worker, 'conn', self.connection),
            patch.object(worker, 'due_profiles', return_value=[{'profile_id':'mila','day':'2026-11-20'}]),
            patch.object(worker, 'compose', return_value={'id':'edition-test','audio_mode':'browser-preview'}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.db)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def test_daily_reservation_prevents_duplicate_jobs(self):
        self.assertEqual(worker.enqueue_due(), 1)
        self.assertEqual(worker.enqueue_due(), 0)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 1)

    def test_job_finishes_as_script_only(self):
        worker.enqueue_due()
        self.assertTrue(worker.process_one())
        self.assertFalse(worker.process_one())
        with self.connection() as db:
            row = db.execute('SELECT * FROM jobs').fetchone()
            self.assertEqual(row['state'], 'local_ready')
            self.assertEqual(json.loads(row['result'])['audio_mode'], 'browser-preview')

    def test_three_failures_are_visible_not_looped_forever(self):
        worker.enqueue_due()
        with patch.object(worker, 'compose', side_effect=RuntimeError('test failure')):
            for _ in range(3):
                self.assertTrue(worker.process_one())
            self.assertFalse(worker.process_one())
        with self.connection() as db:
            row = db.execute('SELECT * FROM jobs').fetchone()
            self.assertEqual(row['state'], 'failed')
            self.assertEqual(json.loads(row['payload'])['attempt'], 3)
            self.assertIn('test failure', row['error'])

    def test_interrupted_work_is_requeued(self):
        worker.enqueue_due()
        with self.connection() as db:
            db.execute("UPDATE jobs SET state='running'")
        worker.recover_interrupted()
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT state FROM jobs').fetchone()[0], 'queued')


if __name__ == '__main__':
    unittest.main()
