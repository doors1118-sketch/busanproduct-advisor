"""
[개발 계획서] 지역상품 구매지원 지능형 매뉴얼 및 챗봇 구축 — HWPX 생성
report 템플릿 기반
"""
import subprocess, sys, os

SKILL_DIR = r"C:\Users\COMTREE\.gemini\antigravity\skills\hwpxskill"
OUTPUT_DIR = r"C:\Users\COMTREE\Desktop\메뉴얼 제작"
SECTION_PATH = os.path.join(OUTPUT_DIR, "plan_section0.xml")
OUTPUT_HWPX = os.path.join(OUTPUT_DIR, "지역상품_구매지원_개발계획서_v2.hwpx")

def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

class X:
    """최소 XML builder — report 템플릿 스타일 ID 사용"""
    def __init__(self):
        self.p = []
        self.pid = 1000000002
        self.tid = 1000090001

    def _np(self):
        r = self.pid; self.pid += 1; return r

    def _nt(self):
        r = self.tid; self.tid += 1; return r

    # ── 문단 ──
    def empty(self):
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p>')

    def title(self, t):
        """20pt 볼드 가운데"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="20" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="7"><hp:t>{esc(t)}</hp:t></hp:run></hp:p>')

    def subtitle(self, t):
        """10pt 가운데"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="20" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>{esc(t)}</hp:t></hp:run></hp:p>')

    def section(self, t):
        """섹션 헤더 (12pt 돋움 볼드, 상하선)"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="27" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="13"><hp:t>{esc(t)}</hp:t></hp:run></hp:p>')

    def h2(self, t):
        """14pt 볼드 소제목"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="8"><hp:t>{esc(t)}</hp:t></hp:run></hp:p>')

    def body(self, t):
        """10pt 본문"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>{esc(t)}</hp:t></hp:run></hp:p>')

    def bold_body(self, bold, normal):
        """볼드+일반 혼합"""
        pid = self._np()
        self.p.append(
            f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="10"><hp:t>{esc(bold)}</hp:t></hp:run>'
            f'<hp:run charPrIDRef="0"><hp:t>{esc(normal)}</hp:t></hp:run></hp:p>')

    def bullet(self, t):
        """□ 항목 (paraPr 24, 들여쓰기 600)"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="24" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>□ {esc(t)}</hp:t></hp:run></hp:p>')

    def sub(self, t):
        """하위 항목 (paraPr 25, 들여쓰기 1200)"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="25" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>{esc(t)}</hp:t></hp:run></hp:p>')

    def deep(self, t):
        """깊은 항목 (paraPr 26, 들여쓰기 1800)"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="26" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>- {esc(t)}</hp:t></hp:run></hp:p>')

    def right(self, t):
        """우측 정렬"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="23" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>{esc(t)}</hp:t></hp:run></hp:p>')

    def small(self, t):
        """9pt 소형"""
        pid = self._np()
        self.p.append(f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="11"><hp:t>{esc(t)}</hp:t></hp:run></hp:p>')

    # ── 표 ──
    def table(self, headers, rows, widths=None):
        cols = len(headers)
        if widths is None:
            base = 42520 // cols
            widths = [base] * cols
            widths[-1] = 42520 - base * (cols - 1)
        total = 1 + len(rows)
        rh = 2800
        cpids = []
        for _ in range(total):
            cpids.append([self._np() for _ in range(cols)])
        tpid = self._np()
        tid = self._nt()

        def cell(txt, ci, ri, is_header):
            bf = '4' if is_header else '3'
            cp = '9' if is_header else '0'
            pp = '21' if is_header else '22'
            hd = '1' if is_header else '0'
            return (
                f'<hp:tc name="" header="{hd}" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="{bf}">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
                f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'<hp:p paraPrIDRef="{pp}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{cpids[ri][ci]}">'
                f'<hp:run charPrIDRef="{cp}"><hp:t>{esc(txt)}</hp:t></hp:run>'
                f'</hp:p></hp:subList>'
                f'<hp:cellAddr colAddr="{ci}" rowAddr="{ri}"/>'
                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{widths[ci]}" height="{rh}"/>'
                f'<hp:cellMargin left="170" right="170" top="0" bottom="0"/>'
                f'</hp:tc>')

        tr = '<hp:tr>' + ''.join(cell(h, i, 0, True) for i, h in enumerate(headers)) + '</hp:tr>'
        for ri, row in enumerate(rows):
            tr += '<hp:tr>' + ''.join(cell(c, ci, ri+1, False) for ci, c in enumerate(row)) + '</hp:tr>'

        self.p.append(
            f'<hp:p id="{tpid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0">'
            f'<hp:tbl id="{tid}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
            f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" '
            f'repeatHeader="1" rowCnt="{total}" colCnt="{cols}" cellSpacing="0" '
            f'borderFillIDRef="3" noAdjust="0">'
            f'<hp:sz width="42520" widthRelTo="ABSOLUTE" height="{rh*total}" heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
            f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
            f'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
            f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
            f'{tr}</hp:tbl></hp:run></hp:p>')

    def xml(self):
        hdr = (
            "<?xml version='1.0' encoding='UTF-8'?>\n"
            '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
            'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">\n'
            '<hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
            '  <hp:run charPrIDRef="0">\n'
            '    <hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" '
            'tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0" '
            'textVerticalWidthHead="0" masterPageCnt="0">\n'
            '      <hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>\n'
            '      <hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>\n'
            '      <hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" '
            'border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>\n'
            '      <hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>\n'
            '      <hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">\n'
            '        <hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" top="5668" bottom="4252"/>\n'
            '      </hp:pagePr>\n'
            '      <hp:footNotePr>\n'
            '        <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>\n'
            '        <hp:noteLine length="-1" type="SOLID" width="0.12 mm" color="#000000"/>\n'
            '        <hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>\n'
            '        <hp:numbering type="CONTINUOUS" newNum="1"/>\n'
            '        <hp:placement place="EACH_COLUMN" beneathText="0"/>\n'
            '      </hp:footNotePr>\n'
            '      <hp:endNotePr>\n'
            '        <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>\n'
            '        <hp:noteLine length="14692344" type="SOLID" width="0.12 mm" color="#000000"/>\n'
            '        <hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>\n'
            '        <hp:numbering type="CONTINUOUS" newNum="1"/>\n'
            '        <hp:placement place="END_OF_DOCUMENT" beneathText="0"/>\n'
            '      </hp:endNotePr>\n'
            '      <hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">\n'
            '        <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>\n'
            '      </hp:pageBorderFill>\n'
            '      <hp:pageBorderFill type="EVEN" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">\n'
            '        <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>\n'
            '      </hp:pageBorderFill>\n'
            '      <hp:pageBorderFill type="ODD" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">\n'
            '        <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>\n'
            '      </hp:pageBorderFill>\n'
            '    </hp:secPr>\n'
            '    <hp:ctrl>\n'
            '      <hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/>\n'
            '    </hp:ctrl>\n'
            '  </hp:run>\n'
            '  <hp:run charPrIDRef="0"><hp:t/></hp:run>\n'
            '</hp:p>\n')
        return hdr + '\n'.join(self.p) + '\n</hs:sec>'


# ══════════════════════════════════════════════════════════════
#                     개발 계획서 본문
# ══════════════════════════════════════════════════════════════

b = X()

# ── 표지 ──
b.empty()
b.empty()
b.empty()
b.empty()
b.title("[개발 계획서]")
b.empty()
b.title("지역상품 구매지원")
b.title("지능형 매뉴얼 및 챗봇 구축")
b.empty()
b.empty()
b.empty()
b.subtitle("부산광역시 공공조달 모니터링 시스템")
b.empty()
b.subtitle("2026년 4월")
b.empty()
b.empty()
b.empty()
b.empty()
b.empty()
b.empty()
b.empty()

# ══════════════════════════════════════════════════════════════
# 1. 프로젝트 개요
# ══════════════════════════════════════════════════════════════
b.section("1. 프로젝트 개요")
b.empty()

b.table(
    ["구분", "내용"],
    [
        ["명칭", "지역상생 조달 협력 어드바이저 (가칭)"],
        ["목적", "복잡한 계약 법령 및 지침에 대한 심리적 장벽을 제거하고, 실시간 데이터를 기반으로 지역 업체와의 계약 가능 여부를 즉시 판단하여 지역 조달 수주율을 제고"],
        ["대상", "부산시 및 구·군 공무원, 출자·출연기관, 관내 국가기관 계약 담당자"],
        ["예산 및 인프라", "자체 개발 / Naver Cloud Platform (NCP)"],
    ],
    [10000, 32520]
)
b.empty()
b.empty()

# ══════════════════════════════════════════════════════════════
# 2. 주요 기능 및 시스템 구조
# ══════════════════════════════════════════════════════════════
b.section("2. 주요 기능 및 시스템 구조")
b.empty()

# ── 2-① ──
b.h2("① 지능형 법령·지침 검색 (RAG 기반 챗봇)")
b.empty()

b.bold_body("법제처 API 연동: ", "지방계약법, 국가계약법 및 시행령을 실시간으로 호출하여 최신 법령 근거 제시.")
b.empty()
b.bold_body("지침 학습: ", "각 기관별(부산시, 공사·공단 등) 내부 업무지침 및 계약 매뉴얼(PDF/HWPX)을 학습하여 기관 맞춤형 답변 제공.")
b.empty()
b.bold_body("판례 검색: ", "지역 제한 입찰이나 수의계약 관련 주요 판례를 요약하여 '위법성 여부'에 대한 가이드라인 제시.")
b.empty()

# ── 2-② ──
b.h2("② 지역업체 매칭 및 사전 검토 (Web App)")
b.empty()

b.bold_body("실시간 업체 검색: ", "기존 모니터링 시스템에 등록된 약 20,000개의 부산 소재 업체 데이터를 활용.")
b.empty()
b.bold_body("면허 및 품명 필터링: ", "18,678개의 면허 업종 및 20,345개의 대표 품명을 기준으로 계약 목적에 맞는 지역 업체 리스트 즉시 제공.")
b.empty()
b.bold_body("계약 가능성 시뮬레이션: ", "발주하려는 사업의 금액과 성격 입력 시, 지역 제한 경쟁이나 수의계약이 가능한지 법적 근거와 함께 판단 결과 도출.")
b.empty()

# ── 2-③ ──
b.h2("③ 멀티 채널 인터페이스")
b.empty()

b.bold_body("웹앱 (Web App): ", "정밀한 검색 및 데이터 시각화, 업체 상세 정보 확인용.")
b.empty()
b.bold_body("메신저 (KakaoTalk/Telegram): ", "이동 중이거나 간이 조회가 필요할 때 프롬프트 형태의 챗봇 상담 제공.")
b.empty()
b.empty()

# ══════════════════════════════════════════════════════════════
# 3. 데이터 및 기술 스택 활용 방안
# ══════════════════════════════════════════════════════════════
b.section("3. 데이터 및 기술 스택 활용 방안")
b.empty()

b.h2("가. 핵심 데이터 소스")
b.empty()

b.bold_body("법령 데이터 (실시간): ", "법제처 국가법령정보센터 OpenAPI를 통해 지방계약법·국가계약법 및 각 시행령·시행규칙을 실시간 호출. 법령 개정 시 자동 감지 및 재학습.")
b.empty()
b.bold_body("행정예규·고시: ", "행안부 계약예규(입찰·계약 집행기준, 낙찰자 결정기준), 조달청 입찰 조건·고시 등을 체계적으로 수집·색인하여 최신 기준 반영.")
b.empty()
b.bold_body("판례·질의회신: ", "지역 제한 입찰, 수의계약 관련 주요 판례 및 행안부 질의회신·감사원 결정례를 수집하여 위법성 판단의 근거 자료로 활용.")
b.empty()
b.bold_body("기관별 내부 지침: ", "부산시 자체 계약 지침, 각 구·군 및 출자·출연기관 내규(PDF/HWPX)를 업로드·학습하여 기관 맞춤형 답변 제공.")
b.empty()

b.h2("나. 기술 스택")
b.empty()

b.table(
    ["구분", "선택", "사유"],
    [
        ["LLM", "Gemini / NCP CLOVA Studio", "롱컨텍스트, 한국어 법률 지원"],
        ["임베딩", "Gemini text-embedding", "동일 생태계, 한국어 최적화"],
        ["벡터 DB", "ChromaDB", "경량, Python 네이티브, 로컬 실행"],
        ["RAG 프레임워크", "LangChain", "RAG 파이프라인 표준, LLM 연동"],
        ["프론트엔드", "Streamlit / Web App", "기존 대시보드 기술, 챗 UI 내장"],
        ["법령 수집", "법제처 OpenAPI", "법령·행정규칙 전문 실시간 제공"],
        ["인프라", "NCP (24시간 운영)", "보안성·안정성 검증, 추가비용 없음"],
    ],
    [10000, 12000, 20520]
)
b.empty()
b.empty()

# ══════════════════════════════════════════════════════════════
# 4. 개발 단계별 로드맵
# ══════════════════════════════════════════════════════════════
b.section("4. 개발 단계별 로드맵")
b.empty()

b.table(
    ["단계", "주요 과제", "비고"],
    [
        ["1단계: 데이터 임베딩", "법령 API 연동 및 기관별 지침서 데이터베이스화", "자체 개발"],
        ["2단계: API 연동", "모니터링 시스템의 업체/계약 데이터 API 연결", "기존 자원 활용"],
        ["3단계: 챗봇 고도화", "판례 및 질의응답 시나리오 학습 (LLM 적용)", "NCP CLOVA Studio 등 검토"],
        ["4단계: 채널 확장", "카카오톡/텔레그램 API 연동 및 웹앱 UI 최적화", "-"],
    ],
    [10000, 22520, 10000]
)
b.empty()
b.empty()

# ══════════════════════════════════════════════════════════════
# 5. 기대 효과
# ══════════════════════════════════════════════════════════════
b.section("5. 기대 효과")
b.empty()

b.bold_body("행정 효율성 증대: ", "계약 담당자가 수많은 법령과 지침을 일일이 확인하는 시간을 획기적으로 단축.")
b.empty()
b.bold_body("심리적 안전장치 마련: ", "법령 근거와 판례를 챗봇이 즉시 제시함으로써 지역 업체 계약 시 발생할 수 있는 감사나 위법성에 대한 우려 불식.")
b.empty()
b.bold_body("지역 수주율 제고: ", "특히 수주율이 상대적으로 낮은 정부 및 국가공공기관(31.6%) 담당자들에게 지역 업체 정보를 선제적으로 제공하여 구매 전환 유도.")
b.empty()
b.bold_body("데이터 기반 행정: ", "70.6% 수준인 부산시 본청의 지역 수주율을 상향 평준화하고, 전체 수주 금액(약 3조 7천억 원) 중 지역 내 환류 비율 극대화.")
b.empty()
b.empty()
b.right("- 끝 -")

# ══════════════════════════════════════════════════════════════
#                     빌드
# ══════════════════════════════════════════════════════════════

with open(SECTION_PATH, 'w', encoding='utf-8') as f:
    f.write(b.xml())
print(f"[1/3] section0.xml 생성: {SECTION_PATH}")

print("[2/3] HWPX 빌드 중...")
r = subprocess.run([
    sys.executable,
    os.path.join(SKILL_DIR, "scripts", "build_hwpx.py"),
    "--template", "report",
    "--section", SECTION_PATH,
    "--title", "지역상품 구매지원 지능형 매뉴얼 및 챗봇 구축 개발 계획서",
    "--creator", "부산광역시",
    "--output", OUTPUT_HWPX,
], capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(f"빌드 실패:\n{r.stderr}")
    sys.exit(1)
print(f"[2/3] 빌드 완료: {OUTPUT_HWPX}")

print("[3/3] 검증 중...")
r = subprocess.run([
    sys.executable,
    os.path.join(SKILL_DIR, "scripts", "validate.py"),
    OUTPUT_HWPX,
], capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(f"검증 실패:\n{r.stderr}")
    sys.exit(1)
print("[완료] 개발계획서 HWPX 생성 완료!")
