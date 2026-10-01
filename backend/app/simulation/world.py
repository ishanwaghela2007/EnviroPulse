"""Static prototype world: industrial zones, sensors, factories, event templates and thresholds.

IMPORTANT (documented in README): zone polygons are APPROXIMATE, SYNTHETIC boundaries placed around
three industrial belts in the Mumbai Metropolitan Region for demo realism. They are not official
MIDC/MPCB boundaries. Facility names are fictional. All sensor streams defined here are served by the
simulator and are labelled SIMULATED DEMO STREAM in the API and UI."""

ZONES = [
    {
        "id": "zone_a", "name": "Industrial Zone A",
        "description": "Thane–Belapur industrial belt (synthetic boundary). Mixed chemicals and dyes cluster.",
        "polygon": [(73.004, 19.086), (73.036, 19.083), (73.043, 19.104), (73.037, 19.127),
                    (73.012, 19.129), (73.001, 19.108), (73.004, 19.086)],
    },
    {
        "id": "zone_b", "name": "Industrial Zone B",
        "description": "Taloja industrial belt (synthetic boundary). Textile processing and pharma cluster.",
        "polygon": [(73.112, 19.046), (73.158, 19.044), (73.163, 19.066), (73.150, 19.083),
                    (73.118, 19.080), (73.112, 19.046)],
    },
    {
        "id": "zone_c", "name": "Industrial Zone C",
        "description": "Trombay industrial belt (synthetic boundary). Fertiliser and petrochemical cluster.",
        "polygon": [(72.884, 18.986), (72.922, 18.984), (72.927, 19.004), (72.915, 19.021),
                    (72.889, 19.019), (72.884, 18.986)],
    },
]
BOUNDARY_NOTE = "Approximate synthetic boundary for the prototype. Not an official MIDC/MPCB boundary."

AIR = ["pm25", "pm10", "no2"]
WATER = ["ph", "turbidity", "dissolved_oxygen"]

SENSORS = [
    # id, zone, type, name, lat, lon, calibration multiplier
    ("a_air_1", "zone_a", "air", "A-Air-1 (north gate)", 19.118, 73.020, 1.00),
    ("a_air_2", "zone_a", "air", "A-Air-2 (south cluster)", 19.094, 73.023, 1.04),
    ("a_wat_1", "zone_a", "water", "A-Water-1 (nallah outfall)", 19.100, 73.008, 1.00),
    ("a_wat_2", "zone_a", "water", "A-Water-2 (CETP inlet)", 19.110, 73.035, 1.02),
    ("b_air_1", "zone_b", "air", "B-Air-1 (east road)", 19.070, 73.150, 1.00),
    ("b_air_2", "zone_b", "air", "B-Air-2 (west gate)", 19.056, 73.122, 0.97),
    ("b_wat_1", "zone_b", "water", "B-Water-1 (Kasadi river)", 19.052, 73.140, 1.00),
    ("b_wat_2", "zone_b", "water", "B-Water-2 (drain junction)", 19.074, 73.128, 1.03),
    ("c_air_1", "zone_c", "air", "C-Air-1 (jetty road)", 19.012, 72.905, 1.00),
    ("c_air_2", "zone_c", "air", "C-Air-2 (township edge)", 18.992, 72.898, 1.05),
    ("c_wat_1", "zone_c", "water", "C-Water-1 (creek)", 18.995, 72.918, 1.00),
]

# Fictional facilities. `effects` is the SIMULATOR'S GROUND TRUTH: pollutant response per % of
# production above nominal, with a lag in 15-min windows. The analytics never read this table —
# tests use it only to check that the attribution estimate recovers the injected relationship.
FACTORIES = [
    {"id": "fac_a1", "zone": "zone_a", "name": "Apex Organics (fictional)", "sector": "Specialty chemicals",
     "lat": 19.108, "lon": 73.027, "nominal": 62, "effects": {"pm25": (1.20, 1), "pm10": (1.50, 1), "no2": (0.30, 1)}},
    {"id": "fac_a2", "zone": "zone_a", "name": "Sunrise Dye Works (fictional)", "sector": "Dyes & intermediates",
     "lat": 19.099, "lon": 73.015, "nominal": 55, "effects": {"pm25": (0.10, 0), "turbidity": (0.08, 1)}},
    {"id": "fac_a3", "zone": "zone_a", "name": "Harbour Packaging (fictional)", "sector": "Packaging",
     "lat": 19.121, "lon": 73.031, "nominal": 70, "effects": {}},
    {"id": "fac_b1", "zone": "zone_b", "name": "Meridian Pharma (fictional)", "sector": "Pharmaceuticals",
     "lat": 19.064, "lon": 73.138, "nominal": 58, "effects": {"no2": (0.25, 0)}},
    {"id": "fac_b2", "zone": "zone_b", "name": "Kasadi Textiles (fictional)", "sector": "Textile processing",
     "lat": 19.058, "lon": 73.132, "nominal": 60, "effects": {"turbidity": (0.60, 1), "pm25": (0.10, 0)}},
    {"id": "fac_c1", "zone": "zone_c", "name": "Bayline Fertilisers (fictional)", "sector": "Fertilisers",
     "lat": 19.006, "lon": 72.911, "nominal": 66, "effects": {"no2": (0.50, 0), "pm10": (0.40, 1)}},
    {"id": "fac_c2", "zone": "zone_c", "name": "Creekside Refining (fictional)", "sector": "Petrochemicals",
     "lat": 18.998, "lon": 72.894, "nominal": 72, "effects": {"pm25": (0.35, 1), "no2": (0.40, 0)}},
]

# Zone baselines: (base level, diurnal amplitude, sensor noise sd)
ZONE_BASELINES = {
    "zone_a": {"pm25": (38, 6, 2.2), "pm10": (68, 9, 3.5), "no2": (34, 7, 2.0),
               "ph": (7.35, 0.05, 0.05), "turbidity": (7.5, 0.8, 0.5), "dissolved_oxygen": (6.6, 0.3, 0.12)},
    "zone_b": {"pm25": (32, 5, 2.0), "pm10": (60, 8, 3.2), "no2": (28, 6, 1.8),
               "ph": (7.20, 0.05, 0.05), "turbidity": (8.5, 0.9, 0.55), "dissolved_oxygen": (6.2, 0.3, 0.12)},
    "zone_c": {"pm25": (41, 6, 2.4), "pm10": (72, 9, 3.6), "no2": (40, 8, 2.2),
               "ph": (7.60, 0.05, 0.05), "turbidity": (6.5, 0.7, 0.45), "dissolved_oxygen": (6.9, 0.3, 0.12)},
}

# Event effects on pollutants while active (simulator ground truth)
EVENT_EFFECTS = {
    "construction": {"pm10": 28.0, "pm25": 5.0},
    "traffic_event": {"no2": 16.0, "pm25": 3.0},
    "local_event": {"pm10": 12.0, "pm25": 4.0},
    "industrial_activity": {"turbidity": 4.0},
}

# Operational thresholds (per 15-min zone mean). `basis` is shown in the UI next to every alert.
THRESHOLDS = [
    # zone (None=global), parameter, value, direction, persistence, min_conf, severity, action, basis
    (None, "pm25", 60.0, "above", 3, 0.5, "high",
     "Notify the zone environmental officer. Inspect stack emissions at facilities ranked as likely contributors and verify sensor calibration.",
     "Prototype operational trigger at the CPCB NAAQS 24-h PM2.5 limit (60 µg/m³) applied to 15-min zone means. Not a regulatory compliance determination."),
    (None, "pm10", 100.0, "above", 3, 0.5, "medium",
     "Check dust suppression at active construction sites and material-handling yards in the zone.",
     "Prototype operational trigger at the CPCB NAAQS 24-h PM10 limit (100 µg/m³) applied to 15-min zone means."),
    (None, "no2", 80.0, "above", 4, 0.5, "medium",
     "Review combustion sources and traffic diversions in the zone.",
     "Prototype operational trigger at the CPCB NAAQS 24-h NO₂ limit (80 µg/m³) applied to 15-min zone means."),
    (None, "turbidity", 25.0, "above", 2, 0.5, "medium",
     "Inspect effluent outfalls upstream of the sensor and collect a grab sample for laboratory confirmation.",
     "Prototype operational trigger for surface-water turbidity chosen for this demo."),
    (None, "dissolved_oxygen", 4.0, "below", 2, 0.5, "high",
     "Collect a grab sample and check for organic-load discharge upstream.",
     "Prototype trigger based on CPCB designated-best-use guidance of DO ≥ 4 mg/L."),
    (None, "ph", 8.5, "above", 2, 0.5, "medium", "Verify effluent neutralisation at upstream facilities.",
     "Prototype trigger based on the CPCB designated-best-use pH range 6.5–8.5."),
    (None, "ph", 6.5, "below", 2, 0.5, "medium", "Verify effluent neutralisation at upstream facilities.",
     "Prototype trigger based on the CPCB designated-best-use pH range 6.5–8.5."),
]

# Historical events relative to history end: (zone, type, hours offset, duration h, (lat, lon), severity, text)
HISTORY_EVENTS = [
    ("zone_a", "construction", -9 * 24 - 5, 6, (19.112, 73.018), "medium", "Service-road resurfacing near north gate"),
    ("zone_a", "traffic_event", -2 * 24 - 14, 3, (19.097, 73.030), "low", "Container truck queue at checkpoint"),
    ("zone_b", "industrial_activity", -5 * 24 - 10, 3, (19.058, 73.133), "medium",
     "Scheduled effluent line flushing reported near textile cluster"),
    ("zone_b", "local_event", -1 * 24 - 20, 4, (19.068, 73.145), "low", "Weekly market"),
    ("zone_c", "local_event", -3 * 24 - 8, 1, (19.001, 72.901), "medium", "Open burning at public gathering"),
    ("zone_c", "construction", -6 * 24 - 30, 8, (19.015, 72.912), "medium", "Pipeline trench excavation"),
]

# Historical factory output overrides: (factory, hours offset, duration h, production level %)
HISTORY_FACTORY_OVERRIDES = [
    ("fac_b2", -5 * 24 - 10.5, 3.0, 100.0),  # zone B discharge episode -> turbidity anomaly + persistent breach
    ("fac_a1", -4 * 24 - 6, 0.5, 82.0),      # zone A short excursion -> anomaly, no persistent breach
]
# One-window spike: zone C PM10 (anomaly + transient breach, NO alert because persistence = 3)
HISTORY_POINT_SPIKES = [("zone_c", "pm10", -3 * 24 - 8, 125.0)]
