from fastapi import APIRouter

from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.organization import router as organization_router
from backend.app.api.routes.branches import router as branches_router
from backend.app.api.routes.customers import router as customers_router
from backend.app.api.routes.products import router as products_router
from backend.app.api.routes.taxes import router as taxes_router
from backend.app.api.routes.invoices import router as invoices_router
from backend.app.api.routes.fbr import router as fbr_router
from backend.app.api.routes.notes import router as notes_router
from backend.app.api.routes.reports import router as reports_router
from backend.app.api.routes.audit import router as audit_router
from backend.app.api.routes.documents import router as documents_router
from backend.app.api.routes.notifications import router as notifications_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.developer import router as developer_router
from backend.app.api.routes.webhooks import router as webhooks_router
from backend.app.api.routes.external_invoices import router as external_invoices_router
from backend.app.api.routes.activation import router as activation_router
from backend.app.api.routes.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(activation_router)
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(organization_router)
api_router.include_router(branches_router)
api_router.include_router(customers_router)
api_router.include_router(products_router)
api_router.include_router(taxes_router)
api_router.include_router(invoices_router)
api_router.include_router(fbr_router)
api_router.include_router(notes_router)
api_router.include_router(reports_router)
api_router.include_router(audit_router)
api_router.include_router(documents_router)
api_router.include_router(notifications_router)
api_router.include_router(health_router)
api_router.include_router(developer_router)
api_router.include_router(webhooks_router)
api_router.include_router(external_invoices_router)


