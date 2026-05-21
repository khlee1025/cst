# CST RF Parameter Sweep Starter

이 폴더는 CST Studio Suite 안테나 모델을 Python으로 반복 실행하기 위한 최소 골격입니다.

## 구조

- `run_sweep.py`: 스윕 실행 진입점
- `src/sweep.py`: 파라미터 조합 생성, run 폴더 생성, 로그 저장
- `src/cst_adapter.py`: CST Studio Suite Python API 연결부
- `configs/sweep.patch_antenna.example.json`: 패치 안테나용 예시 설정
- `runs/`: 실행 결과가 저장되는 폴더

## 중요한 개념

CST 연동은 일반적인 웹 서버 API처럼 `server_url`에 요청을 보내는 구조가 아닙니다.

보통은 세 가지 방식 중 하나입니다.

1. **로컬 GUI 연동**
   - Python이 같은 Windows PC에서 실행 중인 CST Studio Suite를 제어합니다.
   - `cst.interface` 패키지가 필요합니다.
   - 개발과 디버깅에는 이 방식이 가장 쉽습니다.
   - 특수한 원격 Design Environment가 준비된 경우 `connect_address`를 쓸 수 있지만, 단순 IP나 라이선스 서버 주소와는 다릅니다.

2. **원격 서버/HPC 실행**
   - Python이 각 run별 `.cst` 파일과 파라미터 파일을 만들고, 회사 서버의 CST batch/HPC/job scheduler에 제출합니다.
   - 이때 "서버 주소"는 보통 CST API 주소가 아니라 SSH 주소, 공유 폴더, job scheduler, 또는 CST batch 실행 환경입니다.

3. **라이선스 서버**
   - `license server address`는 CST 실행 권한을 가져오는 주소일 뿐입니다.
   - Python이 CST 모델 값을 직접 바꾸는 제어 주소가 아닙니다.

## 먼저 하는 테스트

CST가 없는 환경에서도 dry-run으로 스윕 조합과 폴더 생성만 검증할 수 있습니다.

```powershell
python .\run_sweep.py --config .\configs\sweep.patch_antenna.example.json --dry-run
```

GUI로 직접 파라미터를 넣으려면:

```powershell
python .\gui_sweep.py
```

## 결과 자동 분석

각 run 폴더에 CST에서 export한 S11 파일이 있으면 자동으로 분석합니다.

기본으로 찾는 파일 이름:

```text
s11.csv
result_s11.csv
s11.txt
result_s11.txt
*s11*.csv
*s11*.txt
```

파일은 보통 2열이면 됩니다.

```csv
frequency_ghz,s11_db
2.30,-4
2.40,-12
2.45,-18
2.50,-11
2.60,-5
```

분석 결과:

- 목표 주파수의 S11
- S11 최소값
- S11 최소 주파수
- -10 dB bandwidth
- 목표 통과 여부
- best run ranking

GUI에서는 `Analyze Results` 버튼을 누르면 `runs/analysis_results.csv`가 생성됩니다.
명령줄에서는 다음처럼 실행합니다.

```powershell
python .\analyze_results.py --config .\configs\sweep.patch_antenna.example.json
```

실제 CST 실행은 `dry_run`을 끄고, `template_cst`에 실제 CST 프로젝트 경로를 넣은 뒤 실행합니다.

```powershell
python .\run_sweep.py --config .\configs\my_antenna_sweep.json
```

## 파라미터 간격 지정

두 가지 방식이 가능합니다.

명시적 값 목록:

```json
{
  "name": "feed_x",
  "values": [4.0, 5.0, 6.0, 7.0]
}
```

간격 기반:

```json
{
  "name": "patch_L",
  "start": 28.0,
  "stop": 32.0,
  "step": 1.0
}
```

처음에는 파라미터 2~3개만 sweep하세요. 변수 5개에 각 10점이면 100,000번 시뮬레이션이 됩니다.

## 회사 CST 서버에서 돌릴 때 필요한 정보

다음 중 회사 환경이 어떤 방식인지 확인해야 합니다.

- CST가 설치된 원격 Windows 서버에서 Python도 같이 실행할 수 있는지
- SSH나 원격 데스크톱으로 접속하는지
- 공유 폴더 경로가 있는지
- CST batch 실행 명령을 쓸 수 있는지
- 회사가 CST Distributed Computing / HPC Queue를 쓰는지
- 라이선스 서버 주소만 있는 것인지
- 원격 CST Design Environment 연결 주소가 따로 제공되는지

이 정보가 정해지면 `src/cst_adapter.py`의 실행부를 회사 환경에 맞게 고정하면 됩니다.

## Git에 올릴 때

`.cst` 프로젝트 파일과 `runs/` 결과 폴더는 용량이 커질 수 있어서 기본적으로 `.gitignore`에 넣어두었습니다.
코드, 설정 예시, GUI만 Git에 올리고 실제 CST 모델은 회사 공유 폴더나 Git LFS로 관리하는 편이 안전합니다.
