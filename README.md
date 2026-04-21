# inter-macro (safe monitor)

이 프로젝트는 티켓 페이지를 주기적으로 확인하고, 사용자가 지정한 조건(`가용 인원 >= 목표 인원`)을 만족하면 알림을 주는 도구입니다.

- 결제 자동화/캡차 우회/대기열 우회 기능은 포함하지 않습니다.
- 최종 예매/결제는 사용자가 직접 진행해야 합니다.

## 1) 설치

```bash
cd /Users/jeong-yoonho/IdeaProjects/inter-macro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 2) GUI 실행 (입력창)

```bash
source .venv/bin/activate
python ticket_gui.py
```

GUI에서 입력:
- 사이트 선택
- 뒤 경로(Path) 또는 전체 URL
- 시간 확인 URL(선택)
- 인원수
- 자동 실행 모드(`바로 시작` 또는 `예약 시작`)
- 시작 시간(`YYYY-MM-DD HH:MM:SS`, 예약 시작일 때 사용)
- 일자 텍스트(선택, 예: `2026.05.01`)
- 일자 선택자(선택, 예: `.dateItem button`)
- 모달 닫기 선택자(선택, 쉼표로 여러 개 가능)
- 회차 텍스트(선택, 예: `19:00` 또는 `2회`)
- 회차 선택자(선택, 예: `.timeItem button`)
- 예매 버튼 텍스트(선택, 예: `예매하기`)
- 예매 버튼 선택자(선택, 예: `.btn-booking`)
- CSS 선택자

입력하지 않아도 되는 항목:
- 모달 닫기 선택자/예매 버튼 정보를 비우면, 프로그램이 공통 패턴(닫기/close, 예매하기/booking 등)으로 자동 스캔을 시도합니다.
- 사이트 구조가 다르면 오탐/미탐이 있을 수 있으므로, 실패 시 선택자를 직접 넣는 방식이 가장 안정적입니다.

인터파크 기본값:
- 모달 닫기 선택자: `.popupCloseBtn`
- 예매 버튼 선택자: `.sideBtn`
- 위 값이 비어 있으면 자동으로 주입됩니다.

버튼:
- `시작`: 모니터링 실행
- `중지`: 현재 실행 중지
- `시간 확인`: 시간 확인 URL의 서버 시각(Date 헤더) 확인

실행값은 `monitor_settings.json`에 자동 저장되어 다음 실행 시 복원됩니다.

### tkinter 호환 이슈가 있을 때 (권장 대체)

일부 macOS 구버전/런타임 조합에서 `ticket_gui.py`가 `Tk` 초기화 단계에서 종료될 수 있습니다.
이 경우 브라우저 기반 입력창을 사용하세요.

```bash
source .venv/bin/activate
python3 ticket_webui.py
```

브라우저에서 아래 주소를 엽니다.

- `http://127.0.0.1:8765`

## 3) macOS 설치형(.app) 빌드

```bash
./build_macos_app.sh
```

빌드 결과:
- `dist/InterMacro.app`

## 4) CLI 실행 (선택)

```bash
python ticket_watch.py \
  --url "https://example.com/ticket/123" \
  --people 2 \
  --modal-close-selectors ".popup-close,.btn-close" \
  --date-text "2026.05.01" \
  --date-selector ".dateItem button" \
  --round-text "19:00" \
  --round-selector ".timeItem button" \
  --reserve-text "예매하기" \
  --reserve-selector ".btn-booking" \
  --selector "#remainSeatCount" \
  --time-url "https://example.com" \
  --interval 1.5 \
  --headed
```

## 5) 파일 구성

- `ticket_gui.py`: 데스크톱 입력창 실행기
- `ticket_watch.py`: 모니터링 핵심 로직(CLI)
- `build_macos_app.sh`: macOS `.app` 빌드 스크립트
- `requirements.txt`: 런타임 의존성
