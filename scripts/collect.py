"""일요일 밤: 슬랙 답글 수집 → Claude API로 브리핑 갱신 → index.html 저장"""
import os, re, time, datetime, requests
from anthropic import Anthropic

TOKEN = os.environ["SLACK_BOT_TOKEN"]
USER = os.environ["SLACK_USER_ID"]
PAGES_URL = os.environ.get("PAGES_URL", "")
MODEL = os.environ.get("MODEL", "claude-sonnet-5")
H = {"Authorization": f"Bearer {TOKEN}"}


def slack(method, **kw):
    r = requests.post(f"https://slack.com/api/{method}", headers=H, json=kw).json()
    if not r.get("ok"):
        raise SystemExit(f"슬랙 오류({method}): {r.get('error')}")
    return r


channel = slack("conversations.open", users=USER)["channel"]["id"]

# 최근 7일 메시지에서 가장 최신 'OCREO 주간 체크' 질문 찾기 (서식 기호 무관하게 느슨한 매칭)
oldest = str(time.time() - 7 * 86400)
history = slack("conversations.history", channel=channel, oldest=oldest, limit=200)["messages"]
print(f"[debug] DM 채널 {channel}, 최근 7일 메시지 {len(history)}건")
for m in history[:10]:
    print(f"[debug] ts={m.get('ts')} user={m.get('user')} bot={m.get('bot_id')} text={m.get('text','')[:60]!r}")

question = next((m for m in history if "OCREO 주간 체크" in m.get("text", "")), None)

replies = []
if question:
    print(f"[debug] 질문 메시지 발견 ts={question['ts']} reply_count={question.get('reply_count')}")
    if question.get("reply_count"):
        thread = slack("conversations.replies", channel=channel, ts=question["ts"])["messages"][1:]
        replies += [m["text"] for m in thread if m.get("user") == USER]
    replies += [m["text"] for m in history
                if m.get("user") == USER and float(m["ts"]) > float(question["ts"]) and not m.get("thread_ts")]
else:
    # 예비 동작: 질문 메시지를 못 찾아도 최근 24시간 내 사용자의 DM 메시지가 있으면 답변으로 간주
    day_ago = time.time() - 86400
    replies = [m["text"] for m in history if m.get("user") == USER and float(m["ts"]) > day_ago]
    print(f"[debug] 질문 메시지 미발견 → 24시간 내 사용자 메시지 {len(replies)}건을 답변으로 사용")

if not replies:
    slack("chat.postMessage", channel=channel,
          text="⏰ 아직 답글이 없어 대시보드를 갱신하지 못했어요. 답글 남기시고 GitHub 저장소 Actions 탭에서 '일요일 밤 답글 수집' 워크플로를 Run 해주시면 반영됩니다!")
    raise SystemExit(0)

answers = "\n".join(f"- {t}" for t in replies)
doc = open("index.html", encoding="utf-8").read()
briefing = re.search(r'<section id="briefing".*?</section>', doc, re.S).group(0)
today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%-m/%-d")

client = Anthropic()
resp = client.messages.create(
    model=MODEL, max_tokens=3000,
    messages=[{"role": "user", "content": f"""OCREO 프로젝트 대시보드의 '이번 주 브리핑' 섹션을 PM의 슬랙 답변 기반으로 갱신해줘.

[현재 브리핑 섹션 HTML]
{briefing}

[PM의 이번 주 답변 (슬랙)]
{answers}

[규칙]
- 오늘은 {today} 일요일 밤. "최종 업데이트: {today} (일) 밤"으로 표기.
- 같은 구조(3컬럼: 진행 중 / 배포·공개 / 확인 대기)를 유지하되 답변의 실제 결과를 반영. 완료면 "✅ 완료", 지연이면 사유·새 일정.
- PM이 코멘트를 남겼으면 브리핑 하단에 "💬 PM 코멘트 — ..." 한 줄 추가 (기존 코멘트는 교체).
- 색은 블랙/블루 계열 Tailwind 클래스만, 주황(orange)은 지연·주의 신호에만. 비IT 임원이 읽는 문서이므로 일상어 사용.
- 답변에 없는 내용은 지어내지 말 것.

출력은 갱신된 <section id="briefing">...</section> HTML만, 다른 설명 없이."""}],
)
new_briefing = resp.content[0].text.strip()
m = re.search(r'<section id="briefing".*?</section>', new_briefing, re.S)
if not m:
    raise SystemExit("Claude 응답에서 브리핑 섹션을 찾지 못했습니다.")

doc = re.sub(r'<section id="briefing".*?</section>', lambda _: m.group(0), doc, count=1, flags=re.S)
open("index.html", "w", encoding="utf-8").write(doc)

slack("chat.postMessage", channel=channel,
      text=f"✅ 답변 반영 완료! 잠시 후 웹페이지에 자동 배포됩니다: {PAGES_URL}")
print("브리핑 갱신 완료")
