# Ma trận API Phase 1

Nguồn: OpenAPI của hai ứng dụng; 59 operations. Không có operation trùng giữa hai runtime.

Có handler không tự chứng minh luồng đã chạy thành công; xem [báo cáo kiểm thử](verification.md). Các endpoint 501 giữ nguyên ngoài phạm vi.

| Method | Path | Operation | Runtime | Trạng thái |
|---|---|---|---|---|
| GET | `/v1/admin/dashboard/export` | `export_overview` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/admin/dashboard/overview` | `get_overview` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/admin/users/import` | `import_users` | business | Ngoài phạm vi — 501 |
| POST | `/v1/admin/users/import/{batch_id}/confirm` | `confirm_import` | business | Ngoài phạm vi — 501 |
| GET | `/v1/attempts/{attempt_id}` | `get_attempt` | business | Có handler; xem báo cáo kiểm thử |
| PUT | `/v1/attempts/{attempt_id}/answers/{question_id}` | `save_answer` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/attempts/{attempt_id}/items/{question_id}` | `get_attempt_item` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/attempts/{attempt_id}/results` | `get_attempt_results` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/attempts/{attempt_id}/submit` | `submit_attempt` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/auth/activate` | `activate` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/auth/logout` | `logout` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/auth/refresh` | `refresh` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/auth/staff/login` | `staff_login` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/cards/due` | `list_due_cards` | business | Có handler; xem báo cáo kiểm thử |
| PATCH | `/v1/cards/{card_id}` | `patch_card` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/cards/{card_id}/reviews` | `review_card` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/chat/sessions` | `list_chat_sessions` | chat | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/chat/sessions` | `create_chat_session` | chat | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/chat/sessions/{session_id}/messages` | `list_chat_messages` | chat | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/chat/sessions/{session_id}/messages` | `ask_question` | chat | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/chat/suggestions/{suggestion_id}/accept` | `accept_suggestion` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/chat/turns/active` | `active_turn` | chat | Có handler; xem báo cáo kiểm thử |
| DELETE | `/v1/chat/turns/{turn_id}` | `cancel_turn` | chat | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/chat/turns/{turn_id}` | `get_turn` | chat | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/chat/turns/{turn_id}/events` | `turn_events` | chat | Có handler; xem báo cáo kiểm thử |
| DELETE | `/v1/consent` | `withdraw_consent` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/consent` | `give_consent` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/consent/current` | `get_consent_text` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/decks` | `list_decks` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/exams` | `list_exams` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/exams/{form_id}/attempts` | `start_attempt` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/home` | `get_home` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/items/{question_id}/explain` | `explain_item` | chat | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/items/{question_id}/hint` | `get_hint` | chat | Có handler; xem báo cáo kiểm thử |
| DELETE | `/v1/me` | `delete_me` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/me` | `get_me` | business | Có handler; xem báo cáo kiểm thử |
| PATCH | `/v1/me` | `patch_me` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/me/data` | `export_my_data` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/messages/{message_id}/rating` | `rate_message` | chat | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/modules` | `list_modules` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/modules/{module_id}` | `get_module` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/passages/{passage_id}` | `get_passage` | chat | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/practice-sets/{set_id}` | `get_practice_set` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/practice-sets/{set_id}/complete` | `complete_practice_set` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/practice-sets/{set_id}/responses` | `answer_practice_set` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/progress/rhythm` | `get_progress_rhythm` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/progress/skills` | `get_progress_skills` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/reports` | `create_report` | business | Ngoài phạm vi — 501 |
| GET | `/v1/review/items/{item_id}` | `get_review_item` | business | Ngoài phạm vi — 501 |
| POST | `/v1/review/items/{item_id}/decisions` | `decide_review` | business | Ngoài phạm vi — 501 |
| GET | `/v1/review/queue` | `list_review_queue` | business | Ngoài phạm vi — 501 |
| GET | `/v1/review/reports` | `list_review_reports` | business | Ngoài phạm vi — 501 |
| GET | `/v1/session/today` | `get_session_today` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/session/today/practice` | `get_session_practice` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/session/today/practice/complete` | `complete_session_practice` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/session/today/practice/responses` | `answer_session_practice` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/units/{unit_id}/advance` | `unit_advance` | business | Có handler; xem báo cáo kiểm thử |
| GET | `/v1/units/{unit_id}/next` | `unit_next` | business | Có handler; xem báo cáo kiểm thử |
| POST | `/v1/units/{unit_id}/responses` | `unit_answer` | business | Có handler; xem báo cáo kiểm thử |

Frontend gọi `/api/v1`; Caddy bỏ `/api`. `/health`, `/readyz`, `/metrics` và `/openapi.json` không thuộc hợp đồng `/v1`.

Tạo lại: `backend/.venv/Scripts/python.exe -X utf8 scripts/api-matrix.py --phase1`.
