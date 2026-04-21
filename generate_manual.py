"""
공공계약 법령 해석 챗봇 서비스 — 사용자 매뉴얼 HWPX 생성기
report 템플릿 기반, section0.xml 생성 → build_hwpx.py로 빌드
"""
import subprocess, sys, os

SKILL_DIR = r"C:\Users\COMTREE\.gemini\antigravity\skills\hwpxskill"
OUTPUT_DIR = r"C:\Users\COMTREE\Desktop\메뉴얼 제작"
SECTION_PATH = os.path.join(OUTPUT_DIR, "manual_section0.xml")
OUTPUT_HWPX = os.path.join(OUTPUT_DIR, "공공계약_법령챗봇_사용자매뉴얼.hwpx")

def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# ── XML builder helpers ──────────────────────────────────────────
class XMLBuilder:
    def __init__(self):
        self.parts = []
        self.pid = 1000000001  # paragraph id counter
        self.tid = 1000090001  # table id counter

    def _next_pid(self):
        p = self.pid; self.pid += 1; return p

    def _next_tid(self):
        t = self.tid; self.tid += 1; return t

    # ── paragraphs ──
    def empty(self):
        """빈 줄"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p>')

    def title(self, text):
        """문서 제목 (20pt 볼드, 중앙)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="20" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="7"><hp:t>{esc(text)}</hp:t></hp:run></hp:p>')

    def subtitle(self, text):
        """부제 / 날짜 등 (10pt, 중앙)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="20" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t>{esc(text)}</hp:t></hp:run></hp:p>')

    def section_header(self, text):
        """섹션 헤더 (12pt 돋움 볼드, 상단 굵은선+하단 얇은선)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="27" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="13"><hp:t>{esc(text)}</hp:t></hp:run></hp:p>')

    def heading2(self, text):
        """소제목 (14pt 볼드)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="8"><hp:t>{esc(text)}</hp:t></hp:run></hp:p>')

    def body(self, text):
        """본문 (10pt 바탕, 양쪽 정렬)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t>{esc(text)}</hp:t></hp:run></hp:p>')

    def body_bold_prefix(self, bold_text, normal_text):
        """볼드+일반 혼합 본문"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="10"><hp:t>{esc(bold_text)}</hp:t></hp:run>'
            f'<hp:run charPrIDRef="0"><hp:t>{esc(normal_text)}</hp:t></hp:run></hp:p>')

    def bullet(self, text):
        """글머리 항목 (들여쓰기 600, paraPr 24)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="24" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t>□ {esc(text)}</hp:t></hp:run></hp:p>')

    def sub_bullet(self, text):
        """하위 항목 (들여쓰기 1200, paraPr 25)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="25" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t>{esc(text)}</hp:t></hp:run></hp:p>')

    def deep_bullet(self, text):
        """깊은 하위 항목 (들여쓰기 1800, paraPr 26)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="26" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t>- {esc(text)}</hp:t></hp:run></hp:p>')

    def small_text(self, text):
        """소형 텍스트 (9pt, charPr 11)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="11"><hp:t>{esc(text)}</hp:t></hp:run></hp:p>')

    def right_text(self, text):
        """우측 정렬 텍스트 (paraPr 23)"""
        pid = self._next_pid()
        self.parts.append(
            f'<hp:p id="{pid}" paraPrIDRef="23" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0"><hp:t>{esc(text)}</hp:t></hp:run></hp:p>')

    # ── table ──
    def table(self, headers, rows, col_widths=None):
        """
        표 생성
        headers: ['col1', 'col2', ...]
        rows: [['val1','val2',...], ...]
        col_widths: [w1, w2, ...] (합=42520) or None for equal
        """
        cols = len(headers)
        if col_widths is None:
            base = 42520 // cols
            col_widths = [base] * cols
            col_widths[-1] = 42520 - base * (cols - 1)
        total_rows = 1 + len(rows)
        row_h = 2800

        # 기준 pid 확보, 각 셀마다 pid 소비
        cell_pids = []
        for _ in range(total_rows):
            row_pids = []
            for _ in range(cols):
                row_pids.append(self._next_pid())
            cell_pids.append(row_pids)

        # table wrapper paragraph
        tbl_pid = self._next_pid()
        tbl_id = self._next_tid()

        tr_xml = ""
        # header row
        hcells = ""
        for ci, h in enumerate(headers):
            hcells += (
                f'<hp:tc name="" header="1" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="4">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
                f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'<hp:p paraPrIDRef="21" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{cell_pids[0][ci]}">'
                f'<hp:run charPrIDRef="9"><hp:t>{esc(h)}</hp:t></hp:run>'
                f'</hp:p></hp:subList>'
                f'<hp:cellAddr colAddr="{ci}" rowAddr="0"/>'
                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{col_widths[ci]}" height="{row_h}"/>'
                f'<hp:cellMargin left="170" right="170" top="0" bottom="0"/>'
                f'</hp:tc>')
        tr_xml += f'<hp:tr>{hcells}</hp:tr>'

        # data rows
        for ri, row in enumerate(rows):
            dcells = ""
            for ci, cell in enumerate(row):
                dcells += (
                    f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="3">'
                    f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
                    f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                    f'<hp:p paraPrIDRef="22" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{cell_pids[ri+1][ci]}">'
                    f'<hp:run charPrIDRef="0"><hp:t>{esc(cell)}</hp:t></hp:run>'
                    f'</hp:p></hp:subList>'
                    f'<hp:cellAddr colAddr="{ci}" rowAddr="{ri+1}"/>'
                    f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                    f'<hp:cellSz width="{col_widths[ci]}" height="{row_h}"/>'
                    f'<hp:cellMargin left="170" right="170" top="0" bottom="0"/>'
                    f'</hp:tc>')
            tr_xml += f'<hp:tr>{dcells}</hp:tr>'

        tbl_xml = (
            f'<hp:p id="{tbl_pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0">'
            f'<hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
            f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" '
            f'repeatHeader="1" rowCnt="{total_rows}" colCnt="{cols}" cellSpacing="0" '
            f'borderFillIDRef="3" noAdjust="0">'
            f'<hp:sz width="42520" widthRelTo="ABSOLUTE" height="{row_h * total_rows}" heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
            f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" '
            f'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
            f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
            f'{tr_xml}'
            f'</hp:tbl></hp:run></hp:p>')
        self.parts.append(tbl_xml)

    def get_xml(self):
        """Complete section0.xml"""
        header = (
            '<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n'
            '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
            'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">\n'
            '  <!-- secPr 포함 첫 문단 -->\n'
            '  <hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">\n'
            '    <hp:run charPrIDRef="0">\n'
            '      <hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" '
            'tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0" '
            'textVerticalWidthHead="0" masterPageCnt="0">\n'
            '        <hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>\n'
            '        <hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>\n'
            '        <hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" '
            'border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>\n'
            '        <hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>\n'
            '        <hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">\n'
            '          <hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" top="5668" bottom="4252"/>\n'
            '        </hp:pagePr>\n'
            '        <hp:footNotePr>\n'
            '          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>\n'
            '          <hp:noteLine length="-1" type="SOLID" width="0.12 mm" color="#000000"/>\n'
            '          <hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>\n'
            '          <hp:numbering type="CONTINUOUS" newNum="1"/>\n'
            '          <hp:placement place="EACH_COLUMN" beneathText="0"/>\n'
            '        </hp:footNotePr>\n'
            '        <hp:endNotePr>\n'
            '          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>\n'
            '          <hp:noteLine length="14692344" type="SOLID" width="0.12 mm" color="#000000"/>\n'
            '          <hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>\n'
            '          <hp:numbering type="CONTINUOUS" newNum="1"/>\n'
            '          <hp:placement place="END_OF_DOCUMENT" beneathText="0"/>\n'
            '        </hp:endNotePr>\n'
            '        <hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">\n'
            '          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>\n'
            '        </hp:pageBorderFill>\n'
            '        <hp:pageBorderFill type="EVEN" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">\n'
            '          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>\n'
            '        </hp:pageBorderFill>\n'
            '        <hp:pageBorderFill type="ODD" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">\n'
            '          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>\n'
            '        </hp:pageBorderFill>\n'
            '      </hp:secPr>\n'
            '      <hp:ctrl>\n'
            '        <hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/>\n'
            '      </hp:ctrl>\n'
            '    </hp:run>\n'
            '    <hp:run charPrIDRef="0"><hp:t/></hp:run>\n'
            '  </hp:p>\n')
        # 첫 문단은 secPr 전용이므로 pid를 2부터 시작
        self.pid = max(self.pid, 1000000002)
        footer = '</hs:sec>'
        return header + '\n'.join(self.parts) + '\n' + footer


# ══════════════════════════════════════════════════════════════════
#                         매뉴얼 본문 작성
# ══════════════════════════════════════════════════════════════════

b = XMLBuilder()

# ── 표지 ──────────────────────────────────────────────────────────
b.empty()
b.empty()
b.empty()
b.empty()
b.title("공공계약 법령 해석 챗봇 서비스")
b.title("사용자 매뉴얼")
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
b.empty()

# ── 목차 ──────────────────────────────────────────────────────────
b.section_header("목  차")
b.empty()
b.body("1. 서비스 개요 ·········································································· 2")
b.body("2. 시스템 접속 방법 ···································································· 3")
b.body("3. 챗봇 사용법 ·········································································· 4")
b.body("4. 법령 데이터 계층 구조 ····························································· 6")
b.body("5. 관리자 기능 ·········································································· 7")
b.body("6. 자주 묻는 질문 (FAQ) ······························································ 8")
b.body("7. 문의 및 지원 ········································································· 9")
b.empty()
b.empty()

# ══════════════════════════════════════════════════════════════════
# 1. 서비스 개요
# ══════════════════════════════════════════════════════════════════
b.section_header("1. 서비스 개요")
b.empty()

b.heading2("1.1 서비스 목적")
b.empty()
b.body("공공계약 법령 해석 챗봇은 부산광역시 공공조달 모니터링 시스템의 부가 서비스로,")
b.body("계약 담당자가 법령·예규·내규에 대해 질문하면 근거 조항과 함께 해석을 제공하는 AI 챗봇 서비스입니다.")
b.empty()
b.body("기존에 법령 검색과 해석에 건당 약 30분이 소요되던 업무를 약 2분으로 단축하여,")
b.body("계약 담당자의 업무 효율을 획기적으로 개선합니다.")
b.empty()

b.heading2("1.2 주요 기능")
b.empty()
b.bullet("법령·예규·내규에 대한 AI 기반 질의응답")
b.bullet("관련 법적 근거 조항 자동 검색 및 제시")
b.bullet("법적 우선순위(상위법 → 예규 → 내규)에 따른 체계적 답변")
b.bullet("기관별 내규 반영을 통한 맞춤형 해석 제공")
b.bullet("대화 이력 저장 및 자주 묻는 질문(FAQ) 자동 생성")
b.empty()

b.heading2("1.3 기대 효과")
b.empty()
b.table(
    ["구분", "내용"],
    [
        ["업무 효율", "법령 검색·해석 시간 대폭 단축 (건당 30분 → 2분)"],
        ["정확도 향상", "관련 조항 교차 검토로 누락·오류 방지"],
        ["지식 표준화", "기관별 내규까지 포함한 일관된 계약 업무 지원"],
        ["시스템 연동", "모니터링 대시보드와 연계 → 법적 근거 즉시 조회"],
    ],
    [14000, 28520]
)
b.empty()

# ══════════════════════════════════════════════════════════════════
# 2. 시스템 접속 방법
# ══════════════════════════════════════════════════════════════════
b.section_header("2. 시스템 접속 방법")
b.empty()

b.heading2("2.1 접속 환경")
b.empty()
b.bullet("권장 브라우저: Google Chrome, Microsoft Edge (최신 버전)")
b.bullet("모바일 접속: 스마트폰 브라우저에서도 사용 가능")
b.bullet("네트워크: 부산광역시 행정망 또는 인터넷망 접속 가능")
b.empty()

b.heading2("2.2 접속 절차")
b.empty()
b.body("① 웹 브라우저에서 부산광역시 공공조달 모니터링 시스템에 접속합니다.")
b.body("② 좌측 메뉴 또는 상단 탭에서 「📚 법령 챗봇」을 클릭합니다.")
b.body("③ 소속 기관을 선택합니다 (해당 기관의 내규가 반영된 답변을 받을 수 있습니다).")
b.body("④ 질문 입력란에 궁금한 내용을 입력하고 전송합니다.")
b.empty()

b.heading2("2.3 기관 선택")
b.empty()
b.body("챗봇 화면 상단에서 소속 기관을 선택하면, 해당 기관의 자체 계약 지침(L4)과")
b.body("내규(L5)가 답변에 반영됩니다. 기관을 선택하지 않으면 공통 법령(L1~L3)만 참조합니다.")
b.empty()
b.table(
    ["기관 유형", "예시", "반영 데이터"],
    [
        ["부산광역시 본청", "부산광역시", "L1~L4"],
        ["자치구·군", "해운대구, 기장군 등", "L1~L5"],
        ["출자·출연기관", "부산교통공사 등", "L1~L5"],
    ],
    [10000, 14000, 18520]
)
b.empty()

# ══════════════════════════════════════════════════════════════════
# 3. 챗봇 사용법
# ══════════════════════════════════════════════════════════════════
b.section_header("3. 챗봇 사용법")
b.empty()

b.heading2("3.1 질문 입력 방법")
b.empty()
b.body("화면 하단의 질문 입력란에 궁금한 내용을 자연어로 입력합니다.")
b.body("가능한 한 구체적으로 질문할수록 정확한 답변을 받을 수 있습니다.")
b.empty()
b.body("▶ 좋은 질문 예시:")
b.sub_bullet("① \"수의계약 한도액이 얼마인가요?\"")
b.sub_bullet("② \"지역제한 입찰에서 지역업체 가점은 몇 %인가요?\"")
b.sub_bullet("③ \"MAS 2단계 경쟁에서 지역제한을 적용할 수 있나요?\"")
b.sub_bullet("④ \"긴급한 경우 수의계약이 가능한 조건은 무엇인가요?\"")
b.empty()
b.body("▶ 피해야 할 질문 예시:")
b.sub_bullet("① \"계약 어떻게 해요?\" (너무 광범위)")
b.sub_bullet("② \"법 알려줘\" (구체적 법령/내용 특정 필요)")
b.empty()

b.heading2("3.2 답변 구조")
b.empty()
b.body("챗봇의 답변은 다음 5단계 구조로 체계적으로 제공됩니다:")
b.empty()
b.table(
    ["단계", "구분", "내용"],
    [
        ["1", "결론", "질문에 대한 핵심 답변을 먼저 제시"],
        ["2", "법적 근거", "관련 법령·예규 조항 번호와 원문 제시"],
        ["3", "상세 해석", "조항의 의미와 적용 방법을 상세 설명"],
        ["4", "실무 적용", "실제 업무에서 어떻게 적용해야 하는지 안내"],
        ["5", "주의사항", "유의할 점, 예외 사항, 관련 참고 정보"],
    ],
    [5000, 8000, 29520]
)
b.empty()

b.heading2("3.3 근거 조항 확인")
b.empty()
b.body("답변에 포함된 법적 근거 조항은 법적 우선순위에 따라 표시됩니다:")
b.empty()
b.sub_bullet("① L1 상위법 (지방계약법·시행령·시행규칙) → 최우선 적용")
b.sub_bullet("② L2~L3 예규·고시 (행안부 계약예규, 조달청 기준)")
b.sub_bullet("③ L4~L5 내규 (부산시 지침, 기관별 내규)")
b.empty()
b.body("각 근거 조항은 법령명과 조항 번호가 함께 표시되며,")
b.body("원문 링크를 통해 국가법령정보센터에서 전문을 확인할 수 있습니다.")
b.empty()

b.heading2("3.4 대화 이력")
b.empty()
b.body("이전에 나눈 대화 내용은 자동으로 저장됩니다.")
b.body("좌측의 대화 이력 패널에서 이전 질문과 답변을 다시 확인할 수 있으며,")
b.body("이전 대화를 이어서 추가 질문을 할 수 있습니다.")
b.empty()

# ══════════════════════════════════════════════════════════════════
# 4. 법령 데이터 계층
# ══════════════════════════════════════════════════════════════════
b.section_header("4. 법령 데이터 계층 구조")
b.empty()

b.body("챗봇이 참조하는 법령 데이터는 6개 계층으로 구성되어 있으며,")
b.body("답변 시 L1(상위법) → L6(질의회신) 순서로 법적 우선순위에 따라 근거를 표시합니다.")
b.empty()

b.table(
    ["계층", "문서 유형", "수집 방법", "업데이트 주기"],
    [
        ["L1", "지방계약법·시행령·시행규칙", "법령 API 자동", "주 1회"],
        ["L2", "행안부 계약예규 (입찰·계약 집행기준)", "법령 API 자동", "주 1회"],
        ["L3", "조달청 입찰 조건·고시·기준", "API 또는 반자동", "월 1회"],
        ["L4", "부산시 자체 계약 지침", "관리자 업로드", "수동"],
        ["L5", "자치구군·출자출연기관 내규", "관리자 업로드", "수동"],
        ["L6", "행안부 질의회신·감사원 결정례", "수동 수집", "분기"],
    ],
    [5000, 16000, 11520, 10000]
)
b.empty()

b.heading2("4.1 데이터 수집 및 업데이트")
b.empty()
b.bullet("L1~L2: 국가법령정보센터 OpenAPI를 통해 자동 수집 (주 1회)")
b.bullet("L3: 조달청 API 연계 또는 반자동 수집 (월 1회)")
b.bullet("L4~L5: 관리자가 HWP/PDF 문서를 직접 업로드 (수동)")
b.bullet("L6: 행안부 질의회신·감사원 결정례 수동 등록 (분기)")
b.empty()
b.body("법령이 개정되면 자동 변경 감지 시스템이 작동하여 최신 내용으로 재색인합니다.")
b.empty()

# ══════════════════════════════════════════════════════════════════
# 5. 관리자 기능
# ══════════════════════════════════════════════════════════════════
b.section_header("5. 관리자 기능")
b.empty()

b.body("관리자 권한이 있는 사용자는 다음 기능을 사용할 수 있습니다.")
b.empty()

b.heading2("5.1 문서 업로드")
b.empty()
b.body("관리자 페이지에서 HWP 또는 PDF 형식의 문서를 업로드하면,")
b.body("시스템이 자동으로 텍스트를 추출하고 벡터 DB에 색인합니다.")
b.empty()
b.body("▶ 업로드 절차:")
b.sub_bullet("① 관리자 메뉴 → 「문서 관리」 클릭")
b.sub_bullet("② 「문서 업로드」 버튼 클릭")
b.sub_bullet("③ 파일 선택 (HWP, HWPX, PDF 형식 지원)")
b.sub_bullet("④ 문서 유형(지침/내규/질의회신 등) 및 소속 기관 선택")
b.sub_bullet("⑤ 「업로드」 버튼 클릭 → 자동 텍스트 추출 및 색인 완료")
b.empty()

b.heading2("5.2 기관 내규 등록")
b.empty()
b.body("소속 기관의 자체 계약 지침이나 내부 규정을 등록하면,")
b.body("해당 기관 사용자의 질문에 대해 내규까지 반영된 맞춤형 답변이 제공됩니다.")
b.empty()
b.body("▶ 등록 시 주의사항:")
b.sub_bullet("① 문서에 민감한 개인정보가 포함되어 있는지 확인하세요.")
b.sub_bullet("② 기밀 문서는 업로드 전 담당부서와 협의하세요.")
b.sub_bullet("③ 내규의 시행일을 정확하게 입력해야 답변 정확도가 높아집니다.")
b.empty()

b.heading2("5.3 색인 관리")
b.empty()
b.body("관리자는 색인된 문서 목록을 조회하고, 더 이상 유효하지 않은 문서를 삭제하거나")
b.body("특정 문서를 재색인할 수 있습니다.")
b.empty()

# ══════════════════════════════════════════════════════════════════
# 6. FAQ
# ══════════════════════════════════════════════════════════════════
b.section_header("6. 자주 묻는 질문 (FAQ)")
b.empty()

b.table(
    ["질문", "답변"],
    [
        ["챗봇의 답변에 법적 효력이 있나요?",
         "아닙니다. 본 서비스의 답변은 참고용이며 법적 효력이 없습니다. 최종 판단은 관련 법령 원문과 법무 자문을 통해 확인하시기 바랍니다."],
        ["법령이 최신 버전인지 어떻게 확인하나요?",
         "L1~L2 법령은 주 1회 자동 업데이트됩니다. 답변에 표시되는 법령의 시행일을 확인하시면 최신 여부를 판단할 수 있습니다."],
        ["다른 기관의 내규도 조회할 수 있나요?",
         "보안상 각 기관의 내규는 해당 기관 사용자만 조회할 수 있습니다. 공통 법령(L1~L3)은 모든 사용자가 조회 가능합니다."],
        ["답변이 정확하지 않은 것 같은데 어떻게 하나요?",
         "답변 하단의 👎 버튼을 눌러 피드백을 남겨주세요. 수집된 피드백은 답변 품질 개선에 활용됩니다."],
        ["이전 대화 내용을 삭제할 수 있나요?",
         "좌측 대화 이력에서 개별 대화를 삭제할 수 있습니다. 다만, 품질 분석용으로 익명화된 데이터는 6개월간 보관됩니다."],
        ["업로드한 문서는 외부로 전송되나요?",
         "기관 내규 등 업로드 문서는 NCP 서버 내에서 로컬 처리됩니다. 다만, AI 해석 시 Gemini API에 텍스트가 전달되므로 민감 정보는 마스킹 처리를 권장합니다."],
    ],
    [14000, 28520]
)
b.empty()

# ══════════════════════════════════════════════════════════════════
# 7. 문의 및 지원
# ══════════════════════════════════════════════════════════════════
b.section_header("7. 문의 및 지원")
b.empty()

b.body("서비스 이용 중 문의사항이 있으시면 아래 연락처로 문의해 주시기 바랍니다.")
b.empty()

b.table(
    ["구분", "내용"],
    [
        ["담당부서", "부산광역시 계약담당관"],
        ["전화번호", "051-888-XXXX"],
        ["이메일", "contract@busan.go.kr"],
        ["운영시간", "평일 09:00 ~ 18:00"],
    ],
    [14000, 28520]
)
b.empty()
b.empty()
b.body("※ 본 매뉴얼은 서비스 업데이트에 따라 내용이 변경될 수 있습니다.")
b.small_text("※ 본 서비스의 답변은 참고용이며 법적 효력이 없습니다. 최종 판단은 관련 법령 원문과 법무 자문을 통해 확인하시기 바랍니다.")
b.empty()
b.right_text("- 끝 -")

# ══════════════════════════════════════════════════════════════════
#                     XML 저장 및 HWPX 빌드
# ══════════════════════════════════════════════════════════════════

xml_content = b.get_xml()
with open(SECTION_PATH, 'w', encoding='utf-8') as f:
    f.write(xml_content)
print(f"[1/3] section0.xml 생성 완료: {SECTION_PATH}")

# build_hwpx.py 실행
build_cmd = [
    sys.executable,
    os.path.join(SKILL_DIR, "scripts", "build_hwpx.py"),
    "--template", "report",
    "--section", SECTION_PATH,
    "--title", "공공계약 법령 해석 챗봇 사용자 매뉴얼",
    "--creator", "부산광역시",
    "--output", OUTPUT_HWPX,
]
print(f"[2/3] HWPX 빌드 중...")
result = subprocess.run(build_cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"빌드 실패: {result.stderr}")
    sys.exit(1)
print(result.stdout)
print(f"[2/3] HWPX 빌드 완료: {OUTPUT_HWPX}")

# validate.py 실행
validate_cmd = [
    sys.executable,
    os.path.join(SKILL_DIR, "scripts", "validate.py"),
    OUTPUT_HWPX,
]
print(f"[3/3] HWPX 검증 중...")
result = subprocess.run(validate_cmd, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(f"검증 실패: {result.stderr}")
    sys.exit(1)
print("[완료] 매뉴얼 생성이 완료되었습니다!")
print(f"파일: {OUTPUT_HWPX}")
