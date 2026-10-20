from typing import Any, Dict, Optional

from backend.app.adapters.base import FBRAdapter
from backend.app.adapters.mock_adapter import MockFBRAdapter
from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.adapters.production_adapter import ProductionFBRAdapter
from backend.app.adapters.integrator_adapter import LicensedIntegratorAdapter
from backend.app.core.config import settings


class FBRAdapterFactory:
    """Factory to resolve the appropriate FBR integration adapter
    based on tenant configuration, credentials, and deployment environment.
    """

    @staticmethod
    def get_adapter(
        mode: str = "DEMO",
        tenant_settings: Optional[Any] = None,
        forced_scenario: str = "AUTO",
    ) -> FBRAdapter:
        mode_upper = (mode or settings.FBR_ENVIRONMENT or "DEMO").upper()

        # Extract tenant-level credentials if available
        base_url = getattr(tenant_settings, "fbr_base_url", None) or settings.FBR_API_URL or None
        api_token = getattr(tenant_settings, "fbr_api_token", None) or settings.FBR_API_KEY or None
        pos_id = getattr(tenant_settings, "fbr_pos_id", None) or getattr(settings, "FBR_DEFAULT_POS_ID", "10001")

        if mode_upper in ("DEMO", "MOCK"):
            return MockFBRAdapter(forced_scenario=forced_scenario)

        elif mode_upper == "SANDBOX":
            return SandboxFBRAdapter(
                base_url=base_url,
                bearer_token=api_token,
                pos_id=pos_id,
                forced_scenario=forced_scenario,
            )

        elif mode_upper == "PRODUCTION":
            return ProductionFBRAdapter(
                base_url=base_url,
                bearer_token=api_token,
                pos_id=pos_id,
                client_id=settings.FBR_CLIENT_ID,
                client_secret=settings.FBR_CLIENT_SECRET,
            )

        elif mode_upper in ("LICENSED_INTEGRATOR", "INTEGRATOR", "PRAL"):
            return LicensedIntegratorAdapter(
                base_url=base_url,
                api_key=api_token,
                pos_id=pos_id,
            )

        # Fallback safe default
        return MockFBRAdapter(forced_scenario=forced_scenario)

    @classmethod
    def get_adapter_for_tenant(
        cls,
        credential: Optional[Any] = None,
        tenant_settings: Optional[Any] = None,
        forced_scenario: str = "AUTO",
    ) -> FBRAdapter:
        """Resolves adapter using organization-specific decrypted FBRCredential or settings."""
        # Tenant's configured operating mode is authoritative. A "PRAL" credential
        # describes the issuing authority, NOT an integrator simulation.
        mode = (
            getattr(tenant_settings, "fbr_mode", None)
            or getattr(credential, "environment", None)
            or getattr(credential, "provider", None)
            or "DEMO"
        ).upper()
        if credential is None or not getattr(credential, "is_active", True):
            return cls.get_adapter(
                mode=mode,
                tenant_settings=tenant_settings,
                forced_scenario=forced_scenario,
            )

        token = credential.get_auth_token() or credential.get_api_key()
        base_url = (
            getattr(tenant_settings, "fbr_base_url", None)
            or credential.base_url
            or settings.FBR_API_URL
            or None
        )
        pos_id = (
            credential.fbr_pos_id
            or getattr(tenant_settings, "fbr_pos_id", None)
            or "10001"
        )

        if mode in ("DEMO", "MOCK"):
            return MockFBRAdapter(forced_scenario=forced_scenario)
        if mode == "SANDBOX":
            return SandboxFBRAdapter(
                base_url=base_url, bearer_token=token, pos_id=pos_id,
                forced_scenario=forced_scenario,
            )
        if mode in ("PRODUCTION", "PRAL"):
            return ProductionFBRAdapter(
                base_url=base_url, bearer_token=token, pos_id=pos_id,
                client_id=credential.get_client_id() or settings.FBR_CLIENT_ID,
                client_secret=credential.get_client_secret() or settings.FBR_CLIENT_SECRET,
            )
        if mode in ("LICENSED_INTEGRATOR", "INTEGRATOR"):
            return LicensedIntegratorAdapter(base_url=base_url, api_key=token, pos_id=pos_id)
        raise ValueError(f"Unsupported FBR mode: {mode}")

    @classmethod
    def test_connection(
        cls,
        mode: str = "DEMO",
        tenant_settings: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Utility to probe connection and verification of an adapter configuration."""
        adapter = cls.get_adapter(mode=mode, tenant_settings=tenant_settings)
        return adapter.test_connection()
