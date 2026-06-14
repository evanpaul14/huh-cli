# huh

On-device AI assistant for your terminal. Run `huh` after a failed command and it tells you what you meant to type — no internet required.

## Install

```bash
pip install huh-cli
huh install   # adds shell hook to ~/.zshrc or ~/.bashrc
```

Then open a new terminal (or `source ~/.zshrc`) to activate.

## Usage

```bash
# Fix your last failed command
huh

# Ask for any shell command
huh ask "compress a folder to tar.gz"
huh ask "find files modified in the last 24 hours"

# Copy suggestion to clipboard instead of running
huh --copy
huh ask "list open ports" --copy

# Show or change the model
huh model
huh model mlx-community/Qwen2.5-Coder-3B-Instruct-4bit
```

## How it works

After `huh install`, your shell captures the last failed command and exit code. When you run `huh`, it feeds that context along with a snapshot of your environment (OS, shell, CWD, git branch) to a local LLM and returns a single corrected command.

- **Apple Silicon (M1/M2/M3):** uses [`mlx-lm`](https://github.com/ml-explore/mlx-lm) with a 4-bit quantized model
- **Everything else:** uses [`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python) with a GGUF model auto-downloaded on first use

No data leaves your machine.

## Requirements

- Python 3.10+
- Apple Silicon Mac (MLX backend) or any machine that can run llama.cpp
