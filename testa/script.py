import urllib.request
import urllib.parse
import os

def scrape_jumia(params=None):
    """
    Fetches raw HTML from Jumia Kenya, dumps it to local storage for inspection,
    and returns a preview to the frontend.
    """
    search_query = params.get("query", "phones") if params else "phones"
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://www.jumia.co.ke/catalog/?q={encoded_query}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html_data = response.read().decode('utf-8', errors='ignore')

        # === DUMP TO LOCAL FILE ===
        dump_path = "jumia_dump.html"
        with open(dump_path, "w", encoding="utf-8") as f:
            f.write(html_data)

        full_dump_path = os.path.abspath(dump_path)

        # Snippet of the first 1000 characters to inspect in UI
        preview = html_data[:1000]

        return {
            "success": True,
            "query": search_query,
            "saved_to": full_dump_path,
            "html_length": len(html_data),
            "preview": preview
        }

    except Exception as e:
        return {"error": f"Scrape failed: {str(e)}"}
