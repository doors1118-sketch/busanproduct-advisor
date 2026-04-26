# TEST COMMANDS

사무실 환경(또는 새로운 개발 PC)에서 프로젝트를 재구성하고 검증할 때 사용하는 명령어 목록입니다.

## 1. 초기 환경 세팅
```powershell
# 가상환경 생성
python -m venv .venv

# 가상환경 활성화 (Windows)
.venv\Scripts\activate

# 의존성 패키지 설치
pip install -r requirements.txt
# (또는 환경에 맞춰 pip install -e . / poetry install 등 사용)

# 환경변수 템플릿 복사 후 실제 키값 입력
copy .env.example .env
```

## 2. Staging 전체 검증
```powershell
python run_staging_verification.py
```

## 3. TC8 라우팅 정책 런타임 실행 방법
Pro Quota가 확보되었는지 확인 후, 런타임 테스트를 수행합니다.
```powershell
python run_tc8_routing.py
```
**결과 확인**:
실행이 완료되면 생성된 `tc8_routing_result.json` 및 `TC8_routing_result.md`에서 런타임 관련 필수 필드(`pro_call_executed=true`, `fallback_used` 등)가 정상적으로 찍혔는지 확인합니다.
