"""Shared stateless computation for the exposed calibration comparison."""


def normalize(position, center):
    return (position - center) / 10


def observe(position, center):
    reference = normalize(position, 10)
    return {
        "position": position,
        "reference": reference,
        "candidate": normalize(position, center),
        "negative_control": -reference,
    }
