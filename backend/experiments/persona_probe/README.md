# Persona probe

Thực nghiệm dev/test: chatbot có đổi câu trả lời theo năng lực người học không, và có còn bám tài liệu không.
Người học là **giả lập** ([profiles.yaml](profiles.yaml)). Không dùng dữ liệu người thật.

| File | Vai trò |
|---|---|
| `profiles.yaml` | 5 người học giả: tín hiệu Business, tín hiệu chat, mong đợi |
| `questions.yaml` | 4 câu hỏi, mỗi câu gắn với một chủ đề trong `mastery` |
| `run.py` | Chạy pipeline thật (truy xuất, mô hình, post-check) cho C0 và từng profile, lặp `--repeats` lần |
| `summarize.py` | Gộp `results.jsonl` thành bảng tỷ lệ đạt (chỉ dùng thư viện chuẩn) |
| `find_q.py` | Kiểm tra câu hỏi nào tìm được đoạn tài liệu |

Lớp người học chạy qua code thật ở `app/chat/personalize.py`. Riêng `Signals` được lấy từ `profiles.yaml`
thay vì bảng `mastery`, vì Chat không được ghi vào bảng của Business.

## Chạy

Image của container chat có thể cũ hơn nhánh này, nên phải đưa code nhánh này vào `/tmp` (rootfs chỉ đọc, `docker cp` không dùng được):

```sh
cd backend
tar cf - --exclude=__pycache__ app config config.yaml experiments/persona_probe/*.py experiments/persona_probe/*.yaml \
  | docker exec -i docprep-phase1-chat-1-1 sh -c 'mkdir -p /tmp/pp/backend && tar xf - -C /tmp/pp/backend'
docker exec -w /tmp/pp/backend -e PYTHONPATH=/tmp/pp/backend \
  -e YHDP_ANTHROPIC_MODEL=claude-haiku-5-5 -e YHDP_ANTHROPIC_EFFORT=medium docprep-phase1-chat-1-1 \
  python experiments/persona_probe/run.py --provider anthropic --repeats 3 --out /tmp/pp/out
docker exec docprep-phase1-chat-1-1 tar cf - -C /tmp/pp out | tar xf - -C experiments/persona_probe/
python experiments/persona_probe/summarize.py experiments/persona_probe/out/<run>/results.jsonl
```

Trên Git Bash ở Windows, thêm `MSYS_NO_PATHCONV=1` trước các lệnh `docker exec`.

- Truy xuất giống worker thật: bge-m3 + full-text, gộp RRF (cần Ollama và index của release đang bật).
- Mỗi lượt có quy tắc gọi model 3 lần (tầng A, tầng B, NLI), cộng một lần judge. Gemini gói miễn phí chỉ có
  500 lượt/ngày; script tự dừng khi model lỗi 3 lần liên tiếp.
- Bao phủ được chấm so với tầng A của cùng lượt, vì tầng A tự chọn ý khác nhau giữa các lần chạy.
- Chỉ `out/20261119-final/` được commit; các lần chạy khác bị `.gitignore` bỏ qua.
