import json
import unittest
from unittest.mock import MagicMock, patch

from scraper import company_website_enrichment as enrichment


class CompanyWebsiteResearchTests(unittest.TestCase):
    def test_requires_same_domain_official_evidence(self):
        response = MagicMock()
        response.json.return_value = {
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({
                        "identity_confident": True,
                        "website": "https://www.nova.ai/about",
                        "evidence_urls": ["https://news.example.test/nova"],
                    }),
                }],
            }]
        }
        session = MagicMock()
        session.post.return_value = response

        result = enrichment.research_official_website({
            "company_name": "Nova",
            "source_article_url": "https://news.example.test/nova",
        }, "key", session=session)

        self.assertIsNone(result)

    def test_verified_homepage_is_normalized_and_persisted(self):
        company = {
            "id": "company-1",
            "company_name": "Nova",
            "source_article_url": "https://news.example.test/nova",
        }
        client = MagicMock()
        with patch(
            "scraper.company_website_enrichment.research_official_website",
            return_value={
                "website": "https://nova.ai",
                "evidence_url": "https://nova.ai/about",
            },
        ):
            result = enrichment.enrich_new_company_websites(
                [company], client=client, api_key="key", workers=1
            )

        self.assertEqual(result["enriched"], 1)
        client.table.assert_any_call("company_identity_change_log")
        client.table.assert_any_call("companies")

    def test_pending_enrichment_combines_new_rows_and_retry_backlog(self):
        client = MagicMock()
        new_company = {
            "id": "new-1",
            "company_name": "New Company",
            "source_article_url": "https://news.example.test/new",
        }
        backlog_company = {
            "id": "old-1",
            "company_name": "Old Company",
            "source_article_url": "https://news.example.test/old",
        }
        expected = {"targets": 2, "enriched": 2, "unresolved": 0, "errors": []}
        with patch(
            "scraper.company_website_enrichment.list_missing_website_targets",
            return_value=[backlog_company],
        ), patch(
            "scraper.company_website_enrichment.enrich_new_company_websites",
            return_value=expected,
        ) as enrich:
            result = enrichment.enrich_pending_company_websites(
                [new_company], client=client, api_key="key", workers=2
            )

        self.assertEqual(result, expected)
        enrich.assert_called_once_with(
            [new_company, backlog_company],
            client=client,
            api_key="key",
            workers=2,
        )


if __name__ == "__main__":
    unittest.main()
