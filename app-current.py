#!/usr/bin/env python
# coding: utf-8

# In[2]:


from flask import Flask, render_template, request, redirect, url_for
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote

# 우리말샘 API 설정
API_KEY = "561433A49188D3CB67FEDC2120EC2C87"
SEARCH_URL = "https://opendict.korean.go.kr/api/search"
VIEW_URL = "https://opendict.korean.go.kr/api/view"

class OpenDictAPI:
    """우리말샘 API 클래스"""
    
    @staticmethod
    def search_word(query, num=20):
        """단어 검색 - 어휘만 검색"""
        try:
            params = {
                'key': API_KEY,
                'q': query,
                'req_type': 'xml',
                'num': num,
                'target': 1,  # 1: 어휘만 검색
            }
            
            response = requests.get(SEARCH_URL, params=params, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            items = list(root.iter('item'))
            
            # 표제어별로 그룹화하고 첫 번째 의미만 추출
            word_groups = {}
            
            for item in items:
                word = item.findtext('word')
                if not word:
                    continue
                
                if word not in word_groups:
                    # 첫 번째 sense에서 기본 정보만 추출
                    first_sense = item.find('sense')
                    if first_sense is not None:
                        target_code = first_sense.findtext('target_code')
                        definition = first_sense.findtext('definition', '')
                        
                        word_groups[word] = {
                            'word': word,
                            'target_code': target_code,
                            'definition': definition[:80] + '...' if len(definition) > 80 else definition,
                            'order': len(word_groups) + 1
                        }
            
            return list(word_groups.values())
            
        except Exception as e:
            print(f"API 검색 오류: {e}")
            return []
    
    @staticmethod
    def get_word_details(target_code):
        """단어 상세 정보 조회"""
        try:
            params = {
                'key': API_KEY,
                'method': 'target_code',
                'q': target_code,
                'req_type': 'xml',
            }
            
            response = requests.get(VIEW_URL, params=params, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            # 상세 정보 파싱
            word_info = root.find('.//wordInfo')
            sense_info = root.find('.//senseInfo')
            
            if word_info is None or sense_info is None:
                return None
            
            # 기본 정보
            word = word_info.findtext('word', '')
            
            # 발음 정보
            pronunciation = ''
            pron_infos = word_info.findall('pronunciation_info')
            if pron_infos:
                pronunciation = pron_infos[0].findtext('pronunciation', '')
            
            # 뜻풀이
            definition = sense_info.findtext('definition', '')
            
            # 규범 유형, 품사, type2
            norm_type = sense_info.findtext('norm_grade', '')
            pos = sense_info.findtext('pos', '')
            type2 = sense_info.findtext('type2', '')
            
            # 유의어 (비슷한 말) - relation_info에서 link_target_code 사용
            synonyms = []
            relation_infos = sense_info.findall('relation_info')
            for relation_info in relation_infos:
                relation_type = relation_info.findtext('type')
                if relation_type == '유의어':
                    link_target_code = relation_info.findtext('link_target_code')
                    if link_target_code:
                        synonyms.append(link_target_code)
            
            # 관련 어휘 (참고 어휘) - relation_info에서 link_target_code 사용
            related_words = []
            for relation_info in relation_infos:
                relation_type = relation_info.findtext('type')
                if relation_type in ['참고어휘', '관련어']:
                    link_target_code = relation_info.findtext('link_target_code')
                    if link_target_code:
                        related_words.append(link_target_code)
            
            # 용례
            examples = []
            example_infos = sense_info.findall('example_info')
            for ex_info in example_infos:
                example = ex_info.findtext('example')
                if example:
                    # {표제어} 부분 제거
                    cleaned_example = example.replace(f'{{{word}}}', word)
                    examples.append(cleaned_example)
            
            # 속담
            proverbs = []
            proverb_infos = sense_info.findall('proverb_info')
            for prov_info in proverb_infos:
                proverb = prov_info.findtext('proverb')
                if proverb:
                    # {표제어} 부분 제거
                    cleaned_proverb = proverb.replace(f'{{{word}}}', word)
                    proverbs.append(cleaned_proverb)
            
            return {
                'word': word,
                'pronunciation': pronunciation,
                'definition': definition,
                'norm_type': norm_type,
                'pos': pos,
                'type2': type2,
                'synonyms': synonyms,
                'related_words': related_words,
                'examples': examples,
                'proverbs': proverbs
            }
            
        except Exception as e:
            print(f"API 상세 조회 오류: {e}")
            return None

def truncate_korean(text, max_length):
    """한글 텍스트를 지정된 길이로 자르기"""
    if len(text) <= max_length:
        return text
    return text[:max_length-1] + "…"

# Flask 애플리케이션 초기화
app = Flask(__name__)

@app.route('/')
def index():
    """메인 페이지"""
    return '''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <title>한국어 사전 - 우리말샘 연동</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="description" content="한국어 표준사전, 우리말샘 API 연동 사전 서비스">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.95);
                padding: 60px 40px;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                text-align: center;
                backdrop-filter: blur(10px);
                max-width: 600px;
                width: 90%;
            }
            .logo { 
                font-size: 48px; 
                font-weight: bold;
                background: linear-gradient(45deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 20px; 
            }
            .subtitle {
                color: #666;
                font-size: 18px;
                margin-bottom: 40px;
            }
            .search-form {
                display: flex;
                gap: 15px;
                margin-bottom: 30px;
            }
            .search-input { 
                flex: 1;
                padding: 18px 25px; 
                font-size: 18px; 
                border: 2px solid #e0e0e0; 
                border-radius: 50px;
                outline: none;
                transition: all 0.3s ease;
            }
            .search-input:focus {
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            .search-btn { 
                padding: 18px 35px; 
                font-size: 18px; 
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white; 
                border: none; 
                border-radius: 50px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            .search-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }
            .feature {
                padding: 20px;
                background: rgba(102, 126, 234, 0.1);
                border-radius: 15px;
                color: #333;
            }
            .feature-icon {
                font-size: 32px;
                margin-bottom: 10px;
            }
            .feature-text {
                font-size: 14px;
                font-weight: 500;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">한국어 사전</div>
            <div class="subtitle">우리말샘 API 연동 • 표준국어대사전</div>
            
            <form class="search-form" action="/search" method="get">
                <input type="text" name="q" class="search-input" 
                       placeholder="검색할 단어를 입력하세요" required 
                       autocomplete="off">
                <button type="submit" class="search-btn">검색</button>
            </form>
            
            <div class="features">
                <div class="feature">
                    <div class="feature-icon">📚</div>
                    <div class="feature-text">표준 사전</div>
                </div>
                <div class="feature">
                    <div class="feature-icon">🔊</div>
                    <div class="feature-text">발음 정보</div>
                </div>
                <div class="feature">
                    <div class="feature-icon">📝</div>
                    <div class="feature-text">용례 제공</div>
                </div>
                <div class="feature">
                    <div class="feature-icon">🔗</div>
                    <div class="feature-text">관련 어휘</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/search')
def search():
    """검색 결과 페이지 - 표제어 목록"""
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('index'))
    
    # API에서 검색 결과 가져오기
    search_results = OpenDictAPI.search_word(query)
    
    if not search_results:
        return render_no_results(query)
    
    return render_search_list(query, search_results)

@app.route('/word/<word>/<int:num>')
def word_detail(word, num):
    """단어 상세 페이지"""
    # URL에서 디코딩
    decoded_word = unquote(word)
    
    # 먼저 검색해서 해당 순번의 target_code 찾기
    search_results = OpenDictAPI.search_word(decoded_word)
    
    if not search_results or num > len(search_results) or num < 1:
        return "단어를 찾을 수 없습니다.", 404
    
    target_code = search_results[num-1]['target_code']
    word_data = OpenDictAPI.get_word_details(target_code)
    
    if not word_data:
        return "단어를 찾을 수 없습니다.", 404
    
    return render_word_detail(word_data)

def render_no_results(query):
    """검색 결과 없음 페이지"""
    return f'''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <title>검색 결과 없음 - 한국어 사전</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Noto Sans KR', Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .logo {{ color: #667eea; font-size: 28px; font-weight: bold; margin-bottom: 20px; }}
            .search-form {{ margin: 20px 0; }}
            .search-input {{ padding: 12px; font-size: 16px; width: 300px; border: 2px solid #ddd; border-radius: 25px; }}
            .search-btn {{ padding: 12px 20px; background: #667eea; color: white; border: none; border-radius: 25px; cursor: pointer; }}
            .no-results {{ text-align: center; margin: 50px 0; color: #666; }}
            .suggestions {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo"><a href="/" style="text-decoration:none; color:#667eea;">한국어 사전</a></div>
            <form class="search-form" action="/search" method="get">
                <input type="text" name="q" class="search-input" value="{query}" required>
                <button type="submit" class="search-btn">다시 검색</button>
            </form>
        </div>
        
        <div class="no-results">
            <h2>"{query}"에 대한 검색 결과가 없습니다.</h2>
            <p>다른 검색어로 시도해보세요.</p>
        </div>
        
        <div class="suggestions">
            <h3>💡 검색 팁</h3>
            <ul>
                <li>단어의 정확한 표기를 확인해보세요</li>
                <li>유사한 의미의 다른 단어로 검색해보세요</li>
                <li>단어의 일부만으로 검색해보세요</li>
            </ul>
        </div>
    </body>
    </html>
    '''

def render_search_list(query, search_results):
    """검색 결과 목록 페이지"""
    html = f'''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <title>"{query}" 검색결과 - 한국어 사전</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="description" content="{query} 단어 검색결과, 한국어 표준사전">
        <style>
            body {{ 
                font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif; 
                max-width: 900px; 
                margin: 0 auto; 
                padding: 20px; 
                line-height: 1.6; 
                background: #f8f9fa;
            }}
            .header {{ 
                text-align: center; 
                margin-bottom: 30px; 
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .logo {{ 
                color: #667eea; 
                font-size: 28px; 
                font-weight: bold; 
                margin-bottom: 20px; 
            }}
            .search-form {{ margin: 20px 0; }}
            .search-input {{ 
                padding: 12px 20px; 
                font-size: 16px; 
                width: 300px; 
                border: 2px solid #e0e0e0; 
                border-radius: 25px; 
                outline: none;
            }}
            .search-input:focus {{ border-color: #667eea; }}
            .search-btn {{ 
                padding: 12px 25px; 
                font-size: 16px; 
                background: #667eea; 
                color: white; 
                border: none; 
                border-radius: 25px; 
                cursor: pointer; 
                margin-left: 10px;
                transition: all 0.3s ease;
            }}
            .search-btn:hover {{ background: #5a6fd8; }}
            .results-info {{ 
                color: #666; 
                margin: 20px 0; 
                font-size: 18px; 
                text-align: center;
                font-weight: 600;
            }}
            .word-item {{ 
                background: white;
                border: 1px solid #e0e0e0; 
                margin: 15px 0; 
                padding: 25px; 
                border-radius: 15px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                transition: all 0.3s ease;
                text-decoration: none;
                color: inherit;
                display: block;
                position: relative;
            }}
            .word-item:hover {{
                transform: translateY(-3px);
                box-shadow: 0 12px 30px rgba(102, 126, 234, 0.15);
                text-decoration: none;
                color: inherit;
                border-color: #667eea;
            }}
            .word-title {{ 
                font-size: 26px; 
                font-weight: bold; 
                color: #667eea; 
                margin-bottom: 15px; 
                cursor: pointer;
                transition: color 0.3s ease;
            }}
            .word-item:hover .word-title {{
                color: #5a6fd8;
            }}
            .word-definition {{ 
                color: #555; 
                font-size: 16px; 
                line-height: 1.6;
                margin: 15px 0;
            }}
            .detail-btn {{
                position: absolute;
                top: 25px;
                right: 25px;
                background: #667eea;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                transition: all 0.3s ease;
            }}
            .word-item:hover .detail-btn {{
                background: #5a6fd8;
                transform: scale(1.05);
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">
                <a href="/" style="text-decoration:none; color:#667eea;">한국어 사전</a>
            </div>
            <form class="search-form" action="/search" method="get">
                <input type="text" name="q" class="search-input" value="{query}" 
                       placeholder="검색할 단어를 입력하세요" required>
                <button type="submit" class="search-btn">검색</button>
            </form>
        </div>
        
        <div class="results-info">{query}의 의미</div>
    '''
    
    for result in search_results:
        word_encoded = quote(result['word'], safe='')
        html += f'''
        <a href="/word/{word_encoded}/{result['order']}" class="word-item">
            <div class="word-title">{result['word']}</div>
            <div class="word-definition">{result['definition']}</div>
            <div class="detail-btn">자세히 보기</div>
        </a>
        '''
    
    html += '''
    </body>
    </html>
    '''
    
    return html

def render_word_detail(word_data):
    """단어 상세 페이지"""
    word = word_data['word']
    definition = word_data['definition']
    
    # SEO 최적화를 위한 메타 정보
    title = truncate_korean(f"{word} 뜻과 의미 : {definition}", 35)
    description = truncate_korean(f"{word} 뜻 의미 : {definition}, {word_data.get('norm_type', '')} {word_data.get('pos', '')} {word_data.get('type2', '')}", 45)
    h1_title = truncate_korean(f"{word}의 뜻과 의미", 15)
    
    html = f'''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <title>{title}</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="description" content="{description}">
        <style>
            body {{ 
                font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif; 
                max-width: 900px; 
                margin: 0 auto; 
                padding: 20px; 
                line-height: 1.6; 
                background: #f8f9fa;
            }}
            .header {{ 
                text-align: center; 
                margin-bottom: 30px; 
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .logo {{ 
                color: #667eea; 
                font-size: 24px; 
                font-weight: bold; 
                margin-bottom: 15px; 
            }}
            .back-btn {{
                background: #667eea;
                color: white;
                padding: 10px 20px;
                border-radius: 20px;
                text-decoration: none;
                font-size: 14px;
                display: inline-block;
                margin-bottom: 15px;
            }}
            .word-container {{
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                margin-bottom: 20px;
            }}
            .page-title {{
                font-size: 28px;
                font-weight: bold;
                color: #333;
                margin-bottom: 30px;
                text-align: center;
                border-bottom: 2px solid #f0f0f0;
                padding-bottom: 20px;
            }}
            .word-title {{
                font-size: 36px;
                font-weight: bold;
                color: #333;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 20px;
            }}
            .pronunciation {{
                color: #667eea;
                font-size: 20px;
                font-weight: normal;
            }}
            .definition-text {{
                font-size: 18px;
                color: #333;
                line-height: 1.8;
                margin: 25px 0;
                padding: 20px;
                background: linear-gradient(135deg, #f8f9ff 0%, #f0f2ff 100%);
                border-left: 4px solid #667eea;
                border-radius: 10px;
            }}
            .info-tags {{
                display: flex;
                gap: 15px;
                margin: 20px 0;
                flex-wrap: wrap;
            }}
            .info-tag {{
                background: #667eea;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 500;
            }}
            .section {{
                margin: 30px 0;
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}
            .section-title {{
                font-size: 18px;
                font-weight: bold;
                color: #333;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .related-words {{
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }}
            .related-word {{
                background: #e3f2fd;
                color: #1976d2;
                padding: 6px 12px;
                border-radius: 15px;
                font-size: 14px;
            }}
            .dropdown {{
                margin: 20px 0;
            }}
            .dropdown-toggle {{
                background: #667eea;
                color: white;
                padding: 12px 20px;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 500;
                transition: all 0.3s ease;
            }}
            .dropdown-toggle:hover {{
                background: #5a6fd8;
            }}
            .dropdown-content {{
                display: none;
                margin-top: 15px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 10px;
                border-left: 4px solid #667eea;
            }}
            .dropdown-content.show {{
                display: block;
            }}
            .example-item, .proverb-item {{
                margin: 10px 0;
                padding: 12px;
                background: white;
                border-radius: 8px;
                color: #555;
                line-height: 1.6;
            }}
            .first-example {{
                background: white;
                padding: 15px;
                border-radius: 10px;
                border-left: 4px solid #667eea;
                margin: 15px 0;
                color: #555;
                line-height: 1.6;
            }}
        </style>
        <script>
            function toggleDropdown(id) {{
                const content = document.getElementById(id);
                content.classList.toggle('show');
                const button = content.previousElementSibling;
                button.textContent = content.classList.contains('show') ? 
                    button.textContent.replace('더보기', '접기') : 
                    button.textContent.replace('접기', '더보기');
            }}
        </script>
    </head>
    <body>
        <div class="header">
            <div class="logo">
                <a href="/" style="text-decoration:none; color:#667eea;">한국어 사전</a>
            </div>
            <a href="javascript:history.back()" class="back-btn">← 검색결과로 돌아가기</a>
        </div>
        
        <div class="word-container">
            <h1 class="page-title">{h1_title}</h1>
            
            <div class="word-title">
                {word}
                {f'<span class="pronunciation">[{word_data["pronunciation"]}]</span>' if word_data.get('pronunciation') else ''}
            </div>
            
            <div class="definition-text">{definition}</div>
            
            <div class="info-tags">
    '''
    
    # 규범 유형, 품사, type2 태그 추가
    if word_data.get('norm_type'):
        html += f'<span class="info-tag">{word_data["norm_type"]}</span>'
    if word_data.get('pos'):
        html += f'<span class="info-tag">{word_data["pos"]}</span>'
    if word_data.get('type2'):
        html += f'<span class="info-tag">{word_data["type2"]}</span>'
    
    html += '</div></div>'
    
    # 유의어 섹션
    if word_data.get('synonyms'):
        synonyms_str = ', '.join(word_data['synonyms'])
        html += f'''
        <div class="section">
            <div class="section-title">🔗 유의어: {synonyms_str}</div>
        </div>
        '''
    
    # 관련 단어 섹션
    if word_data.get('related_words'):
        related_str = ', '.join(word_data['related_words'])
        html += f'''
        <div class="section">
            <div class="section-title">📚 관련 단어: {related_str}</div>
        </div>
        '''
    
    # 용례 섹션
    if word_data.get('examples'):
        first_example = word_data['examples'][0]
        remaining_examples = word_data['examples'][1:]
        
        html += f'''
        <div class="section">
            <div class="section-title">📝 {word}의 활용 예시</div>
            <div class="first-example">{first_example}</div>
        '''
        
        if remaining_examples:
            html += f'''
            <div class="dropdown">
                <button class="dropdown-toggle" onclick="toggleDropdown('examples')">
                    더 많은 예시 보기 ({len(remaining_examples)}개) 더보기
                </button>
                <div class="dropdown-content" id="examples">
            '''
            for example in remaining_examples:
                html += f'<div class="example-item">{example}</div>'
            html += '</div></div>'
        
        html += '</div>'
    
    # 속담 섹션 (드롭다운)
    if word_data.get('proverbs'):
        first_proverb = word_data['proverbs'][0]
        remaining_proverbs = word_data['proverbs'][1:]
        
        html += f'''
        <div class="section">
            <div class="section-title">🎭 {word} 관련 속담</div>
            <div class="first-example">{first_proverb}</div>
        '''
        
        if remaining_proverbs:
            html += f'''
            <div class="dropdown">
                <button class="dropdown-toggle" onclick="toggleDropdown('proverbs')">
                    더 많은 속담 보기 ({len(remaining_proverbs)}개) 더보기
                </button>
                <div class="dropdown-content" id="proverbs">
            '''
            for proverb in remaining_proverbs:
                html += f'<div class="proverb-item">{proverb}</div>'
            html += '</div></div>'
        
        html += '</div>'
    
    html += '''
        <div style="text-align: center; margin: 40px 0; padding: 20px; background: linear-gradient(135deg, #e8f5e8 0%, #d4edda 100%); border-radius: 10px; color: #2e7d32; font-weight: 500;">
            🌐 자료 출처: 우리말샘 API | 국립국어원 표준국어대사전
        </div>
    </body>
    </html>
    '''
    
    return html

if __name__ == '__main__':
    import os
    # Render에서 제공하는 PORT 환경변수 사용
    port = int(os.environ.get('PORT', 5000))
    # 프로덕션 환경에서는 debug=False
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

