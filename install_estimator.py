# ============================================================
# AV SHIELD — install_estimator.py — Low-Voltage Install Bid Engine
# ============================================================

import math

LABOR_RATE = 125.00

CABLE_PER_FT = {
    "CMR": 0.16,
    "CMP": 0.28,
    "CMX": 0.32,
}

CONDUIT_PER_FT = 1.50
CONDUIT_LABOR_HRS_PER_FT = 0.05

ENV_HOURS_PER_CAM = {
    "standard": 1.5,
    "industrial": 2.5,
    "high_reach": 4.0,
}

CONNECTORS_PER_CAM = 15.00

SWITCH_COST = 145.00
BRIDGE_COST = 145.00
BRIDGES_PER_DETACHED_BLDG = 2
NVR_COST = 0.00                        # <<< PLACEHOLDER — set real NVR unit cost

WASTE_FACTOR = 1.10
CABLE_MARKUP = 1.30                    # 30% markup — CABLE ONLY

LIFT_DAILY = 250.00
CAMS_PER_LIFT_DAY = 8

RUN_K = 0.75
RUN_DROP_FT = 15
FALLBACK_FT_PER_CAM = 150


def estimate_cable_feet(cam_count, sqft):
    if sqft and sqft > 0:
        per_cam = RUN_K * math.sqrt(sqft) + RUN_DROP_FT
    else:
        per_cam = FALLBACK_FT_PER_CAM
    return cam_count * per_cam * WASTE_FACTOR


def estimate_install(cam_count, sqft=None, cable_type="CMR",
                     environment="standard", buildings=1,
                     conduit_feet=0.0, add_nvr=False):
    n = max(1, int(cam_count))
    cable_type = cable_type.upper() if cable_type else "CMR"
    cable_rate = CABLE_PER_FT.get(cable_type, CABLE_PER_FT["CMR"])
    env = (environment or "standard").lower()
    env_hrs = ENV_HOURS_PER_CAM.get(env, ENV_HOURS_PER_CAM["standard"])
    buildings = max(1, int(buildings))

    cable_ft = estimate_cable_feet(n, sqft)
    cable_cost_raw = cable_ft * cable_rate
    cable_cost = cable_cost_raw * CABLE_MARKUP
    connectors = n * CONNECTORS_PER_CAM
    conduit_material = conduit_feet * CONDUIT_PER_FT * WASTE_FACTOR if conduit_feet else 0.0

    detached = buildings - 1
    switch_count = 1 + detached
    switch_cost = switch_count * SWITCH_COST

    bridge_count = detached * BRIDGES_PER_DETACHED_BLDG
    bridge_cost = bridge_count * BRIDGE_COST

    nvr_cost = NVR_COST if add_nvr else 0.0

    materials_total = (cable_cost + connectors + conduit_material
                       + switch_cost + bridge_cost + nvr_cost)

    cam_hours = n * env_hrs
    conduit_hours = conduit_feet * CONDUIT_LABOR_HRS_PER_FT if conduit_feet else 0.0
    total_hours = cam_hours + conduit_hours
    labor_cost = total_hours * LABOR_RATE

    lift_cost = 0.0
    lift_days = 0
    if env == "high_reach":
        lift_days = math.ceil(n / CAMS_PER_LIFT_DAY)
        lift_cost = lift_days * LIFT_DAILY

    total = materials_total + labor_cost + lift_cost

    return {
        "inputs": {
            "cam_count": n, "sqft": sqft, "cable_type": cable_type,
            "environment": env, "buildings": buildings,
            "conduit_feet": conduit_feet, "add_nvr": add_nvr,
        },
        "materials": {
            "cable_feet": round(cable_ft),
            "cable_cost_raw": round(cable_cost_raw, 2),
            "cable_cost_marked": round(cable_cost, 2),
            "connectors": round(connectors, 2),
            "conduit_material": round(conduit_material, 2),
            "switches": {"count": switch_count, "cost": round(switch_cost, 2)},
            "bridges": {"count": bridge_count, "cost": round(bridge_cost, 2)},
            "nvr": round(nvr_cost, 2),
            "total": round(materials_total, 2),
        },
        "labor": {
            "camera_hours": cam_hours, "conduit_hours": conduit_hours,
            "total_hours": total_hours, "cost": round(labor_cost, 2),
        },
        "lift": {"days": lift_days, "cost": round(lift_cost, 2)},
        "install_total": round(total, 2),
        "flags": {
            "NVR_COST_is_placeholder": (NVR_COST == 0.0),
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(estimate_install(6, sqft=12000, cable_type="CMR",
                                       environment="standard", buildings=1), indent=2))
    print(json.dumps(estimate_install(10, sqft=30000, cable_type="CMX",
                                       environment="industrial", buildings=2), indent=2))
