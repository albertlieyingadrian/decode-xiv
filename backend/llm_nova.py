"""
Amazon Nova (Bedrock) completion for manim workflow.
Uses AWS Bedrock Converse API with Nova 2 Lite (or configured model).
Required for Amazon Nova AI Hackathon: core solution must use a Nova foundation model.
"""

import os
import time
from typing import Any

# Optional: only needed when USE_AMAZON_NOVA=1
try:
    import boto3
    from botocore.config import Config
except ImportError:
    boto3 = None
    Config = None


# Nova 2 Lite (US); see https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-nova.html
DEFAULT_NOVA_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
# Longer timeout for code generation (Nova can take a while)
BEDROCK_READ_TIMEOUT = 300


def _get_client():
    if boto3 is None or Config is None:
        raise RuntimeError("boto3 is required for Amazon Nova. Install: pip install boto3")
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(read_timeout=BEDROCK_READ_TIMEOUT),
    )


def _build_usage_info(model_id: str, usage: dict[str, int], llm_time: float) -> dict[str, Any]:
    """Map Bedrock usage to our usage_info shape."""
    inp = usage.get("inputTokens", 0) or 0
    out = usage.get("outputTokens", 0) or 0
    total = usage.get("totalTokens", 0) or (inp + out)
    return {
        "model": model_id,
        "prompt_tokens": inp,
        "completion_tokens": out,
        "total_tokens": total,
        "reasoning_tokens": 0,
        "answer_tokens": out,
        "cost": 0.0,
        "llm_time": llm_time,
    }


def get_completion(
    model_id: str,
    messages: list[dict[str, Any]],
    temperature: float | None = None,
    timeout: int = 120,
) -> tuple[str, dict[str, Any], str | None]:
    """
    Call Amazon Nova via Bedrock Converse API.
    Returns (content, usage_info, reasoning_content).
    Expects AWS credentials (env, profile, or IAM role).
    """
    if not model_id.strip():
        model_id = os.environ.get("NOVA_MODEL_ID", DEFAULT_NOVA_MODEL_ID)
    client = _get_client()

    # Converse API format: list of messages with role and content list of parts
    formatted = []
    for m in messages:
        role = m.get("role", "user")
        raw = m.get("content", "")
        text = raw if isinstance(raw, str) else (raw[0].get("text", "") if isinstance(raw, list) and raw else "")
        formatted.append({
            "role": "user" if role == "user" else "assistant",
            "content": [{"text": text}],
        })

    inference_config: dict[str, Any] = {"maxTokens": 8192}
    if temperature is not None:
        inference_config["temperature"] = temperature

    start = time.time()
    response = client.converse(
        modelId=model_id,
        messages=formatted,
        inferenceConfig=inference_config,
    )
    llm_time = time.time() - start

    # Extract text from output.message.content
    content = ""
    out_msg = response.get("output", {}).get("message", {})
    for part in out_msg.get("content", []):
        if "text" in part:
            content += part["text"]

    usage = response.get("usage", {})
    if isinstance(usage, dict):
        usage_info = _build_usage_info(model_id, usage, llm_time)
    else:
        usage_info = _build_usage_info(
            model_id,
            {
                "inputTokens": getattr(usage, "inputTokens", 0),
                "outputTokens": getattr(usage, "outputTokens", 0),
                "totalTokens": getattr(usage, "totalTokens", 0),
            },
            llm_time,
        )

    # Nova may expose reasoning in stopReason or elsewhere; leave None if not present
    reasoning_content = None
    return content, usage_info, reasoning_content
