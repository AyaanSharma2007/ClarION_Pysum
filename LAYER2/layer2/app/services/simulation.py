"""
Layer 6 — SimPy Simulation Engine (Bible §10, Phase C).

Discrete-event Monte Carlo simulation for portfolio-level RFI forecasting.
Models the NCA/RFI ecosystem stochastically to forecast:
  - Expected RFI volume over a time horizon
  - SLA breach probabilities per MSC
  - Bottleneck identification (which MSCs/categories are most overloaded)
  - Confidence intervals on all estimates

All outputs are probabilistic forecasts — never phrased as certainty (Bible §5).
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import simpy

logger = logging.getLogger(__name__)


# ─── Configuration ────────────────────────────────────────────────────────────

# Default MSC profiles calibrated to Novo Nordisk's submission mix
# (Bible §14.1 — synthetic data mirroring real-world proportions)
DEFAULT_MSC_PROFILES = [
    {"country": "Germany", "rfi_rate_per_day": 0.35, "avg_cycle_days": 8.5, "cycle_std": 2.0},
    {"country": "France", "rfi_rate_per_day": 0.28, "avg_cycle_days": 9.0, "cycle_std": 2.5},
    {"country": "Spain", "rfi_rate_per_day": 0.22, "avg_cycle_days": 7.5, "cycle_std": 1.8},
    {"country": "Italy", "rfi_rate_per_day": 0.20, "avg_cycle_days": 8.0, "cycle_std": 2.2},
    {"country": "Netherlands", "rfi_rate_per_day": 0.18, "avg_cycle_days": 7.0, "cycle_std": 1.5},
    {"country": "Poland", "rfi_rate_per_day": 0.15, "avg_cycle_days": 9.5, "cycle_std": 3.0},
    {"country": "Belgium", "rfi_rate_per_day": 0.12, "avg_cycle_days": 7.8, "cycle_std": 1.8},
    {"country": "Sweden", "rfi_rate_per_day": 0.10, "avg_cycle_days": 6.5, "cycle_std": 1.2},
    {"country": "Denmark", "rfi_rate_per_day": 0.09, "avg_cycle_days": 6.0, "cycle_std": 1.0},
    {"country": "Austria", "rfi_rate_per_day": 0.08, "avg_cycle_days": 7.2, "cycle_std": 1.5},
]

RFI_CATEGORIES = [
    "statistics",
    "quality_impd",
    "clinical_protocol",
    "safety_pharmacovigilance",
    "regulatory_admin",
]

# Category distribution (probability of each category for a generated RFI)
CATEGORY_DISTRIBUTION = {
    "statistics": 0.28,
    "quality_impd": 0.22,
    "clinical_protocol": 0.20,
    "safety_pharmacovigilance": 0.18,
    "regulatory_admin": 0.12,
}


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class SimulatedRFI:
    """A single RFI event generated during simulation."""
    rfi_id: int
    msc: str
    category: str
    arrival_day: float
    cycle_time: float
    sla_deadline: float = 10.0  # default validation SLA
    breached: bool = False

    @property
    def completion_day(self) -> float:
        return self.arrival_day + self.cycle_time


@dataclass
class SimulationResult:
    """Aggregated results from a single Monte Carlo run."""
    total_rfis: int = 0
    sla_breaches: int = 0
    rfis_per_msc: dict = field(default_factory=dict)
    breaches_per_msc: dict = field(default_factory=dict)
    rfis_per_category: dict = field(default_factory=dict)
    avg_cycle_time: float = 0.0
    max_cycle_time: float = 0.0


# ─── SimPy Process ────────────────────────────────────────────────────────────

def _rfi_arrival_process(
    env: simpy.Environment,
    msc_profile: dict,
    rng: np.random.Generator,
    results: list[SimulatedRFI],
    sla_days: float,
    rfi_counter: list[int],
):
    """
    SimPy generator process: models RFI arrivals for a single MSC.
    RFIs arrive according to a Poisson process (exponential inter-arrival times).
    Cycle times are drawn from a truncated normal distribution.
    """
    country = msc_profile["country"]
    rate = msc_profile["rfi_rate_per_day"]
    avg_cycle = msc_profile["avg_cycle_days"]
    cycle_std = msc_profile["cycle_std"]

    categories = list(CATEGORY_DISTRIBUTION.keys())
    cat_probs = list(CATEGORY_DISTRIBUTION.values())

    while True:
        # Exponential inter-arrival time (Poisson process)
        inter_arrival = rng.exponential(1.0 / rate) if rate > 0 else 365.0
        yield env.timeout(inter_arrival)

        # Generate cycle time (truncated normal, min 1 day)
        cycle_time = max(1.0, rng.normal(avg_cycle, cycle_std))

        # Assign category
        category = rng.choice(categories, p=cat_probs)

        rfi_counter[0] += 1
        rfi = SimulatedRFI(
            rfi_id=rfi_counter[0],
            msc=country,
            category=category,
            arrival_day=env.now,
            cycle_time=cycle_time,
            sla_deadline=sla_days,
            breached=cycle_time > sla_days,
        )
        results.append(rfi)


# ─── Simulation Engine ───────────────────────────────────────────────────────

class SimulationEngine:
    """
    Discrete-event Monte Carlo simulation engine.

    Runs multiple independent simulation instances with different random seeds,
    then aggregates results to produce confidence intervals and statistical
    summaries.
    """

    def __init__(
        self,
        msc_profiles: list[dict] | None = None,
        sla_days: float = 10.0,
    ):
        self.msc_profiles = msc_profiles or DEFAULT_MSC_PROFILES
        self.sla_days = sla_days

    def _run_single(
        self,
        horizon_days: int,
        seed: int,
    ) -> SimulationResult:
        """Run a single simulation instance."""
        env = simpy.Environment()
        rng = np.random.default_rng(seed)
        all_rfis: list[SimulatedRFI] = []
        rfi_counter = [0]

        # Start an arrival process for each MSC
        for profile in self.msc_profiles:
            env.process(
                _rfi_arrival_process(
                    env, profile, rng, all_rfis, self.sla_days, rfi_counter
                )
            )

        # Run simulation
        env.run(until=horizon_days)

        # Aggregate results
        result = SimulationResult()
        result.total_rfis = len(all_rfis)
        result.sla_breaches = sum(1 for r in all_rfis if r.breached)

        for rfi in all_rfis:
            result.rfis_per_msc[rfi.msc] = result.rfis_per_msc.get(rfi.msc, 0) + 1
            result.rfis_per_category[rfi.category] = result.rfis_per_category.get(rfi.category, 0) + 1
            if rfi.breached:
                result.breaches_per_msc[rfi.msc] = result.breaches_per_msc.get(rfi.msc, 0) + 1

        cycle_times = [r.cycle_time for r in all_rfis]
        if cycle_times:
            result.avg_cycle_time = round(statistics.mean(cycle_times), 2)
            result.max_cycle_time = round(max(cycle_times), 2)

        return result

    def run_simulation(
        self,
        n_runs: int = 100,
        horizon_days: int = 90,
        base_seed: int = 42,
    ) -> dict[str, Any]:
        """
        Run a Monte Carlo simulation with n_runs independent instances.

        Returns aggregated statistics with confidence intervals.
        All outputs are probabilistic forecasts — never certainty.
        """
        logger.info(
            "Starting Monte Carlo simulation: %d runs, %d-day horizon, %d MSCs",
            n_runs, horizon_days, len(self.msc_profiles),
        )

        run_results: list[SimulationResult] = []
        for i in range(n_runs):
            result = self._run_single(horizon_days, seed=base_seed + i)
            run_results.append(result)

        # Aggregate across all runs
        total_rfis_list = [r.total_rfis for r in run_results]
        breach_counts = [r.sla_breaches for r in run_results]
        breach_rates = [
            r.sla_breaches / r.total_rfis if r.total_rfis > 0 else 0.0
            for r in run_results
        ]
        avg_cycles = [r.avg_cycle_time for r in run_results]

        # Per-MSC aggregation
        all_mscs = set()
        for r in run_results:
            all_mscs.update(r.rfis_per_msc.keys())

        msc_stats = {}
        for msc in sorted(all_mscs):
            msc_rfis = [r.rfis_per_msc.get(msc, 0) for r in run_results]
            msc_breaches = [r.breaches_per_msc.get(msc, 0) for r in run_results]
            msc_breach_rates = [
                b / t if t > 0 else 0.0
                for b, t in zip(msc_breaches, msc_rfis)
            ]
            msc_stats[msc] = {
                "avg_rfis": round(statistics.mean(msc_rfis), 1),
                "avg_breaches": round(statistics.mean(msc_breaches), 1),
                "breach_rate_mean": round(statistics.mean(msc_breach_rates), 4),
                "breach_rate_p95": round(sorted(msc_breach_rates)[int(0.95 * len(msc_breach_rates))], 4),
            }

        # Per-category aggregation
        all_cats = set()
        for r in run_results:
            all_cats.update(r.rfis_per_category.keys())

        category_stats = {}
        for cat in sorted(all_cats):
            cat_rfis = [r.rfis_per_category.get(cat, 0) for r in run_results]
            category_stats[cat] = {
                "avg_rfis": round(statistics.mean(cat_rfis), 1),
                "std_rfis": round(statistics.stdev(cat_rfis), 1) if len(cat_rfis) > 1 else 0,
            }

        # Identify bottleneck MSCs (highest breach rate)
        bottleneck_mscs = sorted(
            msc_stats.items(),
            key=lambda x: x[1]["breach_rate_mean"],
            reverse=True,
        )[:3]

        output = {
            "simulation_parameters": {
                "n_runs": n_runs,
                "horizon_days": horizon_days,
                "sla_days": self.sla_days,
                "n_mscs": len(self.msc_profiles),
            },
            "portfolio_forecast": {
                "total_rfis_mean": round(statistics.mean(total_rfis_list), 1),
                "total_rfis_std": round(statistics.stdev(total_rfis_list), 1) if len(total_rfis_list) > 1 else 0,
                "total_rfis_p5": sorted(total_rfis_list)[int(0.05 * len(total_rfis_list))],
                "total_rfis_p95": sorted(total_rfis_list)[int(0.95 * len(total_rfis_list))],
                "sla_breach_rate_mean": round(statistics.mean(breach_rates), 4),
                "sla_breach_rate_p95": round(sorted(breach_rates)[int(0.95 * len(breach_rates))], 4),
                "avg_cycle_time_mean": round(statistics.mean(avg_cycles), 2),
            },
            "msc_breakdown": msc_stats,
            "category_breakdown": category_stats,
            "bottleneck_mscs": [
                {"country": msc, "breach_rate": stats["breach_rate_mean"]}
                for msc, stats in bottleneck_mscs
            ],
            "disclaimer": (
                "These are probabilistic Monte Carlo forecasts based on synthetic calibration data. "
                "They estimate likelihood, not certainty. Real-world RFI volumes and timings will vary "
                "based on actual submission patterns, NCA workload, and regulatory changes. "
                "See Clarion Bible §5 (Decision Table) and §14.1 (Synthetic Data)."
            ),
        }

        logger.info(
            "Simulation complete: mean %.0f RFIs over %d days, mean breach rate %.1f%%",
            output["portfolio_forecast"]["total_rfis_mean"],
            horizon_days,
            output["portfolio_forecast"]["sla_breach_rate_mean"] * 100,
        )

        return output


# Module-level singleton
simulation_engine = SimulationEngine()
