"""Independent exact-rational closed-form reference; imports no producer or selector."""

from fractions import Fraction as Q


def exact_loss(system: dict, task: dict) -> dict:
    mass, mu = Q(str(system["mass_kg"])), Q(str(system["friction"]))
    duration = Q(task["steps"], 100)
    target = Q(str(task["distance_m"]))
    force = Q(str(system["gain"])) * (Q(3, 10) * Q(981, 100) + 2 * target / duration**2)
    displacement = max(Q(0), force / mass - mu * Q(981, 100)) * duration**2 / 2
    return {"displacement": str(displacement), "loss": int(abs(displacement - target) > Q(1, 100))}


def assess_case(case: dict, tasks: list[dict]) -> dict:
    pairs = []
    cells = {"both_succeed": 0, "reference_only": 0, "candidate_only": 0, "both_fail": 0}
    for task in tasks:
        old, new = exact_loss(case["reference"], task), exact_loss(case["candidate"], task)
        cells[
            {
                (0, 0): "both_succeed",
                (0, 1): "reference_only",
                (1, 0): "candidate_only",
                (1, 1): "both_fail",
            }[(old["loss"], new["loss"])]
        ] += 1
        pairs.append({"id": task["id"], "reference": old, "candidate": new})
    delta = Q(sum(p["candidate"]["loss"] - p["reference"]["loss"] for p in pairs), len(tasks))
    return {
        "delta": str(delta),
        "relation": "beneficial" if delta < 0 else "harmful" if delta > 0 else "equivalent",
        "contingency": cells,
        "pairs": pairs,
        "scope": "exact constant-force model and finite tasks; not hardware, population inference or independent human review",
    }
