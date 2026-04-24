"""시스템 프롬프트를 md 파일로 내보내기."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from system_prompt import SYSTEM_PROMPT
from gemini_engine import _AGENCY_GUIDE_MAP, _COMMON_PROCUREMENT

out = os.path.join(os.path.dirname(__file__), '시스템프롬프트_현황.md')
with open(out, 'w', encoding='utf-8') as f:
    f.write('# 지역상생 조달 어드바이저 — 시스템 프롬프트\n\n')
    f.write('> 파일: `app/system_prompt.py` + `app/gemini_engine.py` | 최종 수정: 2026.04.24 09:10\n\n')
    f.write('---\n\n')
    f.write('## 1. 고정 프롬프트 (system_prompt.py)\n\n')
    f.write('```\n')
    f.write(SYSTEM_PROMPT)
    f.write('\n```\n\n')
    f.write('---\n\n')
    f.write('## 2. 동적 주입 — 기관별 법체계 (gemini_engine.py)\n\n')
    f.write('### 공통 조달 원칙 (_COMMON_PROCUREMENT)\n```\n')
    f.write(_COMMON_PROCUREMENT.strip())
    f.write('\n```\n\n')
    for key, val in _AGENCY_GUIDE_MAP.items():
        f.write(f'### AGENCY_GUIDE_MAP["{key}"]\n```\n')
        f.write(val.strip())
        f.write('\n```\n\n')

print(f'OK: {out}')
