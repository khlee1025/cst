# RF Run Package Format

`CST 실행 + 결과폴더`를 누르면 실행별 결과 폴더가 만들어집니다. 이 폴더는 나중에 CST 결과와 Python 예측 모듈 결과를 비교하기 위한 공통 포맷입니다.

## 폴더 구조

```text
runs/
  20260526_181500_patch_unitcell_p10_sub_t0.8_patch_w7.2/
    input_plan.json
    design_params.json
    summary.json
    cst_project.cst
    exports/
      README.txt
    logs/
```

## 파일 설명

| 파일 | 설명 |
| --- | --- |
| `input_plan.json` | CST에 실제로 보낸 전체 JSON 명령서 |
| `design_params.json` | 주기, 두께, 패치 폭 같은 핵심 설계 파라미터 |
| `summary.json` | 실행 상태와 결과 위치 요약 |
| `cst_project.cst` | 저장될 CST 프로젝트 파일 |
| `exports/` | S-parameter, CSV, Touchstone 파일을 넣을 위치 |
| `logs/` | 실행 로그를 넣을 위치 |

## CLI로 같은 폴더 만들기

CST 없이 패키지만 확인:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --dry-run --package-run
```

CST까지 실행:

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --visible --package-run
```

## Python 비교 모듈에서 쓰면 좋은 입력

비교 도구는 보통 아래 두 파일을 먼저 읽으면 됩니다.

```text
input_plan.json
design_params.json
```

CST가 export한 S-parameter는 `exports/`에 넣고, Python 모듈 결과도 같은 실행 폴더 아래에 정리하면 비교가 쉬워집니다.
