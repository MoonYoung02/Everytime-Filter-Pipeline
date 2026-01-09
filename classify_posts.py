#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import re
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# -------------------------
# 설정값
# -------------------------
INPUT_PATH  = sys.argv[1] if len(sys.argv) >= 2 else "everytime_posts_filtered.jsonl"
OUTPUT_PATH = sys.argv[2] if len(sys.argv) >= 3 else "everytime_posts_llm_saved.jsonl"
DEBUG_DROP = True
MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "300"))  # 분류 JSON이면 150~400이면 충분

load_dotenv()

SLEEP_SEC = float(os.getenv("OPENAI_SLEEP_SEC", "0.0"))  # 레이트리밋 완화용

# ===== 디버깅 / 통계 =====
START_TIME = time.time()
TOTAL_PROMPT_TOKENS = 0
TOTAL_COMPLETION_TOKENS = 0
TOTAL_TOKENS = 0

# -------------------------
# LLM 백엔드/모델 선택(하드코딩 + if/else)
# -------------------------
LLM_BACKEND = "openrouter"  # "openai" 또는 "openrouter"

if LLM_BACKEND == "openrouter":
    # OpenRouter + Gemini 2.5 Flash
    MODEL = "google/gemini-2.5-flash"  # OpenRouter 모델 ID :contentReference[oaicite:2]{index=2}
    API_KEY_ENV = "OPENROUTER_API_KEY"
    BASE_URL = "https://openrouter.ai/api/v1"  # OpenAI-compatible base URL :contentReference[oaicite:3]{index=3}

    # 아래 헤더는 "선택사항"(리더보드/앱 식별용). 없어도 동작함. :contentReference[oaicite:4]{index=4}
    OR_SITE = os.getenv("OPENROUTER_SITE_URL", "http://localhost")
    OR_APP  = os.getenv("OPENROUTER_APP_NAME", "everytime_RPA")
    DEFAULT_HEADERS = {
        "HTTP-Referer": OR_SITE,
        "X-Title": OR_APP,
    }

else:
    # OpenAI
    MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    API_KEY_ENV = "OPENAI_API_KEY"
    BASE_URL = None
    DEFAULT_HEADERS = None

STORE = os.getenv("OPENAI_STORE", "false").lower() == "true"  # (OpenRouter에서는 무시될 수 있음)

# life override
LIFE_PATTERN = re.compile(r"(기숙사|긱사|생활관|도서관)", re.IGNORECASE)

# 분류 스키마(Structured Outputs)
SCHEMA = {
    "name": "post_classification",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "should_save":  {"type": "boolean"},
            "label_top":    {"type": "string", "enum": ["academic", "life", "other"]},
            "label_sub":    {"type": "string"},
            "confidence":   {"type": "number", "minimum": 0, "maximum": 1},
            "reason_short": {"type": "string"}
        },
        "required": ["should_save", "label_top", "label_sub", "confidence", "reason_short"]
    },
    "strict": True
}

SYSTEM = """
너는 대학 커뮤니티 게시글을 분류하는 필터다.
입력은 title/snippet 뿐이다.

규칙:
- 학사 문의(행정/수강/성적/장학/휴학/복학/증명서/학적/등록금/계절학기/교환/학점교류/전과/전입/전출/졸업/수료/출석 등)이면 should_save=true, label_top="academic".
- 기숙사/긱사/생활관/도서관 관련 생활 인프라는 label_top="life", should_save=true.
- 그 외 잡담/취업/연애/일상/밈/분노표출/정보요청이 아닌 단순 감상은 label_top="other", should_save=false.

추가 지침:
- 제목이 "이거", "뭐냐" 같이 불명확해도 snippet을 근거로 best guess를 해라.
- 애매하면 confidence를 낮게 주고, 그래도 하나로 결론을 내려라.
- reason_short는 한국어 한 줄로 간단히.
""".strip()

# -------------------------
# 실행
# -------------------------

api_key = os.getenv(API_KEY_ENV)
if not api_key:
    print(f"ERROR: {API_KEY_ENV} 환경변수가 없습니다.", file=sys.stderr)
    sys.exit(1)

if LLM_BACKEND == "openrouter":
    client = OpenAI(api_key=api_key, base_url=BASE_URL, default_headers=DEFAULT_HEADERS)
else:
    client = OpenAI(api_key=api_key)

total = 0
saved = 0
skipped = 0
failed = 0

# 출력 파일 초기화
open(OUTPUT_PATH, "w", encoding="utf-8").close()

with open(INPUT_PATH, "r", encoding="utf-8") as fin, open(OUTPUT_PATH, "a", encoding="utf-8") as fout:
    for line_no, line in enumerate(fin, start=1):
        line = line.strip()
        if not line:
            continue

        total += 1

        # JSONL 파싱
        try:
            post = json.loads(line)
        except Exception as e:
            failed += 1
            print(f"[LINE {line_no}] JSON parse error: {e}", file=sys.stderr)
            continue

        title = str(post.get("title", "") or "")
        snippet = str(post.get("snippet", "") or "")
        combined = f"{title} {snippet}".strip()

        # 1) life override
        if LIFE_PATTERN.search(combined):
            decision = {
                "should_save": True,
                "label_top": "life",
                "label_sub": "dorm_or_library",
                "confidence": 1.0,
                "reason_short": "기숙사/도서관 키워드가 포함되어 life로 분류"
            }
            out = dict(post)
            out.update(decision)
            out["classified_by"] = "rule_override"
            out["classified_at"] = datetime.now().isoformat(timespec="seconds")
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")
            saved += 1
            if SLEEP_SEC > 0:
                time.sleep(SLEEP_SEC)
            continue

        # 2) LLM 분류 (재시도 포함)
        max_retries = 3
        last_err = None
        decision = None

        for attempt in range(1, max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": json.dumps({"title": title, "snippet": snippet}, ensure_ascii=False)},
                    ],
                    temperature=0,
                    max_tokens=MAX_TOKENS,   
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "post_classification",
                            "schema": SCHEMA["schema"],
                            "strict": True,
                        },
                    },
                )

                # 결과 JSON 파싱
                content = resp.choices[0].message.content
                decision = json.loads(content)

                # ---- 토큰 사용량 누적 ----
                usage = getattr(resp, "usage", None)
                if usage:
                    TOTAL_PROMPT_TOKENS += getattr(usage, "prompt_tokens", 0) or 0
                    TOTAL_COMPLETION_TOKENS += getattr(usage, "completion_tokens", 0) or 0
                    TOTAL_TOKENS += getattr(usage, "total_tokens", 0) or 0

                break

            except Exception as e:
                last_err = e
                time.sleep(0.8 * attempt)

        if decision is None:
            failed += 1
            print(f"[LINE {line_no}] LLM classify failed: {last_err}", file=sys.stderr)
            continue

        # 3) 저장 여부 반영 (+ drop 디버그 로그)
        if decision.get("should_save") is True:
            out = dict(post)
            out.update(decision)
            out["classified_by"] = f"llm:{LLM_BACKEND}:{MODEL}"
            out["classified_at"] = datetime.now().isoformat(timespec="seconds")
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")
            saved += 1
        else:
            skipped += 1
            if DEBUG_DROP:
                print(
                    "[DROP][LLM]",
                    f"line={line_no}",
                    f"title='{title}'",
                    f"snippet='{snippet[:200]}'",
                    f"label_top={decision.get('label_top')}",
                    f"label_sub={decision.get('label_sub')}",
                    f"confidence={decision.get('confidence')}",
                    sep=" | ",
                    file=sys.stderr
                )

        if SLEEP_SEC > 0:
            time.sleep(SLEEP_SEC)

ELAPSED = time.time() - START_TIME

print(
    f"Done.\n"
    f"  backend={LLM_BACKEND}\n"
    f"  model={MODEL}\n"
    f"  total={total}, saved={saved}, skipped={skipped}, failed={failed}\n"
    f"  time_elapsed={ELAPSED:.2f}s\n"
    f"  tokens_prompt={TOTAL_PROMPT_TOKENS}\n"
    f"  tokens_completion={TOTAL_COMPLETION_TOKENS}\n"
    f"  tokens_total={TOTAL_TOKENS}\n"
    f"  input={INPUT_PATH}\n"
    f"  output={OUTPUT_PATH}",
    file=sys.stderr
)
