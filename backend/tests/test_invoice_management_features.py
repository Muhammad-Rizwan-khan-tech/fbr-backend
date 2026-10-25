from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, Invoice, InvoiceItem, Taxpayer, Branch, Customer, InvoiceSubmissionJob, AuditLog, HSCode
from backend.app.schemas.invoice import InvoiceUpdate
from backend.app.services.invoice_management import update_invoice, remove_invoice, load_mutable
from backend.app.services.pdf_service import pdf_generator

@pytest.fixture
def case():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    db.add_all([Taxpayer(tenant_id='t',legal_name='Seller',ntn='1234567',address='Office',city='Karachi',province='Sindh'),Branch(id='b',tenant_id='t',branch_name='Main',branch_code='01',address='Office',city='Karachi',province='Sindh'),Customer(id='c',tenant_id='t',name='Buyer',address='Market',city='Karachi',province='Sindh')])
    inv=Invoice(id='i',tenant_id='t',branch_id='b',customer_id='c',invoice_number='INV-TEST',invoice_date=datetime(2026,10,25),seller_name='Seller',seller_ntn='1234567',seller_branch_code='01',seller_province='Sindh',buyer_name='Buyer',buyer_address='Missing',buyer_province='Sindh',status='FAILED',fbr_status='FAILED',fbr_error_message='Old error')
    inv.items=[InvoiceItem(item_code='A',description='Test product',hs_code='8471.3000',quantity=1,unit_price=100,tax_rate=0,uom='NOS',gross_amount=100,taxable_amount=100,tax_amount=0,line_total=100)]
    db.add(inv);db.commit()
    yield db,inv,SimpleNamespace(id=None,email='test@example.invalid')
    db.close();engine.dispose()

def test_edit_recalculates_preserves_zero_and_clears_failed(case):
    db,inv,user=case
    data=InvoiceUpdate(buyer_address='Correct market',items=[dict(item_code='A',description='Laptop',hs_code='8471.3000',quantity=2,unit_price=150,discount=10,tax_rate=0,extra_tax=5)])
    updated=update_invoice(db,'t','i',data,user)
    assert updated.buyer_address=='Correct market'
    assert updated.grand_total==Decimal('295.00')
    assert updated.items[0].tax_rate==0
    assert (updated.status,updated.fbr_status,updated.fbr_error_message)==('DRAFT','NOT_SUBMITTED',None)
    assert db.query(AuditLog).filter_by(action='INVOICE_EDIT').count()==1

@pytest.mark.parametrize('attribute,value',[('status','VALID'),('fbr_status','VALID'),('fbr_invoice_number','official-reference'),('status','QUEUED'),('status','VALIDATING')])
def test_accepted_and_inflight_cannot_edit_or_remove(case,attribute,value):
    db,inv,user=case;setattr(inv,attribute,value);db.commit()
    for delete in (False,True):
        with pytest.raises(HTTPException) as err:load_mutable(db,'t','i',delete)
        assert err.value.status_code in (400,409)

def test_active_job_blocks_mutation(case):
    db,inv,user=case
    db.add(InvoiceSubmissionJob(tenant_id='t',invoice_id='i',environment='SANDBOX',provider='SANDBOX',correlation_id='test',status='PROCESSING'));db.commit()
    with pytest.raises(HTTPException) as err:remove_invoice(db,'t','i',user)
    assert err.value.status_code==409

def test_tenant_isolation_and_removal_retains_history(case):
    db,inv,user=case
    with pytest.raises(HTTPException) as err:load_mutable(db,'other','i')
    assert err.value.status_code==404
    remove_invoice(db,'t','i',user)
    assert db.get(Invoice,'i').status=='DELETED'
    assert db.query(InvoiceItem).count()==1
    assert db.query(AuditLog).filter_by(action='INVOICE_REMOVE').count()==1
    with pytest.raises(HTTPException):load_mutable(db,'t','i')

def test_pdf_pagination_headers_and_no_false_acceptance(case):
    import fitz
    db,inv,user=case
    template=inv.items[0]
    inv.items=[InvoiceItem(item_code='A',description='Long product description '*8,hs_code='8471.3000',quantity=1,unit_price=100,tax_rate=0,uom='NOS',gross_amount=100,taxable_amount=100,tax_amount=0,line_total=100,item_seq=i+1) for i in range(45)]
    data=pdf_generator.generate(inv,hs_descriptions={'8471.3000':'Portable digital processing machines'})
    pdf=fitz.open(stream=data,filetype='pdf')
    assert len(pdf)>1
    for i,page in enumerate(pdf):
        text=page.get_text()
        assert 'HS Code' in text and 'Sales Value' in text and 'Petroleum' in text
        assert f'Page {i+1} of {len(pdf)}' in text
    assert 'DRAFT / NOT FBR ACCEPTED' in pdf[0].get_text()
    assert 'QR: FBR response data' not in ''.join(p.get_text() for p in pdf)
    from pathlib import Path
    Path('/tmp/fbr_feature_preview.pdf').write_bytes(data)

def test_hs_search_description_code_and_offline(case,monkeypatch):
    from backend.app.api.routes.hs_search import search_hs_codes,pral_reference_service
    db,inv,user=case
    db.add(HSCode(code='8471.3000',description='Portable computers',chapter='84',is_active=True));db.commit()
    monkeypatch.setattr(pral_reference_service,'fetch_item_codes_envelope',AsyncMock(side_effect=RuntimeError('offline')))
    for term in ('portable','84713'):
        rows=asyncio.run(search_hs_codes(search=term,q='',limit=20,tenant=SimpleNamespace(id='t'),db=db))
        assert rows[0]['hs_code']=='8471.3000'
        assert rows[0]['default_rate'] is None
        assert rows[0]['official_live_verified'] is False

def test_print_endpoint_memory_pdf_and_tenant_scope(case):
    from backend.app.api.routes.documents import printable_invoice_pdf
    db,inv,user=case
    response=printable_invoice_pdf('i',tenant=SimpleNamespace(id='t'),current_user=user,db=db)
    assert response.media_type=='application/pdf'
    assert response.body.startswith(b'%PDF')
    assert response.headers['cache-control']=='private, no-store'
    with pytest.raises(HTTPException) as error:
        printable_invoice_pdf('i',tenant=SimpleNamespace(id='other'),current_user=user,db=db)
    assert error.value.status_code==404
    remove_invoice(db,'t','i',user)
    with pytest.raises(HTTPException):printable_invoice_pdf('i',tenant=SimpleNamespace(id='t'),current_user=user,db=db)


def test_hs_official_catalog_provenance_without_invented_defaults(case,monkeypatch):
    from backend.app.api.routes.hs_search import search_hs_codes,pral_reference_service
    db,inv,user=case
    env=SimpleNamespace(data=[{'hS_CODE':'8471.30.00','description':'Portable computers'}],source='PRAL_LIVE',official_live_verified=True,stale=False)
    monkeypatch.setattr(pral_reference_service,'fetch_item_codes_envelope',AsyncMock(return_value=env))
    rows=asyncio.run(search_hs_codes(search='84713',q='',limit=20,tenant=SimpleNamespace(id='t'),db=db))
    assert rows[0]['source']=='PRAL_LIVE' and rows[0]['official_live_verified'] is True
    assert rows[0]['hs_code']=='8471.3000' and rows[0]['default_rate'] is None and rows[0]['default_uom'] is None
