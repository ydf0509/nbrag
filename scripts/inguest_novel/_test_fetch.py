import httpx, re

url = 'https://www.readnovel.com/chapter/17821913206588004/47997170737459572'
resp = httpx.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
print('status:', resp.status_code)

# 尝试常见的正文容器
found = False
for cls in ['read-content', 'chapter-content', 'txt', 'content', 'main-content', 'j_readContent']:
    pattern = rf'<div[^>]*class=["\'][^"\']*{cls}[^"\']*["\'][^>]*>(.*?)</div>'
    m = re.search(pattern, resp.text, re.DOTALL)
    if m:
        print(f'found class: {cls}')
        print(m.group(1)[:800])
        found = True
        break

if not found:
    # 尝试 id
    for id_name in ['content', 'chapterContent', 'txt', 'read-content']:
        pattern = rf'<div[^>]*id=["\']{id_name}["\'][^>]*>(.*?)</div>'
        m = re.search(pattern, resp.text, re.DOTALL)
        if m:
            print(f'found id: {id_name}')
            print(m.group(1)[:800])
            found = True
            break

if not found:
    print('no common content container found')
    # 打印 HTML 中靠近 "第一章" 的部分
    idx = resp.text.find('第一章')
    if idx > 0:
        print(resp.text[max(0,idx-200):idx+800])
    else:
        print(resp.text[5000:6000])
