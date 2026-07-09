from app import config


def test_deal_size_bands_are_ordered_and_labeled():
    assert list(config.DEAL_SIZE_BANDS.keys()) == ["smb", "mid", "enterprise", "global"]
    for label in config.DEAL_SIZE_BANDS.values():
        assert "ACV" in label


def test_finance_templates_have_company_placeholder():
    assert config.FINANCE_QUERY_TEMPLATES
    for t in config.FINANCE_QUERY_TEMPLATES:
        assert "{company}" in t


def test_token_ceiling_raised_for_longer_brief():
    assert config.MAX_TOKENS >= 3400
