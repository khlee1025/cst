# 차폐 유닛셀 설계 가이드

이 가이드는 RF 엔지니어가 CST Vibe Runner로 기본 차폐 유닛셀을 만들 때 보는 설계 기준입니다.

## 기본 구조

현재 기본 마법사는 가장 단순한 패치 유닛셀을 만듭니다.

```text
공기
구리 패치
유전체 기판
```

기본 목적은 “복잡한 포트/솔버까지 한 번에 자동화”가 아니라, 먼저 CST에 안정적으로 형상과 파라미터를 넘기는 것입니다.

## 핵심 파라미터

| 파라미터 | 의미 | 시작 추천 |
| --- | --- | --- |
| `p` | 유닛셀 주기 | 10 mm |
| `sub_t` | 기판 두께 | 0.8 mm |
| `copper_t` | 구리 두께 | 0.035 mm |
| `patch_w` | 패치 폭 | 7.2 mm |
| `fmin` | 시작 주파수 | 1 GHz |
| `fmax` | 끝 주파수 | 18 GHz |
| `epsilon` | 기판 유전율 | 4.3 |
| `tand` | 손실탄젠트 | 0.02 |

## 초심자 체크

`실행 전 확인`에서 아래를 봅니다.

- `patch_w < p` 이어야 합니다.
- `fmin < fmax` 이어야 합니다.
- `sub_t`, `copper_t`는 0보다 커야 합니다.
- 처음에는 포트와 solver 자동 실행을 넣지 않는 편이 안전합니다.

## 왜 포트를 바로 만들지 않나

차폐 유닛셀의 포트/경계조건은 해석 목적에 따라 달라집니다.

- normal incidence인지
- Floquet port를 쓸지
- waveguide port를 쓸지
- periodic boundary를 어디에 둘지
- S11/S21만 볼지, shielding effectiveness로 후처리할지

이 조건을 잘못 자동 생성하면 CST는 열리지만 결과가 RF적으로 의미 없을 수 있습니다. 그래서 현재 기본 흐름은 **형상과 파라미터를 먼저 안정적으로 생성**하는 쪽입니다.

## 추천 작업 흐름

```text
기본 유닛셀 값 입력
-> 실행 전 확인
-> CST 2025 연결 테스트
-> CST 실행 + 결과폴더
-> CST에서 형상 확인
-> 포트/경계조건 전략 확정
```

LLM을 쓸 때도 처음에는 아래처럼 명확히 제한하는 문장이 좋습니다.

```text
포트는 만들지 말고 형상과 파라미터만 만들어줘.
```

## CST 2025 기본 설정

GUI와 CLI의 기본 CST ProgID:

```text
CSTStudio.Application.2025
```

처음 테스트할 때는 `CST 화면 보이기`를 켜고, CST에서 실제 형상이 맞는지 눈으로 확인하세요.

## 결과 비교를 위한 기록

`CST 실행 + 결과폴더`는 `runs` 아래에 아래 파일을 남깁니다.

```text
input_plan.json
design_params.json
summary.json
cst_project.cst
exports/
```

나중에 Python 모듈로 예측한 결과를 비교하려면 `design_params.json`을 입력으로 쓰고, CST export 파일은 `exports/`에 넣는 방식이 가장 깔끔합니다.
