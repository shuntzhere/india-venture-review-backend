"""Regression checks for wrong-entity and incomplete description extraction."""
import unittest
from scraper.parser import _extract_description

class DescriptionExtractionTests(unittest.TestCase):
    def test_competitor_and_acquirer_descriptions_are_not_used(self):
        cases = [
            ('ByteAsk raises $1 Mn', 'ByteAsk builds C++ coding agents. The founders sold LawSutra to Manupatra, an online legal research platform, last year.'),
            ('Balwaan Krishi raises Rs 100 Cr', 'Balwaan Krishi makes agricultural machinery. Tractor Junction, a digital marketplace for tractors, has raised funding.'),
            ('Sorry Sugar raises $1 Mn', 'Sorry Sugar sells coffee drinks. Peping, a functional beverage startup, has raised funding.'),
        ]
        for title, content in cases:
            with self.subTest(title=title):
                self.assertIsNone(_extract_description(title, content))

    def test_preserves_an_and_requires_company_identity(self):
        self.assertEqual(
            _extract_description('Example raises $2 Mn', 'Example, an enterprise software platform, has raised $2 million.'),
            'An enterprise software platform.',
        )
        self.assertIsNone(_extract_description('Funding news', 'Example, an enterprise platform, has raised funds.'))

    def test_complete_comma_separated_description_is_retained(self):
        self.assertEqual(
            _extract_description('CareCo raises $2 Mn', 'CareCo, a provider of mental health, addiction and dementia care services, has raised funding.'),
            'A provider of mental health, addiction and dementia care services.',
        )

    def test_no_cross_sentence_or_financial_fragment(self):
        self.assertIsNone(_extract_description('Theater raises Rs 75 Cr', 'Theater, a 4.5X increase from its old valuation. The fresh capital will support growth, has announced expansion.'))
        self.assertIsNone(_extract_description('Graph raises $2 Mn', 'Graph, a reduction of over 90%, has reported lower costs.'))

    def test_unknown_and_overlong_descriptions_stay_empty(self):
        self.assertIsNone(_extract_description('Example raises $2 Mn', 'Another firm, a software provider, has raised funding.'))
        self.assertIsNone(_extract_description('Example raises $2 Mn', 'Example, an '+('enterprise '*30)+'platform, has raised funding.'))

if __name__ == '__main__':
    unittest.main()
