import os
import sys

# Prepend the stub modules directory so imports like `import flask` resolve to
# our lightweight test doubles instead of any real packages that may be
# installed in the environment.
STUBS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "stubs"))
sys.path.insert(0, STUBS_PATH)

# Ensure project root is on ``sys.path`` for test imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
