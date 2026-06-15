import platform
import re
import sys
from .context import get_context


def _clean(text: str) -> str:
    """Strip markdown fences, leading/trailing whitespace, and special tokens."""
    text = re.sub(r"```[a-z]*\n?", "", text)
    text = text.strip().splitlines()[0].strip()  # take only first line
    return text


_SYSTEM = """\
You are a shell command expert. Output ONLY the single shell command — no explanation, no markdown, no surrounding quotes.

Rules:
- The command runs as a subprocess of the user's shell, so `cd` effects do NOT persist to the parent; avoid bare `cd` unless it is chained (e.g. `cd /tmp && ls`).
- When operating on the current working directory itself (renaming, moving, deleting it), use absolute paths via shell expansion: e.g. `mv "$(pwd)" "$(dirname "$(pwd)")/new_name"`.
- Always quote paths that may contain spaces.
- Prefer portable POSIX forms unless the context shows a specific shell (zsh/bash/fish).
- Output a single line. No comments.

Examples:
User: This command failed (command not found): gti status
Assistant: git status

User: This command failed (misuse of shell built-in): git log --oneline -n
Assistant: git log --oneline -n 10

User: Give me the shell command to: list all running processes sorted by memory
Assistant: ps aux --sort=-%mem

User: Give me the shell command to: find files larger than 100MB
Assistant: find . -type f -size +100M\
"""


_EXIT_HINTS = {
    127: "command not found (likely a typo in the command name)",
    126: "permission denied or not executable",
    1:   "general error",
    2:   "misuse of shell built-in (bad arguments or flags)",
}


def _build_fix_messages(command: str, exit_code: int, context: str, error_output: str = "") -> list[dict]:
    hint = _EXIT_HINTS.get(exit_code, f"exit code {exit_code}")
    error_section = f"Error output:\n{error_output.strip()}\n\n" if error_output.strip() else ""
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"{context}\n\n"
            f"This command failed ({hint}):\n  {command}\n\n"
            f"{error_section}"
            f"Output the corrected command."
        )},
    ]


def _build_ask_messages(question: str, context: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"{context}\n\n"
            f"Give me the shell command to: {question}"
        )},
    ]


def _is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _run_mlx(messages: list[dict], model_id: str) -> str:
    import os as _os
    _os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    _os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        from mlx_lm import load, generate  # type: ignore
    except ImportError:
        raise RuntimeError("mlx-lm is not installed. Run: pip install mlx-lm")

    model, tokenizer = load(model_id)

    formatted = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=False
    )

    result = generate(model, tokenizer, prompt=formatted, max_tokens=128, verbose=False)
    for tok in ["<|im_end|>", "<|endoftext|>", "</s>", "<|eot_id|>"]:
        result = result.replace(tok, "")
    return _clean(result)


_DEFAULT_GGUF_REPO = "bartowski/Qwen2.5-Coder-1.5B-Instruct-GGUF"
_DEFAULT_GGUF_FILE = "Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf"


def _resolve_gguf_path(config: dict) -> str:
    """Return path to GGUF model, downloading it on first use if needed."""
    model_path = config.get("model_path", "")
    if model_path:
        return model_path

    import os as _os
    _os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    from huggingface_hub import hf_hub_download  # type: ignore

    repo = config.get("model", _DEFAULT_GGUF_REPO)
    filename = config.get("gguf_file", _DEFAULT_GGUF_FILE)
    return hf_hub_download(repo_id=repo, filename=filename)


def _run_llama_cpp(messages: list[dict], config: dict) -> str:
    try:
        from llama_cpp import Llama  # type: ignore
    except ImportError:
        raise RuntimeError(
            "llama-cpp-python is not installed.\n"
            "On Linux/Windows: pip install llama-cpp-python\n"
            "For GPU acceleration see: https://github.com/abetlen/llama-cpp-python"
        )

    model_path = _resolve_gguf_path(config)
    llm = Llama(model_path=model_path, n_ctx=2048, verbose=False, chat_format="chatml")
    output = llm.create_chat_completion(messages=messages, max_tokens=128)
    return _clean(output["choices"][0]["message"]["content"])


def _get_suggestion(messages: list[dict], config: dict) -> str:
    backend = config.get("backend", "mlx")
    if backend == "mlx":
        model_id = config.get("model", "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit")
        return _run_mlx(messages, model_id)
    elif backend == "llama_cpp":
        return _run_llama_cpp(messages, config)
    else:
        raise RuntimeError(f"Unknown backend: {backend}")


def suggest_fix(command: str, exit_code: int, config: dict, error_output: str = "") -> str:
    ctx = get_context()
    messages = _build_fix_messages(command, exit_code, ctx, error_output)
    return _get_suggestion(messages, config)


def suggest_command(question: str, config: dict) -> str:
    ctx = get_context()
    messages = _build_ask_messages(question, ctx)
    return _get_suggestion(messages, config)
