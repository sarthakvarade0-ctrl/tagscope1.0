#!/usr/bin/env python3
"""TagScope Disaster Intelligence: disaster news discovery and situational-awareness analysis."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote_plus
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from xml.etree import ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
import re
import threading
import time
import webbrowser

HOST = "127.0.0.1"
PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TagScopePro/2.0 RSS reader"
CACHE_SECONDS = 300
MIN_SOURCE_INTERVAL = 5.5
MAX_PER_SOURCE = 20

_cache = {}
_cache_lock = threading.Lock()
_source_locks = {"google": threading.Lock(), "bing": threading.Lock()}
_last_source_request = {"google": 0.0, "bing": 0.0}

CATEGORY_TERMS = {
    "Floods": {"flood", "floods", "flooding", "flooded", "flash flood", "flash floods", "inundation", "river overflow", "urban flooding", "dam overflow", "waterlogging"},
    "Cyclones & storms": {"cyclone", "cyclonic", "hurricane", "typhoon", "tropical storm", "storm surge", "landfall", "tornado", "severe storm", "windstorm", "thunderstorm"},
    "Earthquakes": {"earthquake", "earthquakes", "seismic", "tremor", "aftershock", "magnitude", "epicenter", "epicentre"},
    "Tsunamis": {"tsunami", "tsunamis", "tidal wave", "coastal inundation"},
    "Volcanic eruptions": {"volcanic eruption", "volcano", "volcanoes", "volcanic ash", "lava flow", "ash cloud"},
    "Industrial accidents": {"industrial accident", "chemical leak", "chemical spill", "gas leak", "factory explosion", "industrial fire", "hazardous material", "hazmat"},
    "Wildfires": {"wildfire", "wildfires", "forest fire", "forest fires", "bushfire", "bushfires", "firestorm", "burn scar"},
    "Landslides": {"landslide", "landslides", "mudslide", "mudslides", "rockslide", "rockfall", "debris flow"},
    "Extreme heat": {"heatwave", "heat wave", "extreme heat", "heat alert", "hot spell", "high temperature", "heatstroke"},
    "Drought": {"drought", "water scarcity", "water shortage", "dry spell", "crop failure", "reservoir depletion"},
    "Emergency response": {"evacuation", "evacuate", "rescue", "search and rescue", "emergency response", "emergency services", "warning", "alert", "shelter", "first responders", "missing people", "missing persons", "casualties", "disaster management", "relief operation"},
    "Relief & recovery": {"relief", "recovery", "rehabilitation", "reconstruction", "humanitarian aid", "relief camp", "relief camps", "displaced families", "resettlement", "damage assessment", "restoration", "rebuild"},
}
DISASTER_QUERY_TERMS = {
    "Floods": {"flood", "floods", "flooding", "inundation"},
    "Cyclones & storms": {"cyclone", "storm", "hurricane", "typhoon", "tornado"},
    "Earthquakes": {"earthquake", "seismic", "tremor"},
    "Tsunamis": {"tsunami", "tidal wave"},
    "Volcanic eruptions": {"volcanic eruption", "volcano", "volcanoes"},
    "Industrial accidents": {"industrial accident", "chemical leak", "chemical spill", "gas leak", "factory explosion"},
    "Wildfires": {"wildfire", "forest fire", "bushfire"},
    "Landslides": {"landslide", "mudslide", "rockslide"},
    "Extreme heat": {"heatwave", "heat wave", "extreme heat", "heatstroke"},
    "Drought": {"drought", "water scarcity"},
    "Emergency response": {"evacuation", "rescue", "emergency response", "disaster management", "warning", "alert"},
    "Relief & recovery": {"relief", "recovery", "rehabilitation", "reconstruction", "humanitarian aid"},
}

STOP_WORDS = set("a an the and or but if then of to in on at by for from with about as is are was were be been being it its this that these those their they them he she we you your our his her i not no into over after before new says said latest live update updates today amid more than how why what when where who will can could should would may might has have had all any some many much very also than according report reports news video photos watch read top first last one two".split())


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    return re.sub(r"\s+", " ", value).strip()


def local_name(tag):
    return tag.rsplit("}", 1)[-1].lower()


def child_text(element, wanted):
    for child in list(element):
        if local_name(child.tag) == wanted.lower():
            return "".join(child.itertext()).strip()
    return ""


def child_element(element, wanted):
    for child in list(element):
        if local_name(child.tag) == wanted.lower():
            return child
    return None


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def category_for(article, query=""):
    # Classify from the report itself first so a search term does not force every
    # result into the same category. Use the query only as a fallback.
    article_text = (article.get("title", "") + " " + article.get("description", "")).casefold()
    query_text = (query or "").casefold()

    def scores_for(text):
        scores = {}
        for category, terms in CATEGORY_TERMS.items():
            score = 0
            for term in terms:
                if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text):
                    score += 2 if " " in term else 1
            scores[category] = score
        return scores

    scores = scores_for(article_text)
    best = max(scores, key=scores.get)
    if scores[best]:
        return best
    for category, terms in DISASTER_QUERY_TERMS.items():
        if any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", query_text) for term in terms):
            return category
    return "Other disasters"


def wait_for_source_slot(source):
    with _source_locks[source]:
        elapsed = time.monotonic() - _last_source_request[source]
        delay = MIN_SOURCE_INTERVAL - elapsed
        if delay > 0:
            time.sleep(delay)
        _last_source_request[source] = time.monotonic()


def fetch_feed(source, query):
    encoded = quote_plus(query)
    if source == "google":
        url = "https://news.google.com/rss/search?q=" + encoded + "&hl=en-IN&gl=IN&ceid=IN:en"
        provider = "Google News"
    else:
        url = "https://www.bing.com/news/search?q=" + encoded + "&format=RSS"
        provider = "Bing News"
    wait_for_source_slot(source)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urlopen(request, timeout=18) as response:
        payload = response.read(2_500_000)
    root = ET.fromstring(payload)
    results = []
    for item in root.iter():
        if local_name(item.tag) not in ("item", "entry"):
            continue
        title = clean_text(child_text(item, "title"))
        link = child_text(item, "link")
        if not link:
            link_node = child_element(item, "link")
            if link_node is not None:
                link = link_node.attrib.get("href", "")
        description = clean_text(child_text(item, "description") or child_text(item, "summary") or child_text(item, "content"))
        published = clean_text(child_text(item, "pubdate") or child_text(item, "published") or child_text(item, "updated"))
        published_dt = parse_date(published)
        source_node = child_element(item, "source")
        publisher = clean_text("".join(source_node.itertext())) if source_node is not None else ""
        if not publisher and link:
            publisher = urlparse(link).netloc.replace("www.", "")
        if title and link and link.startswith(("https://", "http://")):
            results.append({
                "title": title,
                "url": link,
                "description": description[:900],
                "published": published,
                "publishedAt": published_dt.isoformat() if published_dt else None,
                "publisher": publisher or provider,
                "providers": [provider],
                "category": "Other disasters",
            })
        if len(results) >= MAX_PER_SOURCE:
            break
    return provider, results


def tokenize(text):
    return [word for word in re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", (text or "").casefold()) if word not in STOP_WORDS]


def summarize_results(query, articles):
    candidates = []
    query_words = set(tokenize(query))
    seen = set()
    for article in articles:
        text = article.get("description", "")
        if not text:
            text = article.get("title", "")
        for sentence in re.split(r"(?<=[.!?])\s+|\s+[|•]\s+", text):
            sentence = sentence.strip(" -\t\n")
            normalized = re.sub(r"\W+", " ", sentence.casefold()).strip()
            if len(sentence) < 35 or len(sentence) > 360 or normalized in seen:
                continue
            seen.add(normalized)
            words = tokenize(sentence)
            if not words:
                continue
            overlap = sum(1 for word in words if word in query_words)
            candidates.append((overlap / max(1, len(set(words))) + min(len(words), 25) / 250, sentence))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    key_points = [sentence for _, sentence in candidates[:4]]
    if not key_points:
        key_points = [a.get("title", "") for a in articles[:3] if a.get("title")]
    if not key_points:
        return {"summary": f'No readable descriptions were supplied for “{query}”. Open the original incident reports to review details.', "keyPoints": []}
    return {"summary": " ".join(key_points[:2])[:780], "keyPoints": key_points[:4]}


def deduplicate_articles(articles, query=""):
    merged = []
    by_title = {}
    seen_urls = set()
    for article in articles:
        normalized_title = re.sub(r"[^a-z0-9]+", " ", article["title"].casefold()).strip()
        normalized_url = article["url"].split("?")[0].rstrip("/").casefold()
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        if normalized_title in by_title:
            existing = merged[by_title[normalized_title]]
            existing["providers"] = sorted(set(existing["providers"] + article["providers"]))
            if len(article.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = article["description"]
            continue
        article["category"] = category_for(article, query)
        by_title[normalized_title] = len(merged)
        merged.append(article)
    return merged


def search_news(query):
    key = query.casefold().strip()
    now = time.time()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached["time"] < CACHE_SECONDS:
            result = dict(cached["data"])
            result["cached"] = True
            return result

    collected = []
    errors = []
    successful = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(fetch_feed, source, query): source for source in ("google", "bing")}
        for future in as_completed(futures):
            source = futures[future]
            try:
                provider, articles = future.result()
                successful.append(provider)
                collected.extend(articles)
            except (HTTPError, URLError, TimeoutError, ET.ParseError, OSError, ValueError) as exc:
                errors.append(f"{source.title()} News ({type(exc).__name__})")
            except Exception as exc:
                errors.append(f"{source.title()} News ({type(exc).__name__})")

    articles = deduplicate_articles(collected, query)
    if not articles:
        if errors:
            raise RuntimeError("News sources could not complete this search. Please wait a moment and try again. Details: " + "; ".join(errors))
        raise RuntimeError("No matching articles were returned. Try a broader topic or a different keyword.")

    summary = summarize_results(query, articles)
    data = {
        "query": query,
        "articles": articles,
        "summary": summary["summary"],
        "keyPoints": summary["keyPoints"],
        "providers": successful,
        "sourceErrors": errors,
        "cached": False,
        "notice": "Incident coverage combines available news feeds. Publication dates and descriptions depend on each publisher; this is not an official emergency alert service.",
    }
    with _cache_lock:
        _cache[key] = {"time": time.time(), "data": data}
    return data


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, status, content_type, data):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, obj):
        self.send_bytes(status, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self.send_json(200, {"ok": True, "app": "TagScope Disaster Intelligence"})
        if parsed.path == "/api/search":
            query = parse_qs(parsed.query).get("q", [""])[0].strip()
            query = re.sub(r"\s+", " ", query)[:180]
            if len(query) < 2:
                return self.send_json(400, {"error": "Enter at least two characters to search."})
            try:
                return self.send_json(200, search_news(query))
            except RuntimeError as exc:
                return self.send_json(503, {"error": str(exc)})
        if parsed.path in ("/", "/index.html"):
            return self.serve_static("index.html", "text/html; charset=utf-8")
        if parsed.path in ("/style.css", "/app.js"):
            name = parsed.path.lstrip("/")
            content_type = "text/css; charset=utf-8" if name.endswith(".css") else "text/javascript; charset=utf-8"
            return self.serve_static(name, content_type)
        return self.send_json(404, {"error": "Not found"})

    def serve_static(self, filename, content_type):
        try:
            data = (STATIC_DIR / filename).read_bytes()
        except OSError:
            return self.send_json(500, {"error": "A project file is missing. Re-extract the ZIP and try again."})
        self.send_bytes(200, content_type, data)

    def log_message(self, fmt, *args):
        print("[TagScope] " + (fmt % args))


def main():
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as exc:
        print(f"Could not start TagScope on port {PORT}: {exc}")
        print("Close another TagScope window or change PORT in server.py.")
        input("Press Enter to close...")
        return
    url = f"http://{HOST}:{PORT}"
    print("=" * 56)
    print("TagScope Disaster Intelligence is running")
    print(f"Open this address: {url}")
    print("Disaster reports | Incident brief | Report filters | Coverage signals | Compare reports")
    print("Press Ctrl+C in this window to stop the server.")
    print("=" * 56)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TagScope Pro...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
