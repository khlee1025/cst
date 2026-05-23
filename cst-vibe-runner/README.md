# CST Vibe Runner

로컬 LLM이 만든 JSON/YAML 명령서를 CST Studio Suite에 실행시키는 작은 파이썬 런너입니다.

구조는 단순합니다.

1. 사람이 한국어로 원하는 CST 작업을 씁니다.
2. 로컬 LLM이 그 문장을 `CST Vibe Runner` JSON 명령서로 번역합니다.
3. 이 파이썬 프로그램이 명령서를 읽고 CST COM 자동화로 실행합니다.

LLM API는 이 프로그램 안에 붙이지 않았습니다. 그래서 인터넷 연결 없이도, 로컬 LLM이 만든 결과물만 넣어서 CST를 제어하는 흐름으로 쓸 수 있습니다.

## 설치

Windows에서 CST가 설치되어 있고 COM 자동화가 가능한 상태여야 합니다.

```powershell
python -m pip install pywin32
```

YAML 파일을 쓰고 싶다면 추가로 설치합니다.

```powershell
python -m pip install pyyaml
```

JSON만 쓰면 `pyyaml`은 필요 없습니다.

## GUI 실행

터미널보다 GUI가 편하면 아래처럼 실행합니다.

```powershell
python .\cst_vibe_gui.py
```

GUI에서는 왼쪽에 한국어 요청을 메모하고, 로컬 LLM에서 받은 JSON을 오른쪽 편집기에 붙여넣은 뒤 `드라이런` 또는 `CST 실행`을 누르면 됩니다.

## 먼저 드라이런

CST를 열기 전에 생성될 COM 호출과 CST 매크로를 확인합니다.

```powershell
python .\cst_vibe_runner.py .\examples\shielding_unitcell_plan.json --dry-run
```

## 실제 실행

```powershell
python .\cst_vibe_runner.py .\examples\shielding_unitcell_plan.json --visible
```

`--visible`은 CST UI를 보여 달라는 요청입니다. CST 버전이나 COM 설정에 따라 무시될 수 있습니다.

## 명령서 포맷

최상위 구조는 다음과 같습니다.

```json
{
  "project": {
    "mode": "new",
    "save_as": "output/result.cst"
  },
  "parameters": {
    "p": "10",
    "gap": "0.4"
  },
  "commands": [
    {
      "op": "units",
      "geometry": "mm",
      "frequency": "GHz"
    }
  ]
}
```

지원하는 주요 `op`는 다음과 같습니다.

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

CST에서 특수한 기능이 필요하면 `vba_history`로 CST 매크로를 그대로 넣으면 됩니다. 이게 첫 버전의 탈출구입니다.

## 로컬 LLM 사용법

`prompt_for_local_llm.md` 내용을 로컬 LLM의 시스템 프롬프트 또는 작업 지시문으로 넣고, 네가 원하는 CST 작업을 말하면 됩니다.

예:

```text
주기 10 mm, FR4 두께 0.8 mm, 구리 패치 폭 7.2 mm인 차폐 유닛셀을 만들고 1-18 GHz로 설정해줘.
```

로컬 LLM 출력이 JSON이면 파일로 저장한 뒤 `cst_vibe_runner.py`에 넣습니다.

## 현실적인 주의점

CST COM 매크로 이름은 CST 버전과 템플릿에 따라 조금씩 다를 수 있습니다. 그래서 처음에는 반드시 `--dry-run`으로 매크로를 보고, CST에서 안 먹는 명령은 `vba_history`로 직접 검증된 매크로를 넣는 방식이 가장 빠릅니다.

이 런너는 첫 단계 자동화용입니다. 성능 예측 모델, 데이터셋 구축, 결과 후처리는 나중에 별도 모듈로 붙이면 됩니다.
