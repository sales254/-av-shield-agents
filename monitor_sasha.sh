#!/bin/bash
# Monitor Sasha — restart if down, alert if repeated crashes
STATE_FILE="/tmp/sasha_monitor_state"

if ! systemctl is-active --quiet sasha; then
    echo "[$(date)] Sasha DOWN — restarting"
    systemctl restart sasha
    sleep 5
    if ! systemctl is-active --quiet sasha; then
        FAIL_COUNT=$(($(cat $STATE_FILE 2>/dev/null || echo 0) + 1))
        echo $FAIL_COUNT > $STATE_FILE
        if [ $FAIL_COUNT -ge 3 ]; then
            python3 << 'ENDPY'
import os
from twilio.rest import Client
try:
    client = Client(os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN"))
    client.messages.create(body="SASHA ALERT: 3+ crashes. Manual restart needed.",
        from_=os.environ.get("TWILIO_PHONE_NUMBER"), to="+16613177321")
except Exception as e:
    pass
ENDPY
        fi
    else
        echo 0 > $STATE_FILE
    fi
else
    echo 0 > $STATE_FILE
fi
