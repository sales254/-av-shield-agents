f = open('email_agent.py', encoding='utf-8').read()
# Escape the JSON template braces in the prompt
f = f.replace(
    '{\n  "classification"',
    '{{\n  "classification"'
)
f = f.replace(
    '"action": "reply|label|ignore|escalate"\n}',
    '"action": "reply|label|ignore|escalate"\n}}'
)
open('email_agent.py', 'w', encoding='utf-8').write(f)
print('Done')