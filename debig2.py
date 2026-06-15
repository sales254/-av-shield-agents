from email_agent import EmailAgent
import traceback

agent = EmailAgent()
try:
    result = agent.process_email(
        sender="test@test.com",
        subject="Test",
        body="I need security cameras for my apartment complex"
    )
    print('OK:', result)
except Exception as e:
    traceback.print_exc()