"""Add licensed articles to the local catalog without replacing existing preferences or coverage."""
import argparse
import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .news_topics import story_topics
from .prepare import ROOT, digest, tags_for
from .article_store import store_articles

CATALOG_PATH = ROOT / 'data' / 'catalog.json'
INCOMING = ROOT / 'data' / 'incoming'


def append_batch(path, catalog_path=CATALOG_PATH):
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    topics={topic['id']:topic for topic in catalog['topics']}
    source_ids={src['article_id'] for story in catalog['stories'] for src in story['sources']}
    count=0
    raw=Path(path).read_text(encoding='utf-8-sig')
    rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    for row in rows:
        identifier=row.get('$id') or row.get('article_id')
        headline=row.get('headline')
        language=row.get('language')
        url=row.get('permalink')
        if not all(isinstance(value,str) and value for value in (identifier,headline,language,url)):
            continue
        if identifier in source_ids or language not in ('en','de','nl'):
            if identifier in source_ids:store_articles([row])
            continue
        if urlsplit(url).scheme not in ('http','https') or not urlsplit(url).hostname:
            continue
        try:
            timestamp=dt.datetime.fromisoformat(row['date'])
            if timestamp.tzinfo is None:raise ValueError
            timestamp=timestamp.astimezone(dt.timezone.utc).isoformat()
        except (TypeError,ValueError,KeyError):
            continue
        outlet=str((row.get('publication') or {}).get('name') or row.get('publisher_name') or urlsplit(url).hostname)[:100]
        headline=headline.strip()[:300]
        baseline=tags_for({'headline':headline})
        sections=row.get('provider_categories') if isinstance(row.get('provider_categories'),list) else []
        ticker_tags=story_topics(headline,row.get('company_tickers') if isinstance(row.get('company_tickers'),list) else [],sections,parent=baseline[0])
        for tag in ticker_tags:topics[tag['id']]=tag
        tags=list(dict.fromkeys(baseline+[tag['parent'] for tag in ticker_tags]+[tag['id'] for tag in ticker_tags]))
        translation_group=row.get('translation_group_id')
        publisher=urlsplit(url).hostname.removeprefix('www.').lower()
        translation_key='translation-'+digest(publisher+'|'+str(translation_group)) if translation_group else identifier
        excerpt=row.get('excerpt') or ''
        snippet=' '.join(excerpt.split()[:20]).rstrip('…') if isinstance(excerpt,str) else ''
        thumb=row.get('thumb_url') or ''
        source={'article_id':identifier,'headline':headline,'language':language,'url':url,'date':timestamp,'outlet':outlet,'tags':tags,'snippet':snippet,'translation_key':translation_key,
                'image_url':thumb if isinstance(thumb,str) and thumb.startswith('https://') else ''}
        event=row.get('event_id')
        event_key='event-'+digest(event) if isinstance(event,str) and event else None
        match=next((story for story in catalog['stories'] if
                    (event_key and story.get('event_key')==event_key) or
                    any(src.get('translation_key')==translation_key or
                        (src.get('headline','').casefold()==headline.casefold() and src['date'][:10]==timestamp[:10])
                        for src in story['sources'])),None)
        if match:
            match['sources'].append(source)
            match['tags']=list(dict.fromkeys(match['tags']+tags))
            match['titles'].setdefault(language,headline)
            match['updated_at']=max(match['updated_at'],timestamp)
        else:
            catalog['stories'].append({
                'id':'item-'+digest(identifier),'event_key':event_key,'title':headline,'titles':{language:headline},
                'summary':'Open the source to read this report.','summaries':{},'tags':tags,'sources':[source],
                'claim_source_ids':[],'published_at':timestamp,'updated_at':timestamp,'curated':False,
                'fresh_import':True,'art':'sage','entities':[tag['label'] for tag in ticker_tags],'kind':'new',
            })
        source_ids.add(identifier)
        store_articles([row])
        catalog['as_of']=max(catalog['as_of'],timestamp)
        count+=1
    if not count:return 0
    catalog['topics']=list(topics.values())
    catalog['stats']['articles']=len(source_ids)
    catalog['stats']['stories']=len(catalog['stories'])
    catalog['version']=digest(catalog['version']+'|'+digest(raw))
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=catalog_path.parent,suffix='.pending',delete=False) as temp:
        json.dump(catalog,temp,ensure_ascii=False)
        staged=Path(temp.name)
    try:os.replace(staged,catalog_path)
    finally:staged.unlink(missing_ok=True)
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feed',type=Path)
    args=parser.parse_args()
    print(f'Added {append_batch(args.feed)} articles.')


if __name__=='__main__':
    main()
