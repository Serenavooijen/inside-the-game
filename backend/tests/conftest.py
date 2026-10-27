"""The tests run without a model and without network: they never read the local backend/.env files."""
import os

os.environ["ITG_ENV_FILES"] = ""
