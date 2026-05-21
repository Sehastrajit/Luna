"""Luna tool registry."""
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    RISKY = "risky"
    DANGEROUS = "dangerous"


@dataclass
class ToolDef:
    name: str
    description: str
    risk: RiskLevel
    params: list[str] = field(default_factory=list)
    confirm_template: str = ""


TOOL_REGISTRY: dict[str, ToolDef] = {
    "launch_app": ToolDef("launch_app", "Open an application on the current desktop platform", RiskLevel.SAFE, ["app"]),
    "list_apps": ToolDef("list_apps", "List apps Luna can launch on this platform", RiskLevel.SAFE),
    "spotify_play": ToolDef("spotify_play", "Play music on Spotify", RiskLevel.SAFE, ["query"]),
    "spotify_pause": ToolDef("spotify_pause", "Pause Spotify playback", RiskLevel.SAFE),
    "spotify_next": ToolDef("spotify_next", "Skip to the next track", RiskLevel.SAFE),
    "spotify_prev": ToolDef("spotify_prev", "Go to the previous track", RiskLevel.SAFE),
    "spotify_queue": ToolDef("spotify_queue", "Add a song to the Spotify queue", RiskLevel.SAFE, ["query"]),
    "switch_audio": ToolDef("switch_audio", "Switch the Windows default audio output device", RiskLevel.SAFE, ["device_name"]),
    "create_task": ToolDef("create_task", "Create a task or reminder", RiskLevel.SAFE, ["title", "due", "priority"]),
    "create_event": ToolDef("create_event", "Create a calendar event", RiskLevel.SAFE, ["title", "datetime", "duration"]),
    "take_screenshot": ToolDef("take_screenshot", "Take a screenshot of the current screen", RiskLevel.SAFE),
    "find_text_on_screen": ToolDef("find_text_on_screen", "Use OCR to find text on the screen", RiskLevel.SAFE, ["query"]),
    "get_active_window": ToolDef("get_active_window", "Get the name of the currently focused window", RiskLevel.SAFE),
    "browse_url": ToolDef("browse_url", "Open a URL in the system browser", RiskLevel.SAFE, ["url"]),
    "click_at": ToolDef("click_at", "Click at screen coordinates", RiskLevel.RISKY, ["x", "y"], "Click at position ({x}, {y})?"),
    "type_text": ToolDef("type_text", "Type text into the focused window", RiskLevel.RISKY, ["text"], 'Type "{text}" into the current window?'),
    "web_search": ToolDef("web_search", "Search the web via DuckDuckGo and return results", RiskLevel.SAFE, ["query"]),
    "web_fetch": ToolDef("web_fetch", "Fetch a URL and return readable text content", RiskLevel.SAFE, ["url"]),
    "browser_open": ToolDef("browser_open", "Open a URL in the browser through Luna's browser layer", RiskLevel.SAFE, ["url"]),
    "browser_read": ToolDef("browser_read", "Read a public webpage into clean text", RiskLevel.SAFE, ["url"]),
    "workspace_read": ToolDef("workspace_read", "Read a file from Luna's controlled workspace", RiskLevel.SAFE, ["path"]),
    "workspace_write": ToolDef("workspace_write", "Write a file inside Luna's controlled workspace", RiskLevel.RISKY, ["path", "content"], "Write {path} in Luna's workspace?"),
    "list_skills": ToolDef("list_skills", "List installed Luna skills", RiskLevel.SAFE),
    "create_agent_task": ToolDef("create_agent_task", "Create a persistent multi-step agent task", RiskLevel.SAFE, ["description"]),
    # ── System controls ──────────────────────────────────────────────────────────
    "get_volume":       ToolDef("get_volume", "Get current system volume level (0–100)", RiskLevel.SAFE),
    "set_volume":       ToolDef("set_volume", "Set system volume to a level 0–100", RiskLevel.SAFE, ["level"]),
    "mute_audio":       ToolDef("mute_audio", "Mute system audio output", RiskLevel.SAFE),
    "unmute_audio":     ToolDef("unmute_audio", "Unmute system audio output", RiskLevel.SAFE),
    "get_brightness":   ToolDef("get_brightness", "Get current display brightness (0–100)", RiskLevel.SAFE),
    "set_brightness":   ToolDef("set_brightness", "Set display brightness to a level 0–100", RiskLevel.SAFE, ["level"]),
    "lock_screen":      ToolDef("lock_screen", "Lock the workstation / screen immediately", RiskLevel.SAFE),
    "turn_off_display": ToolDef("turn_off_display", "Turn off the display without sleeping", RiskLevel.SAFE),
    "sleep_system":     ToolDef("sleep_system", "Put the computer to sleep / suspend", RiskLevel.RISKY, [], "Put the system to sleep?"),
    "get_clipboard":    ToolDef("get_clipboard", "Read current clipboard text content", RiskLevel.SAFE),
    "set_clipboard":    ToolDef("set_clipboard", "Write text to the system clipboard", RiskLevel.SAFE, ["text"]),
    "get_system_info":  ToolDef("get_system_info", "Get OS, RAM, battery and machine info", RiskLevel.SAFE),
    # ── GitHub ──────────────────────────────────────────────────────────────────
    "github_list_repos": ToolDef("github_list_repos", "List your GitHub repositories sorted by last updated", RiskLevel.SAFE),
    "github_list_issues": ToolDef("github_list_issues", "List open issues in a GitHub repository", RiskLevel.SAFE, ["repo"]),
    "github_create_issue": ToolDef("github_create_issue", "Create a new GitHub issue", RiskLevel.RISKY, ["repo", "title", "body"], "Create GitHub issue '{title}' in {repo}?"),
    "github_comment": ToolDef("github_comment", "Post a comment on a GitHub issue or pull request", RiskLevel.RISKY, ["repo", "number", "body"], "Post comment on {repo}#{number}?"),
    "github_list_prs": ToolDef("github_list_prs", "List open pull requests in a GitHub repository", RiskLevel.SAFE, ["repo"]),
    "github_get_pr": ToolDef("github_get_pr", "Get details about a specific pull request", RiskLevel.SAFE, ["repo", "number"]),
}


def get_tool(name: str) -> ToolDef | None:
    return TOOL_REGISTRY.get(name)


def get_tools_for_prompt() -> str:
    """Return a compact tool list for inclusion in Luna's system prompt."""
    lines = [
        "You can call tools by including JSON anywhere in your response:",
        '{"tool_call": {"tool": "<name>", "args": {<params>}, "speak": "<what you say>"}}',
        "",
        "Available tools:",
    ]
    for name, tool in TOOL_REGISTRY.items():
        params = ", ".join(tool.params) if tool.params else "-"
        lines.append(f"  {name}({params}) - {tool.description}")
    lines.append("")
    lines.append("For map, Spotify, launches, and simple URL opening use bracket tags when instructed; use tool_call JSON for agentic workflows.")
    lines.append("Use tool_call JSON for: switch_audio, create_task, create_event, screen tools, click/type actions, web_search, web_fetch, browser_read, workspace files, skills, and agent tasks.")
    lines.append("IMPORTANT: When switching audio devices, you MUST emit a tool_call JSON. Do NOT just say you are switching.")
    lines.append("Web tools: use web_search for current information, recent news, prices, or anything that requires searching. Use web_fetch or browser_read to read a specific URL.")
    lines.append("Agent tools: use create_agent_task for multi-step work, workspace_write/read for files inside Luna's workspace, and list_skills to discover installed local skills.")
    lines.append("GitHub tools: use github_list_repos, github_list_issues(repo), github_create_issue(repo,title,body), github_comment(repo,number,body), github_list_prs(repo), github_get_pr(repo,number). Requires github_token in .env.")
    lines.append("System controls: get_volume/set_volume(level)/mute_audio/unmute_audio for audio; get_brightness/set_brightness(level) for display; lock_screen, turn_off_display, sleep_system; get_clipboard/set_clipboard(text); get_system_info.")
    return "\n".join(lines)
