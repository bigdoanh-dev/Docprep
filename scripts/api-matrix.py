"""Regenerate the Alpha API inventory from router decorators (standard library only)."""
import ast
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase1', action='store_true', help='Inventory actual partitioned apps (backend dependencies required)')
args = parser.parse_args()
if args.phase1:
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.application import create_app
    from app.phase_routes import combined_openapi
    combined_openapi()  # Also rejects duplicate operations and conflicting schemas.
    stubs = set()
    for source in (ROOT / 'backend/app/api').glob('*.py'):
        for node in ast.parse(source.read_text(encoding='utf-8')).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'not_implemented'
                for call in ast.walk(node)
            ):
                stubs.add(node.name)
    rows = []
    for service in ('business', 'chat'):
        spec = create_app('mock', service=service).openapi()
        for path, methods in spec['paths'].items():
            for method, operation in methods.items():
                stub = operation['operationId'] in stubs
                rows.append((path, method.upper(), operation['operationId'], service, stub))
    lines = ['# Ma trận API Phase 1', '',
             f'Nguồn: OpenAPI của hai ứng dụng; {len(rows)} operations. Không có operation trùng giữa hai runtime.', '',
             'Có handler không tự chứng minh luồng đã chạy thành công; xem [báo cáo kiểm thử](verification.md). Các endpoint 501 giữ nguyên ngoài phạm vi.', '',
             '| Method | Path | Operation | Runtime | Trạng thái |', '|---|---|---|---|---|']
    for path, method, operation, service, stub in sorted(rows):
        status = 'Ngoài phạm vi — 501' if stub else 'Có handler; xem báo cáo kiểm thử'
        lines.append(f'| {method} | `{path}` | `{operation}` | {service} | {status} |')
    lines += ['', 'Frontend gọi `/api/v1`; Caddy bỏ `/api`. `/health`, `/readyz`, `/metrics` và `/openapi.json` không thuộc hợp đồng `/v1`.', '',
              'Tạo lại: `backend/.venv/Scripts/python.exe -X utf8 scripts/api-matrix.py --phase1`.', '']
    dest = ROOT / 'docs/phase1/api-matrix.md'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('\n'.join(lines), encoding='utf-8')
    print(f'Phase 1 API matrix: {len(rows)} operations')
    raise SystemExit(0)
rows = []
for source in sorted((ROOT / "backend/app/api").glob("*.py")):
    if source.stem == 'turns':
        continue  # Phase 1 replaces three Alpha handlers and adds four operations.
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
