import hashlib
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.config import settings
from backend.app.core.crypto import generate_activation_secret, hash_activation_secret, generate_device_token
from backend.app.core.security import create_access_token
from backend.app.models.base import now_utc
from backend.app.models.tenant import Organization, OrgStatus
from backend.app.models.user import User, UserRole
from backend.app.models.license import License, LicenseStatus, ActivationKey, ActivationKeyStatus
from backend.app.models.device import DeviceInstallation, DeviceStatus
from backend.app.models.session import DeviceSession
from backend.app.models.admin_audit import AdminAuditLog
from backend.app.core.errors import AppError


def _is_past(dt: Optional[datetime]) -> bool:
    """Safe comparison handling both naive (SQLite) and timezone-aware (PostgreSQL) datetimes."""
    if not dt:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < now_utc()


class LicenseService:
    @staticmethod
    def create_permanent_license_for_org(
        db: Session,
        organization: Organization,
        max_devices: int = 5,
        issued_by: str = "SUPER_ADMIN",
    ) -> Tuple[License, str]:
        """Creates a permanent license (no expiration) and generates a one-time activation secret."""
        # Build clean license reference (e.g. LIC-ABC-PERM-3B7A8C)
        slug_prefix = "".join(c for c in organization.slug.upper() if c.isalnum())[:4] or "CORP"
        random_suffix = generate_device_token()[:6].upper()
        license_number = f"LIC-{slug_prefix}-PERM-{random_suffix}"

        license_obj = License(
            organization_id=organization.id,
            license_number=license_number,
            license_type="PERMANENT",
            status=LicenseStatus.ACTIVE.value,
            max_devices=max_devices,
            issued_at=now_utc(),
            issued_by=issued_by,
        )
        db.add(license_obj)
        db.flush()

        # Generate one-time activation secret
        raw_secret = generate_activation_secret()
        key_hash = hash_activation_secret(raw_secret)
        expires_at = now_utc() + timedelta(days=settings.ACTIVATION_KEY_EXPIRY_DAYS)

        act_key = ActivationKey(
            license_id=license_obj.id,
            organization_id=organization.id,
            key_hash=key_hash,
            key_prefix=raw_secret[:12],
            status=ActivationKeyStatus.PENDING.value,
            expires_at=expires_at,
            created_by=issued_by,
        )
        db.add(act_key)
        db.flush()

        # Log admin audit
        audit = AdminAuditLog(
            admin_identity=issued_by,
            action="LICENSE_ISSUED",
            target_type="LICENSE",
            target_id=license_obj.id,
            details=f"Issued permanent license {license_number} with max_devices={max_devices}",
        )
        db.add(audit)
        db.commit()

        return license_obj, raw_secret

    @staticmethod
    def reissue_activation_key(
        db: Session,
        organization_id: str,
        admin_identity: str = "SUPER_ADMIN",
        reason: Optional[str] = None,
    ) -> Tuple[License, str]:
        """Revokes any pending activation keys and issues a fresh one-time activation secret."""
        license_obj = db.query(License).filter(
            License.organization_id == organization_id,
            License.status == LicenseStatus.ACTIVE.value,
        ).first()

        if not license_obj:
            raise AppError("No active permanent license found for this organization", status_code=404, code="LICENSE_NOT_FOUND")

        # Invalidate any previously unredeemed activation keys
        pending_keys = db.query(ActivationKey).filter(
            ActivationKey.license_id == license_obj.id,
            ActivationKey.status == ActivationKeyStatus.PENDING.value,
        ).all()
        for k in pending_keys:
            k.status = ActivationKeyStatus.REVOKED.value

        # Generate new secret
        raw_secret = generate_activation_secret()
        key_hash = hash_activation_secret(raw_secret)
        expires_at = now_utc() + timedelta(days=settings.ACTIVATION_KEY_EXPIRY_DAYS)

        new_key = ActivationKey(
            license_id=license_obj.id,
            organization_id=organization_id,
            key_hash=key_hash,
            key_prefix=raw_secret[:12],
            status=ActivationKeyStatus.PENDING.value,
            expires_at=expires_at,
            created_by=admin_identity,
        )
        db.add(new_key)

        audit = AdminAuditLog(
            admin_identity=admin_identity,
            action="ACTIVATION_KEY_REISSUED",
            target_type="ORGANIZATION",
            target_id=organization_id,
            details=f"Reissued activation key for license {license_obj.license_number}. Reason: {reason or 'Not specified'}",
        )
        db.add(audit)
        db.commit()

        return license_obj, raw_secret

    @staticmethod
    def redeem_activation_key(
        db: Session,
        activation_key: str,
        device_fingerprint: str,
        device_name: str = "Windows Terminal",
        os_info: str = "Windows",
        app_version: str = "1.0.0",
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically validates and redeems an activation key, binding the desktop device to the organization."""
        key_hash = hash_activation_secret(activation_key)

        act_key = db.query(ActivationKey).filter(ActivationKey.key_hash == key_hash).first()
        if not act_key:
            raise AppError("Invalid activation key. Please verify your secret.", status_code=400, code="INVALID_ACTIVATION_KEY")

        if act_key.status == ActivationKeyStatus.REDEEMED.value:
            raise AppError("This activation key has already been redeemed.", status_code=400, code="KEY_ALREADY_REDEEMED")

        if act_key.status == ActivationKeyStatus.REVOKED.value:
            raise AppError("This activation key has been revoked by the administrator.", status_code=403, code="KEY_REVOKED")

        if _is_past(act_key.expires_at):
            act_key.status = ActivationKeyStatus.EXPIRED.value
            db.commit()
            raise AppError("This activation key has expired. Please contact your platform administrator.", status_code=400, code="KEY_EXPIRED")

        # Verify organization
        org = db.query(Organization).filter(Organization.id == act_key.organization_id).first()
        if not org or org.status == OrgStatus.SUSPENDED.value or not org.is_active:
            raise AppError("This customer organization has been suspended or deactivated.", status_code=403, code="ORG_SUSPENDED")

        # Verify permanent license
        license_obj = db.query(License).filter(License.id == act_key.license_id).first()
        if not license_obj or license_obj.status != LicenseStatus.ACTIVE.value:
            raise AppError("This organization's permanent license is revoked or inactive.", status_code=403, code="LICENSE_REVOKED")

        # Check device authorization and limits
        fp_hash = hashlib.sha256(device_fingerprint.strip().encode("utf-8")).hexdigest()
        existing_device = db.query(DeviceInstallation).filter(
            DeviceInstallation.organization_id == org.id,
            DeviceInstallation.device_fingerprint == fp_hash,
        ).first()

        if existing_device:
            if existing_device.status == DeviceStatus.REVOKED.value:
                raise AppError("This device has been explicitly revoked by the administrator.", status_code=403, code="DEVICE_REVOKED")
            device = existing_device
            device.device_name = device_name
            device.os_info = os_info
            device.app_version = app_version
            device.ip_address = ip_address
            device.last_seen_at = now_utc()
        else:
            # Check maximum device count
            active_devices_count = db.query(func.count(DeviceInstallation.id)).filter(
                DeviceInstallation.organization_id == org.id,
                DeviceInstallation.status == DeviceStatus.ACTIVE.value,
            ).scalar() or 0

            if active_devices_count >= license_obj.max_devices:
                raise AppError(
                    f"Activation limit reached ({active_devices_count}/{license_obj.max_devices} devices). Revoke an existing device from admin panel to activate a new terminal.",
                    status_code=403,
                    code="DEVICE_LIMIT_EXCEEDED",
                )

            device = DeviceInstallation(
                organization_id=org.id,
                license_id=license_obj.id,
                device_fingerprint=fp_hash,
                device_name=device_name,
                os_info=os_info,
                app_version=app_version,
                ip_address=ip_address,
                status=DeviceStatus.ACTIVE.value,
                activated_at=now_utc(),
                last_seen_at=now_utc(),
            )
            db.add(device)
            db.flush()

        # Mark key as REDEEMED
        act_key.status = ActivationKeyStatus.REDEEMED.value
        act_key.redeemed_at = now_utc()
        act_key.redeemed_device_id = device.id

        # Find or pick the organization admin user
        user = db.query(User).filter(
            User.tenant_id == org.id,
            User.is_active == True,
        ).first()

        if not user:
            raise AppError("No active user account found for this organization.", status_code=500, code="NO_ACTIVE_USER")

        # Generate Access Token & Refresh Token
        access_token = create_access_token(
            subject=user.id,
            tenant_id=org.id,
            role=user.role,
        )

        raw_refresh_token = generate_device_token()
        refresh_hash = hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()
        session_expires = now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # Invalidate old sessions for this specific device
        db.query(DeviceSession).filter(DeviceSession.device_id == device.id).update({"is_revoked": True})

        session = DeviceSession(
            device_id=device.id,
            user_id=user.id,
            organization_id=org.id,
            refresh_token_hash=refresh_hash,
            expires_at=session_expires,
            is_revoked=False,
        )
        db.add(session)
        db.commit()

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh_token,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "device_id": device.id,
            "organization": {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "status": org.status,
            },
            "license": {
                "id": license_obj.id,
                "license_number": license_obj.license_number,
                "license_type": license_obj.license_type,
                "status": license_obj.status,
                "max_devices": license_obj.max_devices,
                "issued_at": license_obj.issued_at,
                "is_valid": True,
            },
            "user": {
                "id": user.id,
                "username": user.username or user.email,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
            },
        }

    @staticmethod
    def refresh_session(
        db: Session,
        refresh_token: str,
        device_fingerprint: str,
    ) -> Dict[str, Any]:
        """Refreshes an authenticated desktop session with token rotation and device validity check."""
        refresh_hash = hashlib.sha256(refresh_token.strip().encode("utf-8")).hexdigest()
        session = db.query(DeviceSession).filter(
            DeviceSession.refresh_token_hash == refresh_hash,
            DeviceSession.is_revoked == False,
        ).first()

        if not session:
            raise AppError("Invalid or expired session. Please re-activate.", status_code=401, code="INVALID_SESSION")

        if _is_past(session.expires_at):
            session.is_revoked = True
            db.commit()
            raise AppError("Session expired. Please log in again.", status_code=401, code="SESSION_EXPIRED")

        # Verify device
        device = db.query(DeviceInstallation).filter(DeviceInstallation.id == session.device_id).first()
        fp_hash = hashlib.sha256(device_fingerprint.strip().encode("utf-8")).hexdigest()
        if not device or device.device_fingerprint != fp_hash or device.status == DeviceStatus.REVOKED.value:
            session.is_revoked = True
            db.commit()
            raise AppError("Device authorization revoked or mismatch.", status_code=403, code="DEVICE_REVOKED")

        # Verify organization & license
        org = db.query(Organization).filter(Organization.id == session.organization_id).first()
        if not org or org.status == OrgStatus.SUSPENDED.value or not org.is_active:
            session.is_revoked = True
            db.commit()
            raise AppError("Organization access is suspended.", status_code=403, code="ORG_SUSPENDED")

        license_obj = db.query(License).filter(
            License.organization_id == org.id,
            License.status == LicenseStatus.ACTIVE.value,
        ).first()
        if not license_obj:
            session.is_revoked = True
            db.commit()
            raise AppError("Permanent license revoked.", status_code=403, code="LICENSE_REVOKED")

        user = db.query(User).filter(User.id == session.user_id).first()
        if not user or not user.is_active:
            session.is_revoked = True
            db.commit()
            raise AppError("User account inactive.", status_code=403, code="USER_INACTIVE")

        # Rotate refresh token
        session.is_revoked = True  # Old token consumed
        new_refresh = generate_device_token()
        new_hash = hashlib.sha256(new_refresh.encode("utf-8")).hexdigest()

        new_session = DeviceSession(
            device_id=device.id,
            user_id=user.id,
            organization_id=org.id,
            refresh_token_hash=new_hash,
            expires_at=now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
        )
        db.add(new_session)

        # Update device last seen
        device.last_seen_at = now_utc()

        # Issue new access token
        new_access = create_access_token(
            subject=user.id,
            tenant_id=org.id,
            role=user.role,
        )
        db.commit()

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    @staticmethod
    def get_license_status(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Returns the real-time permanent license status for an organization."""
        org = db.query(Organization).filter(Organization.id == tenant_id).first()
        if not org:
            raise AppError("Organization not found", status_code=404, code="ORG_NOT_FOUND")

        license_obj = db.query(License).filter(
            License.organization_id == tenant_id,
        ).order_by(License.created_at.desc()).first()

        is_valid = bool(
            org.status == OrgStatus.ACTIVE.value and
            org.is_active and
            license_obj and
            license_obj.status == LicenseStatus.ACTIVE.value
        )

        fbr_mode = org.settings.fbr_mode if org.settings else "DEMO"

        return {
            "license_number": license_obj.license_number if license_obj else "NONE",
            "license_type": license_obj.license_type if license_obj else "NONE",
            "status": license_obj.status if license_obj else "NOT_FOUND",
            "is_valid": is_valid,
            "organization_id": org.id,
            "organization_name": org.name,
            "fbr_mode": fbr_mode,
            "message": "Permanent license active and in good standing." if is_valid else "License revoked or suspended.",
        }
