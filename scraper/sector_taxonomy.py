"""Stable public sector categories built from the more detailed source labels."""


CATEGORY_NAMES = (
    "Consumer & Commerce",
    "Software & AI",
    "Deep Tech, Space & Defence",
    "Fintech & Financial Services",
    "Health, Wellness & Care",
    "Mobility & Logistics",
    "Food & Agriculture",
    "Climate & Energy",
    "Industry & Built World",
    "Education & Skills",
)


_RAW_INDUSTRY_CATEGORIES = {
    # Canonical values are idempotent when already stored.
    **{category: category for category in CATEGORY_NAMES},
    # Consumer, commerce, media, and lifestyle
    "Ecommerce": "Consumer & Commerce",
    "Retail": "Consumer & Commerce",
    "Consumer Services": "Consumer & Commerce",
    "Ecommerce / Jewellery (lab-grown diamonds)": "Consumer & Commerce",
    "E‑commerce / Home décor and furnishings": "Consumer & Commerce",
    "Jewellery / Lab-grown diamonds": "Consumer & Commerce",
    "Luxury commerce / Private concierge": "Consumer & Commerce",
    "Home services / installation and after-sales services": "Consumer & Commerce",
    "Pet Services": "Consumer & Commerce",
    "Entertainment Providers": "Consumer & Commerce",
    "Technology, Information and Media": "Consumer & Commerce",
    "Gaming": "Consumer & Commerce",
    "Travel": "Consumer & Commerce",
    "Experience-tech / Leisure": "Consumer & Commerce",
    "Retail Luxury Goods and Jewelry": "Consumer & Commerce",
    "Kitchen appliances": "Consumer & Commerce",
    "Retail Apparel and Fashion": "Consumer & Commerce",
    "Beauty & personal care": "Consumer & Commerce",
    "Retail / Jewelry": "Consumer & Commerce",
    "Women's wellness / Period care / D2C": "Health, Wellness & Care",

    # Financial services
    "Fintech": "Fintech & Financial Services",
    "Asset management": "Fintech & Financial Services",
    "Asset servicing / Financial services": "Fintech & Financial Services",
    "Financial technology / Banking infrastructure": "Fintech & Financial Services",
    "Financial‑services enterprise software / SaaS": "Fintech & Financial Services",
    "Fintech / Debt resolution": "Fintech & Financial Services",
    "Fintech (digital gold / savings)": "Fintech & Financial Services",
    "Financial Services": "Fintech & Financial Services",
    "Financial Services (NBFC)": "Fintech & Financial Services",

    # Health and care
    "Healthtech": "Health, Wellness & Care",
    "Eldercare / Senior care": "Health, Wellness & Care",
    "Maternal and baby care": "Health, Wellness & Care",
    "Wellness and Fitness Services": "Health, Wellness & Care",

    # Horizontal software and data products
    "Software Development": "Software & AI",
    "SaaS": "Software & AI",
    "Artificial Intelligence": "Software & AI",
    "Artificial intelligence / Agentic AI": "Software & AI",
    "Software Development (Enterprise AI)": "Software & AI",
    "Technology, Information and Internet": "Software & AI",
    "Staffing / HR tech": "Software & AI",
    "Human resources software / HCM": "Software & AI",
    "Customer experience / AI-powered CX platform": "Software & AI",
    "Data centers / Information Technology & Services": "Software & AI",
    "Embedded Software Products": "Software & AI",
    "Enterprise software, AI / Incident management": "Software & AI",
    "AI": "Software & AI",

    # Research-led, hardware, aerospace, space, and defence businesses
    "Deeptech": "Deep Tech, Space & Defence",
    "Aviation and Aerospace Component Manufacturing": "Deep Tech, Space & Defence",
    "Defense and Space Manufacturing": "Deep Tech, Space & Defence",
    "Space / Spacetech": "Deep Tech, Space & Defence",
    "Computer Hardware Manufacturing": "Deep Tech, Space & Defence",
    "IT Services and IT Consulting (Geospatial / GeoAI)": "Deep Tech, Space & Defence",
    "Physical AI / Robotics": "Deep Tech, Space & Defence",
    "Computer Hardware Manufacturing (photonic quantum computing)": "Deep Tech, Space & Defence",
    "Computer and Network Security": "Deep Tech, Space & Defence",

    # Climate and environmental services
    "Cleantech": "Climate & Energy",
    "Digital platform / Biomass & biofuels marketplace": "Climate & Energy",
    "Environmental Services": "Climate & Energy",
    "Environmental Services / Equipment Manufacturing (oil purification & filtration)": "Climate & Energy",
    "Environmental Services / Indoor Air Quality": "Climate & Energy",
    "Environmental Services / Watertech": "Climate & Energy",
    "Climate Technology Product Manufacturing": "Climate & Energy",

    # Mobility
    "Logistics": "Mobility & Logistics",
    "Transportation, Logistics, Supply Chain and Storage": "Mobility & Logistics",
    "Automotive": "Mobility & Logistics",
    "Electric motorcycle / Motor vehicle manufacturing": "Mobility & Logistics",
    "Electric motors / EV powertrains / Mechatronics": "Mobility & Logistics",
    "Electric two-wheelers / Electric vehicles": "Mobility & Logistics",
    "Electric vehicles (EVs)": "Mobility & Logistics",
    "Motor Vehicle Manufacturing": "Mobility & Logistics",

    # Food and agriculture
    "Agritech": "Food & Agriculture",
    "Foodtech": "Food & Agriculture",
    "Food and Beverage Services": "Food & Agriculture",
    "Food & Beverage": "Food & Agriculture",
    "Food & Beverage / Food Services": "Food & Agriculture",
    "Beverage Manufacturing": "Food & Agriculture",
    "Restaurants / Quick-service restaurants (QSR)": "Food & Agriculture",

    # Education
    "Edtech": "Education & Skills",

    # Industry and the built environment
    "Manufacturing": "Industry & Built World",
    "Industrial Automation": "Industry & Built World",
    "HVAC and Refrigeration Equipment Manufacturing": "Industry & Built World",
    "Specialty chemicals": "Industry & Built World",
    "Real Estate / Flexible Workspaces": "Industry & Built World",
    "Proptech": "Industry & Built World",
    "Wholesale Metals and Minerals": "Industry & Built World",
    "Personal care product manufacturing": "Consumer & Commerce",
}


# Generic imported labels need company-level resolution. These overrides are based
# on the companies' actual products, rather than the source platform label.
_COMPANY_CATEGORY_OVERRIDES = {
    "bct-ventures-launches-ai-native-consumer-brands-platform": "Consumer & Commerce",
    "creedom": "Consumer & Commerce",
    "digidukan": "Industry & Built World",
    "discovered-materials": "Deep Tech, Space & Defence",
    "instaastro": "Health, Wellness & Care",
    "quarkitech": "Deep Tech, Space & Defence",
    "ringg": "Software & AI",
    "switchon": "Industry & Built World",
    "vecton-ai": "Fintech & Financial Services",
    "wispr-flow": "Software & AI",
    "zenalyst": "Software & AI",
}


_KEYWORD_CATEGORIES = (
    ("Fintech & Financial Services", ("fintech", "banking", "payment", "lending", "insurance", "wealth", "asset management")),
    ("Health, Wellness & Care", ("health", "medical", "care", "wellness", "fitness", "pharma", "diagnostic")),
    ("Education & Skills", ("education", "edtech", "learning", "school", "student", "training", "upskill")),
    ("Mobility & Logistics", ("logistics", "supply chain", "transport", "automotive", "vehicle", "mobility", "powertrain")),
    ("Food & Agriculture", ("agri", "farm", "food", "restaurant", "beverage")),
    ("Climate & Energy", ("climate", "clean energy", "renewable", "environment", "biofuel", "waste", "emission")),
    ("Deep Tech, Space & Defence", ("deeptech", "deep tech", "space", "aerospace", "defence", "defense", "semiconductor", "robotics", "advanced materials")),
    ("Industry & Built World", ("manufactur", "industrial", "construction", "real estate", "property", "chemical", "hvac")),
    ("Consumer & Commerce", ("ecommerce", "e-commerce", "retail", "consumer", "creator", "entertainment", "home services", "jewellery", "pet")),
    ("Software & AI", ("software", "saas", "artificial intelligence", "agentic ai", "ai platform", "data center", "information technology", "it services", "technology platform", "internet")),
)


def sector_category(industry=None, canonical_slug=None, description=None):
    """Return one public category while retaining the source industry separately."""
    if canonical_slug in _COMPANY_CATEGORY_OVERRIDES:
        return _COMPANY_CATEGORY_OVERRIDES[canonical_slug]

    if industry in _RAW_INDUSTRY_CATEGORIES:
        return _RAW_INDUSTRY_CATEGORIES[industry]

    searchable = " ".join(value for value in (industry, description) if value).lower()
    for category, keywords in _KEYWORD_CATEGORIES:
        if any(keyword in searchable for keyword in keywords):
            return category
    return None


def present_categories(rows):
    """Return stable UI categories that are represented in the supplied rows."""
    represented = {
        sector_category(row.get("industry"), row.get("canonical_slug"), row.get("description"))
        for row in rows
    }
    return [category for category in CATEGORY_NAMES if category in represented]
