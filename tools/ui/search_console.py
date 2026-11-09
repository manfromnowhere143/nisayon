"""Submit or inspect Nisayon only, using the operator's existing Google ADC.

No credentials or authorization responses are printed or retained. Submission
requires --submit. Readback reports Google's indexed version, not a live test.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ORIGIN = "https://nisayon.danielwahnich.dev/"
DOMAIN = "sc-domain:danielwahnich.dev"
API = "https://www.googleapis.com/webmasters/v3/sites/"


def run(submit: bool) -> dict:
    adc = json.loads(
        (Path.home() / ".config/gcloud/application_default_credentials.json").read_bytes()
    )
    if adc.get("type") != "authorized_user":
        raise ValueError("An existing operator OAuth connection is required")
    form = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            **{key: adc[key] for key in ("client_id", "client_secret", "refresh_token")},
        }
    ).encode()
    with urllib.request.urlopen(
        urllib.request.Request("https://oauth2.googleapis.com/token", data=form), timeout=30
    ) as response:
        token = json.load(response)["access_token"]

    def request(url: str, method="GET", data=None):
        req = urllib.request.Request(
            url,
            method=method,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            data=json.dumps(data).encode() if data is not None else None,
        )
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read()
            return {"status": response.status, "data": json.loads(raw) if raw else None}

    quote = lambda value: urllib.parse.quote(value, safe="")  # noqa: E731
    sites = request(API)["data"].get("siteEntry", [])
    owner = next((site for site in sites if site["siteUrl"] == DOMAIN), None)
    if owner is None or owner["permissionLevel"] != "siteOwner":
        raise ValueError("Verified domain owner access is required before operating Nisayon")
    receipt = {
        "checked_at": datetime.now(UTC).isoformat(),
        "domain_property": owner,
        "submitted": [],
        "sitemaps": [],
        "inspection": {},
    }
    if submit:
        # Never submit a non-live URL, login screen, or another application.
        with urllib.request.urlopen(ORIGIN, timeout=30) as response:
            html = response.read().decode()
            if (
                response.status != 200
                or f'href="{ORIGIN}"' not in html
                or "An experiment engine for physical AI" not in html
            ):
                raise ValueError("Nisayon's canonical HTML is not publicly available")
        receipt["added_property"] = request(API + quote(ORIGIN), "PUT")
    receipt["url_property"] = request(API + quote(ORIGIN))["data"]
    if receipt["url_property"]["permissionLevel"] != "siteOwner":
        raise ValueError("The new URL property did not inherit owner verification")
    for property_url in (DOMAIN, ORIGIN):
        sitemap_endpoint = API + quote(property_url) + "/sitemaps/" + quote(ORIGIN + "sitemap.xml")
        if submit:
            receipt["submitted"].append(
                {
                    "property": property_url,
                    "sitemap": ORIGIN + "sitemap.xml",
                    **request(sitemap_endpoint, "PUT"),
                }
            )
        receipt["sitemaps"].append({"property": property_url, **request(sitemap_endpoint)["data"]})
    for path in ("", "about/"):
        result = request(
            "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
            "POST",
            {"inspectionUrl": ORIGIN + path, "siteUrl": ORIGIN, "languageCode": "en-US"},
        )["data"]["inspectionResult"]
        receipt["inspection"][ORIGIN + path] = result
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.submit)
    except urllib.error.HTTPError as error:
        details = json.loads(error.read())
        value = details.get("error", {})
        message = (
            value.get("message")
            if isinstance(value, dict)
            else details.get("error_description", value)
        )
        raise SystemExit(f"Google returned HTTP {error.code}: {message}") from None
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "property": result["url_property"],
                "submitted": result["submitted"],
                "sitemaps": result["sitemaps"],
                "inspection": {
                    url: data.get("indexStatusResult") for url, data in result["inspection"].items()
                },
            },
            indent=2,
        )
    )
