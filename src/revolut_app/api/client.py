import os
import requests
import jwt
import uuid
import time
import datetime
from pathlib import Path
from typing import Dict, Optional

from revolut_app.core.constants import (
    REVOLUT_BASE_API,
    REVOLUT_AUTH_URL,
    REVOLUT_UI_URL
)


class RevolutClient:
    def __init__(
        self,
        client_id,
        financial_id,
        private_key_path,
        transport_cert_path,
        kid: str,
        redirect_url: str
    ):
        self.client_id = client_id
        self.financial_id = financial_id
        self.private_key_path = Path(private_key_path)
        self.transport_cert_path = Path(transport_cert_path)
        self.kid = kid
        self.redirect_url = redirect_url

        self.base_api = REVOLUT_BASE_API
        self.auth_url = REVOLUT_AUTH_URL
        self.ui_url = REVOLUT_UI_URL

        self.access_token: Optional[str] = None
        self.refresh_token = os.getenv('REVOLUT_REFRESH_TOKEN')
        self.token_expires_at = 0

    @classmethod
    def from_env(cls) -> 'RevolutClient':
        return cls(
            client_id=os.getenv('REVOLUT_CLIENT_ID'),
            financial_id=os.getenv('REVOLUT_FINANCIAL_ID'),
            private_key_path=os.getenv('REVOLUT_PRIVATE_KEY_PATH'),
            transport_cert_path=os.getenv('REVOLUT_TRANSPORT_CERT_PATH'),
            kid=os.getenv('REVOLUT_KID'),
            redirect_url=os.getenv('REVOLUT_REDIRECT_URL')
        )

    def set_refresh_token(self, refresh_token: Optional[str]) -> None:
        if refresh_token:
            self.refresh_token = refresh_token

    def _cert(self):
        return (str(self.transport_cert_path), str(self.private_key_path))

    def _get_signing_key(self):
        return self.private_key_path.read_bytes()

    def _get_client_credentials_token(self) -> str:
        resp = requests.post(
            self.auth_url,
            cert=self._cert(),
            data={
                'grant_type': 'client_credentials',
                'scope': 'accounts',
                'client_id': self.client_id,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()['access_token']
    
    def _build_headers(self):
        if not self.access_token or time.time() > self.token_expires_at:
            self.refresh_tokens()

        return {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}',
            'x-fapi-financial-id': self.financial_id,
            'x-fapi-interaction-id': (
                f"int-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]}"
            ),
        }

    def create_consent(self):
        token = self._get_client_credentials_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'x-fapi-financial-id': self.financial_id,
            'x-fapi-interaction-id': str(uuid.uuid4()),
            'x-idempotency-key': str(uuid.uuid4()),
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        payload = {
            'Data': {
                'Permissions': [
                    'ReadAccountsBasic',
                    'ReadAccountsDetail',
                    'ReadTransactionsBasic',
                    'ReadTransactionsDetail',
                    'ReadTransactionsCredits',
                    'ReadTransactionsDebits',
                ]
            },
            'Risk': {}
        }
        resp = requests.post(
            f'{self.base_api}/account-access-consents',
            json=payload,
            cert=self._cert(),
            headers=headers,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()

    def get_authorization_url(self, consent_id: str):
        now = int(time.time())
        claims = {
            'iss': self.client_id,
            'aud': 'https://oba-auth.revolut.com',
            'response_type': 'code id_token',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_url,
            'scope': 'accounts',
            'state': str(uuid.uuid4()),
            'nonce': str(uuid.uuid4()),
            'max_age': 3600,
            'nbf': now,
            'exp': now + 300,
            'claims': {
                'id_token': {
                    'openbanking_intent_id': {
                        'value': consent_id,
                        'essential': True
                    }
                }
            }
        }

        signed_jwt = jwt.encode(
            claims,
            self._get_signing_key(),
            algorithm='PS256',
            headers={'kid': self.kid, 'alg': 'PS256', 'typ': 'JWT'}
        )

        params = {
            'response_type': 'code id_token',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_url,
            'scope': 'accounts',
            'request': signed_jwt,
            'nonce': claims['nonce'],
            'state': claims['state']
        }
        return self.ui_url + '?' + '&'.join(f'{k}={v}' for k, v in params.items())

    def exchange_code(self, authorization_code: str) -> Dict:
        resp = requests.post(
            self.auth_url,
            cert=self._cert(),
            data={
                'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'code': authorization_code,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            verify=False,
        )
        resp.raise_for_status()
        td = resp.json()
        self.access_token = td['access_token']
        self.refresh_token = td.get('refresh_token')
        self.token_expires_at = time.time() + td.get('expires_in', 300) - 60
        return td

    def refresh_tokens(self):
        if not self.refresh_token:
            import os
            self.refresh_token = os.getenv('REVOLUT_REFRESH_TOKEN')

        if not self.refresh_token:
            raise ValueError(
                'Refresh token is missing. Please run auth.py first.')

        resp = requests.post(
            self.auth_url,
            cert=self._cert(),
            data={
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'refresh_token': self.refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=False,
        )
        resp.raise_for_status()
        td = resp.json()

        self.access_token = td['access_token']
        if 'refresh_token' in td:
            self.refresh_token = td['refresh_token']

        self.token_expires_at = time.time() + td.get('expires_in', 300) - 60
        return td

    def get_accounts(self):
        headers = self._build_headers()
        resp = requests.get(
            f'{self.base_api}/accounts',
            cert=self._cert(),
            headers=headers,
            verify=False,
        )
        if resp.status_code == 401:
            self.refresh_tokens()
            headers = self._build_headers()
            resp = requests.get(
                f'{self.base_api}/accounts',
                cert=self._cert(),
                headers=headers,
                verify=False,
            )
        resp.raise_for_status()
        return resp.json()

    def get_transactions(
            self,
            account_id,
            from_date = None,
            to_date = None
    ):
        headers = self._build_headers()
        params = {}
        if from_date:
            params["fromBookingDateTime"] = from_date
        if to_date:
            params["toBookingDateTime"] = to_date

        resp = requests.get(
            f'{self.base_api}/accounts/{account_id}/transactions',
            cert=self._cert(),
            headers=headers,
            params=params,
            verify=False,
        )
        if resp.status_code == 401:
            self.refresh_tokens()
            headers = self._build_headers()
            resp = requests.get(
                f'{self.base_api}/accounts/{account_id}/transactions',
                cert=self._cert(),
                headers=headers,
                params=params,
                verify=False,
            )
        resp.raise_for_status()
        return resp.json()
