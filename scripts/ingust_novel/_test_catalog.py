import httpx, re

url = 'https://www.readnovel.com/chapterlist/17821913206588004'
resp = httpx.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
print('status:', resp.status_code)

# 提取章节链接
links = re.findall(r'href=["\'](/chapter/17821913206588004/\d+)["\']', resp.text)
print(f'found {len(links)} chapter links')
print(links[:10])
print(links[-5:])

# 也尝试提取标题
titles = re.findall(r'<a[^>]*href=["\']/chapter/17821913206588004/\d+["\'][^>]*>([^<]+)</a>', resp.text)
print(f'found {len(titles)} titles')
if titles:
    print(titles[:10])
