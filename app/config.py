import os
try:
	from dotenv import load_dotenv
	# Load .env if present (developer can create a .env file)
	load_dotenv()
except Exception:
	# dotenv is optional in some environments (e.g., CI/test)
	pass

# Model selection via environment variable for safety and flexibility
MODEL = os.getenv("MODEL", "qwen2.5:3b-instruct")