# CST Vibe Runner 문제 진단 방법

에러가 나면 전체 코드를 외울 필요 없이 아래 순서로 보면 됩니다.

## 1. 먼저 누를 버튼

```text
실행 전 확인
-> CST 2025 연결 테스트
-> CST 실행 + 결과폴더
-> 실패하면 문제 진단
```

`문제 진단`은 실패한 명령에서 바로 멈추지 않고 다음 명령도 계속 시도합니다. 그래서 어느 지점까지 CST가 받아들이는지 찾기 좋습니다.

## 2. 로컬 LLM에게 전달할 때

GUI에서 `리포트 저장` 또는 `출력 복사`를 누른 뒤 아래 형식으로 물어보세요.

```text
CST Studio Suite 2025 CT 자동화 스크립트 실행 중 에러가 발생했습니다.

사용 도구:
- CST Vibe Runner
- Python pywin32 COM 자동화
- CST ProgID: CSTStudio.Application.2025

내가 누른 버튼:
- 실행 전 확인 / CST 2025 연결 테스트 / CST 실행 + 결과폴더 / 문제 진단 중 하나

종료코드:
- 여기에 종료코드 입력

출력 로그:
여기에 출력창 내용을 붙여넣기

요청:
이 에러가 CST 매크로 문법 문제인지, pywin32 COM 호출 문제인지, 파라미터 문제인지 구분해 주세요.
가능하면 CST 2025 CT 기준 수정 방안을 알려주세요.
```

## 3. 종료코드 의미

```text
0 = 정상
1 = Python 또는 CST 실행 중 예상 못한 예외
2 = 입력/JSON/명령 검증 실패 또는 CST가 명령을 거부
```

`종료코드 2`가 무조건 프로그램 고장이라는 뜻은 아닙니다. CST가 어떤 명령을 거부했는지 출력창의 `Original error`를 봐야 합니다.

## 4. 자주 보는 문장

### Original error

CST나 COM이 직접 돌려준 원본 에러입니다. 제일 중요합니다.

### AddToHistory

CST 히스토리에 매크로 명령을 넣는 단계입니다. CST 2025에서 인자 전달이 까다로운 경우가 있어 이 도구는 여러 호출 방식을 자동 시도합니다.

### StoreParameter

파라미터를 CST에 저장하는 단계입니다. 이름이 비어 있거나 값이 숫자로 해석되지 않으면 실패할 수 있습니다.

### COM Dispatch

Python이 CST 프로그램을 여는 단계입니다. 여기서 실패하면 CST 설치, COM 등록, ProgID 문제일 가능성이 큽니다.

## 5. CST 2025 ProgID

기본값:

```text
CSTStudio.Application.2025
```

자동 재시도:

```text
CSTStudio.Application
CSTStudio.Application.2024
CSTStudio.Application.2023
```

## 6. 안전한 재현 순서

에러를 다시 확인할 때는 복잡한 LLM 결과 대신 기본 예제로 시작하세요.

```powershell
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --dry-run
python .\cst_vibe_runner.py .\examples\02_patch_unitcell_no_ports.json --visible --continue-on-error
```

첫 번째는 CST 없이 확인합니다. 두 번째는 CST 설치 PC에서 실제 연결을 확인합니다.
