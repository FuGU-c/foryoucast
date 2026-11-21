"""Durable local scheduler for demo scripts. No paid API calls are made.

Keep this process running beside the API server. An atomic daily reservation
prevents duplicate scheduled editions, and queued work survives restarts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import signal
import time
import uuid

from .server import compose, conn, due_profiles, now
from .import_news import INCOMING, append_batch
from . import server as service, cloud_jobs

stopping = False


def stop(*_):
    global stopping
    stopping = True


def enqueue_due():
    queued = 0
    for listener in due_profiles():
        job_id = 'job-' + uuid.uuid4().hex[:12]
        timestamp = now()
        payload = {**listener, 'kind': 'local-script', 'attempt': 0}
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            inserted = db.execute(
                'INSERT OR IGNORE INTO deliveries VALUES (?,?,?)',
                (listener['profile_id'], listener['day'], job_id),
            ).rowcount
            if not inserted:
                continue
            db.execute(
                'INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)',
                (job_id, listener['profile_id'], 'queued', json.dumps(payload), None, None, timestamp, timestamp),
            )
            queued += 1
    return queued


def recover_interrupted():
    # A prior process may have stopped after reserving a job. Re-running script
    # composition costs no credits; it does not initiate ElevenLabs generation.
    with conn() as db:
        db.execute("UPDATE jobs SET state='queued',updated_at=? WHERE state='running'", (now(),))


def process_one():
    with conn() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
        if not row:
            return False
        job = dict(row)
        db.execute("UPDATE jobs SET state='running',updated_at=? WHERE id=?", (now(), job['id']))
    payload = json.loads(job['payload'])
    try:
        edition = compose(job['profile_id'])
        result = {'edition_id': edition['id'], 'audio_mode': edition['audio_mode'], 'note': 'Script ready; browser voice preview. Paid narration is not connected.'}
        with conn() as db:
            db.execute("UPDATE jobs SET state='local_ready',result=?,error=NULL,updated_at=? WHERE id=?", (json.dumps(result), now(), job['id']))
        print(f"[{now()}] Prepared {edition['id']} for {job['profile_id']} (script only)", flush=True)
    except Exception as exc:
        payload['attempt'] = payload.get('attempt', 0) + 1
        state = 'failed' if payload['attempt'] >= 3 else 'queued'
        with conn() as db:
            db.execute('UPDATE jobs SET state=?,payload=?,error=?,updated_at=? WHERE id=?', (state, json.dumps(payload), str(exc)[:500], now(), job['id']))
        print(f"[{now()}] {job['id']} {state}: {exc}", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Run one scheduling pass and drain queued jobs.')
    parser.add_argument('--interval', type=int, default=2)
    args = parser.parse_args()
    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, stop)
    recover_interrupted()
    cloud_jobs.recover(service)
    if service.cloud_client.connection(service.ROOT).get('verified_at'):
        for listener in service.profiles():
            if listener['onboarded']:cloud_jobs.enqueue_radar(service,listener['id'])
    INCOMING.mkdir(exist_ok=True)
    seen={}
    print('Seranews worker: recorded audio, signed n8n jobs and 30-minute scheduling.', flush=True)
    while not stopping:
        for file in sorted(INCOMING.glob('*.jsonl')):
            try:
                revision=file.stat().st_mtime_ns
                if seen.get(file)==revision:continue
                imported=append_batch(file)
                seen[file]=revision
                if imported:
                    service.refresh_catalog()
                    for listener in service.profiles():cloud_jobs.enqueue_radar(service,listener['id'])
                    print(f"[{now()}] Imported {imported} articles from {file.name}.",flush=True)
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                print(f"[{now()}] Waiting for a complete feed file {file.name}: {exc}",flush=True)
        for listener in due_profiles():
            try:
                job=cloud_jobs.queue_briefing(service,listener['profile_id'])
                with conn() as db:db.execute('INSERT OR IGNORE INTO deliveries VALUES (?,?,?)',(listener['profile_id'],listener['day'],job['job_id']))
            except Exception as exc:
                print(f"[{now()}] Scheduled briefing held: {str(exc)[:180]}",flush=True)
        cloud_jobs.process_outbox(service)
        if not stopping:cloud_jobs.process_one(service)
        try:
            from . import news_preparation
            before=service.CATALOG.get('version')
            if not stopping:news_preparation.process_one(service)
            if before!=service.CATALOG.get('version'):
                for listener in service.profiles():
                    if listener['onboarded']:cloud_jobs.enqueue_radar(service,listener['id'])
        except ImportError:
            pass
        except Exception as exc:
            print(f"[{now()}] News preparation held: {str(exc)[:180]}",flush=True)
        if args.once:
            break
        # Short interruptible sleeps keep shutdown responsive.
        for _ in range(max(1, args.interval)):
            if stopping:
                break
            time.sleep(1)


if __name__ == '__main__':
    main()
