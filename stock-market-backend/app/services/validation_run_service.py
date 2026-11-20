from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.validation_run import ValidationRun
from app.models.signal_state import SignalStateHistory
from app.models.position_state import PositionStateRecord

class ValidationRunService:
    PHASE = "REAL_ANALYTICAL_VALIDATION"
    EXECUTION_MODE = "ANALYSIS_ONLY"
    BASE = Path(__file__).resolve().parents[1]
    BASELINE_FILES = (
        "analysis/opportunity_scorer.py", "analysis/support_resistance.py",
        "strategies/signal_lifecycle.py", "strategies/signal_rearm.py", "strategies/signal_staleness.py",
        "strategies/position_lifecycle.py", "strategies/position_opening_gate.py",
        "risk/position_sizer.py", "risk/risk_reward.py",
        "services/breakout_service.py", "services/setup_service.py", "services/multi_timeframe_service.py",
    )

    @classmethod
    def baseline(cls):
        files = {}
        for rel in cls.BASELINE_FILES:
            p = cls.BASE / rel
            files[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"
        manifest = {"phase": cls.PHASE, "execution_mode": cls.EXECUTION_MODE, "files": files}
        raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest(), raw

    @staticmethod
    def active(db: Session) -> ValidationRun | None:
        return db.scalar(select(ValidationRun).where(ValidationRun.status == "ACTIVE").order_by(ValidationRun.validation_run_id.desc()).limit(1))

    @classmethod
    def create(cls, db: Session, strategy_version: str):
        active = cls.active(db)
        if active is not None:
            raise ValueError(f"Validation run {active.validation_run_id} is already ACTIVE for {active.strategy_version}")
        h, manifest = cls.baseline()
        row = ValidationRun(strategy_version=strategy_version.strip(), validation_phase=cls.PHASE,
                            execution_mode=cls.EXECUTION_MODE, status="ACTIVE", baseline_hash=h,
                            baseline_manifest=manifest)
        db.add(row); db.commit(); db.refresh(row)
        return cls.serialize(row)

    @classmethod
    def baseline_status(cls, row: ValidationRun):
        h, _ = cls.baseline()
        if h == row.baseline_hash:
            return "MATCH", None
        return "BASELINE_MISMATCH", "Frozen strategy source differs from the baseline captured when this validation run started. Do not combine post-drift evidence with this run."

    @classmethod
    def serialize(cls, row: ValidationRun):
        status, note = cls.baseline_status(row)
        return {"validation_run_id": row.validation_run_id, "strategy_version": row.strategy_version,
                "validation_phase": row.validation_phase, "execution_mode": row.execution_mode,
                "status": row.status, "baseline_hash": row.baseline_hash, "baseline_status": status,
                "baseline_note": note, "started_at": row.started_at, "completed_at": row.completed_at,
                "broker_order_submitted": False}

    @classmethod
    def get(cls, db: Session, run_id: int):
        row = db.get(ValidationRun, run_id)
        if row is None: raise ValueError(f"Validation run not found: {run_id}")
        return cls.serialize(row)

    @classmethod
    def get_active(cls, db: Session):
        row = cls.active(db)
        if row is None: raise ValueError("No ACTIVE real analytical validation run")
        return cls.serialize(row)

    @classmethod
    def progress(cls, db: Session, run_id: int):
        row = db.get(ValidationRun, run_id)
        if row is None: raise ValueError(f"Validation run not found: {run_id}")
        bs, _ = cls.baseline_status(row)
        hist = list(db.scalars(select(SignalStateHistory).where(SignalStateHistory.validation_run_id == run_id)).all())
        positions = list(db.scalars(select(PositionStateRecord).where(PositionStateRecord.validation_run_id == run_id)).all())
        closed = [p for p in positions if p.closed_at is not None and p.exit_price is not None]
        wins = sum(float(p.exit_price) > float(p.entry_price) for p in closed)
        losses = sum(float(p.exit_price) < float(p.entry_price) for p in closed)
        return {"validation_run_id": run_id, "strategy_version": row.strategy_version, "status": row.status,
                "baseline_status": bs,
                "signals_observed": sum(h.to_state == "WATCHING" for h in hist),
                "breakouts_detected": sum(h.to_state in {"BREAKOUT_PENDING","FOLLOW_THROUGH_PENDING","ENTRY_CONFIRMED"} for h in hist),
                "follow_through_confirmed": sum(h.to_state in {"FOLLOW_THROUGH_PENDING","ENTRY_CONFIRMED"} for h in hist),
                "entries_confirmed": sum(h.to_state == "ENTRY_CONFIRMED" for h in hist),
                "positions_opened": len(positions), "positions_closed": len(closed),
                "wins": wins, "losses": losses, "breakeven": len(closed)-wins-losses,
                "execution_mode": cls.EXECUTION_MODE, "isolated_test_positions_included": False,
                "broker_order_submitted": False}

    @classmethod
    def complete(cls, db: Session, run_id: int):
        row = db.get(ValidationRun, run_id)
        if row is None: raise ValueError(f"Validation run not found: {run_id}")
        if row.status != "ACTIVE": raise ValueError(f"Validation run {run_id} is already {row.status}")
        row.status = "COMPLETED"; row.completed_at = datetime.now(timezone.utc)
        db.commit(); db.refresh(row); return cls.serialize(row)
