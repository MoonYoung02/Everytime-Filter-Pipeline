# Everytime Academic Filter (Playwright + LLM)

에브리타임(Everytime) 자유게시판에서 글 목록을 수집한 뒤,  
**학사/생활(기숙사·도서관)** 관련 글만 골라 JSONL로 저장하는 간단한 파이프라인입니다.

## 1. Playwright를 이용한 에브리타임 게시글 수집

Playwright를 사용해 에브리타임 자유게시판의 게시글 목록을 수집합니다.  
이 단계에서는 **키워드 기반 필터링**을 적용하여, 특정 키워드를 포함한 게시글만 `raw_academic.jsonl` 파일로 저장합니다.

사용법

```bash
python crawl_academic_filter.py
```

## 2. raw_academic.jsonl을 입력으로 LLM에게 해당 게시글이 학사문의 글인지 다시 필터링

1단계에서 생성된 raw_academic.jsonl 파일을 입력으로 받아,
LLM을 이용해 해당 게시글이 실제로 학사 문의 글인지 여부를 다시 판단합니다.

사용법

```bash
python classify_posts.py [input arg: raw_academic_filter.jsonl] [ouput arg]
```

1단계는 단순 키워드 기반 필터링이므로,
키워드가 포함되어 있더라도 실제 학사 문의가 아닌 글이 포함될 수 있습니다.

예를 들어, 아래 게시글은 졸업 키워드를 포함하고 있지만
학사 문의라기보다는 취업 관련 잡담에 가깝습니다.

```jsonl
{
  "board_url": "https://everytime.kr/384921/p/7",
  "post_url": "https://everytime.kr/384921/v/397826899",
  "title": "충붕이들 졸업하면 보통 대기업 취직함?",
  "snippet": "사촌언니 하이닉스 들어갔는디 ㄱㄴ?",
  "time": "11:35",
  "fetched_at": "2026-01-09T15:56:31"
}
```

2단계에서는 이러한 게시글을 LLM이 분석하여
학사 문의가 아니라고 판단할 경우 다음과 같이 [DROP] 로그와 함께 저장하지 않습니다.

```bash
[DROP][LLM] | line=67 | title='충붕이들 졸업하면 보통 대기업 취직함?' | snippet='사촌언니 하이닉스 들어갔는디 ㄱㄴ?' | label_top=other | label_sub=취업 | confidence=0.9
```

반대로 학사 문의 글로 판단될 경우,
아래와 같은 형식으로 결과가 저장됩니다.

```jsonl
{
  "board_url": "https://everytime.kr/384921",
  "post_url": "https://everytime.kr/384921/v/397836095",
  "title": "8월 졸업 예정인 친구 있음?",
  "snippet": "졸업예정 증명서 8월로 나와?",
  "time": "4분 전",
  "fetched_at": "2026-01-09T14:56:56",
  "should_save": true,
  "label_top": "academic",
  "label_sub": "졸업",
  "confidence": 0.9,
  "reason_short": "졸업 예정 증명서 발급에 대한 문의이다.",
  "classified_by": "llm:openrouter:google/gemini-2.5-flash",
  "classified_at": "2026-01-09T15:57:39"
}
```

## Environment

### Installation

필요한 Python 패키지는 다음과 같습니다.

```bash
pip install -r requirements.txt
```

requirements.txt

```txt
playwright>=1.40.0
openai>=1.0.0
python-dotenv>=1.0.0
```

이후 Playwright 브라우저 바이너리를 설치합니다.

```bash
playwright install chromium
```

### Environment Variables

루트 디렉터리에 다음 예시와 같이 `.env` 파일을 생성합니다.

```txt
# OpenRouter (default use gemini-2.5-flash)
OPENROUTER_API_KEY=PUT_YOUR_KEY_HERE

# If using OpenAI instead
# OPENAI_API_KEY=PUT_YOUR_KEY_HERE
# OPENAI_MODEL=gpt-4o-mini
```
