import hashlib
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

import revolut_app.real_market.binance.downloader as downloader
from revolut_app.real_market.binance.downloader import (
    _download_atomic,
    _is_retryable_download_error,
    verify_sha256,
)


def test_verifies_sha256(tmp_path: Path):
    archive_path = tmp_path / 'data.zip'
    checksum_path = (
        tmp_path / 'data.zip.CHECKSUM'
    )

    payload = b'real-market-test-data'

    archive_path.write_bytes(payload)

    expected = hashlib.sha256(
        payload
    ).hexdigest()

    checksum_path.write_text(
        f'{expected}  data.zip\n',
        encoding='utf-8',
    )

    resolved_expected, actual = (
        verify_sha256(
            archive_path=archive_path,
            checksum_path=checksum_path,
        )
    )

    assert resolved_expected == expected
    assert actual == expected


def test_rejects_checksum_mismatch(
    tmp_path: Path,
):
    archive_path = tmp_path / 'data.zip'
    checksum_path = (
        tmp_path / 'data.zip.CHECKSUM'
    )

    archive_path.write_bytes(b'actual')

    wrong_hash = hashlib.sha256(
        b'another-value'
    ).hexdigest()

    checksum_path.write_text(
        f'{wrong_hash}  data.zip\n',
        encoding='utf-8',
    )

    with pytest.raises(
        ValueError,
        match='checksum mismatch',
    ):
        verify_sha256(
            archive_path=archive_path,
            checksum_path=checksum_path,
        )


def test_download_atomic_retries_transient_url_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    destination = tmp_path / 'archive.zip'
    calls = []
    sleeps = []

    def fake_urlopen(
        request,
        *,
        timeout: int,
    ):
        calls.append((request.full_url, timeout))

        if len(calls) == 1:
            raise URLError(
                'temporary DNS failure'
            )

        return BytesIO(b'archive-bytes')

    monkeypatch.setattr(
        downloader,
        'urlopen',
        fake_urlopen,
    )
    monkeypatch.setattr(
        downloader.time,
        'sleep',
        sleeps.append,
    )

    _download_atomic(
        url='https://data.binance.vision/test.zip',
        destination=destination,
        timeout_seconds=10,
        attempts=2,
        retry_backoff_seconds=0.25,
    )

    assert destination.read_bytes() == b'archive-bytes'
    assert not destination.with_suffix(
        '.zip.part'
    ).exists()
    assert calls == [
        (
            'https://data.binance.vision/test.zip',
            10,
        ),
        (
            'https://data.binance.vision/test.zip',
            10,
        ),
    ]
    assert sleeps == [0.25]


def test_http_not_found_is_not_retryable():
    error = HTTPError(
        url='https://data.binance.vision/missing.zip',
        code=404,
        msg='Not Found',
        hdrs=None,
        fp=None,
    )

    assert not _is_retryable_download_error(error)
