def predict_feed_portion(temp: float, dissolved_oxygen: float, hopper_level: int = 100) -> tuple[int, str]:
    base_portion = 130

    if 26.5 <= temp <= 28.5 and dissolved_oxygen >= 6.0:
        portion = int(base_portion * 1.15)
        reasoning = (
            f"Portion increased by 15% due to optimal water temp ({temp:.1f}°C) "
            f"and elevated daytime fish activity."
        )
    elif temp > 30.0 or dissolved_oxygen < 5.0:
        portion = int(base_portion * 0.70)
        reasoning = (
            f"Portion reduced by 30% to prevent unconsumed feed pollution "
            f"due to stressed pond conditions (Temp: {temp:.1f}°C, DO: {dissolved_oxygen:.1f} mg/L)."
        )
    else:
        portion = base_portion
        reasoning = "Standard scheduled maintenance portion under nominal conditions."

    if hopper_level < 20:
        portion = min(portion, 50)
        reasoning += f" Hopper reserve low ({hopper_level}% remaining); portion capped for conservation."

    return portion, reasoning
