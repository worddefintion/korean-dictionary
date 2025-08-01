import sqlite3
from flask import Flask, render_template, request, jsonify
import requests
import xml.etree.ElementTree as ET
import threading
from datetime import datetime

# 우리말샘 API 설정
API_KEY = "561433A49188D3CB67FEDC2120EC2C87"
SEARCH_URL = "https://opendict.korean.go.kr/api/search"
VIEW_URL = "https://opendict.korean.go.kr/api/view"

class KoreanDictionary:
    def __init__(self):
        self.create_database()
        self.insert_sample_data()
    
    def create_database(self):
        """SQLite 데이터베이스 및 테이블 생성"""
        conn = sqlite3.connect('korean_dict.db')
        cursor = conn.cursor()
        
        # 단어 테이블
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            pronunciation TEXT,
            origin TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 품사 테이블
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parts_of_speech (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            abbreviation TEXT
        )
        ''')
        
        # 정의 테이블
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER,
            part_of_speech_id INTEGER,
            meaning TEXT NOT NULL,
            example TEXT,
            order_num INTEGER DEFAULT 1,
            FOREIGN KEY (word_id) REFERENCES words (id),
            FOREIGN KEY (part_of_speech_id) REFERENCES parts_of_speech (id)
        )
        ''')
        
        # 인덱스 생성
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_word ON words(word)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meaning ON definitions(meaning)')
        
        conn.commit()
        conn.close()
        print("✅ 데이터베이스가 성공적으로 생성되었습니다!")
    
    def insert_sample_data(self):
        """품사 데이터 및 샘플 단어 삽입"""
        conn = sqlite3.connect('korean_dict.db')
        cursor = conn.cursor()
        
        # 품사 데이터
        pos_data = [
            ('명사', '명'), ('동사', '동'), ('형용사', '형'), ('부사', '부'),
            ('관형사', '관'), ('감탄사', '감'), ('조사', '조'), ('어미', '어'),
        ]
        
        cursor.executemany('''
        INSERT OR IGNORE INTO parts_of_speech (name, abbreviation) 
        VALUES (?, ?)
        ''', pos_data)
        
        # 샘플 단어 데이터
        sample_words = [
            ('가을', '[가을]', '고유어'),
            ('봄', '[봄]', '고유어'),
            ('여름', '[여름]', '고유어'),
            ('겨울', '[겨울]', '고유어'),
            ('사랑', '[사랑]', '고유어'),
            ('희망', '[히망]', '한자어'),
            ('학교', '[학꾜]', '한자어'),
            ('컴퓨터', '[컴퓨터]', '외래어'),
        ]
        
        for word_data in sample_words:
            cursor.execute('''
            INSERT OR IGNORE INTO words (word, pronunciation, origin) 
            VALUES (?, ?, ?)
            ''', word_data)
        
        # 가을 단어의 정의 추가
        try:
            cursor.execute('SELECT id FROM words WHERE word = "가을"')
            word_result = cursor.fetchone()
            if word_result:
                word_id = word_result[0]
                
                cursor.execute('SELECT id FROM parts_of_speech WHERE name = "명사"')
                pos_result = cursor.fetchone()
                if pos_result:
                    pos_id = pos_result[0]
                    
                    definitions = [
                        (word_id, pos_id, '여름과 겨울 사이의 계절. 음력으로는 7, 8, 9월이고, 양력으로는 9, 10, 11월이다.', 
                         '가을이 되니 날씨가 선선해졌다.', 1),
                        (word_id, pos_id, '사물이 무르익은 때를 비유적으로 이르는 말.', 
                         '인생의 가을을 맞이하다.', 2),
                    ]
                    
                    cursor.executemany('''
                    INSERT OR IGNORE INTO definitions 
                    (word_id, part_of_speech_id, meaning, example, order_num) 
                    VALUES (?, ?, ?, ?, ?)
                    ''', definitions)
        except Exception as e:
            print(f"샘플 정의 삽입 중 오류: {e}")
        
        conn.commit()
        conn.close()
        print("✅ 샘플 데이터가 입력되었습니다!")

class OpenDictAPI:
    """우리말샘 API 클래스"""
    
    @staticmethod
    def search_word(query, num=10):
        """단어 검색"""
        try:
            params = {
                'key': API_KEY,
                'q': query,
                'req_type': 'xml',
                'num': num,
            }
            
            response = requests.get(SEARCH_URL, params=params, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            items = list(root.iter('item'))
            
            return items
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
            return root
        except Exception as e:
            print(f"API 상세 조회 오류: {e}")
            return None

# Flask 애플리케이션 초기화
app = Flask(__name__)
dict_db = KoreanDictionary()

def get_db_connection():
    """데이터베이스 연결"""
    conn = sqlite3.connect('korean_dict.db')
    conn.row_factory = sqlite3.Row
    return conn

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
            
            <form class="search-form" action="/search/m/" method="get">
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

@app.route('/search/m/')
def search_meaning():
    """검색 결과 페이지"""
    query = request.args.get('q', '').strip()
    if not query:
        return redirect_to_home("검색어를 입력해주세요.")
    
    # 1. 우리말샘 API에서 검색
    api_items = OpenDictAPI.search_word(query)
    word_groups = {}
    
    if api_items:
        # API 결과가 있는 경우
        for item in api_items[:5]:  # 상위 5개만 처리
            word = item.findtext('word')
            if not word:
                continue
                
            if word not in word_groups:
                word_groups[word] = {
                    'word': word,
                    'pronunciation': '',
                    'origin': '',
                    'definitions': []
                }
            
            # sense 정보 처리
            senses = item.findall('sense')
            for sense in senses:
                target_code = sense.findtext('target_code')
                if target_code:
                    # 상세 정보 조회
                    detail_root = OpenDictAPI.get_word_details(target_code)
                    if detail_root is not None:
                        word_info = detail_root.find('.//wordInfo')
                        sense_info = detail_root.find('.//senseInfo')
                        
                        if word_info is not None and sense_info is not None:
                            # 발음 정보
                            pron_infos = word_info.findall('pronunciation_info')
                            if pron_infos and not word_groups[word]['pronunciation']:
                                word_groups[word]['pronunciation'] = f"[{pron_infos[0].findtext('pronunciation', '')}]"
                            
                            # 어원 정보
                            word_type = word_info.findtext('word_type')
                            if word_type and not word_groups[word]['origin']:
                                word_groups[word]['origin'] = word_type
                            
                            # 의미 정보
                            pos = sense_info.findtext('pos', '명사')
                            definition = sense_info.findtext('definition', '')
                            word_type = sense_info.findtext('type', '')
                            
                            # 용례 정보
                            examples = []
                            example_infos = sense_info.findall('example_info')
                            for ex_info in example_infos[:3]:  # 최대 3개
                                example = ex_info.findtext('example')
                                if example:
                                    examples.append(example)
                            
                            word_groups[word]['definitions'].append({
                                'pos': pos,
                                'pos_abbr': pos[:1] if pos else '명',
                                'meaning': definition,
                                'examples': examples,
                                'word_type': word_type
                            })
    
    # 2. API 결과가 없으면 로컬 DB에서 검색
    if not word_groups:
        conn = get_db_connection()
        try:
            local_results = conn.execute('''
            SELECT DISTINCT w.word, w.pronunciation, w.origin,
                           d.meaning, d.example, p.name as pos_name, p.abbreviation
            FROM words w
            LEFT JOIN definitions d ON w.id = d.word_id
            LEFT JOIN parts_of_speech p ON d.part_of_speech_id = p.id
            WHERE w.word LIKE ? OR d.meaning LIKE ?
            ORDER BY w.word, d.order_num
            ''', (f'%{query}%', f'%{query}%')).fetchall()
            
            if local_results:
                for row in local_results:
                    word = row['word']
                    if word not in word_groups:
                        word_groups[word] = {
                            'word': word,
                            'pronunciation': row['pronunciation'] or '',
                            'origin': row['origin'] or '',
                            'definitions': []
                        }
                    if row['meaning']:
                        word_groups[word]['definitions'].append({
                            'pos': row['pos_name'] or '명사',
                            'pos_abbr': row['abbreviation'] or '명',
                            'meaning': row['meaning'],
                            'examples': [row['example']] if row['example'] else [],
                            'word_type': '일반어'
                        })
        finally:
            conn.close()
    
    if not word_groups:
        return render_no_results(query)
    
    return render_search_results(query, word_groups)

def redirect_to_home(message):
    """홈으로 리다이렉트"""
    return f'''
    <script>
        alert("{message}");
        window.location.href = "/";
    </script>
    '''

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
            <form class="search-form" action="/search/m/" method="get">
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

def render_search_results(query, word_groups):
    """검색 결과 페이지 렌더링"""
    html = f'''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <title>"{query}" 검색결과 - 한국어 사전</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
            }}
            .word-entry {{ 
                background: white;
                border: 1px solid #e0e0e0; 
                margin: 25px 0; 
                padding: 30px; 
                border-radius: 15px; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                transition: all 0.3s ease;
            }}
            .word-entry:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(0,0,0,0.12);
            }}
            .word-title {{ 
                font-size: 32px; 
                font-weight: bold; 
                color: #333; 
                margin-bottom: 15px; 
                display: flex;
                align-items: center;
                gap: 15px;
            }}
            .pronunciation {{ 
                color: #667eea; 
                font-size: 20px; 
                font-weight: normal;
            }}
            .origin {{ 
                color: #999; 
                font-size: 14px; 
                margin-bottom: 20px; 
                padding: 5px 12px;
                background: #f1f3f4;
                border-radius: 20px;
                display: inline-block;
            }}
            .definition {{ 
                margin: 20px 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #f8f9ff 0%, #f0f2ff 100%);
                border-left: 4px solid #667eea; 
                border-radius: 10px;
            }}
            .def-header {{
                display: flex;
                align-items: center;
                gap: 15px;
                margin-bottom: 15px;
            }}
            .pos {{ 
                color: #667eea; 
                font-weight: bold; 
                background: white;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 14px;
            }}
            .word-type {{
                color: #888;
                font-size: 12px;
                background: #f1f3f4;
                padding: 3px 8px;
                border-radius: 10px;
            }}
            .meaning {{ 
                font-size: 16px; 
                margin: 10px 0;
                color: #333;
                line-height: 1.7;
            }}
            .examples {{ 
                margin-top: 15px; 
            }}
            .example {{ 
                color: #555; 
                font-style: italic; 
                margin: 8px 0; 
                padding: 10px 15px; 
                background: rgba(255,255,255,0.7); 
                border-radius: 8px; 
                border-left: 3px solid #667eea;
            }}
            .api-source {{ 
                text-align: center; 
                margin-top: 40px; 
                padding: 20px; 
                background: linear-gradient(135deg, #e8f5e8 0%, #d4edda 100%);
                border-radius: 10px; 
                color: #2e7d32; 
                font-weight: 500;
            }}
            .definition-number {{
                background: #667eea;
                color: white;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">
                <a href="/" style="text-decoration:none; color:#667eea;">한국어 사전</a>
            </div>
            <form class="search-form" action="/search/m/" method="get">
                <input type="text" name="q" class="search-input" value="{query}" 
                       placeholder="검색할 단어를 입력하세요" required>
                <button type="submit" class="search-btn">검색</button>
            </form>
        </div>
        
        <div class="results-info">"{query}" 검색결과 ({len(word_groups)}개)</div>
    '''
    
    for word_data in word_groups.values():
        html += f'''
        <div class="word-entry">
            <div class="word-title">
                {word_data['word']}
                <span class="pronunciation">{word_data['pronunciation']}</span>
            </div>
            {f'<div class="origin">{word_data["origin"]}</div>' if word_data['origin'] else ''}
        '''
        
        for i, definition in enumerate(word_data['definitions'], 1):
            html += f'''
            <div class="definition">
                <div class="def-header">
                    <div class="definition-number">{i}</div>
                    <span class="pos">{definition['pos']}</span>
                    {f'<span class="word-type">{definition["word_type"]}</span>' if definition.get('word_type') else ''}
                </div>
                <div class="meaning">{definition['meaning']}</div>
            '''
            
            if definition.get('examples'):
                html += '<div class="examples">'
                for example in definition['examples']:
                    html += f'<div class="example">예: {example}</div>'
                html += '</div>'
            
            html += '</div>'
        
        html += '</div>'
    
    # API 사용 정보
    source_info = "우리말샘 API" if any(word_groups.values()) else "로컬 데이터베이스"
    html += f'''
        <div class="api-source">
            🌐 검색 결과: {source_info} 제공 | 국립국어원 표준국어대사전
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
