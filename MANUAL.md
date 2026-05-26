# CST Vibe Runner 사용 설명서

이 설명서는 CST가 없어도 먼저 프로그램을 확인하고, 나중에 CST가 있는 PC에서 실제로 실행하는 흐름까지 안내합니다.

## 1. 이 프로그램이 하는 일

CST Vibe Runner는 자연어를 직접 이해하는 프로그램이 아닙니다.

대신 흐름을 이렇게 나눕니다.

```text
내가 한국어로 원하는 작업을 씀
-> 로컬 LLM이 JSON 명령서로 번역
-> CST Vibe Runner가 JSON을 읽음
-> CST에 실행할 매크로/COM 명령 생성
-> CST가 있는 PC에서는 실제 실행
```

즉, LLM은 "번역기" 역할이고, 이 프로그램은 "CST 실행기" 역할입니다.

## 2. 다운로드 방법

GitHub 화면에서 받는 방법:

1. 저장소로 들어갑니다.
2. 브랜치가 `master`인지 확인합니다.
3. 오른쪽 위 `Code` 버튼을 누릅니다.
4. `Download ZIP`을 누릅니다.
5. 받은 ZIP 파일의 압축을 풉니다.

바로 다운로드:

[Download ZIP](https://github.com/khlee1025/cst/archive/refs/heads/master.zip)

Git으로 받는 방법:

```powershell
git clone https://github.com/khlee1025/cst.git
cd cst
```

## 3. 폴더 안에 있어야 하는 파일

압축을 풀거나 Git으로 받으면 아래 파일들이 있어야 합니다.

```text
README.md
MANUAL.md
DESIGN_GUIDE.md
cst_vibe_gui.py
cst_vibe_runner.py
prompt_for_local_llm.md
requirements.txt
examples/
  00_connection_test.json
  01_units_only.json
  02_patch_unitcell_no_ports.json
  03_patch_unitcell_with_ports_experimental.json
```

가장 중요한 파일은 두 개입니다.

- `cst_vibe_gui.py`: 화면으로 쓰는 GUI 프로그램
- `cst_vibe_runner.py`: JSON 명령서를 실행하는 핵심 프로그램

초심자는 [DESIGN_GUIDE.md](./DESIGN_GUIDE.md)를 먼저 보고, `examples/02_patch_unitcell_no_ports.json`부터 실행하는 것을 추천합니다.

## 4. CST 없이 먼저 테스트하기

CST가 없어도 드라이런으로 확인할 수 있습니다.

PowerShell에서 프로젝트 폴더로 이동한 뒤 실행합니다.

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --dry-run
```

정상이라면 이런 문구들이 출력됩니다.

```text
[dry-run] COM Dispatch: CSTStudio.Application
--- AddToHistory: set units ---
With Units
...
--- AddToHistory: create brick substrate ---
With Brick
...
```

이 출력이 보이면 다음 단계까지 성공한 것입니다.

```text
JSON 파일 읽기
-> 명령서 해석
-> CST에 보낼 매크로 생성
```

아직 CST가 없기 때문에 실제 시뮬레이션 실행만 확인하지 못한 상태입니다.

## 5. GUI 실행하기

GUI는 이렇게 실행합니다.

```powershell
python .\cst_vibe_gui.py
```

GUI가 열리면 다음 순서로 쓰면 됩니다.

1. 왼쪽 `요청 메모`에 원하는 CST 작업을 적습니다.
2. CST가 있는 PC라면 먼저 `CST 연동 테스트`를 누릅니다.
3. 연동 테스트가 종료코드 0이면 CST COM 연결은 된 것입니다.
4. `LLM 프롬프트 복사` 버튼을 누릅니다.
5. 로컬 LLM에 프롬프트와 요청 문장을 넣습니다.
6. 로컬 LLM이 만든 JSON을 오른쪽 `JSON 명령서` 칸에 붙여넣습니다.
7. `JSON 정렬`을 눌러 문법 오류가 없는지 봅니다.
8. `드라이런`을 눌러 CST에 보낼 명령을 미리 확인합니다.
9. CST가 있는 PC에서는 `CST 실행`을 누릅니다.

### 버튼 차이

- `CST 연동 테스트`: CST가 COM으로 열리는지만 확인합니다. 매크로는 넣지 않습니다.
- `드라이런`: CST를 열지 않고 JSON이 어떤 CST 매크로로 바뀌는지 봅니다.
- `CST 실행`: 실제 CST에 매크로를 넣고 실행합니다.

처음 확인 순서는 `CST 연동 테스트` -> `드라이런` -> `CST 실행`이 가장 안전합니다.

## 6. 로컬 LLM에 넣는 방법

`prompt_for_local_llm.md` 파일을 열면 로컬 LLM용 지시문이 있습니다.

로컬 LLM에는 보통 이렇게 넣으면 됩니다.

```text
아래 지시문을 따라 CST Vibe Runner용 JSON만 출력해줘.

[prompt_for_local_llm.md 내용 붙여넣기]

요청:
주기 10 mm, FR4 두께 0.8 mm, 구리 패치 폭 7.2 mm인 차폐 유닛셀을 만들고 1-18 GHz로 설정해줘.
```

중요한 점:

- 로컬 LLM 출력은 JSON만 나오게 하는 것이 좋습니다.
- 설명 문장이나 markdown 코드블록이 섞이면 GUI에서 JSON 오류가 날 수 있습니다.
- 오류가 나면 JSON 부분만 복사해서 다시 붙여넣으면 됩니다.

## 7. CST가 있는 PC에서 실제 실행하기

CST 실제 연동에는 Windows COM 자동화가 필요합니다.

먼저 패키지를 설치합니다.

```powershell
python -m pip install pywin32
```

YAML 명령서도 쓰고 싶으면 추가 설치합니다.

```powershell
python -m pip install pyyaml
```

실제 실행은 이렇게 합니다.

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --visible
```

GUI로 실행하려면:

```powershell
python .\cst_vibe_gui.py
```

그 다음 `CST 실행` 버튼을 누릅니다.

## 8. 자주 생기는 문제

### `python` 명령을 찾을 수 없다고 나올 때

Windows에서 Python이 설치되어 있지 않거나 PATH에 등록되지 않은 상태입니다.

해결 방법:

1. Python을 설치합니다.
2. 설치할 때 `Add python.exe to PATH`를 체크합니다.
3. PowerShell을 새로 열고 다시 실행합니다.

확인 명령:

```powershell
python --version
```

### GUI가 안 열릴 때

먼저 Python 기본 GUI 모듈인 `tkinter`가 있는지 확인합니다.

```powershell
python -c "import tkinter; print('tkinter ok')"
```

오류가 나면 Python 설치를 다시 확인해야 합니다.

### `pywin32` 오류가 날 때

CST 실제 실행에는 `pywin32`가 필요합니다.

```powershell
python -m pip install pywin32
```

CST 없이 `--dry-run`만 할 때는 `pywin32`가 없어도 됩니다.

### JSON 오류가 날 때

대부분 로컬 LLM 출력에 설명 문장이나 ```json 같은 코드블록 문자가 섞여서 생깁니다.

해결 방법:

1. `{` 로 시작해서 `}` 로 끝나는 JSON 부분만 복사합니다.
2. GUI에 붙여넣습니다.
3. `JSON 정렬`을 누릅니다.

### CST에서 매크로가 안 먹을 때

CST 버전마다 매크로 이름이나 옵션이 조금 다를 수 있습니다.

이럴 때는:

1. 먼저 `드라이런`으로 생성된 매크로를 확인합니다.
2. CST에서 직접 기록한 매크로와 비교합니다.
3. 지원하지 않는 기능은 `vba_history` 명령으로 직접 매크로를 넣습니다.

`CST 실행`에서 종료코드 1 또는 2가 나오면 출력창의 `CST AddToHistory failed` 아래를 확인합니다.
거기에 CST가 거절한 `History name`과 `Macro code`가 표시됩니다. 그 블록이 수정해야 할 부분입니다.

### CST 2025에서 AddToHistory 인자 오류가 날 때

예를 들어 이런 오류가 나올 수 있습니다.

```text
This method call requires a different number of arguments: 2 required, 0 provided
```

이 경우는 두 가지 가능성이 있습니다.

1. CST가 매크로 코드 안의 어떤 메서드를 잘못 해석한 경우
2. CST 2025 COM이 `AddToHistory(name, code)` 인자 전달을 pywin32 기본 방식으로 받지 못한 경우

현재 버전은 기본 호출이 실패하면 raw COM `Invoke` 방식으로 한 번 더 시도합니다.
그래도 실패하면 출력창에 아래 정보가 나옵니다.

```text
normal call failed:
raw COM Invoke failed:
name='...'
code_length=...
```

이 정보가 보이면 `name`이 비어있는지, `code_length`가 0인지 먼저 확인합니다.
둘 다 정상인데도 실패하면 CST 버전의 COM 호출 방식 또는 매크로 문법 문제일 가능성이 큽니다.

## 9. 추천 사용 순서

처음에는 아래 순서로 확인하는 것을 추천합니다.

```text
1. ZIP 다운로드
2. python .\cst_vibe_gui.py 로 GUI 열기
3. 예제 JSON 그대로 드라이런
4. prompt_for_local_llm.md를 로컬 LLM에 넣기
5. 원하는 CST 작업을 JSON으로 변환
6. GUI에 붙여넣고 JSON 정렬
7. 드라이런
8. CST가 있는 PC에서 실제 실행
```

## 10. 현재 버전의 한계

이 버전은 첫 자동화용 뼈대입니다.

잘하는 것:

- JSON 명령서를 읽기
- CST 매크로 생성
- GUI에서 붙여넣고 드라이런하기
- 기본 유닛셀 형상 만들기

아직 조심해야 하는 것:

- CST 버전별 매크로 차이
- 포트/경계조건의 세부 설정
- 실제 해석 결과 추출 자동화
- 복잡한 형상의 완전 자동 생성

그래서 처음에는 간단한 유닛셀부터 시작해서, CST에서 실제로 잘 먹는 명령을 하나씩 늘려가는 방식이 좋습니다.
