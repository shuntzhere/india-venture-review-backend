import unittest
from pathlib import Path

from scraper import parser
from scraper.company_identity import (
    clean_company_name,
    company_lookup_key,
    company_name_key,
    normalize_website,
    website_domain,
)
from scripts.standardize_company_data import proposed_updates


class CompanyIdentityNormalizationTests(unittest.TestCase):
    def test_shape_cleanup_preserves_brand_case_and_standardizes_dotted_ai(self):
        self.assertEqual(clean_company_name("  Exclusive:  SiMa.AI, "), "SiMa.ai")
        self.assertEqual(clean_company_name("Graph AI"), "Graph.ai")
        self.assertEqual(clean_company_name("YoLearn Ai"), "YoLearn.ai")
        self.assertEqual(clean_company_name("betterhood"), "betterhood")
        self.assertEqual(clean_company_name("CUNIN"), "CUNIN")

    def test_ai_spelling_variants_share_a_matching_key(self):
        keys = {company_name_key(value) for value in ("YoLearn.ai", "YOLEARN AI", "YoLearn Ai")}
        self.assertEqual(keys, {"yolearn ai"})

    def test_reviewed_former_name_resolves_to_current_identity(self):
        self.assertEqual(company_lookup_key("Curelink"), company_lookup_key("Disha"))

    def test_website_urls_have_one_storage_shape(self):
        self.assertEqual(normalize_website("HTTP://WWW.Example.AI/path?q=1"), "https://example.ai")
        self.assertEqual(normalize_website("example.ai"), "https://example.ai")
        self.assertEqual(website_domain("https://www.Example.ai/"), "example.ai")
        self.assertIsNone(normalize_website("not-a-domain"))


class NewIngestionRulesTests(unittest.TestCase):
    def test_investor_led_ai_name_keeps_internal_dot(self):
        title = "BluVenture leads Rs 100 Cr Series A round in E3 Electric.AI"
        self.assertEqual(parser._extract_company_name(title), "E3 Electric.ai")

    def test_compound_headline_keeps_only_company_subject(self):
        title = "BCT Ventures launches AI native consumer brands platform, raises Rs 42 Cr"
        self.assertEqual(parser._extract_company_name(title), "BCT Ventures")

    def test_descriptors_and_investment_purpose_are_not_company_names(self):
        cases = {
            "Novastar Partners invests in AJVC to back pre-seed startups": "AJVC",
            "Coffee equipment and services provider Kaapi Machines raises Rs 50 Cr": "Kaapi Machines",
            "The Pizza Bakery operator Popo Global raises Rs 532 Cr": "Popo Global",
            "Transition VC-backed Matel raises Rs 130 Cr": "Matel",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(parser._extract_company_name(title), expected)

    def test_article_domains_are_not_treated_as_verified_company_websites(self):
        fields = parser.extract_company_fields(
            "Runable raises $21 Mn",
            "Runable competes with Edysor.ai and other startups.",
        )
        self.assertIsNone(fields["website"])

    def test_founding_month_is_not_a_headquarters_city(self):
        city, state, country = parser._extract_headquarters("The company was founded in November 2025.")
        self.assertEqual((city, state, country), (None, None, None))


class ExistingDataBackfillTests(unittest.TestCase):
    def test_known_name_and_website_corrections_are_proposed(self):
        company = {
            "id": "company-1",
            "company_name": "YoLearn ai",
            "website": "yolearn.ai",
            "headquarters_city": None,
            "headquarters_country": None,
        }
        updates, reasons, _ = proposed_updates(company)
        self.assertEqual(updates["company_name"], "YoLearn.ai")
        self.assertEqual(updates["website"], "https://yolearn.ai")
        self.assertIn("canonical company display name", reasons)

    def test_month_city_is_cleared(self):
        company = {
            "id": "company-1",
            "company_name": "Example",
            "website": None,
            "headquarters_city": "November",
            "headquarters_country": "India",
        }
        updates, _, _ = proposed_updates(company)
        self.assertIsNone(updates["headquarters_city"])
        self.assertIsNone(updates["headquarters_country"])

    def test_schema_migration_contains_identity_guards(self):
        migration = Path("sql/standardize_company_identity.sql").read_text(encoding="utf-8")
        self.assertIn("company_name_normalized", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS public.company_aliases", migration)
        self.assertIn("website and website_evidence_url are required", migration)
        self.assertIn("companies_00_normalize_identity", migration)


if __name__ == "__main__":
    unittest.main()
