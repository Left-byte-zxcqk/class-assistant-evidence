from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen


BASE = "https://zanhealth.top/class-assistant/api/usage/evidence"


def previous_month() -> str:
    last = date.today().replace(day=1) - timedelta(days=1)
    return last.strftime("%Y-%m")


def write_once(path: Path, body: bytes) -> None:
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError(f"refusing to overwrite sealed evidence: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=previous_month())
    args = parser.parse_args()
    request = Request(f"{BASE}/{args.month}", headers={"User-Agent": "class-assistant-evidence/1"})
    with urlopen(request, timeout=30) as response:
        body = response.read()
        server_digest = response.headers.get("X-Content-SHA256", "").lower()
    digest = hashlib.sha256(body).hexdigest()
    if not server_digest or digest != server_digest:
        raise RuntimeError("snapshot SHA-256 does not match the server header")
    payload = json.loads(body)
    if payload.get("month") != args.month:
        raise RuntimeError("snapshot month mismatch")

    snapshots = Path("snapshots")
    target = snapshots / f"usage-{args.month}.json"
    write_once(target, body)
    write_once(snapshots / f"usage-{args.month}.sha256", f"{digest}  {target.name}\n".encode("ascii"))

    totals = payload["usage"]["totals"]
    report = f"""# {args.month} 月度运行证据

- 访问会话：{totals['session_started']}
- 日均估算活跃设备：{totals['average_active_devices']}
- 峰值估算活跃设备：{totals['peak_active_devices']}
- 核心栏目查看：{totals['feature_views']}
- 任务详情展开：{totals['task_detail_open']}
- 资料链接点击：{totals['resource_click']}
- 摘要复制：{totals.get('task_summary_copy', 0)}
- 链接复制：{totals.get('task_link_copy', 0)}
- 独立链接打开：{totals.get('task_permalink_open', 0)}
- SHA-256：`{digest}`

{payload.get('periodNote') or '本月为完整自然月统计期。'}

“估算活跃设备”不是独立用户数，也不表示班级使用率。完整口径与隐私边界见 [METHODOLOGY.md](../METHODOLOGY.md)。
""".encode("utf-8")
    write_once(Path("reports") / f"{args.month}.md", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
