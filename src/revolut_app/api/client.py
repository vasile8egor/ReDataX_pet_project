import requests
import jwt
import uuid
import time
import datetime
from pathlib import Path
from typing import Dict, Optional


class RevolutClient:
    def __init__(
        self,
        client_id: str,
        financial_id: str,
        private_key_path: str,
        transport_cert_path: str,
        kid: str,
        redirect_url: str
    ):
        self.client_id = client_id
        self.financial_id = financial_id
        self.private_key_path = Path(private_key_path)
        self.transport_cert_path = Path(transport_cert_path)
        self.kid = kid
        self.redirect_url = redirect_url

        self.base_api = "https://sandbox-oba-auth.revolut.com"
        self.auth_url = f"{self.base_api}/token"
        self.ui_url = "https://sandbox-oba.revolut.com/ui/index.html"

        import os
        self.access_token: Optional[str] = None
        self.refresh_token = os.getenv("REVOLUT_REFRESH_TOKEN")
        self.token_expires_at: float = 0

    def _cert(self):
        return (str(self.transport_cert_path), str(self.private_key_path))

    def _get_signing_key(self):
        return self.private_key_path.read_bytes()

    def _get_client_credentials_token(self) -> str:
        resp = requests.post(
            self.auth_url,
            cert=self._cert(),
            data={
                "grant_type": "client_credentials",
                "scope": "accounts",
                "client_id": self.client_id,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def create_consent(self) -> Dict:
        token = self._get_client_credentials_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "x-fapi-financial-id": self.financial_id,
            "x-fapi-interaction-id": str(uuid.uuid4()),
            "x-idempotency-key": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "Data": {
                "Permissions": [
                    "ReadAccountsBasic", "ReadAccountsDetail",
                    "ReadTransactionsBasic", "ReadTransactionsDetail",
                    "ReadTransactionsCredits", "ReadTransactionsDebits",
                ]
            },
            "Risk": {}
        }
        resp = requests.post(
            f"{self.base_api}/account-access-consents",
            json=payload,
            cert=self._cert(),
            headers=headers,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()

    def get_authorization_url(self, consent_id: str) -> str:
        now = int(time.time())
        claims = {
            "iss": self.client_id,
            "aud": "https://oba-auth.revolut.com",
            "response_type": "code id_token",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_url,
            "scope": "accounts",
            "state": str(uuid.uuid4()),
            "nonce": str(uuid.uuid4()),
            "max_age": 3600,
            "nbf": now,
            "exp": now + 300,
            "claims": {
                "id_token": {
                    "openbanking_intent_id": {"value": consent_id, "essential": True}
                }
            }
        }

        signed_jwt = jwt.encode(
            claims,
            self._get_signing_key(),
            algorithm="PS256",
            headers={"kid": self.kid, "alg": "PS256", "typ": "JWT"}
        )

        params = {
            "response_type": "code id_token",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_url,
            "scope": "accounts",
            "request": signed_jwt,
            "nonce": claims["nonce"],
            "state": claims["state"]
        }
        return self.ui_url + "?" + "&".join(f"{k}={v}" for k, v in params.items())

    def exchange_code(self, authorization_code: str) -> Dict:
        resp = requests.post(
            self.auth_url,
            cert=self._cert(),
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "code": authorization_code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=False,
        )
        resp.raise_for_status()
        td = resp.json()
        self.access_token = td["access_token"]
        self.refresh_token = td.get("refresh_token")
        self.token_expires_at = time.time() + td.get("expires_in", 300) - 60
        return td

    def refresh_tokens(self):
        """Обновляет access_token, используя существующий refresh_token"""
        if not self.refresh_token:
            import os
            self.refresh_token = os.getenv("REVOLUT_REFRESH_TOKEN")

        if not self.refresh_token:
            raise ValueError(
                "Refresh token is missing. Please run auth.py first.")

        resp = requests.post(
            self.auth_url,
            cert=self._cert(),
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": self.refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=False,
        )
        resp.raise_for_status()
        td = resp.json()

        self.access_token = td["access_token"]
        # Иногда Revolut выдает новый refresh_token, обновим его, если он пришел
        if "refresh_token" in td:
            self.refresh_token = td["refresh_token"]

        self.token_expires_at = time.time() + td.get("expires_in", 300) - 60
        return td

    def _build_headers(self) -> Dict:
        if not self.access_token or time.time() > self.token_expires_at:
            self.refresh_tokens()

        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "x-fapi-financial-id": self.financial_id,
            "x-fapi-interaction-id": f"int-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]}",
        }

    def get_accounts(self) -> Dict:
        headers = self._build_headers()
        resp = requests.get(
            f"{self.base_api}/accounts",
            cert=self._cert(),
            headers=headers,
            verify=False,
        )
        if resp.status_code == 401:
            self.refresh_tokens()
            headers = self._build_headers()
            resp = requests.get(
                f"{self.base_api}/accounts",
                cert=self._cert(),
                headers=headers,
                verify=False,
            )
        resp.raise_for_status()
        return resp.json()

    def get_transactions(
            self,
            account_id: str,
            from_date: Optional[str] = None,
            to_date: Optional[str] = None
    ) -> Dict:
        headers = self._build_headers()
        params = {}
        if from_date:
            params["fromBookingDateTime"] = from_date
        if to_date:
            params["toBookingDateTime"] = to_date

        resp = requests.get(
            f"{self.base_api}/accounts/{account_id}/transactions",
            cert=self._cert(),
            headers=headers,
            params=params,
            verify=False,
        )
        if resp.status_code == 401:
            self.refresh_tokens()
            headers = self._build_headers()
            resp = requests.get(
                f"{self.base_api}/accounts/{account_id}/transactions",
                cert=self._cert(), headers=headers, params=params,
                verify=False,
            )
        resp.raise_for_status()
        return resp.json()
