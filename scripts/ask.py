"""일요일 저녁: 슬랙 DM으로 주간 진행 상황 질문 전송"""
import os, re, html, requests

TOKEN = os.environ["SLACK_BOT_TOKEN"]
USER = os.environ["SLACK_USER_ID"]
H = {"Authorization": f"Bearer {TOKEN}"}


def slack(method, **kw):
    r = requests.post(f"https://slack.com/api/{method}", headers=H, json=kw).json()
    if not r.get("ok"):
        raise SystemExit(f"슬랙 오류({method}): {r.get('error')}")
    return r


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


# 대시보드에서 이번 주 예정 항목을 읽어 질문에 포함
context = ""
try:
    doc = open("index.html", encoding="utf-8").read()
    m = re.search(r'<section id="briefing".*?</section>', doc, re.S)
    if m:
        cols = re.findall(r'<p class="[^"]*font-bold[^"]*mb-1">([^<]+)</p>\s*<p[^>]*>(.*?)</p>', m.group(0), re.S)
        for name, body in cols:
            if "배포" in name or "진행" in name:
                context += f"\n· {name.strip()}: {strip_tags(body)[:200]}"
except Exception:
    pass

msg = f"""🗓️ *[OCREO 주간 체크]* 안녕하세요! 내일(월) 실장님이 대시보드를 열어보기 전에 이번 주 진행 상황을 확인합니다.
이 메시지에 *스레드 답글*로 남겨주세요 — 오늘 밤 10시에 수집해 대시보드와 웹페이지에 자동 반영됩니다.
{f'참고로 대시보드 기준 이번 주 항목은:{context}' if context else ''}

1️⃣ 배포·공개 예정이던 항목들 — 각각 완료 / 지연 / 일부만 되었나요?
2️⃣ 진행 중 항목들 — 순조로운가요, 지연되는 건 없나요?
3️⃣ 새로 생긴 이슈나 일정 변경이 있나요?
4️⃣ 실장님 확인 대기 사항 중 결정된 것이 있나요?
5️⃣ 그 외 실장님께 공유할 코멘트가 있다면 자유롭게!"""

channel = slack("conversations.open", users=USER)["channel"]["id"]
slack("chat.postMessage", channel=channel, text=msg)
print("질문 전송 완료")
