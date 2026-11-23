#!/usr/bin/env python3
"""Publish BalVoice trained checkpoints and supporting files to Hugging Face.

Run from a checked-out BalVoice-Robot-Control repository after `hf auth login`:
    python -m pip install -U huggingface_hub
    python scripts/publish_huggingface.py

The upload is only performed when this script is executed by the repository owner.
It never opens serial ports or controls motors.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "shah-bakhsh/BalVoice-Robot-Control"
MODEL_FILES = [
    "balochi_model_v02.joblib",
    "research_dual_models/balochi_cnn_final.pt",
    "research_dual_models/balochi_cnn_numpy.npz",
    "research_dual_models/balochi_svm_final.joblib",
]
SUPPORT_FILES = [
    "balochi_features.py",
    "balochi_v02.py",
    "research_dual_models/balochi_features.py",
    "research_dual_models/balochi_v02.py",
    "research_dual_models/cnn_runtime.py",
    "research_dual_models/dual_recognizer.py",
    "research_dual_models/evaluation.json",
    "research_dual_models/test_dual.py",
    "research_dual_models/requirements_pi.txt",
    "research_dual_models/README.md",
    "research_dual_models/train_dual.py",
    "research_dual_models/prep.py",
    "research_dual_models/export_numpy.py",
    "research_dual_models/requirements_train.txt",
    "MODEL_SHA256SUMS",
]
MODEL_CARD = """---
language:
- bal
tags:
- audio
- keyword-spotting
- robotics
- balochi
- speech-classification
- experimental
license: other
license_name: no-license-selected
---

# BalVoice Robot Control — Balochi voice-command research

Experimental speech-command models for a four-wheel robot using a Raspberry Pi 5 and Arduino Mega 2560.

**WARNING:** These checkpoints are research prototypes, NOT safe autonomous vehicle control systems.
Use for recognition-only testing; never enable motors based solely on these predictions.

## Models

| Checkpoint | Description |
| --- | --- |
| `balochi_model_v02.joblib` | Original MFCC/SVM used by the legacy bilingual voice controller |
| `research_dual_models/balochi_svm_final.joblib` | Research MFCC/SVM comparison model |
| `research_dual_models/balochi_cnn_final.pt` | Experimental PyTorch log-mel CNN |
| `research_dual_models/balochi_cnn_numpy.npz` | NumPy/SciPy inference export of CNN |

Supported Balochi commands (Latin transcription):
- `bosht` = stop (S)
- `dema bro` = forward (F)
- `poshta bro` = backward (B)
- `chapen kasha bro` = left (L)
- `rasten kash a bro` = right (R)

## Dataset and evaluation

The research comparison used 226 unique recordings in six classes
(five commands and noise), after removing three duplicate clips from 229.
Shuffled three-fold cross-validation recorded:
- SVM: **69.0%** (156/226)
- CNN: **72.1%** (163/226)

The CNN misclassified 12 of the 25 noise clips. Results are **not**
independent-speaker or real-world driving accuracy; low confidence and
false positives have also occurred in phone tests. Original recordings
are excluded for privacy and consent reasons.

## Usage

See the Python inference code and requirements in `research_dual_models/`.
Load `.joblib` and `.pt` files only from trusted sources because model
deserialization can execute arbitrary code. Check checksums before loading.

Python inference on Raspberry Pi: start with
`research_dual_models/requirements_pi.txt` and
`research_dual_models/test_dual.py`.

The English Vosk model is a **separate third-party model**, and is not
included here. The CNN is **not** the active model in the legacy
integrated motor application.

## Source code and documentation

[GitHub: shah-bakhsh/BalVoice-Robot-Control](https://github.com/shah-bakhsh/BalVoice-Robot-Control)

Model weights and source are supplied for research and evaluation.
**No open-source license is granted by default**; contact the repository
owner for redistribution permissions. Third-party packages retain their
own licenses.
"""

def validate(repo_root: Path) -> None:
    missing = [f for f in MODEL_FILES + SUPPORT_FILES if not (repo_root / f).is_file()]
    if missing:
        raise SystemExit("Missing required files:\n" + "\n".join(missing))
    if any((repo_root / p).stat().st_size == 0 for p in MODEL_FILES):
        raise SystemExit("One or more checkpoint files are empty.")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Hugging Face model repo ID")
    parser.add_argument("--dry-run", action="store_true", help="Check files without uploading")
    args = parser.parse_args()
    validate(ROOT)
    with TemporaryDirectory(prefix="balvoice_hf_") as temp:
        staging = Path(temp)
        for name in MODEL_FILES + SUPPORT_FILES:
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        (staging / "README.md").write_text(MODEL_CARD, encoding="utf-8")
        manifest = []
        for p in MODEL_FILES:
            raw = (ROOT / p).read_bytes()
            manifest.append(f"{hashlib.sha256(raw).hexdigest()}  {p}")
        (staging / "SHA256SUMS.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
        print(f"Repo: {args.repo}")
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                print(f"  {p.relative_to(staging)} ({p.stat().st_size:,} bytes)")
        if args.dry_run:
            print("Dry run complete. Nothing uploaded.")
            return
        api = HfApi(token=os.getenv("HF_TOKEN") or None)
        user = api.whoami()
        print(f"Authenticated as: {user.get('name', 'unknown')}")
        api.create_repo(repo_id=args.repo, repo_type="model", exist_ok=True)
        result = api.upload_folder(
            folder_path=str(staging),
            repo_id=args.repo,
            repo_type="model",
            commit_message="Publish BalVoice Balochi model checkpoints and evaluation",
        )
        print(f"Uploaded successfully: {result}")
        listed = {item.rfilename for item in api.list_repo_tree(
            repo_id=args.repo, repo_type="model", recursive=True)
            if hasattr(item, "rfilename")}
        required = set(MODEL_FILES + SUPPORT_FILES + ["README.md", "SHA256SUMS.txt"])
        # Check using list_repo_files to support multiple hub versions.
        listed = set(api.list_repo_files(repo_id=args.repo, repo_type="model"))
        missing = required - listed
        if missing:
            raise SystemExit("Upload returned but verification missing: " + str(sorted(missing)))
        print(f"Verified {len(required)} expected files on Hugging Face.")

if __name__ == "__main__":
    main()
