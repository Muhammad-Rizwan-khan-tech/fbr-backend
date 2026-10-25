from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from backend.app.api.routes.activation import get_fbr_connection_status
from backend.app.api.routes.fbr import get_fbr_status
from backend.app.schemas.license import FBRConnectionPublicStatusResponse
from backend.app.services.invoice_service import InvoiceService
from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.adapters.production_adapter import ProductionFBRAdapter
from backend.app.core.fbr_hs_code import normalize_hs_code, valid_hs_code

@pytest.mark.parametrize('taxid', ['1234567', '4130212327131'])
def test_public_endpoint_preserves_canonical_verified_status_for_ntn_and_cnic(taxid):
    now = datetime.now(timezone.utc)
    cred = SimpleNamespace(is_active=True, environment='SANDBOX', provider='SANDBOX', status='VERIFIED', last_success_at=now, last_tested_at=now, last_error=None, fbr_pos_id=None, get_auth_token=lambda:'fixture', get_api_key=lambda:None, to_masked_dict=lambda:{'masked_api_key':'***'})
    db=MagicMock();db.query.return_value.filter.return_value.first.return_value=cred
    tenant=SimpleNamespace(id='org', taxpayer=SimpleNamespace(ntn=taxid))
    canonical=SimpleNamespace(connection_status='VERIFIED',is_connected=True)
    with patch('backend.app.api.routes.fbr.get_fbr_status', return_value=canonical):
        result=FBRConnectionPublicStatusResponse(**get_fbr_connection_status(tenant=tenant,db=db))
    assert result.connection_status=='VERIFIED' and result.is_connected
    assert result.status=='VERIFIED'
    assert 'fixture' not in result.model_dump_json()

@pytest.mark.parametrize('adapter_class', [SandboxFBRAdapter, ProductionFBRAdapter])
@pytest.mark.parametrize('code', ['8471.30.10', '84713010', '8471.3010', '0101.21.00'])
def test_official_hs_format_preserves_digits(adapter_class,code):
    adapter=adapter_class(base_url='https://gw.fbr.gov.pk',bearer_token='fixture')
    item=adapter._transform_to_fbr_schema({'items':[{'hs_code':code,'quantity':1}]})['items'][0]
    assert valid_hs_code(item['hsCode'])
    assert item['hsCode']==normalize_hs_code(code)


def test_local_invoice_validation_uses_complete_submission_payload():
    db=MagicMock()
    invoice=SimpleNamespace(id='invoice',tenant_id='tenant',seller_ntn='1234567',buyer_name='Buyer',buyer_registration_type='Unregistered',invoice_type='Sale Invoice',reference_number=None,items=[SimpleNamespace(hs_code='8471.3010',quantity=1,unit_price=100)])
    payload={'sellerBusinessName':'Seller','sellerProvince':'Sindh','sellerAddress':'Seller address','buyerBusinessName':'Buyer','buyerProvince':'Sindh','buyerAddress':'Buyer address','items':[{'hsCode':'8471.3010'}]}
    adapter=MagicMock();adapter.validate_invoice.return_value={'errors':[],'warnings':[]}
    with patch('backend.app.services.invoice_service.FBRAdapterFactory.get_adapter_for_tenant',return_value=adapter),patch('backend.app.services.fbr_service.FBRService._build_fbr_payload',return_value=payload),patch.object(InvoiceService,'serialize_invoice_to_fbr_v112',return_value=payload):
        result=InvoiceService.validate_invoice(db,invoice)
    adapter.validate_invoice.assert_called_once_with(payload)
    assert result.is_valid

@pytest.mark.parametrize('mode,active,expiry,status,expected', [
    ('SANDBOX',True,None,'VERIFIED','VERIFIED'),
    ('PRODUCTION',True,None,'VERIFIED','CONFIGURED_NOT_VERIFIED'),
    ('SANDBOX',False,None,'VERIFIED','NOT_CONFIGURED'),
    ('DEMO',True,None,'VERIFIED','CONFIGURED_NOT_VERIFIED'),
    ('SANDBOX',True,datetime(2020,1,1),'VERIFIED','AUTHENTICATION_FAILED'),
    ('SANDBOX',True,None,'AUTH_FAILED','AUTHENTICATION_FAILED'),
])
def test_admin_desktop_connection_policy(mode,active,expiry,status,expected):
    from backend.app.core.fbr_connection import connection_status
    cred=SimpleNamespace(is_active=active,encrypted_auth_token='encrypted-fixture',encrypted_api_key=None,environment='SANDBOX',token_expires_at=expiry,status=status,last_success_at=datetime.now(timezone.utc))
    assert connection_status(cred,mode)==expected

def test_desktop_fallback_origins_are_bounded():
    from backend.app.core.config import Settings
    config=Settings(_env_file=None,CORS_ORIGINS='https://client.example')
    assert 'http://localhost:5174' in config.BACKEND_CORS_ORIGINS
    assert 'http://127.0.0.1:8081' in config.BACKEND_CORS_ORIGINS
    assert 'https://client.example' in config.BACKEND_CORS_ORIGINS
    assert 'http://localhost:9999' not in config.BACKEND_CORS_ORIGINS
    assert '*' not in config.BACKEND_CORS_ORIGINS
