#!/usr/bin/env python3
"""
Phase 생성 헬퍼 — 대화형으로 phase 디렉토리와 step 파일을 생성한다.

Usage:
    python3 scripts/new-phase.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHASES_DIR = ROOT / "phases"


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n중단됨.")
        sys.exit(0)
    return val or default


def ask_int(prompt: str, default: int) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("  숫자를 입력하세요.")


def slugify(text: str) -> str:
    return text.strip().lower().replace(" ", "-")


def main():
    print("\n" + "=" * 55)
    print("  Harness Phase 생성 도우미")
    print("=" * 55)

    # 1. 프로젝트 이름 (index.json 의 project 필드)
    project = ask("프로젝트 이름", "Meeting Room")

    # 2. phase 이름 (디렉토리명 + phase 필드)
    phase_name = ask("phase 이름 (kebab-case, 예: 0-mvp)")
    if not phase_name:
        print("phase 이름은 필수입니다.")
        sys.exit(1)
    phase_slug = slugify(phase_name)
    phase_dir = PHASES_DIR / phase_slug

    if phase_dir.exists():
        print(f"\n❌ 이미 존재합니다: {phase_dir}")
        sys.exit(1)

    # 3. step 수
    n_steps = ask_int("step 수", 3)

    # 4. 각 step 이름
    print(f"\nStep 이름을 입력하세요 (kebab-case):")
    step_names = []
    for i in range(n_steps):
        name = ask(f"  step {i}", f"step-{i}")
        step_names.append(slugify(name))

    # 5. 확인
    print(f"\n생성될 구조:")
    print(f"  phases/{phase_slug}/")
    print(f"    index.json  (project={project!r}, phase={phase_slug!r})")
    for i, name in enumerate(step_names):
        print(f"    step{i}.md   ({name})")
    top_exists = (PHASES_DIR / "index.json").exists()
    if top_exists:
        print(f"  phases/index.json  ← phases 항목 추가")
    else:
        print(f"  phases/index.json  ← 신규 생성")

    confirm = ask("\n생성하시겠습니까? (y/N)", "N")
    if confirm.lower() not in ("y", "yes"):
        print("취소됨.")
        sys.exit(0)

    # 6. 파일 생성
    phase_dir.mkdir(parents=True)

    # phases/{phase}/index.json
    index = {
        "project": project,
        "phase": phase_slug,
        "steps": [
            {"step": i, "name": name, "status": "pending"}
            for i, name in enumerate(step_names)
        ],
    }
    (phase_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # step{N}.md — 템플릿으로 생성
    for i, name in enumerate(step_names):
        step_file = phase_dir / f"step{i}.md"
        step_file.write_text(
            _step_template(i, name, phase_slug), encoding="utf-8"
        )

    # phases/index.json (top-level)
    top_file = PHASES_DIR / "index.json"
    if top_file.exists():
        top = json.loads(top_file.read_text(encoding="utf-8"))
    else:
        top = {"phases": []}
    top["phases"].append({"dir": phase_slug, "status": "pending"})
    top_file.write_text(json.dumps(top, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✓ Phase '{phase_slug}' 생성 완료!")
    print(f"\n다음 단계:")
    print(f"  1. phases/{phase_slug}/step{{N}}.md 파일에 작업 지시를 작성하세요.")
    print(f"  2. python3 scripts/execute.py {phase_slug}")


def _step_template(num: int, name: str, phase: str) -> str:
    return f"""\
# Step {num}: {name}

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`
- (이전 step에서 생성/수정된 파일 경로 추가)

## 작업

(구체적인 구현 지시를 여기에 작성. 파일 경로, 함수 시그니처, 핵심 규칙을 포함.)

## Acceptance Criteria

```bash
# 예시 — 실제 검증 커맨드로 교체할 것
uv run pytest
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가?
   - ADR 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가?
3. `phases/{phase}/index.json` 의 step {num} 상태를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 3회 시도 후 실패 → `"status": "error"`, `"error_message": "구체적 에러"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "사유"` 후 즉시 중단

## 금지사항

- 이 step 범위 밖의 파일을 수정하지 마라.
- `pip install` 을 사용하지 마라. 반드시 `uv add <pkg>` 를 사용하라.
"""


if __name__ == "__main__":
    main()
