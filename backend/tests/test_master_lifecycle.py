from types import SimpleNamespace
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.models import Base, Organization, Product, Customer, Invoice, InvoiceItem, Branch, AuditLog
from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.api.routes.products import router as products
from backend.app.api.routes.customers import router as customers

@pytest.fixture
def case():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def fk(conn,_):conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    db.add(Organization(id='t',name='Test',slug='test-master'));db.commit()
    app=FastAPI();app.include_router(products);app.include_router(customers)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_tenant]=lambda:SimpleNamespace(id='t')
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id=None,email='qa@example.invalid')
    with TestClient(app) as client:yield db,client
    db.close();engine.dispose()

def add_product(client,code='P-1'):
    response=client.post('/products',json={'item_code':code,'name':'Laptop','hs_code':'8471.30.10','unit_price':'100','tax_rate':'0','uom':'NOS','sale_type':'STANDARD'})
    assert response.status_code==200,response.text
    return response.json()

def add_customer(client):
    response=client.post('/customers',json={'name':'Buyer','ntn':'1234567','address':'Original address','city':'Karachi','province':'Sindh'})
    assert response.status_code==200,response.text
    return response.json()

def linked_invoice(db,product,customer):
    branch=Branch(id='b',tenant_id='t',branch_name='Main',branch_code='01',address='Office',city='Karachi',province='Sindh')
    db.add(branch);db.commit()
    inv=Invoice(id='inv',tenant_id='t',branch_id='b',customer_id=customer['id'],invoice_number='INV-1',seller_name='Seller',seller_ntn='1234567',seller_branch_code='01',seller_province='Sindh',buyer_name='Buyer',buyer_address='Original address',buyer_province='Sindh',status='VALID',fbr_status='VALID',fbr_invoice_number='accepted-reference',grand_total=100)
    inv.items=[InvoiceItem(product_id=product['id'],item_code='P-1',description='Original laptop',hs_code='8471.3010',quantity=1,unit_price=100,tax_rate=0,gross_amount=100,taxable_amount=100,tax_amount=0,line_total=100)]
    db.add(inv);db.commit();return inv

def test_product_create_patch_duplicate_and_unused_delete(case):
    db,client=case;p=add_product(client)
    assert p['hs_code']=='8471.3010' and Decimal(p['tax_rate'])==0
    changed=client.patch('/products/'+p['id'],json={'unit_price':125,'description':'Updated','item_code':'abc'})
    assert changed.status_code==200 and Decimal(changed.json()['unit_price'])==125
    assert changed.json()['item_code']=='ABC'
    other=add_product(client,'OTHER')
    assert client.patch('/products/'+other['id'],json={'item_code':'abc'}).status_code==409
    response=client.delete('/products/'+p['id'])
    assert response.status_code==200 and response.json()['action']=='DELETED'
    assert db.get(Product,p['id']) is None
    assert db.query(AuditLog).filter_by(action='UPDATE_PRODUCT').count()==1
    assert db.query(AuditLog).filter_by(action='DELETE_PRODUCT').count()==1

def test_customer_create_patch_clear_ids_and_unused_delete(case):
    db,client=case;c=add_customer(client)
    response=client.patch('/customers/'+c['id'],json={'address':'New address','ntn':None,'cnic':'4210112345671','buyer_type':'B2C','buyer_reference':'REF','phone':'03000000000'})
    assert response.status_code==200,response.text
    assert response.json()['ntn'] is None and response.json()['cnic']=='4210112345671'
    assert response.json()['address']=='New address'
    response=client.delete('/customers/'+c['id']);assert response.json()['action']=='DELETED'
    assert db.get(Customer,c['id']) is None
    assert db.query(AuditLog).filter_by(action='DELETE_CUSTOMER').count()==1

def test_referenced_masters_archive_preserve_accepted_invoice_and_restore(case):
    db,client=case;p=add_product(client);c=add_customer(client);inv=linked_invoice(db,p,c)
    assert client.patch('/products/'+p['id'],json={'unit_price':999,'description':'New product'}).status_code==200
    assert client.patch('/customers/'+c['id'],json={'address':'Changed master address'}).status_code==200
    for route,record,model in [('products',p,Product),('customers',c,Customer)]:
        response=client.delete('/'+route+'/'+record['id']);assert response.status_code==200,response.text
        assert response.json()['action']=='ARCHIVED' and db.get(model,record['id']).is_active is False
        assert client.get('/'+route+'?is_active=true').json()==[]
        assert len(client.get('/'+route+'?is_active=false').json())==1
        assert client.patch('/'+route+'/'+record['id'],json={'is_active':True}).status_code==200
        assert len(client.get('/'+route+'?is_active=true').json())==1
    db.refresh(inv)
    assert inv.status=='VALID' and inv.fbr_invoice_number=='accepted-reference' and inv.buyer_address=='Original address'
    assert inv.items[0].description=='Original laptop' and inv.items[0].unit_price==100

@pytest.mark.parametrize('route,kind',[('products',Product),('customers',Customer)])
def test_cross_tenant_update_delete_404(case,route,kind):
    db,client=case;record=add_product(client) if kind is Product else add_customer(client)
    row=db.get(kind,record['id']);row.tenant_id='other';db.commit()
    assert client.patch('/'+route+'/'+record['id'],json={'name':'Changed'}).status_code==404
    assert client.delete('/'+route+'/'+record['id']).status_code==404
    assert db.get(kind,record['id']).name==record['name']

@pytest.mark.parametrize('payload',[{'name':None},{'name':'  '},{'unit_price':-1},{'tax_rate':-1},{'hs_code':'wrong'},{'unit_price':'10000000000'},{'name':'x'*256}])
def test_invalid_product_edits_are_rejected_without_mutation(case,payload):
    db,client=case;p=add_product(client)
    assert client.patch('/products/'+p['id'],json=payload).status_code==422
    db.expire_all();assert db.get(Product,p['id']).name=='Laptop'

def test_invalid_customer_required_fields(case):
    db,client=case;c=add_customer(client)
    assert client.patch('/customers/'+c['id'],json={'address':None}).status_code==422
    assert client.patch('/customers/'+c['id'],json={'city':'  '}).status_code==422
