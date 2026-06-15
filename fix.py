import re

for filename in ['voice_agent.py', 'email_agent.py']:
    c = open(filename, encoding='utf-8').read()
    if 'import re' not in c:
        c = 'import re\n' + c
    old = 'result = json.loads(response.content[0].text)'
    new = "raw=response.content[0].text; raw=re.sub(r'```json\\s*','',raw); raw=re.sub(r'```\\s*','',raw); result=json.loads(raw.strip())"
    c = c.replace(old, new)
    open(filename, 'w', encoding='utf-8').write(c)
    print(f'Fixed {filename}')