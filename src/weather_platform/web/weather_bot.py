import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_model = None
_tokenizer = None


def load_model(model_path: str):
    global _model, _tokenizer

    if _model is not None:
        return

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        model_path = Path(model_path)
        if not model_path.exists():
            logger.warning(f"Model not found at {model_path}")
            return

        logger.info(f"Loading Weather-Bot model from {model_path}")
        _tokenizer = AutoTokenizer.from_pretrained(model_path)
        _model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16)
        logger.info("Weather-Bot model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Weather-Bot model: {e}")


def generate_forecast_summary(predictions: List[Dict], current_temp: float, location: str) -> Optional[str]:
    global _model, _tokenizer

    if _model is None or _tokenizer is None:
        return None

    try:
        import torch
        from datetime import datetime

        temps_by_period = {'morning': [], 'afternoon': [], 'evening': [], 'night': []}
        for pred in predictions[:24]:
            time = datetime.fromisoformat(pred['time'].replace('Z', '+00:00'))
            hour = time.hour
            temp = pred['predicted_temperature']
            if 5 <= hour < 12:
                temps_by_period['morning'].append(temp)
            elif 12 <= hour < 17:
                temps_by_period['afternoon'].append(temp)
            elif 17 <= hour < 21:
                temps_by_period['evening'].append(temp)
            else:
                temps_by_period['night'].append(temp)

        summary_parts = []
        for period, temps in temps_by_period.items():
            if temps:
                avg = sum(temps) / len(temps)
                high = max(temps)
                low = min(temps)
                summary_parts.append(f"{period}: high {high:.0f}°F, low {low:.0f}°F")

        forecast_summary = "; ".join(summary_parts)

        prompt = f"""<|system|>
You are a weather assistant. Write one short, friendly natural sentence summarizing the forecast. Use phrases like "this morning", "in the afternoon", "tonight". Mention specific temperatures useing °F. Never use the word 'temperature'. Mention changes in temperature. Keep it under 30 words.
</s>
<|user|>
Current: {current_temp:.0f}°F. Forecast: {forecast_summary}
</s>
<|assistant|>
"""

        inputs = _tokenizer(prompt, return_tensors="pt")

        with torch.no_grad():
            outputs = _model.generate(
                **inputs,
                max_new_tokens=200,
                do_sample=True,
                temperature=0.6,
                top_p=0.9,
                pad_token_id=_tokenizer.eos_token_id,
                eos_token_id=_tokenizer.eos_token_id
            )

        full_response = _tokenizer.decode(outputs[0], skip_special_tokens=True)

        if "<|assistant|>" in full_response:
            response = full_response.split("<|assistant|>")[-1].strip()
        else:
            response = full_response[len(prompt):].strip()

        response = response.split("</s>")[0].strip()
        response = response.split("<|")[0].strip()
        response = response.split("\n")[0].strip()

        return response

    except Exception as e:
        logger.error(f"Failed to generate forecast summary: {e}")
        return None
