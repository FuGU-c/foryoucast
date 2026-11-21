"""Local tags derived from the reporting, in addition to the editorial taxonomy."""
import re

ENTITIES = {
    'Nvidia': ('technology', r'\bnvidia\b|\$NVDA\b'),
    'Intel': ('technology', r'\bintel\b|\$INTC\b'),
    'Artificial intelligence': ('technology', r'\bartificial intelligence\b|\bAI\b|künstliche intelligenz'),
    'European Central Bank': ('economy', r'\bECB\b|\bEZB\b|European Central Bank'),
    'Federal Reserve': ('economy', r'Federal Reserve|\bFed\b'),
    'Bank of Japan': ('forex', r'Bank of Japan|\bBoJ\b'),
    'Bitcoin': ('crypto', r'\bBitcoin\b'),
    'Apple': ('technology', r'\bApple\b|\biPhone\b'),
    'Microsoft': ('technology', r'\bMicrosoft\b|\$MSFT\b'),
    'Oil prices': ('energy', r'\b(?:Brent|crude oil|WTI|oil prices)\b'),
    'Gold prices': ('energy', r'\b(?:gold prices|gold futures|XAU\/USD)\b'),
}


def story_topics(headline, tickers=(), sections=(), parent='world'):
    tags = [
        {'id':'news-'+re.sub(r'[^a-z0-9]+','-',name.lower()),'label':name,'parent':parent,'dynamic':True}
        for name,(parent,pattern) in ENTITIES.items() if re.search(pattern,headline,re.I)
    ]
    for ticker in dict.fromkeys(tickers or []):
        if not isinstance(ticker,str) or not re.fullmatch(r'[A-Z][A-Z0-9]{0,7}(?:[.-][A-Z0-9]{1,5})?',ticker):
            continue
        tags.append({'id':'ticker-'+ticker.lower(),'label':ticker,'parent':'markets','dynamic':True})
    ignored={'trending','uncategorized','news','latest','live comments','positive','negative','press releases','analyst blog'}
    for section in sections or []:
        if not isinstance(section,str):continue
        label=' '.join(section.split())
        if not 3<=len(label)<=45 or label.lower() in ignored or not re.fullmatch(r'[\w &+\-]+',label):continue
        if label.isupper() and len(label)>6:continue
        identifier='section-'+re.sub(r'[^a-z0-9]+','-',label.casefold()).strip('-')
        if identifier=='section-' or any(tag['label'].casefold()==label.casefold() for tag in tags):continue
        tags.append({'id':identifier,'label':label,'parent':parent,'dynamic':True})
        if len(tags)>=8:break
    return tags[:8]
