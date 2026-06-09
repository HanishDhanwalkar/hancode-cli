"""Interactive CLI interface for Hancode."""

from __future__ import annotations

import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.table import Table


from src import __version__
from src.agent.orchestrator import AgentOrchestrator
from src.config import ProjectConfig
from src.models.entities import Mode, TrustLevel
from src.policy.audit import AuditLog
from src.providers import get_provider
from src.session.store import SessionStore
from src.workspace.detector import detect_workspace, initialize_project, set_trust_level

console = Console()

SLASH_COMMANDS = {
    "/help": "Display help message",
    "/exit": "Exit",
    # "/mode": "Change the mode", TODO: eat /chat, /plan, /edit, /review, /debug
    "/chat": "Switch to chat mode",
    "/plan": "Switch to plan mode; Create implementation plans for a task",
    "/edit": "Switch to edit mode",
    "/review": "Switch to review mode",
    "/debug": "Switch to debug mode",
    "/trust": "Set the trust level",
    "/index": "Rebuild file index",
    "/apply": "Apply a pending patch",
    "/reject": "Reject a pending patch",
    "/approve-cmd": "Approve a pending shell/tool call",
    "/reject-cmd": "Reject a pending shell/tool call",
    "/test": "Run tests (if test framework is detected)",
    "/rollback": "Rollback to last checkpoint",
    "/git": "show git status and diff summary",
    "/audit": "Display audit log",
    "/memory": "Display memory contents",
    "/sessions": "list sessions", # TODO: implement switching sessions and deleting sessions
    "/model": "Show or switch models (/model list; /model '<provider>/<model>')",
    # "/clear": "Clear the conversation history" TODO: implement clear
}


def print_banner(workspace_root: str, mode: str, model: str, file_count: int) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold cyan]HanCode CLI[/]", f"v{__version__}")
    table.add_row("Workspace", workspace_root)
    table.add_row("Mode", f"[green]{mode}[/]")
    table.add_row("Model", model)
    table.add_row("Indexed", f"{file_count} files")
    console.print(Panel(table, title="Ready", border_style="cyan"))


def print_help() -> None:
    for cmd, desc in SLASH_COMMANDS.items():
        console.print(f"  [bold]{cmd}[/] — {desc}")
    console.print("\nType natural language to chat. Use /plan <task> to plan before editing.")


def prompt_trust(root: Path) -> TrustLevel:
    console.print("\n[yellow]This workspace has not been trusted yet.[/]")
    console.print("Trust levels: read_only (inspect), editable (patch), automated (low-risk auto)")
    choice = Prompt.ask(
        "Trust this workspace?",
        choices=["read_only", "editable", "no"],
        default="read_only",
    )
    if choice == "no":
        return TrustLevel.UNTRUSTED
    level = TrustLevel.READ_ONLY if choice == "read_only" else TrustLevel.EDITABLE
    set_trust_level(root, level)
    return level


def ask_yes_no(question: str) -> bool:
    return Confirm.ask(question, default=False)


class SlashCommandCompleter(Completer):
    def __init__(self, commands: list[str]):
        self.commands = sorted(commands)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Only suggest if we are at the start of the line and it begins with /
        if not text.startswith("/"):
            return

        # Only suggest for the first word (the command itself)
        if " " in text:
            return

        for cmd in self.commands:
            if cmd.startswith(text):
                yield Completion(cmd, start_position=-len(text))


def handle_slash(
    command: str,
    args: str,
    agent: AgentOrchestrator,
) -> str | None:
    """Returns None to continue loop, or a sentinel to quit."""

    if command in ("/quit", "/exit"):
        return "__quit__"

    if command == "/help":
        print_help()
        return ""

    if command == "/chat":
        agent.set_mode(Mode.CHAT)
        return "Switched to chat mode."

    if command == "/edit":
        agent.set_mode(Mode.EDIT)
        return "Switched to edit mode."

    if command == "/review":
        agent.set_mode(Mode.REVIEW)
        return "Switched to review mode."

    if command == "/debug":
        agent.set_mode(Mode.DEBUG)
        return "Switched to debug mode."

    if command == "/plan":
        if not args.strip():
            return "Usage: /plan <task description>"
        plan = agent.create_plan(args.strip())
        console.print(Panel(Markdown(plan.content), title=f"Plan {plan.plan_id}", border_style="blue"))
        if ask_yes_no("Approve this plan and switch to edit mode?"):
            agent.approve_plan(plan)
            return f"Plan {plan.plan_id} approved. You can now ask for implementation."
        return f"Plan {plan.plan_id} created (not approved). Use /edit after reviewing."

    if command == "/apply":
        if agent.pending_patch:
            patch = agent.pending_patch
            console.print(Panel(
                patch.diff_content[:4000] or "(empty diff)",
                title=f"Patch {patch.patch_id}: {patch.summary}",
                border_style="yellow",
            ))
        result = agent.apply_pending_patch()
        if agent.pending_patch is None and "Applied" in result:
            console.print(Panel(result, title="Patch Applied", border_style="green"))
        return result

    if command == "/reject":
        return agent.reject_pending_patch()

    if command == "/approve-cmd":
        return agent.approve_pending_command()

    if command == "/reject-cmd":
        agent.pending_command = None
        return "Command rejected."

    if command == "/test":
        return agent.run_tests()

    if command == "/rollback":
        return agent.rollback_last()

    if command == "/index":
        count = agent.index.build()
        return f"Re-indexed {count} files."

    if command == "/git":
        if not agent.git.is_repo():
            return "Not a Git repository."
        status = agent.git.status()
        diff_stat = agent.git.diff_stat()
        return (
            f"Branch: {status.branch} | Clean: {status.clean}\n"
            f"Staged: {len(status.staged)} | Unstaged: {len(status.unstaged)} | "
            f"Untracked: {len(status.untracked)}\n\n{diff_stat or '(no changes)'}"
        )

    if command == "/audit":
        entries = agent.audit.read_recent(20)
        if not entries:
            return "Audit log empty."
        lines = []
        for e in entries:
            lines.append(f"{e['timestamp'][:19]} [{e['event_type']}] {str(e['details'])[:80]}")
        return "\n".join(lines)

    if command == "/memory":
        return agent.project_memory or "(empty — edit .hancode/MEMORY.md)"

    if command == "/sessions":
        sessions = agent.session_store.list_sessions()
        return "Sessions:\n" + "\n".join(sessions[:20]) if sessions else "No saved sessions."

    if command == "/model":
        from src.providers import list_available_models, resolve_model
        arg = args.strip().lower()
        if not arg:
            return f"Current model: [bold cyan]{agent.provider.model_name}[/]"

        if arg == "list":
            models = list_available_models()
            table = Table(title="Available Models")
            table.add_column("Provider/Model", style="cyan")
            for m in models:
                table.add_row(m)
            console.print(table)
            return ""

        resolved = resolve_model(arg)
        if resolved:
            provider_name, model_name = resolved
            return agent.switch_provider(provider_name, model_name)

        return f"Unknown model: {arg}. Use /model list to see available models."

    if command == "/trust":
        root = agent.root
        level_map = {
            "read_only": TrustLevel.READ_ONLY,
            "editable": TrustLevel.EDITABLE,
            "automated": TrustLevel.AUTOMATED,
        }
        if args.strip() in level_map:
            level = level_map[args.strip()]
            set_trust_level(root, level)
            agent.trust_level = level
            return f"Trust set to {level.value}."
        return "Usage: /trust read_only|editable|automated"

    return f"Unknown command: {command}. Type /help."


def main() -> None:
    console.print("[bold cyan]HanCode CLI[/] — starting...\n")

    workspace = detect_workspace()
    root = Path(workspace.root_path)
    hancode_dir = initialize_project(root)
    config = ProjectConfig.load(hancode_dir)

    trust = workspace.trust_level
    if trust == TrustLevel.UNTRUSTED:
        trust = prompt_trust(root)
        workspace.trust_level = trust

    if trust == TrustLevel.UNTRUSTED:
        console.print("[red]Cannot proceed without trust. Exiting.[/]")
        sys.exit(1)

    try:
        provider = get_provider(
            config.default_provider,
            model=config.default_model,
        )
    except Exception as e:
        console.print(f"[red]Provider error: {e}[/]")
        console.print("Check ANTHROPIC_API_KEY and RESOURCE in .env")
        sys.exit(1)

    session_store = SessionStore(hancode_dir / "sessions")
    audit = AuditLog(hancode_dir / "audit.log")

    def on_status(msg: str) -> None:
        console.print(f"[dim]{msg}[/]")

    streamed: list[bool] = []

    def on_token(token: str) -> None:
        streamed.append(True)
        console.print(token, end="")

    agent = AgentOrchestrator(
        root=root,
        workspace_id=workspace.workspace_id,
        trust_level=trust,
        provider=provider,
        config=config,
        session_store=session_store,
        audit=audit,
        on_status=on_status,
        on_token=on_token,
        ask_approval=ask_yes_no,
    )

    file_count = agent.initialize_index()
    print_banner(str(root), agent.session.mode.value, provider.model_name, file_count)
    print_help()
    console.print()

    audit.record("session_start", {
        "session_id": agent.session.session_id,
        "workspace": str(root),
        "trust": trust.value,
    })

    # Command completer for slash commands
    completer = SlashCommandCompleter(list(SLASH_COMMANDS.keys()))
    style = Style.from_dict({
        "prompt": "bold green",
    })
    session = PromptSession(completer=completer, style=style)

    while True:
        try:
            user_input = session.prompt([("class:prompt", "hancode: ")]).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            result = handle_slash(cmd, args, agent)
            if result == "__quit__":
                break
            if result:
                if len(result) > 500 and ("diff" in result.lower() or "---" in result):
                    console.print(Syntax(result[:3000], "diff", theme="monokai"))
                else:
                    console.print(result)
            console.print()
            continue

        console.print()
        streamed.clear()
        try:
            response = agent.handle_message(user_input)
            if streamed:
                console.print()
            elif response:
                console.print(response)
        except KeyboardInterrupt:
            console.print("\n[yellow]Generation stopped by user.[/]")
        console.print()

    audit.record("session_end", {"session_id": agent.session.session_id})
    session_store.save(agent.session)
    console.print(f"[dim]Session saved: {agent.session.session_id}[/]")


if __name__ == "__main__":
    main()
 