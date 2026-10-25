from datetime import date

import pytest

from app.auth.authorization import is_document_active

TODAY = date(2026, 10, 25)


def doc(**overrides):
    base = {
        "status": "official",
        "effective_date": "2026-01-01",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("bad", [0, False, "garbage", "2026-13-40", 123])
def test_malformed_expiration_is_denied(bad):
    assert not is_document_active(doc(expiration_date=bad), today=TODAY)


@pytest.mark.parametrize("ok", [None, ""])
def test_missing_expiration_means_no_expiry(ok):
    assert is_document_active(doc(expiration_date=ok), today=TODAY)