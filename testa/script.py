import urllib.request
import urllib.parse
from html.parser import HTMLParser

class JumiaHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.products = []
        self.in_card = False
        self.in_name = False
        self.in_price = False
        self.current_name = ""
        self.current_price = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_class = attr_dict.get('class', '')

        # Detect product card container
        if tag == 'article' and 'prd' in tag_class:
            self.in_card = True
            self.current_name = ""
            self.current_price = ""

        if self.in_card:
            if tag in ['div', 'h3'] and 'name' in tag_class:
                self.in_name = True
            elif tag == 'div' and 'prc' in tag_class:
                self.in_price = True

    def handle_endtag(self, tag):
        if tag in ['div', 'h3']:
            self.in_name = False
            self.in_price = False

        if tag == 'article' and self.in_card:
            if self.current_name and self.current_price:
                self.products.append({
                    "name": self.current_name.strip(),
                    "price": self.current_price.strip()
                })
            self.in_card = False

    def handle_data(self, data):
        if self.in_name:
            self.current_name += data
        elif self.in_price:
            self.current_price += data


def scrape_jumia(params=None):
    """
    Queries Jumia Kenya using pure Python standard libraries (urllib + html.parser).
    No pip dependencies required!
    """
    search_query = params.get("query", "phones") if params else "phones"
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://www.jumia.co.ke/catalog/?q={encoded_query}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html_data = response.read().decode('utf-8', errors='ignore')

        parser = JumiaHTMLParser()
        parser.feed(html_data)

        return {
            "success": True,
            "query": search_query,
            "total_found": len(parser.products),
            "products": parser.products[:8] # Return top 8
        }

    except Exception as e:
        return {"error": f"Scrape failed: {str(e)}"}
