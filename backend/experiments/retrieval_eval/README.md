# Bộ đánh giá tìm kiếm (silver)

Đo chất lượng tìm tài liệu của chat trên release đang bật, để so các phiên bản tìm kiếm
(reranker, gate, tách từ, từ đồng nghĩa, chunking lại) với một mốc chung.

**Đây là bộ silver:** câu hỏi và nhãn do model tạo (Claude Haiku 5.5), chưa có chuyên gia duyệt.
Dùng tốt để so phiên bản A với B trên cùng bộ; không nên coi là con số tuyệt đối.

| File | Vai trò |
|---|---|
| `build_set.py` | Tạo bộ câu hỏi và nhãn (pooling) |
| `run_eval.py` | Đo tìm kiếm hiện tại trên bộ đó; không gọi model, chỉ embed câu hỏi bằng bge-m3 |
| `common.py` | Gateway, hai đường tìm kiếm giống chat thật |
| `silver_set.jsonl` | Bộ câu hỏi đang dùng (111 câu, tạo 22/11/2026, seed 20261122) |
| `out/<lần chạy>/` | `summary.md` và `results.jsonl` của mỗi lần đo |

## Cách tạo bộ câu hỏi

1. Lấy mẫu 90 đoạn, rải đều theo 3 văn bản và 51 chương; bỏ đoạn ngắn hơn 250 ký tự.
2. Với mỗi đoạn, model viết **một** câu hỏi kiểu sinh viên, theo 5 kiểu luân phiên (định nghĩa, số liệu,
   quy trình, phân biệt, lý do), bằng lời của mình (không chép cụm từ của đoạn), kèm một câu trích để
   chứng minh đoạn trả lời được. Câu trích không có trong đoạn thì bỏ.
3. Câu ngoài phạm vi: model viết 30 câu cùng lĩnh vực mà các chương không trả lời, gồm loại **gần**
   (cùng nhóm bệnh, chi tiết vắc xin, thuốc) và **xa**.
4. **Pooling** (như TREC): gộp top 30 của tìm kết hợp và top 30 của tìm từ khoá (tối đa 45 đoạn, xáo
   trộn), model đánh dấu đoạn nào trả lời được. Nhãn đúng = mọi đoạn trả lời được, nên các đoạn trùng
   nội dung cũng tính.
5. Lọc: câu trong phạm vi chỉ giữ khi chính đoạn nguồn được xác nhận; câu ngoài phạm vi chỉ giữ khi
   không đoạn nào trả lời được, kể cả một phần.

Kết quả lần tạo 22/11: giữ 86 câu trong phạm vi và 25 câu ngoài phạm vi; bỏ 4 câu không xác nhận được
nguồn và 5 câu "ngoài phạm vi" mà kho có trả lời.

## Giới hạn

- Câu hỏi sinh từ đoạn nên gọn và đúng trọng tâm hơn câu người học thật gõ.
- Cùng một model viết câu hỏi và gắn nhãn.
- Pooling chỉ thấy đoạn nằm trong top 30 của hai cách tìm hiện có: đoạn đúng nằm ngoài cả hai sẽ không
  được tính. Khi thêm cách tìm mới, nên gắn nhãn bổ sung cho các đoạn mới xuất hiện.

## Chạy

```sh
cd backend
# rootfs của container chỉ đọc: gửi code và bộ câu hỏi vào /tmp bằng tar
tar cf - --exclude=__pycache__ app config config.yaml experiments/retrieval_eval/*.py experiments/retrieval_eval/silver_set.jsonl \
  | docker exec -i docprep-phase1-chat-1-1 sh -c 'mkdir -p /tmp/re/backend && tar xf - -C /tmp/re/backend'
docker exec -w /tmp/re/backend/experiments/retrieval_eval \
  -e PYTHONPATH=/tmp/re/backend:/tmp/re/backend/experiments/retrieval_eval \
  -e YHDP_ANTHROPIC_MODEL=claude-haiku-5-5 docprep-phase1-chat-1-1 python run_eval.py --out /tmp/re/out
docker exec docprep-phase1-chat-1-1 tar cf - -C /tmp/re out | tar xf - -C experiments/retrieval_eval/
```

Trên Git Bash ở Windows, thêm `MSYS_NO_PATHCONV=1` trước các lệnh `docker exec`.

Tạo lại bộ câu hỏi (`build_set.py`) tốn khoảng 200 lượt gọi Haiku (dưới 0,5 USD). Chỉ tạo lại khi
release thay đổi; còn để so các phiên bản tìm kiếm thì giữ nguyên bộ.
