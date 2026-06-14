import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.text import Text

from .llm import suggest_fix, suggest_command
from .shell import install_snippet

console = Console()

CONFIG_PATH = Path.home() / ".config" / "huh" / "config.json"

DEFAULT_CONFIG = {
    "model": "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit",
    "backend": "mlx",
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    cfg = dict(DEFAULT_CONFIG)
    if not (sys.platform == "darwin" and platform.machine() == "arm64"):
        cfg["backend"] = "llama_cpp"
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def _print_suggestion(suggestion: str) -> None:
    arrow = Text("→ ", style="bold green")
    cmd = Text(suggestion, style="bold cyan")
    console.print(arrow + cmd)


def _copy_to_clipboard(text: str) -> bool:
    import shutil
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        elif shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        elif shutil.which("xsel"):
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=True)
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode(), check=True)
        else:
            return False
        return True
    except Exception:
        return False


def _act_on_suggestion(suggestion: str, copy: bool) -> None:
    _print_suggestion(suggestion)
    if copy:
        if _copy_to_clipboard(suggestion):
            console.print("[dim]Copied to clipboard.[/dim]")
        else:
            console.print("[yellow]Clipboard unavailable on this system.[/yellow]")
    elif Confirm.ask("Run it?", default=False):
        subprocess.run(suggestion, shell=True)


def _run_fix_mode(cfg: dict, copy: bool = False) -> None:
    last_cmd = os.environ.get("HUH_LAST_CMD", "").strip()
    last_exit = os.environ.get("HUH_LAST_EXIT", "").strip()
    last_output = os.environ.get("HUH_LAST_OUTPUT", "").strip()

    if not last_cmd:
        console.print(
            "[yellow]No failed command captured.[/yellow] "
            "Run [bold]huh install[/bold] to set up shell integration, "
            "or ask directly: [bold]huh ask \"your question\"[/bold]"
        )
        raise SystemExit(1)

    # Stale capture: last command succeeded, hook cleared HUH_LAST_EXIT
    if not last_exit or last_exit == "0":
        console.print(
            "[yellow]Last command succeeded — nothing to fix.[/yellow] "
            "huh only helps after a failed command. "
            "Ask directly: [bold]huh ask \"your question\"[/bold]"
        )
        raise SystemExit(1)

    console.print(
        f"[dim]Last failed command:[/dim] [bold]{last_cmd}[/bold] "
        f"[dim](exit {last_exit})[/dim]"
    )

    with console.status("[dim]thinking...[/dim]", spinner="dots"):
        try:
            suggestion = suggest_fix(last_cmd, int(last_exit), cfg, error_output=last_output)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)

    _act_on_suggestion(suggestion, copy)


# ── commands ─────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--copy", is_flag=True, help="Copy suggestion to clipboard instead of running.")
@click.pass_context
def cli(ctx: click.Context, copy: bool) -> None:
    """huh — the CLI that figures out what you meant.

    \b
    Run after a failed command:   huh
    Ask for a command:            huh ask "compress folder to tar.gz"
    """
    if ctx.invoked_subcommand is None:
        _run_fix_mode(load_config(), copy=copy)


@cli.command()
@click.argument("question", nargs=-1, required=True)
@click.option("--copy", is_flag=True, help="Copy suggestion to clipboard instead of running.")
def ask(question: tuple[str, ...], copy: bool) -> None:
    """Ask for the command you need."""
    cfg = load_config()
    q = " ".join(question)
    with console.status("[dim]thinking...[/dim]", spinner="dots"):
        try:
            suggestion = suggest_command(q, cfg)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)
    _act_on_suggestion(suggestion, copy)


@cli.command()
def install() -> None:
    """Add shell hook to ~/.zshrc or ~/.bashrc."""
    shell = os.environ.get("SHELL", "")
    already, path = install_snippet(shell)
    if already:
        console.print(f"[yellow]Already installed[/yellow] in {path}")
    else:
        console.print(f"[green]✓[/green] Installed shell hook in [bold]{path}[/bold]")
        console.print(f"Run [bold]source {path}[/bold] (or open a new terminal) to activate.")


@cli.command()
@click.argument("model_id", required=False)
def model(model_id: str | None) -> None:
    """Show or set the model used for inference."""
    cfg = load_config()
    if model_id:
        cfg["model"] = model_id
        save_config(cfg)
        console.print(f"[green]✓[/green] Model set to [bold]{model_id}[/bold]")
    else:
        console.print(f"Backend: [bold]{cfg.get('backend')}[/bold]")
        console.print(f"Model:   [bold]{cfg.get('model')}[/bold]")
        if cfg.get("backend") == "llama_cpp":
            from .llm import _DEFAULT_GGUF_FILE
            console.print(f"File:    [bold]{cfg.get('gguf_file', _DEFAULT_GGUF_FILE)}[/bold] [dim](auto-downloaded on first use)[/dim]")
