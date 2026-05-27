# 모기장 구조 유닛셀 설계 가이드

기본 구조는 사각기둥 실 4개로 만드는 `ㅁ`자 모기장 유닛셀입니다.
기본 재료는 CST 내장 재료인 `PEC`입니다.

## 기본 좌표계

원점 `(0, 0)`을 ㅁ자의 한쪽 모서리 기준으로 둡니다.

```text
x 방향: 0 -> length
y 방향: 0 -> -length
z 방향: 0 -> thickness
단위: um
주파수 단위: GHz
```

## 생성되는 사각기둥

| 이름 | 역할 | x 범위 | y 범위 | z 범위 |
| --- | --- | --- | --- | --- |
| `thread_top_x` | x+ 방향 윗 실 | `0..length` | `-width..0` | `0..thickness` |
| `thread_left_y` | y- 방향 왼쪽 실 | `0..width` | `-length..0` | `0..thickness` |
| `thread_bottom_x` | 대칭된 아래 실 | `0..length` | `-length..-length+width` | `0..thickness` |
| `thread_right_y` | 대칭된 오른쪽 실 | `length-width..length` | `-length..0` | `0..thickness` |

이 네 개가 합쳐져 ㅁ자 모기장 프레임을 만듭니다.

## 핵심 파라미터

| 파라미터 | 의미 | 기본값 |
| --- | --- | --- |
| `length` | ㅁ자 외곽 한 변 길이이자 기본 space | 100 um |
| `width` | 실 폭 | 10 um |
| `thickness` | z축 두께 | 2 um |
| `fmin` | 시작 주파수 | 1 GHz |
| `fmax` | 끝 주파수 | 18 GHz |
| `floquet_modes` | Floquet mode number | 2 |

## 체크 기준

- `length > 0`
- `width > 0`
- `thickness > 0`
- `width < length / 2`
- `fmin < fmax`
- 기본 경계조건은 x/y `unit cell`, z `open add space`입니다. JSON/매크로 값은 `expanded open`을 씁니다.
- 기본 Floquet port는 `Zmin`/`Zmax`, mode number `2`

`width`가 너무 크면 가운데 빈 공간이 사라집니다.

## 추천 작업 흐름

```text
숫자 직접 입력 또는 대사 적용
-> 실행 전 확인
-> CST 해석 + 결과 보기
-> S11/S21 결과 확인
```

기본 실행은 Floquet port를 만든 뒤 Solver Start까지 자동으로 보냅니다. 스윕은 같은 CST 프로젝트 안에서 파라미터 값을 바꾸고 Solver Start를 반복합니다.
