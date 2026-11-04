#!/bin/bash
hermes config set provider $AI_PROVIDER
hermes config set api_key $AI_API_KEY
hermes config set telegram.token $TELEGRAM_BOT_TOKEN
hermes config set telegram.allowed_users $TELEGRAM_USER_ID
exec hermes gateway run --platform telegram
