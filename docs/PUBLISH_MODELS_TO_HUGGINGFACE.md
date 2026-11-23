# Publish BalVoice models to Hugging Face

Target: https://huggingface.co/shah-bakhsh/BalVoice-Robot-Control

The connected Hugging Face plugin can list and create repos but does not currently expose a direct upload action. Its remote Jobs/Sandbox environment returned **402 Payment Required** during attempted publication. This guide provides a local publisher that uses your own Hugging Face authorization.

## Run on your Raspberry Pi or laptop

```bash
git clone https://github.com/shah-bakhsh/BalVoice-Robot-Control.git
cd BalVoice-Robot-Control
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U huggingface_hub
hf auth login
python scripts/publish_huggingface.py --dry-run
python scripts/publish_huggingface.py
```

A Hugging Face account with model-repository write permission is required. **Never commit your access token to GitHub.**

On Windows PowerShell, activate your environment with `.venv\\Scripts\\Activate.ps1`.

The script stages four model weight files, classifier/inference code, training scripts, measured evaluation results, checksums, and a model card, uploads them, then lists the remote files to verify publication.

## Important distinctions

- The **original integrated SVM** is different from the research **CNN** and **SVM**.
- The research CNN and SVM are for **recognition-only testing**, not live motor driving.
- English Vosk model weights are external and not redistributed.
- No raw audio recordings or private Tailscale credentials are uploaded.
- `.joblib` and `.pt` checkpoints should be loaded only from trusted sources.
- No license is selected yet. Do not imply an open-source redistribution license.
