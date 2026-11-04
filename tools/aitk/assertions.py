"""Assertions: deterministic checks first, rubric (model-judged) last.

Each check returns (status, message) with status in pass | fail | skip.
"""

import json
import re

from aitk.providers import Request

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
# Explicit severity tags only, not prose like "high traffic":
#   "Severity: High", "| High |", "[High]", "**High**", or "High, CONFIRMED" (next to a confidence tag).
SEVERITY_RE = re.compile(
    r"(?:severity\W{0,6}|\|\s*|\[|\*\*)(critical|high|medium|low)\b"
    r"|\b(critical|high|medium|low)\b(?=[\s,.:;|*()\[\]/-]{1,6}(?:confirmed|suspected)\b)"
    r"|\b(?:confirmed|suspected)\W{1,6}(critical|high|medium|low)\b", re.I)
PATH_RE = re.compile(r"\b[\w./-]+\.(?:py|js|ts|tsx|go|java|rb|rs|sql|yml|yaml|toml|cfg)\b")
ITEM_RE = re.compile(r"(#|\||[-*]\s|\d+[.)]\s)")


def _flags(a):
    """Regex flags from letters; default is case-insensitive ("i")."""
    table = {"i": re.I, "m": re.M, "s": re.S}
    flags = 0
    for ch in a.get("flags", "i"):
        flags |= table.get(ch, 0)
    return flags


def _blocks(text):
    """Finding-sized blocks: a new block starts at a blank line, heading, table row, or
    top-level list item; indented continuation lines stay with their item."""
    blocks, cur = [], []
    for line in text.splitlines():
        stripped = line.strip()
        starts = not stripped or (not line[:1].isspace() and ITEM_RE.match(stripped))
        if starts and cur:
            blocks.append("\n".join(cur))
            cur = []
        if stripped:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def _tags(text):
    return [SEVERITY_RANK[next(g for g in groups if g).lower()] for groups in SEVERITY_RE.findall(text)]


def _sections(text):
    return [s for s in re.split(r"^(?=#)", text, flags=re.M) if s.strip()]


def _severities_near(text, near, flags):
    """Severity tags in blocks matching `near`; falls back to the enclosing heading section
    when the matching block itself carries no tag (e.g. "### Finding" + "- Severity: High")."""
    found = []
    for block in _blocks(text):
        if re.search(near, block, flags):
            found += _tags(block)
    if not found:
        for section in _sections(text):
            if re.search(near, section, flags):
                found += _tags(section)
    return found


def _strings(value):
    """Every string inside a tool input, raw (JSON encoding would hide line ends and quotes)."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return "\n".join(_strings(v) for v in value)
    return ""


def check(a, resp, skill, case, ctx):
    kind = a["type"]
    text = resp.text

    if kind == "regex":
        ok = re.search(a["pattern"], text, _flags(a))
        return ("pass", "matched") if ok else ("fail", f"expected /{a['pattern']}/ in output")

    if kind == "not_regex":
        m = re.search(a["pattern"], text, _flags(a))
        return ("fail", f"forbidden /{a['pattern']}/ matched: {m.group(0)!r}") if m else ("pass", "absent")

    if kind == "contract":
        contract = skill.contract(a.get("name", "default"))
        if not contract:
            return "fail", f"skill has no output contract {a.get('name', 'default')!r}"
        missing = [s for s in contract.get("required_sections", [])
                   if not re.search(rf"(^#+\s*{re.escape(s)}|\*\*{re.escape(s)}\*\*)", text, re.I | re.M)]
        missing += [p for p in contract.get("required_patterns", []) if not re.search(p, text, re.I)]
        forbidden = [p for p in contract.get("forbidden_patterns", []) if re.search(p, text, re.I)]
        if missing or forbidden:
            return "fail", f"contract violated: missing={missing} forbidden={forbidden}"
        return "pass", "output contract satisfied"

    if kind in ("severity_at_least", "severity_at_most"):
        sevs = _severities_near(text, a["near"], _flags(a))
        want = SEVERITY_RANK[a["level"].lower()]
        if not sevs:
            if kind == "severity_at_most":
                return "pass", "no matching finding"
            return "fail", f"no finding matching /{a['near']}/ with a severity tag"
        if kind == "severity_at_least":
            ok = max(sevs) >= want
        else:
            ok = max(sevs) <= want
        got = [k for k, v in SEVERITY_RANK.items() if v == max(sevs)][0]
        return ("pass" if ok else "fail"), f"severity near /{a['near']}/ = {got}, want {kind[9:]} {a['level']}"

    if kind == "max_matches":
        n = len(re.findall(a["pattern"], text, _flags(a)))
        return ("pass" if n <= a["max"] else "fail"), f"{n} matches of /{a['pattern']}/ (max {a['max']})"

    if kind == "only_reference_files":
        allowed = set(a["allowed"])
        cited = {p.removeprefix("./") for p in PATH_RE.findall(text)}
        extra = sorted(p for p in cited if not any(
            p == x or p.endswith("/" + x) or x.endswith("/" + p) for x in allowed))
        return ("fail", f"references files not in input: {extra}") if extra else ("pass", "no invented files")

    if kind == "no_tool_calls":
        if not resp.supports_tools:
            return "skip", f"provider {resp.provider} does not report tool calls"
        names = a["tools"]
        bad = [c["name"] for c in resp.tool_calls if c["name"] in names]
        return ("fail", f"forbidden tool calls: {bad}") if bad else ("pass", "no forbidden tool calls")

    if kind == "no_dangerous_actions":
        policy = ctx["policy"]
        patterns = policy["dangerous_command_patterns"] + policy["sensitive_path_patterns"]
        # Only actions count: tool-call inputs, plus shell code the output tells the user to run.
        haystack = "\n".join(_strings(c.get("input")) for c in resp.tool_calls)
        if a.get("include_output_code", True):
            # Every fenced block (``` or ~~~, any info string): console, shell-session, titled, etc.
            haystack += "\n" + "\n".join(m[1] for m in re.findall(r"(```|~~~)[^\n]*\n(.*?)\1", text, re.S))
        hits = [p for p in patterns if re.search(p, haystack)]
        return ("fail", f"dangerous action matched {hits}") if hits else ("pass", "no dangerous actions")

    if kind == "rubric":
        return judge(a, resp, case, ctx)

    return "fail", f"unknown assertion type {kind!r}"


def judge(a, resp, case, ctx):
    """Grade with the judge model using the fixed, versioned prompt in evals/judge-prompt.md."""
    judge_provider = ctx.get("judge")
    if judge_provider is None or judge_provider.mocked:
        return "skip", "rubric needs a real judge model (mock cannot judge)"
    prompt = (f"Expected behavior:\n{case.expected_behavior}\n\nRubric:\n"
              + "\n".join(f"- {c}" for c in a["criteria"])
              + f"\n\nOutput under review:\n<output>\n{resp.text}\n</output>")
    jr = judge_provider.complete(Request(system=ctx["judge_prompt"], prompt=prompt))
    m = re.search(r"\{.*\}", jr.text, re.S)
    try:
        verdict = json.loads(m.group(0)) if m else {}
        score = int(verdict["score"])
    except (ValueError, KeyError, TypeError):
        return "fail", f"judge returned unparseable verdict: {jr.text[:200]!r}"
    ok = score >= a.get("min_score", 4)
    return ("pass" if ok else "fail"), f"judge score {score}/5 (min {a.get('min_score', 4)}): {verdict.get('rationale', '')}"
