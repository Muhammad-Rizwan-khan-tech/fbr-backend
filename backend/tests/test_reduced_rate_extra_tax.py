from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch
import pytest
from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.adapters.production_adapter import ProductionFBRAdapter
from backend.app.core.fbr_extra_tax import is_reduced_rate
from backend.app.core.pral_error_codes import lookup_pral_error


def payload(sale_type='Goods at Reduced Rate', extra=0):
    return {'invoiceType':'Sale Invoice','invoiceDate':'2026-10-26','sellerNTNCNIC':'1234567','sellerBusinessName':'Seller','sellerProvince':'Sindh','sellerAddress':'Seller office','buyerNTNCNIC':'7654321','buyerBusinessName':'Buyer','buyerProvince':'Sindh','buyerAddress':'Buyer market','buyerRegistrationType':'Registered','scenarioId':'SN028','items':[{'hsCode':'8504.4010','productDescription':'UPS','rate':'1%','uoM':'Numbers, pieces, units','quantity':1,'totalValues':101,'valueSalesExcludingST':100,'fixedNotifiedValueOrRetailPrice':0,'salesTaxApplicable':1,'salesTaxWithheldAtSource':0,'extraTax':extra,'furtherTax':0,'fedPayable':0,'discount':0,'saleType':sale_type,'sroScheduleNo':'EIGHTH SCHEDULE Table 1','sroItemSerialNo':'81'}]}

@pytest.mark.parametrize('adapter_type',[SandboxFBRAdapter,ProductionFBRAdapter])
@pytest.mark.parametrize('extra',[0,0.0,Decimal('0.00'),'',None])
def test_reduced_zero_is_omitted_and_transform_is_idempotent(adapter_type,extra):
    adapter=adapter_type(bearer_token='test-fixture-not-real')
    original=payload(extra=extra);before=deepcopy(original)
    wire=adapter._transform_to_fbr_schema(original)
    assert 'extraTax' not in wire['items'][0]
    assert adapter._transform_to_fbr_schema(wire)==wire
    assert original==before
    assert wire['items'][0]['totalValues']==101 and wire['items'][0]['salesTaxApplicable']==1
    assert wire['items'][0]['furtherTax']==0 and wire['items'][0]['sroItemSerialNo']=='81'
    assert adapter.validate_invoice(original)['is_valid']

@pytest.mark.parametrize('adapter_type',[SandboxFBRAdapter,ProductionFBRAdapter])
@pytest.mark.parametrize('extra',[5,Decimal('0.004')])
def test_positive_extra_tax_is_blocked_before_any_http_call(adapter_type,extra):
    adapter=adapter_type(bearer_token='test-fixture-not-real')
    data=payload(extra=extra)
    validation=adapter.validate_invoice(data)
    assert not validation['is_valid'] and any('[0091]' in err for err in validation['errors'])
    with patch('httpx.Client') as client,patch('httpx.post') as post:
        response=adapter.submit_invoice(data)
    assert not response.success and response.status=='INVALID'
    client.assert_not_called();post.assert_not_called()
    assert data['items'][0]['extraTax']==extra

@pytest.mark.parametrize('adapter_type',[SandboxFBRAdapter,ProductionFBRAdapter])
@pytest.mark.parametrize('sale_type,extra',[('Goods at standard rate (default)',0),('Goods at standard rate (default)',5),('Goods at zero-rate',0),('Exempt goods',0)])
def test_other_sale_types_keep_existing_numeric_extra_tax(adapter_type,sale_type,extra):
    wire=adapter_type(bearer_token='test-fixture-not-real')._transform_to_fbr_schema(payload(sale_type,extra))
    assert wire['items'][0]['extraTax']==extra

@pytest.mark.parametrize('name',['Goods at Reduced Rate',' goods at reduced rate ','REDUCED_RATE','REDUCED','Retailers selling goods at reduced rate'])
def test_reduced_rate_names(name):assert is_reduced_rate(name)


def test_mixed_lines_use_their_own_sale_type():
    data=payload();standard=deepcopy(data['items'][0]);standard.update(saleType='Goods at standard rate (default)',extraTax=5,rate='18%');data['items'].append(standard)
    items=SandboxFBRAdapter()._transform_to_fbr_schema(data)['items']
    assert 'extraTax' not in items[0] and items[1]['extraTax']==5
    assert lookup_pral_error('0091').related_field=='extraTax'

from backend.tests.test_invoice_management_features import case

def test_persisted_and_unsaved_preview_share_correct_wire_and_local_guard(case):
    from backend.app.services.invoice_service import InvoiceService
    from backend.app.schemas.invoice import InvoiceCreate
    db,inv,user=case
    inv.scenario_id='SN028';inv.items[0].sale_type='Goods at Reduced Rate';inv.items[0].tax_rate=1;inv.items[0].extra_tax=0
    db.commit()
    wire=InvoiceService.serialize_invoice_to_fbr_v112(db,inv,environment='SANDBOX')
    assert 'extraTax' not in wire['items'][0]
    def draft(extra):return InvoiceCreate(branch_id='b',customer_id='c',scenario_id='SN028',items=[dict(item_code='UPS',description='UPS',hs_code='8504.4010',quantity=1,unit_price=100,tax_rate=1,sale_type='Goods at Reduced Rate',extra_tax=extra)])
    wire=InvoiceService.serialize_draft_to_fbr_v112(db,'t',draft(0),environment='SANDBOX')
    assert 'extraTax' not in wire['items'][0]
    result=InvoiceService.validate_draft_invoice(db,'t',draft(5))
    assert not result.is_valid and any('[0091]' in e for e in result.errors)
