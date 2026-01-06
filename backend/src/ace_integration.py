"""Helper utilities for running ACE adaptation from the backend API."""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

from .manual_ocr import MANUAL_OCR_ROOT

ACE_ROOT = Path(__file__).resolve().parents[2] / "agentic-context-engineering-main"
if ACE_ROOT.exists():
    if str(ACE_ROOT) not in sys.path:
        sys.path.insert(0, str(ACE_ROOT))
else:
    raise RuntimeError(f"ACE framework directory not found at {ACE_ROOT}")

EMPTY_DATASET_DIR = ACE_ROOT / "empty_dataset"
EMPTY_DATASET_DIR.mkdir(parents=True, exist_ok=True)

from ace_framework.config import Config, ExperimentConfig  # type: ignore  # noqa: E402
from ace_framework.config import ModelConfig  # type: ignore  # noqa: E402
from ace_framework.core.ace_framework import ACEFramework  # type: ignore  # noqa: E402


def _sanitize_part(value: Optional[str], fallback: str) -> str:
    if not value:
        return fallback
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    return cleaned or fallback


def _ace_sample_dir(session_id: str) -> Path:
    sanitized_session = _sanitize_part(session_id, "unknown-session")
    return MANUAL_OCR_ROOT / sanitized_session / "ace_samples"


class ACEManager:
    """Wrapper to keep an ACEFramework instance in memory and provide single-sample adaptation."""

    def __init__(self, playbook_type: str):
        # Force ACE agents to use qwen3-max unless caller intentionally overrides
        os.environ["ACE_LLM_MODEL"] = "dashscope/qwen3-max"
        os.environ.setdefault(
            "ACE_LLM_BASE_URL",
            os.environ.get(
                "DASHSCOPE_API_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
        )

        self.playbook_type = (playbook_type or "spec").strip() or "spec"
        results_dir = ACE_ROOT / "results" / self.playbook_type
        results_dir.mkdir(parents=True, exist_ok=True)

        model_config = ModelConfig(
            name="dashscope/qwen3-max",
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            base_url=os.environ.get("ACE_LLM_BASE_URL"),
        )
        experiment_config = ExperimentConfig(
            dataset_path=str(EMPTY_DATASET_DIR),
            num_samples=0,
            checkpoint_interval=1,
            output_dir=str(results_dir),
        )
        self.config = Config(model_config=model_config, experiment_config=experiment_config)
        self.framework = ACEFramework(self.config)
        self.lock = threading.Lock()

        # Load previous checkpoint if available so playbook persists between requests
        output_dir = Path(self.config.experiment.output_dir)
        if output_dir.exists():
            try:
                self.framework.load_checkpoint(str(output_dir))
            except Exception:
                pass

    def unlock(self):
        # Backward-compatible no-op. Kept to avoid breaking any external callers.
        return

    def store_external_result(
        self,
        *,
        question: str,
        prediction: str,
        ground_truth: str,
        is_correct: bool,
        algo_evaluation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store a result without running LLM reflection/curation.

        This is used by the spec evaluator fast-path: when algorithmic evaluation
        says the output is already correct, we still want metrics/history to move
        forward and persist artifacts under results/{playbook_type}.
        """

        with self.lock:
            self.framework.metrics.record_result(
                question=question,
                predicted=prediction,
                ground_truth=ground_truth,
                is_correct=is_correct,
                playbook_size=len(self.framework.playbook),
                algo_evaluation=algo_evaluation,
            )
            self.framework.save_results(self.config.experiment.output_dir)

            return {
                "generation": {
                    "reasoning": prediction,
                    "used_bullet_ids": [],
                    "final_answer": prediction,
                },
                "reflection": {
                    "error_identification": "",
                    "root_cause": "",
                    "key_insight": "",
                    "bullet_tags": [],
                    "is_correct": is_correct,
                },
                "correct": is_correct,
            }

    def attach_last_algo_evaluation(self, algo_evaluation: Dict[str, Any]) -> None:
        with self.lock:
            history = getattr(self.framework.metrics, "history", None)
            if not history:
                return
            history[-1]["algo_evaluation"] = algo_evaluation
            self.framework.save_results(self.config.experiment.output_dir)

    def force_last_metrics_correctness(self, is_correct: bool) -> None:
        """Force the correctness of the latest metrics record and recompute accuracy.

        ACEFramework currently records metrics based on Reflector.is_correct.
        For spec, we may compute correctness via deterministic evaluator; this
        helper makes metrics.json consistent with that evaluator.
        """

        with self.lock:
            history = getattr(self.framework.metrics, "history", None)
            if not history:
                return
            history[-1]["correct"] = bool(is_correct)

            # Recompute counters
            self.framework.metrics.processed = len(history)
            self.framework.metrics.correct = sum(1 for r in history if r.get("correct"))

            # Recompute accuracy field per record
            correct_so_far = 0
            for idx, record in enumerate(history, start=1):
                if record.get("correct"):
                    correct_so_far += 1
                record["step"] = idx
                record["accuracy"] = (correct_so_far / idx) * 100 if idx else 0.0

            self.framework.save_results(self.config.experiment.output_dir)

    def adapt_single_sample(self, question: str, context: str, ground_truth: str, verbose: bool = False) -> Dict[str, Any]:
        """Run ACE adaptation on a single sample and persist updated playbook/metrics."""
        with self.lock:
            result = self.framework.adapt_online(
                question=question,
                context=context,
                ground_truth=ground_truth,
                verbose=verbose,
            )
            # Persist state after each adaptation so generator can use latest playbook
            self.framework.save_results(self.config.experiment.output_dir)
            return result

    def adapt_with_prediction(
        self,
        question: str,
        context: str,
        prediction: str,
        ground_truth: str,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Run ACE adaptation with an externally supplied prediction."""
        with self.lock:
            result = self.framework.adapt_with_prediction(
                question=question,
                context=context,
                prediction=prediction,
                ground_truth=ground_truth,
                verbose=verbose,
            )
            self.framework.save_results(self.config.experiment.output_dir)
            return result

    def get_playbook_size(self) -> int:
        return len(self.framework.playbook)
    
    def get_playbook_snapshot(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.lock:
            bullets = [bullet.to_dict() for bullet in self.framework.playbook]
        if limit is not None and limit > 0:
            return bullets[-limit:]
        return bullets

    def remove_rule(self, rule_id: str) -> bool:
        if not rule_id:
            return False
        with self.lock:
            removed = self.framework.playbook.remove_bullet(rule_id)
            if removed:
                self.framework.save_results(self.config.experiment.output_dir)
            return removed


_ACE_MANAGERS: Dict[str, ACEManager] = {}
_ACE_MANAGERS_LOCK = threading.Lock()


def get_ace_manager(playbook_type: str) -> ACEManager:
    normalized = (playbook_type or "spec").strip().lower() or "spec"
    with _ACE_MANAGERS_LOCK:
        manager = _ACE_MANAGERS.get(normalized)
        if manager is None:
            manager = ACEManager(normalized)
            _ACE_MANAGERS[normalized] = manager
        return manager


# Backward-compatible alias (defaults to spec)
ace_manager = get_ace_manager("spec")


def _pending_sample_path(session_id: str, bom_code: Optional[str]) -> Path:
    sample_dir = _ace_sample_dir(session_id)
    suffix = f"_{_sanitize_part(bom_code, 'default')}" if bom_code else ""
    return sample_dir / f"pending{suffix}.json"


def save_pending_sample(
    session_id: str,
    bom_code: Optional[str],
    *,
    question: str,
    context: str,
    prediction: Dict[str, Any],
) -> Path:
    """Persist the latest generation context for later ACE training."""
    sample_dir = _ace_sample_dir(session_id)
    sample_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "question": question,
        "context": context,
        "prediction": prediction,
        "saved_at": datetime.utcnow().isoformat() + "Z",
    }
    pending_path = _pending_sample_path(session_id, bom_code)
    pending_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return pending_path


def load_pending_sample(session_id: str, bom_code: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load previously saved generation context for ACE training."""
    pending_path = _pending_sample_path(session_id, bom_code)
    if not pending_path.exists():
        return None
    try:
        return json.loads(pending_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_pending_sample(session_id: str, bom_code: Optional[str]) -> None:
    """Remove pending sample once ACE training is complete."""
    pending_path = _pending_sample_path(session_id, bom_code)
    if pending_path.exists():
        try:
            pending_path.unlink()
        except OSError:
            pass


def store_ace_sample(session_id: str, bom_code: Optional[str], sample: Dict[str, Any]) -> Path:
    """Persist raw ACE sample JSON for auditing."""
    sample_dir = _ace_sample_dir(session_id)
    sample_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    suffix = f"_{_sanitize_part(bom_code, 'default')}" if bom_code else ""
    sample_path = sample_dir / f"ace_sample{suffix}_{timestamp}.json"
    sample_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    return sample_path
