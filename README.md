# CST Vibe Runner

CST Vibe Runner는 **한국어로 설계 의도를 적고, 그 내용을 JSON 명령서로 바꾼 뒤, CST Studio Suite 2025 CT에서 모기장 구조 차폐 유닛셀을 Python으로 실행하는 도구**입니다.

최종 목표는 아래 흐름입니다.

```text
내가 대사 입력
-> 회사/로컬 LLM이 CST JSON 생성
-> Python이 CST 2025 CT 자동 실행
-> runs 폴더에 입력값/결과 정리
-> 나중에 Python 예측 모듈 결과와 비교
```

처음 쓰는 사람 기준으로 GUI를 단순화했습니다. 기본값은 **CSTStudio.Application.2025**입니다.

## 다운로드

GitHub 화면에서 받는 법:

1. 저장소 `khlee1025/cst`로 갑니다.
2. branch가 `master`인지 확인합니다.
3. 초록색 `Code` 버튼을 누릅니다.
4. `Download ZIP`을 누릅니다.
5. ZIP을 풀고 그 폴더에서 실행합니다.

바로 받기:

[Download ZIP](https://github.com/khlee1025/cst/archive/refs/heads/master.zip)

Git으로 받기:

```powershell
git clone https://github.com/khlee1025/cst.git
cd cst
```

## 설치

Python 3.13에서도 실행 가능합니다.

```powershell
python --version
python -m pip install -r requirements.txt
```

`requirements.txt`에는 아래가 들어 있습니다.

- `pywin32`: CST COM 자동 실행용
- `openai`: 회사/로컬 LLM 서버 연결용

CST가 없는 PC에서도 GUI 실행, JSON 생성, 실행 전 확인은 할 수 있습니다. 실제 CST 실행만 CST 설치 PC에서 가능합니다.

## 실행

```powershell
python .\cst_vibe_gui.py
```

GUI가 안 열리면 먼저 현재 폴더가 맞는지 확인하세요.

```powershell
dir
```

`cst_vibe_gui.py`, `cst_vibe_runner.py`, `examples`가 보여야 합니다.

## 가장 쉬운 사용 순서

처음에는 이 순서만 기억하면 됩니다.

```text
1. 설정
2. 기본 유닛셀 값 입력
3. 실행 전 확인
4. CST 2025 연결 테스트
5. CST 실행 + 결과폴더
```

LLM을 쓰는 경우:

```text
1. 설정에서 LLM Base URL / Model / API Key 저장
2. 왼쪽 요청 메모에 대사 입력
3. 대사 -> JSON 만들기
4. 실행 전 확인
5. CST 실행 + 결과폴더
```

스윕을 쓰는 경우:

```text
1. 기본 유닛셀 값 입력
2. 실행 전 확인
3. 파라미터 스윕
4. 스윕 파라미터 선택, 예: width
5. 값 목록 입력, 예: 5, 10, 15
6. 스윕 드라이런 또는 스윕 실행 + 결과폴더
```

## 버튼 설명

### 설정

우측 상단 버튼입니다.

- `CST ProgID`: 기본값은 `CSTStudio.Application.2025`
- `CST 화면 보이기`: 켜면 CST가 실제로 열리는 것을 볼 수 있습니다.
- `LLM Base URL`: 회사/로컬 LLM 서버 주소
- `Model`: 사용할 모델명
- `API Key`: 서버가 요구하면 입력, 필요 없으면 비워도 됩니다.
- `LLM 연결 테스트`: LLM 서버 연결 확인
- `저장`: 다음 실행 때도 같은 설정 사용

### 기본 유닛셀 값 입력

CST나 JSON을 잘 몰라도 숫자만 넣어서 기본 모기장 ㅁ자 유닛셀 명령서를 만듭니다.

입력값:

- `length`: ㅁ자 외곽 한 변 길이, um
- `width`: 실 폭, um
- `thickness`: z축 두께, um
- `fmin`, `fmax`: 해석 주파수 범위, GHz

여기서 넣은 값은 CST가 켜진 뒤 다시 입력하는 값이 아닙니다. Python이 실행 전에 JSON에 넣고, CST에 자동 전달합니다.

기본 실행에서는 CST 안에 새 파라미터를 만들지 않습니다. 예를 들어 `length-width`는 Python에서 먼저 `90`으로 계산해서 CST에 넘깁니다. 그래서 CST가 `New Parameter` 창을 띄우며 다시 물어보지 않아야 합니다.

### 대사 -> JSON 만들기

왼쪽 요청 메모를 LLM으로 보내 CST JSON 명령서로 바꿉니다.

예시 대사:

```text
모기장 구조의 ㅁ자 차폐 유닛셀을 만들어줘.
원점 기준으로 x+ 방향 실과 y- 방향 실을 만들고, 대칭 이동해서 ㅁ자를 만들어줘.
length는 100 um, width는 10 um, thickness는 2 um.
1 GHz부터 18 GHz까지 확인하고 싶어.
포트는 아직 만들지 말고 형상 중심으로 만들어줘.
```

LLM 결과가 이상하면 `기본 유닛셀 값 입력`으로 다시 만드는 것이 더 안전합니다.

### 실행 전 확인

CST를 열지 않고 아래를 확인합니다.

- JSON 문법이 맞는지
- 핵심 RF 파라미터가 숫자인지
- 실 폭이 외곽 길이에 비해 너무 큰지
- 주파수 범위가 이상하지 않은지
- CST에 보낼 명령이 어떤 형태인지

여기서 성공하면 `종료코드 0`이 뜹니다.

### CST 2025 연결 테스트

실제 CST COM 연결만 먼저 확인합니다. CST가 열리고 기본 명령이 넘어가는지 보는 단계입니다.

- 성공: `종료코드 0`
- 실패: `종료코드 1` 또는 `2`와 함께 원본 에러 출력

### CST 실행 + 결과폴더

실제 CST를 실행하고 `runs` 폴더에 이번 실행 기록을 남깁니다.

생성되는 구조:

```text
runs/
  20260526_181500_mesh_frame_unitcell_length100_width10_thickness2/
    input_plan.json
    design_params.json
    summary.json
    cst_project.cst
    exports/
    logs/
```

나중에 Python 예측 모듈과 비교할 때 이 폴더를 기준으로 쓰면 됩니다.

### 파라미터 스윕

`width`, `length`, `thickness`, `fmin`, `fmax` 같은 값을 여러 번 바꿔가며 실행합니다.

예:

```text
parameter = width
values = 5, 10, 15
```

이 기능은 CST 내부 파라미터를 흔드는 방식이 아닙니다. 각 값마다 JSON을 새로 만들고, Python이 좌표를 다시 계산해서 CST에 숫자로 넘깁니다. 그래서 `New Parameter` 팝업을 피할 수 있습니다.

각 값은 별도 `runs` 폴더로 저장됩니다.

### 문제 진단

CST 실행이 실패했을 때 누릅니다. 한 명령에서 실패해도 다음 명령을 계속 보내서 어디까지 성공했는지 확인합니다.

## 종료코드

```text
0 = 정상
1 = Python 실행 중 예상 못한 예외 또는 CST가 명령을 거부
2 = JSON/입력/계획 검증 실패 또는 CST 명령 실패를 도구가 잡아낸 상태
```

중요한 것은 숫자만이 아니라 출력창의 `Original error`, `[diagnostic-error]`, `[ok]` 문장입니다.

## CST 2025 연결 문제

기본 ProgID는 아래입니다.

```text
CSTStudio.Application.2025
```

러너는 2025가 실패하면 아래도 자동으로 시도합니다.

```text
CSTStudio.Application
CSTStudio.Application.2024
CSTStudio.Application.2023
```

그래도 실패하면 CST가 COM 등록이 안 된 상태일 수 있습니다. CST 2025 CT를 한 번 직접 실행한 뒤 다시 시도하세요.

## CLI 사용

GUI 없이도 실행할 수 있습니다.

드라이런:

```powershell
python .\cst_vibe_runner.py .\examples\02_mesh_frame_unitcell.json --dry-run
```

CST 실행:

```powershell
python .\cst_vibe_runner.py .\examples\02_mesh_frame_unitcell.json --visible --package-run
```

CST 내부에도 파라미터를 남기고 싶은 고급 사용자는 `--store-parameters`를 추가할 수 있습니다. 다만 이 옵션은 CST가 `New Parameter` 창을 띄울 수 있어서 기본값은 꺼져 있습니다.

문제 진단:

```powershell
python .\cst_vibe_runner.py .\examples\02_mesh_frame_unitcell.json --visible --continue-on-error
```

## 파일 설명

```text
cst_vibe_gui.py          초보자용 GUI
cst_vibe_runner.py       CST COM 실행 엔진
prompt_for_local_llm.md  LLM에게 JSON 생성을 시킬 때 쓰는 프롬프트
examples/                예제 JSON
requirements.txt         필요한 Python 패키지
MANUAL.md                더 자세한 설명서
DEBUG_WORKFLOW.md        에러 전달/진단 방법
RF_RUN_PACKAGE.md        runs 결과 폴더 구조
```

## LLM 서버 설정

`khlee1025/claude-exam` 방식처럼 OpenAI 호환 API를 사용합니다.

환경변수로도 설정할 수 있습니다.

```powershell
$env:LLM_BASE_URL="http://10.240.246.158:8000/v1"
$env:LLM_MODEL="Qwen3.5-122B"
$env:LLM_API_KEY="EMPTY"
python .\cst_vibe_gui.py
```

GUI의 `설정`에서 저장하면 `cst_llm_config.json`이 로컬에 생깁니다. 이 파일은 개인 설정이라 Git에는 올라가지 않습니다.

## 지금 버전에서 의도적으로 제한한 것

- 포트는 자동 생성하지 않는 기본 흐름을 우선합니다.
- 복잡한 구조는 LLM JSON으로 만들 수 있지만, 처음에는 `기본 유닛셀 값 입력`으로 검증하는 것을 추천합니다.
- CST 결과 해석/그래프 비교 도구는 다음 단계입니다. 현재는 좋은 CST 실행 결과를 안정적으로 만드는 데 집중합니다.
