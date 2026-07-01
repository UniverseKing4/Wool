import httpx
import asyncio
import urllib.parse
import html

async def test_wiki(query):
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote_plus(query)}&utf8=&format=json"
    async with httpx.AsyncClient(headers={"User-Agent": "WoolBot/1.0 (https://github.com/UniverseKing4/Wool)"}) as client:
        resp = await client.get(url)
    data = resp.json()
    results = []
    for item in data.get("query", {}).get("search", []):
        results.append({
            "title": item["title"],
            "url": f"https://en.wikipedia.org/wiki/{item['title'].replace(' ', '_')}",
            "snippet": html.unescape(item["snippet"].replace('<span class="searchmatch">', '').replace('</span>', ''))
        })
    print("Wiki results:", len(results))
    for r in results[:2]: print(r)

asyncio.run(test_wiki("python programming"))
