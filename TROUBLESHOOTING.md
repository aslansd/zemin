# Troubleshooting

Start with:

```bash
zemin doctor
```

---

## `ValueError: No geospatial observations available inside the selected footprint.`

Your GeoJSON polygon coordinates may be ordered `[lat, lon]` instead of the
GeoJSON RFC 7946 standard `[lon, lat]` (for Tehran, longitude is ~`51.3`,
latitude is ~`35.6`). Verify your ring coordinates match `[51.xxx, 35.xxx]`.

---

## `INSAR_DATA_INTEGRITY` flags a ~28 mm jump

Sentinel-1 C-band radar has wavelength ~55.5 mm, so a single phase-unwrapping
cycle slip appears as an instantaneous +/-27.7 mm step between consecutive
12-day epochs. `zemin` intentionally flags this rather than silently folding
the jump into your subsidence velocity estimate. Inspect the interferogram pair
at the reported date before signing off on structural tilt calculations.

---

## `CRITICAL_SLOWING_DOWN` does not trigger on short datasets

Rolling Ornstein-Uhlenbeck AR(1) recovery-rate estimation requires at least
`csd_window_epochs + 12` epochs (default 36 Sentinel-1 epochs, roughly 1.2
years at 12-day repeat) to distinguish dynamical slowing down from seasonal
noise. Shorter series safely skip this check without false alarms.
