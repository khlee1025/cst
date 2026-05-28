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
2. 왼쪽에 하고 싶은 작업 입력
3. 1. 대사 적용
4. 2. 실행 전 확인
5. 3. 시뮬레이션 시작
6. CST 해석이 끝난 뒤 결과 불러오기
```

보조로 `숫자 직접 입력`, `스윕 설정`, `결과 불러오기`만 화면에 남겨두었습니다.

## 버튼 설명

### 1. 대사 적용

왼쪽에 적은 문장에서 `length`, `width`, `thickness`, `fmin`, `fmax`를 읽어서 기본 유닛셀 값에 바로 채웁니다.

예를 들어 아래처럼 쓰면 됩니다.

```text
length=100, width=10, thickness=2, fmin=1, fmax=18
```

이 버튼은 JSON도 같이 만들고, x/y `unit cell`, z `open add space` 경계조건을 기본으로 넣습니다. JSON/매크로에는 CST가 쓰는 값인 `expanded open`으로 저장됩니다.

### 2. 실행 전 확인

CST를 열지 않고 JSON, 치수, 주파수 범위, CST에 보낼 매크로를 확인합니다.

### 3. 시뮬레이션 시작

기본 메인 실행 버튼입니다. CST를 열고 형상, `Background Normal`, x/y `unit cell`, z `open add space`, Floquet port를 만든 뒤 기본 `HF Time Domain` solver type으로 CST의 `Setup Solver -> Start`에 해당하는 Solver Start를 실행합니다.

시작 버튼을 누르면 바로 CST를 실행하지 않고 먼저 시작 전 설정 디버그를 수행합니다.

- 필수 명령: units, frequency range, background, boundary, Floquet, rebuild, solver start
- 기본값 검사: Background Normal, x/y unit cell, z expanded open, Floquet mode 2
- 치수 검사: length/width/thickness/fmin/fmax
- 매크로 생성 검사: CST를 열기 전 `--dry-run`으로 VBA 블록 생성 확인

이 단계에서 error가 나오면 CST를 시작하지 않습니다.

이 버튼은 Touchstone export를 자동으로 하지 않습니다. CST solver가 실제로 도는 것이 먼저라서, 해석 완료 뒤 CST에서 `.s2p`를 export하거나 생성된 결과 폴더를 `결과 불러오기`로 읽습니다.

Floquet mode number 기본값은 `2`이고, `Zmin`/`Zmax`에 적용합니다.

```text
runs/
  날짜_시간_mesh_frame_unitcell/
    cst_project.cst
    cst_project.cst
    input_plan.json
    summary.json
```

### 현재 CST 시뮬레이션

이미 CST 창에 형상이 만들어져 있는데 solver만 안 돈 것 같으면 이 버튼을 누릅니다.

- 새 형상을 다시 만들지 않고 현재 열려 있는 CST 3D 프로젝트에 붙습니다.
- `Background Normal`, x/y `unit cell`, z `open add space`, Floquet mode `2`를 다시 적용합니다.
- 선택된 solver type을 한 번 더 지정합니다. 기본값은 `HF Time Domain`입니다.
- `Rebuild -> Solver Start`만 실행합니다.

즉, “도형은 보이는데 해석이 안 돈다”를 확인할 때 쓰는 버튼입니다.

### 숫자 직접 입력

CST나 JSON을 잘 몰라도 숫자만 넣어서 기본 모기장 ㅁ자 유닛셀 명령서를 만듭니다.

입력값:

- `length`: ㅁ자 외곽 한 변 길이, um
- `width`: 실 폭, um
- `thickness`: z축 두께, um
- `fmin`, `fmax`: 해석 주파수 범위, GHz
- 배경조건: 기본 `Normal`, epsilon `1`, mue `1`
- 경계조건: 기본으로 x/y `unit cell`, z `open add space` (`expanded open`)
- Solver: 기본 `HF Time Domain`, 필요하면 숫자 입력 창에서 `HF Frequency Domain`으로 변경
- Floquet mode number: 기본 `2`

여기서 넣은 값은 CST가 켜진 뒤 다시 입력하는 값이 아닙니다. Python이 실행 전에 JSON에 넣고, CST에 자동 전달합니다.

기본 단일 해석에서는 CST 파라미터를 만들지 않습니다. Python이 `length-width` 같은 식을 먼저 숫자로 계산해서 CST에 넘기므로 `New Parameter` 입력창이 뜨지 않아야 합니다.

### 스윕 설정

오른쪽 `스윕 설정` 탭에서 `width`, `length`, `thickness`, `fmin`, `fmax` 중 하나 또는 전체 변수 조합을 고릅니다.

값을 넣고 `스윕 실행 + 결과 보기`를 누르면 같은 CST 프로젝트 안에서 파라미터 값을 바꾸고, 각 케이스마다 Solver Start를 실행한 뒤 마지막에 S11/S21을 한 표로 합칩니다.

### 결과 불러오기

이미 CST에서 export한 `.s2p` 또는 CSV/TXT 결과를 한 번에 모읍니다.

1. `결과 불러오기` 클릭
2. 결과 파일이 있는 폴더 선택
3. `S11/S21 결과` 탭에서 요약 확인

출력 컬럼:

```text
source, freq_ghz, s11_db, s21_db, note
```

Touchstone `.s2p`는 `MA`, `DB`, `RI` 형식을 읽어서 dB로 정리합니다.

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

CST 형상 생성만:

```powershell
python .\cst_vibe_runner.py .\examples\02_mesh_frame_unitcell.json --visible --no-project-save
```

CST 내부에도 파라미터를 남기고 싶은 고급 사용자는 `--store-parameters`를 추가할 수 있습니다. 다만 이 옵션은 CST가 `New Parameter` 창을 띄울 수 있어서 기본값은 꺼져 있습니다.

## 파일 설명

```text
cst_vibe_gui.py          초보자용 GUI
cst_vibe_runner.py       CST COM 실행 엔진
CST_AUTOMATION_NOTES.md  CST/Floquet/solver 자동화 기준 메모
prompt_for_local_llm.md  LLM에게 JSON 생성을 시킬 때 쓰는 프롬프트
examples/                예제 JSON
requirements.txt         필요한 Python 패키지
MANUAL.md                더 자세한 설명서
DEBUG_WORKFLOW.md        에러 전달 방법
RF_RUN_PACKAGE.md        고급 결과 폴더 구조
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

- Floquet port는 자동 생성하며 mode number 기본값은 2입니다.
- 복잡한 구조는 LLM JSON으로 만들 수 있지만, 처음에는 `숫자 직접 입력`으로 검증하는 것을 추천합니다.
- 결과 비교 도구는 다음 단계입니다. 현재는 CST S11/S21 결과를 안정적으로 만들고 CSV로 모으는 데 집중합니다.
