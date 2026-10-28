import score
from native import collect


def run(ctx):
    diagnostic = ctx.upstream("score")
    confirmation = score.evaluate(collect(ctx, "confirmation_seed"))
    if diagnostic["mode"] != confirmation["mode"]:
        raise ValueError("Diagnostic and confirmation scoring differ")
    return {
        "diagnostic": diagnostic,
        "confirmation": confirmation,
        "decision": "adopt" if diagnostic["holds"] and confirmation["holds"] else "reject",
        "scope": "Exposed finite camera preprocessing; deployment remains unresolved.",
    }
