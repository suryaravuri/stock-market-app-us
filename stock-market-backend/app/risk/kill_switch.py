from dataclasses import dataclass


@dataclass
class KillSwitchResult:
    allowed: bool
    reason: str | None


def check_kill_switch(
    trading_enabled: bool,
    paper_trading_enabled: bool,
    live_trading_enabled: bool,
    mode: str,
) -> KillSwitchResult:

    mode = mode.strip().upper()

    if not trading_enabled:
        return KillSwitchResult(
            allowed=False,
            reason="Trading is globally disabled",
        )

    if mode == "PAPER":
        if not paper_trading_enabled:
            return KillSwitchResult(
                allowed=False,
                reason="Paper trading is disabled",
            )

        return KillSwitchResult(
            allowed=True,
            reason=None,
        )

    if mode == "LIVE":
        if not live_trading_enabled:
            return KillSwitchResult(
                allowed=False,
                reason="Live trading is disabled",
            )

        return KillSwitchResult(
            allowed=True,
            reason=None,
        )

    return KillSwitchResult(
        allowed=False,
        reason=f"Unsupported trading mode '{mode}'",
    )