"""Private local storage for the original articles supplied to the demo."""
import json
import re
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

ARTICLE_DB=Path(__file__).resolve().parents[1]/'data'/'articles.db'


def store_articles(rows, database=ARTICLE_DB):
    database=Path(database)
    database.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(database,timeout=20)) as connection, connection:
        connection.execute('CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        count=0
        for row in rows:
            identifier=row.get('$id') or row.get('article_id')
            text=row.get('text_content')
            if not isinstance(identifier,str) or not isinstance(text,str) or not text.strip():
                continue
            text=text.strip()
            parts=[part.strip() for part in re.split(r'\n\s*\n|\n',text) if part.strip()]
            paragraphs=[]
            for part in parts:
                if len(part)<1000:
                    paragraphs.append(part)
                    continue
                sentences=re.split(r'(?<=[.!?])\s+(?=[A-ZÄÖÜÀ-Ý0-9“‘"\'])',part)
                buffer=''
                for sentence in sentences:
                    if buffer and len(buffer)+len(sentence)>750:
                        paragraphs.append(buffer)
                        buffer=''
                    buffer=(buffer+' '+sentence).strip()
                if buffer:paragraphs.append(buffer)
            data={
                'article_id':identifier,'title':row.get('headline',''),'language':row.get('language','en'),
                'outlet':(row.get('publication') or {}).get('name') or row.get('publisher_name',''),
                'url':row.get('permalink',''),'date':row.get('date',''),'paragraphs':paragraphs,
                'word_count':len(text.split()),
            }
            connection.execute('INSERT INTO articles VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                               (identifier,json.dumps(data,ensure_ascii=False)))
            count+=1
    return count


def read_article(identifier, database=ARTICLE_DB):
    if not Path(database).is_file():return None
    with closing(sqlite3.connect(database,timeout=20)) as connection:
        row=connection.execute('SELECT data FROM articles WHERE id=?',(identifier,)).fetchone()
    return json.loads(row[0]) if row else None


def import_zip(path, database=ARTICLE_DB):
    def records():
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith('.jsonl'):
                    for line in archive.read(name).decode('utf-8-sig').splitlines():
                        if line.strip():yield json.loads(line)
    return store_articles(records(),database)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip',type=Path)
    args=parser.parse_args()
    print(f'Original articles stored locally: {import_zip(args.zip)}')
