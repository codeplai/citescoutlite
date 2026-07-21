import urllib.request
import re
from collections import Counter
from urllib.parse import urljoin

try:
    base_url = 'https://citeagrochavimochic.itp.gob.pe/'
    req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    
    css_links = set(re.findall(r'href=[\'"]([^\'"]+\.css)[^\'"]*[\'"]', html, re.IGNORECASE))
    
    colors = []
    colors.extend(re.findall(r'#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}', html))
    
    for link in css_links:
        full_url = urljoin(base_url, link)
        try:
            css_req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
            css_content = urllib.request.urlopen(css_req).read().decode('utf-8', errors='ignore')
            colors.extend(re.findall(r'#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}', css_content))
        except Exception as e:
            pass
            
    print("Found colors:")
    for color, count in Counter(colors).most_common(20):
        print(f"{color.upper()}: {count}")
except Exception as e:
    print(f"Error: {e}")
