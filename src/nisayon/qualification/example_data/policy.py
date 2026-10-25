"""Small development example; no learned policy or robot is executed."""


def normalize(value):
    return {"action": [(position - 10) / 10 for position in value["position"]]}


def reference(value):
    return normalize(value)


def candidate(value):
    return normalize(value)


def wrong_sign(value):
    result = normalize(value)
    result["action"][0] = -result["action"][0]
    return result
