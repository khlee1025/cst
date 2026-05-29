# CST Vibe Runner

한국어로 설계 의도를 적으면 로컬/회사 LLM이 CST 실행용 JSON으로 바꾸고, Python이 CST Studio Suite 2025 CT를 열어 모기장 구조 차폐 유닛셀을 만드는 도구입니다.

현재 1단계 목표는 하나입니다.

```text
모기장 유닛셀 생성
-> Background / Boundary / Floquet 기본 세팅
-> HF Time Domain solver 시작
-> 나중에 S11/S21 결과 정리
```

아직 모든 CST 설계를 다루는 범용 툴이 아닙니다. 먼저 기본 유닛셀이 CST에서 안정적으로 돌아가게 만드는 것이 기준입니다.

## 다운로드

GitHub에서 받는 방법:

1. [khlee1025/cst](https://github.com/khlee1025/cst)로 갑니다.
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

Python 3.13에서 실행 가능합니다.

```powershell
python --version
python -m pip install -r requirements.txt
```

`requirements.txt`에는 기본적으로 다음이 들어 있습니다.

- `pywin32`: CST COM fallback 자동화용
- `openai`: 회사/로컬 LLM 서버 연결용

CST가 없는 PC에서도 GUI 실행, JSON 생성, dry-run 확인은 가능합니다. 실제 CST 실행은 CST 2025 CT가 설치된 PC에서만 됩니다.

## 실행

```powershell
python .\cst_vibe_gui.py
```

폴더가 맞는지 확인하려면:

```powershell
dir
```

`cst_vibe_gui.py`, `cst_vibe_runner.py`, `examples`가 보여야 합니다.

## 가장 쉬운 사용 순서

```text
1. 숫자 직접 입력 또는 하고 싶은 작업 입력
2. 적용 버튼으로 JSON 생성
3. 실행 전 확인
4. 시뮬레이션 시작
5. CST 해석 완료 후 결과 불러오기
```

처음에는 LLM 없이 `숫자 직접 입력`으로 확인하는 것을 추천합니다. 이게 성공해야 LLM JSON 변환도 믿을 수 있습니다.

## 기본 유닛셀 구조

기본 형상은 모기장 형태의 사각 프레임입니다.

- 단위: `um`
- 주파수 단위: `GHz`
- `length`: 유닛셀 한 변 길이
- `width`: 실/금속 기둥 폭
- `thickness`: z축 두께
- `fmin`, `fmax`: 해석 주파수 범위
- 재질: 기본 `PEC`
- Background: `Normal`, epsilon `1`, mue `1`
- Boundary: x/y `unit cell`, z `expanded open`
- Floquet: `Zmin`, `Zmax`, mode number `2`
- Solver: 기본 `HF Time Domain`

기본 단일 실행에서는 CST 파라미터를 일부러 만들지 않습니다. Python이 `length-width` 같은 식을 먼저 숫자로 계산해서 CST에 넘깁니다. 그래서 정상이라면 CST의 `New Parameter` 입력창이 뜨면 안 됩니다.

## 버튼 설명

### 적용

입력한 숫자나 LLM이 만든 JSON을 현재 실행 계획으로 적용합니다.

예:

```text
length=100, width=10, thickness=2, fmin=1, fmax=18
```

### 실행 전 확인

CST를 열기 전에 다음을 검사합니다.

- JSON 문법
- 필수 명령 존재 여부
- length/width/thickness/fmin/fmax 숫자 검증
- Background / Boundary / Floquet / Solver 설정
- dry-run 매크로 생성

### 시뮬레이션 시작

CST를 열고 다음 순서로 실행합니다.

```text
units
solver type
background
frequency range
brick 4개 생성
rebuild
boundary
floquet port
rebuild
solver start
```

이 버튼은 Touchstone export를 바로 붙이지 않습니다. 지금 목표는 먼저 CST solver가 실제로 도는지 확인하는 것입니다.

## CST 연결 방식

기본 실행 방식은 `--api auto`입니다.

`auto`는 먼저 CST 공식 Python API를 찾습니다. 성공하면 로그에 아래처럼 나옵니다.

```text
[cst-python] Connected through CST Python API
[cst-python] add_to_history: set units
[cst-python] modeler.run_solver completed
```

공식 API를 못 찾으면 기존 COM 방식으로 자동 fallback합니다.

```text
[cst-python] unavailable, falling back to COM: ...
[cst] Connected ProgID: CSTStudio.Application.2025
```

가능하면 공식 CST Python API가 잡히는 쪽이 좋습니다. CST 설치 위치가 특이해서 못 찾는다면 PowerShell에서 CST의 `python_cst_libraries` 폴더를 직접 지정할 수 있습니다.

예:

```powershell
$env:CST_PYTHON_LIB="C:\Program Files\CST Studio Suite 2025\AMD64\python_cst_libraries"
python .\cst_vibe_gui.py
```

## 정상 로그 기준

단일 실행에서 봐야 하는 핵심 로그는 아래입니다.

```text
[param] CST macro expressions resolved to numbers; no New Parameter dialog is needed.
[ok] commands[...] op=boundary
[ok] commands[...] op=floquet_port
[ok] commands[...] op=solver_start
```

공식 CST Python API가 잡혔다면 solver 시작은 보통 아래처럼 보입니다.

```text
[cst-python] modeler.run_solver completed
```

COM fallback이면 아래 계열 로그가 나옵니다.

```text
[cst] Solver.Start completed
```

## 결과 보기

현재는 CST solver가 끝난 뒤 결과를 불러오는 흐름입니다.

1. CST에서 해석이 끝났는지 확인합니다.
2. CST에서 `.s2p` 또는 CSV/TXT를 export합니다.
3. GUI의 `결과 불러오기`로 결과 폴더를 선택합니다.
4. `해석 후 S11/S21` 탭에서 정리된 값을 봅니다.

지원 형식:

- Touchstone `.s2p`
- S11/S21 CSV 또는 TXT

출력 컬럼:

```text
source, freq_ghz, s11_db, s21_db, note
```

## 스윕

스윕은 한 CST 프로젝트 안에서 케이스를 반복합니다.

```text
StoreParameter
-> Rebuild
-> Solver Start
-> Touchstone export 시도
```

단일 실행과 다르게 스윕은 CST 내부 파라미터를 사용합니다. GUI의 `스윕 확인`은 CST를 열지 않고 명령 흐름만 확인하고, `스윕 시작`은 실제 CST에서 케이스를 반복합니다.

처음 확인 순서는 다음이 안전합니다.

```text
1. 단일 실행 성공
2. CST solver가 실제로 도는 것 확인
3. `width` 하나만 `스윕 확인`
4. `width` 하나만 `스윕 시작`
5. 여러 변수 조합 스윕
6. 생성된 `.s2p`가 있으면 S11/S21 자동 수집
```

Touchstone export는 케이스마다 시도하지만, export가 실패해도 solver 반복 자체는 계속 진행합니다. 이 경우 CST에서 직접 `.s2p`를 export한 뒤 `결과 불러오기`로 같은 폴더를 선택하면 됩니다.

## CLI 사용

dry-run:

```powershell
python .\cst_vibe_runner.py .\examples\02_mesh_frame_unitcell.json --dry-run --no-project-save
```

CST 실행:

```powershell
python .\cst_vibe_runner.py .\examples\02_mesh_frame_unitcell.json --visible
```

공식 CST Python API만 강제로 사용:

```powershell
python .\cst_vibe_runner.py .\examples\02_mesh_frame_unitcell.json --api cst-python --visible
```

COM만 강제로 사용:

```powershell
python .\cst_vibe_runner.py .\examples\02_mesh_frame_unitcell.json --api com --visible
```

## 종료 코드

```text
0 = Python 명령 실행 정상 종료
1 = 예상 못 한 예외 또는 CST가 명령을 거부
2 = JSON/입력/계획 검증 실패 또는 CST 명령 실패를 도구가 잡아낸 상태
```

숫자만 보지 말고 출력창의 `Original error`, `[diagnostic-error]`, `[ok]` 문장을 같이 봐야 합니다.

## 문제 해결

### CST에서 New Parameter 창이 뜸

단일 실행에서는 뜨면 안 됩니다. 출력에 아래 문장이 있는지 봅니다.

```text
no New Parameter dialog is needed
```

스윕 실행은 예외입니다. 스윕은 CST Parameter List를 사용하므로 파라미터가 만들어질 수 있습니다.

### 그림은 그려지는데 solver가 안 돎

먼저 로그에서 이 둘 중 하나가 있는지 확인합니다.

```text
[cst-python] modeler.run_solver completed
[cst] Solver.Start completed
```

둘 다 없으면 solver start 호출이 실패한 것입니다. 이 경우 출력창의 `CST solver start failed` 아래 원문 에러를 봐야 합니다.

### 공식 CST Python API를 못 찾음

아래처럼 환경변수를 지정한 뒤 다시 실행합니다.

```powershell
$env:CST_PYTHON_LIB="C:\Program Files\CST Studio Suite 2025\AMD64\python_cst_libraries"
python .\cst_vibe_gui.py
```

### pywin32 오류

```powershell
python -m pip install pywin32
```

### openai 패키지 오류

LLM 연결 버튼을 쓰려면 필요합니다.

```powershell
python -m pip install openai
```

LLM을 안 쓰고 숫자 직접 입력만 할 때는 CST 실행 자체와 별개입니다.

## 파일 구성

```text
cst_vibe_gui.py          GUI
cst_vibe_runner.py       CST 실행기
cst_plan_defaults.py     RF 기본 설정/검증
collect_sparams.py       S11/S21 결과 정리
prompt_for_local_llm.md  로컬 LLM용 JSON 변환 프롬프트
examples/                예제 JSON
runs/                    실행 결과 폴더
```

## 현재 한계

- CST 2025 CT 실기 테스트 로그가 없으면 100% 검증은 어렵습니다.
- 공개 문서와 일반 CST 자동화 패턴을 바탕으로 만들었지만, 회사 PC의 CST 설정/라이선스/템플릿 차이에 따라 macro 명령이 거부될 수 있습니다.
- 지금은 `모기장 유닛셀 단일 실행`을 최우선으로 안정화하는 단계입니다.
