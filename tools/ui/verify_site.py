"""Check the packaged or deployed site, including crawl resources and evidence roots."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import struct
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

ORIGIN = "https://nisayon.danielwahnich.dev"


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def values(self, tag, attribute, value, target):
        return [
            attrs.get(target)
            for name, attrs in self.tags
            if name == tag and attrs.get(attribute) == value
        ]


def verify(directory: Path | None, origin: str, retained_study: str | None = None) -> dict:
    checks: list[str] = []
    reads: dict[str, tuple[bytes, dict]] = {}

    def get(path: str) -> tuple[bytes, dict]:
        if path in reads:
            return reads[path]
        if directory:
            pathname = urllib.parse.urlsplit(path).path
            file = directory / pathname.lstrip("/")
            if pathname.endswith("/"):
                file /= "index.html"
            result = file.read_bytes(), {}
        else:
            request = urllib.request.Request(
                origin + path, headers={"User-Agent": "Nisayon-release-check/1.0"}
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                assert response.status == 200, (path, response.status)
                result = response.read(), dict(response.headers.items())
        reads[path] = result[0], {key.lower(): value for key, value in result[1].items()}
        return reads[path]

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        checks.append(message)

    robots = urllib.robotparser.RobotFileParser()
    robots.parse(get("/robots.txt")[0].decode().splitlines())
    check(robots.site_maps() == [ORIGIN + "/sitemap.xml"], "robots names the canonical sitemap")
    sitemap = ET.fromstring(get("/sitemap.xml")[0])
    urls = [node.text for node in sitemap.findall("{*}url/{*}loc")]
    check(
        urls
        in (
            [ORIGIN + "/", ORIGIN + "/about/"],
            [ORIGIN + path for path in ("/", "/about/", "/sdk/", "/portable-review/")],
        ),
        "sitemap contains only canonical public pages",
    )
    has_guides = ORIGIN + "/sdk/" in urls
    titles: set[str] = set()
    for url in urls:
        path = urllib.parse.urlsplit(url).path
        raw, headers = get(path)
        html = raw.decode()
        page = Page(html)
        title = re.findall(r"<title>(.*?)</title>", html, re.S)
        check(
            len(title) == 1 and bool(title[0].strip()) and title[0] not in titles,
            f"{path} has a unique title",
        )
        titles.update(title)
        check(
            page.values("link", "rel", "canonical", "href") == [url],
            f"{path} has one self-canonical",
        )
        check(
            len(re.findall(r"<h1\b", html)) == 1,
            f"{path} has one primary heading before JavaScript",
        )
        check(
            len(page.values("meta", "name", "description", "content")) == 1,
            f"{path} has a description",
        )
        check(
            page.values("meta", "property", "og:url", "content") == [url],
            f"{path} sharing URL agrees",
        )
        check(
            page.values("meta", "property", "og:site_name", "content") == ["Nisayon"],
            f"{path} brand agrees",
        )
        check(
            "noindex" not in headers.get("x-robots-tag", "").lower(), f"{path} indexable response"
        )
        check(
            not any(
                "noindex" in value for value in page.values("meta", "name", "robots", "content")
            ),
            f"{path} indexable markup",
        )
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        check(len(blocks) == 1, f"{path} has one structured-data graph")
        graph = json.loads(blocks[0])
        check(graph["@context"] == "https://schema.org", f"{path} structured data parses")
        if path in {"/sdk/", "/portable-review/"}:
            article = next(node for node in graph["@graph"] if node["@type"] == "TechArticle")
            check(
                article["url"] == url and article["headline"] == title[0],
                f"{path} article agrees with visible metadata",
            )
            check(
                "nisayon-qualify" in html and "deployment acceptance" in html.lower(),
                f"{path} explains the interface and acceptance boundary",
            )
        if path == "/":
            website = [node for node in graph["@graph"] if node["@type"] == "WebSite"]
            check(
                len(website) == 1
                and website[0]["name"] == "Nisayon"
                and website[0]["url"] == ORIGIN + "/",
                "homepage WebSite identity is canonical",
            )
        check(robots.can_fetch("Googlebot", url), f"{path} allows crawling")
        check(not headers.get("x-robots-tag", "").startswith("noindex"), f"{path} permits indexing")
        if not directory:
            check("text/html" in headers.get("content-type", ""), f"{path} serves HTML")
            check(
                headers.get("x-content-type-options") == "nosniff", f"{path} has nosniff protection"
            )
        csp = headers.get("content-security-policy", "")
        if directory:
            config = json.loads((directory.parent / "config.json").read_bytes())
            csp = next(
                route["headers"]["Content-Security-Policy"]
                for route in config["routes"]
                if "Content-Security-Policy" in route.get("headers", {})
            )
        for attributes, script in re.findall(r"<script\b([^>]*)>(.*?)</script>", html, re.S):
            if not re.search(r"\bsrc\s*=", attributes):
                sha = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                check(f"'sha256-{sha}'" in csp, f"{path} inline script is covered by CSP")
        for tag, attrs in page.tags:
            ref = (
                attrs.get("src")
                if tag in {"script", "img"}
                else attrs.get("href")
                if tag in {"a", "link"}
                else None
            )
            if not ref or ref.startswith("#"):
                continue
            absolute = urllib.parse.urljoin(url, ref)
            if urllib.parse.urlsplit(absolute).netloc != urllib.parse.urlsplit(ORIGIN).netloc:
                continue
            resource = urllib.parse.urlsplit(absolute).path
            check(robots.can_fetch("Googlebot", absolute), f"crawler can read {resource}")
            get(resource)
    for path, expected in (
        ("/favicon-96.png", (96, 96)),
        ("/apple-touch-icon.png", (180, 180)),
        ("/brand/nisayon-share.png", (1200, 630)),
    ):
        raw, _ = get(path)
        check(
            raw[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", raw[16:24]) == expected,
            f"{path} dimensions match the metadata",
        )
    manifest = json.loads(get("/site.webmanifest")[0])
    for icon in manifest["icons"]:
        raw, _ = get(urllib.parse.urljoin("/site.webmanifest", icon["src"]))
        width, height = struct.unpack(">II", raw[16:24])
        check(
            icon["sizes"] == f"{width}x{height}",
            f"manifest icon {icon['src']} exists at the declared size",
        )

    if manifest.get("id") == "./":
        check(
            manifest["scope"] == "./" and manifest["display"] == "standalone",
            "install identity and scope are explicit",
        )
        check(
            [item["url"] for item in manifest["shortcuts"]]
            == ["./#view=system", "./#view=research", "./#view=lab"],
            "all three instrument surfaces have app shortcuts",
        )
        raw_worker, worker_headers = get("/sw.js")
        match = re.match(rb"const RELEASE = (\{[^\n]+\});", raw_worker)
        check(match is not None, "offline release has an exact resource manifest")
        offline = json.loads(match[1])
        for entry in offline["precache"]:
            path = entry["path"]
            check(
                not path.startswith("/") and ".." not in path.split("/"),
                "offline path stays within the application",
            )
            raw, _ = get("/" if path == "index.html" else "/" + path)
            check(
                hashlib.sha256(raw).hexdigest() == entry["sha256"], f"offline bytes match: {path}"
            )
        check(
            not any(item["path"].startswith(("fixtures/", "api/")) for item in offline["precache"]),
            "offline research excludes mutable discovery and robot records",
        )
        if not directory:
            check(
                "javascript" in worker_headers.get("content-type", ""),
                "worker has an executable JavaScript content type",
            )
            check(
                "no-cache" in worker_headers.get("cache-control", ""),
                "worker revalidates at its stable URL",
            )

    def bound(path: str, ref: dict):
        raw, headers = get(path)
        check(
            len(raw) == ref["byte_length"] and hashlib.sha256(raw).hexdigest() == ref["sha256"],
            f"verified exact evidence bytes: {path}",
        )
        if not directory:
            check(
                headers.get("x-robots-tag") == "noindex",
                f"{path} is readable without becoming a search result",
            )
            check("immutable" in headers.get("cache-control", ""), f"{path} has immutable caching")
        return json.loads(raw)

    library = json.loads(get("/fixtures/ui/recorded/library.json")[0])
    check(len(library["cases"]) == 6, "six recorded cases are available")
    for case in library["cases"]:
        base = "/fixtures/ui/recorded/" + case["directory"] + "/"
        discovery = json.loads(get(base + "evidence.json")[0])
        check(
            discovery["manifest"] == case["manifest"],
            f"{case['case_id']} discovery agrees with the catalog",
        )
        generation = bound(base + case["manifest"]["path"], case["manifest"])
        case_ref = next(ref for ref in generation["files"] if ref.get("kind") == "case")
        bound(base + case_ref["path"], case_ref)
    inventory = json.loads(get("/api/engine.json")[0])
    check(
        inventory["execution_connected"] is False,
        "engine inventory preserves the recorded-only boundary",
    )
    base = "/fixtures/ui/study/"
    discovery = json.loads(get(base + "evidence.json")[0])
    ref = discovery["generation"]
    study = bound(base + ref["path"], ref)
    check(
        study["execution_connected"] is False and study["scientific_acceptance"] == "none",
        "study preserves execution and acceptance boundaries",
    )
    if retained_study is not None:
        # A runtime-only release may retain the exact previously published
        # historical Study while displaying a newer source inventory. This is
        # an explicit digest pin, never an admission/revalidation of old trials.
        check(
            re.fullmatch(r"[0-9a-f]{64}", retained_study) is not None
            and ref["sha256"] == retained_study,
            "historical Study remains the exact previously published generation",
        )
    else:
        check(
            study["source"]["engine_commit"] == inventory["provenance"]["engine_commit"],
            "study and engine inventory agree on canonical source",
        )
    pairs = records = 0
    for entry in study["trials"]:
        trial = bound(base + entry["object"]["path"], entry["object"])
        check(
            entry["key"] == f"{trial['comparison']}/{trial['case_id']}/{trial['arm']}",
            "study trial identity agrees: " + entry["key"],
        )
        confirmation = trial["confirmation"]
        pairs += len(confirmation["pairs"]) if confirmation else 0
        records += len(confirmation["observations"]) if confirmation else 0
    check(
        study["counts"]["pairs"] == pairs and study["counts"]["records"] == records,
        "study pair and execution counts agree with retained objects",
    )
    for ref in study.get("reports", {}).values():
        bound(base + ref["path"], ref)
    if not directory:
        for path in (
            "/not-a-nisayon-page",
            "/dev-fixture/evidence.json",
            "/.env",
            "/.git/config",
            "/local-reviews/merged.nisayon.zip",
            "/test/fixtures/qualification/merged.nisayon.zip",
        ):
            try:
                get(path)
            except urllib.error.HTTPError as error:
                check(error.code == 404, f"{path} returns a real 404")
            else:
                raise AssertionError(f"Unexpectedly public or soft-404: {path}")
        redirects = [
            ("/index.html", "/"),
            ("/about", "/about/"),
            ("/about/index.html", "/about/"),
        ]
        if has_guides:
            redirects.extend(
                (path, f"/{name}/")
                for name in ("sdk", "portable-review")
                for path in (f"/{name}", f"/{name}/index.html")
            )
        for path, target in redirects:
            with urllib.request.urlopen(origin + path, timeout=30) as response:
                check(response.url == origin + target, f"{path} redirects to {target}")
        check(
            get("/?r=regression-0")[0] == get("/")[0],
            "query selections retain the canonical application shell",
        )
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": str(directory) if directory else origin,
        "checks_passed": len(checks),
        "checks": checks,
        "files_read": [
            {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw)}
            for path, (raw, _) in reads.items()
        ],
        "browser_rendered": False,
        "retained_study": retained_study,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--origin", default=ORIGIN)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--retained-study",
        help="Exact previously published Study generation for a runtime-only release",
    )
    args = parser.parse_args()
    result = verify(args.directory, args.origin.rstrip("/"), args.retained_study)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {key: result[key] for key in ("scope", "checks_passed", "browser_rendered")}, indent=2
        )
    )
