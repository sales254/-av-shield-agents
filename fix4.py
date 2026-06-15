f = open('email_agent.py', encoding='utf-8').read()
old = 'return json.loads(response.content[0].text)'
new = "raw=response.content[0].text; raw=raw.replace('```json','').replace('```',''); return json.loads(raw.strip())"
f = f.replace(old, new)
open('email_agent.py', 'w', encoding='utf-8').write(f)
print('Done')