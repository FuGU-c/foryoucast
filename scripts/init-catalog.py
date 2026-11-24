"""Create a starter data/catalog.json so the app can boot with your own news data.

Run:  python scripts/init-catalog.py
Then: python -m backend.import_news docs/news-intake.example.jsonl
See docs/news-intake.md for the article format.
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.prepare import tags_for
from backend.news_topics import story_topics

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data' / 'catalog.json'

if CATALOG.exists():
    print(f'{CATALOG} already exists — nothing to do.')
    sys.exit(0)

now = datetime.now(timezone.utc).isoformat()
catalog = {
    'version': 'starter-1',
    'as_of': now,
    'replay_day': now[:10],
    'topics': [
        {'id': 'world', 'label': 'World'},
        {'id': 'section-technology', 'label': 'Technology'},
        {'id': 'section-business', 'label': 'Business'},
        {'id': 'section-general', 'label': 'General news'},
    ],
    'stats': {'articles': 0, 'feeds': 0, 'stories': 0, 'curated': 0,
              'translation_links': 0, 'recent_articles': 0,
              'feed_counts': {}, 'date_counts': {}},
    'stories': [],
}
CATALOG.parent.mkdir(exist_ok=True)
CATALOG.write_text(json.dumps(catalog, indent=1), encoding='utf-8')
print(f'Wrote starter catalog: {CATALOG}')
print('Next: python -m backend.import_news <your-articles.jsonl>')
