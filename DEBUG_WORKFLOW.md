# 오류가 많을 때 쓰는 디버그 흐름

이 문서는 CST 2025 CT에서 매크로 오류가 반복될 때, 매번 파일을 다시 받고 설명을 주고받는 불편함을 줄이기 위한 흐름입니다.

## 1. 앞으로는 Step Diagnose 먼저

GUI에서 문제가 생기면 바로 `CST 실행`만 반복하지 말고 아래 순서로 확인하세요.

```text
1. CST 연동 테스트
2. 형상 JSON 만들기
3. 드라이런
4. Step Diagnose
5. Save Report
```

`Step Diagnose`는 한 명령이 실패해도 다음 명령을 계속 시도합니다.
그래서 어떤 명령은 통과했고 어떤 명령은 실패했는지 한 번에 볼 수 있습니다.

## 2. Save Report

`Save Report`를 누르면 실행 출력 전체를 텍스트 파일로 저장할 수 있습니다.

추천 파일명:

```text
cst_vibe_diagnostic_report.txt
```

회사 LLM에는 이 파일 내용을 그대로 넣고 이렇게 물어보면 됩니다.

```text
아래는 CST 2025 CT에서 CST Vibe Runner Step Diagnose를 실행한 리포트입니다.
실패한 command 번호와 History name을 기준으로 원인을 분류해 주세요.
수정이 필요한 JSON 명령 또는 CST VBA 매크로만 제안해 주세요.

[리포트 내용 붙여넣기]
```

## 3. 종료코드 해석

```text
종료코드 0: 성공
종료코드 1: 예상하지 못한 Python/CST 오류
종료코드 2: 프로그램이 잡아낸 PlanError 또는 JSON/CST 매크로 오류
```

`Step Diagnose`에서 종료코드 2가 나와도 이상한 것이 아닙니다.
중요한 것은 출력 중간의 `[ok]`와 `[diagnostic-error]`입니다.

## 4. 매번 ZIP을 다시 받기 싫을 때

Git으로 받은 폴더라면 아래만 실행하면 최신 버전으로 업데이트됩니다.

```powershell
git pull
```

ZIP으로 받은 경우에는 업데이트가 자동으로 되지 않습니다.
그때는 새 ZIP을 다시 받아야 합니다.

가능하면 한 번만 Git으로 받는 것을 추천합니다.

```powershell
git clone https://github.com/khlee1025/cst.git
cd cst
python .\cst_vibe_gui.py
```

이후에는:

```powershell
git pull
python .\cst_vibe_gui.py
```

## 5. CST 2025 CT에서 안전한 기본 흐름

처음에는 포트와 solver를 넣지 않습니다.

```text
유닛셀 경계조건 포함: 끔
포트: 없음
solver_start: 없음
형상: substrate + top_patch만
```

형상이 맞게 생기는 것을 확인한 뒤에만 포트와 경계조건을 추가하세요.
