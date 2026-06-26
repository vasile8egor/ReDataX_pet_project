import hashlib
import os
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

from revolut_app.real_market.models import (
    BinanceAggTradeArchiveSpec,
    DownloadedBinanceArchive,
)


BINANCE_PUBLIC_DATA_BASE_URL = 'https://data.binance.vision'

DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def calculate_sha256(path: Path):
    digest = hashlib.sha256()

    with path.open("rb") as source:
        while chunk := source.read(DOWNLOAD_CHUNK_SIZE):
            digest.update(chunk)

    return digest.hexdigest()


def parse_checksum_file(path: Path):
    content = path.read_text(encoding='utf-8').strip()

    if not content:
        raise ValueError(f'Checksum file is empty: {path}')

    expected_hash = content.split()[0].lower()

    if len(expected_hash) != 64:
        raise ValueError(
            'Expected SHA-256 checksum with '
            f'64 hexadecimal characters: {expected_hash!r}'
        )

    try:
        int(expected_hash, 16)
    except ValueError as error:
        raise ValueError(
            f'Checksum is not hexadecimal: {expected_hash!r}'
        ) from error

    return expected_hash


def verify_sha256(archive_path: Path, checksum_path: Path):
    expected = parse_checksum_file(checksum_path)

    actual = calculate_sha256(archive_path)

    if actual != expected:
        raise ValueError(
            'Binance archive checksum mismatch: '
            f'path={archive_path}, '
            f'expected={expected}, '
            f'actual={actual}'
        )

    return expected, actual


def download_binance_agg_trades_archive(
    *,
    spec: BinanceAggTradeArchiveSpec,
    output_directory: Path,
    timeout_seconds: int = 180,
) -> DownloadedBinanceArchive:
    if timeout_seconds <= 0:
        raise ValueError(
            'timeout_seconds must be positive'
        )

    symbol_directory = (
        output_directory
        / 'spot'
        / 'daily'
        / 'aggTrades'
        / spec.symbol
    )

    symbol_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    archive_path = (
        symbol_directory / spec.filename
    )

    checksum_path = (
        symbol_directory
        / spec.checksum_filename
    )

    archive_url = (
        f'{BINANCE_PUBLIC_DATA_BASE_URL}/'
        f'{spec.relative_path}'
    )

    checksum_url = (
        f'{archive_url}.CHECKSUM'
    )

    _download_atomic(
        url=checksum_url,
        destination=checksum_path,
        timeout_seconds=timeout_seconds,
    )

    if archive_path.exists():
        try:
            expected, actual = verify_sha256(
                archive_path=archive_path,
                checksum_path=checksum_path,
            )

            return DownloadedBinanceArchive(
                spec=spec,
                archive_path=archive_path,
                checksum_path=checksum_path,
                expected_sha256=expected,
                actual_sha256=actual,
            )
        except ValueError:
            archive_path.unlink(
                missing_ok=True
            )

    _download_atomic(
        url=archive_url,
        destination=archive_path,
        timeout_seconds=timeout_seconds,
    )

    expected, actual = verify_sha256(
        archive_path=archive_path,
        checksum_path=checksum_path,
    )

    return DownloadedBinanceArchive(
        spec=spec,
        archive_path=archive_path,
        checksum_path=checksum_path,
        expected_sha256=expected,
        actual_sha256=actual,
    )


def _download_atomic(
    *,
    url: str,
    destination: Path,
    timeout_seconds: int,
):
    temporary_path = destination.with_suffix(
        destination.suffix + ".part"
    )

    temporary_path.unlink(
        missing_ok=True
    )

    request = Request(
        url,
        headers={
            'User-Agent': (
                'ReDataX-real-market-research/1.0'
            )
        },
    )

    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            with temporary_path.open(
                'wb'
            ) as output:
                shutil.copyfileobj(
                    response,
                    output,
                    length=DOWNLOAD_CHUNK_SIZE,
                )

        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
