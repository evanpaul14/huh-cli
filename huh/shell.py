import re

ZSH_SNIPPET = """
# huh shell integration v4 — auto-capture failed commands + stderr
_huh_preexec() {
  _HUH_LAST_CMD="$1"
  _HUH_STDERR_FILE="$(mktemp /tmp/.huh.XXXXXX 2>/dev/null || mktemp)"
  exec {_HUH_SAVED_STDERR}>&2
  exec 2> >(tee "${_HUH_STDERR_FILE}" >&"${_HUH_SAVED_STDERR}")
  _HUH_TEE_PID=$!
}
_huh_precmd() {
  local code=$?
  if [[ -n "${_HUH_SAVED_STDERR:-}" ]]; then
    exec 2>&"${_HUH_SAVED_STDERR}" {_HUH_SAVED_STDERR}>&-
    unset _HUH_SAVED_STDERR
    [[ -n "${_HUH_TEE_PID:-}" ]] && wait "${_HUH_TEE_PID}" 2>/dev/null
    unset _HUH_TEE_PID
  fi
  if [[ $code -ne 0 ]]; then
    local cmd="${_HUH_LAST_CMD:-$(fc -ln -1 2>/dev/null | sed 's/^[[:space:]]*//')}"
    if [[ -n "$cmd" ]]; then
      export HUH_LAST_CMD="$cmd"
      export HUH_LAST_EXIT="$code"
      if [[ -f "${_HUH_STDERR_FILE:-}" ]]; then
        export HUH_LAST_OUTPUT="$(head -20 "${_HUH_STDERR_FILE}")"
        rm -f "${_HUH_STDERR_FILE}"
      fi
    fi
  else
    unset HUH_LAST_CMD HUH_LAST_EXIT HUH_LAST_OUTPUT
    [[ -f "${_HUH_STDERR_FILE:-}" ]] && rm -f "${_HUH_STDERR_FILE}"
  fi
  _HUH_LAST_CMD=""
  _HUH_STDERR_FILE=""
}
command_not_found_handler() {
  export HUH_LAST_CMD="$*"
  export HUH_LAST_EXIT=127
  export HUH_LAST_OUTPUT="zsh: command not found: $1"
  echo "zsh: command not found: $1" >&2
  return 127
}
preexec_functions+=(_huh_preexec)
precmd_functions+=(_huh_precmd)
"""

BASH_SNIPPET = """
# huh shell integration v4 — auto-capture failed commands + stderr
_huh_stderr_file=""
_huh_saved_stderr=""
_huh_tee_pid=""
_huh_preexec() {
  [[ -n "${_huh_saved_stderr}" ]] && return
  _huh_stderr_file="$(mktemp /tmp/.huh.XXXXXX 2>/dev/null || mktemp)"
  export HUH_LAST_CMD="$BASH_COMMAND"
  exec {_huh_saved_stderr}>&2
  exec 2> >(tee "${_huh_stderr_file}" >&"${_huh_saved_stderr}")
  _huh_tee_pid=$!
}
trap '_huh_preexec' DEBUG
_huh_precmd() {
  local code=$?
  if [[ -n "${_huh_saved_stderr}" ]]; then
    exec 2>&"${_huh_saved_stderr}" {_huh_saved_stderr}>&-
    _huh_saved_stderr=""
    [[ -n "${_huh_tee_pid}" ]] && wait "${_huh_tee_pid}" 2>/dev/null
    _huh_tee_pid=""
  fi
  if [[ $code -ne 0 ]]; then
    export HUH_LAST_EXIT="$code"
    if [[ -f "${_huh_stderr_file}" ]]; then
      export HUH_LAST_OUTPUT="$(head -20 "${_huh_stderr_file}")"
      rm -f "${_huh_stderr_file}"
    fi
  else
    unset HUH_LAST_CMD HUH_LAST_EXIT HUH_LAST_OUTPUT
    [[ -f "${_huh_stderr_file}" ]] && rm -f "${_huh_stderr_file}"
  fi
  _huh_stderr_file=""
}
PROMPT_COMMAND="_huh_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
command_not_found_handle() {
  export HUH_LAST_CMD="$1"
  export HUH_LAST_EXIT=127
  export HUH_LAST_OUTPUT="bash: $1: command not found"
  echo "bash: $1: command not found" >&2
  return 127
}
"""

MARKER = "# huh shell integration v4"
OLD_MARKER = "# huh shell integration"

# Match old snippet blocks (any version) by their unique terminal lines
_OLD_ZSH_RE = re.compile(
    r"\n# huh shell integration[^\n]*\n"
    r".*?"
    r"precmd_functions\+=\(_huh_precmd\)\n",
    re.DOTALL,
)

_OLD_BASH_RE = re.compile(
    r"\n# huh shell integration[^\n]*\n"
    r".*?"
    r'echo "bash: \$1: command not found" >&2\n  return 127\n}\n',
    re.DOTALL,
)


def get_snippet(shell: str) -> str:
    if "zsh" in shell:
        return ZSH_SNIPPET
    return BASH_SNIPPET


def rc_path(shell: str) -> str:
    import os
    home = os.path.expanduser("~")
    if "zsh" in shell:
        return f"{home}/.zshrc"
    return f"{home}/.bashrc"


def _read_rc(rc_file: str) -> str:
    try:
        with open(rc_file) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def remove_snippet(shell: str) -> tuple[bool, str]:
    """Returns (was_installed, rc_path). Strips any version of the huh hook."""
    path = rc_path(shell)
    contents = _read_rc(path)

    if OLD_MARKER not in contents:
        return False, path

    old_re = _OLD_ZSH_RE if "zsh" in shell else _OLD_BASH_RE
    stripped = old_re.sub("\n", contents).rstrip("\n") + "\n"
    with open(path, "w") as f:
        f.write(stripped)
    return True, path


def install_snippet(shell: str) -> tuple[bool, str]:
    """Returns (already_installed, rc_path)."""
    path = rc_path(shell)
    contents = _read_rc(path)

    if MARKER in contents:
        return True, path

    snippet = get_snippet(shell)

    if OLD_MARKER in contents:
        old_re = _OLD_ZSH_RE if "zsh" in shell else _OLD_BASH_RE
        stripped = old_re.sub("\n", contents).rstrip("\n") + "\n"
        with open(path, "w") as f:
            f.write(stripped)
            f.write(snippet)
        return False, path

    with open(path, "a") as f:
        f.write(snippet)
    return False, path
