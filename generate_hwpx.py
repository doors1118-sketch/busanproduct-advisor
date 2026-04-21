import re
import os

def escape(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def process_inline(text):
    parts = re.split(r'(\*\*.*?\*\*)', text)
    res = ''
    for p in parts:
        if p.startswith('**') and p.endswith('**'):
            inner = escape(p[2:-2])
            res += f'<hp:run charPrIDRef="10"><hp:t>{inner}</hp:t></hp:run>'
        else:
            if p:
                res += f'<hp:run charPrIDRef="0"><hp:t>{escape(p)}</hp:t></hp:run>'
    if not res:
        res = '<hp:run charPrIDRef="0"><hp:t/></hp:run>'
    return res

lines = open(r'C:\Users\COMTREE\.gemini\antigravity\brain\463cb875-f260-4395-a82f-7285d378d666\답변초안_부산교통공사.md', encoding='utf-8').read().split('\n')

xml = []
xml.append('''<?xml version='1.0' encoding='UTF-8'?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
  <hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" masterPageCnt="0">
        <hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>
        <hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>
        <hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>
        <hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>
        <hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">
          <hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" top="5668" bottom="4252"/>
        </hp:pagePr>
        <hp:footNotePr>
          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>
          <hp:noteLine length="-1" type="SOLID" width="0.12 mm" color="#000000"/>
          <hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>
          <hp:numbering type="CONTINUOUS" newNum="1"/>
          <hp:placement place="EACH_COLUMN" beneathText="0"/>
        </hp:footNotePr>
        <hp:endNotePr>
          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>
          <hp:noteLine length="14692344" type="SOLID" width="0.12 mm" color="#000000"/>
          <hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>
          <hp:numbering type="CONTINUOUS" newNum="1"/>
          <hp:placement place="END_OF_DOCUMENT" beneathText="0"/>
        </hp:endNotePr>
        <hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
        <hp:pageBorderFill type="EVEN" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
        <hp:pageBorderFill type="ODD" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
      </hp:secPr>
      <hp:ctrl>
        <hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/>
      </hp:ctrl>
    </hp:run>
    <hp:run charPrIDRef="0">
      <hp:t/>
    </hp:run>
  </hp:p>
''')

pid = 1000000002

in_table = False
table_rows = []

def render_table(rows, current_pid):
    cols = len(rows[0])
    widths = [42520 // cols] * cols
    tr_xml = ""
    for r_idx, row in enumerate(rows):
        tc_xml = ""
        for c_idx, cell in enumerate(row):
            bg = 'borderFillIDRef="4"' if r_idx == 0 else 'borderFillIDRef="3"'
            tc_xml += f"""
        <hp:tc name="" header="{1 if r_idx==0 else 0}" hasMargin="0" protect="0" editable="0" dirty="1" {bg}>
          <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
            <hp:p paraPrIDRef="21" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="{current_pid}">
              {process_inline(cell)}
            </hp:p>
          </hp:subList>
          <hp:cellAddr colAddr="{c_idx}" rowAddr="{r_idx}"/>
          <hp:cellSpan colSpan="1" rowSpan="1"/>
          <hp:cellSz width="{widths[c_idx]}" height="3000"/>
          <hp:cellMargin left="0" right="0" top="0" bottom="0"/>
        </hp:tc>"""
            current_pid += 1
        tr_xml += f"<hp:tr>{tc_xml}</hp:tr>"
    
    tbl_xml = f"""
<hp:p id="{current_pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0">
    <hp:tbl id="{current_pid+1}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" rowCnt="{len(rows)}" colCnt="{cols}" cellSpacing="0" borderFillIDRef="3" noAdjust="0">
      <hp:sz width="42520" widthRelTo="ABSOLUTE" height="{3000*len(rows)}" heightRelTo="ABSOLUTE" protect="0"/>
      <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>
      <hp:outMargin left="0" right="0" top="0" bottom="0"/>
      <hp:inMargin left="0" right="0" top="0" bottom="0"/>
      {tr_xml}
    </hp:tbl>
  </hp:run>
</hp:p>
"""
    return tbl_xml, current_pid + 2

for line in lines:
    orig_line = line
    line = line.strip()
    
    if line.startswith('|'):
        in_table = True
        if '---' in line:
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        table_rows.append(cells)
        continue
    else:
        if in_table:
            in_table = False
            t_xml, pid = render_table(table_rows, pid)
            xml.append(t_xml)
            table_rows = []

    if not line:
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t/></hp:run></hp:p>')
        pid += 1
        continue

    # blockquote
    if line.startswith('>') and '[!' not in line:
        content = process_inline(line[1:].strip())
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="24" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{content}</hp:p>')
        pid += 1
        continue
    elif line.startswith('> [!'):
        continue
        
    # headings
    if line.startswith('# '):
        content = escape(line[2:].strip())
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="20" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="7"><hp:t>{content}</hp:t></hp:run></hp:p>')
    elif line.startswith('## '):
        content = escape(line[3:].strip())
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="27" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="13"><hp:t>{content}</hp:t></hp:run></hp:p>')
    elif line.startswith('### '):
        content = escape(line[4:].strip())
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="8"><hp:t>{content}</hp:t></hp:run></hp:p>')
    elif line.startswith('#### '):
        content = escape(line[5:].strip())
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="12"><hp:t>{content}</hp:t></hp:run></hp:p>')
    # lists
    elif line.startswith('- '):
        content = process_inline(line[2:].strip())
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="25" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>· </hp:t></hp:run>{content}</hp:p>')
    elif re.match(r'^\d+\.\s', line):
        content = process_inline(line[line.find(' ')+1:].strip())
        num = line.split('.')[0]
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="24" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="0"><hp:t>{num}. </hp:t></hp:run>{content}</hp:p>')
    else:
        content = process_inline(line)
        xml.append(f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{content}</hp:p>')
    pid += 1

if in_table:
    t_xml, pid = render_table(table_rows, pid)
    xml.append(t_xml)

xml.append('</hs:sec>')

with open(r'C:\Users\COMTREE\Desktop\메뉴얼 제작\temp_section0.xml', 'w', encoding='utf-8') as f:
    f.write('\n'.join(xml))
print("XML creation completed.")
