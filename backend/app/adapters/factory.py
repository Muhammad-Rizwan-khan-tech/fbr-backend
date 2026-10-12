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
        if credential is not None:
            provider = getattr(credential, "provider", None) or getattr(credential, "environment", "MOCK")
            pos_id = getattr(credential, "fbr_pos_id", None) or getattr(settings, "FBR_DEFAULT_POS_ID", "10001")
            base_url = getattr(credential, "base_url", None) or settings.FBR_API_URL or None
            
            # Decrypt secrets if method exists
            api_key = credential.get_api_key() if hasattr(credential, "get_api_key") else None
            auth_token = credential.get_auth_token() if hasattr(credential, "get_auth_token") else None
            client_id = credential.get_client_id() if hasattr(credential, "get_client_id") else None
            client_secret = credential.get_client_secret() if hasattr(credential, "get_client_secret") else None
            
            token = auth_token or api_key

            prov_upper = provider.upper()
            if prov_upper in ("DEMO", "MOCK"):
                return MockFBRAdapter(forced_scenario=forced_scenario)
            elif prov_upper == "SANDBOX":
                return SandboxFBRAdapter(
                    base_url=base_url,
                    bearer_token=token,
                    pos_id=pos_id,
                    forced_scenario=forced_scenario,
                )
            elif prov_upper == "PRODUCTION":
                return ProductionFBRAdapter(
                    base_url=base_url,
                    bearer_token=token,
                    pos_id=pos_id,
                    client_id=client_id or settings.FBR_CLIENT_ID,
                    client_secret=client_secret or settings.FBR_CLIENT_SECRET,
                )
            elif prov_upper in ("LICENSED_INTEGRATOR", "INTEGRATOR", "PRAL"):
                return LicensedIntegratorAdapter(
                    base_url=base_url,
                    api_key=token,
                    pos_id=pos_id,
                )
        
        mode = getattr(tenant_settings, "fbr_mode", "DEMO") if tenant_settings else "DEMO"
        return cls.get_adapter(mode=mode, tenant_settings=tenant_settings, forced_scenario=forced_scenario)

    @classmethod
    def test_connection(
        cls,
        mode: str = "DEMO",
        tenant_settings: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Utility to probe connection and verification of an adapter configuration."""
        adapter = cls.get_adapter(mode=mode, tenant_settings=tenant_settings)
        return adapter.test_connection()
