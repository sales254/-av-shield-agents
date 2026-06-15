f = open('email_agent.py', encoding='utf-8').read()
# Add MANAGED_EMAIL_ACCOUNTS import from config at the top after other imports
old = 'from config import'
new = 'from config import MANAGED_EMAIL_ACCOUNTS\nfrom config import'
if 'MANAGED_EMAIL_ACCOUNTS' not in f:
    f = f.replace(old, new, 1)
open('email_agent.py', 'w', encoding='utf-8').write(f)
print('Done')