from __future__ import annotations

import hashlib
import os
import re
import zipfile
from pathlib import Path

BASELINE_SHA = os.environ.get(
    "BASELINE_SHA", "bd12073c4322a88ce666fe062b7bb265f5de131a"
)
ZIP_PATH = Path("H3-Continuum-Skill-v1.zip")
ROOT = "write-continuum-h3-prompts/"
TARGETS = {
    "skill": ROOT + "SKILL.md",
    "contract": ROOT + "references/continuum-contract.md",
    "examples": ROOT + "references/examples.md",
    "readme_ja": "README_JA.md",
}


def insert_after_h1(text: str, block: str, marker: str) -> str:
    if marker in text:
        return text
    match = re.search(r"(?m)^# .+\n", text)
    if match:
        return text[: match.end()] + "\n" + block.rstrip() + "\n\n" + text[match.end() :]
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            pos = end + len("\n---\n")
            return text[:pos] + "\n" + block.rstrip() + "\n\n" + text[pos:]
    return block.rstrip() + "\n\n" + text


def main() -> None:
    with zipfile.ZipFile(ZIP_PATH, "r") as zin:
        infos = zin.infolist()
        data = {info.filename: zin.read(info.filename) for info in infos}

    names = [info.filename for info in infos]
    if len(names) != 7:
        raise SystemExit(f"expected 7 ZIP entries, found {len(names)}: {names}")
    for label, name in TARGETS.items():
        if name not in data:
            raise SystemExit(f"missing required {label} file: {name}")

    def decode(name: str) -> str:
        return data[name].decode("utf-8")

    def encode(name: str, text: str) -> None:
        data[name] = text.encode("utf-8")

    hard_rule = r'''## Timeline syntax hard rule

Treat this as a hard formatting rule whenever you write Continuum Timeline prompts: every Continuum timeline header must occupy the entire line. Never place prompt text on the same line as `[0-5s]`, `[5-10s]`, `[Chunk 1]`, or any other Continuum timeline header.

Correct:

```text
[0-5s]
The girl walks forward on a street.

[5-10s]
Continuation of Chunk 1. The scene moves into a parking garage.
```

Incorrect:

```text
[0-5s] The girl walks forward on a street.
[5-10s] The scene moves into a parking garage.
```

Why this matters: the current V3.8 parser recognizes Timeline headers only when the whole line is a valid header. Inline prompt text can prevent Timeline detection; with `Prompt Format = Auto`, the script may then fall back to Fixed behavior and the full script can be sent to every chunk.

If a user supplies inline headers, normalize them to the standalone form in the output instead of preserving the invalid layout. A blank line after the header is optional; the standalone header line itself is mandatory.

This is a Continuum routing rule. H3 shot markers such as `[Shot 1]` belong inside the chunk body and must not be used as Continuum chunk headers.'''

    skill_text = decode(TARGETS["skill"])
    skill_text = insert_after_h1(
        skill_text, hard_rule, "## Timeline syntax hard rule"
    )
    encode(TARGETS["skill"], skill_text)

    contract_rule = f'''## Current Timeline parser baseline and standalone-header contract

Verified against H3 Continuum V3.8 `main` commit `{BASELINE_SHA}` on 2026-09-12.

- `[0-5s]`, `[5-10s]`, `[Chunk 1]`, and `[Clip 1]` are Continuum routing headers only when the header occupies the full line.
- Prompt text starts on the following line. A blank separator line is optional.
- Inline forms such as `[0-5s] walk forward` are not valid Timeline headers for this baseline and must be normalized before output.
- With `Prompt Format = Auto`, an inline-only script can be detected as Fixed and therefore be reused as the complete prompt for every chunk.
- This is a prompt-format contract and does not change MiniMax H3 shot syntax inside each chunk body.

If an older baseline identifier elsewhere in this reference conflicts with this section, this verified baseline supersedes it for Timeline-header syntax.'''

    original_contract = decode(TARGETS["contract"])
    refreshed_lines = []
    for line in original_contract.splitlines():
        if "baseline" in line.lower():
            line = re.sub(r"\b[0-9a-f]{7,40}\b", BASELINE_SHA, line)
        refreshed_lines.append(line)
    contract_text = "\n".join(refreshed_lines)
    if original_contract.endswith("\n"):
        contract_text += "\n"
    contract_text = insert_after_h1(
        contract_text,
        contract_rule,
        "## Current Timeline parser baseline and standalone-header contract",
    )
    encode(TARGETS["contract"], contract_text)

    examples_block = r'''## Simple Continuum Timeline examples

These examples intentionally keep the H3 body simple. The important Continuum rule is that every timeline header is on its own line.

### 3 x 5 seconds — simple scene progression

```text
[0-5s]
The girl walks forward on a city street at a steady pace. The camera tracks backward in front of the girl.

[5-10s]
Continuation of Chunk 1. The scene changes to a parking garage. The girl looks around, notices a red motorcycle, and walks toward it.

[10-15s]
Continuation of Chunk 2. The girl rides the red motorcycle along a city street and stops at a red traffic light.
```

### 3 x 10 seconds — continuous one-shot motion

```text
[0-10s]
A dancer begins a slow routine in the center of a rehearsal room. The camera tracks laterally while keeping the full body visible.

[10-20s]
Continuation of Chunk 1. The dancer crosses the room with wider steps and turns once while the same lateral tracking shot continues.

[20-30s]
Continuation of Chunk 2. The dancer slows, returns toward center frame, and finishes in a stable standing pose while the camera settles.
```

### 2 x 15 seconds — two-part action

```text
[0-15s]
A mechanic examines a motorcycle beside an open garage door, checks the front wheel, and reaches for a tool on a workbench.

[15-30s]
Continuation of Chunk 1. The mechanic adjusts the motorcycle, puts the tool down, starts the engine, and watches the motorcycle idle in place.
```

### Normalize inline user input before output

User input:

```text
[0-5s] walk forward
[5-10s] enter the garage
```

Skill output:

```text
[0-5s]
walk forward

[5-10s]
Continuation of Chunk 1. enter the garage
```
'''

    examples_text = decode(TARGETS["examples"])
    if "## Simple Continuum Timeline examples" not in examples_text:
        examples_text = examples_text.rstrip() + "\n\n" + examples_block.rstrip() + "\n"
    encode(TARGETS["examples"], examples_text)

    readme_note = r'''## Timelineプロンプトの重要ルール

ContinuumのTimelineヘッダーは、必ずヘッダーだけで1行を使ってください。

正しい例:

```text
[0-5s]
女の子が通りを前へ歩く。

[5-10s]
Continuation of Chunk 1. 駐車場へ場面が移り、赤いバイクへ歩いていく。
```

誤った例:

```text
[0-5s] 女の子が通りを前へ歩く。
```

`[0-5s]` の後ろへ同じ行で本文を書くと、V3.8ではTimelineヘッダーとして認識されず、`Prompt Format = Auto` ではFixed扱いになって全文が各Chunkへ渡る場合があります。ヘッダー直後の空行は必須ではありませんが、ヘッダーを単独行にすることは必須です。'''

    readme_text = decode(TARGETS["readme_ja"])
    readme_text = insert_after_h1(
        readme_text, readme_note, "## Timelineプロンプトの重要ルール"
    )
    encode(TARGETS["readme_ja"], readme_text)

    tmp_path = ZIP_PATH.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp_path, "w") as zout:
        for info in infos:
            zout.writestr(info, data[info.filename])
    tmp_path.replace(ZIP_PATH)

    with zipfile.ZipFile(ZIP_PATH, "r") as check:
        checked_names = check.namelist()
        if checked_names != names:
            raise SystemExit(f"ZIP entry order changed: {checked_names}")
        bad = check.testzip()
        if bad is not None:
            raise SystemExit(f"ZIP CRC validation failed: {bad}")
        skill_after = check.read(TARGETS["skill"]).decode("utf-8")
        contract_after = check.read(TARGETS["contract"]).decode("utf-8")
        examples_after = check.read(TARGETS["examples"]).decode("utf-8")
        readme_after = check.read(TARGETS["readme_ja"]).decode("utf-8")

    checks = {
        "skill standalone rule": "## Timeline syntax hard rule" in skill_after,
        "skill incorrect inline example": "[0-5s] The girl walks forward on a street." in skill_after,
        "contract baseline": BASELINE_SHA in contract_after,
        "contract inline behavior": "inline-only script can be detected as Fixed" in contract_after,
        "3x5 example": "### 3 x 5 seconds" in examples_after,
        "3x10 example": "### 3 x 10 seconds" in examples_after,
        "2x15 example": "### 2 x 15 seconds" in examples_after,
        "Japanese note": "## Timelineプロンプトの重要ルール" in readme_after,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("validation failed: " + ", ".join(failed))

    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest().upper()
    print("ZIP entries:", len(names))
    print("ZIP SHA-256:", digest)
    print("Updated files:", TARGETS)
    Path("skill_update_sha256.txt").write_text(digest + "\n", encoding="utf-8")

    worklog = Path("WORKLOG.md")
    entry = f'''\n\n## Prompt skill Timeline syntax hardening — GitHub (2026-09-12)\n\n- Updated repository-root `H3-Continuum-Skill-v1.zip` without changing runtime code or workflows. Promoted the standalone Timeline-header rule into `SKILL.md`, refreshed `references/continuum-contract.md` to the current V3.8 parser baseline `{BASELINE_SHA}`, added simple `3x5`, `3x10`, and `2x15` Timeline examples plus inline-input normalization to `references/examples.md`, and added the same critical syntax note to `README_JA.md`.\n- Validation: `tools/snapshot.ps1` completed before modification; ZIP retained exactly seven entries and passed `ZipFile.testzip()`; targeted `tests/test_v2_prompts.py` is run by the helper workflow after repacking. New ZIP SHA-256: `{digest}`. This is documentation/prompt-skill only; Sampling, Run Storage, public node schema, workflows, and runtime tensors are unchanged. H3情報チェック handoff remains pending because that cross-task destination is not available from this GitHub Actions job.\n'''
    worklog.write_text(worklog.read_text(encoding="utf-8").rstrip() + entry, encoding="utf-8")


if __name__ == "__main__":
    main()
