# CST 3x3 Shield Mesh Sweep

이 저장소는 CST Studio Suite에서 만든 **3x3 차폐 메쉬망(shielding mesh)** 모델을 Python GUI로 반복 실행하기 위한 도구입니다.

현재 기본 목적은 간단합니다.

- 이미 만들어서 한 번 검증한 `.cst` 프로젝트를 템플릿으로 사용
- CST 안에 등록된 영어 파라미터 이름을 GUI에 그대로 입력
- `mesh_width`, `mesh_thickness` 같은 폭/두께 값을 바꿔가며 반복 실행
- 각 run의 파라미터와 결과를 폴더별로 저장
- export된 S-parameter 결과를 CSV로 분석

## 주요 파일

```text
gui_sweep.py                              # GUI 실행 파일
run_sweep.py                              # 명령줄 스윕 실행
analyze_results.py                        # 명령줄 결과 분석
configs/sweep.shield_mesh_3x3.example.json # 3x3 차폐 메쉬망 기본 설정
configs/sweep.patch_antenna.example.json  # 이전 패치 안테나 예시
src/sweep.py                              # 스윕 조합과 실행 로직
src/cst_adapter.py                        # CST Python API 연결부
src/results.py                            # S-parameter 결과 분석
```

## 실행

PowerShell에서 저장소 폴더로 이동한 뒤:

```powershell
python .\gui_sweep.py
```

일반 `python`이 안 되면:

```powershell
py .\gui_sweep.py
```

CST API 연결에서 `cst.interface` import 에러가 나면 CST에 포함된 Python으로 실행해야 합니다.

```powershell
"C:\Program Files\CST Studio Suite 2024\AMD64\python\python.exe" .\gui_sweep.py
```

## GUI 사용 순서

1. `Template .cst`에서 이미 한 번 정상 실행된 3x3 메쉬망 CST 파일 선택
2. `Runs dir`은 처음에는 기본값 `runs_shield_mesh_3x3` 유지
3. CST에 등록된 파라미터 이름을 그대로 입력
4. 폭과 두께 범위를 입력
5. 처음에는 `Dry run` 체크 ON 상태로 `Run Sweep`
6. run 폴더와 파라미터 조합이 맞는지 확인
7. `Dry run` 체크 OFF 후 실제 CST 실행

## 기본 파라미터 예시

기본 config는 다음 두 파라미터를 예시로 사용합니다.

```text
mesh_width
mesh_thickness
```

중요: 이 이름은 예시입니다. 실제 CST 프로젝트에 등록된 파라미터 이름이 다르면 GUI에서도 그 이름을 그대로 써야 합니다.

예를 들어 CST에서 폭 파라미터 이름을 `wire_w`, 두께 파라미터 이름을 `metal_t`로 만들었다면 GUI에도 이렇게 입력해야 합니다.

```text
Name: wire_w
Name: metal_t
```

## 값 입력 방식

직접 값 목록을 넣을 수 있습니다.

```text
Values: 0.2, 0.4, 0.6, 0.8, 1.0
```

또는 시작/끝/간격으로 넣을 수 있습니다.

```text
Start: 0.2
Stop: 1.0
Step: 0.2
```

처음 연결 테스트는 반드시 한 점만 돌리는 것을 추천합니다.

```text
Start: 현재값
Stop: 현재값
Step: 1
```

## 결과 폴더

`Runs dir`이 `runs_shield_mesh_3x3`이면 실행 결과는 이렇게 저장됩니다.

```text
runs_shield_mesh_3x3/
  run_0001/
    params.json
    run_info.json
    model.cst
  run_0002/
    params.json
    run_info.json
    model.cst
```

`params.json`에는 해당 run에서 사용한 폭/두께 값이 저장됩니다.

## 결과 분석

차폐 메쉬망에서는 보통 투과 특성인 `S21`이 중요합니다. `s21.csv`가 있으면 목표 주파수의 `S21`과 shielding effectiveness를 계산합니다.

```text
shielding_effectiveness_at_target_db = -S21_at_target_db
```

자동으로 찾는 S21 파일 이름:

```text
s21.csv
result_s21.csv
s21.txt
result_s21.txt
*s21*.csv
*S21*.csv
*s21*.txt
*S21*.txt
```

S11도 같이 export하면 참고용으로 분석합니다. 자동으로 찾는 S11 파일 이름:

```text
s11.csv
result_s11.csv
s11.txt
result_s11.txt
*s11*.csv
*S11*.csv
*s11*.txt
*S11*.txt
```

파일은 2열이면 됩니다. S21 파일도 같은 형식입니다.

```csv
frequency_ghz,s11_db
2.30,-4
2.40,-12
2.45,-18
2.50,-11
2.60,-5
```

GUI에서 `Analyze Results`를 누르면:

```text
runs_shield_mesh_3x3/analysis_results.csv
```

가 생성됩니다.

## Git 주의사항

`.cst` 파일과 run 결과는 용량이 커질 수 있어서 Git에 올리지 않습니다.

`.gitignore`에 다음이 제외되어 있습니다.

```text
*.cst
runs/
runs_shield_mesh_3x3/
```

실제 CST 모델은 회사 공유 폴더나 로컬 디스크에서 관리하고, Git에는 자동화 코드와 config 예시만 올리는 방식이 안전합니다.
