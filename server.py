"""
pai2d serveur d'inférence FastAPI

Charge Qwen2-VL-2B-Instruct (ou un checkpoint QLoRA) une seule fois au démarrage,
puis sert les requêtes POST /predict du plugin GIMP continu.

Utilisation:
  pip install fastapi uvicorn[standard] torch transformers accelerate pillow peft

  # Modèle de base :
  MODEL_PATH=Qwen/Qwen2-VL-2B-Instruct uvicorn server:app --host 0.0.0.0 --port 8000

  # Adapter LoRA fine-tuné :
  MODEL_PATH=/chemin/vers/qwen2vl-gimp-lora uvicorn server:app --host 0.0.0.0 --port 8000
"""

import base64
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import BaseModel
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

# Configuration
MODEL_PATH: str = os.getenv("MODEL_PATH", "Qwen/Qwen2-VL-2B-Instruct")
CONFIDENCE_GATE: float = float(os.getenv("CONFIDENCE_GATE", "0.0"))
MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "12"))

VALID_COMMANDS: list[str] = [
    "brightness_contrast",
    "colorize",
    "desaturate",
    "edge_detect",
    "flip",
    "gaussian_blur",
    "hue_saturation",
    "invert",
    "posterize",
    "red_eye_removal",
    "rotation",
    "sharpen",
    "threshold",
]

_COMMANDS_BY_LENGTH = sorted(VALID_COMMANDS, key=len, reverse=True)

SYSTEM_PROMPT: str = (
    "You are a GIMP image-editing analysis assistant. "
    "You will be shown a composite image: the LEFT third is the ORIGINAL image, "
    "the MIDDLE third is the RESULT after exactly ONE GIMP operation was applied, "
    "and the RIGHT third is an amplified pixel-difference map (x15). "
    "Your task is to identify that single operation. "
    "Reply with ONLY the operation name from the provided list — "
    "no explanation, no punctuation."
)

_model: Optional[Qwen2VLForConditionalGeneration] = None
_processor: Optional[AutoProcessor] = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ai2d.server")


# Helpers
def _get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


# Chargement du modèle
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _processor

    is_lora = (
        os.path.exists(os.path.join(MODEL_PATH, "adapter_config.json"))
        and not os.path.exists(os.path.join(MODEL_PATH, "preprocessor_config.json"))
    )

    t0 = time.time()
    device = _get_device()
    logger.info("Target device: %s", device)

    if is_lora:
        from peft import PeftModel
        base_id = "Qwen/Qwen2-VL-2B-Instruct"
        logger.info("Adapter LoRA détecté : chargement base : %s", base_id)
        _processor = AutoProcessor.from_pretrained(base_id, trust_remote_code=True)
        base = Qwen2VLForConditionalGeneration.from_pretrained(
            base_id,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        logger.info("Application du LoRA depuis : %s", MODEL_PATH)
        _model = PeftModel.from_pretrained(base, MODEL_PATH)
        _model = _model.merge_and_unload()
    else:
        logger.info("Chargement processeur depuis : %s", MODEL_PATH)
        _processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
        logger.info("Chargement modèle depuis : %s", MODEL_PATH)
        _model = Qwen2VLForConditionalGeneration.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )

    _model = _model.to(device)
    _model.eval()
    logger.info("Modèle prêt en %.1f s sur %s.", time.time() - t0, device)

    yield  

    logger.info("Arrêt — libération du modèle.")
    del _model, _processor
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# Application FastAPI
app = FastAPI(
    title="PAI2D — Serveur d'inférence",
    description="Classificateur de commandes GIMP — Qwen2-VL-2B affiné avec QLoRA.",
    version="1.1.0",
    lifespan=lifespan,
)


# Schémas
class PredictRequest(BaseModel):
    image_b64: str


class PredictResponse(BaseModel):
    command: str
    confidence: float
    suppressed: bool


# Inférence
def _build_messages(valid_ops_str: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {
                    "type": "text",
                    "text": (
                        "The LEFT third of the image is BEFORE, "
                        "the MIDDLE third is AFTER one GIMP operation was applied, "
                        "and the RIGHT third is the amplified difference (×15).\n\n"
                        f"Valid operations:\n{valid_ops_str}"
                    ),
                },
            ],
        },
    ]


def _command_token_ids() -> dict[str, list[int]]:
    token_map: dict[str, list[int]] = {}
    for cmd in VALID_COMMANDS:
        ids = _processor.tokenizer.encode(cmd, add_special_tokens=False)
        if ids:
            token_map[cmd] = ids
    return token_map


@torch.inference_mode()
def _run_inference(pil_image: Image.Image) -> tuple[str, float]:
    valid_ops_str = ", ".join(VALID_COMMANDS)
    messages = _build_messages(valid_ops_str)

    text_prompt: str = _processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    inputs = _processor(
        text=[text_prompt],
        images=[pil_image],
        return_tensors="pt",
        padding=True,
    )

    device = next(_model.parameters()).device
    inputs = {
        k: v.to(device) if isinstance(v, torch.Tensor) else v
        for k, v in inputs.items()
    }

    output = _model.generate(
        **inputs,
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=False,
        temperature=None,   
        top_p=None,
        top_k=None,
        output_scores=True,
        return_dict_in_generate=True,
    )

    input_len = inputs["input_ids"].shape[1]
    generated_ids = output.sequences[0][input_len:]
    raw_text: str = _processor.decode(generated_ids, skip_special_tokens=True).strip().lower()
    predicted_cmd = _match_command(raw_text)
    confidence = _compute_confidence(output.scores, predicted_cmd)

    return predicted_cmd, confidence


def _compute_confidence(scores: tuple, predicted_cmd: str) -> float:
    if not scores:
        return 0.0

    first_logits = scores[0][0]   # shape: (vocab_size,)

    tok = _processor.tokenizer
    cmd_first_ids: dict[str, int] = {}
    for cmd in VALID_COMMANDS:
        ids = tok.encode(cmd, add_special_tokens=False)
        if ids:
            cmd_first_ids[cmd] = ids[0]

    if not cmd_first_ids:
        probs = torch.softmax(first_logits, dim=-1)
        return float(probs.max().item())

    cmd_logits = torch.stack([first_logits[tid] for tid in cmd_first_ids.values()])
    cmd_probs  = torch.softmax(cmd_logits, dim=-1)

    cmd_names = list(cmd_first_ids.keys())
    if predicted_cmd in cmd_names:
        idx = cmd_names.index(predicted_cmd)
        return float(cmd_probs[idx].item())

    return float(cmd_probs.max().item())


def _match_command(raw: str) -> str:
    if raw in VALID_COMMANDS:
        return raw
    for cmd in _COMMANDS_BY_LENGTH:
        if cmd in raw:
            return cmd
    best, best_score = VALID_COMMANDS[0], -1
    for cmd in VALID_COMMANDS:
        score = sum(1 for a, b in zip(raw, cmd) if a == b)
        if score > best_score:
            best, best_score = cmd, score
    return best


# Endpoints
@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    if _model is None or _processor is None:
        raise HTTPException(status_code=503, detail="Modèle non encore chargé.")

    try:
        raw_bytes = base64.b64decode(request.image_b64)
        pil_image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Données image invalides : {exc}") from exc

    t0 = time.time()
    command, confidence = _run_inference(pil_image)
    elapsed = time.time() - t0
    logger.info("Inférence → '%s' (conf=%.3f) en %.2f s", command, confidence, elapsed)

    suppressed = confidence < CONFIDENCE_GATE
    if suppressed:
        logger.info("Supprimé (conf %.3f < seuil %.2f)", confidence, CONFIDENCE_GATE)

    return PredictResponse(command=command, confidence=confidence, suppressed=suppressed)


@app.get("/health")
async def health():
    model_ready = _model is not None
    device_str  = str(_get_device()) if model_ready else "—"
    return JSONResponse({
        "status":  "ok" if model_ready else "loading",
        "model":   MODEL_PATH,
        "device":  device_str,
        "classes": len(VALID_COMMANDS),
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
