"""Temporary: archive ICP's classification document (which headings its "consumption
without housing" leaves out), so section ④'s rent can be described from the publisher's
own text (this project's sandbox cannot reach it; the pipeline in GitHub Actions can).
Nothing here is parsed or published: the snapshots ("probe/...") belong to no source in
sources_meta.  To be removed once read."""
from __future__ import annotations

from ..fetch import Fetcher, FetchError
from ..model import Obs

PROBES = [
    ("probe/icp/classification_nonh", "https://thedocs.worldbank.org/en/doc/606871598905573891-0050022020/render/ICPClassificaitonwithNonH.pdf", "pdf"),
    ("probe/icp/vc_tech_3", "https://www.worldbank.org/en/programs/icp/brief/VC_Tech_3", "html"),
]


def collect(f: Fetcher) -> list[Obs]:
    if f.offline:
        return []
    for key, url, ext in PROBES:
        try:
            snap = f.get(key, url, ext=ext, retries=1)
            print(f"[probe] {key}: {len(snap.read())} bytes", flush=True)
        except FetchError as exc:
            print(f"[probe] {key}: {exc}", flush=True)
    return []
