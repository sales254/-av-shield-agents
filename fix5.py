import re

# Fix sasha_qualifier - escape ALL remaining {name} instances
f = open('sasha_qualifier.py', encoding='utf-8').read()
f = f.replace('{name}', '{{name}}')
open('sasha_qualifier.py', 'w', encoding='utf-8').write(f)
print('sasha_qualifier done')

# Fix voice_agent
f = open('voice_agent.py', encoding='utf-8').read()
f = f.replace('{name}', '{{name}}')
f = f.replace('{First Name}', '{{First Name}}')
open('voice_agent.py', 'w', encoding='utf-8').write(f)
print('voice_agent done')