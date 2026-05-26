# CST Automation Notes

이 문서는 CST Vibe Runner를 고칠 때 기준으로 삼는 자동화 규칙입니다.

## Unit Cell 기본 해석

- 모기장/차폐 유닛셀은 x/y 방향을 `unit cell`로 둡니다.
- z 방향은 `open`으로 두고, 주파수 영역 해석에서는 Floquet port를 기본으로 씁니다.
- Floquet mode number 기본값은 `2`입니다.
- 기본 포트 위치는 `Zmin`, `Zmax`입니다.

## Floquet Port VBA 패턴

기본 매크로 패턴:

```vb
With FloquetPort
    .Reset
    .SetDialogTheta "0"
    .SetDialogPhi "0"
    .SetPolarizationIndependentOfScanAnglePhi "0", "False"
    .SetSortCode "+beta/pw"
    .SetCustomizedListFlag "False"
    .Port "Zmin"
    .SetNumberOfModesConsidered "2"
    .SetDistanceToReferencePlane "0.0"
    .SetUseCircularPolarization "False"
    .Port "Zmax"
    .SetNumberOfModesConsidered "2"
    .SetDistanceToReferencePlane "0.0"
    .SetUseCircularPolarization "False"
End With
With Boundary
    .SetPeriodicBoundaryAngles "0", "0"
    .SetPeriodicBoundaryAnglesDirection "outward"
End With
```

## Solver Start

사용자가 CST에서 `Setup Solver -> Start`를 누르는 흐름은 자동화에서는 아래 명령으로 대응합니다.

```vb
FDSolver.Start
```

현재 기본 해석 버튼은 형상 생성, Floquet port 설정, rebuild 이후 `FDSolver.Start`까지 실행합니다.

## Parameter Sweep

Python이 각 케이스마다 새 CST 프로젝트를 여는 방식은 기본 흐름이 아닙니다.

기본 스윕은 같은 CST 프로젝트 안에서 아래 순서를 반복합니다.

```text
StoreParameter
Rebuild
FDSolver.Start
Touchstone export
```

이를 위해 GUI 스윕은 `case_sweep` 명령을 만들고, 러너가 같은 CST 세션 안에서 케이스를 반복합니다.

## 검증 규칙

- CST가 없는 환경에서는 `--dry-run`으로 VBA 매크로 생성만 검증합니다.
- CST 2025에서 실제로 에러가 나면 CST의 History/Macro Recorder에서 생성되는 VBA를 우선 기준으로 삼습니다.
- AddToHistory 에러는 인자 문제와 CST 객체 메서드 차이를 분리해서 봅니다.

## 참고한 자료

- Floquet VBA 패턴: https://src.koda.cnrs.fr/hermes/cst-python-api/-/issues/27
- CST boundary 설명: https://www.mweda.com/cst/cst2013/mergedprojects/cst_microwave_studio/special_solvopt/special_solvopt_boundary_conditions_boundaries.htm
- CST port mode 개념: https://www.mweda.com/cst/cst2013/mergedProjects/CST_PARTICLE_STUDIO/special_overview/special_overview_waveguideover.htm
- StoreParameter/Rebuild sweep 패턴: https://studylib.net/doc/18799477/cst-2010-webcast-draft
