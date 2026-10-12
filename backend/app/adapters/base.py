from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class FBRAdapterResponse:
    def __init__(
        self,
        success: bool,
        status: str, # "VALID", "INVALID", "FAILED", "PENDING"
        fbr_invoice_number: Optional[str] = None,
        fbr_reference: Optional[str] = None,
        qr_code_data: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        is_retryable: bool = False,
        raw_response: Optional[Dict[str, Any]] = None,
        environment: str = "DEMO",
        provider: str = "MOCK",
        is_simulated: bool = False,
    ):
        self.success = success
        self.status = status
        self.fbr_invoice_number = fbr_invoice_number
        self.fbr_reference = fbr_reference
        self.qr_code_data = qr_code_data
        self.error_code = error_code
        self.error_message = error_message
        self.is_retryable = is_retryable
        self.raw_response = raw_response or {}
        self.environment = environment
        self.provider = provider
        self.is_simulated = is_simulated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "fbr_invoice_number": self.fbr_invoice_number,
            "fbr_reference": self.fbr_reference,
            "qr_code_data": self.qr_code_data,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "is_retryable": self.is_retryable,
            "raw_response": self.raw_response,
            "environment": self.environment,
            "provider": self.provider,
            "is_simulated": self.is_simulated,
        }


class FBRAdapter(ABC):
    """
    Abstract FBR Digital Invoicing Adapter Interface.
    Decouples the SaaS invoice engine from specific integration routes
    (Mock, Sandbox, Licensed Integrator, PRAL).
    """

    @abstractmethod
    def validate_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payload against FBR schema and scenario rules"""
        pass

    @abstractmethod
    def submit_invoice(self, invoice_data: Dict[str, Any]) -> FBRAdapterResponse:
        """Submit invoice to FBR / Licensed Integrator API"""
        pass

    def submit_note(self, note_data: Dict[str, Any]) -> FBRAdapterResponse:
        """Submit a credit or debit note to FBR / Licensed Integrator API.
        Default delegates to submit_invoice with note document type.
        """
        return self.submit_invoice(note_data)

    def test_connection(self) -> Dict[str, Any]:
        """Probe the adapter endpoint to verify network, credentials, and latency."""
        return {
            "success": True,
            "status": "ONLINE",
            "latency_ms": 10,
            "message": "Adapter connection successful",
            "environment": getattr(self, "environment", "DEMO"),
            "provider": getattr(self, "provider", "MOCK"),
            "is_simulated": getattr(self, "is_simulated", True),
        }

    @abstractmethod
    def get_reference_data(self) -> Dict[str, Any]:
        """Fetch latest official reference data (HS codes, tax rates)"""
        pass

    @abstractmethod
    def parse_response(self, raw_response: Dict[str, Any]) -> FBRAdapterResponse:
        """Parse provider response into normalized internal representation"""
        pass

    @abstractmethod
    def get_status(self, submission_id: str) -> FBRAdapterResponse:
        """Poll or check status of a pending submission"""
        pass
