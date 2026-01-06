from __future__ import annotations

import time
from copy import deepcopy
from threading import Lock


class ManualOcrProgressManager:
    """Track OCR progress for each session so the frontend can poll."""

    def __init__(self) -> None:
        self._states: dict[str, dict] = {}
        self._lock = Lock()

    def start_session(self, session_id: str, *, product_name: str, total_files: int) -> None:
        state = {
            "session_id": session_id,
            "product_name": product_name,
            "stage": "等待开始",
            "detail": "准备执行 OCR",
            "percent": 0,
            "status": "active",
            "current_file": None,
            "current_page": None,
            "processed_files": 0,
            "total_files": total_files,
            "ocr_completed": 0,
            "ocr_total": 0,
            "result": None,
            "updated_at": time.time(),
        }
        with self._lock:
            self._states[session_id] = state

    def update(self, session_id: str, **payload) -> None:
        with self._lock:
            state = self._states.get(session_id)
            if not state:
                return
            state.update(payload)
            state["updated_at"] = time.time()
            self._recalculate_percent(state)

    def increment_processed_files(self, session_id: str, delta: int = 1) -> None:
        with self._lock:
            state = self._states.get(session_id)
            if not state:
                return
            state["processed_files"] = state.get("processed_files", 0) + delta
            state["updated_at"] = time.time()
            self._recalculate_percent(state)

    def set_ocr_totals(self, session_id: str, total_pages: int) -> None:
        with self._lock:
            state = self._states.get(session_id)
            if not state:
                return
            state["ocr_total"] = total_pages
            state["updated_at"] = time.time()
            self._recalculate_percent(state)

    def increment_ocr_completed(self, session_id: str, delta: int = 1) -> None:
        with self._lock:
            state = self._states.get(session_id)
            if not state:
                return
            state["ocr_completed"] = state.get("ocr_completed", 0) + delta
            state["updated_at"] = time.time()
            self._recalculate_percent(state)

    def get_state(self, session_id: str) -> dict | None:
        with self._lock:
            state = self._states.get(session_id)
            return deepcopy(state) if state else None

    def mark_complete(self, session_id: str, success: bool, error: str | None = None) -> None:
        with self._lock:
            state = self._states.get(session_id)
            if not state:
                return
            state["status"] = "success" if success else "exception"
            state["stage"] = "完成" if success else "出错"
            state["detail"] = "OCR 已完成" if success else (error or "OCR 失败")
            state["percent"] = 100 if success else state.get("percent", 95)
            if error:
                state["error"] = error
            state["updated_at"] = time.time()

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._states.pop(session_id, None)

    def _recalculate_percent(self, state: dict) -> None:
        total_pages = state.get("ocr_total") or 0
        completed = state.get("ocr_completed") or 0
        if total_pages > 0:
            progress = int(min(99, max(0, round((completed / total_pages) * 100))))
            state["percent"] = max(state.get("percent", 0), progress)


progress_manager = ManualOcrProgressManager()
