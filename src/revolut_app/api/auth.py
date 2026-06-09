import os
from pathlib import Path
from dotenv import load_dotenv, set_key

from . import RevolutClient


def main():
    env_path = Path(__file__).resolve().parents[3] / '.env'
    load_dotenv(env_path)

    client_params = {
        'client_id': os.getenv('REVOLUT_CLIENT_ID'),
        'financial_id': os.getenv('REVOLUT_FINANCIAL_ID'),
        'private_key_path': os.getenv('REVOLUT_PRIVATE_KEY_PATH'),
        'transport_cert_path': os.getenv('REVOLUT_TRANSPORT_CERT_PATH'),
        'kid': os.getenv('REVOLUT_KID'),
        'redirect_url': os.getenv('REVOLUT_REDIRECT_URL'),
    }

    missing = [k for k, v in client_params.items() if not v]
    if missing:
        raise ValueError(
            f'Missing required ENV variables: {', '.join(missing)}'
        )

    client = RevolutClient(**client_params)

    consent = client.create_consent()
    consent_id = consent['Data']['ConsentId']
    print(f'Successfull start create consent. \n Consent ID: {consent_id}')

    url = client.get_authorization_url(consent_id)
    print(f'\n Open this URL in your browser:\n{url}\n')

    code = input(
        "Enter the 'code' parameter from the redirect URL:"
    ).strip()
    if not code:
        print('Error: code is required.')
        return

    tokens = client.exchange_code(code)
    refresh_token = tokens.get('refresh_token')

    if refresh_token:
        set_key(str(env_path), 'REVOLUT_REFRESH_TOKEN', refresh_token)
        print(f'Success: REVOLUT_REFRESH_TOKEN saved')
    else:
        print('Error: Did not receive refresh_token.')


if __name__ == "__main__":
    main()
