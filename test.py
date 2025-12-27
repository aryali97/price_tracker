import asyncio
from crawl4ai import *

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://www.abercrombie.com/shop/us/p/boucle-cardigan-61412332?categoryId=12202&faceout=life&seq=03&pagefm=navigation-grid&prodvm=navigation-grid"
        )
        print(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())
