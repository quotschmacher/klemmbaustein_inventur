from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx


class RebrickableImportError(RuntimeError):
    pass


class RebrickableClient:
    def __init__(self, api_key: str, client: httpx.Client) -> None:
        if not api_key:
            raise RebrickableImportError("REBRICKABLE_API_KEY ist nicht konfiguriert.")
        self._client = client
        self._headers = {"Authorization": f"key {api_key}"}
        self._base_host = urlparse(str(client.base_url)).netloc

    def fetch_all_pages(self, path: str) -> list[dict[str, object]]:
        next_url: str | None = path
        results: list[dict[str, object]] = []

        while next_url is not None:
            parsed = urlparse(next_url)
            if parsed.netloc and parsed.netloc != self._base_host:
                raise RebrickableImportError("Die API-Pagination verweist auf eine unzulässige Quelle.")
            try:
                response = self._client.get(next_url, headers=self._headers, timeout=10.0)
            except httpx.RequestError as error:
                raise RebrickableImportError("Rebrickable ist derzeit nicht erreichbar.") from error
            if response.status_code == 429:
                raise RebrickableImportError("Rebrickable hat das Rate-Limit erreicht.")
            try:
                response.raise_for_status()
                payload = response.json()
                page_results = payload["results"]
                next_value = payload["next"]
            except (httpx.HTTPStatusError, KeyError, TypeError, ValueError) as error:
                raise RebrickableImportError(
                    "Rebrickable lieferte keine vollständige Ergebnisliste."
                ) from error
            if not isinstance(page_results, list) or not all(isinstance(item, dict) for item in page_results):
                raise RebrickableImportError("Rebrickable lieferte keine vollständige Ergebnisliste.")
            if next_value is not None and not isinstance(next_value, str):
                raise RebrickableImportError("Rebrickable lieferte eine ungültige Pagination.")
            results.extend(page_results)
            next_url = urljoin(str(self._client.base_url), next_value) if next_value else None

        return results

    def fetch_object(self, path: str) -> dict[str, object]:
        try:
            response = self._client.get(path, headers=self._headers, timeout=10.0)
        except httpx.RequestError as error:
            raise RebrickableImportError("Rebrickable ist derzeit nicht erreichbar.") from error
        if response.status_code == 429:
            raise RebrickableImportError("Rebrickable hat das Rate-Limit erreicht.")
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, ValueError) as error:
            raise RebrickableImportError("Rebrickable lieferte keine vollständigen Set-Daten.") from error
        if not isinstance(payload, dict):
            raise RebrickableImportError("Rebrickable lieferte keine vollständigen Set-Daten.")
        return payload
