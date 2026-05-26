# RF Run Package Format

이 프로젝트의 다음 목표는 CST 결과와 Python 모듈 결과를 비교하는 것입니다.
그 전에 CST 결과를 항상 같은 구조로 남겨야 합니다.

## GUI 버튼

- `RF Check`: 현재 JSON의 기본 RF 설계값을 검사합니다.
- `RF Package`: CST 없이 표준 run 폴더를 만들고 드라이런을 실행합니다.
- `RF Run`: 표준 run 폴더를 만들고 CST 실행까지 시도합니다.

처음에는 `RF Check` -> `RF Package` -> `RF Run` 순서로 쓰는 것을 추천합니다.

## 생성되는 폴더

`RF Package` 또는 `RF Run`을 누르면 아래 구조가 생깁니다.

```text
runs/
  20260526_153000_patch_unitcell_p10_sub_t0.8_patch_w7.2/
    input_plan.json
    design_params.json
    summary.json
    cst_project.cst
    exports/
      README.txt
    logs/
```

## 파일 의미

### input_plan.json

CST에 넣은 원본 JSON 명령서입니다.

### design_params.json

비교 툴이 읽기 쉬운 설계 파라미터 파일입니다.

예:

```json
{
  "p": "10",
  "sub_t": "0.8",
  "copper_t": "0.035",
  "patch_w": "7.2",
  "fmin": "1",
  "fmax": "18"
}
```

### summary.json

실행 상태와 결과 파일 위치를 적는 표준 요약 파일입니다.

예:

```json
{
  "status": "completed",
  "source": "cst",
  "tool": "CST Vibe Runner",
  "cst_project": "cst_project.cst",
  "parameters_file": "design_params.json",
  "input_plan_file": "input_plan.json",
  "exports_dir": "exports",
  "result_files": {}
}
```

### exports/

CST에서 export한 결과를 넣는 폴더입니다.

나중에 들어갈 수 있는 파일:

```text
sparameters.s2p
s11.csv
s21.csv
shielding_effectiveness.csv
```

## Python 비교 모듈과 맞출 규칙

나중에 Python 모듈도 같은 run 폴더 안에 결과를 남기면 됩니다.

추천 구조:

```text
runs/.../
  cst_project.cst
  design_params.json
  exports/
    sparameters.s2p
  python_prediction/
    summary.json
    predicted_sparams.csv
```

비교 툴은 `design_params.json`, `exports/`, `python_prediction/`만 보면 됩니다.

## CLI 사용

GUI 없이도 사용할 수 있습니다.

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --dry-run --package-run
```

CST 실행까지 포함:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --visible --package-run
```

정확한 run 폴더를 지정하고 싶으면:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --dry-run --run-dir .\runs\manual_test_001
```
