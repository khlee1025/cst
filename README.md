# CST Vibe Runner

한국어로 원하는 CST 작업을 적고, 로컬 LLM이 만든 JSON 명령서를 CST Studio Suite에 실행시키는 도구입니다.

이 프로젝트는 LLM API를 직접 연결하지 않습니다. 로컬 LLM은 번역기처럼 쓰고, 이 프로그램은 번역된 JSON 명령서를 읽어서 CST 자동화 명령으로 실행합니다.

처음 쓰는 경우에는 [MANUAL.md](./MANUAL.md)를 먼저 보면 됩니다. 다운로드, GUI 실행, 로컬 LLM 사용법, CST 없이 테스트하는 방법까지 순서대로 정리해두었습니다.

초심자 설계 흐름은 [DESIGN_GUIDE.md](./DESIGN_GUIDE.md)를 보면 됩니다. 포트 없이 형상부터 만드는 안전한 순서와 파라미터 규칙을 정리했습니다.

회사 LLM과 왔다 갔다 하기 불편하면 GUI 왼쪽의 `설계 마법사`를 쓰면 됩니다. 기본 유닛셀은 숫자만 넣어도 JSON을 자동 생성합니다.

오류가 반복될 때는 [DEBUG_WORKFLOW.md](./DEBUG_WORKFLOW.md)를 보세요. `Step Diagnose`와 `Save Report`로 실패 지점을 한 번에 모으는 방법을 정리했습니다.

## 지금 들어있는 것

```text
MANUAL.md                         # 친절한 사용 설명서
DESIGN_GUIDE.md                   # 초심자용 설계 가이드
DEBUG_WORKFLOW.md                 # 오류 진단/리포트 저장 흐름
cst_vibe_gui.py                    # GUI 실행 파일
cst_vibe_runner.py                 # JSON/YAML 명령서 실행기
prompt_for_local_llm.md            # 로컬 LLM에 넣을 프롬프트
requirements.txt                   # CST 실연동에 필요한 패키지
examples/
  00_connection_test.json          # CST 연결 확인
  01_units_only.json               # 단위 설정 확인
  02_patch_unitcell_no_ports.json  # 초심자 기본 형상 예제
  03_patch_unitcell_with_ports_experimental.json # 포트 실험 예제
```

예전에 있던 sweep/분석용 파일들은 정리했습니다. 지금은 CST Vibe Runner만 남겨서 바로 테스트하기 쉽게 만들었습니다.

## 다운로드

GitHub 화면에서 받는 방법:

1. 브랜치가 `master`인지 확인합니다.
2. 저장소 루트 화면으로 이동합니다.
3. 오른쪽 위 `Code` 버튼을 누릅니다.
4. `Download ZIP`을 누릅니다.
5. ZIP 압축을 풉니다.

바로 받기:

[Download ZIP](https://github.com/khlee1025/cst/archive/refs/heads/master.zip)

Git으로 받기:

```powershell
git clone https://github.com/khlee1025/cst.git
cd cst
```

## CST 없이 먼저 확인

CST가 없어도 프로그램 구조와 JSON 변환 결과는 확인할 수 있습니다.

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --dry-run
```

정상이라면 `With Material`, `With Brick`, `Solver.FrequencyRange` 같은 CST 매크로가 출력됩니다.

GUI도 CST 없이 열 수 있습니다.

```powershell
python .\cst_vibe_gui.py
```

GUI에서 `드라이런` 버튼을 누르면 CST를 열지 않고 실행될 명령을 확인합니다.

## CST와 실제 연동

CST가 설치된 Windows PC에서 아래 패키지가 필요합니다.

```powershell
python -m pip install pywin32
```

YAML 명령서도 쓰고 싶으면 추가로 설치합니다.

```powershell
python -m pip install pyyaml
```

JSON만 쓸 거면 `pyyaml`은 없어도 됩니다.

실제 실행:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --visible
```

GUI 실행:

```powershell
python .\cst_vibe_gui.py
```

## 사용 흐름

1. `prompt_for_local_llm.md` 내용을 로컬 LLM에 넣습니다.
2. 한국어로 원하는 CST 작업을 말합니다.
3. 로컬 LLM이 출력한 JSON을 GUI 오른쪽 편집기에 붙여넣습니다.
4. `JSON 정렬`로 문법을 확인합니다.
5. `드라이런`으로 CST 매크로를 미리 봅니다.
6. CST가 있는 PC에서 `CST 실행`을 누릅니다.

## 예시 요청

```text
주기 10 mm, FR4 두께 0.8 mm, 구리 패치 폭 7.2 mm인 차폐 유닛셀을 만들고 1-18 GHz로 설정해줘.
```

로컬 LLM은 이런 구조의 JSON을 만들어야 합니다.

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
      "op": "frequency_range",
      "fmin": "fmin",
      "fmax": "fmax"
    },
    {
      "op": "rebuild"
    },
    {
      "op": "save"
    }
  ]
}
```

더 완성된 초심자 예제는 `examples/02_patch_unitcell_no_ports.json`에 있습니다.

## 지원하는 명령

- `units`
- `frequency_range`
- `boundary`
- `background`
- `material`
- `brick`
- `cylinder`
- `boolean`
- `discrete_port`
- `solver_start`
- `export_touchstone`
- `parameter`
- `rebuild`
- `save`
- `sweep`
- `vba_history`

지원되지 않는 CST 기능은 `vba_history`에 CST 매크로를 직접 넣어서 실행할 수 있습니다.

## 주의

CST COM 매크로 이름은 CST 버전과 템플릿에 따라 조금씩 다를 수 있습니다. 처음에는 반드시 `--dry-run`으로 생성된 매크로를 확인하고, CST에서 실제로 동작하는 매크로를 조금씩 늘려가는 방식이 가장 안전합니다.
