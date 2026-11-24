"""Small residual hypothesis bank. Scores are not calibrated probabilities."""

import numpy as np


class HypothesisBank:
    def __init__(self):
        self.wrist_average = None
        self.sustained = 0

    def update(self, obs, estimate):
        if obs is None or estimate is None or not all(obs.valid):
            self.sustained = 0
            return {
                "mode": "unknown_degraded",
                "trigger": False,
                "scores": None,
                "calibrated_probabilities": False,
                "features": None,
            }
        w = np.asarray(obs.wrist_wrench)
        if self.wrist_average is None:
            self.wrist_average = w.copy()
        # Modeling allowance dominates electronic noise. A score of one means
        # a 0.8N / 0.08Nm dynamic wrench departure or a 0.03m/s foot residual.
        residual = w - self.wrist_average
        load = float(
            np.linalg.norm(residual / np.array([0.8, 0.8, 0.8, 0.08, 0.08, 0.08])) / np.sqrt(12)
        )
        self.wrist_average = 0.96 * self.wrist_average + 0.04 * w
        foot = max(
            (
                np.linalg.norm(x["velocity_residual"]) / 0.03
                for x in estimate["innovations"]
                if x["nis"] is not None
            ),
            default=0.0,
        )
        scores = {
            "nominal": foot**2 + load**2,
            "unreliable_support": max(0, 3 - foot) ** 2 + load**2,
            "moving_load": foot**2 + max(0, 3 - load) ** 2,
        }
        if foot > 2 and load > 2:
            mode = "unknown_compound"
        elif foot > 2 and load < 1.5:
            mode = "unreliable_support"
        elif load > 2 and foot < 1.5:
            mode = "moving_load"
        elif foot < 1.5 and load < 1.5:
            mode = "nominal"
        else:
            mode = "unknown_ambiguous"
        # Development nominal residual peak was 3.37. Four, for two packets,
        # avoids firing on the measured set-down transient. Frozen before holdout.
        active = max(foot, load) > 4.0
        self.sustained = self.sustained + 1 if active else 0
        return {
            "mode": mode,
            "trigger": self.sustained >= 2,
            "scores": scores,
            "calibrated_probabilities": False,
            "features": {"foot": float(foot), "load": load},
        }
