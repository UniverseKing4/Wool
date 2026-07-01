import httpx
import re
import html
import asyncio

async def test_mojeek(query):
    url = f"https://www.mojeek.com/search?q={query}"
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        resp = await client.get(url)
    body = resp.text
    results = []
    # Mojeek: <li>...<a href="url" class="ob">title</a>...<p class="s">snippet</p>
    for block in re.finditer(r'<li>\s*<div[^>]*>.*?<a href="([^"]+)" class="ob"[^>]*>(.*?)</a>.*?<p class="s">(.*?)</p>', body, re.DOTALL | re.IGNORECASE):
        url = html.unescape(block.group(1))
        title = re.sub(r"<[^>]+>", "", block.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", block.group(3)).strip()
        results.append({"title": title, "url": url, "snippet": snippet})
    print("Mojeek results:", len(results))
    for r in results[:2]: print(r)

async def test_ecosia(query):
    url = f"https://www.ecosia.org/search?q={query}"
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        resp = await client.get(url)
    body = resp.text
    results = []
    # Ecosia might be SSR or JS only, let's see.
    # Look for a href and title.
    for block in re.finditer(r'<a class="result-title[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<p class="result-snippet[^"]*"[^>]*>(.*?)</p>', body, re.DOTALL | re.IGNORECASE):
        url = html.unescape(block.group(1))
        title = re.sub(r"<[^>]+>", "", block.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", block.group(3)).strip()
        results.append({"title": title, "url": url, "snippet": snippet})
    print("Ecosia results:", len(results))
    for r in results[:2]: print(r)

async def test_ddg_lite(query):
    url = f"https://lite.duckduckgo.com/lite/"
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        resp = await client.post(url, data={"q": query})
    body = resp.text
    results = []
    
    # DDG lite blocks look like:
    # <tr><td>...<a class="result-snippet" href="...">TITLE</a></td></tr>
    # <tr><td class="result-snippet">SNIPPET</td></tr>
    # <tr><td class="result-url">URL</td></tr>
    
    blocks = re.findall(r'<td class=\'result-snippet\'[^>]*>(.*?)</td>.*?<a class="result-url" href="([^"]+)">(.*?)</a>', body, re.DOTALL)
    if not blocks:
        # try another regex
        blocks2 = re.split(r"<table", body)
        for b in blocks2:
            m_a = re.search(r'<a class="result-snippet"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.DOTALL)
            m_snip = re.search(r'<td class=\'result-snippet\'[^>]*>(.*?)</td>', b, re.DOTALL)
            if m_a and m_snip:
                url = html.unescape(m_a.group(1))
                title = re.sub(r"<[^>]+>", "", m_a.group(2)).strip()
                snippet = re.sub(r"<[^>]+>", "", m_snip.group(1)).strip()
                results.append({"title": title, "url": url, "snippet": snippet})
    
    print("DDG Lite results:", len(results))
    for r in results[:2]: print(r)

asyncio.run(test_mojeek("python programming"))
asyncio.run(test_ecosia("python programming"))
asyncio.run(test_ddg_lite("python programming"))
