# 초심자용 CST Vibe 설계 가이드

이 가이드는 로컬 LLM이 숫자를 멋대로 해석하거나 포트를 자동으로 넣어서 이상한 형상이 생기는 일을 줄이기 위한 규칙입니다.

## 핵심 원칙

처음에는 **형상만 만들고 포트는 넣지 마세요.**

추천 순서:

```text
1. CST 연동 테스트
2. 단위 설정만 테스트
3. 기판 brick 하나 생성
4. 금속 패치 brick 하나 생성
5. 치수 확인
6. 경계조건 추가
7. 포트는 마지막에 수동으로 추가
```

포트와 경계조건은 CST 해석 방식에 따라 달라집니다. 로컬 LLM이 자동으로 넣게 두면 이상한 위치에 포트가 생길 수 있습니다.

## 기본 좌표계

초심자용 예제는 아래 좌표계를 씁니다.

```text
x 방향: 유닛셀 가로
y 방향: 유닛셀 세로
z 방향: 두께 방향

기판 아래면: z = 0
기판 윗면: z = sub_t
금속 패치: z = sub_t ~ sub_t + copper_t
중심: x = 0, y = 0
```

## 기본 파라미터

| 이름 | 뜻 | 예시 | 주의 |
| --- | --- | --- | --- |
| `p` | 유닛셀 주기 | `10` | 보통 mm 단위 |
| `sub_t` | 기판 두께 | `0.8` | 너무 작게 하면 형상 확인이 어려움 |
| `copper_t` | 구리 두께 | `0.035` | 35 um = 0.035 mm |
| `patch_w` | 패치 한 변 길이 | `7.2` | `p`보다 작아야 함 |
| `fmin` | 시작 주파수 | `1` | GHz |
| `fmax` | 끝 주파수 | `18` | GHz |

처음에는 아래 조건을 지키세요.

```text
patch_w < p
sub_t > 0
copper_t > 0
fmax > fmin
```

## 가장 안전한 첫 JSON

형상과 포트가 전혀 없는 연결 확인용입니다.

```json
{
  "project": {
    "mode": "new"
  },
  "parameters": {},
  "commands": []
}
```

그 다음은 단위만 확인합니다.

```json
{
  "project": {
    "mode": "new"
  },
  "parameters": {},
  "commands": [
    {
      "op": "units",
      "geometry": "mm",
      "frequency": "GHz",
      "time": "ns"
    }
  ]
}
```

## 초심자 기본 유닛셀

가장 먼저 써야 하는 예제는 이 파일입니다.

```text
examples/02_patch_unitcell_no_ports.json
```

이 예제는 포트를 만들지 않습니다. 기판과 패치만 만듭니다.

포함되는 형상:

```text
substrate: FR4 기판
top_patch: 구리 패치
```

포함하지 않는 것:

```text
포트
solver_start
결과 export
복잡한 boundary
```

## 로컬 LLM에 요청할 때 쓰는 문장

처음에는 이렇게 요청하세요.

```text
CST Vibe Runner JSON을 만들어줘.
포트는 만들지 마.
solver_start도 넣지 마.
기판과 금속 패치 형상만 만들어줘.
단위는 mm, GHz, ns로 해줘.
주기 p=10, 기판 두께 sub_t=0.8, 구리 두께 copper_t=0.035, 패치 폭 patch_w=7.2.
주파수 범위는 fmin=1, fmax=18.
```

나쁜 요청:

```text
알아서 차폐 유닛셀 만들어줘.
```

이렇게 말하면 LLM이 포트, 경계조건, solver를 마음대로 만들 수 있습니다.

좋은 요청:

```text
포트 없이 형상만 만들어줘.
기판은 FR4, 크기는 x/y -p/2~p/2, z 0~sub_t.
패치는 Copper, 크기는 x/y -patch_w/2~patch_w/2, z sub_t~sub_t+copper_t.
```

## 포트는 언제 넣어야 하나요?

초심자는 처음부터 포트를 넣지 않는 것을 추천합니다.

포트는 아래 정보를 정확히 알 때만 넣으세요.

```text
포트 종류: discrete port, waveguide port, floquet port 등
포트 위치: point1, point2 또는 면 위치
임피던스: 보통 50 ohm
해석 목적: S11, S21, 차폐효과 등
```

지금 프로그램의 `discrete_port`는 아주 단순한 선형 포트입니다. 차폐 유닛셀/주기구조 해석에는 CST에서 별도 포트 설정이 더 적절할 수 있습니다.

## 이상한 도형이 생길 때 확인할 것

1. `patch_w`가 `p`보다 큰지 확인합니다.
2. `xrange`, `yrange`, `zrange`가 의도와 맞는지 봅니다.
3. 숫자 단위가 mm 기준인지 확인합니다.
4. LLM이 포트나 cylinder를 몰래 추가했는지 봅니다.
5. `commands`에 원하지 않는 `solver_start`, `discrete_port`, `boolean`이 있는지 확인합니다.

## 추천 예제 순서

```text
examples/00_connection_test.json
examples/01_units_only.json
examples/02_patch_unitcell_no_ports.json
examples/03_patch_unitcell_with_ports_experimental.json
```

`03_patch_unitcell_with_ports_experimental.json`은 포트 실험용입니다. 초심자 기본 예제가 아닙니다.

## GUI에서 안전하게 쓰는 법

### 방법 A: 설계 마법사 사용

GUI 왼쪽의 `설계 마법사`에 숫자를 넣으면 회사 LLM을 왔다 갔다 하지 않아도 기본 JSON을 만들 수 있습니다.

1. `p`, `sub_t`, `copper_t`, `patch_w`, `fmin`, `fmax`를 입력합니다.
2. 처음에는 `유닛셀 경계조건 포함`을 끄고 시작합니다.
3. `형상 JSON 만들기`를 누릅니다.
4. `드라이런`으로 생성될 CST 매크로를 확인합니다.
5. CST에서 `CST 실행`을 눌러 형상만 먼저 확인합니다.

설계 마법사는 기본적으로 포트와 solver를 넣지 않습니다. CST 2025에서 초심자가 확인하기 가장 안전한 방식입니다.

### 방법 B: 예제 파일 사용

1. `열기` 버튼으로 `examples/02_patch_unitcell_no_ports.json`를 엽니다.
2. `드라이런`을 누릅니다.
3. 출력에 `create brick substrate`, `create brick top_patch`가 있는지 확인합니다.
4. `CST 실행`을 누릅니다.
5. CST에서 형상만 먼저 확인합니다.
6. 형상이 맞으면 그때 포트와 경계조건을 추가합니다.

## CST 2025 CT 버전 추천 설정

처음에는 아래 설정으로 시작하세요.

```text
COM ProgID: CSTStudio.Application
CST UI 보이기: 켬
유닛셀 경계조건 포함: 끔
포트: 만들지 않음
solver_start: 넣지 않음
```

이 상태에서 형상이 정확히 만들어지는 것을 확인한 뒤에만 경계조건과 포트를 추가하는 것이 좋습니다.
