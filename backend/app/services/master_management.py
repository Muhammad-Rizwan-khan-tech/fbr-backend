"""Tenant-scoped product/buyer removal preserving invoice snapshots and audit."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from backend.app.models.invoice import Invoice, InvoiceItem
from backend.app.models.product import Product
from backend.app.services.audit_service import AuditService
from backend.app.core.fbr_hs_code import normalize_hs_code, valid_hs_code


def validate_changes(changes, required, entity):
    for key in required:
        if key in changes and (changes[key] is None or (isinstance(changes[key], str) and not changes[key].strip())):
            raise HTTPException(422, f'{key} cannot be empty')
    for key, value in changes.items():
        if isinstance(value, str):
            changes[key] = value.strip()
    limits = {'name':255, 'item_code':100, 'hs_code':20, 'uom':20, 'sale_type':50, 'sro_reference':100, 'ntn':20, 'strn':30, 'cnic':20, 'registration_type':50, 'buyer_type':50, 'province':100, 'city':100, 'phone':50, 'email':255, 'buyer_reference':100, 'postal_code':20, 'country':100}
    for key, maximum in limits.items():
        if isinstance(changes.get(key), str) and len(changes[key]) > maximum:
            raise HTTPException(422, f'{key} must be at most {maximum} characters')
    if 'country' in changes and not changes['country']:
        raise HTTPException(422, 'country cannot be empty')
    if entity == 'Product':
        if 'item_code' in changes:
            changes['item_code'] = changes['item_code'].upper()
        if 'hs_code' in changes:
            if not valid_hs_code(changes['hs_code']):
                raise HTTPException(422, 'A valid 8-digit Pakistan HS code is required')
            changes['hs_code'] = normalize_hs_code(changes['hs_code'])
        for key in ('unit_price', 'tax_rate'):
            if key in changes:
                value = Decimal(str(changes[key]))
                if not value.is_finite() or value < 0 or value > (Decimal('999.99') if key == 'tax_rate' else Decimal('9999999999.99')):
                    raise HTTPException(422, f'{key} must be a finite non-negative number within the supported range')
    return changes


def remove_master(db, tenant_id, record_id, model, user):
    entity = model.__name__
    record = db.query(model).filter(model.id == record_id, model.tenant_id == tenant_id).with_for_update().first()
    if not record:
        raise HTTPException(404, f'{entity} not found')
    before = {'name': record.name, 'is_active': record.is_active}
    if model is Product:
        before['item_code'] = record.item_code
        linked = db.query(InvoiceItem.id).filter(InvoiceItem.product_id == record_id).first() is not None
    else:
        before.update(ntn=record.ntn, cnic=record.cnic)
        linked = db.query(Invoice.id).filter(Invoice.customer_id == record_id).first() is not None
    def archive(row):
        row.is_active = False
        row.updated_by = user.id
    action = 'ARCHIVED' if linked else 'DELETED'
    if linked:
        archive(record)
    else:
        db.delete(record)
    def log():
        AuditService.log(db=db, tenant_id=tenant_id, action=f'DELETE_{entity.upper()}', entity=entity, entity_id=record_id, user_id=user.id, user_email=user.email, before_state=before, after_state={'action': action, **before, 'is_active': False}, commit=False)
    try:
        log()
        db.commit()
    except IntegrityError:
        # A concurrent invoice may have acquired a reference after our check.
        db.rollback()
        record = db.query(model).filter(model.id == record_id, model.tenant_id == tenant_id).with_for_update().first()
        if not record:
            raise HTTPException(409, 'Record changed during removal. Refresh and try again')
        archive(record)
        action = 'ARCHIVED'
        log()
        db.commit()
    noun = 'Product' if model is Product else 'Buyer'
    message = f'{noun} is linked to invoices. It has been archived and hidden from active lists.' if action == 'ARCHIVED' else f'{noun} successfully removed.'
    return {'success': True, 'message': message, 'action': action}
