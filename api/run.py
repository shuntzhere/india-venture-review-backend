import sys
import os
import json
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler

from scraper.entrackr import fetch_entrackr_articles
from scraper.parser import extract_funding_records
from scraper.database import persist_funding_records


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self._run()

    def do_POST(self):
        self._run()

    def _run(self):
        start = datetime.datetime.now(datetime.timezone.utc)
        run_id = f"IVR-{start.strftime('%Y%m%d-%H%M')}"

        try:
            articles = fetch_entrackr_articles(verbose=False)

            if not articles:
                self._json(200, {
                    "run_id": run_id,
                    "status": "success",
                    "message": "No funding articles found in the last 24 hours",
                    "articles_fetched": 0,
                })
                return

            records = extract_funding_records(articles)
            db_result = persist_funding_records(records)

            self._json(200, {
                "run_id": run_id,
                "status": "success",
                "articles_fetched": len(articles),
                "records_produced": len(records),
                "stats": db_result["stats"],
            })

        except Exception as e:
            self._json(500, {
                "run_id": run_id,
                "status": "error",
                "message": str(e),
            })

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))
