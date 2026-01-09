# Everytime Academic Filter (Playwright + LLM)

에브리타임(Everytime) 자유게시판에서 글 목록을 수집한 뒤,  
**학사/생활(기숙사·도서관)** 관련 글만 골라 JSONL로 저장하는 간단한 파이프라인입니다.
</br>
</br>

## 1. Playwright로 에브리타임 게시글 수집

- 게시글 중 필요한 키워드를 포함한 글만 저장하여 raw_academic.jsonl로 저장

사용법

```python
python crawl_academic_filter.py
```

</br>

## 2. raw_academic.jsonl을 입력으로 LLM에게 해당 게시글이 학사문의 글인지 다시 필터링

사용법

```python
python classify_posts.py [input arg: raw_academic_fiter.py] [ouput arg]
```

1번 과정은 단순히 키워드 기반으로 게시글을 필터링 하기에 정확히 학사 문의 글만을 저장한다 할 수 없다.

예를 들면, 다음과 같은 게시글은 '졸업'이라는 키워드로 인해 저장되었다. 하지만, '졸업' 키워드가 들어갔다고 무조건 학사 문의 글이 아니다.

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

2번 과정은 이를 LLM에게 주어서 필터링하게 한다. 위 예시의 경우 학사 문의 글이라 판단 되지 않기에 다음과 같이 저장하지 않는다.

```bash
[DROP][LLM] | line=67 | title='충붕이들 졸업하면 보통 대기업 취직함?' | snippet='사촌언니 하이닉스 들어갔는디 ㄱㄴ?' | label_top=other | label_sub=취업 | confidence=0.9
```

</br>
만약 학사 문의 글이라 판단되면 다음과 같은 형식으로 저장된다.
</br>

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
