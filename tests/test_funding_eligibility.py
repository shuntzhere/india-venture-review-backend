import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from scraper import database, parser
from scraper.entrackr import classify_article


def _article(title, url="https://example.test/article", content=""):
    return {
        "article_title": title,
        "article_url": url,
        "article_publication_date": "2026-09-02",
        "source_name": "Entrackr",
        "raw_content": content,
        "classification_confidence": "Strong",
    }


class FundingStatusTests(unittest.TestCase):
    def test_comet_raising_is_extracted_but_prospective(self):
        article = _article("Exclusive: Sneaker brand Comet raising Rs 99 Cr")
        with patch("scraper.parser._fetch_full_article", return_value=""):
            record, report = parser.process_article(article)

        self.assertEqual(record["company_name"], "Comet")
        self.assertEqual(record["funding_status"], "prospective")
        self.assertFalse(record["persistence_eligible"])
        self.assertFalse(report["persistence_eligible"])

    def test_mokobara_set_to_raise_is_extracted_but_prospective(self):
        article = _article("Exclusive: Mokobara set to raise Rs 91 Cr in Series C round")
        with patch("scraper.parser._fetch_full_article", return_value=""):
            record, report = parser.process_article(article)

        self.assertEqual(record["company_name"], "Mokobara")
        self.assertEqual(record["funding_status"], "prospective")
        self.assertFalse(record["persistence_eligible"])
        self.assertFalse(report["persistence_eligible"])

    def test_confirmed_headlines_are_classified_confirmed(self):
        self.assertEqual(parser.classify_funding_status("Nova raises $10M", ""), "confirmed")
        self.assertEqual(parser.classify_funding_status("Nova raised $10M", ""), "confirmed")

    def test_prospective_headlines_are_classified_prospective(self):
        self.assertEqual(parser.classify_funding_status("Nova in talks to raise $10M", ""), "prospective")
        self.assertEqual(parser.classify_funding_status("Nova plans to raise $10M", ""), "prospective")

    def test_ambiguous_article_is_unknown(self):
        self.assertEqual(parser.classify_funding_status("Nova funding update", ""), "unknown")
        self.assertEqual(
            parser.classify_funding_status("Nova funding update", "Nova has raised before and is raising again"),
            "unknown",
        )


class CurrentEventExtractionTests(unittest.TestCase):
    def test_headline_amount_beats_other_company_comparisons(self):
        title = "MSME-focused digital lender NeoGrowth raises Rs 85 Cr from FMO, LeapFrog"
        content = (
            "NeoGrowth has raised Rs 85 crore through a mix of equity and debt from FMO and "
            "LeapFrog Investments. In February 2026, Prayaan Capital raised Rs 110 crore in "
            "a Series A round led by Peak XV Partners."
        )
        fields = parser.extract_funding_fields(title, content)
        self.assertEqual(fields["funding_amount"], 85.0)
        self.assertEqual(fields["funding_round"], "equity and debt")

    def test_historical_round_does_not_supply_current_lead(self):
        self.assertIsNone(parser._extract_lead_investors(
            "NeoGrowth raises Rs 85 Cr from FMO, LeapFrog",
            "The company previously raised Rs 300 crore in a round led by FMO.",
        ))

    def test_theater_articles_do_not_treat_valuation_or_history_as_current_funding(self):
        cases = (
            (
                "Exclusive: Fashion brand Theater raises Series A at Rs 400 Cr valuation",
                "Digital-first fashion brand Theater has raised Rs 56.25 crore (around $6 million) "
                "in Series A funding. In September 2024, the company had raised $1.5 million in a "
                "pre-Series A round. The company's valuation stood at around Rs 402 crore, a 4.5X "
                "increase from its previous valuation of Rs 90 crore.",
                56.25,
                "Series A",
                400.0,
            ),
            (
                "Niveshaay leads Rs 75 Cr Series A round in fashion brand Theater",
                "Design-led fashion brand Theater has raised Rs 75 crore in its Series A funding "
                "round at a post-money valuation of Rs 410 crore. The startup had earlier raised "
                "$1.5 million in a pre-Series A round.",
                75.0,
                "Series A",
                410.0,
            ),
        )
        for title, content, amount, round_name, valuation in cases:
            with self.subTest(title=title):
                fields = parser.extract_funding_fields(title, content)
                self.assertEqual(fields["funding_amount"], amount)
                self.assertEqual(fields["funding_round"], round_name)
                self.assertEqual(fields["valuation"], valuation)


class CompanyNameExtractionTests(unittest.TestCase):
    def test_descriptor_prefixed_company_names_are_stripped(self):
        cases = {
            "Exclusive: Dosa chain Benne raises Rs 35 Cr": "Benne",
            "D2C athleisure brand BlissClub raises Rs 160 Cr": "BlissClub",
            "Fintech startup Nova raises $10M": "Nova",
            "Healthtech startup House of Student raises $2 Mn": "House of Student",
            "Electric motorcycle maker Matter raises $25 Mn growth round": "Matter",
            "MSME-focused digital lender NeoGrowth raises Rs 85 Cr from FMO, LeapFrog": "NeoGrowth",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(parser._extract_company_name(title), expected)

    def test_investor_led_headlines_extract_the_investee(self):
        cases = {
            "Lightspeed India leads $9 Mn seed round in deep-tech startup Discovered Materials": "Discovered Materials",
            "HighLeaf leads Rs 5 Cr pre-Series A round in FreightFox": "FreightFox",
            "Kae Capital leads Rs 8.5 Cr pre-seed round in Lane": "Lane",
            "Nikhil Kamath invests Rs 200 Cr in CtrlS as hyperscale data centre operator raises Rs 250 Cr": "CtrlS",
            "IAN Angel Fund and Rainmatter co-lead Rs 12.5 Cr seed round in climate-tech startup CarbonStrong": "CarbonStrong",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(parser._extract_company_name(title), expected)

    def test_investor_led_announced_round_is_confirmed_and_eligible(self):
        article = _article(
            "Lightspeed India leads $9 Mn seed round in deep-tech startup Discovered Materials"
        )
        with patch("scraper.parser._fetch_full_article", return_value=""):
            record, report = parser.process_article(article)

        self.assertEqual(record["company_name"], "Discovered Materials")
        self.assertEqual(record["funding_status"], "confirmed")
        self.assertTrue(report["persistence_eligible"])

    def test_investor_first_investment_is_confirmed_and_eligible(self):
        article = _article(
            "Nikhil Kamath invests Rs 200 Cr in CtrlS as hyperscale data centre operator raises Rs 250 Cr"
        )
        with patch("scraper.parser._fetch_full_article", return_value=""):
            record, report = parser.process_article(article)

        self.assertEqual(record["company_name"], "CtrlS")
        self.assertEqual(record["funding_status"], "confirmed")
        self.assertTrue(report["persistence_eligible"])

    def test_co_led_round_extracts_the_investee_and_is_eligible(self):
        article = _article(
            "IAN Angel Fund and Rainmatter co-lead Rs 12.5 Cr seed round in climate-tech startup CarbonStrong"
        )
        with patch("scraper.parser._fetch_full_article", return_value=""):
            record, report = parser.process_article(article)

        self.assertEqual(record["company_name"], "CarbonStrong")
        self.assertEqual(record["funding_status"], "confirmed")
        self.assertTrue(report["persistence_eligible"])

    def test_existing_and_prospective_company_name_patterns_are_preserved(self):
        cases = {
            "Nova raises $10M": "Nova",
            "Exclusive: Sneaker brand Comet raising Rs 99 Cr": "Comet",
            "Exclusive: Mokobara set to raise Rs 91 Cr in Series C round": "Mokobara",
            "Chain Reaction raises $10M": "Chain Reaction",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(parser._extract_company_name(title), expected)


class RelevanceExclusionTests(unittest.TestCase):
    def test_non_company_financial_events_are_rejected(self):
        cases = {
            "Bernstein raises Paytm target to Rs 2,200 on UPI MDR upside": "analyst price-target change",
            "Accel raises $550 Mn India fund, takes India corpus to $1.2 Bn": "VC or fund-manager fundraise",
            "Mirae Asset Venture Investments closes MAVOF II at Rs 1,125 Cr": "venture-fund close",
            "Aum Ventures announces first close of its Rs 250 Cr fund": "VC or fund-manager fundraise",
            "Aum Ventures closes State Street's Rs 580 Cr strategic investment fund": "VC or fund-manager fundraise",
            "TILT launches Rs 250 Cr impact-focused venture fund": "VC or fund-manager fundraise",
            "Table Space files DRHP for its proposed IPO": "IPO or public-markets fundraising",
            "Zetwerk files UDRHP to raise Rs 2,600 Cr via fresh issue": "IPO or public-markets fundraising",
            "Atomberg plans Rs 450 Cr fresh issue, Rs 90 Cr pre-IPO placement": "IPO or public-markets fundraising",
            "Nova acquires Rival in a block deal": "acquisition or secondary-market transaction",
            "Y Combinator sells another Rs 1,435 Cr stake in Groww": "acquisition or secondary-market transaction",
            "A91 invests Rs 143 Cr in Atomberg, sells Rs 445 Cr stake while retaining 21%": "acquisition or secondary-market transaction",
            "GST Council removes arrest powers, raises prosecution threshold to Rs 5 Cr": "regulatory or legal threshold",
            "NABVENTURES Fund II secures Rs 450 Cr in first close": "venture-fund close",
        }
        for title, reason in cases.items():
            with self.subTest(title=title):
                result = classify_article(title, "")
                self.assertFalse(result["accepted"])
                self.assertEqual(result["rejection_reason"], reason)

    def test_weekly_roundups_have_a_specific_rejection_reason(self):
        result = classify_article(
            "Funding and acquisitions in Indian startups this week [Aug 03 - Aug 08]",
            "The roundup also mentions a company that filed a DRHP.",
        )

        self.assertFalse(result["accepted"])
        self.assertEqual(result["rejection_reason"], "funding roundup")

    def test_body_context_does_not_trigger_structural_exclusions(self):
        cases = (
            (
                "Info Edge's Shiksha faces AI traffic headwinds as Q1 billings fall 23%",
                "The company previously made an acquisition and completed a secondary stake sale.",
            ),
            (
                "Table Space revenue crosses Rs 2,200 Cr in FY26; EBITDA jumps 88%",
                "The report also discusses a possible IPO and earlier DRHP plans.",
            ),
        )
        for title, content in cases:
            with self.subTest(title=title):
                result = classify_article(title, content)
                self.assertFalse(result["accepted"])
                self.assertIsNone(result["rejection_reason"])

    def test_legitimate_funding_is_not_rejected_for_body_history(self):
        result = classify_article(
            "Nova raises $10M in Seed round led by Apex",
            "The article notes a prior acquisition and a discontinued IPO plan.",
        )

        self.assertTrue(result["accepted"])
        self.assertIsNone(result["rejection_reason"])

    def test_private_funding_ahead_of_ipo_remains_eligible(self):
        title = "Navi raises $100 Mn from Prosus ahead of IPO"
        result = classify_article(title, "")

        self.assertTrue(result["accepted"])
        self.assertIsNone(result["rejection_reason"])
        article = _article(title)
        with patch("scraper.parser._fetch_full_article", return_value=""):
            record, report = parser.process_article(article)
        self.assertEqual(record["company_name"], "Navi")
        self.assertEqual(record["funding_status"], "confirmed")
        self.assertTrue(report["persistence_eligible"])

    def test_completed_strategic_investment_is_eligible(self):
        title = "Groww AMC closes State Street's Rs 580 Cr strategic investment"
        result = classify_article(title, "")

        self.assertTrue(result["accepted"])
        self.assertIn("funding_keyword", result["signals"])
        article = _article(title)
        with patch("scraper.parser._fetch_full_article", return_value=""):
            record, report = parser.process_article(article)
        self.assertEqual(record["company_name"], "Groww AMC")
        self.assertEqual(record["funding_status"], "confirmed")
        self.assertTrue(report["persistence_eligible"])

    def test_backed_and_non_funding_headlines_fail_relevance(self):
        cases = (
            "KKR-backed LEAP India makes muted debut, lists at 4% premium",
            "Bain Capital-backed Dhoot Transmission shares debut at 38% premium",
            "Exclusive: Krafton-backed Bobble AI enters insolvency process after failing to repay debt",
        )
        for title in cases:
            with self.subTest(title=title):
                result = classify_article(title, "")
                self.assertFalse(result["accepted"])

    def test_secondary_stake_sale_is_structurally_rejected(self):
        title = "Vijay Shekhar Sharma-backed Resilient to sell 4.98% Paytm stake; Antfin to benefit"
        result = classify_article(title, "")
        self.assertFalse(result["accepted"])
        self.assertEqual(result["rejection_reason"], "acquisition or secondary-market transaction")

    def test_legitimate_company_funding_remains_accepted(self):
        for title in (
            "Nova raises $10M in Seed round led by Apex",
            "Nova raises $10M from Apex Fund",
            "HighLeaf leads Rs 5 Cr pre-Series A round in FreightFox",
            "Kae Capital leads Rs 8.5 Cr pre-seed round in Lane",
        ):
            with self.subTest(title=title):
                self.assertTrue(classify_article(title, "")["accepted"])


class PersistenceEligibilityTests(unittest.TestCase):
    def test_prospective_record_is_not_persisted(self):
        record = {
            "company_name": "Comet",
            "article_title": "Comet raising Rs 99 Cr",
            "article_url": "https://example.test/comet",
            "article_publication_date": "2026-09-02",
            "source_name": "Entrackr",
            "funding_status": "prospective",
        }
        report = {
            "funding_status": "prospective",
            "funding_status_reason": "Prospective fundraising language detected",
        }
        client = MagicMock()
        with patch("scraper.database._get_client", return_value=client):
            result = database.persist_funding_records([(record, report)])

        self.assertEqual(result["stats"]["ineligible_skipped"], 1)
        self.assertEqual(result["stats"]["events_inserted"], 0)
        self.assertEqual(result["stats"]["companies_created"], 0)
        self.assertEqual(result["article_log"][0]["outcome"], "ineligible")
        self.assertEqual(client.method_calls, [])

    def test_unknown_record_is_not_persisted(self):
        record = {
            "company_name": "Nova",
            "article_title": "Nova funding update",
            "article_url": "https://example.test/nova-update",
            "article_publication_date": "2026-09-02",
            "source_name": "Entrackr",
            "funding_status": "unknown",
        }
        client = MagicMock()
        with patch("scraper.database._get_client", return_value=client):
            result = database.persist_funding_records([(record, {"funding_status": "unknown"})])

        self.assertEqual(result["stats"]["ineligible_skipped"], 1)
        self.assertEqual(result["stats"]["events_inserted"], 0)
        self.assertEqual(client.method_calls, [])

    def test_confirmed_record_is_persisted(self):
        article = _article(
            "Nova raises $10M in Seed round led by Apex",
            "https://example.test/nova",
        )
        record, report = parser.process_article(article)
        self.assertEqual(record["funding_status"], "confirmed")
        self.assertTrue(report["persistence_eligible"])
        with patch("scraper.database._get_client", return_value=MagicMock()), \
             patch("scraper.database._article_exists", return_value=False), \
             patch("scraper.database._find_company", return_value=None), \
             patch("scraper.database._create_company", return_value={"id": "company-1"}), \
             patch("scraper.database._find_matching_funding_event", return_value=None), \
             patch("scraper.database._insert_funding_event", return_value=True):
            result = database.persist_funding_records([(record, report)])

        self.assertEqual(result["stats"]["events_inserted"], 1)
        self.assertEqual(result["stats"]["companies_created"], 1)
        self.assertEqual(result["website_enrichment_targets"], [{
            "id": "company-1",
            "company_name": "Nova",
            "source_article_url": "https://example.test/nova",
        }])

    def test_repeat_coverage_attaches_source_instead_of_inserting_an_event(self):
        record = {
            "company_name": "Theater",
            "article_title": "Niveshaay leads Rs 75 Cr Series A round in fashion brand Theater",
            "article_url": "https://example.test/theater-follow-up",
            "article_publication_date": "2026-09-10",
            "source_name": "Entrackr",
            "funding_status": "confirmed",
            "funding_amount": 75.0,
            "currency": "INR Cr",
            "funding_round": "Series A",
            "lead_investors": "Niveshaay",
            "valuation": 410.0,
        }
        existing_event = {
            "id": "event-1",
            "funding_amount": 56.25,
            "currency": "INR crore",
            "funding_round": "Series A",
            "lead_investors": "Niveshaay",
            "valuation": 400.0,
            "manual_review_reason": None,
        }
        with patch("scraper.database._get_client", return_value=MagicMock()), \
             patch("scraper.database._article_exists", return_value=False), \
             patch("scraper.database._find_company", return_value={"id": "company-1"}), \
             patch("scraper.database._find_matching_funding_event", return_value=existing_event), \
             patch("scraper.database._attach_event_source", return_value=True) as attach, \
             patch("scraper.database._flag_event_conflict") as flag, \
             patch("scraper.database._insert_funding_event") as insert:
            result = database.persist_funding_records([(record, {"funding_status": "confirmed"})])

        self.assertEqual(result["stats"]["events_inserted"], 0)
        self.assertEqual(result["stats"]["event_sources_attached"], 1)
        self.assertEqual(result["stats"]["event_conflicts_flagged"], 1)
        self.assertEqual(result["article_log"][0]["outcome"], "source_attached")
        attach.assert_called_once_with(ANY, "event-1", record)
        flag.assert_called_once()
        insert.assert_not_called()

    def test_event_match_requires_round_and_independent_corroboration(self):
        existing = {
            "funding_amount": 56.25,
            "currency": "INR crore",
            "funding_round": "Series A",
            "lead_investors": "Niveshaay",
        }
        same_event = {
            "funding_amount": 75.0,
            "currency": "INR Cr",
            "funding_round": "series-a",
            "lead_investors": "Niveshaay",
        }
        unrelated = {**same_event, "lead_investors": "Other Capital", "funding_amount": 120.0}
        different_round = {**same_event, "funding_round": "Series B"}

        self.assertTrue(database._events_match(existing, same_event))
        self.assertFalse(database._events_match(existing, unrelated))
        self.assertFalse(database._events_match(existing, different_round))

    def test_source_migration_backfills_and_captures_canonical_articles(self):
        migration = Path("sql/add_funding_event_sources.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS public.funding_event_sources", migration)
        self.assertIn("INSERT INTO public.funding_event_sources", migration)
        self.assertIn("AFTER INSERT ON public.funding_events", migration)
        self.assertIn("ON CONFLICT (article_url) DO NOTHING", migration)

        repair = Path("sql/reconcile_theater_series_a.sql").read_text(encoding="utf-8")
        self.assertIn("SET funding_event_id = canonical_event_id", repair)
        self.assertIn("DELETE FROM public.funding_events", repair)


if __name__ == "__main__":
    unittest.main()
