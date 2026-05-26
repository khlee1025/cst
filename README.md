# CST Vibe Runner

CST Vibe Runner는 **CST Studio Suite 2025 CT에서 차폐/유닛셀 설계를 쉽게 만들고, 실행 결과를 나중에 Python 모듈 결과와 비교할 수 있도록 정리하는 도구**입니다.

처음 목표는 단순합니다.

```text
설계 파라미터 입력
-> CST 형상 생성
-> CST 실행 또는 드라이런
-> 결과 폴더 자동 정리
-> 나중에 Python 모듈 결과와 비교
```

이 프로그램은 회사 LLM이나 외부 LLM API를 필수로 쓰지 않습니다. 기본 유닛셀은 GUI 안의 **설계 마법사**에서 숫자만 넣어도 JSON이 만들어집니다. 복잡한 구조가 필요할 때만 회사 LLM을 보조로 쓰면 됩니다.

## 가장 먼저 할 일

처음에는 이 순서대로만 하면 됩니다.

```text
1. python .\cst_vibe_gui.py
2. CST 연동 테스트
3. 설계 마법사에 숫자 입력
4. 형상 JSON 만들기
5. RF Check
6. 드라이런
7. RF Package
8. RF Run 또는 CST 실행
```

처음부터 포트, solver, 복잡한 boundary를 넣지 마세요. 먼저 기판과 패치 형상이 정확히 만들어지는지 확인하는 것이 안전합니다.

## 다운로드

GitHub에서 받기:

1. 저장소 화면으로 이동합니다.
2. 브랜치가 `master`인지 확인합니다.
3. 오른쪽 위 `Code` 버튼을 누릅니다.
4. `Download ZIP`을 누릅니다.
5. ZIP 압축을 풉니다.

바로 다운로드:

[Download ZIP](https://github.com/khlee1025/cst/archive/refs/heads/master.zip)

Git으로 받기:

```powershell
git clone https://github.com/khlee1025/cst.git
cd cst
```

Git으로 받으면 업데이트가 편합니다.

```powershell
git pull
```

## 실행 준비

Python이 필요합니다.

```powershell
python --version
```

CST 없이 드라이런만 할 때는 추가 패키지가 거의 필요 없습니다.

CST와 실제 연동하려면 `pywin32`가 필요합니다.

```powershell
python -m pip install pywin32
```

YAML 명령서를 쓰고 싶으면 추가로 설치합니다.

```powershell
python -m pip install pyyaml
```

JSON만 쓸 거면 `pyyaml`은 없어도 됩니다.

## GUI 실행

```powershell
python .\cst_vibe_gui.py
```

GUI는 크게 세 부분입니다.

```text
왼쪽: 요청 메모, 설계 마법사, 빠른 작업
오른쪽 위: 실행 버튼들
오른쪽 아래: JSON 명령서 / 실행 출력 탭
```

## GUI 버튼 설명

### 설계 마법사

왼쪽에 있는 숫자 입력 영역입니다. 회사 LLM 없이 기본 패치 유닛셀 JSON을 만듭니다.

입력값:

| 항목 | 의미 | 기본값 |
| --- | --- | --- |
| `p` | 유닛셀 주기, mm | `10` |
| `sub_t` | 기판 두께, mm | `0.8` |
| `copper_t` | 구리 두께, mm | `0.035` |
| `patch_w` | 패치 폭, mm | `7.2` |
| `fmin` | 시작 주파수, GHz | `1` |
| `fmax` | 끝 주파수, GHz | `18` |
| `epsilon` | 기판 유전율 | `4.3` |
| `tand` | 손실탄젠트 | `0.02` |

기본 규칙:

```text
patch_w < p
sub_t > 0
copper_t > 0
fmax > fmin
```

### 형상 JSON 만들기

설계 마법사 숫자로 오른쪽 JSON 명령서를 자동 생성합니다.

기본 생성 내용:

```text
units
frequency_range
FR4 material
substrate brick
top_patch brick
rebuild
save
```

기본적으로 포트와 solver는 넣지 않습니다.

### JSON 만들고 드라이런

설계 마법사 JSON을 만든 뒤 바로 드라이런합니다.

### RF Check

현재 오른쪽 JSON을 RF 관점에서 간단히 검사합니다.

확인하는 것:

```text
patch_w가 p보다 작은지
sub_t/copper_t가 양수인지
fmax가 fmin보다 큰지
포트가 들어가 있는지
solver_start가 들어가 있는지
boundary가 들어가 있는지
brick 개수가 몇 개인지
```

초심자는 `RF Check`에서 경고가 없는 상태로 시작하는 것이 좋습니다.

### 드라이런

CST를 열지 않고, CST에 보낼 매크로만 출력합니다.

정상 출력 예:

```text
With Units
    .Geometry "mm"
    .Frequency "GHz"
    .Time "ns"
End With

With Brick
...
End With
```

드라이런이 성공하면 JSON 해석과 매크로 생성은 성공한 것입니다.

### CST 연동 테스트

CST가 COM으로 열리는지만 확인합니다. 매크로는 넣지 않습니다.

이 버튼이 성공하면:

```text
Python -> pywin32 -> CST COM
```

연결은 된 것입니다.

### CST 실행

현재 JSON 명령서를 CST에 실제로 넣습니다.

주의:

```text
CST 실행은 CST 2025 CT가 설치된 PC에서만 사용하세요.
처음에는 포트 없는 예제로만 실행하세요.
```

### Step Diagnose

한 명령이 실패해도 멈추지 않고 다음 명령을 계속 시도합니다.

출력 예:

```text
[ok] commands[1] op=units
[diagnostic-error] commands[2] op=frequency_range failed: ...
[ok] commands[3] op=material
```

어떤 명령이 통과했고 어떤 명령이 실패했는지 한 번에 모을 때 씁니다.

### Save Report

실행 출력 전체를 텍스트 파일로 저장합니다.

추천 파일명:

```text
cst_vibe_diagnostic_report.txt
```

오류가 반복되면 이 파일을 회사 LLM에 그대로 넣고 물어보면 됩니다.

### RF Package

CST 없이 표준 결과 폴더를 만들고 드라이런합니다.

생성되는 구조:

```text
runs/
  20260526_162507_patch_unitcell_p10_sub_t0.8_patch_w7.2/
    input_plan.json
    design_params.json
    summary.json
    exports/
      README.txt
    logs/
```

이 기능은 나중에 Python 모듈 결과와 비교하기 위한 준비 단계입니다.

### RF Run

표준 결과 폴더를 만들고 CST 실행까지 시도합니다.

실패해도 진단 정보가 남도록 `continue-on-error` 모드로 실행합니다.

### 열기 / 저장 / 다른 이름 저장

JSON 명령서를 파일로 열거나 저장합니다.

### 예제 불러오기

기본 예제 `examples/02_patch_unitcell_no_ports.json`을 불러옵니다.

### JSON 정렬

오른쪽 JSON 문법을 확인하고 보기 좋게 정렬합니다.

### 출력 복사

실행 출력 탭의 내용을 클립보드에 복사합니다.

### 출력 지우기

실행 출력 탭을 비웁니다.

## 추천 사용 순서

### CST 없이 확인

```text
1. GUI 실행
2. 형상 JSON 만들기
3. RF Check
4. 드라이런
5. RF Package
```

### CST 2025 CT에서 처음 확인

```text
1. GUI 실행
2. CST 연동 테스트
3. 형상 JSON 만들기
4. RF Check
5. 드라이런
6. CST 실행
7. CST에서 형상 확인
```

### 결과 비교 준비

```text
1. 형상 JSON 만들기
2. RF Check
3. RF Package
4. RF Run
5. runs/.../exports/에 CST 결과 export 파일 저장
6. 나중에 Python 모듈 결과를 같은 run 폴더에 저장
```

## 파일 설명

```text
README.md                         # 전체 기능 설명
MANUAL.md                         # 자세한 사용 설명서
DESIGN_GUIDE.md                   # 초심자용 설계 가이드
DEBUG_WORKFLOW.md                 # 오류 진단/리포트 저장 흐름
RF_RUN_PACKAGE.md                 # CST/Python 비교를 위한 run 폴더 규격
cst_vibe_gui.py                    # GUI 실행 파일
cst_vibe_runner.py                 # JSON/YAML 명령서 실행기
prompt_for_local_llm.md            # 회사/로컬 LLM에 넣을 프롬프트
requirements.txt                   # 필요한 패키지 목록
examples/
  00_connection_test.json
  01_units_only.json
  02_patch_unitcell_no_ports.json
  03_patch_unitcell_with_ports_experimental.json
  shielding_unitcell_plan.json
```

## 예제 파일 설명

### examples/00_connection_test.json

CST 연결만 확인합니다. commands가 비어 있습니다.

### examples/01_units_only.json

단위 설정만 확인합니다.

### examples/02_patch_unitcell_no_ports.json

초심자 기본 예제입니다.

포함:

```text
FR4 기판
구리 패치
단위
주파수 범위
저장
```

포함하지 않음:

```text
포트
solver_start
복잡한 boundary
결과 export
```

### examples/03_patch_unitcell_with_ports_experimental.json

포트 실험용 예제입니다. 초심자 기본 예제가 아닙니다.

### examples/shielding_unitcell_plan.json

이전 호환용 예제입니다. 새로 시작할 때는 `02_patch_unitcell_no_ports.json`를 쓰세요.

## CLI 사용

GUI 없이 명령어로도 실행할 수 있습니다.

드라이런:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --dry-run
```

CST 실행:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --visible
```

단계별 진단:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --visible --continue-on-error
```

RF Package:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --dry-run --package-run
```

RF Run:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --visible --package-run --continue-on-error
```

## JSON 명령서 구조

기본 구조:

```json
{
  "project": {
    "mode": "new",
    "save_as": "output/patch_unitcell_no_ports.cst"
  },
  "parameters": {
    "p": "10",
    "sub_t": "0.8",
    "copper_t": "0.035",
    "patch_w": "7.2",
    "fmin": "1",
    "fmax": "18"
  },
  "commands": [
    {
      "op": "units",
      "geometry": "mm",
      "frequency": "GHz",
      "time": "ns"
    },
    {
      "op": "brick",
      "name": "substrate",
      "component": "unitcell",
      "material": "FR4_local",
      "xrange": ["-p/2", "p/2"],
      "yrange": ["-p/2", "p/2"],
      "zrange": ["0", "sub_t"]
    }
  ]
}
```

## 지원 명령

```text
units
frequency_range
boundary
background
material
brick
cylinder
boolean
discrete_port
solver_start
export_touchstone
parameter
rebuild
save
sweep
vba_history
```

처음에는 아래 명령만 쓰는 것을 추천합니다.

```text
units
frequency_range
material
brick
rebuild
save
```

## 종료코드

```text
0: 성공
1: 예상하지 못한 Python/CST 오류
2: JSON, PlanError, CST 매크로 오류
```

`Step Diagnose`에서는 종료코드 2가 떠도 출력 안의 `[ok]`, `[diagnostic-error]`가 더 중요합니다.

## CST 2025 CT 권장 시작 설정

```text
COM ProgID: CSTStudio.Application
CST UI 보이기: 켬
유닛셀 경계조건 포함: 끔
포트: 만들지 않음
solver_start: 넣지 않음
```

형상이 맞게 생기는 것을 확인한 뒤에만 포트와 solver를 추가하세요.

## 문제 해결

### python 명령이 안 될 때

Python이 설치되어 있지 않거나 PATH에 없습니다.

```powershell
python --version
```

### pywin32 오류

CST 실제 연동에는 `pywin32`가 필요합니다.

```powershell
python -m pip install pywin32
```

### CST가 열리지 않을 때

GUI의 `COM ProgID`를 확인하세요.

기본값:

```text
CSTStudio.Application
```

후보:

```text
CSTStudio.Application.2025
CSTStudio.Application.2024
CSTStudio.Application.2023
```

### AddToHistory 오류

`Step Diagnose`를 누른 뒤 `Save Report`로 리포트를 저장하세요.

리포트에서 확인할 것:

```text
History name
Macro code
Original error
normal call failed
raw COM Invoke failed
```

### 이상한 도형이 생길 때

먼저 `RF Check`를 누르세요.

확인할 것:

```text
patch_w < p
sub_t > 0
copper_t > 0
fmax > fmin
commands에 discrete_port가 들어갔는지
commands에 solver_start가 들어갔는지
```

## 회사 LLM을 쓸 때

복잡한 구조가 필요하면 `prompt_for_local_llm.md` 내용을 회사 LLM에 넣고 요청하세요.

추천 요청:

```text
CST Vibe Runner JSON을 만들어줘.
포트는 만들지 마.
solver_start도 넣지 마.
기판과 금속 패치 형상만 만들어줘.
단위는 mm, GHz, ns.
p=10, sub_t=0.8, copper_t=0.035, patch_w=7.2, fmin=1, fmax=18.
```

나쁜 요청:

```text
알아서 차폐 유닛셀 만들어줘.
```

이렇게 말하면 LLM이 포트, solver, boundary를 마음대로 넣을 수 있습니다.

## 현재 한계

아직 완성형 CST 자동 설계 툴은 아닙니다.

현재 잘하는 것:

```text
초심자용 패치 유닛셀 JSON 생성
CST COM 연결 확인
CST 매크로 드라이런
단계별 진단
RF run folder 생성
Python 비교용 design_params/summary 생성
```

아직 조심해야 하는 것:

```text
CST 버전별 매크로 차이
포트 자동 설정
solver setup 자동화
S-parameter export 자동화
복잡한 주기구조/Floquet 포트 설정
```

그래서 현재 추천은:

```text
형상 생성 툴로 먼저 안정화
-> CST 결과 export 규칙 고정
-> Python 모듈 결과와 비교 툴 연결
```
