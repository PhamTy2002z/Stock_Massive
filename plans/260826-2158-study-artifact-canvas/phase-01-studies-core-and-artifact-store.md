# Phase 01 — Studies core + agent_artifact store

Nhóm A. Không phụ thuộc phase nào. Mở đường cho 03/04.

## Context

Study là đơn vị mới: recipe phân tích có tên, có version, deterministic.
Khuôn mẫu bắt chước là `src/stocks/signals/` (SignalField 9 thuộc tính, kiểm
hai chiều lúc import trong `agent/tools/signals.py::_check_the_catalog_holds`)
— không phát minh khuôn mới.

## Requirements

- Package `apps/api/src/studies/` độc lập với `src/agent/` (agent import
  studies, không ngược lại — dependency rule 2 của SOT).
- Bảng `agent_artifact` persist kết quả; as-of đóng băng lúc tạo.
- Kiểm registry hai chiều lúc import: study đăng ký thiếu display
  name/description → ImportError.

## Files

| File | Việc |
|---|---|
| `src/studies/__init__.py` | export public: `StudyDefinition`, `StudyResult`, `Frame`, `REGISTRY`, `run` |
| `src/studies/contracts.py` | dataclasses (dưới) |
| `src/studies/registry.py` | `register()`, `REGISTRY: dict[str, StudyDefinition]`, kiểm import-time |
| `src/studies/runner.py` | `run(name, params, *, session) -> StoredArtifact`: validate params theo schema → `compute` → `view` → persist |
| `src/alpha/models.py` | model `AgentArtifact` (bảng `agent_artifact`) |
| `alembic/versions/<new>` | revision tạo `agent_artifact` — additive, downgrade drop |
| `tests/studies/test_contracts.py`, `test_registry.py`, `test_runner.py` | unit |
| `CLAUDE.md` | amend freeze + ghi quyết định canvas dynamic đã chốt |

## Shapes (chốt ở phase này, các phase sau không đổi)

```python
@dataclass(frozen=True)
class Frame:                      # một dãy/ma trận, KHÔNG vào context model
    kind: Literal["series", "matrix", "table"]
    columns: tuple[str, ...]      # tên cột; matrix: cột = bucket labels
    rows: tuple[tuple[Any, ...], ...]
    unit: str | None
    labels: Mapping[str, str]     # column -> nhãn tiếng Việt

@dataclass(frozen=True)
class StudyResult:
    headline: Mapping[str, Any]   # ≤ ~300 token — phần DUY NHẤT model thấy
    frames: Mapping[str, Frame]
    provenance: Provenance        # source, as_of, sessions_used, health, reason

@dataclass(frozen=True)
class StudyDefinition:
    name: str                     # vd "intraday_liquidity_profile"
    version: int
    question: str                 # câu hỏi study trả lời — hiện trong list_studies
    display_name: str             # tiếng Việt, cho rail/tool event
    params_schema: Mapping        # JSON schema object — model điền
    requires: tuple[str, ...]     # tiền đề dữ liệu, vd ("intraday_bar_15m",)
    compute: Callable[[StudyContext], StudyResult]
    view: Callable[[StudyResult], CanvasSpec]

CanvasSpec = {"title": str, "blocks": [
    {"widget": str, "widget_version": int, "frame": str,  # key vào frames
     "options": Mapping}          # options typed per widget, server-chosen
]}
```

`agent_artifact`: `id UUID PK · turn_id FK agent_turn · thread_id FK
agent_thread · study_name text · study_version int · params jsonb · frames
jsonb · canvas_spec jsonb · provenance jsonb · created_at timestamptz`.
Index: `thread_id`, `turn_id`.

## Steps

1. Backup DB: `docker compose exec db pg_dump -U postgres stockmassive | gzip > backups/pre-agent-artifact-$(date +%y%m%d).sql.gz`.
   Kiểm `alembic heads` = đúng 1 head trước khi tạo revision (DB dev chia sẻ
   với stack strict 8001 + worktree khác — audit N12).
2. Viết `contracts.py` + `registry.py` (kiểm import-time: name trùng → raise;
   thiếu question/display_name → raise; `view(result)` tham chiếu frame key
   không tồn tại → test bắt).
3. **Params một nguồn (audit N8):** mỗi study khai params bằng **pydantic
   model**; JSON schema model-facing sinh từ `model_json_schema()`; server
   validate bằng chính model đó. jsonschema lib KHÔNG có trong requirements
   và không thêm.
4. **Contract fixtures (audit N1, N7):** phát hành
   `contracts/canvas-widget-catalog.json` (repo root — danh mục widget
   name+version, pytest và vitest cùng đọc) + `contracts/fixtures/
   artifact-intraday-liquidity.json` (một artifact payload mẫu đầy đủ:
   canvasSpec + frames + provenance, sinh từ golden fixture của phase 03 —
   tạm handcraft ở phase này để phase 05 bước 0 khởi động ngay).
5. Model + alembic revision; `docker compose restart api`; `alembic upgrade head`.
6. `runner.py`.
7. Amend CLAUDE.md (mục Branch & freeze của plan.md).
8. Tests, gồm test pytest đọc `canvas-widget-catalog.json` khớp catalog trong
   code.

## Validation

- `make test` xanh; test import-time check có case negative.
- `alembic downgrade -1 && alembic upgrade head` chạy sạch trên DB dev.

## Risk & rollback

- Rủi ro thấp — toàn bộ additive. Rollback: downgrade revision (bảng mới,
  drop được), revert commit.
