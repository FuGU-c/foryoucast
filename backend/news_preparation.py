"""Prepare one imported report with checked source quotes and saved narration.

Only n8n invokes a model. Original articles and source records are immutable.
Related reports stay separate when other articles' complete evidence was not
part of this review, so a new development never replaces older checked facts.
"""
from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from . import audio_production, cloud_client
from .prepare import TOPICS

LANGUAGES = ('en', 'nl', 'de')
MAX_ATTEMPTS = 3


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _usage_only(value, depth=0):
    """Retain token accounting from nested provider responses, never secrets."""
    if not isinstance(value, dict) or depth > 5:
        return {}
    retained = {}
    containers = {'preparation', 'review', 'writing', 'input_tokens_details',
                  'output_tokens_details', 'cache_write_tokens_details'}
    for key, item in value.items():
        if key in containers and isinstance(item, dict):
            retained[key] = _usage_only(item, depth + 1)
        elif re.fullmatch(r'[a-zA-Z0-9_]*(?:tokens|cost|calls|seconds)[a-zA-Z0-9_]*', key) and isinstance(item, (int, float)) and not isinstance(item, bool):
            if item >= 0 and item < float('inf'):
                retained[key] = item
        elif key in ('model', 'provider') and isinstance(item, str) and len(item) <= 100:
            retained[key] = item
    return retained


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, suffix='.pending', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _catalog_path(service):
    return Path(getattr(service, 'CATALOG_PATH', Path(service.ROOT) / 'data' / 'catalog.json'))


def _init(service):
    with service.conn() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS news_preparations(
          story_id TEXT NOT NULL,version TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,
          response TEXT,usage TEXT,error TEXT,attempt INTEGER NOT NULL DEFAULT 0,
          next_run TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
          PRIMARY KEY(story_id,version))''')


def _time(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def _latest(values):
    return max((value for value in values if isinstance(value, str)), key=_time, default=None)


def _tokens(text):
    ignored = {'the', 'and', 'for', 'with', 'from', 'after', 'that', 'this', 'van', 'het', 'een', 'der', 'die', 'das', 'und', 'mit'}
    return set(re.findall(r'[^\W\d_]{3,}', text.casefold())) - ignored


def _candidates(story, catalog):
    headline = ' '.join([story.get('title', ''), *story.get('titles', {}).values(),
                         *(source.get('headline', '') for source in story.get('sources', []))])
    tokens = _tokens(headline)
    entities = {str(value).casefold() for value in story.get('entities', [])}
    moment = _time(story.get('updated_at'))
    def score(other):
        other_tokens = _tokens(' '.join([other.get('title', ''), *other.get('titles', {}).values()]))
        common_entities = entities.intersection(str(value).casefold() for value in other.get('entities', []))
        proximity = 1 / (1 + abs((moment - _time(other.get('updated_at'))).total_seconds()) / 86400)
        return 12 * len(tokens & other_tokens) / max(1, len(tokens | other_tokens)) + 4 * len(common_entities) + proximity
    nearby = sorted((other for other in catalog['stories'] if other['id'] != story['id'] and other.get('curated')),
                    key=lambda other: (-score(other), other['id']))[:20]
    return [{key: copy.deepcopy(item.get(key)) for key in ('id', 'title', 'titles', 'summary', 'tags', 'published_at', 'updated_at')}
            for item in nearby]


def _request(service, story, catalog):
    sources = sorted(story.get('sources', []), key=lambda source: _time(source.get('date')), reverse=True)
    article = None
    chosen = None
    for source in sources:
        candidate = service.read_article(source['article_id'])
        if isinstance(candidate, dict) and isinstance(candidate.get('paragraphs'), list) and any(
                isinstance(paragraph, str) and paragraph.strip() for paragraph in candidate['paragraphs']):
            article, chosen = candidate, source
            break
    if article is None:
        raise ValueError('The imported report has no stored original article paragraphs')
    language = article.get('language') or chosen.get('language')
    if language not in LANGUAGES:
        raise ValueError('The imported report has an unsupported original language')
    return {'article_id': chosen['article_id'], 'language': language,
            'outlet': chosen.get('outlet') or article.get('outlet', ''),
            'title': article.get('title') or chosen.get('headline', ''),
            'paragraphs': [paragraph for paragraph in article['paragraphs'] if isinstance(paragraph, str) and paragraph.strip()],
            'date': chosen.get('date') or article.get('date'), 'existing_stories': _candidates(story, catalog)}


def _numbers(text, language):
    # Dutch/German clock punctuation is not a thousands separator.
    text = re.sub(r'\b([01]?\d|2[0-3])\.([0-5]\d)(?=\s*(?:uur|uhr|gmt|utc|cet)\b)', r'\1:\2', text, flags=re.I)
    values = set()
    for token in re.findall(r'(?<!\w)\d+(?:[.,]\d+)*(?!\w)', text):
        if language in ('de', 'nl'):
            normalized = token.replace('.', '').replace(',', '.')
        else:
            normalized = token.replace(',', '')
        try:
            values.add(Decimal(normalized))
        except InvalidOperation:
            pass
    return values


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\x00' in value:
        raise ValueError(f'{label} must be nonempty bounded text')
    return value.strip()


def _validate(response, request, catalog):
    value = response.get('story') if isinstance(response, dict) else None
    if not isinstance(value, dict):
        raise ValueError('The news workflow did not return a prepared story')
    review = value.get('evidence_review')
    if not isinstance(review, dict) or review.get('passed') is not True:
        raise ValueError('The news story did not pass its evidence review')
    result = {'evidence_review': {'passed': True, 'method': 'n8n-evidence-review'}}
    result['title'] = _text(value.get('title'), 'Prepared title', 300)
    for field, maximum in [('titles', 300), ('summaries', 4000)]:
        if not isinstance(value.get(field), dict):
            raise ValueError(f'The prepared story requires {field} in English, Dutch and German')
        result[field] = {language: _text(value[field].get(language), f'{language} {field}', maximum) for language in LANGUAGES}
    claims = value.get('claims')
    if not isinstance(claims, list) or not 1 <= len(claims) <= 24:
        raise ValueError('The story requires nonempty source-verified claims')
    original = '\n'.join(request['paragraphs'])
    verified = []
    for claim in claims:
        if not isinstance(claim, dict) or claim.get('article_id') != request['article_id']:
            raise ValueError('A news claim refers to an article outside the supplied original evidence')
        quote = _text(claim.get('quote'), 'Source quote', 3000)
        text = _text(claim.get('text'), 'Claim text', 1500)
        if len(quote) < 10 or quote not in original:
            raise ValueError('A news claim quote is not an exact substring of the original article')
        # The second model checks meaning; this independent deterministic check
        # also rejects altered figures even when the quoted passage exists.
        claim_numbers = _numbers(text, request['language']) | _numbers(text, 'en')
        quote_numbers = _numbers(quote, request['language']) | _numbers(quote, 'en')
        if not claim_numbers.issubset(quote_numbers):
            raise ValueError('A news claim introduces a number absent from its exact source quote')
        verified.append({'article_id': request['article_id'], 'quote': quote, 'text': text})
    identifiers = value.get('claim_source_ids')
    if not isinstance(identifiers, list) or identifiers != [request['article_id']]:
        raise ValueError('Summary source IDs must exactly match the independently verified claim sources')
    source_numbers = _numbers(original + ' ' + request['title'], request['language'])
    for language in LANGUAGES:
        combined = result['titles'][language] + ' ' + result['summaries'][language]
        if not _numbers(combined, language).issubset(source_numbers):
            raise ValueError('A translated news summary introduces a figure absent from the original report')
    result['claims'] = verified
    result['claim_source_ids'] = [request['article_id']]
    tags = value.get('tags')
    if not isinstance(tags, list) or not 1 <= len(tags) <= 12:
        raise ValueError('Prepared news requires one to twelve valid topic tags')
    known = {topic['id']: topic for topic in catalog.get('topics', [])}
    checked = []
    for tag in tags:
        if not isinstance(tag, dict):
            raise ValueError('Each prepared news tag must be a topic object')
        identifier, parent = tag.get('id'), tag.get('parent')
        if (not isinstance(identifier, str) or len(identifier) > 64
                or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', identifier)
                or parent not in TOPICS):
            raise ValueError('A prepared news tag has an invalid slug or base parent topic')
        label = _text(tag.get('label'), 'Topic label', 64)
        if identifier in TOPICS and parent != identifier:
            raise ValueError('A base topic cannot be assigned to a different parent')
        if identifier in known and known[identifier].get('parent', parent) != parent:
            raise ValueError('An existing topic cannot be moved to another parent')
        if identifier not in {item['id'] for item in checked}:
            checked.append({'id': identifier, 'label': label, 'parent': parent, 'dynamic': identifier not in TOPICS})
    result['tags'] = checked
    related = value.get('related_story_id')
    relation = value.get('relation', 'new')
    candidates = {item['id'] for item in request['existing_stories']}
    if relation not in ('new', 'same-event', 'translation'):
        raise ValueError('The prepared news relationship is invalid')
    if relation != 'new' and related in candidates:
        result['related_story_id'] = related
        result['relation'] = relation
    else:
        result.pop('related_story_id', None)
        result['relation'] = 'new'
    return result


def _save(service, item, state, *, error=None, next_run=None):
    with service.conn() as db:
        db.execute('UPDATE news_preparations SET state=?,payload=?,response=?,usage=?,error=?,attempt=?,next_run=?,updated_at=? WHERE story_id=? AND version=?',
                   (state, _json(item['payload']), _json(item['response']) if item.get('response') else None,
                    _json(item['usage']) if item.get('usage') is not None else None, error,
                    item['attempt'], next_run or service.now(), service.now(), item['story_id'], item['version']))


def _source_signature(story):
    return _hash({'sources': story.get('sources', []), 'published_at': story.get('published_at')})


def _publish(service, item):
    # Serialize preparation publishers across worker processes while the atomic
    # file replacement runs; model and voice calls never hold this DB lock.
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        _apply_catalog(service, item)


def _apply_catalog(service, item):
    path = _catalog_path(service)
    # Re-read the current catalog so unrelated imports/edits are retained.
    catalog = json.loads(path.read_text(encoding='utf-8'))
    story = next((story for story in catalog['stories'] if story['id'] == item['story_id']), None)
    if not story:
        raise ValueError('The imported story was removed before publication')
    if _source_signature(story) != item['payload']['source_signature']:
        raise ValueError('The original source metadata changed during preparation; prepare the new source version')
    prepared = item['response']
    request = item['payload']['request']
    source_ids = list(prepared['claim_source_ids'])
    # Keep source.headline/source.language untouched. The editorial translations
    # occupy their own fields, with explicit source and translation provenance.
    story.update({'title': prepared['title'], 'titles': copy.deepcopy(prepared['titles']),
                  'summary': prepared['summaries']['en'], 'summaries': copy.deepcopy(prepared['summaries']),
                  'claim_source_ids': source_ids, 'claims': copy.deepcopy(prepared['claims']),
                  'evidence_review': copy.deepcopy(prepared['evidence_review']),
                  'summary_source_ids': {language: source_ids[:] for language in LANGUAGES},
                  'translation_provenance': {language: {'source_language': request['language'],
                      'translated_by_ai': language != request['language'], 'source_ids': source_ids[:]}
                      for language in LANGUAGES}, 'curated': True, 'fresh_import': True,
                  'prepared_at': service.now(), 'prepared_by': 'n8n-source-checked',
                  'freshness': {'prepared_at': service.now(), 'source_updated_at': _latest(source.get('date') for source in story['sources'])}})
    story['original_titles'] = {source['article_id']: {'title': source.get('headline', ''), 'language': source.get('language')}
                                for source in story['sources']}
    topics = {topic['id']: topic for topic in catalog.get('topics', [])}
    tags = list(story.get('tags', []))
    for tag in prepared['tags']:
        if tag['id'] not in topics:
            topics[tag['id']] = copy.deepcopy(tag)
        tags.extend([tag['parent'], tag['id']])
    story['tags'] = list(dict.fromkeys(tags))
    story['primary_topic'] = prepared['tags'][0]['parent']
    if prepared.get('related_story_id'):
        story.update({'related_story_id': prepared['related_story_id'], 'relation': prepared['relation'],
                      'related_story_ids': [prepared['related_story_id']],
                      'merge_policy': 'separate-reviewed-coverage'})
    else:
        story['relation'] = 'new'
    story['updated_at'] = _latest([story.get('updated_at'), *(source.get('date') for source in story['sources'])])
    catalog['as_of'] = _latest([catalog.get('as_of'), story.get('updated_at')])
    catalog['topics'] = list(topics.values())
    catalog.setdefault('stats', {})['stories'] = len(catalog['stories'])
    catalog['stats']['articles'] = len({source['article_id'] for record in catalog['stories'] for source in record.get('sources', [])})
    catalog['version'] = _hash({key: value for key, value in catalog.items() if key != 'version'})
    _atomic_json(path, catalog)
    item['payload']['published_version'] = catalog['version']
    item['payload']['published_story'] = copy.deepcopy(story)
    service.refresh_catalog()


def _audio(service, item):
    story = item['payload']['published_story']
    request = item['payload']['request']
    recorded = item['payload'].setdefault('audio', {})
    media = Path(service.ROOT) / 'media'
    for language in LANGUAGES:
        if language in recorded:
            try:
                audio_production._media_file(recorded[language]['url'], media.resolve())
                continue
            except (OSError, ValueError):
                pass
        introduction = {'en': f'According to {request["outlet"]}, here is the story.',
                        'nl': f'Volgens {request["outlet"]} is dit het verhaal.',
                        'de': f'Laut {request["outlet"]} ist dies die aktuelle Meldung.'}[language]
        chapter = {'story_id': story['id'], 'claim_source_ids': list(story['claim_source_ids']),
                   'sources': copy.deepcopy(story['sources']), 'turns': [{'speaker': 'maya',
                       'text': introduction + ' ' + story['summaries'][language],
                       'source_ids': list(story['claim_source_ids'])}]}
        key = _hash({'news_version': item['version'], 'language': language, 'turns': chapter['turns']})
        result = audio_production.render_basic_chapter(chapter, language, media, key)
        recorded[language] = {key: result[key] for key in ('url', 'duration_seconds', 'provider', 'voice_ids') if key in result}
        recorded[language].update({'language': language, 'source_ids': list(story['claim_source_ids']),
                                   'script_origin': 'n8n-source-checked'})
        _save(service, item, 'audio')
    sidecar = Path(service.ROOT) / 'data' / 'demo-story-audio.json'
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            manifest = json.loads(sidecar.read_text(encoding='utf-8'))
        except FileNotFoundError:
            manifest = {'stories': {}}
        manifest.setdefault('stories', {})[story['id']] = copy.deepcopy(recorded)
        _atomic_json(sidecar, manifest)


def process_one(service):
    """Prepare at most one story; resume its saved local audio without new AI."""
    if not cloud_client.connection(service.ROOT).get('ai_ready'):
        return False
    _init(service)
    service.refresh_catalog()
    path = _catalog_path(service)
    catalog = json.loads(path.read_text(encoding='utf-8'))
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        # A stale lease can only repeat a source-analysis request, never a paid
        # voice take. All narration here uses installed Microsoft voices.
        stale = (dt.datetime.fromisoformat(service.now()) - dt.timedelta(minutes=10)).isoformat()
        db.execute("UPDATE news_preparations SET state='waiting_retry',next_run=? WHERE state='running' AND updated_at<?", (service.now(), stale))
        row = db.execute("SELECT * FROM news_preparations WHERE state IN ('audio','waiting_retry') AND next_run<=? ORDER BY created_at LIMIT 1", (service.now(),)).fetchone()
        if row:
            item = dict(row)
            item['payload'] = json.loads(item['payload'])
            item['response'] = json.loads(item['response']) if item['response'] else None
            item['usage'] = json.loads(item['usage']) if item['usage'] else None
        else:
            item = None
            for story in catalog['stories']:
                if story.get('curated') or not story.get('fresh_import'):
                    continue
                try:
                    request = _request(service, story, catalog)
                    version = _hash({'sources': story['sources'], 'request': {key: value for key, value in request.items() if key != 'existing_stories'}})
                except ValueError:
                    continue
                if db.execute('SELECT 1 FROM news_preparations WHERE story_id=? AND version=?', (story['id'], version)).fetchone():
                    continue
                item = {'story_id': story['id'], 'version': version, 'state': 'running',
                        'payload': {'request': request, 'source_signature': _source_signature(story)},
                        'response': None, 'usage': None, 'attempt': 0}
                db.execute('INSERT INTO news_preparations VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (story['id'], version, 'running', _json(item['payload']), None, None, None,
                            0, service.now(), service.now(), service.now()))
                break
        if item is None:
            return False
        item['attempt'] += 1
        db.execute("UPDATE news_preparations SET state='running',attempt=?,updated_at=? WHERE story_id=? AND version=?",
                   (item['attempt'], service.now(), item['story_id'], item['version']))
    try:
        if item['response'] is None:
            response = cloud_client.invoke('news', item['payload']['request'], root=service.ROOT,
                request_id='news-' + item['story_id'] + '-' + item['version'][:16], timeout=120)
            item['response'] = _validate(response, item['payload']['request'], catalog)
            # Only retain aggregate usage, never arbitrary provider response data.
            usage = response.get('usage')
            if isinstance(usage, dict):
                item['usage'] = _usage_only(usage)
            _save(service, item, 'audio')
        if not item['payload'].get('published_story'):
            _publish(service, item)
            _save(service, item, 'audio')
        _audio(service, item)
        _save(service, item, 'ready')
    except Exception as exc:
        retryable = isinstance(exc, cloud_client.CloudError) and exc.retryable
        # Local narration failures can resume their saved response/partial audio.
        retryable = retryable or bool(item['payload'].get('published_story'))
        retry = retryable and item['attempt'] < MAX_ATTEMPTS
        delay = min(180, max(10, getattr(exc, 'retry_after', 30)))
        _save(service, item, 'waiting_retry' if retry else 'failed', error=str(exc)[:500],
              next_run=(dt.datetime.fromisoformat(service.now()) + dt.timedelta(seconds=delay)).isoformat())
    return True
