import hashlib
from pathlib import Path

import pytest

from revolut_app.real_market.binance.downloader import (
    verify_sha256,
)


def test_verifies_sha256(tmp_path: Path) -> None:
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
) -> None:
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
