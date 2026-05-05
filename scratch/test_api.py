import requests
import xml.etree.ElementTree as ET

url = 'http://www.law.go.kr/DRF/lawSearch.do'
params = {
    'target': 'law',
    'query': '지방자치단체를 당사자로 하는 계약에 관한 법률',
    'display': 1,
    'OC': 'busanproduct1',
    'type': 'XML'
}

try:
    print('법제처 API 호출 시도 중...')
    response = requests.get(url, params=params, timeout=10)
    print(f'HTTP Status: {response.status_code}')
    if response.status_code == 200:
        if len(response.content) < 100:
            print(f'응답이 너무 짧습니다: {response.content}')
        else:
            try:
                root = ET.fromstring(response.content)
                law_items = root.findall('.//law')
                print(f'검색된 법령 수: {len(law_items)}')
                if law_items:
                    name_el = law_items[0].find("법령명한글")
                    if name_el is None:
                        name_el = law_items[0].find("법령명_한글")
                    print(f'첫 번째 결과 법령명: {name_el.text if name_el is not None else "Unknown"}')
                print('✅ 정상적으로 응답을 수신했습니다 (차단 해제 확인됨).')
            except ET.ParseError:
                print('응답이 XML 형태가 아닙니다. 여전히 차단 페이지일 수 있습니다.')
                print(response.text[:200])
    else:
        print('오류 응답을 받았습니다.')
except Exception as e:
    print(f'❌ 연결 실패: {e}')
