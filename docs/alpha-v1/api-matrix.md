# Ma trận API Alpha V1

Nguồn: decorator trong backend/app/api; 55 operations, 7 stub. Có handler không tự chứng minh đã chạy thành công. Đối chiếu báo cáo kiểm thử và OpenAPI trước khi mở tính năng.

| Method | Path | Trạng thái | Nhóm |
|---|---|---|---|
| GET | `/v1/consent/current` | Có handler; xem báo cáo kiểm thử | account |
| POST | `/v1/consent` | Có handler; xem báo cáo kiểm thử | account |
| DELETE | `/v1/consent` | Có handler; xem báo cáo kiểm thử | account |
| GET | `/v1/me` | Có handler; xem báo cáo kiểm thử | account |
| PATCH | `/v1/me` | Có handler; xem báo cáo kiểm thử | account |
| GET | `/v1/me/data` | Có handler; xem báo cáo kiểm thử | account |
| DELETE | `/v1/me` | Có handler; xem báo cáo kiểm thử | account |
| POST | `/v1/admin/users/import` | Ngoài Alpha — 501 | admin |
| POST | `/v1/admin/users/import/{batch_id}/confirm` | Ngoài Alpha — 501 | admin |
| POST | `/v1/auth/activate` | Có handler; xem báo cáo kiểm thử | auth |
| POST | `/v1/auth/staff/login` | Có handler; xem báo cáo kiểm thử | auth |
| POST | `/v1/auth/refresh` | Có handler; xem báo cáo kiểm thử | auth |
| POST | `/v1/auth/logout` | Có handler; xem báo cáo kiểm thử | auth |
| GET | `/v1/cards/due` | Có handler; xem báo cáo kiểm thử | cards |
| POST | `/v1/cards/{card_id}/reviews` | Có handler; xem báo cáo kiểm thử | cards |
| PATCH | `/v1/cards/{card_id}` | Có handler; xem báo cáo kiểm thử | cards |
| GET | `/v1/decks` | Có handler; xem báo cáo kiểm thử | cards |
| POST | `/v1/chat/sessions` | Có handler; xem báo cáo kiểm thử | chat |
| GET | `/v1/chat/sessions` | Có handler; xem báo cáo kiểm thử | chat |
| GET | `/v1/chat/sessions/{session_id}/messages` | Có handler; xem báo cáo kiểm thử | chat |
| POST | `/v1/chat/sessions/{session_id}/messages` | Có handler; xem báo cáo kiểm thử | chat |
| POST | `/v1/chat/suggestions/{suggestion_id}/accept` | Có handler; xem báo cáo kiểm thử | chat |
| GET | `/v1/passages/{passage_id}` | Có handler; xem báo cáo kiểm thử | chat |
| POST | `/v1/messages/{message_id}/rating` | Có handler; xem báo cáo kiểm thử | chat |
| GET | `/v1/admin/dashboard/overview` | Có handler; xem báo cáo kiểm thử | dashboard |
| GET | `/v1/admin/dashboard/export` | Có handler; xem báo cáo kiểm thử | dashboard |
| GET | `/v1/exams` | Có handler; xem báo cáo kiểm thử | exams |
| POST | `/v1/exams/{form_id}/attempts` | Có handler; xem báo cáo kiểm thử | exams |
| GET | `/v1/attempts/{attempt_id}` | Có handler; xem báo cáo kiểm thử | exams |
| PUT | `/v1/attempts/{attempt_id}/answers/{question_id}` | Có handler; xem báo cáo kiểm thử | exams |
| POST | `/v1/attempts/{attempt_id}/submit` | Có handler; xem báo cáo kiểm thử | exams |
| GET | `/v1/attempts/{attempt_id}/results` | Có handler; xem báo cáo kiểm thử | exams |
| GET | `/v1/attempts/{attempt_id}/items/{question_id}` | Có handler; xem báo cáo kiểm thử | exams |
| GET | `/v1/home` | Có handler; xem báo cáo kiểm thử | home |
| GET | `/v1/modules` | Có handler; xem báo cáo kiểm thử | modules |
| GET | `/v1/modules/{module_id}` | Có handler; xem báo cáo kiểm thử | modules |
| GET | `/v1/practice-sets/{set_id}` | Có handler; xem báo cáo kiểm thử | practice |
| POST | `/v1/practice-sets/{set_id}/responses` | Có handler; xem báo cáo kiểm thử | practice |
| POST | `/v1/practice-sets/{set_id}/complete` | Có handler; xem báo cáo kiểm thử | practice |
| GET | `/v1/progress/skills` | Có handler; xem báo cáo kiểm thử | progress |
| GET | `/v1/progress/rhythm` | Có handler; xem báo cáo kiểm thử | progress |
| POST | `/v1/reports` | Ngoài Alpha — 501 | reports |
| GET | `/v1/review/queue` | Ngoài Alpha — 501 | review |
| GET | `/v1/review/items/{item_id}` | Ngoài Alpha — 501 | review |
| POST | `/v1/review/items/{item_id}/decisions` | Ngoài Alpha — 501 | review |
| GET | `/v1/review/reports` | Ngoài Alpha — 501 | review |
| GET | `/v1/session/today` | Có handler; xem báo cáo kiểm thử | session |
| GET | `/v1/session/today/practice` | Có handler; xem báo cáo kiểm thử | session |
| POST | `/v1/session/today/practice/responses` | Có handler; xem báo cáo kiểm thử | session |
| POST | `/v1/session/today/practice/complete` | Có handler; xem báo cáo kiểm thử | session |
| GET | `/v1/units/{unit_id}/next` | Có handler; xem báo cáo kiểm thử | units |
| POST | `/v1/units/{unit_id}/responses` | Có handler; xem báo cáo kiểm thử | units |
| POST | `/v1/units/{unit_id}/advance` | Có handler; xem báo cáo kiểm thử | units |
| POST | `/v1/items/{question_id}/explain` | Có handler; xem báo cáo kiểm thử | units |
| POST | `/v1/items/{question_id}/hint` | Có handler; xem báo cáo kiểm thử | units |

Frontend gọi `/api/v1`; Vite bỏ `/api` trước khi chuyển tới FastAPI. `/health` và `/openapi.json` không nằm dưới `/v1`.

`POST /v1/practice-sets` chưa có và nằm ngoài Alpha. Library card, inbox, bookmark và study-plan chưa có API đồng bộ. Giữ UI chưa hỗ trợ cho các chức năng đó.

Tạo lại bằng `py -3.13 scripts/api-matrix.py`.
