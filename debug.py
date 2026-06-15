from email_agent import EmailAgent
import traceback

agent = EmailAgent()
try:
    email = {
        "id": "test123",
        "sender": "test@test.com",
        "subject": "Need security cameras",
        "body": "I need security cameras for my 200 unit apartment complex"
    }
    result = agent.handle_email(email)
    print('OK:', result)
except Exception as e:
    traceback.print_exc()