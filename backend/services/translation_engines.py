"""
Translation engine adapters for BhashaSetu.

Architecture:

    translation_service.translate()
            |
            v
    BhashiniDhruvaEngine  (Bhashini NMT, cloud, requires credentials)
            |
            v
    phrase / glossary fallback (offline, labelled)

Only a configured, successful engine call ever produces mode="real".
Local IndicTrans2 is intentionally NOT an adapter here: its checkpoints
(objectstore fairseq copies) are HTTP 403 from this network, the official
Hugging Face copies are licence-gated, and neither fairseq nor
IndicTransToolkit ships Windows wheels on this toolchain, so a verified
local Hindi→Santali model cannot be loaded in this environment today.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

from backend.config import Config


class TranslationEngineUnavailable(RuntimeError):
    """Raised when an engine cannot run (no credentials, network, model)."""


class BhashiniDhruvaEngine:
    """Bhashini (DHRUVA / ULCA pipeline) NMT adapter.

    Uses the public-inference flow exactly as documented at
    https://bhashini.gitbook.io/bhashini-apis:

    1. Pipeline Config Call:
       POST https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline
       headers: userID, ulcaApiKey
       body:    {pipelineTasks:[{taskType:"translation",
                                 config:{language:{sourceLanguage,targetLanguage}}}],
                 pipelineRequestConfig:{pipelineId}}
       -> returns the compute callback URL, an inference auth header, and the
          per-language-pair serviceId.

    2. Compute Call:
       POST <callbackURL>
       headers: <inference auth header>, Content-Type: application/json
       body:    {pipelineTasks:[{taskType:"translation",
                                 config:{language:{sourceLanguage,targetLanguage},
                                         serviceId}}],
                 inputData:{input:[{source: text}]}}
       -> returns {pipelineResponse:[{output:[{target: translated}]}]}
    """

    CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"

    def __init__(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.user_id = (user_id if user_id is not None else Config.BHASHINI_USER_ID) or ""
        self.api_key = (api_key if api_key is not None else Config.BHASHINI_API_KEY) or ""
        self.pipeline_id = (pipeline_id if pipeline_id is not None else Config.BHASHINI_PIPELINE_ID) or ""
        self.timeout = timeout if timeout is not None else Config.BHASHINI_TRANSLATION_TIMEOUT
        # Cache of per-pair compute endpoints: (src, tgt) -> (callback_url, headers, service_id)
        self._config_cache: dict = {}
        # Prevent hammering a failing config call on every request.
        self._last_config_attempt: float = 0.0
        self._config_retry_after: float = 15.0

    # ------------------------------------------------------------------
    def available(self) -> bool:
        return bool(self.user_id and self.api_key and self.pipeline_id)

    # ------------------------------------------------------------------
    def _config_for(self, source: str, target: str) -> tuple[str, dict, str]:
        key = (source, target)
        cached = self._config_cache.get(key)
        if cached:
            return cached

        if not self.available():
            raise TranslationEngineUnavailable(
                "Bhashini credentials are incomplete (need BHASHINI_USER_ID, "
                "BHASHINI_API_KEY and BHASHINI_PIPELINE_ID)."
            )

        now = time.time()
        if now - self._last_config_attempt < self._config_retry_after:
            raise TranslationEngineUnavailable("Bhashini pipeline config call throttled.")

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source,
                            "targetLanguage": target,
                        }
                    },
                }
            ],
            "pipelineRequestConfig": {"pipelineId": self.pipeline_id},
        }
        headers = {
            "userID": self.user_id,
            "ulcaApiKey": self.api_key,
            "Content-Type": "application/json",
        }
        self._last_config_attempt = now

        try:
            response = requests.post(self.CONFIG_URL, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TranslationEngineUnavailable(
                f"Bhashini pipeline config call failed: {exc.__class__.__name__}: {exc}"
            ) from exc

        data = response.json()
        endpoint = data.get("pipelineInferenceAPIEnfPoint") or {}
        callback_url = (endpoint.get("callbackURL") or "").strip()
        inference_key = endpoint.get("inferenceApiKey") or {}
        auth_header = {
            (inference_key.get("name") or "Authorization").strip():
            (inference_key.get("value") or "").strip()
        }
        if not callback_url:
            raise TranslationEngineUnavailable(
                "Bhashini pipeline config returned no callbackURL (pair may be unsupported)."
            )

        service_id = ""
        for task in data.get("pipelineResponseConfig") or []:
            if task.get("taskType") != "translation":
                continue
            cfg = task.get("config")
            entries = cfg if isinstance(cfg, list) else [cfg]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                lang = entry.get("language") or {}
                sid = entry.get("serviceId") or ""
                if lang.get("sourceLanguage") == source and lang.get("targetLanguage") == target:
                    service_id = (sid or "").strip()
                if service_id:
                    break
            if service_id:
                break
        if not service_id:
            raise TranslationEngineUnavailable(
                f"Bhashini pipeline has no translation service for {source}->{target}."
            )

        entry = (callback_url, auth_header, service_id)
        self._config_cache[key] = entry
        return entry

    # ------------------------------------------------------------------
    def translate(self, text: str, source: str, target: str) -> str:
        """Return translated text or raise TranslationEngineUnavailable."""
        callback_url, auth_header, service_id = self._config_for(source, target)

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source,
                            "targetLanguage": target,
                        },
                        "serviceId": service_id,
                    },
                }
            ],
            "inputData": {"input": [{"source": text}]},
        }
        headers = dict(auth_header)
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json")

        try:
            response = requests.post(callback_url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TranslationEngineUnavailable(
                f"Bhashini inference call failed: {exc.__class__.__name__}: {exc}"
            ) from exc

        data = response.json()
        try:
            output = data["pipelineResponse"][0]["output"][0]["target"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationEngineUnavailable(
                f"Bhashini inference returned an unexpected payload: {type(data).__name__}"
            ) from exc
        translated = str(output).strip()
        if not translated:
            raise TranslationEngineUnavailable("Bhashini inference returned empty text.")
        return translated