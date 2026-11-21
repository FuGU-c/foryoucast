"""Offline, deterministic preparation for the licensed hackathon dataset.

All records receive tags. Native-language editions are linked by author/time;
English event clusters use conservative headline token overlap. The demo's
editorial cards are human-authored paraphrases, not copied article bodies.
"""
from __future__ import annotations
import argparse, collections, datetime as dt, hashlib, json, re, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = {
 'markets': ('Business & investing', r'stock|share|earnings|etf|mutual fund|invest|nasdaq|s&p|equity|portfolio|aandelen|aktien|fonds'),
 'economy': ('Economy & policy', r'central bank|inflation|interest rate|fed\b|ecb\b|boj\b|rba\b|rbnz\b|retail sales|ppi\b|gdp\b|industrial production|trade deficit|yield|econom'),
 'technology': ('Technology & AI', r'\bai\b|artificial intelligence|nvidia|chip|semiconductor|microsoft|anthropic|software|cyber|iphone|technology|technologie|intel|internet|tech\b'),
 'crypto': ('Crypto', r'bitcoin|crypto|ethereum|solana|\bxrp\b|defi|blockchain'),
 'world': ('World & politics', r'trump|president|politic|ukraine|russia|zelensky|government|congress|election|world|china|iran|national security|diploma'),
 'money': ('Money & everyday life', r'personal finance|savings|scam|mortgage|household|banking|consumer|pension|credit card|bank outage'),
 'culture': ('Culture & sport', r'royal|markle|middleton|prince|celebrity|entertainment|film|movie|actor|actress|sport|football|pattinson|james bond|watts|prison|crime|murder'),
 'energy': ('Energy & commodities', r'\boil\b|brent|crude|gold|silver|commodit|energy|uranium|metal'),
 'forex': ('Currencies', r'forex|\baud\b|\bjpy\b|\bnzd\b|\busd\b|yen|dollar|currency|currencies|exchange rate'),
}
STOP = set('the a an as on at of to in for and with is are by from why how what after before its it this that stock shares stocks says over amid more new'.split())
DETAILS = {
 'earnings': ('Company earnings','markets',r'earnings|quarterly results|profit forecast|kwartaalcijfers|quartalszahlen'),
 'funds': ('ETFs & funds','markets',r'\betf\b|mutual fund|index fund'),
 'deals': ('IPOs & deals','markets',r'\bipo\b|merger|acquisition|beursgang|börsengang'),
 'rates': ('Central banks & rates','economy',r'central bank|interest rate|rate hik|fed\b|ecb\b|boj\b'),
 'inflation': ('Inflation & jobs','economy',r'inflation|producer prices|employment|payroll|\bppi\b'),
 'trade': ('Trade & tariffs','economy',r'tariff|trade deficit|trade surplus|exports|imports'),
 'chips': ('Chips & semiconductors','technology',r'nvidia|intel|semiconductor|chipmaker|\bchips?\b'),
 'ai': ('AI & software','technology',r'\bai\b|artificial intelligence|anthropic|software'),
 'outages': ('Outages & cybersecurity','technology',r'outage|cybersecurity|service disruption|data breach'),
 'bitcoin': ('Bitcoin & other coins','crypto',r'bitcoin|ethereum|solana|\bxrp\b'),
 'diplomacy': ('Diplomacy & conflict','world',r'ukraine|diploma|ceasefire|sanctions|international relations'),
 'elections': ('Elections & government','world',r'election|parliament|congress|government'),
 'consumer': ('Consumers & scams','money',r'consumer|scam|savings|credit card|retail sales'),
 'banking': ('Banking & borrowing','money',r'banking|mortgage|loan|bank outage'),
 'film': ('Film & entertainment','culture',r'film|actor|actress|celebrity|entertainment'),
 'sports': ('Sports','culture',r'sport|football|tennis'),
 'oil': ('Oil & energy','energy',r'\boil\b|brent|crude|gas prices|energy'),
 'metals': ('Gold & metals','energy',r'gold|silver|uranium|metal'),
 'fx-pairs': ('FX pairs','forex',r'forex|\baud\b|\bjpy\b|\bnzd\b|\busd\b|\beur\b|yen|exchange rate'),
}
TOPIC_LABELS = {key: value[0] for key,value in (TOPICS | DETAILS).items()}

def tags_for(a):
 text = ' '.join([a.get('headline',''), ' '.join(a.get('provider_categories') or []), a.get('excerpt','')[:600]]).lower()
 tags = [k for k, (_, pat) in TOPICS.items() if re.search(pat,text)]
 detail_tags = [key for key,(_,parent,pattern) in DETAILS.items() if re.search(pattern,text)]
 return list(dict.fromkeys((tags or ([] if detail_tags else ['world']))+[DETAILS[key][1] for key in detail_tags]+detail_tags))

def tokens(s):
 return set(re.findall(r'[a-z0-9]{3,}',s.lower()))-STOP

def digest(s): return hashlib.sha256(s.encode()).hexdigest()[:16]

# Each tuple: English title, Dutch title, German title, matching headline regex,
# and an original source-grounded summary in each language.
CARDS = [
 ('The AI earnings story everyone is watching','De AI-cijfers waar iedereen naar kijkt','Die KI-Zahlen im Fokus',r'nvidia.*(earnings|forecast)|nasdaq rises as nvidia',
  'The latest Invezz coverage follows Nvidia earnings and the reaction across technology shares. The report distinguishes the company outlook from investor expectations. This is a developing market story; a strong forecast and a share-price reaction describe different things.',
  'De nieuwste berichtgeving van Invezz volgt de cijfers van Nvidia en de reactie bij technologieaandelen. Het artikel maakt onderscheid tussen de vooruitzichten van het bedrijf en de verwachtingen van beleggers. Dit verhaal ontwikkelt zich nog; een prognose is geen garantie.',
  'Die aktuelle Invezz-Berichterstattung behandelt Nvidias Zahlen und die Reaktion der Technologieaktien. Der Bericht unterscheidet zwischen dem Ausblick des Unternehmens und den Erwartungen der Anleger. Die Geschichte entwickelt sich weiter; eine Prognose ist keine Zusage.'),
 ('A new chapter for Nvidia leadership','Een nieuw hoofdstuk voor Nvidia','Ein neues Kapitel für Nvidia',r'nvidia.*(huang|leadership|exit)|huang.*nvidia',
  'Reports in the supplied dataset describe a leadership transition at Nvidia and the responses around it. Some details are attributed to reports and unnamed sources. Those accounts should remain attributed, rather than being presented as independently established facts.',
  'Berichten in de dataset beschrijven een leiderschapswissel bij Nvidia en de reacties daarop. Sommige details komen uit andere berichten en van anonieme bronnen. Die informatie blijft toegeschreven aan de berichtgeving en wordt niet als onafhankelijk bevestigd gepresenteerd.',
  'Berichte im Datensatz beschreiben einen Führungswechsel bei Nvidia und die Reaktionen darauf. Einige Einzelheiten stammen aus anderen Berichten und von ungenannten Quellen. Diese Angaben bleiben ausdrücklich den jeweiligen Berichten zugeschrieben.'),
 ('The dollar and the next Fed decision','De dollar en het volgende Fed-besluit','Der Dollar und die nächste Fed-Entscheidung',r'dollar.*(retail sales|firms)|fed.*musalem|fed.*rate hikes',
  'ActionForex reports on the dollar as investors assess economic releases and the path of US interest rates. Comments from Federal Reserve officials describe their policy views, not an announced decision. The distinction matters when interpreting currency-market expectations.',
  'ActionForex volgt de dollar terwijl beleggers economische cijfers en de Amerikaanse rente beoordelen. Uitspraken van Fed-bestuurders geven hun beleidsopvattingen weer en zijn geen aangekondigd rentebesluit. Dat onderscheid is belangrijk voor de valutamarkt.',
  'ActionForex berichtet über den Dollar, Konjunkturdaten und den erwarteten US-Zinspfad. Aussagen einzelner Fed-Mitglieder geben deren Position wieder und sind kein beschlossener Zinsschritt. Für die Einordnung am Devisenmarkt ist dieser Unterschied wichtig.'),
 ('Japan signals more rate increases','Japan wijst op verdere renteverhogingen','Japan signalisiert weitere Zinsschritte',r'boj.*(ueda|takata)|yen leads',
  'ActionForex reports that Bank of Japan officials support further interest-rate increases. Its coverage connects the policy discussion with inflation, the yen and bond yields. The officials’ comments signal a direction of travel; the timing of future decisions remains separate.',
  'ActionForex meldt dat bestuurders van de Bank of Japan verdere renteverhogingen steunen. De berichtgeving verbindt die discussie met inflatie, de yen en obligatierentes. Hun uitspraken wijzen op een beleidsrichting, zonder de timing van toekomstige besluiten vast te leggen.',
  'Laut ActionForex unterstützen Vertreter der Bank of Japan weitere Zinserhöhungen. Die Berichterstattung verbindet dies mit Inflation, Yen und Anleiherenditen. Die Äußerungen zeigen eine Richtung, legen aber den Zeitpunkt künftiger Entscheidungen nicht fest.'),
 ('US shoppers slow down, with a twist','Amerikaanse consument doet het rustiger aan','US-Konsum verliert an Tempo',r'us retail sales slow',
  'ActionForex reports slower monthly growth in US retail sales, with stronger spending when automobiles are excluded. That means the headline and underlying measures tell different parts of the story. A single monthly release should not be treated as proof of a broader trend.',
  'ActionForex meldt een lagere maandelijkse groei van de Amerikaanse detailhandelsverkopen. Zonder autoverkopen was de ontwikkeling sterker. Het totaalcijfer en de onderliggende cijfers vertellen dus verschillende delen van het verhaal; één maand bewijst nog geen trend.',
  'ActionForex meldet ein langsameres monatliches Wachstum der US-Einzelhandelsumsätze. Ohne Autoverkäufe fiel die Entwicklung stärker aus. Gesamtzahl und Teilbereiche erzählen verschiedene Teile der Geschichte; ein einzelner Monat belegt noch keinen Trend.'),
 ('Oil faces a changing supply picture','Olie krijgt te maken met ruimer aanbod','Das Ölangebot verändert sich',r'brent crude price analysis',
  'Invezz reports falling oil prices alongside recovering supplies and concerns about demand. The article cites an International Energy Agency forecast for supply to exceed demand. That supply estimate is a forecast, while the reported price moves describe a specific trading session.',
  'Invezz beschrijft dalende olieprijzen bij herstellend aanbod en zorgen over de vraag. Het artikel verwijst naar een IEA-raming waarin het aanbod groter is dan de vraag. Die raming is een prognose; de koersbeweging betreft een specifieke handelsdag.',
  'Invezz berichtet über fallende Ölpreise, ein höheres Angebot und Nachfragesorgen. Der Artikel verweist auf eine IEA-Prognose für ein Überangebot. Diese Schätzung ist eine Prognose; die beschriebenen Kursbewegungen beziehen sich auf einen bestimmten Handelstag.'),
 ('Bitcoin: price pressure, not a prediction','Bitcoin: koersdruk is geen voorspelling','Bitcoin: Kursdruck ist keine Prognose',r"bitcoin.*(bottom|62000|62,000)",
  'Invezz reports continued pressure on Bitcoin and withdrawals from US spot Bitcoin funds. The article also includes differing analyst views about a possible bottom. Those opinions do not establish where the price will go next.',
  'Invezz beschrijft aanhoudende druk op Bitcoin en uitstroom uit Amerikaanse Bitcoinfondsen. Het artikel bevat ook verschillende analistenmeningen over een mogelijke bodem. Die meningen stellen niet vast waar de koers vervolgens heen gaat.',
  'Invezz beschreibt anhaltenden Druck auf Bitcoin und Abflüsse aus US-Bitcoinfonds. Der Artikel enthält unterschiedliche Analystenmeinungen zu einem möglichen Tiefpunkt. Daraus lässt sich der weitere Kursverlauf nicht sicher ableiten.'),
 ('Gold meets the interest-rate question','Goud en de rentevraag','Gold und die Zinsfrage',r'gold gains slightly',
  'Invezz reports a modest recovery in gold after a recent low. Its report connects the limited rebound with expectations of higher US interest rates. Market-implied probabilities are estimates of expectations, rather than promises about the next policy decision.',
  'Invezz meldt een bescheiden herstel van goud na een recent dieptepunt. Het artikel verbindt het beperkte herstel met verwachtingen van een hogere Amerikaanse rente. Marktverwachtingen zijn geen belofte over het volgende beleidsbesluit.',
  'Invezz meldet eine leichte Erholung des Goldpreises nach einem jüngsten Tief. Der Bericht stellt einen Zusammenhang mit höheren US-Zinserwartungen her. Markterwartungen sind keine Zusage über die nächste geldpolitische Entscheidung.'),
 ('Home Depot: results and a leadership handover','Home Depot: cijfers en een bestuurswissel','Home Depot: Zahlen und Führungswechsel',r'home depot beats earnings',
  'Invezz reports that Home Depot exceeded earnings expectations and announced a chief-executive succession. Its coverage also describes continued weakness in discretionary home-improvement spending. Better quarterly results and a cautious outlook can coexist.',
  'Invezz meldt dat Home Depot de winstverwachtingen overtrof en een opvolging aan de top aankondigde. Tegelijk beschrijft het artikel zwakke uitgaven aan grotere, niet-noodzakelijke verbouwingen. Betere kwartaalcijfers en voorzichtigheid kunnen dus samengaan.',
  'Laut Invezz übertraf Home Depot die Gewinnerwartungen und kündigte eine Nachfolge an der Unternehmensspitze an. Zugleich beschreibt der Bericht schwache Ausgaben für größere, aufschiebbare Renovierungen. Gute Quartalszahlen und Vorsicht können zusammenpassen.'),
 ('Intel’s turnaround faces more questions','Meer vragen rond Intels herstel','Neue Fragen zu Intels Umbau',r'why is intel stock falling|intel.*lawsuit',
  'Invezz reports pressure on Intel shares, a change in Nvidia’s disclosed holding and a shareholder lawsuit. The lawsuit contains allegations about past disclosures. An allegation in a complaint is distinct from a court finding.',
  'Invezz bericht over druk op Intel, een wijziging in Nvidia’s gemelde belang en een rechtszaak van aandeelhouders. De zaak bevat beschuldigingen over eerdere informatieverstrekking. Een beschuldiging is geen rechterlijke vaststelling.',
  'Invezz berichtet über Kursdruck bei Intel, eine veränderte Nvidia-Beteiligung und eine Aktionärsklage. Die Klage enthält Vorwürfe zu früheren Veröffentlichungen. Ein Vorwurf in einer Klage ist kein gerichtliches Urteil.'),
 ('Software shares react to disruption','Softwareaandelen reageren op storingen','Softwareaktien reagieren auf Störungen',r'salesforce stock slides as technology outages',
  'Invezz reports declines in Salesforce and other software shares during a period of technology disruptions. The article explicitly says no public link has been established between those disruptions and the companies whose shares fell. A market reaction does not establish technical responsibility.',
  'Invezz meldt dalingen bij Salesforce en andere softwareaandelen tijdens technologische storingen. Het artikel zegt expliciet dat geen openbaar verband is vastgesteld tussen de storingen en deze bedrijven. Een koersreactie bewijst geen technische verantwoordelijkheid.',
  'Invezz meldet Verluste bei Salesforce und anderen Softwareaktien während technischer Störungen. Der Bericht hält fest, dass kein öffentlicher Zusammenhang zu diesen Unternehmen belegt ist. Eine Kursreaktion beweist keine technische Verantwortung.'),
 ('An AI listing attracts early attention','Een AI-beursgang trekt aandacht','Ein KI-Börsengang weckt Interesse',r'anthropic receives its first',
  'Invezz describes an early analyst endorsement ahead of the Anthropic listing discussed in this dataset. The valuation and growth arguments are the analyst’s estimates. This briefing reports the coverage and does not adopt the rating as a recommendation.',
  'Invezz beschrijft een vroeg analistenrapport over de Anthropic-beursgang in deze dataset. De waardering en groeiverwachtingen zijn schattingen van die analist. Deze briefing beschrijft het bericht en neemt de aanbeveling niet over.',
  'Invezz beschreibt eine frühe Analysteneinschätzung zum im Datensatz behandelten Anthropic-Börsengang. Bewertung und Wachstumserwartungen sind Schätzungen des Analysten. Diese Zusammenfassung übernimmt die Bewertung nicht als Anlageempfehlung.'),
 ('A phone scam with a real-world pickup','Telefoonfraude met een fysieke ophaaldienst','Telefonbetrug mit persönlicher Abholung',r'police issue urgent warning over phone scam',
  'IBTimes UK reports a Las Vegas police warning about callers impersonating officials and arranging collection of money or valuables. The article says some collections involve rideshare drivers who may not know what they are transporting. The warning concerns the specific scheme described by police.',
  'IBTimes UK beschrijft een politiewaarschuwing uit Las Vegas over bellers die zich voordoen als functionarissen en geld of waardevolle spullen laten ophalen. Soms zouden chauffeurs niet weten wat zij vervoeren. De waarschuwing betreft de door de politie beschreven fraude.',
  'IBTimes UK berichtet über eine Polizeiwarnung aus Las Vegas: Anrufer geben sich als Amtsträger aus und lassen Geld oder Wertsachen abholen. Manche Fahrer wissen laut Bericht möglicherweise nichts von dem Betrug. Die Warnung bezieht sich auf diese konkrete Masche.'),
]

CARDS += [
 ('The flight disruption: what is established','De vluchtverstoring: wat vaststaat','Flugausfälle: Was belegt ist',r'faa.*(ground stop|root cause)|flight crisis despite',
  'IBTimes UK reports on disruption following a nationwide US departure halt. Its coverage says investigators were still examining the technical cause. Political accusations in the report are attributed statements and do not establish responsibility for the failure.',
  'IBTimes UK bericht over verstoringen na een landelijke vertrekstop in de Verenigde Staten. Onderzoekers bekeken volgens het artikel nog de technische oorzaak. Politieke beschuldigingen zijn uitspraken van betrokkenen en stellen geen verantwoordelijkheid vast.',
  'IBTimes UK berichtet über Störungen nach einem landesweiten US-Abflugstopp. Die technische Ursache wurde laut Bericht noch untersucht. Politische Anschuldigungen sind zugeschriebene Aussagen und belegen keine Verantwortung.'),
 ('Ukraine’s satellite-link concerns','Oekraïense zorgen over satellietverbindingen','Sorgen um Satellitenverbindungen in der Ukraine',r'zelensky.*starlink cap',
  'IBTimes UK reports Ukrainian concerns about a speed restriction affecting satellite connections used by interceptor drones. The account attributes the operational claims to President Zelensky. The reported effects should be understood as his account of the situation.',
  'IBTimes UK beschrijft Oekraïense zorgen over een snelheidsbeperking bij satellietverbindingen voor onderscheppingsdrones. Het artikel schrijft de operationele beweringen toe aan president Zelensky. Het gaat om zijn beschrijving van de situatie.',
  'IBTimes UK beschreibt ukrainische Bedenken zu einer Geschwindigkeitsgrenze für Satellitenverbindungen von Abfangdrohnen. Der Bericht schreibt die operativen Angaben Präsident Selenskyj zu. Sie bleiben seine Darstellung der Lage.'),
 ('A glimpse of a possible future iPhone','Een glimp van een mogelijke nieuwe iPhone','Ein Blick auf ein mögliches künftiges iPhone',r'iphone 20 pro could',
  'IBTimes UK describes a leaked video that may hint at a future iPhone design. Apple has not confirmed the design or the product name discussed in the article. A component shown in an online video is not a confirmed finished product.',
  'IBTimes UK beschrijft een gelekte video die mogelijk op een toekomstig iPhone-ontwerp wijst. Apple heeft het ontwerp en de genoemde productnaam niet bevestigd. Een onderdeel in een online video is geen bevestigd eindproduct.',
  'IBTimes UK beschreibt ein geleaktes Video mit Hinweisen auf ein mögliches iPhone-Design. Apple hat weder das Design noch den genannten Produktnamen bestätigt. Ein Bauteil in einem Video ist kein bestätigtes Endprodukt.'),
 ('Banking interruptions and unanswered questions','Bankstoringen en onbeantwoorde vragen','Bankstörungen und offene Fragen',r'chase outage sparks',
  'IBTimes UK reports customer complaints about access to US online banking. The article distinguishes user reports from confirmed independent outages at every named bank. Speculation about a cyberattack does not establish the cause.',
  'IBTimes UK beschrijft klachten over toegang tot Amerikaans internetbankieren. Meldingen van gebruikers zijn niet hetzelfde als bevestigde, afzonderlijke storingen bij elke genoemde bank. Speculatie over een cyberaanval stelt de oorzaak niet vast.',
  'IBTimes UK berichtet über Zugangsprobleme beim US-Onlinebanking. Nutzermeldungen belegen nicht automatisch unabhängige Störungen bei jeder genannten Bank. Spekulationen über einen Cyberangriff klären die Ursache nicht.'),
 ('Indian design at the Earthshot gala','Indiaas ontwerp op het Earthshot-gala','Indisches Design bei der Earthshot-Gala',r'kate middleton.*earthshot gala',
  'IBTimes UK covers the Earthshot awards appearance in Mumbai and the Indian designers behind the royal outfits. The report includes the designer’s account of how an existing boutique garment was adapted for the event.',
  'IBTimes UK beschrijft de Earthshot-prijsuitreiking in Mumbai en de Indiase ontwerpers achter de koninklijke kleding. Een ontwerper vertelt in het artikel hoe een bestaand kledingstuk uit een boetiek voor het evenement werd aangepast.',
  'IBTimes UK berichtet über die Earthshot-Verleihung in Mumbai und die indischen Designer der königlichen Garderobe. Der Bericht enthält die Schilderung einer Designerin zur Anpassung eines vorhandenen Boutique-Kleides.'),
 ('Inside a water-focused investment fund','Een blik op een watergericht fonds','Ein Blick auf einen Wasserfonds',r'invesco global water etf.*strong',
  'Zacks examines the Invesco Global Water exchange-traded fund and explains its investment approach. This is fund research from a publisher, rather than a personal recommendation. A thematic fund’s name is a starting point for understanding its exposure, not a complete risk assessment.',
  'Zacks bespreekt het Invesco Global Water-beursfonds en de beleggingsaanpak. Dit is onderzoek van een uitgever, geen persoonlijke aanbeveling. De naam van een themafonds geeft een eerste indruk, maar is geen volledige risicobeoordeling.',
  'Zacks untersucht den Invesco Global Water ETF und erläutert dessen Ansatz. Es handelt sich um Fondsresearch eines Anbieters, nicht um eine persönliche Empfehlung. Ein Themenname ersetzt keine vollständige Risikobewertung.'),
]

def build(zip_path):
 z = zipfile.ZipFile(zip_path)
 rows = [json.loads(line) for n in z.namelist() if n.endswith('.jsonl') for line in z.read(n).decode('utf-8-sig').splitlines() if line.strip()]
 english = [a for a in rows if a.get('language')=='en']
 eng_invezz = [a for a in english if 'Invezz' in a.get('publication',{}).get('name','')]
 translations = collections.defaultdict(list)
 for a in rows:
  if a.get('language')=='en': continue
  candidates = [b for b in eng_invezz if b.get('source')==a.get('source')]
  if candidates:
   b = min(candidates,key=lambda b:abs((dt.datetime.fromisoformat(a['date'])-dt.datetime.fromisoformat(b['date'])).total_seconds()))
   if abs((dt.datetime.fromisoformat(a['date'])-dt.datetime.fromisoformat(b['date'])).total_seconds()) <= 1200:
    translations[b['$id']].append(a)
 translation_keys={variant['$id']:original for original,variants in translations.items() for variant in variants}
 def source(a):
  snippet=' '.join(a.get('excerpt','').split()[:20]).rstrip('…') if isinstance(a.get('excerpt'),str) else ''
  thumb=a.get('thumb_url') or ''
  return {'article_id':a['$id'],'outlet':a['publication']['name'],'headline':a['headline'],'url':a['permalink'],'date':a['date'],'language':a['language'],'tags':tags_for(a),'snippet':snippet,'translation_key':translation_keys.get(a['$id'],a['$id']),'image_url':thumb if isinstance(thumb,str) and thumb.startswith('https://') else ''}
 stories=[]; assigned=set()
 for i,card in enumerate(CARDS):
  en,nl,de,pat,se,sn,sd=card
  matches=[a for a in english if re.search(pat,a['headline'].lower()) and a['date'][:10]>='2026-11-13']
  if not matches: continue
  matches.sort(key=lambda a:a['date'],reverse=True)
  # Use the report that supports the reviewed summary, even if a related report is newer.
  evidence_pattern={0:r'^nasdaq rises as nvidia forecast',1:r'^jensen huang.s nvidia exit takes',2:r'^dollar firms after retail sales',13:r'^trump blames biden for us flight crisis'}.get(i)
  primary=next((a for a in matches if evidence_pattern and re.search(evidence_pattern,a['headline'],re.I)),matches[0])
  sources=[source(primary),*(source(a) for a in matches if a['$id']!=primary['$id'])]
  for a in matches:
   sources.extend(source(t) for t in translations[a['$id']]); assigned.add(a['$id'])
  sources=list({x['article_id']:x for x in sources}.values())
  tags=sorted(set(t for a in matches for t in tags_for(a)))
  # The summary is anchored to its primary report. Other articles are related
  # coverage, not evidence for every sentence in the human-written summary.
  primary_topic=['technology','technology','forex','economy','economy','energy','crypto','energy','markets','technology','technology','technology','money','world','world','technology','money','culture','markets'][i]
  stories.append({'id':'story-'+str(i+1),'title':en,'titles':{'en':en,'nl':nl,'de':de},'summary':se,'summaries':{'en':se,'nl':sn,'de':sd},'tags':tags,'primary_topic':primary_topic,'sources':sources,'claim_source_ids':[primary['$id']],'published_at':min(a['date'] for a in matches),'updated_at':max(a['date'] for a in matches),'curated':True,'art':['coral','sage','ink','sand','lavender'][i%5],'entities':[v for v in ['Nvidia','Intel','Bitcoin','Anthropic','Home Depot','Salesforce','Fed','Japan','Gold','Oil'] if v.lower() in (en+' '+primary['headline']).lower()],'kind':'developing' if len(matches)>1 else 'new'})
 linked_native_ids={a['$id'] for group in translations.values() for a in group}
 standalone_native=[a for a in rows if a.get('language')!='en' and a['$id'] not in linked_native_ids]
 for a in english+standalone_native:
  if a['$id'] in assigned: continue
  # Searchable metadata cards never expose the licensed body or full excerpt.
  related=[a]+translations[a['$id']]
  title=a['headline']; sid='item-'+digest(a['$id'])
  stories.append({'id':sid,'title':title,'titles':{b['language']:b['headline'] for b in related},'summary':'Additional source coverage. Open the original report for the complete story.','summaries':{},'tags':tags_for(a),'sources':[source(b) for b in related],'claim_source_ids':[],'published_at':a['date'],'updated_at':a['date'],'curated':False,'art':'sand','entities':[],'kind':'new'})
 dates=collections.Counter(a['date'][:10] for a in rows)
 topic_metadata=[{'id':k,'label':v[0]} for k,v in TOPICS.items()]+[{'id':k,'label':v[0],'parent':v[1]} for k,v in DETAILS.items()]
 catalog={'version':digest('catalog-v2|'+'|'.join(a['$id'] for a in rows)),'as_of':max(a['date'] for a in rows),'replay_day':'2026-11-19','topics':topic_metadata,'stats':{'articles':len(rows),'feeds':6,'stories':len(stories),'curated':sum(x['curated'] for x in stories),'translation_links':sum(len(v) for v in translations.values()),'recent_articles':sum(a['date'][:10]>='2026-11-13' for a in rows),'feed_counts':dict(collections.Counter(a['publication']['name'] for a in rows)),'date_counts':dict(sorted(dates.items()))},'stories':stories}
 (ROOT/'data').mkdir(exist_ok=True)
 # Keep full bodies in a separate local reader store, outside the shared catalog.
 if __package__:
  from .article_store import store_articles
 else:
  from article_store import store_articles
 store_articles(rows)
 path=ROOT/'data'/'catalog.json'
 pending=path.with_suffix('.pending')
 pending.write_text(json.dumps(catalog,ensure_ascii=False),encoding='utf-8')
 pending.replace(path)
 print(json.dumps(catalog['stats'],indent=2))
 return catalog

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('zip');args=p.parse_args();build(args.zip)
