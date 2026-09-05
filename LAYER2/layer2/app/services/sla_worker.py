"""
Layer 6 — SLA Background Worker.

Periodically queries open RFIs to check for SLA breaches. If an RFI's
sla_due_at has passed and it is not in the 'submitted' stage, the worker
logs an SLA breach audit event.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from LAYER2.layer2.app.database import AsyncSessionLocal
from LAYER2.layer2.app.models.audit import AuditLog, WorkflowState
from LAYER2.layer2.app.models.rfi import RFI
from LAYER2.layer2.app.utils.audit import compute_hash

logger = logging.getLogger(__name__)


class SLAWorker:
    def __init__(self, check_interval_seconds: int = 3600):
        self.check_interval_seconds = check_interval_seconds
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def start(self):
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run_loop())
            logger.info("SLA worker started (interval=%ss)", self.check_interval_seconds)

    async def stop(self):
        if self._task:
            logger.info("Stopping SLA worker...")
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None

    async def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                await self.check_slas()
            except Exception as e:
                logger.error("SLA worker error during check: %s", e)
            
            # Wait for the interval, but allow early wake-up for shutdown
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.check_interval_seconds)
            except asyncio.TimeoutError:
                pass  # Timeout means it's time for the next check

    async def check_slas(self):
        """Query for breached SLAs and log audit events."""
        now = datetime.now(tz=timezone.utc)
        
        async with AsyncSessionLocal() as db:
            # Find workflow states where sla_due_at < now and it hasn't been flagged yet
            stmt = (
                select(WorkflowState)
                .join(RFI)
                .options(selectinload(WorkflowState.rfi).selectinload(RFI.audit_logs))
                .where(WorkflowState.sla_due_at < now)
                .where(WorkflowState.current_stage != "submitted")
            )
            result = await db.execute(stmt)
            states = result.scalars().all()

            for state in states:
                rfi = state.rfi
                
                # Check if we already logged a breach to avoid spamming
                already_breached = any(log.action == "sla_breached" for log in rfi.audit_logs)
                if already_breached:
                    continue
                
                logger.warning("SLA Breach detected for RFI: %s (due: %s)", rfi.rfi_id, state.sla_due_at)
                
                last_hash = rfi.audit_logs[-1].curr_hash if rfi.audit_logs else None
                audit_data = {
                    "action": "sla_breached",
                    "actor": "system",
                    "metadata": {
                        "sla_due_at": state.sla_due_at.isoformat() if state.sla_due_at else None,
                        "breached_at": now.isoformat(),
                        "current_stage": state.current_stage,
                    },
                    "created_at": now.isoformat(),
                }
                curr_hash = compute_hash(last_hash, audit_data)
                audit = AuditLog(
                    rfi_id=rfi.id,
                    action="sla_breached",
                    actor="system",
                    prev_hash=last_hash,
                    curr_hash=curr_hash,
                    metadata_=audit_data,
                )
                db.add(audit)
            
            await db.commit()


# Singleton
sla_worker = SLAWorker(check_interval_seconds=60)  # Check every minute for demo/testing
