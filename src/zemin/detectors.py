from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, median

from .geo import haversine_m
from .schema import AuditConfig, Finding, GeoObservation, Severity, SiteSummary


def _solve_linear_system(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Solve small dense linear system Ax = b via Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        div = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= div
        for r in range(n):
            if r != col:
                factor = m[r][col]
                for j in range(col, n + 1):
                    m[r][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


def _invert_matrix(a: list[list[float]]) -> list[list[float]] | None:
    n = len(a)
    inv_cols: list[list[float]] = []
    for i in range(n):
        e = [1.0 if j == i else 0.0 for j in range(n)]
        col = _solve_linear_system(a, e)
        if col is None:
            return None
        inv_cols.append(col)
    return [[inv_cols[j][i] for j in range(n)] for i in range(n)]


def _ols_fit(xs: list[list[float]], ys: list[float]) -> tuple[list[float], list[float], list[float]] | None:
    """Return (beta, residuals, se_beta) for ordinary least squares."""
    n = len(ys)
    p = len(xs[0]) if xs else 0
    if n <= p + 1:
        return None
    xtx = [[sum(xs[k][i] * xs[k][j] for k in range(n)) for j in range(p)] for i in range(p)]
    xty = [sum(xs[k][i] * ys[k] for k in range(n)) for i in range(p)]
    beta = _solve_linear_system(xtx, xty)
    if beta is None:
        return None
    resid = [ys[k] - sum(xs[k][j] * beta[j] for j in range(p)) for k in range(n)]
    rss = sum(r * r for r in resid)
    sigma2 = rss / max(1, n - p)
    xtx_inv = _invert_matrix(xtx)
    if xtx_inv is None:
        return None
    se = [math.sqrt(max(0.0, sigma2 * xtx_inv[j][j])) for j in range(p)]
    return beta, resid, se


def _times_in_years(series: list[GeoObservation]) -> list[float]:
    t0 = series[0].timestamp
    return [(o.timestamp - t0).total_seconds() / (365.25 * 86400.0) for o in series]


def _kendall_tau(vals: list[float]) -> float:
    n = len(vals)
    if n < 4:
        return 0.0
    concordant = 0
    discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            diff = vals[j] - vals[i]
            if diff > 1e-12:
                concordant += 1
            elif diff < -1e-12:
                discordant += 1
    denom = concordant + discordant
    return (concordant - discordant) / denom if denom > 0 else 0.0


def group_by_site(observations: list[GeoObservation]) -> dict[str, list[GeoObservation]]:
    grouped: dict[str, list[GeoObservation]] = defaultdict(list)
    for o in observations:
        grouped[o.site_id].append(o)
    for sid in grouped:
        grouped[sid].sort(key=lambda x: x.timestamp)
    return dict(sorted(grouped.items()))


def summarize_sites(grouped: dict[str, list[GeoObservation]]) -> list[SiteSummary]:
    summaries: list[SiteSummary] = []
    for sid, series in grouped.items():
        ts = _times_in_years(series)
        ys = [o.displacement_mm for o in series]
        span = ts[-1] - ts[0] if len(ts) >= 2 else 0.0
        vel = 0.0
        acc = 0.0
        if len(ts) >= 3 and span > 1e-4:
            lin = _ols_fit([[1.0, t] for t in ts], ys)
            if lin is not None:
                vel = lin[0][1]
        if len(ts) >= 6 and span > 0.25:
            quad = _ols_fit([[1.0, t, 0.5 * t * t] for t in ts], ys)
            if quad is not None:
                acc = quad[0][2]
        cohs = [o.coherence for o in series if o.coherence is not None]
        summaries.append(
            SiteSummary(
                site_id=sid,
                lat=mean(o.lat for o in series),
                lon=mean(o.lon for o in series),
                epoch_count=len(series),
                span_years=span,
                velocity_mm_yr=vel,
                acceleration_mm_yr2=acc,
                cumulative_mm=ys[-1] - ys[0] if len(ys) >= 2 else 0.0,
                mean_coherence=mean(cohs) if cohs else None,
            )
        )
    return summaries


def detect_subsidence_velocity(summaries: list[SiteSummary], cfg: AuditConfig) -> list[Finding]:
    sinking = [s for s in summaries if s.velocity_mm_yr <= -cfg.velocity_warn_mm_yr]
    if not sinking:
        return []
    worst = min(sinking, key=lambda s: s.velocity_mm_yr)
    rate = abs(worst.velocity_mm_yr)
    severity = Severity.CRITICAL if rate >= cfg.velocity_crit_mm_yr else Severity.WARNING
    return [
        Finding(
            code="SUBSIDENCE_VELOCITY_HAZARD",
            title="High-rate vertical land subsidence",
            severity=severity,
            site_id=worst.site_id,
            metric_value=round(worst.velocity_mm_yr, 2),
            metric_unit="mm/yr",
            summary=(
                f"{len(sinking)}/{len(summaries)} monitoring point(s) exceed {cfg.velocity_warn_mm_yr:.0f} mm/yr "
                f"subsidence; worst site '{worst.site_id}' sinks at {worst.velocity_mm_yr:.1f} mm/yr "
                f"(cumulative {worst.cumulative_mm:.1f} mm over {worst.span_years:.2f} yr)."
            ),
            evidence={
                "worst_site": worst.site_id,
                "worst_velocity_mm_yr": round(worst.velocity_mm_yr, 2),
                "affected_sites": [s.site_id for s in sinking],
                "mean_affected_velocity_mm_yr": round(mean(s.velocity_mm_yr for s in sinking), 2),
            },
        )
    ]


def detect_subsidence_acceleration(
    grouped: dict[str, list[GeoObservation]],
    cfg: AuditConfig,
) -> list[Finding]:
    worst_hit: tuple[str, float, float, float] | None = None
    for sid, series in grouped.items():
        ts = _times_in_years(series)
        if len(ts) < 10 or ts[-1] < 0.75:
            continue
        ys = [o.displacement_mm for o in series]
        xs = [
            [
                1.0,
                t,
                0.5 * t * t,
                math.cos(2.0 * math.pi * t),
                math.sin(2.0 * math.pi * t),
                t * math.cos(2.0 * math.pi * t),
                t * math.sin(2.0 * math.pi * t),
            ]
            for t in ts
        ]
        fit = _ols_fit(xs, ys)
        if fit is None:
            continue
        beta, _, se = fit
        acc = beta[2]
        tstat = abs(acc) / max(se[2], 1e-9)
        if acc <= -cfg.accel_warn_mm_yr2 and tstat >= cfg.accel_min_tstat:
            if worst_hit is None or acc < worst_hit[1]:
                worst_hit = (sid, acc, tstat, beta[1])

    if worst_hit is None:
        return []
    sid, acc, tstat, v0 = worst_hit
    severity = Severity.CRITICAL if abs(acc) >= cfg.accel_crit_mm_yr2 else Severity.WARNING
    return [
        Finding(
            code="SUBSIDENCE_ACCELERATION",
            title="Accelerating ground subsidence (non-linear downward curvature)",
            severity=severity,
            site_id=sid,
            metric_value=round(acc, 2),
            metric_unit="mm/yr^2",
            summary=(
                f"Site '{sid}' exhibits statistically significant downward acceleration of "
                f"{acc:.1f} mm/yr^2 (t={tstat:.1f}), indicating intensifying compaction rather than steady creep."
            ),
            evidence={
                "site_id": sid,
                "acceleration_mm_yr2": round(acc, 2),
                "initial_velocity_mm_yr": round(v0, 2),
                "t_statistic": round(tstat, 2),
            },
        )
    ]


def detect_aquifer_rebound_failure(
    grouped: dict[str, list[GeoObservation]],
    cfg: AuditConfig,
) -> list[Finding]:
    """Detect collapse of wet-season elastic aquifer rebound (inelastic clay compaction regime)."""
    worst: tuple[str, float, float, float, float] | None = None
    for sid, series in grouped.items():
        ts = _times_in_years(series)
        if len(ts) < 24 or ts[-1] < 1.5:
            continue
        ys = [o.displacement_mm for o in series]
        mid = len(ts) // 2

        def _fit_harm(sub_t: list[float], sub_y: list[float]) -> tuple[float, float] | None:
            xs = [[1.0, t, math.cos(2.0 * math.pi * t), math.sin(2.0 * math.pi * t)] for t in sub_t]
            f = _ols_fit(xs, sub_y)
            if f is None:
                return None
            b = f[0]
            return b[1], math.hypot(b[2], b[3])

        full = _fit_harm(ts, ys)
        h1 = _fit_harm(ts[:mid], ys[:mid])
        h2 = _fit_harm(ts[mid:], ys[mid:])
        if full is None or h1 is None or h2 is None:
            continue

        vel, _ = full
        _, amp1 = h1
        _, amp2 = h2

        step_deltas = [ys[i] - ys[i - 1] for i in range(1, len(ys))]
        smoothed_deltas = [sum(step_deltas[i : i + 3]) for i in range(0, max(1, len(step_deltas) - 2), 3)]
        total_up = sum(d for d in smoothed_deltas if d > 0)
        total_down = sum(-d for d in smoothed_deltas if d < 0)
        rebound_ratio = total_up / max(total_down, 1e-6)
        amp_decay = (amp1 - amp2) / max(amp1, 0.5)

        if vel <= -15.0 and (rebound_ratio < cfg.rebound_ratio_min or amp_decay >= cfg.rebound_decay_warn):
            if worst is None or rebound_ratio < worst[1]:
                worst = (sid, rebound_ratio, amp_decay, amp1, amp2)

    if worst is None:
        return []
    sid, ratio, decay, amp1, amp2 = worst
    severity = Severity.CRITICAL if ratio < 0.10 or decay >= 0.50 else Severity.WARNING
    return [
        Finding(
            code="AQUIFER_REBOUND_FAILURE",
            title="Seasonal aquifer elastic rebound failure (inelastic compaction)",
            severity=severity,
            site_id=sid,
            metric_value=round(ratio, 3),
            metric_unit="rebound_ratio",
            summary=(
                f"Site '{sid}' lost seasonal elastic uplift: wet-season recovery ratio dropped to "
                f"{ratio * 100:.1f}% (seasonal amplitude {amp1:.1f} mm -> {amp2:.1f} mm, decay {decay * 100:.0f}%), "
                f"consistent with permanent clay aquitard compaction."
            ),
            evidence={
                "site_id": sid,
                "elastic_rebound_ratio": round(ratio, 3),
                "early_seasonal_amp_mm": round(amp1, 2),
                "late_seasonal_amp_mm": round(amp2, 2),
                "amplitude_decay_fraction": round(decay, 3),
            },
        )
    ]


def detect_critical_slowing_down(
    grouped: dict[str, list[GeoObservation]],
    cfg: AuditConfig,
) -> list[Finding]:
    """Track rolling Ornstein-Uhlenbeck recovery rate lambda(t) and variance on detrended residuals."""
    best: tuple[str, float, float, float, float, float] | None = None
    win = cfg.csd_window_epochs

    for sid, series in grouped.items():
        ts = _times_in_years(series)
        if len(ts) < win + 12:
            continue
        ys = [o.displacement_mm for o in series]
        xs = [
            [
                1.0,
                t,
                0.5 * t * t,
                math.cos(2.0 * math.pi * t),
                math.sin(2.0 * math.pi * t),
                t * math.cos(2.0 * math.pi * t),
                t * math.sin(2.0 * math.pi * t),
            ]
            for t in ts
        ]
        fit = _ols_fit(xs, ys)
        if fit is None:
            continue
        resid = fit[1]

        dts = [ts[i] - ts[i - 1] for i in range(1, len(ts)) if ts[i] > ts[i - 1]]
        dt_yr = median(dts) if dts else (12.0 / 365.25)

        lambdas: list[float] = []
        variances: list[float] = []
        phis: list[float] = []

        for start in range(0, len(resid) - win + 1, 2):
            seg = resid[start : start + win]
            m_seg = mean(seg)
            centered = [x - m_seg for x in seg]
            var_seg = sum(x * x for x in centered) / max(1, len(centered) - 1)
            if var_seg < 1e-9:
                continue
            num = sum(centered[i] * centered[i - 1] for i in range(1, len(centered)))
            den = sum(centered[i - 1] ** 2 for i in range(1, len(centered)))
            raw_phi = num / max(den, 1e-12)
            # Marriott-Pope small-sample OU AR(1) bias correction
            corr_phi = raw_phi + (1.0 + 3.0 * raw_phi) / len(seg)
            clamped_phi = max(0.02, min(0.995, corr_phi))
            lam = -math.log(clamped_phi) / max(dt_yr, 1e-4)
            lambdas.append(lam)
            variances.append(var_seg)
            phis.append(clamped_phi)

        if len(lambdas) < 8:
            continue

        tau_lam = _kendall_tau(lambdas)
        tau_var = _kendall_tau(variances)
        early_phi = mean(phis[:3])
        final_phi = mean(phis[-3:])
        early_var = mean(variances[:3])
        final_var = mean(variances[-3:])
        delta_phi = final_phi - early_phi
        var_ratio = final_var / max(early_var, 1e-9)

        if (
            tau_lam <= cfg.csd_lambda_tau_limit
            and tau_var >= cfg.csd_var_tau_limit
            and final_phi >= cfg.csd_final_phi_min
            and delta_phi >= cfg.csd_delta_phi_min
            and var_ratio >= cfg.csd_var_ratio_min
        ):
            if best is None or tau_lam < best[1]:
                best = (sid, tau_lam, tau_var, final_phi, lambdas[-1], var_ratio)

    if best is None:
        return []
    sid, tau_lam, tau_var, final_phi, end_lam, var_ratio = best
    severity = Severity.CRITICAL if tau_lam <= -0.55 and final_phi >= 0.70 else Severity.WARNING
    return [
        Finding(
            code="CRITICAL_SLOWING_DOWN",
            title="Ornstein-Uhlenbeck critical slowing down (declining recovery rate)",
            severity=severity,
            site_id=sid,
            metric_value=round(tau_lam, 3),
            metric_unit="kendall_tau",
            summary=(
                f"Detrended residuals at '{sid}' show declining OU recovery rate "
                f"(Kendall tau={tau_lam:.2f}, final AR(1) phi={final_phi:.2f}, "
                f"variance ratio={var_ratio:.1f}x, tau_var={tau_var:+.2f}), signaling loss of dynamical resilience."
            ),
            evidence={
                "site_id": sid,
                "lambda_kendall_tau": round(tau_lam, 3),
                "variance_kendall_tau": round(tau_var, 3),
                "variance_ratio_late_to_early": round(var_ratio, 2),
                "final_ar1_phi": round(final_phi, 3),
                "final_recovery_rate_per_yr": round(end_lam, 2),
            },
        )
    ]


def compute_max_angular_distortion(
    summaries: list[SiteSummary],
    cfg: AuditConfig,
) -> tuple[float, dict[str, object]]:
    max_beta = 0.0
    worst_pair: dict[str, object] = {}
    for i in range(len(summaries)):
        for j in range(i + 1, len(summaries)):
            a, b = summaries[i], summaries[j]
            dist_m = haversine_m(a.lat, a.lon, b.lat, b.lon)
            if dist_m < cfg.tilt_min_baseline_m or dist_m > cfg.tilt_max_baseline_m:
                continue
            delta_s_m = abs(a.cumulative_mm - b.cumulative_mm) / 1000.0
            beta = delta_s_m / dist_m
            if beta > max_beta:
                max_beta = beta
                worst_pair = {
                    "site_a": a.site_id,
                    "site_b": b.site_id,
                    "baseline_m": round(dist_m, 1),
                    "differential_settlement_mm": round(abs(a.cumulative_mm - b.cumulative_mm), 1),
                    "differential_rate_mm_yr": round(abs(a.velocity_mm_yr - b.velocity_mm_yr), 1),
                    "angular_distortion": round(beta, 6),
                    "angular_distortion_ratio": f"1/{int(round(1.0 / beta))}" if beta > 1e-6 else "0",
                }
    return max_beta, worst_pair


def detect_differential_settlement(
    summaries: list[SiteSummary],
    cfg: AuditConfig,
) -> tuple[float, list[Finding]]:
    max_beta, pair = compute_max_angular_distortion(summaries, cfg)
    if max_beta < cfg.tilt_warn_ratio or not pair:
        return max_beta, []

    severity = Severity.CRITICAL if max_beta >= cfg.tilt_crit_ratio else Severity.WARNING
    inv = int(round(1.0 / max_beta))
    return max_beta, [
        Finding(
            code="DIFFERENTIAL_SETTLEMENT_TILT",
            title="Structural differential settlement / angular distortion risk",
            severity=severity,
            site_id=f"{pair['site_a']}..{pair['site_b']}",
            metric_value=round(max_beta, 6),
            metric_unit="rad",
            summary=(
                f"Differential settlement of {pair['differential_settlement_mm']} mm over "
                f"{pair['baseline_m']} m between '{pair['site_a']}' and '{pair['site_b']}' "
                f"yields angular distortion 1/{inv}, exceeding Eurocode-7 cracking limit (1/500)."
            ),
            evidence=pair,
        )
    ]


def detect_groundwater_coupling(
    grouped: dict[str, list[GeoObservation]],
    cfg: AuditConfig,
) -> list[Finding]:
    worst: tuple[str, float, float, float | None] | None = None
    for sid, series in grouped.items():
        gw_pts = [(o.timestamp, o.groundwater_depth_m, o.displacement_mm) for o in series if o.groundwater_depth_m is not None]
        tws_pts = [(o.timestamp, o.tws_cm, o.displacement_mm) for o in series if o.tws_cm is not None]

        if len(gw_pts) >= 6:
            t0 = gw_pts[0][0]
            ts = [(t - t0).total_seconds() / (365.25 * 86400.0) for t, _, _ in gw_pts]
            if ts[-1] >= 0.5:
                gw_fit = _ols_fit([[1.0, t] for t in ts], [float(g) for _, g, _ in gw_pts])
                disp_fit = _ols_fit([[1.0, t] for t in ts], [d for _, _, d in gw_pts])
                if gw_fit and disp_fit:
                    gw_rate_m_yr = gw_fit[0][1]
                    sub_rate_mm_yr = -disp_fit[0][1]
                    comp_ratio = sub_rate_mm_yr / max(gw_rate_m_yr, 0.05) if gw_rate_m_yr > 0 else 0.0
                    if gw_rate_m_yr >= cfg.gw_drawdown_warn_m_yr and comp_ratio >= cfg.compaction_ratio_warn_mm_m:
                        if worst is None or comp_ratio > worst[2]:
                            tws_rate = None
                            if len(tws_pts) >= 6:
                                t0_w = tws_pts[0][0]
                                t_w = [(t - t0_w).total_seconds() / (365.25 * 86400.0) for t, _, _ in tws_pts]
                                tws_fit = _ols_fit([[1.0, t] for t in t_w], [float(w) for _, w, _ in tws_pts])
                                if tws_fit:
                                    tws_rate = tws_fit[0][1]
                            worst = (sid, gw_rate_m_yr, comp_ratio, tws_rate)

        elif len(tws_pts) >= 6:
            t0 = tws_pts[0][0]
            ts = [(t - t0).total_seconds() / (365.25 * 86400.0) for t, _, _ in tws_pts]
            if ts[-1] >= 0.5:
                tws_fit = _ols_fit([[1.0, t] for t in ts], [float(w) for _, w, _ in tws_pts])
                disp_fit = _ols_fit([[1.0, t] for t in ts], [d for _, _, d in tws_pts])
                if tws_fit and disp_fit and tws_fit[0][1] <= -cfg.tws_loss_warn_cm_yr and disp_fit[0][1] <= -20.0:
                    if worst is None:
                        worst = (sid, 0.0, abs(disp_fit[0][1]) / max(abs(tws_fit[0][1]), 0.1), tws_fit[0][1])

    if worst is None:
        return []
    sid, gw_rate, ratio, tws_rate = worst
    severity = Severity.CRITICAL if (gw_rate >= 1.0 or ratio >= 50.0) else Severity.WARNING
    extra = f" and GRACE TWS loss {tws_rate:.2f} cm/yr" if tws_rate is not None else ""
    return [
        Finding(
            code="GROUNDWATER_COMPACTION_COUPLING",
            title="Severe groundwater depletion coupled to skeletal aquifer compaction",
            severity=severity,
            site_id=sid,
            metric_value=round(ratio, 1),
            metric_unit="mm/m",
            summary=(
                f"Site '{sid}' shows groundwater drawdown of {gw_rate:.2f} m/yr{extra}, "
                f"driving {ratio:.1f} mm of land subsidence per meter of head drop."
            ),
            evidence={
                "site_id": sid,
                "groundwater_drawdown_m_yr": round(gw_rate, 3),
                "compaction_ratio_mm_per_m": round(ratio, 2),
                "grace_tws_trend_cm_yr": round(tws_rate, 3) if tws_rate is not None else None,
            },
        )
    ]


def detect_insar_data_integrity(
    grouped: dict[str, list[GeoObservation]],
    cfg: AuditConfig,
) -> list[Finding]:
    """Audit InSAR telemetry quality: low coherence and Sentinel-1 C-band phase-unwrapping jumps (~28 mm)."""
    issues: list[str] = []
    evidence: dict[str, object] = {}

    low_coh_sites: list[str] = []
    unwrapping_jumps: list[dict[str, object]] = []

    for sid, series in grouped.items():
        cohs = [o.coherence for o in series if o.coherence is not None]
        if cohs:
            bad_frac = sum(1 for c in cohs if c < cfg.coherence_min) / len(cohs)
            if bad_frac >= cfg.coherence_bad_frac_limit:
                low_coh_sites.append(sid)

        if len(series) >= 5:
            steps = [series[i].displacement_mm - series[i - 1].displacement_mm for i in range(1, len(series))]
            med_step = median(steps)
            for idx, st in enumerate(steps, 1):
                jump = st - med_step
                if abs(jump) >= cfg.unwrapping_jump_mm:
                    unwrapping_jumps.append(
                        {
                            "site_id": sid,
                            "epoch": series[idx].timestamp.date().isoformat(),
                            "step_anomaly_mm": round(jump, 1),
                        }
                    )

    if low_coh_sites:
        issues.append(f"low coherence (<{cfg.coherence_min:.2f}) at {len(low_coh_sites)} site(s)")
        evidence["low_coherence_sites"] = low_coh_sites
    if unwrapping_jumps:
        issues.append(f"{len(unwrapping_jumps)} suspected phase-unwrapping jump(s) (>={cfg.unwrapping_jump_mm:.0f} mm)")
        evidence["unwrapping_jumps"] = unwrapping_jumps[:10]

    if not issues:
        return []

    return [
        Finding(
            code="INSAR_DATA_INTEGRITY",
            title="InSAR telemetry quality hazard (coherence loss / unwrapping jump)",
            severity=Severity.WARNING,
            site_id=str(unwrapping_jumps[0]["site_id"]) if unwrapping_jumps else low_coh_sites[0],
            metric_value=float(len(unwrapping_jumps) + len(low_coh_sites)),
            metric_unit="anomalies",
            summary="Detected " + " and ".join(issues) + "; verify interferogram unwrapping before engineering sign-off.",
            evidence=evidence,
        )
    ]
