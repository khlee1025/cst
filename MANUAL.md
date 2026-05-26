# CST Vibe Runner 사용 설명서

이 문서는 실제 사용 순서 중심 설명서입니다. CST나 JSON을 잘 몰라도 아래 순서대로 하면 됩니다.

## 1. 프로그램 열기

압축을 푼 폴더에서 PowerShell을 열고 실행합니다.

```powershell
python .\cst_vibe_gui.py
```

창 이름이 `CST Vibe Runner - Simple Mode`로 뜨면 정상입니다.

## 2. 첫 화면 구조

화면은 크게 세 부분입니다.

- 왼쪽: 내가 원하는 설계를 말로 적는 곳
- 왼쪽 버튼: 실제 작업 순서
- 오른쪽: 실행 출력과 JSON 명령서 확인

처음에는 오른쪽 JSON을 직접 고칠 필요가 거의 없습니다.

## 3. CST 2025 기본값 확인

우측 상단 `설정`을 누릅니다.

`CST ProgID`가 아래처럼 되어 있으면 정상입니다.

```text
CSTStudio.Application.2025
```

`CST 화면 보이기`를 켜면 CST가 열리는 모습을 볼 수 있습니다. 처음 테스트할 때는 켜두는 것을 추천합니다.

## 4. LLM 없이 기본 모기장 유닛셀 만들기

가장 안정적인 첫 사용법입니다.

1. 왼쪽 요청 메모에 원하는 값을 적습니다.
2. `1. 대사 적용` 클릭
3. `2. 실행 전 확인` 클릭
4. 문제가 없으면 `3. CST 실행 + 결과폴더`

입력값 의미:

| 이름 | 의미 | 단위 |
| --- | --- | --- |
| `length` | ㅁ자 외곽 한 변 길이이자 기본 space | um |
| `width` | 실 폭 | um |
| `thickness` | z축 두께 | um |
| `fmin` | 시작 주파수 | GHz |
| `fmax` | 끝 주파수 | GHz |

경계조건은 기본으로 x/y `unit cell`, z `open`입니다.

주의: 이 값들은 CST가 켜진 뒤 손으로 다시 넣는 값이 아닙니다. Python이 CST에 자동으로 넘깁니다.

더 정확히 말하면 기본 실행에서는 CST에 새 파라미터를 만들지 않고, Python이 먼저 계산한 숫자를 넘깁니다. 예를 들어 `length=100`, `width=10`이면 `length-width`를 CST에 보내는 대신 `90`을 보냅니다. 그래서 CST의 `New Parameter` 팝업에서 사용자가 다시 입력할 일이 없어야 합니다.

기본 좌표계:

```text
원점: ㅁ자의 한쪽 모서리 기준
x 범위: 0 .. length
y 범위: -length .. 0
z 범위: 0 .. thickness
단위: um
```

## 5. LLM으로 대사 입력하기

회사/로컬 LLM 서버를 쓰려면 먼저 `설정`에서 아래를 맞춥니다.

```text
LLM Base URL
Model
API Key
Max Tokens
```

그다음 순서:

1. 왼쪽 요청 메모에 원하는 설계를 적습니다.
2. `대사 -> JSON` 클릭
3. 오른쪽 JSON 탭에서 결과를 한 번 확인
4. `실행 전 확인`
5. `CST 실행 + 결과폴더`

좋은 대사 예시:

```text
모기장 구조의 ㅁ자 차폐 유닛셀을 만들어줘.
원점 기준으로 x+ 방향 실과 y- 방향 실을 만들고 대칭 이동해서 ㅁ자를 만들어줘.
length는 100 um, width는 10 um, thickness는 2 um로 해줘.
주파수는 1 GHz부터 18 GHz까지.
포트는 만들지 말고 형상만 만들어줘.
```

나쁜 대사 예시:

```text
대충 좋은 차폐 구조 만들어줘.
```

LLM은 숫자와 조건이 구체적일수록 안정적입니다.

## 6. 각 버튼이 하는 일

### 1. 대사 적용

요청 메모에서 숫자를 읽어서 기본 모기장 유닛셀 값에 바로 반영합니다.

예:

```text
length=100, width=10, thickness=2, fmin=1, fmax=18
```

이 버튼은 JSON을 만들고 경계조건도 x/y `unit cell`, z `open`으로 넣습니다.

### 대사 -> JSON

요청 메모를 LLM에 보내서 CST JSON 명령서로 바꿉니다.

OpenAI 패키지가 없다고 뜨면:

```powershell
python -m pip install openai
```

### 기본 유닛셀 값 입력

LLM 없이 숫자 기반으로 안전한 기본 JSON을 만듭니다.

초심자에게 가장 추천하는 시작점입니다.

### 실행 전 확인

CST를 열지 않고 검증합니다.

확인하는 것:

- JSON 형식
- 파라미터 숫자 여부
- 실 폭과 외곽 길이 관계
- 주파수 범위
- CST로 보낼 매크로 내용

여기서 `종료코드 0`이면 기본 문법은 통과한 것입니다.

### CST 2025 연결 테스트

CST COM 연결을 실제로 확인합니다. CST가 설치된 PC에서만 의미가 있습니다.

실패하면 `문제 진단`을 눌러 자세한 원본 에러를 봅니다.

### CST 실행 + 결과폴더

실제 CST 실행과 결과 폴더 생성을 같이 합니다.

결과는 `runs` 폴더에 생깁니다.

파일을 남기는 버튼은 기본적으로 `CST 실행 + 결과폴더`와 `스윕 실행 + 결과폴더`입니다.

### 파라미터 스윕

`width`, `length`, `thickness`, `fmin`, `fmax` 중 하나를 골라 여러 값으로 반복 실행합니다.

사용 순서:

```text
1. 파라미터 스윕 클릭
2. 스윕 파라미터 입력 또는 선택, 예: width
3. 값 목록 입력, 예: 5, 10, 15
4. 스윕 드라이런 또는 스윕 실행 + 결과폴더 클릭
```

스윕은 각 값마다 새 JSON을 만들고, 각 JSON을 별도 실행으로 돌립니다. CST 내부 파라미터를 직접 흔들지 않기 때문에 `New Parameter` 팝업을 피하는 방식입니다.

결과는 값마다 별도 `runs` 폴더에 저장됩니다.
단, `스윕 드라이런`은 미리보기/검증용이라 `runs` 폴더를 만들지 않습니다.

### 문제 진단

한 명령에서 실패해도 멈추지 않고 다음 명령까지 시도합니다. 어떤 명령에서 CST가 거부했는지 찾을 때 씁니다.

진단은 프로젝트 파일을 저장하지 않고, `runs` 폴더도 만들지 않습니다. 내부 임시 JSON은 윈도우 임시폴더에 잠깐 만들었다가 실행 후 자동 삭제합니다.

### JSON 보기

현재 만들어진 JSON 명령서를 오른쪽 탭에서 보여줍니다.

### 리포트 저장

출력창 내용을 `.txt` 파일로 저장합니다. 다른 LLM이나 사람에게 에러를 전달할 때 씁니다.

### 출력 복사

출력창 전체를 클립보드로 복사합니다.

## 7. 종료코드 보는 법

| 종료코드 | 뜻 |
| --- | --- |
| 0 | 정상 |
| 1 | Python 또는 CST 실행 중 예상 못한 예외 |
| 2 | JSON/입력/명령 검증 실패 또는 CST 명령 실패 |

예를 들어 `실행 전 확인`에서 0이면 CST 없이도 JSON은 대체로 정상입니다.

`CST 실행 + 결과폴더`에서 2가 나오면 출력창의 `Original error`를 봐야 합니다.

## 8. 자주 나오는 문제

### python이라고만 뜨고 실행이 안 됨

PowerShell에서 현재 폴더가 다를 수 있습니다.

```powershell
dir
```

`cst_vibe_gui.py`가 있는 폴더에서 실행해야 합니다.

### OpenAI 패키지가 필요하다고 뜸

```powershell
python -m pip install openai
```

또는 전체 설치:

```powershell
python -m pip install -r requirements.txt
```

### pywin32가 필요하다고 뜸

CST를 실제로 실행하려면 필요합니다.

```powershell
python -m pip install pywin32
```

### CST가 안 열림

먼저 CST 2025 CT를 직접 한 번 실행한 뒤 다시 시도하세요.

설정의 `CST ProgID` 기본값:

```text
CSTStudio.Application.2025
```

러너가 자동으로 재시도하는 값:

```text
CSTStudio.Application
CSTStudio.Application.2024
CSTStudio.Application.2023
```

### CST가 New Parameter를 계속 물어봄

최신 버전에서는 기본 실행에서 `StoreParameter`를 호출하지 않고 숫자로 계산해서 넘깁니다.

출력창에 아래 문장이 있어야 합니다.

```text
[param] CST macro expressions resolved to numbers; no New Parameter dialog is needed.
```

만약 CLI에서 `--store-parameters`를 직접 붙였다면 빼고 다시 실행하세요.

### AddToHistory 에러

이 도구는 CST 2025에서 `AddToHistory(name, code)`가 이상하게 전달되는 경우를 대비해 다른 COM 호출 방식도 자동 시도합니다.

그래도 실패하면 `문제 진단`을 누르고 출력창을 저장해서 에러 메시지를 확인하세요.

## 9. CST 없이 확인 가능한 것

CST가 없어도 가능합니다.

```text
GUI 열기
기본 유닛셀 JSON 생성
LLM JSON 생성
실행 전 확인
드라이런 로그 확인
```

CST가 있어야 가능합니다.

```text
CST 2025 연결 테스트
CST 실행 + 결과폴더
실제 .cst 프로젝트 저장
실제 S-parameter export
```

## 10. 결과 폴더

`CST 실행 + 결과폴더`를 누르면 `runs` 아래에 실행별 폴더가 생깁니다.

```text
runs/
  날짜_시간_설계명/
    input_plan.json
    design_params.json
    summary.json
    cst_project.cst
    exports/
    logs/
```

파일 의미:

- `input_plan.json`: CST에 보낸 전체 명령서
- `design_params.json`: 설계 파라미터만 정리한 파일
- `summary.json`: 실행 요약
- `cst_project.cst`: CST 프로젝트
- `exports`: 나중에 S-parameter, csv 등을 넣을 위치

## 11. 추천 작업 습관

처음 구조를 만들 때:

```text
기본 유닛셀 값 입력 -> 실행 전 확인 -> CST 2025 연결 테스트
```

LLM 대사를 실험할 때:

```text
대사 -> JSON 만들기 -> 실행 전 확인 -> CST 실행 + 결과폴더
```

에러가 날 때:

```text
문제 진단 -> 리포트 저장 -> Original error 확인
```

좋은 결과가 나온 뒤:

```text
runs 폴더의 input_plan.json과 design_params.json을 Python 비교 모듈 입력으로 사용
```
