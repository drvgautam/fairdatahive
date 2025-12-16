from __future__ import annotations

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    *,
    user_sub: str,
    type: str,
    message: str,
    resource_version_id: str | None = None,
    related_id: str | None = None,
    commit: bool = False,
) -> Notification:
    n = Notification(
        user_sub=user_sub,
        type=type,
        message=message,
        resource_version_id=resource_version_id,
        related_id=related_id,
    )
    db.add(n)
    if commit:
        await db.commit()
        await db.refresh(n)
    else:
        await db.flush()
    return n


async def list_for_user(
    db: AsyncSession,
    user_sub: str,
    *,
    unread_only: bool = False,
    limit: int = 100,
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_sub == user_sub)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    return list((await db.execute(stmt)).scalars().all())


async def mark_read(
    db: AsyncSession, notification_id: int, user_sub: str
) -> Notification | None:
    n = await db.get(Notification, notification_id)
    if n is None or n.user_sub != user_sub:
        return None
    n.read = True
    await db.commit()
    return n


async def mark_all_read(db: AsyncSession, user_sub: str) -> int:
    stmt = (
        update(Notification)
        .where(Notification.user_sub == user_sub)
        .where(Notification.read.is_(False))
        .values(read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return int(result.rowcount or 0)


async def deliver_email(to_email: str, subject: str, body: str) -> bool:
    if not settings.smtp_host:
        return False
    try:
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = settings.email_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=True,
        )
        return True
    except Exception as exc:  # pragma: no cover - SMTP failures non-fatal
        logger.warning("Email send failed: %s", exc)
        return False
