"""Streamlit Web 界面启动器

用法:
    python web/launch.py

或双击运行（需在项目根目录）
"""

import os
import subprocess
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 禁用 Streamlit telemetry 弹窗
os.environ["STREAMLIT_TELEMETRY_OPT_OUT"] = "1"
os.environ["STREAMLIT_BROWSER_GATHERUSAGESTATS"] = "false"

# 确保绑定到 127.0.0.1（避免 localhost IPv6 解析问题）
os.environ["STREAMLIT_SERVER_ADDRESS"] = "127.0.0.1"
os.environ["STREAMLIT_SERVER_PORT"] = "8501"
os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"

# 找到 streamlit 可执行文件
venv_scripts = PROJECT_ROOT / ".venv" / "Scripts"
if sys.platform == "win32":
    streamlit_exe = venv_scripts / "streamlit.exe"
else:
    streamlit_exe = venv_scripts / "streamlit"

# 优先使用虚拟环境中的 streamlit
if streamlit_exe.exists():
    cmd = [str(streamlit_exe), "run", str(PROJECT_ROOT / "web" / "streamlit_app.py")]
else:
    # 回退到系统 PATH 中的 streamlit
    cmd = ["streamlit", "run", str(PROJECT_ROOT / "web" / "streamlit_app.py")]

print("=" * 50)
print("Starting Paper Crawler Web UI...")
print("=" * 50)
print()
print("When ready, open in your browser:")
print("  http://127.0.0.1:8501")
print()
print("Press Ctrl+C to stop")
print()

try:
    subprocess.run(cmd, cwd=str(PROJECT_ROOT))
except KeyboardInterrupt:
    print("\nStopped.")
except FileNotFoundError:
    print("ERROR: streamlit not found.")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)
