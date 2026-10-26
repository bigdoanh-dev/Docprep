"""Regenerate the Alpha API inventory from router decorators (standard library only)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rows = []
for source in sorted((ROOT / "backend/app/api").glob("*.py")):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name) and dec.func.value.id == "router"
                    and dec.func.attr in ("get", "post", "put", "patch", "delete")):
                continue
            stub = any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                       and call.func.id == "not_implemented" for call in ast.walk(node))
            rows.append((dec.func.attr.upper(), "/v1" + ast.literal_eval(dec.args[0]), stub, source.stem))

text = ("# Ma trận API Alpha V1\n\n"
        f"Nguồn: decorator trong backend/app/api; {len(rows)} operations, {sum(r[2] for r in rows)} stub. "
        "Có handler không tự chứng minh đã chạy thành công. Đối chiếu báo cáo kiểm thử và OpenAPI trước khi mở tính năng.\n\n"
        "| Method | Path | Trạng thái | Nhóm |\n|---|---|---|---|\n")
for method, route, stub, group in rows:
    status = "Ngoài Alpha — 501" if stub else "Có handler; xem báo cáo kiểm thử"
    text += f"| {method} | `{route}` | {status} | {group} |\n"
text += ("\nFrontend gọi `/api/v1`; Vite bỏ `/api` trước khi chuyển tới FastAPI. "
         "`/health` và `/openapi.json` không nằm dưới `/v1`.\n\n"
         "`POST /v1/practice-sets` chưa có và nằm ngoài Alpha. Library card, inbox, bookmark và study-plan "
         "chưa có API đồng bộ. Giữ UI chưa hỗ trợ cho các chức năng đó.\n\n"
         "Tạo lại bằng `py -3.13 scripts/api-matrix.py`.\n")
dest = ROOT / "docs/alpha-v1/api-matrix.md"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(text, encoding="utf-8")
print(f"API matrix: {len(rows)} operations")
