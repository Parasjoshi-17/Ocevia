from database import get_city_by_name
from agents.orchestrator import run_orchestrator


city = get_city_by_name("Mumbai")

result = run_orchestrator(
    latitude=city["latitude"],
    longitude=city["longitude"],
    forecast_date="2026-09-19",
    time_window="morning",
    city_name="Mumbai",
    target_day="tomorrow",
)

print("\n==============================")
print("ORCHESTRATOR TEST")
print("==============================")

print("Status:", result.get("status"))

if result.get("status") == "success":

    print(
        "Verdict:",
        result["safety"].get("verdict")
    )

    print(
        "Hours:",
        result["safety"].get("hours_evaluated")
    )

    print(
        "Metrics:",
        result["metrics"]
    )

    print(
        "Explanation:",
        result["explanation"]
    )

else:

    print(
        "Stage:",
        result.get("stage")
    )

    print(
        "Error:",
        result.get("error")
    )