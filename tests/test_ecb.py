"""Tests for ECB vendor adapter (no DB, mocked HTTP)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import polars as pl
import pytest

from deephold_db.vendors.ecb import ECB_SERIES, ECBVendor, _parse_ecb_csv

# --- Sample CSV payloads (real-ish, taken from the SDMX 2.1 endpoint) -----

DAILY_CSV = (
    "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE,"
    "OBS_STATUS,OBS_CONF,OBS_PRE_BREAK,OBS_COM,TIME_FORMAT,BREAKS,COLLECTION,"
    "COMPILING_ORG,DISS_ORG,DOM_SER_IDS,PUBL_ECB,PUBL_MU,PUBL_PUBLIC,"
    "UNIT_INDEX_BASE,COMPILATION,COVERAGE,DECIMALS,NAT_TITLE,SOURCE_AGENCY,"
    "SOURCE_PUB,TITLE,TITLE_COMPL,UNIT,UNIT_MULT\n"
    "EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2024-06-03,1.0842,A,F,,,,,,,,"
    ",,,,,,,,,,4,,4F0,,US dollar/Euro,EUR,0\n"
    "EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2024-06-04,1.0865,A,F,,,,,,,,"
    ",,,,,,,,,,4,,4F0,,US dollar/Euro,EUR,0\n"
    "EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2024-06-05,1.0872,A,F,,,,,,,,"
    ",,,,,,,,,,4,,4F0,,US dollar/Euro,EUR,0\n"
)

MONTHLY_CSV = (
    "KEY,FREQ,REF_AREA,ADJUSTMENT,ICP_ITEM,STS_INSTITUTION,ICP_SUFFIX,TIME_PERIOD,"
    "OBS_VALUE,OBS_STATUS,OBS_CONF,OBS_PRE_BREAK,OBS_COM,TIME_FORMAT,BREAKS,"
    "COLLECTION,COMPILING_ORG,DATA_COMP,DISS_ORG,DOM_SER_IDS,PUBL_ECB,PUBL_MU,"
    "PUBL_PUBLIC,UNIT_INDEX_BASE,COMPILATION,COVERAGE,DECIMALS,SOURCE_AGENCY,"
    "TITLE,TITLE_COMPL,UNIT,UNIT_MULT\n"
    "ICP.M.U2.N.000000.4.ANR,M,U2,N,000000,4,ANR,2024-01,2.8,A,F,,,,,,,,,"
    ",,,,,,1,,HICP - Overall,PCCH,0\n"
    "ICP.M.U2.N.000000.4.ANR,M,U2,N,000000,4,ANR,2024-02,2.6,A,F,,,,,,,,,"
    ",,,,,,1,,HICP - Overall,PCCH,0\n"
    "ICP.M.U2.N.000000.4.ANR,M,U2,N,000000,4,ANR,2024-03,2.4,A,F,,,,,,,,,"
    ",,,,,,1,,HICP - Overall,PCCH,0\n"
)

EMPTY_CSV = (
    "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE,"
    "OBS_STATUS,OBS_CONF,OBS_PRE_BREAK,OBS_COM,TIME_FORMAT,BREAKS,COLLECTION,"
    "COMPILING_ORG,DISS_ORG,DOM_SER_IDS,PUBL_ECB,PUBL_MU,PUBL_PUBLIC,"
    "UNIT_INDEX_BASE,COMPILATION,COVERAGE,DECIMALS,NAT_TITLE,SOURCE_AGENCY,"
    "SOURCE_PUB,TITLE,TITLE_COMPL,UNIT,UNIT_MULT\n"
)


# --- Parser unit tests -----------------------------------------------------


def test_parse_daily_csv() -> None:
    df = _parse_ecb_csv(DAILY_CSV)
    assert df.height == 3
    assert df.columns == ["date", "value"]
    assert df.schema == {"date": pl.Date, "value": pl.Float64}
    assert df["value"][0] == pytest.approx(1.0842)
    assert df["date"][0] == date(2024, 6, 3)


def test_parse_monthly_csv() -> None:
    df = _parse_ecb_csv(MONTHLY_CSV)
    assert df.height == 3
    # Monthly TIME_PERIOD "2024-01" → date 2024-01-01
    assert df["date"][0] == date(2024, 1, 1)
    assert df["value"][0] == pytest.approx(2.8)
    assert df["date"][2] == date(2024, 3, 1)


def test_parse_empty_csv() -> None:
    df = _parse_ecb_csv(EMPTY_CSV)
    assert df.is_empty()
    assert df.schema == {"date": pl.Date, "value": pl.Float64}


# --- Vendor tests ----------------------------------------------------------


def test_ecb_registry_has_known_series() -> None:
    assert "ECB:EXR:USD.EUR.SP00.A" in ECB_SERIES
    assert "ECB:ICP:U2.N.000000.4.ANR" in ECB_SERIES
    assert ECB_SERIES["ECB:EXR:USD.EUR.SP00.A"]["flow"] == "EXR"


def test_ecb_vendor_default_url() -> None:
    v = ECBVendor()
    assert v.base_url == "https://data-api.ecb.europa.eu/service"


def test_ecb_vendor_custom_url() -> None:
    v = ECBVendor(base_url="https://example.test/service/")
    assert v.base_url == "https://example.test/service"  # trailing slash stripped


def test_ecb_fetch_registry_symbol() -> None:
    v = ECBVendor()
    v._get_csv = MagicMock(return_value=DAILY_CSV)  # type: ignore[method-assign]
    df = v.fetch("ECB:EXR:USD.EUR.SP00.A", date(2024, 6, 1), date(2024, 6, 30))
    assert df.height == 3
    args, _ = v._get_csv.call_args
    assert args[0] == "/data/EXR/D.USD.EUR.SP00.A"


def test_ecb_fetch_adhoc_symbol() -> None:
    v = ECBVendor()
    v._get_csv = MagicMock(return_value=DAILY_CSV)  # type: ignore[method-assign]
    df = v.fetch("EXR/D.USD.EUR.SP00.A", date(2024, 6, 1), date(2024, 6, 30))
    assert df.height == 3


def test_ecb_fetch_monthly_series() -> None:
    v = ECBVendor()
    v._get_csv = MagicMock(return_value=MONTHLY_CSV)  # type: ignore[method-assign]
    df = v.fetch("ECB:ICP:U2.N.000000.4.ANR", date(2024, 1, 1), date(2024, 12, 31))
    assert df.height == 3
    assert df["date"][0] == date(2024, 1, 1)


def test_ecb_fetch_unknown_symbol() -> None:
    v = ECBVendor()
    df = v.fetch("not-a-real-symbol", date(2024, 1, 1), date(2024, 12, 31))
    assert df.is_empty()
    assert df.schema == {"date": pl.Date, "value": pl.Float64}


def test_ecb_healthcheck_ok() -> None:
    v = ECBVendor()
    v._get_csv = MagicMock(return_value=DAILY_CSV)  # type: ignore[method-assign]
    assert v.healthcheck() is True


def test_ecb_healthcheck_fail_on_exception() -> None:
    v = ECBVendor()
    v._get_csv = MagicMock(side_effect=Exception("network down"))  # type: ignore[method-assign]
    assert v.healthcheck() is False


def test_ecb_healthcheck_fail_on_empty() -> None:
    v = ECBVendor()
    v._get_csv = MagicMock(return_value=EMPTY_CSV)  # type: ignore[method-assign]
    assert v.healthcheck() is False
