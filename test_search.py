import httpx
import re
import html
import asyncio

async def test_yahoo(query):
    url = f"https://search.yahoo.com/search?p={query}"
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        resp = await client.get(url)
    body = resp.text
    results = []
    # Yahoo result blocks usually have class="algo-sr" or similar.
    # Let's just look for <h3 class="title"><a href="url">title</a>
    for block in re.finditer(r'<div class="compTitle[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<div class="compText[^>]*>(.*?)</div>', body, re.DOTALL | re.IGNORECASE):
        url = html.unescape(block.group(1))
        title = re.sub(r"<[^>]+>", "", block.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", block.group(3)).strip()
        results.append({"title": title, "url": url, "snippet": snippet})
    print("Yahoo results:", len(results))
    for r in results[:2]: print(r)

async def test_mojeek(query):
    url = f"https://www.mojeek.com/search?q={query}"
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        resp = await client.get(url)
    body = resp.text
    results = []
    # Mojeek: <li> <div class="ob"><a href="url" class="ob">title</a></div> <p class="s">snippet</p>
    for block in re.finditer(r'<li>.*?<a href="([^"]+)" class="ob"[^>]*>(.*?)</a>.*?<p class="s">(.*?)</p>', body, re.DOTALL | re.IGNORECASE):
        url = html.unescape(block.group(1))
        title = re.sub(r"<[^>]+>", "", block.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", block.group(3)).strip()
        results.append({"title": title, "url": url, "snippet": snippet})
    print("Mojeek results:", len(results))
    for r in results[:2]: print(r)

async def test_ddg_lite(query):
    url = f"https://lite.duckduckgo.com/lite/"
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        resp = await client.post(url, data={"q": query})
    body = resp.text
    results = []
    # DDG Lite: <tr class='result-snippet'>...
    # The URL is in the previous tr, <a class='result-snippet' href='...'>
    # DDG Lite is a bit tricky, let's look for <a class="result-url" href="...">
    for title_match, snippet_match in zip(
        re.finditer(r'<a[^>]+class="result-url"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.DOTALL),
        re.finditer(r'<td class="result-snippet"[^>]*>(.*?)</td>', body, re.DOTALL)
    ):
        url = html.unescape(title_match.group(1))
        title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()
        results.append({"title": title, "url": url, "snippet": snippet})
    print("DDG Lite results:", len(results))
    for r in results[:2]: print(r)

asyncio.run(test_yahoo("python programming"))
asyncio.run(test_mojeek("python programming"))
asyncio.run(test_ddg_lite("python programming"))
